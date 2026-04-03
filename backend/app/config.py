"""
Application configuration using Pydantic Settings.
Reads from environment variables and .env files.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Claude API
    claude_api_key: str = ""

    # LLM provider selection
    llm_provider: str = "claude"  # "claude" or "gemini"
    gemini_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./athletics.db"

    # CORS origins
    cors_origins: list[str] = [
        "http://localhost:8788",  # Wrangler dev server
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:8788",
        "http://127.0.0.1:3000",
    ]

    # Rate limiting
    rate_limit_chat: int = 10  # requests per minute for chat
    rate_limit_generate: int = 5  # requests per minute for plan generation


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
