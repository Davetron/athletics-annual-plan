"""
SQLAlchemy database models and initialization.
Uses async SQLite for development, can switch to PostgreSQL for production.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""
    pass


class InviteCode(Base):
    """Invite codes for authentication."""

    __tablename__ = "invite_codes"

    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    max_uses: Mapped[int] = mapped_column(Integer, default=10)
    used_count: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    last_used: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationship to sessions
    sessions: Mapped[list["Session"]] = relationship(back_populates="invite_code_rel")


class Session(Base):
    """User sessions linked to invite codes."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    invite_code: Mapped[str] = mapped_column(
        String(50), ForeignKey("invite_codes.code")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    # Relationship to invite code
    invite_code_rel: Mapped["InviteCode"] = relationship(back_populates="sessions")


# Database engine and session factory
settings = get_settings()
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial invite codes if none exist
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(select(InviteCode).limit(1))
        if not result.scalar_one_or_none():
            # Add default invite codes for testing
            default_codes = [
                InviteCode(code="SPRINT2025", max_uses=100, active=True),
                InviteCode(code="COACH2025", max_uses=50, active=True),
                InviteCode(code="TEST", max_uses=1000, active=True),
            ]
            session.add_all(default_codes)
            await session.commit()


async def get_db():
    """Dependency that yields database sessions."""
    async with async_session() as session:
        yield session
