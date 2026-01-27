"""
Service layer for invite code operations.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import InviteCode, Session


async def validate_code(db: AsyncSession, code: str) -> tuple[bool, str | None, str | None, int | None]:
    """
    Validate an invite code and create a session if valid.

    Returns:
        Tuple of (valid, session_id, error_message, remaining_uses)
    """
    code_upper = code.upper().strip()

    # Look up code
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code_upper)
    )
    invite_code = result.scalar_one_or_none()

    if not invite_code:
        return False, None, "Invalid invite code", None

    # Check if active
    if not invite_code.active:
        return False, None, "This code has been deactivated", None

    # Check usage limit
    if invite_code.max_uses and invite_code.used_count >= invite_code.max_uses:
        return False, None, "This code has reached its usage limit", None

    # Increment usage count
    invite_code.used_count += 1
    invite_code.last_used = datetime.utcnow()

    # Generate session ID
    session_id = str(uuid4())

    # Create session record
    session = Session(session_id=session_id, invite_code=code_upper)
    db.add(session)

    await db.commit()

    remaining = invite_code.max_uses - invite_code.used_count if invite_code.max_uses else None
    return True, session_id, None, remaining


async def get_invite_code(db: AsyncSession, code: str) -> InviteCode | None:
    """Get an invite code by its code string."""
    result = await db.execute(
        select(InviteCode).where(InviteCode.code == code.upper().strip())
    )
    return result.scalar_one_or_none()


async def create_invite_code(
    db: AsyncSession,
    code: str,
    max_uses: int = 10,
    active: bool = True,
) -> InviteCode:
    """Create a new invite code."""
    invite_code = InviteCode(
        code=code.upper().strip(),
        max_uses=max_uses,
        active=active,
    )
    db.add(invite_code)
    await db.commit()
    await db.refresh(invite_code)
    return invite_code
