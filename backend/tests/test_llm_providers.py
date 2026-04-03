"""Unit tests for LLM provider abstraction."""

import pytest


def test_get_provider_defaults_to_claude():
    """Factory returns claude module when provider is 'claude'."""
    from app.services.llm import get_provider

    provider = get_provider(llm_provider="claude")
    assert provider.__name__ == "app.services.llm.claude"


def test_get_provider_returns_gemini():
    """Factory returns gemini module when provider is 'gemini'."""
    from app.services.llm import get_provider

    provider = get_provider(llm_provider="gemini")
    assert provider.__name__ == "app.services.llm.gemini"


def test_get_provider_invalid_raises():
    """Factory raises ValueError for unknown provider."""
    from app.services.llm import get_provider

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_provider(llm_provider="openai")
