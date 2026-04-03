# Gemini LLM Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Gemini 2.5 Flash Lite as a switchable LLM provider alongside Claude for plan generation and competition search.

**Architecture:** Extract current Claude API calls from routers into a provider module, create a matching Gemini provider, and wire them together via a config-driven factory. Shared prompts and schemas stay in `plan_generator.py`.

**Tech Stack:** Python, FastAPI, httpx, Gemini REST API (`generativelanguage.googleapis.com/v1beta`)

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `backend/app/config.py` | Add `llm_provider` and `gemini_api_key` settings |
| Create | `backend/app/services/llm/__init__.py` | Factory function `get_provider()` |
| Create | `backend/app/services/llm/claude.py` | Claude API calls: `generate_plan()`, `search_competitions()` |
| Create | `backend/app/services/llm/gemini.py` | Gemini API calls + schema translation |
| Modify | `backend/app/routers/plan.py:29-131` | Replace inline Claude call with provider call |
| Modify | `backend/app/routers/competitions.py:136-321` | Replace inline Claude call with provider call |
| Create | `backend/tests/test_llm_providers.py` | Unit tests for factory, schema translation, response parsing |

---

### Task 1: Add config fields and create LLM factory

**Files:**
- Modify: `backend/app/config.py:19-20`
- Create: `backend/app/services/llm/__init__.py`
- Create: `backend/tests/test_llm_providers.py`

- [ ] **Step 1: Write tests for config and factory**

Create `backend/tests/test_llm_providers.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source venv/bin/activate && pytest tests/test_llm_providers.py -v`
Expected: FAIL — `ImportError` because `app.services.llm` doesn't exist yet.

- [ ] **Step 3: Add config fields**

In `backend/app/config.py`, add after line 20 (`claude_api_key: str = ""`):

```python
    # LLM provider selection
    llm_provider: str = "claude"  # "claude" or "gemini"
    gemini_api_key: str = ""
```

- [ ] **Step 4: Create the factory module**

Create `backend/app/services/llm/__init__.py`:

```python
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
```

- [ ] **Step 5: Create stub provider files so imports work**

Create `backend/app/services/llm/claude.py`:

```python
"""Claude LLM provider — placeholder, will be filled in Task 2."""
```

Create `backend/app/services/llm/gemini.py`:

```python
"""Gemini LLM provider — placeholder, will be filled in Tasks 4-6."""
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_llm_providers.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/services/llm/__init__.py backend/app/services/llm/claude.py backend/app/services/llm/gemini.py backend/tests/test_llm_providers.py
git commit -m "feat: add LLM provider config and factory module"
```

---

### Task 2: Extract Claude provider from routers

**Files:**
- Modify: `backend/app/services/llm/claude.py`

This is a refactor — existing e2e tests are the safety net. No new tests needed.

- [ ] **Step 1: Implement Claude provider**

Replace `backend/app/services/llm/claude.py` with:

