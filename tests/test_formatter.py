"""Unit tests for the Brief Forge formatter module (brief_forge/formatter.py).

Covers:
- :func:`~brief_forge.formatter.format_markdown` — Markdown output structure,
  headings, colour palette table, typography, layout, copy hierarchy,
  and additional notes sections.
- :func:`~brief_forge.formatter.format_plain_text` — plain-text output with
  correct separators, indentation, and section ordering.
- :func:`~brief_forge.formatter.format_json` — valid JSON output, correct
  structure, and round-trip fidelity.
- :func:`~brief_forge.formatter.format_brief` — dispatcher routing and
  error handling for unsupported formats.
- Internal helpers :func:`~brief_forge.formatter._md_table_row`,
  :func:`~brief_forge.formatter._md_table_separator`,
  :func:`~brief_forge.formatter._swatch_md_row`,
  :func:`~brief_forge.formatter._swatch_text_line`.

All tests are pure (no I/O, no external services) and follow pytest conventions.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from brief_forge.formatter import (
    _md_table_row,
    _md_table_separator,
    _swatch_md_row,
    _swatch_text_line,
    format_brief,
    format_json,
    format_markdown,
    format_plain_text,
)
from brief_forge.models import (
    ColorPalette,
    ColorSwatch,
    DesignBrief,
    Layout,
    TypographyPairing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_swatch() -> ColorSwatch:
    """A single, valid ColorSwatch."""
    return ColorSwatch(
        role="Primary",
        name="Espresso Brown",
        hex_code="#3B2314",
        usage="Headlines and CTAs",
    )


@pytest.fixture()
def minimal_swatch() -> ColorSwatch:
    """A swatch with no usage string."""
    return ColorSwatch(
        role="Accent",
        name="Sage Green",
        hex_code="#7D9B76",
        usage="",
    )


@pytest.fixture()
def full_palette() -> ColorPalette:
    """A five-swatch ColorPalette."""
    return ColorPalette(
        swatches=[
            ColorSwatch(role="Primary", name="Espresso Brown", hex_code="#3B2314", usage="Headlines"),
            ColorSwatch(role="Secondary", name="Sage Green", hex_code="#7D9B76", usage="Accents"),
            ColorSwatch(role="Background", name="Oat Cream", hex_code="#F5EFE6", usage="Page BG"),
            ColorSwatch(role="Surface", name="Warm Sand", hex_code="#E8D9C5", usage="Cards"),
            ColorSwatch(role="Text", name="Dark Roast", hex_code="#1A1008", usage="Body copy"),
        ]
    )


@pytest.fixture()
def full_typography() -> TypographyPairing:
    """A complete TypographyPairing with all optional fields set."""
    return TypographyPairing(
        display_font="Playfair Display",
        body_font="Inter",
        accent_font="Playfair Display Italic",
        display_weight="700",
        body_weight="400",
        notes="Use 1.6 line-height for body copy.",
    )


@pytest.fixture()
def minimal_typography() -> TypographyPairing:
    """A TypographyPairing with only required fields set."""
    return TypographyPairing(
        display_font="Roboto Slab",
        body_font="Roboto",
    )


@pytest.fixture()
def full_layout() -> Layout:
    """A complete Layout with all optional fields set."""
    return Layout(
        description="Single-column hero with full-bleed background texture.",
        grid="12-column, 24px gutter",
        sections=["Hero", "Social proof", "Product showcase", "Email capture", "Footer"],
        spacing_notes="80px section padding.",
    )


@pytest.fixture()
def minimal_layout() -> Layout:
    """A Layout with only required fields set."""
    return Layout(description="Simple single-column layout.")


@pytest.fixture()
def full_brief(
    full_palette: ColorPalette,
    full_typography: TypographyPairing,
    full_layout: Layout,
) -> DesignBrief:
    """A fully populated DesignBrief with all optional fields set."""
    return DesignBrief(
        title="Sustainable Coffee Landing Page",
        project_overview=(
            "A conversion-focused landing page for a sustainable coffee "
            "subscription brand targeting environmentally-conscious millennials."
        ),
        mood_descriptors=["earthy", "premium", "approachable", "conscious", "warm"],
        color_palette=full_palette,
        typography=full_typography,
        layout=full_layout,
        copy_hierarchy=[
            "H1: Good coffee. Good planet.",
            "H2: Ethically sourced. Carbon-neutral shipping.",
            "CTA: Start My Subscription",
        ],
        additional_notes="Keep the overall tone warm but authoritative.",
    )


@pytest.fixture()
def minimal_brief(
    full_palette: ColorPalette,
    minimal_typography: TypographyPairing,
    minimal_layout: Layout,
) -> DesignBrief:
    """A DesignBrief with no optional fields set (empty additional_notes etc.)."""
    return DesignBrief(
        title="Minimal Brief",
        project_overview="A minimal project overview.",
        mood_descriptors=["clean"],
        color_palette=full_palette,
        typography=minimal_typography,
        layout=minimal_layout,
        copy_hierarchy=["Headline"],
    )


# ---------------------------------------------------------------------------
# Internal helper tests
# ---------------------------------------------------------------------------


class TestMdTableRow:
    """Tests for the _md_table_row helper."""

    def test_single_cell(self) -> None:
        assert _md_table_row("A") == "| A |"

    def test_multiple_cells(self) -> None:
        assert _md_table_row("A", "B", "C") == "| A | B | C |"

    def test_four_cells(self) -> None:
        result = _md_table_row("Role", "Name", "Hex", "Usage")
        assert result == "| Role | Name | Hex | Usage |"

    def test_empty_cell(self) -> None:
        result = _md_table_row("A", "", "C")
        assert "| A |  | C |" == result

    def test_starts_with_pipe(self) -> None:
        result = _md_table_row("X", "Y")
        assert result.startswith("|")

    def test_ends_with_pipe(self) -> None:
        result = _md_table_row("X", "Y")
        assert result.endswith("|")


class TestMdTableSeparator:
    """Tests for the _md_table_separator helper."""

    def test_single_column(self) -> None:
        result = _md_table_separator(5)
        assert result == "| ----- |"

    def test_minimum_width_enforced(self) -> None:
        # Width 1 should be expanded to at least 3 dashes.
        result = _md_table_separator(1)
        assert "---" in result

    def test_multiple_columns(self) -> None:
        result = _md_table_separator(3, 5, 3)
        assert result == "| --- | ----- | --- |"

    def test_starts_and_ends_with_pipe(self) -> None:
        result = _md_table_separator(4, 4)
        assert result.startswith("|")
        assert result.endswith("|")

    def test_zero_width_uses_three_dashes(self) -> None:
        result = _md_table_separator(0)
        assert "---" in result


class TestSwatchMdRow:
    """Tests for the _swatch_md_row helper."""

    def test_contains_role(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(sample_swatch)
        assert "Primary" in result

    def test_contains_name(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(sample_swatch)
        assert "Espresso Brown" in result

    def test_hex_code_in_backticks(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(sample_swatch)
        assert "`#3B2314`" in result

    def test_contains_usage(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(sample_swatch)
        assert "Headlines and CTAs" in result

    def test_empty_usage_renders_dash(self, minimal_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(minimal_swatch)
        assert "—" in result

    def test_is_pipe_delimited(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_md_row(sample_swatch)
        assert result.startswith("|")
        assert result.endswith("|")


class TestSwatchTextLine:
    """Tests for the _swatch_text_line helper."""

    def test_contains_index(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(sample_swatch, 1)
        assert "1." in result

    def test_contains_role(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(sample_swatch, 1)
        assert "Primary" in result

    def test_contains_name(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(sample_swatch, 1)
        assert "Espresso Brown" in result

    def test_contains_hex_code(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(sample_swatch, 1)
        assert "#3B2314" in result

    def test_contains_usage_in_parentheses(self, sample_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(sample_swatch, 1)
        assert "(Headlines and CTAs)" in result

    def test_empty_usage_omits_parentheses(self, minimal_swatch: ColorSwatch) -> None:
        result = _swatch_text_line(minimal_swatch, 2)
        assert "(" not in result

    def test_index_appears_in_output(self, sample_swatch: ColorSwatch) -> None:
        result_3 = _swatch_text_line(sample_swatch, 3)
        assert "3." in result_3


# ---------------------------------------------------------------------------
# format_markdown
# ---------------------------------------------------------------------------


class TestFormatMarkdown:
    """Tests for the format_markdown function."""

    def test_returns_string(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert isinstance(result, str)

    def test_ends_with_newline(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert result.endswith("\n")

    def test_contains_h1_title(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "# Design Brief — Sustainable Coffee Landing Page" in result

    def test_contains_project_overview_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Project Overview" in result

    def test_contains_project_overview_text(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "conversion-focused landing page" in result

    def test_contains_mood_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Mood" in result

    def test_mood_descriptors_joined_with_separator(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "earthy · premium" in result

    def test_contains_colour_palette_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Colour Palette" in result

    def test_colour_table_header_row(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "| Role" in result
        assert "| Name" in result
        assert "| Hex" in result
        assert "| Usage" in result

    def test_colour_table_separator_row(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "|---" in result

    def test_all_swatches_in_table(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        for swatch in full_brief.color_palette.swatches:
            assert swatch.role in result
            assert swatch.name in result
            assert f"`{swatch.hex_code}`" in result

    def test_contains_typography_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Typography" in result

    def test_display_font_in_typography(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "Playfair Display" in result

    def test_body_font_in_typography(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "Inter" in result

    def test_accent_font_in_typography_when_present(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "Playfair Display Italic" in result

    def test_typography_notes_in_output_when_present(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "1.6 line-height" in result

    def test_accent_font_absent_when_empty(self, minimal_brief: DesignBrief) -> None:
        result = format_markdown(minimal_brief)
        # minimal_typography has no accent_font — line should not appear
        assert "Accent / Labels" not in result

    def test_contains_layout_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Layout" in result

    def test_layout_description_in_output(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "full-bleed background texture" in result

    def test_layout_grid_in_output(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "12-column" in result

    def test_layout_sections_in_output(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        for section in full_brief.layout.sections:
            assert section in result

    def test_layout_spacing_notes_in_output(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "80px" in result

    def test_contains_copy_hierarchy_heading(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Copy Hierarchy" in result

    def test_copy_hierarchy_items_numbered(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "1. H1:" in result
        assert "2. H2:" in result
        assert "3. CTA:" in result

    def test_contains_additional_notes_heading_when_present(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "## Additional Notes" in result

    def test_additional_notes_content_present(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "warm but authoritative" in result

    def test_additional_notes_heading_absent_when_empty(self, minimal_brief: DesignBrief) -> None:
        result = format_markdown(minimal_brief)
        assert "## Additional Notes" not in result

    def test_section_order_is_correct(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        overview_pos = result.index("## Project Overview")
        mood_pos = result.index("## Mood")
        palette_pos = result.index("## Colour Palette")
        typography_pos = result.index("## Typography")
        layout_pos = result.index("## Layout")
        copy_pos = result.index("## Copy Hierarchy")
        assert overview_pos < mood_pos < palette_pos < typography_pos < layout_pos < copy_pos

    def test_minimal_layout_no_sections_block(self, minimal_brief: DesignBrief) -> None:
        result = format_markdown(minimal_brief)
        # minimal_layout has no sections, so the sections list block should be absent
        assert "Page sections" not in result

    def test_minimal_layout_no_spacing_notes(self, minimal_brief: DesignBrief) -> None:
        result = format_markdown(minimal_brief)
        assert "Spacing notes" not in result

    def test_typography_weights_present(self, full_brief: DesignBrief) -> None:
        result = format_markdown(full_brief)
        assert "700" in result
        assert "400" in result

    def test_non_empty_output(self, minimal_brief: DesignBrief) -> None:
        result = format_markdown(minimal_brief)
        assert len(result) > 100


# ---------------------------------------------------------------------------
# format_plain_text
# ---------------------------------------------------------------------------


class TestFormatPlainText:
    """Tests for the format_plain_text function."""

    def test_returns_string(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert isinstance(result, str)

    def test_ends_with_newline(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert result.endswith("\n")

    def test_no_markdown_headings(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "##" not in result
        assert result.count("# ") == 0 or "# Design" not in result
        # Specifically no H1/H2 markdown
        import re
        assert not re.search(r"^#{1,6} ", result, re.MULTILINE)

    def test_title_in_output_uppercase(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "SUSTAINABLE COFFEE LANDING PAGE" in result

    def test_contains_separator_lines(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "=" * 60 in result

    def test_contains_thin_separator_lines(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "-" * 60 in result

    def test_project_overview_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "PROJECT OVERVIEW" in result

    def test_project_overview_content(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "conversion-focused landing page" in result

    def test_mood_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "MOOD" in result

    def test_mood_descriptors_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "earthy" in result
        assert "premium" in result

    def test_colour_palette_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "COLOUR PALETTE" in result

    def test_all_swatches_present(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        for swatch in full_brief.color_palette.swatches:
            assert swatch.name in result
            assert swatch.hex_code in result

    def test_swatch_numbered(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "1." in result
        assert "2." in result

    def test_typography_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "TYPOGRAPHY" in result

    def test_display_font_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "Playfair Display" in result

    def test_body_font_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "Inter" in result

    def test_accent_font_in_output_when_present(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "Playfair Display Italic" in result

    def test_accent_font_absent_when_empty(self, minimal_brief: DesignBrief) -> None:
        result = format_plain_text(minimal_brief)
        assert "Accent" not in result

    def test_typography_notes_in_output_when_present(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "1.6 line-height" in result

    def test_layout_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "LAYOUT" in result

    def test_layout_description_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "full-bleed background texture" in result

    def test_layout_grid_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "12-column" in result

    def test_layout_sections_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        for section in full_brief.layout.sections:
            assert section in result

    def test_layout_spacing_notes_in_output(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "80px" in result

    def test_copy_hierarchy_section_header(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "COPY HIERARCHY" in result

    def test_copy_hierarchy_numbered(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "1. H1:" in result
        assert "2. H2:" in result
        assert "3. CTA:" in result

    def test_additional_notes_section_when_present(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "ADDITIONAL NOTES" in result
        assert "warm but authoritative" in result

    def test_additional_notes_absent_when_empty(self, minimal_brief: DesignBrief) -> None:
        result = format_plain_text(minimal_brief)
        assert "ADDITIONAL NOTES" not in result

    def test_no_backtick_markup(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        assert "`" not in result

    def test_section_order_is_correct(self, full_brief: DesignBrief) -> None:
        result = format_plain_text(full_brief)
        overview_pos = result.index("PROJECT OVERVIEW")
        mood_pos = result.index("MOOD")
        palette_pos = result.index("COLOUR PALETTE")
        typography_pos = result.index("TYPOGRAPHY")
        layout_pos = result.index("LAYOUT")
        copy_pos = result.index("COPY HIERARCHY")
        assert overview_pos < mood_pos < palette_pos < typography_pos < layout_pos < copy_pos

    def test_non_empty_output(self, minimal_brief: DesignBrief) -> None:
        result = format_plain_text(minimal_brief)
        assert len(result) > 100


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


class TestFormatJson:
    """Tests for the format_json function."""

    def test_returns_string(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        assert isinstance(result, str)

    def test_valid_json(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_contains_title(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert parsed["title"] == "Sustainable Coffee Landing Page"

    def test_contains_all_top_level_keys(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
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
        assert set(parsed.keys()) == expected_keys

    def test_color_palette_structure(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert "swatches" in parsed["color_palette"]
        assert len(parsed["color_palette"]["swatches"]) == 5

    def test_swatch_hex_codes_correct(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        hex_codes = [s["hex_code"] for s in parsed["color_palette"]["swatches"]]
        assert "#3B2314" in hex_codes
        assert "#7D9B76" in hex_codes

    def test_typography_structure(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert parsed["typography"]["display_font"] == "Playfair Display"
        assert parsed["typography"]["body_font"] == "Inter"

    def test_layout_structure(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert "description" in parsed["layout"]
        assert "sections" in parsed["layout"]
        assert len(parsed["layout"]["sections"]) == 5

    def test_mood_descriptors_is_list(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert isinstance(parsed["mood_descriptors"], list)
        assert len(parsed["mood_descriptors"]) == 5

    def test_copy_hierarchy_is_list(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert isinstance(parsed["copy_hierarchy"], list)
        assert len(parsed["copy_hierarchy"]) == 3

    def test_default_indent_is_two_spaces(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        # 2-space indent means lines starting with two spaces exist
        assert any(line.startswith("  ") and not line.startswith("   ") for line in result.splitlines())

    def test_custom_indent(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief, indent=4)
        assert any(line.startswith("    ") and not line.startswith("     ") for line in result.splitlines())

    def test_round_trip_to_design_brief(self, full_brief: DesignBrief) -> None:
        """JSON output can be parsed back into a valid DesignBrief."""
        from brief_forge.models import DesignBrief as DB
        result = format_json(full_brief)
        parsed = json.loads(result)
        restored = DB.from_dict(parsed)
        assert restored.title == full_brief.title
        assert restored.color_palette.hex_codes == full_brief.color_palette.hex_codes
        assert restored.typography.display_font == full_brief.typography.display_font
        assert restored.layout.sections == full_brief.layout.sections
        assert restored.copy_hierarchy == full_brief.copy_hierarchy
        assert restored.mood_descriptors == full_brief.mood_descriptors

    def test_additional_notes_in_output(self, full_brief: DesignBrief) -> None:
        result = format_json(full_brief)
        parsed = json.loads(result)
        assert parsed["additional_notes"] == "Keep the overall tone warm but authoritative."

    def test_empty_additional_notes(self, minimal_brief: DesignBrief) -> None:
        result = format_json(minimal_brief)
        parsed = json.loads(result)
        assert parsed["additional_notes"] == ""

    def test_non_ascii_characters_preserved(self) -> None:
        """Non-ASCII characters (e.g. in font names) are not escaped."""
        brief = DesignBrief(
            title="Café Brand",
            project_overview="A café brand brief.",
            mood_descriptors=["warm"],
            color_palette=ColorPalette(
                swatches=[ColorSwatch(role="Primary", name="Red", hex_code="#FF0000", usage="")]
            ),
            typography=TypographyPairing(display_font="Arial", body_font="Georgia"),
            layout=Layout(description="Simple layout."),
            copy_hierarchy=["Headline"],
        )
        result = format_json(brief)
        assert "Café" in result  # ensure_ascii=False means it's not escaped


# ---------------------------------------------------------------------------
# format_brief dispatcher
# ---------------------------------------------------------------------------


class TestFormatBrief:
    """Tests for the format_brief dispatcher function."""

    def test_markdown_format(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "markdown")
        assert "# Design Brief" in result

    def test_markdown_format_uppercase(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "MARKDOWN")
        assert "# Design Brief" in result

    def test_markdown_format_mixed_case(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "Markdown")
        assert "# Design Brief" in result

    def test_text_format(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "text")
        assert "PROJECT OVERVIEW" in result

    def test_text_format_uppercase(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "TEXT")
        assert "PROJECT OVERVIEW" in result

    def test_plain_format_alias(self, full_brief: DesignBrief) -> None:
        """'plain' should be accepted as an alias for 'text'."""
        result = format_brief(full_brief, "plain")
        assert "PROJECT OVERVIEW" in result

    def test_plain_text_format_alias(self, full_brief: DesignBrief) -> None:
        """'plain_text' should be accepted as an alias for 'text'."""
        result = format_brief(full_brief, "plain_text")
        assert "PROJECT OVERVIEW" in result

    def test_plain_text_hyphen_alias(self, full_brief: DesignBrief) -> None:
        """'plain-text' should be accepted as an alias."""
        result = format_brief(full_brief, "plain-text")
        assert "PROJECT OVERVIEW" in result

    def test_json_format(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "json")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_format_uppercase(self, full_brief: DesignBrief) -> None:
        result = format_brief(full_brief, "JSON")
        parsed = json.loads(result)
        assert parsed["title"] == "Sustainable Coffee Landing Page"

    def test_unsupported_format_raises_value_error(self, full_brief: DesignBrief) -> None:
        with pytest.raises(ValueError, match="Unsupported output format"):
            format_brief(full_brief, "html")

    def test_empty_format_string_raises_value_error(self, full_brief: DesignBrief) -> None:
        with pytest.raises(ValueError):
            format_brief(full_brief, "")

    def test_unknown_format_raises_value_error(self, full_brief: DesignBrief) -> None:
        with pytest.raises(ValueError, match="Unsupported output format"):
            format_brief(full_brief, "xml")

    def test_error_message_includes_format_name(self, full_brief: DesignBrief) -> None:
        with pytest.raises(ValueError, match="pdf"):
            format_brief(full_brief, "pdf")

    def test_format_brief_markdown_matches_format_markdown(self, full_brief: DesignBrief) -> None:
        dispatcher_result = format_brief(full_brief, "markdown")
        direct_result = format_markdown(full_brief)
        assert dispatcher_result == direct_result

    def test_format_brief_text_matches_format_plain_text(self, full_brief: DesignBrief) -> None:
        dispatcher_result = format_brief(full_brief, "text")
        direct_result = format_plain_text(full_brief)
        assert dispatcher_result == direct_result

    def test_format_brief_json_matches_format_json(self, full_brief: DesignBrief) -> None:
        dispatcher_result = format_brief(full_brief, "json")
        direct_result = format_json(full_brief)
        assert dispatcher_result == direct_result

    def test_whitespace_around_format_name_handled(self, full_brief: DesignBrief) -> None:
        """Leading/trailing whitespace should be stripped before lookup."""
        result = format_brief(full_brief, "  markdown  ")
        assert "# Design Brief" in result


# ---------------------------------------------------------------------------
# Cross-format consistency
# ---------------------------------------------------------------------------


class TestCrossFormatConsistency:
    """Verify that all formats include the same core content."""

    def test_all_formats_contain_title(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        assert "Sustainable Coffee Landing Page" in md
        assert "SUSTAINABLE COFFEE LANDING PAGE" in txt
        parsed = json.loads(jsn)
        assert parsed["title"] == "Sustainable Coffee Landing Page"

    def test_all_formats_contain_hex_codes(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        for swatch in full_brief.color_palette.swatches:
            assert swatch.hex_code in md
            assert swatch.hex_code in txt
            assert swatch.hex_code in jsn

    def test_all_formats_contain_display_font(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        assert "Playfair Display" in md
        assert "Playfair Display" in txt
        assert "Playfair Display" in jsn

    def test_all_formats_contain_mood_descriptors(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        assert "earthy" in md
        assert "earthy" in txt
        assert "earthy" in jsn

    def test_all_formats_contain_copy_hierarchy_items(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        for item in full_brief.copy_hierarchy:
            assert item in md
            assert item in txt
            assert item in jsn

    def test_all_formats_contain_layout_description(self, full_brief: DesignBrief) -> None:
        md = format_markdown(full_brief)
        txt = format_plain_text(full_brief)
        jsn = format_json(full_brief)

        assert "full-bleed background texture" in md
        assert "full-bleed background texture" in txt
        assert "full-bleed background texture" in jsn

    def test_minimal_brief_renders_in_all_formats(self, minimal_brief: DesignBrief) -> None:
        """Ensure minimal briefs (no optional fields) don't raise exceptions."""
        md = format_markdown(minimal_brief)
        txt = format_plain_text(minimal_brief)
        jsn = format_json(minimal_brief)

        assert isinstance(md, str) and len(md) > 0
        assert isinstance(txt, str) and len(txt) > 0
        assert isinstance(jsn, str) and len(jsn) > 0
