"""
Chat routes - Claude API proxy.
"""

from fastapi import APIRouter, Header, HTTPException
import httpx

from app.config import get_settings
from app.models.schemas import ChatRequest
from app.services.rate_limiter import chat_limiter

router = APIRouter()
settings = get_settings()


@router.post("/chat")
async def chat(
    request: ChatRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
):
    """
    Proxy chat messages to Claude API.

    Requires X-Session-ID header for rate limiting.
    """
    if not x_session_id:
        raise HTTPException(status_code=401, detail="Session ID required")

    # Rate limiting
    allowed, remaining = chat_limiter.check(x_session_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a moment before trying again.",
        )

    if not settings.claude_api_key:
        raise HTTPException(status_code=500, detail="Claude API key not configured")

    # Build messages for Claude API
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

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
                    "max_tokens": 4096,
                    "system": request.system or "",
                    "messages": messages,
                },
                timeout=60.0,
            )

            if response.status_code != 200:
                raise HTTPException(
                    status_code=502,
                    detail="Failed to get response from AI",
                )

            return response.json()

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request to AI timed out")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Failed to connect to AI: {str(e)}")
