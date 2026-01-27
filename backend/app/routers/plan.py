"""
Plan generation and download routes.
"""

from io import BytesIO

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
import httpx

from app.config import get_settings
from app.models.schemas import (
    GeneratePlanRequest,
    GeneratePlanResponse,
    DownloadExcelRequest,
)
from app.services.plan_generator import (
    GENERATE_PLAN_TOOL,
    GENERATION_SYSTEM_PROMPT,
    build_context_message,
)
from app.services.rate_limiter import generate_limiter
from app.services.excel_generator import generate_excel_from_plan

router = APIRouter()
settings = get_settings()


@router.post("/generate-plan", response_model=GeneratePlanResponse)
async def generate_plan(
    request: GeneratePlanRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
):
    """
    Generate a 52-week periodized training plan using Claude tool_use.

    Requires X-Session-ID header for rate limiting.
    """
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required")

    # Rate limiting (5 req/min for generation)
    allowed, remaining = generate_limiter.check(x_session_id)
    if not allowed:
        return GeneratePlanResponse(
            success=False,
            error="Rate limit exceeded. Please wait before generating another plan.",
        )

    if not settings.claude_api_key:
        raise HTTPException(status_code=500, detail="Claude API key not configured")

    # Build context message from form data and conversation
    form_data = request.formData.model_dump(by_alias=True)
    messages = (
        [{"role": m.role, "content": m.content} for m in request.messages]
        if request.messages
        else None
    )
    context_message = build_context_message(form_data, messages)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": settings.claude_api_key,
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
                error_detail = response.text[:500] if response.text else "No details"
                print(f"[DEBUG] Generate plan API error: {response.status_code} - {error_detail}")
                return GeneratePlanResponse(
                    success=False,
                    error=f"Failed to generate plan (status {response.status_code}). Please try again.",
                )

            data = response.json()

            # Extract the tool use result
            tool_use = None
            for block in data.get("content", []):
                if block.get("type") == "tool_use" and block.get("name") == "generate_annual_plan":
                    tool_use = block
                    break

            if not tool_use:
                return GeneratePlanResponse(
                    success=False,
                    error="Failed to generate structured plan. Please try again.",
                )

            # The plan is in tool_use.input
            plan = tool_use.get("input", {})

            # Validate basic structure
            weeks = plan.get("weeks", [])
            if len(weeks) != 52:
                print(f"[DEBUG] Plan has {len(weeks)} weeks instead of 52")
                print(f"[DEBUG] Stop reason: {data.get('stop_reason')}")
                return GeneratePlanResponse(
                    success=False,
                    error=f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
                )

            return GeneratePlanResponse(success=True, plan=plan)

    except httpx.TimeoutException:
        return GeneratePlanResponse(
            success=False,
            error="Plan generation timed out. Please try again.",
        )
    except httpx.RequestError as e:
        return GeneratePlanResponse(
            success=False,
            error=f"Failed to connect to AI: {str(e)}",
        )


@router.post("/download-excel")
async def download_excel(request: DownloadExcelRequest):
    """
    Generate and download an Excel file from the plan data.

    Returns the Excel file as a downloadable attachment.
    """
    try:
        # Generate Excel workbook
        workbook = generate_excel_from_plan(request.plan.model_dump())

        # Save to bytes
        output = BytesIO()
        workbook.save(output)
        output.seek(0)

        # Create filename
        athlete_safe = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in request.plan.athlete
        ).strip()
        season_safe = request.plan.season.replace("/", "-")
        filename = f"{athlete_safe}_Annual_Plan_{season_safe}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Excel file: {str(e)}",
        )