```python
"""
Claude LLM provider.

Uses the Anthropic Messages API via httpx for plan generation (tool_use)
and competition search (web_search).
"""

import json

import httpx

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"


async def generate_plan(
    system_prompt: str,
    context_message: str,
    tool: dict,
    api_key: str,
) -> dict:
    """
    Generate a training plan using Claude tool_use.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 16384,
                "temperature": 0,
                "system": system_prompt,
                "tools": [tool],
                "tool_choice": {"type": "tool", "name": tool["name"]},
                "messages": [{"role": "user", "content": context_message}],
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Generate plan API error: {response.status_code} - {error_detail}")
            return {
                "success": False,
                "error": f"Failed to generate plan (status {response.status_code}). Please try again.",
            }

        data = response.json()

        # Extract the tool use result
        tool_use = None
        for block in data.get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == tool["name"]:
                tool_use = block
                break

        if not tool_use:
            return {
                "success": False,
                "error": "Failed to generate structured plan. Please try again.",
            }

        plan = tool_use.get("input", {})

        # Validate basic structure
        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Plan has {len(weeks)} weeks instead of 52")
            print(f"[DEBUG] Stop reason: {data.get('stop_reason')}")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}


async def search_competitions(
    prompt: str,
    api_key: str,
) -> list[dict] | None:
    """
    Search for competitions using Claude web_search.

    Returns list of competition dicts, or None if no JSON found.
    Raises httpx exceptions on network errors.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            API_URL,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": MODEL,
                "max_tokens": 4096,
                "temperature": 0,
                "tools": [{"type": "web_search_20250305", "name": "web_search"}],
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Search API error: {response.status_code} - {error_detail}")
            return None

        data = response.json()

        # Extract text from response (handles multiple content blocks)
        response_text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                response_text += block.get("text", "")

        print(f"[DEBUG] Claude search response ({len(response_text)} chars)")

        # Parse JSON array from response
        return _extract_competitions_json(response_text)


def _extract_competitions_json(text: str) -> list[dict] | None:
    """Extract a JSON array of competitions from response text."""
    try:
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        if start_idx != -1 and end_idx > start_idx:
            raw = json.loads(text[start_idx:end_idx])
            return [
                {
                    "name": c.get("name", "Unknown"),
                    "date": c.get("date", ""),
                    "end_date": c.get("end_date"),
                    "location": c.get("location"),
                    "importance": c.get("importance", 3),
                    "type": c.get("type"),
                }
                for c in raw
            ]
        return None
    except json.JSONDecodeError:
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/llm/claude.py
git commit -m "refactor: extract Claude API calls into provider module"
```

---

### Task 3: Rewire routers to use provider abstraction

**Files:**
- Modify: `backend/app/routers/plan.py:1-131`
- Modify: `backend/app/routers/competitions.py:136-321`

- [ ] **Step 1: Update plan router**

Replace `backend/app/routers/plan.py` with:

```python
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
```

- [ ] **Step 2: Update competitions router**

In `backend/app/routers/competitions.py`, replace the `search_competitions` function (lines 136-249) and remove `_call_claude_search` (lines 252-321):

```python
@router.post("/search-competitions", response_model=SearchCompetitionsResponse)
async def search_competitions(request: SearchCompetitionsRequest):
    """
    Search for athletics competitions using the configured LLM provider.
    """
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

    start_year = int(request.season_year.split("/")[0])
    end_year = int(request.season_year.split("/")[1])

    # Build age groups text
    age_groups_text = ", ".join(request.age_groups)
    is_masters = "Masters" in request.age_groups

    # Build competition levels requirements
    comp_requirements = []
    if "National" in request.comp_levels:
        comp_requirements.append(f"- National Indoor Championships (typically Jan-Mar {end_year})")
        comp_requirements.append(f"- National Outdoor Championships (typically Jun-Aug {end_year})")
        comp_requirements.append("- Regional/Provincial Championships")
    if "European" in request.comp_levels:
        if is_masters:
            comp_requirements.append("- European Masters Indoor Championships")
            comp_requirements.append("- European Masters Outdoor Championships")
        else:
            comp_requirements.append("- European Indoor Championships (if applicable)")
            comp_requirements.append("- European Outdoor Championships (if applicable)")
    if "World" in request.comp_levels:
        if is_masters:
            comp_requirements.append("- World Masters Athletics Championships")
        else:
            comp_requirements.append("- World Indoor Championships (if applicable)")
            comp_requirements.append("- World Outdoor Championships (if applicable)")
    if "Leagues" in request.comp_levels:
        comp_requirements.append("- National League events")
        comp_requirements.append("- Graded meets or open competitions")

    comp_list = "\n".join(comp_requirements) if comp_requirements else "- National Championships"

    # Federation URL hint
    federation_hint = ""
    if request.federation_url:
        federation_hint = f"\n\nStart by checking the official fixtures at: {request.federation_url}"

    prompt = f"""Search for track and field athletics competitions for the {request.season_year} season in {request.country}.

I need competitions suitable for {age_groups_text} athletes in {request.event_group} events.

Competitions to find:
{comp_list}{federation_hint}

Return the competitions as a JSON array sorted by date, with this format:
```json
[
  {{
    "name": "Competition Name",
    "date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "location": "City, Country",
    "importance": 1,
    "type": "indoor"
  }}
]
```

Importance levels:
- 1 = Major championship (Nationals, Europeans, Worlds)
- 2 = Significant (Regional championships, major leagues)
- 3 = Development (Graded meets, open competitions)

Type should be "indoor" or "outdoor".

IMPORTANT: You MUST return a JSON array even if you couldn't find all competitions. Return what you found. If you found nothing, return an empty array []. Do not explain what you couldn't find - just return the JSON array."""

    max_attempts = 3
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            competitions = await provider.search_competitions(
                prompt=prompt,
                api_key=api_key,
            )
            if competitions is not None:
                return SearchCompetitionsResponse(
                    success=True,
                    competitions=[
                        CompetitionResult(**comp) for comp in competitions
                    ],
                )
            if attempt < max_attempts:
                print(f"[DEBUG] Attempt {attempt} returned no results, retrying...")
                continue
            else:
                print(f"[DEBUG] All {max_attempts} attempts failed to return JSON")
                return SearchCompetitionsResponse(
                    success=True,
                    competitions=[],
                )

        except httpx.TimeoutException:
            last_error = "Search request timed out"
            if attempt < max_attempts:
                print(f"[DEBUG] Attempt {attempt} timed out, retrying...")
                continue
        except httpx.RequestError as e:
            last_error = f"Failed to search: {str(e)}"
            if attempt < max_attempts:
                print(f"[DEBUG] Attempt {attempt} request error: {e}, retrying...")
                continue

    return SearchCompetitionsResponse(
        success=False,
        error=last_error or "Search failed after multiple attempts",
    )
```

