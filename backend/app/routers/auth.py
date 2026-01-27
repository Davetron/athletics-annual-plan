"""
Authentication routes - invite code validation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.schemas import ValidateCodeRequest, ValidateCodeResponse
from app.services.invite_codes import validate_code

router = APIRouter()


@router.post("/validate-code", response_model=ValidateCodeResponse)
async def validate_invite_code(
    request: ValidateCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate an invite code and create a session.

    Returns session ID if valid, error message if not.
    """
    valid, session_id, error, remaining = await validate_code(db, request.code)

    if valid:
        return ValidateCodeResponse(
            valid=True,
            session_id=session_id,
            remaining_uses=remaining,
        )
    else:
        return ValidateCodeResponse(
            valid=False,
            error=error,
        )
