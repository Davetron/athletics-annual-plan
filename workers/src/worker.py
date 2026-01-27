"""
Cloudflare Workers entry point - minimal implementation without FastAPI.
Uses JS APIs directly to avoid startup CPU limits.
"""

from js import Response, JSON, Object, Headers, Uint8Array
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

    if path == "/api/validate-code" and method == "POST":
        return await handle_validate_code(request, env, cors_headers)

    if path == "/api/search-competitions" and method == "POST":
        return await handle_search_competitions(request, env, cors_headers)

    if path == "/api/fetch-url" and method == "POST":
        return await handle_fetch_url(request, cors_headers)

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
                    "Accept-Encoding": "identity",  # Disable compression for Pyodide compatibility
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

        # Convert Python bytes to JavaScript Uint8Array for proper binary response
        excel_bytes = output.getvalue()
        js_array = Uint8Array.new(list(excel_bytes))

        return Response.new(js_array, headers=headers)

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
                    "Accept-Encoding": "identity",  # Disable compression for Pyodide compatibility
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


async def handle_validate_code(request, env, cors_headers):
    """Validate an invite code and return a session ID."""
    import uuid

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))
        code = body.get("code", "").strip().upper()

        if not code:
            return json_response({"valid": False, "error": "Code is required"}, cors_headers, 400)

        # Get KV namespace
        kv = getattr(env, "INVITE_CODES", None)
        if not kv:
            return json_response({"valid": False, "error": "Invite codes not configured"}, cors_headers, 500)

        # Look up code in KV (stored as JSON: {"active": true, "max_uses": 100, "current_uses": 5})
        code_data_str = await kv.get(code)
        if not code_data_str:
            return json_response({"valid": False, "error": "Invalid invite code"}, cors_headers)

        code_data = json.loads(code_data_str)

        # Check if active
        if not code_data.get("active", False):
            return json_response({"valid": False, "error": "This code is no longer active"}, cors_headers)

        # Check usage limits
        max_uses = code_data.get("max_uses")
        current_uses = code_data.get("current_uses", 0)

        if max_uses is not None and current_uses >= max_uses:
            return json_response({"valid": False, "error": "This code has reached its usage limit"}, cors_headers)

        # Increment usage count
        code_data["current_uses"] = current_uses + 1
        await kv.put(code, json.dumps(code_data))

        # Generate session ID
        session_id = str(uuid.uuid4())

        # Calculate remaining uses
        remaining = None
        if max_uses is not None:
            remaining = max_uses - code_data["current_uses"]

        return json_response({
            "valid": True,
            "session_id": session_id,
            "remaining_uses": remaining,
        }, cors_headers)

    except Exception as e:
        return json_response({"valid": False, "error": str(e)}, cors_headers, 500)


async def handle_fetch_url(request, cors_headers):
    """Fetch a URL and return text content for Claude to parse."""
    import re
    import httpx
    from urllib.parse import urlparse

    def html_to_text(html):
        """Convert HTML to readable text."""
        text = re.sub(r"<script[^>]*>[\s\S]*?</script>", "", html, flags=re.IGNORECASE)
        text = re.sub(r"<style[^>]*>[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<head[^>]*>[\s\S]*?</head>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</tr>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</li>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</h[1-6]>", "\n\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<td[^>]*>", "\t", text, flags=re.IGNORECASE)
        text = re.sub(r"<th[^>]*>", "\t", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        entities = {"&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'"}
        for entity, char in entities.items():
            text = text.replace(entity, char)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))
        url = body.get("url", "")

        # Validate URL
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return json_response({"success": False, "error": "Invalid URL protocol"}, cors_headers)
        except Exception:
            return json_response({"success": False, "error": "Invalid URL"}, cors_headers)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; AthleticsAnnualPlan/1.0)",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                follow_redirects=True,
                timeout=30.0,
            )

            if response.status_code != 200:
                return json_response({"success": False, "error": f"Failed to fetch URL: {response.status_code}"}, cors_headers)

            text = html_to_text(response.text)
            max_length = 15000
            truncated = len(text) > max_length
            content = text[:max_length] + "\n\n[Content truncated...]" if truncated else text

            return json_response({
                "success": True,
                "url": url,
                "content": content,
                "truncated": truncated,
                "original_length": len(text),
            }, cors_headers)

    except Exception as e:
        return json_response({"success": False, "error": str(e)}, cors_headers, 500)