Also add the import at the top of the file (after existing imports):

```python
from app.services.llm import get_provider
```

And remove the `import json` since it's no longer needed in this file (JSON parsing moved to provider).

- [ ] **Step 3: Run existing tests to verify no regression**

Run: `cd backend && pytest tests/test_e2e.py -v -k "not real_api"`
Expected: All non-API tests PASS (auth, URL fetch, Excel tests).

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/plan.py backend/app/routers/competitions.py
git commit -m "refactor: rewire routers to use LLM provider abstraction"
```

---

### Task 4: Gemini schema translation

**Files:**
- Modify: `backend/app/services/llm/gemini.py`
- Modify: `backend/tests/test_llm_providers.py`

- [ ] **Step 1: Write tests for schema translation**

Append to `backend/tests/test_llm_providers.py`:

```python
class TestGeminiSchemaTranslation:
    """Tests for translating Claude tool schema to Gemini function declarations."""

    def test_basic_translation(self):
        """Top-level name, description, and parameters are mapped correctly."""
        from app.services.llm.gemini import translate_tool_to_gemini

        claude_tool = {
            "name": "my_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string", "description": "The name"},
                },
            },
        }
        result = translate_tool_to_gemini(claude_tool)

        assert result["name"] == "my_tool"
        assert result["description"] == "A test tool"
        assert result["parameters"]["type"] == "object"
        assert result["parameters"]["required"] == ["name"]
        assert result["parameters"]["properties"]["name"]["type"] == "string"

    def test_nullable_type(self):
        """Array type like ["integer", "null"] becomes type + nullable."""
        from app.services.llm.gemini import _translate_schema

        schema = {"type": ["integer", "null"], "description": "Maybe a number"}
        result = _translate_schema(schema)

        assert result["type"] == "integer"
        assert result["nullable"] is True
        assert result["description"] == "Maybe a number"

    def test_strips_unsupported_keys(self):
        """minItems, maxItems, minimum, maximum are removed."""
        from app.services.llm.gemini import _translate_schema

        schema = {
            "type": "array",
            "minItems": 52,
            "maxItems": 52,
            "items": {
                "type": "integer",
                "minimum": 0,
                "maximum": 4,
            },
        }
        result = _translate_schema(schema)

        assert "minItems" not in result
        assert "maxItems" not in result
        assert "minimum" not in result["items"]
        assert "maximum" not in result["items"]
        assert result["type"] == "array"
        assert result["items"]["type"] == "integer"

    def test_nested_properties(self):
        """Nested objects are translated recursively."""
        from app.services.llm.gemini import _translate_schema

        schema = {
            "type": "object",
            "properties": {
                "inner": {
                    "type": "object",
                    "properties": {
                        "value": {"type": "string"},
                    },
                },
            },
        }
        result = _translate_schema(schema)

        assert result["properties"]["inner"]["properties"]["value"]["type"] == "string"

    def test_enum_preserved(self):
        """Enum values are kept in the translated schema."""
        from app.services.llm.gemini import _translate_schema

        schema = {"type": "string", "enum": ["a", "b", "c"]}
        result = _translate_schema(schema)

        assert result["enum"] == ["a", "b", "c"]

    def test_real_plan_tool_translates(self):
        """The actual GENERATE_PLAN_TOOL translates without error."""
        from app.services.llm.gemini import translate_tool_to_gemini
        from app.services.plan_generator import GENERATE_PLAN_TOOL

        result = translate_tool_to_gemini(GENERATE_PLAN_TOOL)

        assert result["name"] == "generate_annual_plan"
        assert "parameters" in result
        weeks_schema = result["parameters"]["properties"]["weeks"]
        assert weeks_schema["type"] == "array"
        assert "minItems" not in weeks_schema
        # Check nullable competitionImportance
        week_props = weeks_schema["items"]["properties"]
        assert week_props["competitionImportance"]["nullable"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_llm_providers.py::TestGeminiSchemaTranslation -v`
Expected: FAIL — `translate_tool_to_gemini` not defined.

- [ ] **Step 3: Implement schema translation**

Replace `backend/app/services/llm/gemini.py` with:

```python
"""
Gemini LLM provider.

Uses the Gemini REST API via httpx for plan generation (function calling)
and competition search (Google Search grounding).
"""

import json

import httpx

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = "gemini-2.5-flash-lite"

# Keys in Claude's JSON Schema that Gemini's OpenAPI subset doesn't support
_UNSUPPORTED_SCHEMA_KEYS = {"minItems", "maxItems", "minimum", "maximum"}


def translate_tool_to_gemini(claude_tool: dict) -> dict:
    """Convert a Claude tool_use definition to a Gemini function declaration."""
    return {
        "name": claude_tool["name"],
        "description": claude_tool["description"],
        "parameters": _translate_schema(claude_tool["input_schema"]),
    }


def _translate_schema(schema: dict) -> dict:
    """Recursively translate JSON Schema to Gemini's OpenAPI subset."""
    result = {}

    # Handle type (may be a list like ["integer", "null"])
    type_val = schema.get("type")
    if isinstance(type_val, list):
        non_null = [t for t in type_val if t != "null"]
        result["type"] = non_null[0] if non_null else "string"
        if "null" in type_val:
            result["nullable"] = True
    elif type_val:
        result["type"] = type_val

    # Copy supported fields
    for key in ("description", "enum", "required"):
        if key in schema:
            result[key] = schema[key]

    # Recurse into properties
    if "properties" in schema:
        result["properties"] = {
            k: _translate_schema(v) for k, v in schema["properties"].items()
        }

    # Recurse into array items
    if "items" in schema:
        result["items"] = _translate_schema(schema["items"])

    # Unsupported keys (minItems, maxItems, minimum, maximum) are simply omitted

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_llm_providers.py -v`
Expected: All tests PASS (factory + schema translation).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/gemini.py backend/tests/test_llm_providers.py
git commit -m "feat: add Gemini schema translation for function calling"
```

---

### Task 5: Gemini plan generation

**Files:**
- Modify: `backend/app/services/llm/gemini.py`
- Modify: `backend/tests/test_llm_providers.py`

- [ ] **Step 1: Write test for plan generation response parsing**

Append to `backend/tests/test_llm_providers.py`:

```python
from unittest.mock import AsyncMock, patch, MagicMock


class TestGeminiPlanGeneration:
    """Tests for Gemini generate_plan response parsing."""

    @pytest.mark.asyncio
    async def test_successful_plan_extraction(self):
        """Extracts plan from Gemini functionCall response."""
        from app.services.llm.gemini import generate_plan

        # Build a minimal valid 52-week plan
        weeks = [
            {
                "weekNum": i + 1,
                "startDate": f"2025-09-{(i % 28) + 1:02d}",
                "month": "Sep 25",
                "phase": "General Prep",
                "phaseType": "general-prep",
                "load": 3,
            }
            for i in range(52)
        ]
        mock_plan = {
            "athlete": "Test",
            "season": "2025/2026",
            "eventGroup": "sprints",
            "periodization": "bi-phase",
            "seasonStart": "2025-08-25",
            "competitions": [],
            "weeks": weeks,
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "generate_annual_plan",
                                    "args": mock_plan,
                                }
                            }
                        ]
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await generate_plan(
                system_prompt="test prompt",
                context_message="test message",
                tool={"name": "generate_annual_plan", "description": "test", "input_schema": {"type": "object", "properties": {}}},
                api_key="fake-key",
            )

        assert result["success"] is True
        assert result["plan"]["athlete"] == "Test"
        assert len(result["plan"]["weeks"]) == 52

    @pytest.mark.asyncio
    async def test_api_error_returns_failure(self):
        """Non-200 response returns success=False."""
        from app.services.llm.gemini import generate_plan

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await generate_plan(
                system_prompt="test",
                context_message="test",
                tool={"name": "t", "description": "t", "input_schema": {"type": "object", "properties": {}}},
                api_key="fake-key",
            )

        assert result["success"] is False
        assert "400" in result["error"]

    @pytest.mark.asyncio
    async def test_incomplete_plan_returns_failure(self):
        """Plan with fewer than 52 weeks returns success=False."""
        from app.services.llm.gemini import generate_plan

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "generate_annual_plan",
                                    "args": {"weeks": [{"weekNum": 1}] * 30},
                                }
                            }
                        ]
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await generate_plan(
                system_prompt="test",
                context_message="test",
                tool={"name": "generate_annual_plan", "description": "t", "input_schema": {"type": "object", "properties": {}}},
                api_key="fake-key",
            )

        assert result["success"] is False
        assert "30 weeks" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_llm_providers.py::TestGeminiPlanGeneration -v`
Expected: FAIL — `generate_plan` not defined in gemini module.

- [ ] **Step 3: Implement generate_plan**

Append to `backend/app/services/llm/gemini.py` (after the `_translate_schema` function):

```python
async def generate_plan(
    system_prompt: str,
    context_message: str,
    tool: dict,
    api_key: str,
) -> dict:
    """
    Generate a training plan using Gemini function calling.

    Returns {"success": True, "plan": {...}} or {"success": False, "error": "..."}.
    """
    gemini_func = translate_tool_to_gemini(tool)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/models/{MODEL}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "systemInstruction": {
                    "parts": [{"text": system_prompt}],
                },
                "contents": [
                    {"role": "user", "parts": [{"text": context_message}]},
                ],
                "tools": [{"functionDeclarations": [gemini_func]}],
                "toolConfig": {
                    "functionCallingConfig": {
                        "mode": "ANY",
                        "allowedFunctionNames": [tool["name"]],
                    }
                },
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 16384,
                },
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Gemini generate plan error: {response.status_code} - {error_detail}")
            return {
                "success": False,
                "error": f"Failed to generate plan (status {response.status_code}). Please try again.",
            }

        data = response.json()

        # Extract function call from response
        plan = None
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                fc = part.get("functionCall")
                if fc and fc.get("name") == tool["name"]:
                    plan = fc.get("args", {})
                    break
            if plan is not None:
                break

        if plan is None:
            return {
                "success": False,
                "error": "Failed to generate structured plan. Please try again.",
            }

        # Validate basic structure
        weeks = plan.get("weeks", [])
        if len(weeks) != 52:
            print(f"[DEBUG] Gemini plan has {len(weeks)} weeks instead of 52")
            return {
                "success": False,
                "error": f"Generated plan was incomplete ({len(weeks)} weeks). Please try again.",
            }

        return {"success": True, "plan": plan}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_llm_providers.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/gemini.py backend/tests/test_llm_providers.py
git commit -m "feat: add Gemini plan generation with function calling"
```

---

### Task 6: Gemini competition search

**Files:**
- Modify: `backend/app/services/llm/gemini.py`
- Modify: `backend/tests/test_llm_providers.py`

- [ ] **Step 1: Write test for competition search response parsing**

Append to `backend/tests/test_llm_providers.py`:

```python
class TestGeminiCompetitionSearch:
    """Tests for Gemini search_competitions response parsing."""

    @pytest.mark.asyncio
    async def test_successful_search(self):
        """Extracts competitions from Gemini text response with grounding."""
        from app.services.llm.gemini import search_competitions

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": 'Here are the competitions:\n[\n  {"name": "National Indoors", "date": "2026-02-21", "location": "Dublin", "importance": 1, "type": "indoor"}\n]'
                            }
                        ],
                        "role": "model",
                    },
                    "groundingMetadata": {
                        "webSearchQueries": ["Ireland athletics 2026"],
                    },
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await search_competitions(
                prompt="Search for competitions",
                api_key="fake-key",
            )

        assert result is not None
        assert len(result) == 1
        assert result[0]["name"] == "National Indoors"
        assert result[0]["importance"] == 1

    @pytest.mark.asyncio
    async def test_no_json_returns_none(self):
        """Response with no JSON array returns None."""
        from app.services.llm.gemini import search_competitions

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": "I couldn't find any competitions."}],
                        "role": "model",
                    }
                }
            ]
        }

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await search_competitions(
                prompt="Search for competitions",
                api_key="fake-key",
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self):
        """Non-200 response returns None."""
        from app.services.llm.gemini import search_competitions

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("app.services.llm.gemini.httpx.AsyncClient", return_value=mock_client):
            result = await search_competitions(
                prompt="Search for competitions",
                api_key="fake-key",
            )

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_llm_providers.py::TestGeminiCompetitionSearch -v`
Expected: FAIL — `search_competitions` not defined in gemini module.

- [ ] **Step 3: Implement search_competitions**

Append to `backend/app/services/llm/gemini.py`:

```python
async def search_competitions(
    prompt: str,
    api_key: str,
) -> list[dict] | None:
    """
    Search for competitions using Gemini with Google Search grounding.

    Returns list of competition dicts, or None if no JSON found.
    Raises httpx exceptions on network errors.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/models/{MODEL}:generateContent",
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json={
                "contents": [
                    {"role": "user", "parts": [{"text": prompt}]},
                ],
                "tools": [{"google_search": {}}],
                "generationConfig": {
                    "temperature": 0,
                    "maxOutputTokens": 4096,
                },
            },
            timeout=120.0,
        )

        if response.status_code != 200:
            error_detail = response.text[:500] if response.text else "No details"
            print(f"[DEBUG] Gemini search error: {response.status_code} - {error_detail}")
            return None

        data = response.json()

        # Extract text from response
        response_text = ""
        for candidate in data.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "text" in part:
                    response_text += part["text"]

        print(f"[DEBUG] Gemini search response ({len(response_text)} chars)")

        # Parse JSON array from response (same format as Claude)
        return _extract_competitions_json(response_text)


def _extract_competitions_json(text: str) -> list[dict] | None:
    """Extract a JSON array of competitions from response text."""
    try:
        start_idx = text.find("[")
        end_idx = text.rfind("]") + 1
        if start_idx != -1 and end_idx > start_idx:
            raw = json.loads(text[start_idx:end_idx])
            return [
                {
                    "name": c.get("name", "Unknown"),
                    "date": c.get("date", ""),
                    "end_date": c.get("end_date"),
                    "location": c.get("location"),
                    "importance": c.get("importance", 3),
                    "type": c.get("type"),
                }
                for c in raw
            ]
        return None
    except json.JSONDecodeError:
        return None
```

- [ ] **Step 4: Run all tests to verify everything passes**

Run: `cd backend && pytest tests/ -v -k "not real_api"`
Expected: All tests PASS (factory, schema, plan gen, search, plus existing e2e tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/gemini.py backend/tests/test_llm_providers.py
git commit -m "feat: add Gemini competition search with Google Search grounding"
```

---

### Task 7: Documentation and .env update

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md environment variables section**

In the "Environment Variables" section of `CLAUDE.md`, add the new config options after the existing `.env` block:

```markdown
### Switching LLM Provider

To use Gemini instead of Claude, add to `backend/.env`:
```
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...
```

Supported providers: `claude` (default), `gemini` (Gemini 2.5 Flash Lite).
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add LLM provider switching instructions"
```
