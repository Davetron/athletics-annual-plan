"""
Gemini LLM provider.

Uses the Gemini REST API via httpx for plan generation (function calling)
and competition search (Google Search grounding).
"""

import json

import httpx

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-2.5-flash-lite"

# Keys in Claude's JSON Schema that Gemini's OpenAPI subset doesn't support
_UNSUPPORTED_SCHEMA_KEYS = {"minItems", "maxItems", "minimum", "maximum"}


def translate_tool_to_gemini(claude_tool: dict) -> dict:
    """Convert a Claude tool_use definition to a Gemini function declaration."""
    return {
        "name": claude_tool["name"],
        "description": claude_tool["description"],
        "parameters": _translate_schema(claude_tool["input_schema"]),
    }


def _translate_schema(schema: dict) -> dict:
    """Recursively translate JSON Schema to Gemini's OpenAPI subset."""
    result = {}

    # Handle type (may be a list like ["integer", "null"])
    type_val = schema.get("type")
    if isinstance(type_val, list):
        non_null = [t for t in type_val if t != "null"]
        result["type"] = non_null[0] if non_null else "string"
        if "null" in type_val:
            result["nullable"] = True
    elif type_val:
        result["type"] = type_val

    # Copy supported fields
    for key in ("description", "enum", "required"):
        if key in schema:
            result[key] = schema[key]

    # Recurse into properties
    if "properties" in schema:
        result["properties"] = {
            k: _translate_schema(v) for k, v in schema["properties"].items()
        }

    # Recurse into array items
    if "items" in schema:
        result["items"] = _translate_schema(schema["items"])

    # Unsupported keys (minItems, maxItems, minimum, maximum) are simply omitted

    return result


async def generate_plan(
    system_prompt: str,
    context_message: str,
    tool: dict,
    api_key: str,
) -> dict:
    """
    Generate a training plan using Gemini function calling.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    gemini_func = translate_tool_to_gemini(tool)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/models/{MODEL}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
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
                    "maxOutputTokens": 16384,
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

        # Extract function call from response
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
            return {
                "success": False,
                "error": "Failed to generate structured plan. Please try again.",
            }

        # Validate basic structure
        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Gemini plan has {len(weeks)} weeks instead of 52")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}
