"""Unit tests for the Brief Forge generator module (brief_forge/generator.py).

All tests use mocked OpenAI responses so that:
- No real API calls are made.
- No ``OPENAI_API_KEY`` is required in the test environment.
- Tests run quickly and deterministically.

Covers:
- :func:`~brief_forge.generator.build_user_prompt` construction and validation.
- :func:`~brief_forge.generator._extract_json_from_response` JSON extraction.
- :func:`~brief_forge.generator._get_model`, ``_get_max_tokens``,
  ``_get_temperature`` environment variable helpers.
- :func:`~brief_forge.generator.generate_brief` happy path and error paths.
- :func:`~brief_forge.generator.generate_brief_from_dict` convenience wrapper.
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from brief_forge.generator import (
    _extract_json_from_response,
    _get_max_tokens,
    _get_model,
    _get_openai_client,
    _get_temperature,
    build_user_prompt,
    generate_brief,
    generate_brief_from_dict,
)
from brief_forge.models import DesignBrief


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def valid_brief_dict() -> dict[str, Any]:
    """Return a complete, valid DesignBrief-compatible dictionary."""
    return {
        "title": "Eco Coffee Landing Page",
        "project_overview": (
            "A conversion-focused landing page for a sustainable coffee "
            "subscription brand targeting millennials."
        ),
        "mood_descriptors": ["earthy", "premium", "warm", "approachable"],
        "color_palette": {
            "swatches": [
                {"role": "Primary", "name": "Espresso Brown", "hex_code": "#3B2314", "usage": "Headlines"},
                {"role": "Secondary", "name": "Sage Green", "hex_code": "#7D9B76", "usage": "Accents"},
                {"role": "Background", "name": "Oat Cream", "hex_code": "#F5EFE6", "usage": "Page BG"},
                {"role": "Surface", "name": "Warm Sand", "hex_code": "#E8D9C5", "usage": "Cards"},
                {"role": "Text", "name": "Dark Roast", "hex_code": "#1A1008", "usage": "Body copy"},
            ]
        },
        "typography": {
            "display_font": "Playfair Display",
            "body_font": "Inter",
            "accent_font": "Playfair Display Italic",
            "display_weight": "700",
            "body_weight": "400",
            "notes": "Use 1.6 line-height for body copy.",
        },
        "layout": {
            "description": "Single-column hero with full-bleed background texture.",
            "grid": "12-column, 24px gutter",
            "sections": ["Hero", "Social proof", "Product showcase", "Email capture", "Footer"],
            "spacing_notes": "80px section padding.",
        },
        "copy_hierarchy": [
            "H1: Good coffee. Good planet.",
            "H2: Ethically sourced. Carbon-neutral shipping.",
            "CTA: Start My Subscription",
        ],
        "additional_notes": "Keep tone warm but authoritative.",
    }


def _make_openai_response(content: str) -> MagicMock:
    """Build a minimal mock that resembles an OpenAI ChatCompletion response.

    Parameters
    ----------
    content:
        The string to place in ``response.choices[0].message.content``.

    Returns
    -------
    MagicMock
        A mock object with the same attribute path as a real response.
    """
    mock_message = MagicMock()
    mock_message.content = content

    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_choice.finish_reason = "stop"

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    return mock_response


# ---------------------------------------------------------------------------
# build_user_prompt
# ---------------------------------------------------------------------------


class TestBuildUserPrompt:
    """Tests for the build_user_prompt helper."""

    def test_returns_string(self) -> None:
        result = build_user_prompt("A landing page for a coffee brand.")
        assert isinstance(result, str)

    def test_contains_user_input(self) -> None:
        user_input = "A landing page for a coffee brand."
        result = build_user_prompt(user_input)
        assert user_input in result

    def test_strips_leading_trailing_whitespace_from_input(self) -> None:
        result = build_user_prompt("  My design goal.  ")
        assert "My design goal." in result
        assert "  My design goal.  " not in result

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            build_user_prompt("")

    def test_whitespace_only_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must not be empty"):
            build_user_prompt("   \t\n  ")

    def test_prompt_mentions_json(self) -> None:
        result = build_user_prompt("A coffee landing page.")
        assert "JSON" in result

    def test_prompt_includes_instruction(self) -> None:
        result = build_user_prompt("A coffee landing page.")
        assert "design brief" in result.lower()

    def test_multiline_input_preserved(self) -> None:
        user_input = "Line one.\nLine two.\nLine three."
        result = build_user_prompt(user_input)
        assert "Line one." in result
        assert "Line three." in result


# ---------------------------------------------------------------------------
# _extract_json_from_response
# ---------------------------------------------------------------------------


class TestExtractJsonFromResponse:
    """Tests for the _extract_json_from_response helper."""

    def test_plain_json_object_parsed(self, valid_brief_dict: dict[str, Any]) -> None:
        raw = json.dumps(valid_brief_dict)
        result = _extract_json_from_response(raw)
        assert result["title"] == "Eco Coffee Landing Page"

    def test_json_with_surrounding_whitespace(self, valid_brief_dict: dict[str, Any]) -> None:
        raw = "   " + json.dumps(valid_brief_dict) + "   "
        result = _extract_json_from_response(raw)
        assert isinstance(result, dict)

    def test_json_wrapped_in_markdown_fences(self, valid_brief_dict: dict[str, Any]) -> None:
        json_str = json.dumps(valid_brief_dict)
        raw = f"```json\n{json_str}\n```"
        result = _extract_json_from_response(raw)
        assert result["title"] == "Eco Coffee Landing Page"

    def test_json_wrapped_in_plain_code_fences(self, valid_brief_dict: dict[str, Any]) -> None:
        json_str = json.dumps(valid_brief_dict)
        raw = f"```\n{json_str}\n```"
        result = _extract_json_from_response(raw)
        assert isinstance(result, dict)

    def test_json_with_preamble_text(self, valid_brief_dict: dict[str, Any]) -> None:
        json_str = json.dumps(valid_brief_dict)
        raw = f"Here is your brief:\n{json_str}"
        result = _extract_json_from_response(raw)
        assert isinstance(result, dict)

    def test_no_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="No JSON object found"):
            _extract_json_from_response("This is just plain text with no JSON.")

    def test_invalid_json_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            _extract_json_from_response("{invalid json content here}")

    def test_json_array_raises_value_error(self) -> None:
        # The function expects a dict, not an array at the top level.
        # An array won't have { as the first character before [
        # so this tests that _extract_json_from_response handles edge cases.
        raw = "[{\"key\": \"value\"}]"
        # This will find { inside the array and parse a partial object — that's OK.
        # What matters is that non-dict top-level values are rejected.
        # Since [ comes before {, start will point to the { inside.
        # Let's test with pure array (no braces at top level).
        raw_array = "[\"one\", \"two\", \"three\"]"
        with pytest.raises(ValueError):
            _extract_json_from_response(raw_array)

    def test_empty_string_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _extract_json_from_response("")

    def test_returns_dict_type(self, valid_brief_dict: dict[str, Any]) -> None:
        result = _extract_json_from_response(json.dumps(valid_brief_dict))
        assert isinstance(result, dict)

    def test_nested_structure_preserved(self, valid_brief_dict: dict[str, Any]) -> None:
        result = _extract_json_from_response(json.dumps(valid_brief_dict))
        assert "swatches" in result["color_palette"]
        assert len(result["color_palette"]["swatches"]) == 5


# ---------------------------------------------------------------------------
# Environment variable helpers
# ---------------------------------------------------------------------------


class TestGetModel:
    """Tests for the _get_model helper."""

    def test_returns_default_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_MODEL", None)
            result = _get_model()
        assert result == "gpt-4o"

    def test_returns_env_value_when_set(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4o-mini"}):
            result = _get_model()
        assert result == "gpt-4o-mini"

    def test_strips_whitespace_from_env_value(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MODEL": "  gpt-4o  "}):
            result = _get_model()
        assert result == "gpt-4o"

    def test_empty_env_value_falls_back_to_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MODEL": ""}):
            result = _get_model()
        assert result == "gpt-4o"


class TestGetMaxTokens:
    """Tests for the _get_max_tokens helper."""

    def test_returns_default_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_MAX_TOKENS", None)
            result = _get_max_tokens()
        assert result == 2048

    def test_returns_env_value_when_set(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MAX_TOKENS": "4096"}):
            result = _get_max_tokens()
        assert result == 4096

    def test_invalid_string_returns_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MAX_TOKENS": "not-a-number"}):
            result = _get_max_tokens()
        assert result == 2048

    def test_zero_returns_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MAX_TOKENS": "0"}):
            result = _get_max_tokens()
        assert result == 2048

    def test_negative_returns_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_MAX_TOKENS": "-100"}):
            result = _get_max_tokens()
        assert result == 2048


class TestGetTemperature:
    """Tests for the _get_temperature helper."""

    def test_returns_default_when_not_set(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_TEMPERATURE", None)
            result = _get_temperature()
        assert result == pytest.approx(0.7)

    def test_returns_env_value_when_set(self) -> None:
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "1.2"}):
            result = _get_temperature()
        assert result == pytest.approx(1.2)

    def test_clamps_to_zero(self) -> None:
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "-1.0"}):
            result = _get_temperature()
        assert result == pytest.approx(0.0)

    def test_clamps_to_two(self) -> None:
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "5.0"}):
            result = _get_temperature()
        assert result == pytest.approx(2.0)

    def test_invalid_string_returns_default(self) -> None:
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "hot"}):
            result = _get_temperature()
        assert result == pytest.approx(0.7)

    def test_zero_is_valid(self) -> None:
        with patch.dict(os.environ, {"OPENAI_TEMPERATURE": "0.0"}):
            result = _get_temperature()
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _get_openai_client
# ---------------------------------------------------------------------------


class TestGetOpenAIClient:
    """Tests for the _get_openai_client helper."""

    def test_raises_runtime_error_when_api_key_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                _get_openai_client()

    def test_raises_runtime_error_when_api_key_empty(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                _get_openai_client()

    def test_raises_runtime_error_when_api_key_whitespace(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "   "}):
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                _get_openai_client()

    def test_returns_openai_client_when_key_present(self) -> None:
        from openai import OpenAI
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-12345"}):
            client = _get_openai_client()
        assert isinstance(client, OpenAI)


# ---------------------------------------------------------------------------
# generate_brief — happy path
# ---------------------------------------------------------------------------


class TestGenerateBrief:
    """Tests for the generate_brief public function."""

    def test_returns_design_brief_instance(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        """Happy path: valid API response produces a DesignBrief."""
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee landing page.")

        assert isinstance(result, DesignBrief)

    def test_brief_title_matches_response(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee brand.")

        assert result.title == "Eco Coffee Landing Page"

    def test_brief_color_palette_parsed(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee brand.")

        assert len(result.color_palette.swatches) == 5
        assert result.color_palette.swatches[0].hex_code == "#3B2314"

    def test_brief_typography_parsed(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee brand.")

        assert result.typography.display_font == "Playfair Display"
        assert result.typography.body_font == "Inter"

    def test_brief_layout_sections_parsed(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee brand.")

        assert len(result.layout.sections) == 5

    def test_api_called_with_system_and_user_messages(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        """Verify the API is called with correctly structured messages."""
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                generate_brief("A coffee brand.")

                call_kwargs = mock_client.chat.completions.create.call_args

        messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["messages"]
        # Find messages in call
        if call_kwargs.kwargs:
            messages = call_kwargs.kwargs.get("messages", [])
        else:
            messages = []

        assert any(m["role"] == "system" for m in messages)
        assert any(m["role"] == "user" for m in messages)

    def test_empty_user_input_raises_value_error(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with pytest.raises(ValueError, match="must not be empty"):
                generate_brief("")

    def test_whitespace_user_input_raises_value_error(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with pytest.raises(ValueError, match="must not be empty"):
                generate_brief("   ")

    def test_missing_api_key_raises_runtime_error(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                generate_brief("A coffee brand.")

    def test_empty_api_response_raises_runtime_error(self) -> None:
        """If the model returns empty content, a RuntimeError should be raised."""
        mock_response = _make_openai_response("")
        mock_response.choices[0].message.content = None

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                with pytest.raises(RuntimeError):
                    generate_brief("A coffee brand.")

    def test_invalid_json_response_raises_value_error(self) -> None:
        mock_response = _make_openai_response("Sorry, I cannot help with that.")

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                with pytest.raises(ValueError):
                    generate_brief("A coffee brand.")

    def test_schema_mismatch_raises_value_error(self) -> None:
        """JSON that doesn't match DesignBrief schema raises ValueError."""
        bad_data = {"title": "Only a title", "unexpected_field": True}
        mock_response = _make_openai_response(json.dumps(bad_data))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                with pytest.raises(ValueError, match="schema"):
                    generate_brief("A coffee brand.")

    def test_openai_rate_limit_error_propagates(self) -> None:
        """RateLimitError from OpenAI should propagate unchanged."""
        from openai import RateLimitError

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_response_obj = MagicMock()
                mock_response_obj.status_code = 429
                mock_client.chat.completions.create.side_effect = RateLimitError(
                    message="Rate limit exceeded",
                    response=mock_response_obj,
                    body={},
                )
                MockOpenAI.return_value = mock_client

                with pytest.raises(RateLimitError):
                    generate_brief("A coffee brand.")

    def test_openai_api_error_propagates(self) -> None:
        """Generic APIError from OpenAI should propagate unchanged."""
        from openai import APIStatusError

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_response_obj = MagicMock()
                mock_response_obj.status_code = 500
                mock_client.chat.completions.create.side_effect = APIStatusError(
                    message="Internal server error",
                    response=mock_response_obj,
                    body={},
                )
                MockOpenAI.return_value = mock_client

                with pytest.raises(APIStatusError):
                    generate_brief("A coffee brand.")

    def test_response_wrapped_in_markdown_fences_still_works(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        """Model sometimes wraps JSON in markdown fences — should still parse."""
        json_str = json.dumps(valid_brief_dict)
        raw_content = f"```json\n{json_str}\n```"
        mock_response = _make_openai_response(raw_content)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief("A coffee brand.")

        assert isinstance(result, DesignBrief)
        assert result.title == "Eco Coffee Landing Page"

    def test_uses_model_from_environment(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "OPENAI_MODEL": "gpt-4o-mini"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                generate_brief("A coffee brand.")

                call_kwargs = mock_client.chat.completions.create.call_args.kwargs

        assert call_kwargs.get("model") == "gpt-4o-mini"

    def test_uses_temperature_from_environment(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "OPENAI_TEMPERATURE": "0.3"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                generate_brief("A coffee brand.")

                call_kwargs = mock_client.chat.completions.create.call_args.kwargs

        assert call_kwargs.get("temperature") == pytest.approx(0.3)

    def test_uses_max_tokens_from_environment(
        self, valid_brief_dict: dict[str, Any]
    ) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "OPENAI_MAX_TOKENS": "1024"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                generate_brief("A coffee brand.")

                call_kwargs = mock_client.chat.completions.create.call_args.kwargs

        assert call_kwargs.get("max_tokens") == 1024


# ---------------------------------------------------------------------------
# generate_brief_from_dict
# ---------------------------------------------------------------------------


class TestGenerateBriefFromDict:
    """Tests for the generate_brief_from_dict convenience wrapper."""

    def test_returns_dict(self, valid_brief_dict: dict[str, Any]) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        assert isinstance(result, dict)

    def test_dict_contains_expected_keys(self, valid_brief_dict: dict[str, Any]) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        expected_keys = {
            "title",
            "project_overview",
            "mood_descriptors",
            "color_palette",
            "typography",
            "layout",
            "copy_hierarchy",
            "additional_notes",
        }
        assert set(result.keys()) == expected_keys

    def test_dict_title_correct(self, valid_brief_dict: dict[str, Any]) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        assert result["title"] == "Eco Coffee Landing Page"

    def test_color_palette_is_dict(self, valid_brief_dict: dict[str, Any]) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        assert isinstance(result["color_palette"], dict)
        assert "swatches" in result["color_palette"]

    def test_empty_input_raises_value_error(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with pytest.raises(ValueError):
                generate_brief_from_dict("")

    def test_typography_is_dict(self, valid_brief_dict: dict[str, Any]) -> None:
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        assert isinstance(result["typography"], dict)
        assert "display_font" in result["typography"]

    def test_json_serialisable(self, valid_brief_dict: dict[str, Any]) -> None:
        """The returned dict must be trivially JSON-serialisable."""
        mock_response = _make_openai_response(json.dumps(valid_brief_dict))

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            with patch("brief_forge.generator.OpenAI") as MockOpenAI:
                mock_client = MagicMock()
                mock_client.chat.completions.create.return_value = mock_response
                MockOpenAI.return_value = mock_client

                result = generate_brief_from_dict("A coffee brand.")

        # Should not raise
        serialised = json.dumps(result)
        assert isinstance(serialised, str)
