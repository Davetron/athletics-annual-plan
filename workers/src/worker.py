"""
Cloudflare Workers entry point - minimal implementation without FastAPI.
Uses JS APIs directly to avoid startup CPU limits.
"""

from js import Response, JSON, Object, Headers
import json


async def on_fetch(request, env):
    """Handle incoming HTTP requests."""
    url = request.url
    method = request.method
    path = url.split("//")[1].split("/", 1)[1] if "//" in url else "/"
    path = "/" + path.split("?")[0] if "?" in path else "/" + path

    # CORS headers
    cors_headers = {
        "Access-Control-Allow-Origin": getattr(env, "CORS_ORIGIN", "*"),
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-Session-ID",
    }

    # Handle OPTIONS preflight
    if method == "OPTIONS":
        return Response.new("", headers=Object.fromEntries([[k, v] for k, v in cors_headers.items()]))

    # Simple routing
    if path in ("/", ""):
        return json_response({"status": "ok", "service": "athletics-annual-plan-api"}, cors_headers)

    if path == "/health":
        return json_response({"status": "healthy"}, cors_headers)

    if path == "/api/generate-plan" and method == "POST":
        return await handle_generate_plan(request, env, cors_headers)

    if path == "/api/download-excel" and method == "POST":
        return await handle_download_excel(request, cors_headers)

    if path == "/api/chat" and method == "POST":
        return await handle_chat(request, env, cors_headers)

    return json_response({"error": "Not found"}, cors_headers, 404)


def json_response(data, cors_headers, status=200):
    """Create a JSON response with CORS headers."""
    headers = Headers.new()
    headers.set("Content-Type", "application/json")
    for k, v in cors_headers.items():
        headers.set(k, v)
    return Response.new(json.dumps(data), status=status, headers=headers)


async def handle_generate_plan(request, env, cors_headers):
    """Handle plan generation request."""
    # Lazy import heavy modules
    import httpx
    from plan_generator import GENERATE_PLAN_TOOL, GENERATION_SYSTEM_PROMPT, build_context_message

    # Check session ID
    session_id = request.headers.get("X-Session-ID")
    if not session_id:
        return json_response({"success": False, "error": "Session ID required"}, cors_headers, 401)

    api_key = getattr(env, "CLAUDE_API_KEY", None)
    if not api_key:
        return json_response({"success": False, "error": "Claude API key not configured"}, cors_headers, 500)

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))  # Convert JS object to Python dict
        form_data = body.get("formData", {})
        messages = body.get("messages")

        context_message = build_context_message(form_data, messages)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 16384,
                    "system": GENERATION_SYSTEM_PROMPT,
                    "tools": [GENERATE_PLAN_TOOL],
                    "tool_choice": {"type": "tool", "name": "generate_annual_plan"},
                    "messages": [{"role": "user", "content": context_message}],
                },
                timeout=120.0,
            )

            if response.status_code != 200:
                return json_response(
                    {"success": False, "error": f"Failed to generate plan (status {response.status_code})"},
                    cors_headers,
                )

            data = response.json()

            # Extract tool use result
            tool_use = None
            for block in data.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "generate_annual_plan":
                    tool_use = block
                    break

            if not tool_use:
                return json_response(
                    {"success": False, "error": "Failed to generate structured plan"},
                    cors_headers,
                )

            plan = tool_use.get("input", {})
            weeks = plan.get("weeks", [])

            if len(weeks) != 52:
                return json_response(
                    {"success": False, "error": f"Generated plan was incomplete ({len(weeks)} weeks)"},
                    cors_headers,
                )

            return json_response({"success": True, "plan": plan}, cors_headers)

    except Exception as e:
        return json_response({"success": False, "error": str(e)}, cors_headers)


async def handle_download_excel(request, cors_headers):
    """Handle Excel download request."""
    # Lazy import heavy modules
    from io import BytesIO
    from excel_generator import generate_excel_from_plan

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))
        plan = body.get("plan", {})

        workbook = generate_excel_from_plan(plan)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        athlete_safe = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in plan.get("athlete", "Athlete")
        ).strip()
        season_safe = plan.get("season", "Season").replace("/", "-")
        filename = f"{athlete_safe}_Annual_Plan_{season_safe}.xlsx"

        headers = Headers.new()
        headers.set("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        headers.set("Content-Disposition", f'attachment; filename="{filename}"')
        for k, v in cors_headers.items():
            headers.set(k, v)

        return Response.new(output.getvalue(), headers=headers)

    except Exception as e:
        return json_response({"error": f"Failed to generate Excel file: {str(e)}"}, cors_headers, 500)


async def handle_chat(request, env, cors_headers):
    """Handle chat request."""
    # Lazy import
    import httpx

    api_key = getattr(env, "CLAUDE_API_KEY", None)
    if not api_key:
        return json_response({"error": "Claude API key not configured"}, cors_headers, 500)

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "system": body.get("system") or "You are a helpful athletics coaching assistant.",
                    "messages": body.get("messages", []),
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                return json_response({"error": "Chat request failed"}, cors_headers, response.status_code)

            data = response.json()
            return json_response({
                "content": data.get("content", []),
                "model": data.get("model"),
                "stop_reason": data.get("stop_reason"),
            }, cors_headers)

    except Exception as e:
        return json_response({"error": str(e)}, cors_headers, 500)
