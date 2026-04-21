"""LLM generator module for Brief Forge.

This module handles all OpenAI API interaction.  It is responsible for:

1. Building a structured, detailed system + user prompt from plain-language
   user input.
2. Calling the OpenAI Chat Completions API and requesting a JSON response
   that matches the :class:`~brief_forge.models.DesignBrief` schema.
3. Parsing and validating the raw JSON response into a
   :class:`~brief_forge.models.DesignBrief` instance via Pydantic.

All configuration (model name, temperature, max tokens) is read from
environment variables so that the module works correctly with the project's
``.env`` file without any hardcoded secrets.

Example usage::

    from brief_forge.generator import generate_brief

    brief = generate_brief(
        "A landing page for a sustainable coffee brand. "
        "Earthy, premium, millennial audience."
    )
    print(brief.title)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError, RateLimitError
from pydantic import ValidationError

from brief_forge.models import DesignBrief

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

_DEFAULT_MODEL = "gpt-4o"
_DEFAULT_MAX_TOKENS = 2048
_DEFAULT_TEMPERATURE = 0.7

# The JSON schema we ask the model to emit.  Keeping it inline ensures the
# prompt is always in sync with the Pydantic models without needing a
# separate schema file.
_BRIEF_JSON_SCHEMA = """
{
  "title": "string — short descriptive title for the brief",
  "project_overview": "string — 2-3 sentence summary of goals and audience",
  "mood_descriptors": ["string", "..."],
  "color_palette": {
    "swatches": [
      {
        "role": "string (e.g. Primary, Secondary, Background, Surface, Text, Accent)",
        "name": "string — descriptive colour name",
        "hex_code": "string — 6-digit hex starting with #",
        "usage": "string — where this colour is applied"
      }
    ]
  },
  "typography": {
    "display_font": "string — headline typeface name",
    "body_font": "string — body copy typeface name",
    "accent_font": "string — optional accent typeface name (can be empty)",
    "display_weight": "string — CSS font-weight for headlines (e.g. 700)",
    "body_weight": "string — CSS font-weight for body (e.g. 400)",
    "notes": "string — additional typography guidance"
  },
  "layout": {
    "description": "string — high-level layout approach",
    "grid": "string — grid system description (e.g. 12-column, 24px gutter)",
    "sections": ["string", "..."],
    "spacing_notes": "string — spacing and rhythm guidance"
  },
  "copy_hierarchy": ["string", "..."],
  "additional_notes": "string — any extra guidance (can be empty)"
}
"""

_SYSTEM_PROMPT = f"""You are an expert creative director and UX designer with 15+ years of \
experience producing design briefs for agencies, startups, and Fortune 500 brands.

Your task is to transform a plain-language design goal provided by the user into a \
complete, structured design brief that can be used directly in Figma, Canva, or Adobe tools.

You MUST respond with a single, valid JSON object that exactly matches the following schema. \
Do not include any text, explanation, or markdown outside the JSON object.

Required JSON schema:
{_BRIEF_JSON_SCHEMA}