async def handle_search_competitions(request, env, cors_headers):
    """Search for athletics competitions using Claude with web search."""
    import httpx

    api_key = getattr(env, "CLAUDE_API_KEY", None)
    if not api_key:
        return json_response({"success": False, "error": "Claude API key not configured"}, cors_headers, 500)

    try:
        body = await request.json()
        body = json.loads(JSON.stringify(body))

        season_year = body.get("season_year", "2025/2026")
        country = body.get("country", "Ireland")
        event_group = body.get("event_group", "Sprints")
        age_groups = body.get("age_groups", ["Senior"])
        comp_levels = body.get("comp_levels", ["National"])
        federation_url = body.get("federation_url")

        start_year = season_year.split("/")[0]
        end_year = season_year.split("/")[1]
        age_groups_text = ", ".join(age_groups)
        is_masters = "Masters" in age_groups

        # Build competition requirements
        comp_requirements = []
        if "National" in comp_levels:
            comp_requirements.append(f"- National Indoor Championships (typically Jan-Mar {end_year})")
            comp_requirements.append(f"- National Outdoor Championships (typically Jun-Aug {end_year})")
        if "European" in comp_levels:
            if is_masters:
                comp_requirements.append("- European Masters Indoor/Outdoor Championships")
            else:
                comp_requirements.append("- European Indoor/Outdoor Championships (if applicable)")
        if "World" in comp_levels:
            if is_masters:
                comp_requirements.append("- World Masters Athletics Championships")
            else:
                comp_requirements.append("- World Indoor/Outdoor Championships (if applicable)")
        if "Leagues" in comp_levels:
            comp_requirements.append("- National League events and graded meets")

        comp_list = "\n".join(comp_requirements) if comp_requirements else "- National Championships"
        federation_hint = f"\n\nStart by checking: {federation_url}" if federation_url else ""

        prompt = f"""Search for track and field athletics competitions for the {season_year} season in {country}.

I need competitions suitable for {age_groups_text} athletes in {event_group} events.

Competitions to find:
{comp_list}{federation_hint}

Return the competitions as a JSON array sorted by date:
```json
[{{"name": "Competition Name", "date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "location": "City, Country", "importance": 1, "type": "indoor"}}]
```

Importance: 1=Major championship, 2=Significant, 3=Development
Type: "indoor" or "outdoor"

Only return the JSON array, no other text."""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "Accept-Encoding": "identity",  # Disable compression for Pyodide compatibility
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 4096,
                    "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120.0,
            )

            if response.status_code != 200:
                return json_response({"success": False, "error": f"Search failed (status {response.status_code})"}, cors_headers)

            data = response.json()

            # Extract text from response
            response_text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    response_text += block.get("text", "")

            # Parse JSON from response
            competitions = []
            try:
                start_idx = response_text.find("[")
                end_idx = response_text.rfind("]") + 1
                if start_idx != -1 and end_idx > start_idx:
                    raw_competitions = json.loads(response_text[start_idx:end_idx])
                    for comp in raw_competitions:
                        competitions.append({
                            "name": comp.get("name", "Unknown"),
                            "date": comp.get("date", ""),
                            "end_date": comp.get("end_date"),
                            "location": comp.get("location"),
                            "importance": comp.get("importance", 3),
                            "type": comp.get("type"),
                        })
            except json.JSONDecodeError:
                pass

            return json_response({"success": True, "competitions": competitions}, cors_headers)

    except Exception as e:
        return json_response({"success": False, "error": str(e)}, cors_headers, 500)
