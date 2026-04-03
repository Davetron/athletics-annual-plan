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
