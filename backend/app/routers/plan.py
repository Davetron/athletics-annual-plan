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
from app.services.llm import get_provider
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
    Generate a 52-week periodized training plan using the configured LLM provider.

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

    # Determine API key for active provider
    provider = get_provider(settings.llm_provider)
    api_key = (
        settings.gemini_api_key
        if settings.llm_provider == "gemini"
        else settings.claude_api_key
    )
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=f"{settings.llm_provider.title()} API key not configured",
        )

    # Build context message from form data and conversation
    form_data = request.formData.model_dump(by_alias=True)
    messages = (
        [{"role": m.role, "content": m.content} for m in request.messages]
        if request.messages
        else None
    )
    context_message = build_context_message(form_data, messages)

    try:
        result = await provider.generate_plan(
            system_prompt=GENERATION_SYSTEM_PROMPT,
            context_message=context_message,
            tool=GENERATE_PLAN_TOOL,
            api_key=api_key,
        )
        return GeneratePlanResponse(**result)

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
