"""Pydantic data models for Brief Forge.

Defines the core domain objects used throughout the application:

- :class:`ColorSwatch` — a single colour with name, hex code, and usage note.
- :class:`ColorPalette` — an ordered collection of colour swatches.
- :class:`TypographyPairing` — a font pairing with display and body typefaces.
- :class:`Layout` — suggested grid and structural layout description.
- :class:`DesignBrief` — the top-level container that aggregates all sections.

All models are built on :class:`pydantic.BaseModel` so they benefit from
automatic validation, clear error messages, and trivial JSON serialisation
via :meth:`~pydantic.BaseModel.model_dump` / :meth:`~pydantic.BaseModel.model_dump_json`.

Example usage::

    from brief_forge.models import DesignBrief

    brief = DesignBrief(
        title="My Brief",
        project_overview="A landing page for …",
        mood_descriptors=["warm", "earthy", "premium"],
        color_palette=ColorPalette(swatches=[…]),
        typography=TypographyPairing(display_font="Playfair Display", …),
        layout=Layout(description="Single-column hero…", …),
        copy_hierarchy=["Headline", "Sub-headline", "CTA"],
    )
    json_str = brief.model_dump_json(indent=2)
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEX_RE = re.compile(r'^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$')


def _normalise_hex(value: str) -> str:
    """Normalise a hex colour code to uppercase 7-character form.

    Parameters
    ----------
    value:
        Raw hex string, e.g. ``"#3b2314"`` or ``"#FFF"``.

    Returns
    -------
    str
        Uppercase, 7-character hex string, e.g. ``"#3B2314"`` or ``"#FFFFFF"``.

    Raises
    ------
    ValueError
        If *value* is not a valid 3- or 6-digit hex colour code.
    """
    stripped = value.strip()
    if not _HEX_RE.match(stripped):
        raise ValueError(
            f"Invalid hex colour code: {value!r}. "
            "Expected format: #RGB or #RRGGBB (e.g. '#3B2314')."
        )
    hex_digits = stripped[1:]
    if len(hex_digits) == 3:
        hex_digits = "".join(ch * 2 for ch in hex_digits)
    return f"#{hex_digits.upper()}"


# ---------------------------------------------------------------------------
# ColorSwatch
# ---------------------------------------------------------------------------


class ColorSwatch(BaseModel):
    """A single colour entry within a colour palette.

    Attributes
    ----------
    role:
        Semantic role of the colour, e.g. ``"Primary"`` or ``"Background"``.
    name:
        Human-readable colour name, e.g. ``"Espresso Brown"``.
    hex_code:
        6-digit HTML hex colour code including the leading ``#``,
        normalised to uppercase (e.g. ``"#3B2314"``).
    usage:
        Short description of where this colour should be applied,
        e.g. ``"Headlines and primary CTAs"``.
    """

    role: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Semantic role of the colour (e.g. 'Primary', 'Accent').",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Human-readable colour name (e.g. 'Espresso Brown').",
    )
    hex_code: str = Field(
        ...,
        description="HTML hex colour code, e.g. '#3B2314'.",
    )
    usage: str = Field(
        default="",
        max_length=256,
        description="Where this colour is applied in the design.",
    )

    @field_validator("hex_code", mode="before")
    @classmethod
    def validate_hex_code(cls, v: Any) -> str:
        """Validate and normalise the hex colour code."""
        if not isinstance(v, str):
            raise ValueError(f"hex_code must be a string, got {type(v).__name__!r}.")
        return _normalise_hex(v)

    @field_validator("role", "name", mode="before")
    @classmethod
    def strip_strings(cls, v: Any) -> str:
        """Strip leading/trailing whitespace from string fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    def to_dict(self) -> dict[str, str]:
        """Return a plain dictionary representation of this swatch.

        Returns
        -------
        dict[str, str]
            Keys: ``role``, ``name``, ``hex_code``, ``usage``.
        """
        return {
            "role": self.role,
            "name": self.name,
            "hex_code": self.hex_code,
            "usage": self.usage,
        }


# ---------------------------------------------------------------------------
# ColorPalette
# ---------------------------------------------------------------------------


