"""Unit tests for the Brief Forge data models (brief_forge/models.py).

Covers:
- :class:`~brief_forge.models.ColorSwatch` validation and normalisation.
- :class:`~brief_forge.models.ColorPalette` collection helpers.
- :class:`~brief_forge.models.TypographyPairing` defaults and validation.
- :class:`~brief_forge.models.Layout` section coercion.
- :class:`~brief_forge.models.DesignBrief` full round-trip (to_dict / from_dict / to_json / from_json).

All tests use pytest conventions and have zero external I/O.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from brief_forge.models import (
    ColorPalette,
    ColorSwatch,
    DesignBrief,
    Layout,
    TypographyPairing,
    _normalise_hex,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_swatch() -> ColorSwatch:
    """Return a minimal, valid ColorSwatch."""
    return ColorSwatch(
        role="Primary",
        name="Espresso Brown",
        hex_code="#3B2314",
        usage="Headlines and CTAs",
    )


@pytest.fixture()
def sample_palette(sample_swatch: ColorSwatch) -> ColorPalette:
    """Return a ColorPalette with one swatch."""
    return ColorPalette(swatches=[sample_swatch])


@pytest.fixture()
def sample_typography() -> TypographyPairing:
    """Return a minimal, valid TypographyPairing."""
    return TypographyPairing(
        display_font="Playfair Display",
        body_font="Inter",
    )


@pytest.fixture()
def sample_layout() -> Layout:
    """Return a minimal, valid Layout."""
    return Layout(
        description="Single-column hero with full-bleed background.",
        sections=["Hero", "Features", "CTA"],
    )


@pytest.fixture()
def sample_brief(
    sample_palette: ColorPalette,
    sample_typography: TypographyPairing,
    sample_layout: Layout,
) -> DesignBrief:
    """Return a fully populated, valid DesignBrief."""
    return DesignBrief(
        title="Sustainable Coffee Landing Page",
        project_overview="A conversion-focused landing page for a sustainable coffee brand.",
        mood_descriptors=["earthy", "premium", "warm"],
        color_palette=sample_palette,
        typography=sample_typography,
        layout=sample_layout,
        copy_hierarchy=["Hero Headline", "Sub-headline", "CTA Button"],
        additional_notes="Keep the tone approachable.",
    )


# ---------------------------------------------------------------------------
# _normalise_hex helper
# ---------------------------------------------------------------------------


class TestNormaliseHex:
    """Tests for the internal _normalise_hex helper."""

    def test_lowercase_six_digit_hex(self) -> None:
        assert _normalise_hex("#3b2314") == "#3B2314"

    def test_uppercase_six_digit_hex(self) -> None:
        assert _normalise_hex("#3B2314") == "#3B2314"

    def test_three_digit_hex_expands_to_six(self) -> None:
        assert _normalise_hex("#FFF") == "#FFFFFF"

    def test_three_digit_lowercase_expands(self) -> None:
        assert _normalise_hex("#abc") == "#AABBCC"

    def test_strips_surrounding_whitespace(self) -> None:
        assert _normalise_hex("  #3B2314  ") == "#3B2314"

    def test_invalid_hex_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex colour code"):
            _normalise_hex("not-a-colour")

    def test_missing_hash_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex colour code"):
            _normalise_hex("3B2314")

    def test_seven_digit_hex_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex colour code"):
            _normalise_hex("#3B23140")

    def test_two_digit_hex_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid hex colour code"):
            _normalise_hex("#AB")


# ---------------------------------------------------------------------------
# ColorSwatch
# ---------------------------------------------------------------------------


class TestColorSwatch:
    """Tests for ColorSwatch validation and serialisation."""

    def test_valid_swatch_creates_successfully(self, sample_swatch: ColorSwatch) -> None:
        assert sample_swatch.role == "Primary"
        assert sample_swatch.name == "Espresso Brown"
        assert sample_swatch.hex_code == "#3B2314"
        assert sample_swatch.usage == "Headlines and CTAs"

    def test_hex_code_normalised_to_uppercase(self) -> None:
        swatch = ColorSwatch(role="Accent", name="Sage", hex_code="#7d9b76")
        assert swatch.hex_code == "#7D9B76"

    def test_three_digit_hex_expanded(self) -> None:
        swatch = ColorSwatch(role="BG", name="White", hex_code="#fff")
        assert swatch.hex_code == "#FFFFFF"

    def test_usage_defaults_to_empty_string(self) -> None:
        swatch = ColorSwatch(role="Text", name="Dark", hex_code="#111111")
        assert swatch.usage == ""

    def test_invalid_hex_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(role="X", name="Bad", hex_code="not-hex")

    def test_empty_role_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(role="", name="Name", hex_code="#FFFFFF")

    def test_empty_name_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(role="Primary", name="", hex_code="#FFFFFF")

    def test_role_is_stripped(self) -> None:
        swatch = ColorSwatch(role="  Primary  ", name="Test", hex_code="#AABBCC")
        assert swatch.role == "Primary"

    def test_name_is_stripped(self) -> None:
        swatch = ColorSwatch(role="Primary", name="  Test Name  ", hex_code="#AABBCC")
        assert swatch.name == "Test Name"

    def test_to_dict_returns_correct_keys(self, sample_swatch: ColorSwatch) -> None:
        result = sample_swatch.to_dict()
        assert set(result.keys()) == {"role", "name", "hex_code", "usage"}

    def test_to_dict_values_match(self, sample_swatch: ColorSwatch) -> None:
        result = sample_swatch.to_dict()
        assert result["role"] == "Primary"
        assert result["hex_code"] == "#3B2314"

    def test_hex_code_non_string_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ColorSwatch(role="X", name="Y", hex_code=123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ColorPalette
# ---------------------------------------------------------------------------


class TestColorPalette:
    """Tests for ColorPalette collection helpers."""

    def test_valid_palette_with_one_swatch(self, sample_palette: ColorPalette) -> None:
        assert len(sample_palette.swatches) == 1

    def test_palette_with_multiple_swatches(self) -> None:
        swatches = [
            ColorSwatch(role="Primary", name="A", hex_code="#111111"),
            ColorSwatch(role="Secondary", name="B", hex_code="#222222"),
            ColorSwatch(role="Accent", name="C", hex_code="#333333"),
        ]
        palette = ColorPalette(swatches=swatches)
        assert len(palette.swatches) == 3

    def test_empty_swatches_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            ColorPalette(swatches=[])

    def test_hex_codes_property(self) -> None:
        swatches = [
            ColorSwatch(role="Primary", name="A", hex_code="#111111"),
            ColorSwatch(role="Secondary", name="B", hex_code="#222222"),
        ]
        palette = ColorPalette(swatches=swatches)
        assert palette.hex_codes == ["#111111", "#222222"]

    def test_by_role_returns_correct_swatch(self, sample_palette: ColorPalette) -> None:
        result = sample_palette.by_role("Primary")
        assert result is not None
        assert result.name == "Espresso Brown"

    def test_by_role_case_insensitive(self, sample_palette: ColorPalette) -> None:
        result = sample_palette.by_role("primary")
        assert result is not None

    def test_by_role_returns_none_when_not_found(self, sample_palette: ColorPalette) -> None:
        result = sample_palette.by_role("Nonexistent")
        assert result is None

    def test_to_dict_contains_swatches_key(self, sample_palette: ColorPalette) -> None:
        result = sample_palette.to_dict()
        assert "swatches" in result
        assert isinstance(result["swatches"], list)
        assert len(result["swatches"]) == 1

    def test_to_dict_swatches_are_dicts(self, sample_palette: ColorPalette) -> None:
        result = sample_palette.to_dict()
        for swatch_dict in result["swatches"]:
            assert isinstance(swatch_dict, dict)
            assert "hex_code" in swatch_dict

    def test_single_dict_coerced_to_list(self) -> None:
        """Passing a single swatch dict should be coerced to a list."""
        swatch_dict = {"role": "Primary", "name": "Test", "hex_code": "#ABCDEF"}
        palette = ColorPalette(swatches=swatch_dict)  # type: ignore[arg-type]
        assert len(palette.swatches) == 1


# ---------------------------------------------------------------------------
# TypographyPairing
# ---------------------------------------------------------------------------


class TestTypographyPairing:
    """Tests for TypographyPairing validation and defaults."""

    def test_minimal_pairing_uses_defaults(self, sample_typography: TypographyPairing) -> None:
        assert sample_typography.display_font == "Playfair Display"
        assert sample_typography.body_font == "Inter"
        assert sample_typography.accent_font == ""
        assert sample_typography.display_weight == "700"
        assert sample_typography.body_weight == "400"
        assert sample_typography.notes == ""

    def test_full_pairing_stores_all_fields(self) -> None:
        tp = TypographyPairing(
            display_font="Playfair Display",
            body_font="Inter",
            accent_font="Playfair Display Italic",
            display_weight="800",
            body_weight="300",
            notes="Use 1.6 line-height for body.",
        )
        assert tp.accent_font == "Playfair Display Italic"
        assert tp.display_weight == "800"
        assert tp.notes == "Use 1.6 line-height for body."

    def test_empty_display_font_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TypographyPairing(display_font="", body_font="Inter")

    def test_empty_body_font_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            TypographyPairing(display_font="Arial", body_font="")

    def test_font_names_are_stripped(self) -> None:
        tp = TypographyPairing(display_font="  Arial  ", body_font="  Inter  ")
        assert tp.display_font == "Arial"
        assert tp.body_font == "Inter"

    def test_to_dict_returns_all_keys(self, sample_typography: TypographyPairing) -> None:
        result = sample_typography.to_dict()
        expected_keys = {
            "display_font",
            "body_font",
            "accent_font",
            "display_weight",
            "body_weight",
            "notes",
        }
        assert set(result.keys()) == expected_keys

    def test_to_dict_values_are_strings(self, sample_typography: TypographyPairing) -> None:
        result = sample_typography.to_dict()
        for value in result.values():
            assert isinstance(value, str)


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class TestLayout:
    """Tests for Layout validation and section coercion."""

    def test_minimal_layout_uses_defaults(self) -> None:
        layout = Layout(description="Single-column.")
        assert layout.grid == "12-column grid"
        assert layout.sections == []
        assert layout.spacing_notes == ""

    def test_sections_stored_as_list(self, sample_layout: Layout) -> None:
        assert sample_layout.sections == ["Hero", "Features", "CTA"]

    def test_sections_coerced_from_string(self) -> None:
        layout = Layout(
            description="Desc",
            sections="Hero\nFeatures\nCTA",  # type: ignore[arg-type]
        )
        assert layout.sections == ["Hero", "Features", "CTA"]

    def test_sections_string_skips_blank_lines(self) -> None:
        layout = Layout(
            description="Desc",
            sections="Hero\n\nFeatures\n",  # type: ignore[arg-type]
        )
        assert layout.sections == ["Hero", "Features"]

    def test_empty_description_raises_validation_error(self) -> None:
        with pytest.raises(ValidationError):
            Layout(description="")

    def test_description_is_stripped(self) -> None:
        layout = Layout(description="  My layout  ")
        assert layout.description == "My layout"

    def test_to_dict_returns_correct_structure(self, sample_layout: Layout) -> None:
        result = sample_layout.to_dict()
        assert set(result.keys()) == {"description", "grid", "sections", "spacing_notes"}
        assert isinstance(result["sections"], list)

    def test_to_dict_sections_are_strings(self, sample_layout: Layout) -> None:
        result = sample_layout.to_dict()
        for section in result["sections"]:
            assert isinstance(section, str)


# ---------------------------------------------------------------------------
# DesignBrief
# ---------------------------------------------------------------------------


class TestDesignBrief:
    """Tests for DesignBrief validation, helpers, and serialisation."""

    def test_valid_brief_creates_successfully(self, sample_brief: DesignBrief) -> None:
        assert sample_brief.title == "Sustainable Coffee Landing Page"
        assert len(sample_brief.mood_descriptors) == 3
        assert len(sample_brief.copy_hierarchy) == 3

    def test_additional_notes_defaults_to_empty_string(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        brief = DesignBrief(
            title="Minimal",
            project_overview="Overview.",
            mood_descriptors=["calm"],
            color_palette=sample_palette,
            typography=sample_typography,
            layout=sample_layout,
            copy_hierarchy=["H1"],
        )
        assert brief.additional_notes == ""

    def test_empty_title_raises_validation_error(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        with pytest.raises(ValidationError):
            DesignBrief(
                title="",
                project_overview="Overview.",
                mood_descriptors=["calm"],
                color_palette=sample_palette,
                typography=sample_typography,
                layout=sample_layout,
                copy_hierarchy=["H1"],
            )

    def test_empty_mood_descriptors_raises_validation_error(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        with pytest.raises(ValidationError):
            DesignBrief(
                title="Title",
                project_overview="Overview.",
                mood_descriptors=[],
                color_palette=sample_palette,
                typography=sample_typography,
                layout=sample_layout,
                copy_hierarchy=["H1"],
            )

    def test_blank_only_mood_descriptors_raises_validation_error(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        with pytest.raises(ValidationError):
            DesignBrief(
                title="Title",
                project_overview="Overview.",
                mood_descriptors=["   ", ""],
                color_palette=sample_palette,
                typography=sample_typography,
                layout=sample_layout,
                copy_hierarchy=["H1"],
            )

    def test_mood_descriptors_coerced_from_comma_string(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        brief = DesignBrief(
            title="Title",
            project_overview="Overview.",
            mood_descriptors="earthy, premium, warm",  # type: ignore[arg-type]
            color_palette=sample_palette,
            typography=sample_typography,
            layout=sample_layout,
            copy_hierarchy=["H1"],
        )
        assert brief.mood_descriptors == ["earthy", "premium", "warm"]

    def test_mood_descriptors_coerced_from_newline_string(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        brief = DesignBrief(
            title="Title",
            project_overview="Overview.",
            mood_descriptors="earthy\npremium\nwarm",  # type: ignore[arg-type]
            color_palette=sample_palette,
            typography=sample_typography,
            layout=sample_layout,
            copy_hierarchy=["H1"],
        )
        assert brief.mood_descriptors == ["earthy", "premium", "warm"]

    def test_copy_hierarchy_coerced_from_string(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        brief = DesignBrief(
            title="Title",
            project_overview="Overview.",
            mood_descriptors=["calm"],
            color_palette=sample_palette,
            typography=sample_typography,
            layout=sample_layout,
            copy_hierarchy="H1\nH2\nCTA",  # type: ignore[arg-type]
        )
        assert brief.copy_hierarchy == ["H1", "H2", "CTA"]

    def test_empty_copy_hierarchy_raises_validation_error(
        self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        with pytest.raises(ValidationError):
            DesignBrief(
                title="Title",
                project_overview="Overview.",
                mood_descriptors=["calm"],
                color_palette=sample_palette,
                typography=sample_typography,
                layout=sample_layout,
                copy_hierarchy=[],
            )

    def test_title_is_stripped(self,
        sample_palette: ColorPalette,
        sample_typography: TypographyPairing,
        sample_layout: Layout,
    ) -> None:
        brief = DesignBrief(
            title="  My Brief  ",
            project_overview="Overview.",
            mood_descriptors=["calm"],
            color_palette=sample_palette,
            typography=sample_typography,
            layout=sample_layout,
            copy_hierarchy=["H1"],
        )
        assert brief.title == "My Brief"

    # ------------------------------------------------------------------
    # to_dict
    # ------------------------------------------------------------------

    def test_to_dict_returns_all_top_level_keys(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
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

    def test_to_dict_nested_color_palette_is_dict(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
        assert isinstance(result["color_palette"], dict)
        assert "swatches" in result["color_palette"]

    def test_to_dict_nested_typography_is_dict(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
        assert isinstance(result["typography"], dict)
        assert "display_font" in result["typography"]

    def test_to_dict_nested_layout_is_dict(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
        assert isinstance(result["layout"], dict)
        assert "description" in result["layout"]

    def test_to_dict_mood_descriptors_is_list(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
        assert isinstance(result["mood_descriptors"], list)

    def test_to_dict_copy_hierarchy_is_list(self, sample_brief: DesignBrief) -> None:
        result = sample_brief.to_dict()
        assert isinstance(result["copy_hierarchy"], list)

    # ------------------------------------------------------------------
    # to_json / from_json
    # ------------------------------------------------------------------

    def test_to_json_returns_valid_json_string(self, sample_brief: DesignBrief) -> None:
        json_str = sample_brief.to_json()
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["title"] == "Sustainable Coffee Landing Page"

    def test_to_json_with_custom_indent(self, sample_brief: DesignBrief) -> None:
        json_str = sample_brief.to_json(indent=4)
        assert "    " in json_str  # 4-space indent present

    def test_from_json_round_trip(self, sample_brief: DesignBrief) -> None:
        json_str = sample_brief.to_json()
        restored = DesignBrief.from_json(json_str)
        assert restored.title == sample_brief.title
        assert restored.mood_descriptors == sample_brief.mood_descriptors
        assert restored.color_palette.hex_codes == sample_brief.color_palette.hex_codes
        assert restored.typography.display_font == sample_brief.typography.display_font
        assert restored.layout.sections == sample_brief.layout.sections
        assert restored.copy_hierarchy == sample_brief.copy_hierarchy

    def test_from_json_invalid_json_raises_value_error(self) -> None:
        with pytest.raises((ValueError, Exception)):
            DesignBrief.from_json("{not valid json")

    # ------------------------------------------------------------------
    # from_dict
    # ------------------------------------------------------------------

    def test_from_dict_round_trip(self, sample_brief: DesignBrief) -> None:
        data = sample_brief.to_dict()
        restored = DesignBrief.from_dict(data)
        assert restored.title == sample_brief.title
        assert restored.additional_notes == sample_brief.additional_notes

    def test_from_dict_raises_validation_error_on_bad_data(self) -> None:
        with pytest.raises(ValidationError):
            DesignBrief.from_dict({"title": "Only title, nothing else"})

    def test_from_dict_with_nested_dicts(self, sample_brief: DesignBrief) -> None:
        data = sample_brief.to_dict()
        # Ensure nested objects are properly reconstructed.
        restored = DesignBrief.from_dict(data)
        assert isinstance(restored.color_palette, ColorPalette)
        assert isinstance(restored.typography, TypographyPairing)
        assert isinstance(restored.layout, Layout)
        assert isinstance(restored.color_palette.swatches[0], ColorSwatch)

    # ------------------------------------------------------------------
    # Full schema round-trip with real-world-style data
    # ------------------------------------------------------------------

    def test_full_real_world_brief_round_trip(self) -> None:
        """Construct a brief from a rich dict and verify the full round-trip."""
        data: dict = {
            "title": "Eco Coffee Landing Page",
            "project_overview": (
                "A landing page for a sustainable coffee subscription brand "
                "targeting environmentally-conscious millennials."
            ),
            "mood_descriptors": ["earthy", "premium", "approachable", "conscious", "warm"],
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
                "sections": [
                    "Hero: headline + CTA",
                    "Social proof strip",
                    "Product showcase",
                    "Email capture",
                    "Footer",
                ],
                "spacing_notes": "Generous vertical rhythm; 80px section padding.",
            },
            "copy_hierarchy": [
                "Hero Headline (H1): 'Good coffee. Good planet.'",
                "Sub-headline (H2): 'Ethically sourced. Carbon-neutral shipping.'",
                "CTA Button: 'Start My Subscription'",
            ],
            "additional_notes": "Keep the overall tone warm but authoritative.",
        }

        brief = DesignBrief.from_dict(data)

        assert brief.title == "Eco Coffee Landing Page"
        assert len(brief.color_palette.swatches) == 5
        assert brief.color_palette.by_role("Primary") is not None
        assert brief.color_palette.by_role("primary").hex_code == "#3B2314"  # type: ignore[union-attr]
        assert brief.typography.accent_font == "Playfair Display Italic"
        assert len(brief.layout.sections) == 5
        assert len(brief.copy_hierarchy) == 3
        assert brief.additional_notes == "Keep the overall tone warm but authoritative."

        # JSON round-trip
        json_str = brief.to_json()
        restored = DesignBrief.from_json(json_str)
        assert restored == brief
