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