class ColorPalette(BaseModel):
    """An ordered collection of colour swatches forming a complete palette.

    Attributes
    ----------
    swatches:
        Ordered list of :class:`ColorSwatch` objects.  At least one swatch
        must be provided; five is the recommended design standard.
    """

    swatches: list[ColorSwatch] = Field(
        ...,
        min_length=1,
        description="Ordered list of colour swatches (minimum 1).",
    )

    @field_validator("swatches", mode="before")
    @classmethod
    def coerce_swatches(cls, v: Any) -> list[Any]:
        """Ensure swatches is always a list."""
        if isinstance(v, dict):
            return [v]
        return v

    @property
    def hex_codes(self) -> list[str]:
        """Return all hex codes in palette order.

        Returns
        -------
        list[str]
            Hex code strings, e.g. ``['#3B2314', '#7D9B76', …]``.
        """
        return [swatch.hex_code for swatch in self.swatches]

    def by_role(self, role: str) -> ColorSwatch | None:
        """Look up a swatch by its semantic role (case-insensitive).

        Parameters
        ----------
        role:
            Role string to search for, e.g. ``"Primary"``.

        Returns
        -------
        ColorSwatch or None
            The first matching swatch, or ``None`` if not found.
        """
        role_lower = role.strip().lower()
        for swatch in self.swatches:
            if swatch.role.lower() == role_lower:
                return swatch
        return None

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation of this palette.

        Returns
        -------
        dict[str, Any]
            Keys: ``swatches`` (list of swatch dicts).
        """
        return {"swatches": [s.to_dict() for s in self.swatches]}


# ---------------------------------------------------------------------------
# TypographyPairing
# ---------------------------------------------------------------------------


class TypographyPairing(BaseModel):
    """A font pairing recommendation for a design brief.

    Attributes
    ----------
    display_font:
        Name of the display/headline typeface, e.g. ``"Playfair Display"``.
    body_font:
        Name of the body-copy typeface, e.g. ``"Inter"``.
    accent_font:
        Optional name of an accent/label typeface.
    display_weight:
        CSS font-weight for display usage, e.g. ``"700"`` or ``"Bold"``.
    body_weight:
        CSS font-weight for body usage, e.g. ``"400"``.
    notes:
        Any additional typography guidance (scale, line-height, etc.).
    """

    display_font: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Typeface used for headlines and display text.",
    )
    body_font: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Typeface used for body copy.",
    )
    accent_font: str = Field(
        default="",
        max_length=128,
        description="Optional accent or label typeface.",
    )
    display_weight: str = Field(
        default="700",
        max_length=32,
        description="Font-weight for display/headline usage.",
    )
    body_weight: str = Field(
        default="400",
        max_length=32,
        description="Font-weight for body copy.",
    )
    notes: str = Field(
        default="",
        max_length=512,
        description="Additional typography guidance.",
    )

    @field_validator("display_font", "body_font", "accent_font", mode="before")
    @classmethod
    def strip_font_names(cls, v: Any) -> str:
        """Strip whitespace from font name fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    def to_dict(self) -> dict[str, str]:
        """Return a plain dictionary representation of this typography pairing.

        Returns
        -------
        dict[str, str]
            All typography fields as string key-value pairs.
        """
        return {
            "display_font": self.display_font,
            "body_font": self.body_font,
            "accent_font": self.accent_font,
            "display_weight": self.display_weight,
            "body_weight": self.body_weight,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class Layout(BaseModel):
    """Structural layout recommendations for a design project.

    Attributes
    ----------
    description:
        High-level description of the overall layout approach.
    grid:
        Grid system description, e.g. ``"12-column, 24 px gutter"``.
    sections:
        Ordered list of page/screen sections with brief descriptions.
    spacing_notes:
        Guidance on spacing, padding, and rhythm.
    """

    description: str = Field(
        ...,
        min_length=1,
        description="High-level layout description.",
    )
    grid: str = Field(
        default="12-column grid",
        max_length=256,
        description="Grid system specification.",
    )
    sections: list[str] = Field(
        default_factory=list,
        description="Ordered list of layout sections.",
    )
    spacing_notes: str = Field(
        default="",
        max_length=512,
        description="Spacing and rhythm guidance.",
    )

    @field_validator("description", mode="before")
    @classmethod
    def strip_description(cls, v: Any) -> str:
        """Strip whitespace from the description field."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("sections", mode="before")
    @classmethod
    def coerce_sections(cls, v: Any) -> list[Any]:
        """Accept a newline-delimited string as well as a list."""
        if isinstance(v, str):
            return [line.strip() for line in v.splitlines() if line.strip()]
        return v

    def to_dict(self) -> dict[str, Any]:
        """Return a plain dictionary representation of this layout.

        Returns
        -------
        dict[str, Any]
            Keys: ``description``, ``grid``, ``sections``, ``spacing_notes``.
        """
        return {
            "description": self.description,
            "grid": self.grid,
            "sections": list(self.sections),
            "spacing_notes": self.spacing_notes,
        }


# ---------------------------------------------------------------------------
# DesignBrief
# ---------------------------------------------------------------------------


class DesignBrief(BaseModel):
    """Top-level container for a complete design brief.

    Every field is required except those with defaults.  Pydantic validation
    ensures that a :class:`DesignBrief` instance always contains all sections
    even when the upstream LLM response omits optional detail.

    Attributes
    ----------
    title:
        Short descriptive title for the brief, e.g.
        ``"Sustainable Coffee Landing Page"``.
    project_overview:
        One-to-three sentence summary of the project's goals and audience.
    mood_descriptors:
        A list of one-word or short-phrase mood/tone descriptors.
    color_palette:
        The :class:`ColorPalette` for this brief.
    typography:
        The :class:`TypographyPairing` recommendation.
    layout:
        The :class:`Layout` structural recommendation.
    copy_hierarchy:
        Ordered list of copy elements from most to least prominent,
        e.g. ``["Hero Headline", "Sub-headline", "CTA"]``.
    additional_notes:
        Free-form section for any extra guidance not captured above.
    """

    title: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Short title for the design brief.",
    )
    project_overview: str = Field(
        ...,
        min_length=1,
        description="Summary of the project goals and target audience.",
    )
    mood_descriptors: list[str] = Field(
        ...,
        min_length=1,
        description="Mood/tone descriptors (at least one required).",
    )
    color_palette: ColorPalette = Field(
        ...,
        description="The colour palette for this brief.",
    )
    typography: TypographyPairing = Field(
        ...,
        description="Font pairing recommendation.",
    )
    layout: Layout = Field(
        ...,
        description="Structural layout recommendation.",
    )
    copy_hierarchy: list[str] = Field(
        ...,
        min_length=1,
        description="Ordered copy elements from most to least prominent.",
    )
    additional_notes: str = Field(
        default="",
        description="Any extra guidance not captured in other sections.",
    )

    @field_validator("title", "project_overview", mode="before")
    @classmethod
    def strip_text_fields(cls, v: Any) -> str:
        """Strip whitespace from primary text fields."""
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("mood_descriptors", mode="before")
    @classmethod
    def coerce_mood_descriptors(cls, v: Any) -> list[str]:
        """Accept a comma- or newline-delimited string as well as a list."""
        if isinstance(v, str):
            # Try comma-separated first, fall back to newline-separated.
            separators = "," if "," in v else "\n"
            return [part.strip() for part in v.split(separators) if part.strip()]
        return v

    @field_validator("copy_hierarchy", mode="before")
    @classmethod
    def coerce_copy_hierarchy(cls, v: Any) -> list[str]:
        """Accept a newline-delimited string as well as a list."""
        if isinstance(v, str):
            return [line.strip() for line in v.splitlines() if line.strip()]
        return v

    @model_validator(mode="after")
    def validate_mood_not_empty_strings(self) -> "DesignBrief":
        """Ensure no mood descriptors are blank after stripping."""
        cleaned = [m.strip() for m in self.mood_descriptors if m.strip()]
        if not cleaned:
            raise ValueError(
                "mood_descriptors must contain at least one non-empty string."
            )
        self.mood_descriptors = cleaned
        return self

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return a fully serialisable plain-Python dictionary.

        Nested model objects are recursively converted via their own
        ``to_dict`` helpers so the result contains only built-in types
        (``str``, ``list``, ``dict``).

        Returns
        -------
        dict[str, Any]
            Plain dictionary representation of the complete brief.
        """
        return {
            "title": self.title,
            "project_overview": self.project_overview,
            "mood_descriptors": list(self.mood_descriptors),
            "color_palette": self.color_palette.to_dict(),
            "typography": self.typography.to_dict(),
            "layout": self.layout.to_dict(),
            "copy_hierarchy": list(self.copy_hierarchy),
            "additional_notes": self.additional_notes,
        }

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise the brief to a JSON string.

        Parameters
        ----------
        indent:
            JSON indentation level (default: 2).

        Returns
        -------
        str
            Pretty-printed JSON string.
        """
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DesignBrief":
        """Construct a :class:`DesignBrief` from a plain dictionary.

        This is a thin convenience wrapper around Pydantic's
        :meth:`~pydantic.BaseModel.model_validate`.

        Parameters
        ----------
        data:
            Dictionary that matches the :class:`DesignBrief` schema.

        Returns
        -------
        DesignBrief
            A validated :class:`DesignBrief` instance.

        Raises
        ------
        pydantic.ValidationError
            If *data* does not satisfy the schema constraints.
        """
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> "DesignBrief":
        """Construct a :class:`DesignBrief` from a JSON string.

        Parameters
        ----------
        json_str:
            JSON-encoded string matching the :class:`DesignBrief` schema.

        Returns
        -------
        DesignBrief
            A validated :class:`DesignBrief` instance.

        Raises
        ------
        pydantic.ValidationError
            If the decoded data does not satisfy the schema constraints.
        ValueError
            If *json_str* is not valid JSON.
        """
        return cls.model_validate_json(json_str)
