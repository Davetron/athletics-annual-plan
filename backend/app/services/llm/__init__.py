"""
LLM provider factory.

Selects between Claude and Gemini based on configuration.
Both providers export the same interface:
  - generate_plan(system_prompt, context_message, tool, api_key) -> dict
  - search_competitions(prompt, api_key) -> list[dict] | None
"""

from types import ModuleType


def get_provider(llm_provider: str) -> ModuleType:
    """Return the LLM provider module matching the config."""
    if llm_provider == "claude":
        from app.services.llm import claude
        return claude
    if llm_provider == "gemini":
        from app.services.llm import gemini
        return gemini
    raise ValueError(f"Unknown LLM provider: {llm_provider!r}. Use 'claude' or 'gemini'.")
