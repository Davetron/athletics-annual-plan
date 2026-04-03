# Gemini LLM Provider Integration

## Goal

Add Gemini 2.5 Flash Lite as a switchable LLM provider alongside Claude, for evaluating plan generation and competition search quality. Switching is controlled by a single environment variable.

## Architecture

```
backend/app/
├── config.py                    # + llm_provider, gemini_api_key
├── services/
│   ├── llm/
│   │   ├── __init__.py          # Factory: get_provider()
│   │   ├── claude.py            # generate_plan(), search_competitions()
│   │   └── gemini.py            # generate_plan(), search_competitions()
│   └── plan_generator.py        # Unchanged — shared schema + prompts
├── routers/
│   ├── plan.py                  # Calls provider.generate_plan()
│   └── competitions.py          # Calls provider.search_competitions()
```

Shared assets (`GENERATE_PLAN_TOOL`, `GENERATION_SYSTEM_PROMPT`, `build_context_message`) stay in `plan_generator.py`. Each provider module handles API transport and response parsing.

## Config

Two new fields in `Settings` (`config.py`):

```python
llm_provider: str = "claude"       # "claude" or "gemini"
gemini_api_key: str = ""
```

Activated via `.env`:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

## Provider Contract

Both `claude.py` and `gemini.py` export two async functions:

```python
async def generate_plan(
    system_prompt: str,
    context_message: str,
    tool: dict,
    api_key: str,
) -> dict:
    """Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}"""

async def search_competitions(
    prompt: str,
    api_key: str,
) -> list[dict] | None:
    """Returns list of competition dicts, or None if no results found."""
```

## Factory

`services/llm/__init__.py`:

```python
def get_provider(settings):
    if settings.llm_provider == "gemini":
        from . import gemini
        return gemini
    from . import claude
    return claude
```

Routers call `provider = get_provider(settings)` then `await provider.generate_plan(...)`.

## Claude Provider (`claude.py`)

Extracted from current inline code in `routers/plan.py` and `routers/competitions.py`. No behavior changes — just moved into a module.

- Plan generation: `POST https://api.anthropic.com/v1/messages` with `tool_use` and `tool_choice`
- Competition search: Same endpoint with `web_search_20250305` tool
- Model: `claude-haiku-4-5-20251001`

## Gemini Provider (`gemini.py`)

- API: Raw `httpx` calls to `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Model: `gemini-2.5-flash-lite`
- Plan generation: Uses Gemini function calling (`function_declarations`). The existing `GENERATE_PLAN_TOOL` schema translates to Gemini's format — same JSON Schema structure, different wrapper.
- Competition search: Uses Google Search grounding (`"tools": [{"google_search": {}}]`). Response text is parsed for JSON array, same as Claude path.
- API key passed as `?key=` query parameter per Gemini REST API convention.

## Router Changes

### `routers/plan.py`

- Remove inline Claude API call
- Import `get_provider` from `services.llm`
- Call `provider.generate_plan(system_prompt, context_message, tool, api_key)`
- Keep validation (52 weeks check), rate limiting, and error handling in the router

### `routers/competitions.py`

- Remove inline `_call_claude_search` function
- Import `get_provider` from `services.llm`
- Call `provider.search_competitions(prompt, api_key)` inside the retry loop
- Keep retry logic, prompt building, and response mapping in the router

## Error Handling

Each provider handles its own API errors and returns the same result shape. The routers handle timeouts and request errors uniformly via `httpx` exceptions (both providers use `httpx`).

## Testing

- Existing backend tests should continue to pass (no behavior change for Claude path)
- Manual testing: switch `LLM_PROVIDER=gemini`, generate a plan, search competitions, verify output quality