Guidelines for generating high-quality briefs:
- title: Create a concise, descriptive title (max ~8 words).
- project_overview: Summarise the project type, primary audience, and key goal in 2-3 sentences.
- mood_descriptors: Provide 4-6 single-word or short-phrase descriptors that capture the \
emotional tone (e.g. "warm", "premium", "playful").
- color_palette: Provide exactly 5 swatches with semantically meaningful roles: Primary, \
Secondary, Background, Surface, and Text. Each hex_code MUST be a valid 6-digit HTML hex \
colour (e.g. #3B2314). Choose colours that are visually harmonious and appropriate to the mood.
- typography: Select real, widely available typefaces (Google Fonts preferred). \
Provide display and body fonts; accent font is optional.
- layout: Describe a concrete structural layout with named page/screen sections in order.
- copy_hierarchy: List the actual copy elements from most to least prominent, with suggested \
wording where relevant.
- additional_notes: Include any platform-specific guidance, accessibility notes, or design \
system recommendations.

Return ONLY the raw JSON object. No markdown fences, no preamble, no explanation."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_openai_client() -> OpenAI:
    """Construct and return a configured :class:`openai.OpenAI` client.

    The API key is read from the ``OPENAI_API_KEY`` environment variable.

    Returns
    -------
    OpenAI
        A ready-to-use OpenAI client instance.

    Raises
    ------
    RuntimeError
        If ``OPENAI_API_KEY`` is not set in the environment.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY environment variable is not set. "
            "Copy .env.example to .env and add your API key."
        )
    return OpenAI(api_key=api_key)


def _get_model() -> str:
    """Return the OpenAI model name from the environment or the default.

    Returns
    -------
    str
        Model identifier string, e.g. ``"gpt-4o"``.
    """
    return os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


def _get_max_tokens() -> int:
    """Return the max-tokens setting from the environment or the default.

    Returns
    -------
    int
        Maximum number of tokens the model may generate.
    """
    raw = os.environ.get("OPENAI_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS))
    try:
        value = int(raw)
        return value if value > 0 else _DEFAULT_MAX_TOKENS
    except (ValueError, TypeError):
        logger.warning(
            "Invalid OPENAI_MAX_TOKENS value %r — using default %d.",
            raw,
            _DEFAULT_MAX_TOKENS,
        )
        return _DEFAULT_MAX_TOKENS


def _get_temperature() -> float:
    """Return the sampling temperature from the environment or the default.

    Returns
    -------
    float
        Temperature value in the range [0.0, 2.0].
    """
    raw = os.environ.get("OPENAI_TEMPERATURE", str(_DEFAULT_TEMPERATURE))
    try:
        value = float(raw)
        return max(0.0, min(2.0, value))
    except (ValueError, TypeError):
        logger.warning(
            "Invalid OPENAI_TEMPERATURE value %r — using default %.1f.",
            raw,
            _DEFAULT_TEMPERATURE,
        )
        return _DEFAULT_TEMPERATURE


def build_user_prompt(user_input: str) -> str:
    """Build the user-facing prompt from the plain-language design goal.

    Wraps the raw input in a short context sentence so the model
    understands exactly what it should produce.

    Parameters
    ----------
    user_input:
        The plain-language description provided by the user via the web UI.

    Returns
    -------
    str
        The formatted user prompt string ready to send to the API.

    Raises
    ------
    ValueError
        If *user_input* is empty or contains only whitespace.
    """
    cleaned = user_input.strip()
    if not cleaned:
        raise ValueError(
            "user_input must not be empty — please provide a design description."
        )
    return (
        f"Please generate a complete design brief for the following project:\n\n"
        f"{cleaned}\n\n"
        f"Return the brief as a single JSON object matching the schema exactly."
    )


def _extract_json_from_response(content: str) -> dict[str, Any]:
    """Extract and parse a JSON object from the model's response string.

    Handles edge cases where the model wraps the JSON in markdown fences
    (`` ```json ... ``` ``) despite being instructed not to.

    Parameters
    ----------
    content:
        Raw text content from the model's response message.

    Returns
    -------
    dict[str, Any]
        Parsed JSON as a Python dictionary.

    Raises
    ------
    ValueError
        If no valid JSON object can be found or parsed in *content*.
    """
    stripped = content.strip()

    # Strip markdown code fences if present (model sometimes ignores instructions).
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove first line (```json or ```) and last line (```)
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        stripped = "\n".join(inner_lines).strip()

    # Attempt to find the JSON object boundaries if there is surrounding text.
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(
            f"No JSON object found in model response. "
            f"Response preview: {content[:200]!r}"
        )

    json_str = stripped[start : end + 1]

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Failed to parse JSON from model response: {exc}. "
            f"Response preview: {content[:200]!r}"
        ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected a JSON object (dict) but got {type(data).__name__!r}. "
            f"Response preview: {content[:200]!r}"
        )

    return data


def _call_openai_api(
    client: OpenAI,
    user_prompt: str,
    model: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Make the Chat Completions API call and return the response content string.

    Parameters
    ----------
    client:
        Configured :class:`openai.OpenAI` instance.
    user_prompt:
        The formatted user message string.
    model:
        OpenAI model identifier.
    max_tokens:
        Maximum response tokens.
    temperature:
        Sampling temperature.

    Returns
    -------
    str
        The raw text content of the first response choice.

    Raises
    ------
    RuntimeError
        If the API returns an empty or null response content.
    openai.APIError
        For upstream OpenAI API errors.
    openai.RateLimitError
        When the rate limit is exceeded.
    openai.APIConnectionError
        On network connectivity issues.
    openai.APITimeoutError
        When the request times out.
    """
    logger.debug(
        "Calling OpenAI API: model=%s, max_tokens=%d, temperature=%.2f",
        model,
        max_tokens,
        temperature,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
    )

    choice = response.choices[0]
    content = choice.message.content

    if not content:
        finish_reason = choice.finish_reason
        raise RuntimeError(
            f"OpenAI returned an empty response (finish_reason={finish_reason!r}). "
            "Try increasing OPENAI_MAX_TOKENS or rephrasing your input."
        )

    logger.debug(
        "Received response: finish_reason=%s, content_length=%d",
        choice.finish_reason,
        len(content),
    )
    return content


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_brief(user_input: str) -> DesignBrief:
    """Generate a structured :class:`~brief_forge.models.DesignBrief` from plain text.

    This is the primary public entry point for the generator module.  It:

    1. Validates *user_input* is non-empty.
    2. Builds the formatted user prompt.
    3. Calls the OpenAI Chat Completions API.
    4. Parses and validates the JSON response into a :class:`DesignBrief`.

    Parameters
    ----------
    user_input:
        Plain-language description of the design project.  The richer the
        description, the more detailed the brief will be.

    Returns
    -------
    DesignBrief
        A fully validated :class:`~brief_forge.models.DesignBrief` object.

    Raises
    ------
    ValueError
        If *user_input* is empty, or if the model response cannot be parsed
        into a valid :class:`DesignBrief`.
    RuntimeError
        If ``OPENAI_API_KEY`` is not configured, or if the API returns an
        empty response.
    openai.RateLimitError
        When the OpenAI rate limit is exceeded.
    openai.APIConnectionError
        On network connectivity issues.
    openai.APITimeoutError
        When the API request times out.
    openai.APIError
        For any other upstream OpenAI API error.
    """
    user_prompt = build_user_prompt(user_input)

    client = _get_openai_client()
    model = _get_model()
    max_tokens = _get_max_tokens()
    temperature = _get_temperature()

    try:
        raw_content = _call_openai_api(
            client=client,
            user_prompt=user_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except (RateLimitError, APIConnectionError, APITimeoutError, APIError):
        # Re-raise OpenAI errors as-is so callers can handle them specifically.
        raise

    try:
        data = _extract_json_from_response(raw_content)
    except ValueError as exc:
        raise ValueError(
            f"Could not extract JSON from OpenAI response: {exc}"
        ) from exc

    try:
        brief = DesignBrief.from_dict(data)
    except ValidationError as exc:
        raise ValueError(
            f"OpenAI response did not match the DesignBrief schema: {exc}"
        ) from exc

    logger.info("Generated design brief: %r", brief.title)
    return brief


def generate_brief_from_dict(user_input: str) -> dict[str, Any]:
    """Generate a brief and return it as a plain dictionary.

    Convenience wrapper around :func:`generate_brief` that returns the
    plain-Python :meth:`~brief_forge.models.DesignBrief.to_dict`
    representation instead of a Pydantic model instance.  Useful for
    Flask route handlers that need to serialise the result to JSON.

    Parameters
    ----------
    user_input:
        Plain-language design description.

    Returns
    -------
    dict[str, Any]
        Plain dictionary representation of the :class:`DesignBrief`.

    Raises
    ------
    Same exceptions as :func:`generate_brief`.
    """
    return generate_brief(user_input).to_dict()
