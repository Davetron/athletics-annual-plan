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
