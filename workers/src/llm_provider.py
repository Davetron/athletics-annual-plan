"""
LLM provider abstraction for the Cloudflare Python Worker.

Supports Claude (Anthropic) and Gemini (Google) via env var LLM_PROVIDER.
All httpx requests include "Accept-Encoding: identity" for Pyodide compatibility.
"""

import json

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash-lite"


# ---------------------------------------------------------------------------
# Schema translation (Claude tool_use → Gemini functionDeclarations)
# ---------------------------------------------------------------------------

def translate_tool_to_gemini(claude_tool):
    """Convert a Claude tool_use definition to a Gemini function declaration."""
    return {
        "name": claude_tool["name"],
        "description": claude_tool["description"],
        "parameters": _translate_schema(claude_tool["input_schema"]),
    }


def _translate_schema(schema):
    """Recursively translate JSON Schema to Gemini's OpenAPI subset.

    - Handles nullable union types like ["integer", "null"]
    - Strips unsupported keys: minItems, maxItems, minimum, maximum
    """
    result = {}

    type_val = schema.get("type")
    if isinstance(type_val, list):
        non_null = [t for t in type_val if t != "null"]
        result["type"] = non_null[0] if non_null else "string"
        if "null" in type_val:
            result["nullable"] = True
    elif type_val:
        result["type"] = type_val

    for key in ("description", "enum", "required"):
        if key in schema:
            result[key] = schema[key]

    if "properties" in schema:
        result["properties"] = {
            k: _translate_schema(v) for k, v in schema["properties"].items()
        }

    if "items" in schema:
        result["items"] = _translate_schema(schema["items"])

    # minItems, maxItems, minimum, maximum are intentionally omitted

    return result


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _extract_competitions_json(text):
    """Extract JSON array from response text. Returns list of dicts or None."""
    try:
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        if start_idx != -1 and end_idx > start_idx:
            raw = json.loads(text[start_idx:end_idx])
            return [
                {
                    "name": c.get("name", "Unknown"),
                    "date": c.get("date", ""),
                    "end_date": c.get("end_date"),
                    "location": c.get("location"),
                    "importance": c.get("importance", 3),
                    "type": c.get("type"),
                }
                for c in raw
                if isinstance(c, dict)
            ]
        return None
    except (json.JSONDecodeError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Claude provider
# ---------------------------------------------------------------------------

async def claude_generate_plan(system_prompt, context_message, tool, api_key):
    """
    Generate a training plan using Claude tool_use.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            CLAUDE_API_URL,
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 16384,
                "temperature": 0,
                "system": system_prompt,
                "tools": [tool],
                "tool_choice": {"type": "tool", "name": tool["name"]},
                "messages": [{"role": "user", "content": context_message}],
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Claude generate plan error: {response.status_code} - {error_detail}")
            return {
                "success": False,
                "error": f"Failed to generate plan (status {response.status_code}). Please try again.",
            }

        data = response.json()

        tool_use = None
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                tool_use = block
                break

        if not tool_use:
            return {
                "success": False,
                "error": "Failed to generate structured plan. Please try again.",
            }

        plan = tool_use.get("input", {})
        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Claude plan has {len(weeks)} weeks instead of 52")
            print(f"[DEBUG] Stop reason: {data.get('stop_reason')}")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}


async def claude_search_competitions(prompt, api_key):
    """
    Search for competitions using Claude web_search.

    Returns list of competition dicts, or None if no JSON found.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            CLAUDE_API_URL,
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 4096,
                "temperature": 0,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Claude search error: {response.status_code} - {error_detail}")
            return None

        data = response.json()

        response_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                response_text += block.get("text", "")

        print(f"[DEBUG] Claude search response ({len(response_text)} chars)")
        return _extract_competitions_json(response_text)


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

async def gemini_generate_plan(system_prompt, context_message, tool, api_key):
    """
    Generate a training plan using Gemini function calling.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    import httpx

    gemini_func = translate_tool_to_gemini(tool)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
            params={"key": api_key},
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
            },
            json={
                "systemInstruction": {
                    "parts": [{"text": system_prompt}],
                },
                "contents": [
                    {"role": "user", "parts": [{"text": context_message}]},
                ],
                "tools": [{"functionDeclarations": [gemini_func]}],
                "toolConfig": {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tool["name"]],
                    }
                },
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 32768,
                },
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Gemini generate plan error: {response.status_code} - {error_detail}")
            return {
                "success": False,
                "error": f"Failed to generate plan (status {response.status_code}). Please try again.",
            }

        data = response.json()

        plan = None
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                fc = part.get("functionCall")
                if fc and fc.get("name") == tool["name"]:
                    plan = fc.get("args", {})
                    break
            if plan is not None:
                break

        if plan is None:
            finish_reason = data.get("candidates", [{}])[0].get("finishReason", "UNKNOWN")
            print(f"[DEBUG] Gemini plan extraction failed, finishReason={finish_reason}")
            return {
                "success": False,
                "error": "Failed to generate structured plan. Please try again.",
            }

        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Gemini plan has {len(weeks)} weeks instead of 52")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}


async def gemini_search_competitions(prompt, api_key):
    """
    Search for competitions using Gemini with Google Search grounding.

    Returns list of competition dicts, or None if no JSON found.
    """
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent",
            params={"key": api_key},
            headers={
                "Content-Type": "application/json",
                "Accept-Encoding": "identity",
            },
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]},
                ],
                "tools": [{"google_search": {}}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 4096,
                },
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Gemini search error: {response.status_code} - {error_detail}")
            return None

        data = response.json()

        response_text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    response_text += part["text"]

        print(f"[DEBUG] Gemini search response ({len(response_text)} chars)")
        return _extract_competitions_json(response_text)


# ---------------------------------------------------------------------------
# Dispatcher functions
# ---------------------------------------------------------------------------

async def generate_plan(provider, system_prompt, context_message, tool, api_key):
    """Dispatch to the appropriate LLM provider for plan generation."""
    if provider == "gemini":
        return await gemini_generate_plan(system_prompt, context_message, tool, api_key)
    return await claude_generate_plan(system_prompt, context_message, tool, api_key)


async def search_competitions(provider, prompt, api_key):
    """Dispatch to the appropriate LLM provider for competition search."""
    if provider == "gemini":
        return await gemini_search_competitions(prompt, api_key)
    return await claude_search_competitions(prompt, api_key)
