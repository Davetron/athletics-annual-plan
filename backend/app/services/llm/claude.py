"""
Claude LLM provider.

Uses the Anthropic Messages API via httpx for plan generation (tool_use)
and competition search (web_search).
"""

import json

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"


async def generate_plan(
    system_prompt: str,
    context_message: str,
    tool: dict,
    api_key: str,
) -> dict:
    """
    Generate a training plan using Claude tool_use.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
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
            print(f"[DEBUG] Generate plan API error: {response.status_code} - {error_detail}")
            return {
                "success": False,
                "error": f"Failed to generate plan (status {response.status_code}). Please try again.",
            }

        data = response.json()

        # Extract the tool use result
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

        # Validate basic structure
        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Plan has {len(weeks)} weeks instead of 52")
            print(f"[DEBUG] Stop reason: {data.get('stop_reason')}")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}


async def search_competitions(
    prompt: str,
    api_key: str,
) -> list[dict] | None:
    """
    Search for competitions using Claude web_search.

    Returns list of competition dicts, or None if no JSON found.
    Raises httpx exceptions on network errors.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 4096,
                "temperature": 0,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Search API error: {response.status_code} - {error_detail}")
            return None

        data = response.json()

        # Extract text from response (handles multiple content blocks)
        response_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                response_text += block.get("text", "")

        print(f"[DEBUG] Claude search response ({len(response_text)} chars)")

        # Parse JSON array from response
        return _extract_competitions_json(response_text)


def _extract_competitions_json(text: str) -> list[dict] | None:
    """Extract a JSON array of competitions from response text."""
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
