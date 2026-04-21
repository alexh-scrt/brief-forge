"""Output formatter module for Brief Forge.

This module is responsible for rendering a :class:`~brief_forge.models.DesignBrief`
instance into multiple output formats that are suitable for copy-pasting into
design tools such as Figma, Canva, and Adobe products:

- **Markdown** — richly formatted with tables, headings, and code spans for
  hex codes.  Ideal for pasting into Notion, README files, or Figma's notes.
- **Plain text** — clean, readable output with no markup, suitable for email,
  Slack, or any plain-text field in a design tool.
- **JSON** — the raw, validated :class:`DesignBrief` serialised to indented
  JSON, suitable for programmatic consumption or storing in a design system.

All formatters are pure functions — they accept a :class:`DesignBrief` and
return a ``str``.  No I/O or side effects occur.

Example usage::

    from brief_forge.formatter import format_markdown, format_plain_text, format_json

    brief = ...  # a DesignBrief instance

    md  = format_markdown(brief)
    txt = format_plain_text(brief)
    jsn = format_json(brief)

The module also exposes a convenience dispatcher :func:`format_brief` that
accepts a format name string (``"markdown"``, ``"text"``, or ``"json"``) and
delegates to the appropriate function.
"""

from __future__ import annotations

import json
from typing import Literal

from brief_forge.models import ColorSwatch, DesignBrief

# Supported format literals used by the dispatcher.
FormatName = Literal["markdown", "text", "json"]

_SUPPORTED_FORMATS: tuple[str, ...] = ("markdown", "text", "json")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _md_table_row(*cells: str) -> str:
    """Format a sequence of cell strings as a Markdown table row.

    Parameters
    ----------
    *cells:
        Cell content strings.

    Returns
    -------
    str
        Pipe-delimited Markdown table row, e.g. ``"| A | B | C |"``.
    """
    return "| " + " | ".join(cells) + " |"


def _md_table_separator(*widths: int) -> str:
    """Build a Markdown table separator row.

    Parameters
    ----------
    *widths:
        Minimum column widths (number of dashes per column).  Each value
        must be at least 3 for Markdown compatibility.

    Returns
    -------
    str
        Pipe-delimited separator row, e.g. ``"|---|---|---|"``.  Each cell
        contains at least three dashes.
    """
    dashes = ["-" * max(3, w) for w in widths]
    return "| " + " | ".join(dashes) + " |"


def _swatch_md_row(swatch: ColorSwatch) -> str:
    """Format a single :class:`~brief_forge.models.ColorSwatch` as a Markdown table row.

    Parameters
    ----------
    swatch:
        The colour swatch to render.

    Returns
    -------
    str
        A Markdown table row string with role, name, hex code (in backticks),
        and usage columns.
    """
    return _md_table_row(
        swatch.role,
        swatch.name,
        f"`{swatch.hex_code}`",
        swatch.usage if swatch.usage else "—",
    )


def _swatch_text_line(swatch: ColorSwatch, index: int) -> str:
    """Format a single :class:`~brief_forge.models.ColorSwatch` as a plain-text line.

    Parameters
    ----------
    swatch:
        The colour swatch to render.
    index:
        1-based index within the palette list.

    Returns
    -------
    str
        A human-readable line, e.g.
        ``"  1. Primary — Espresso Brown  #3B2314  (Headlines and CTAs)"``.
    """
    usage_part = f"  ({swatch.usage})" if swatch.usage else ""
    return f"  {index}. {swatch.role} — {swatch.name}  {swatch.hex_code}{usage_part}"


# ---------------------------------------------------------------------------
# Public formatters
# ---------------------------------------------------------------------------


def format_markdown(brief: DesignBrief) -> str:
    """Render a :class:`~brief_forge.models.DesignBrief` as a Markdown document.

    The output is structured with H1 / H2 headings, a colour palette table,
    typography pairing block, ordered layout section list, and numbered copy
    hierarchy.  Hex codes are wrapped in backticks so they stand out.

    Parameters
    ----------
    brief:
        The design brief to render.

    Returns
    -------
    str
        A complete Markdown-formatted design brief string.
    """
    lines: list[str] = []

    # ── Title ────────────────────────────────────────────────────────────────
    lines.append(f"# Design Brief — {brief.title}")
    lines.append("")

    # ── Project Overview ─────────────────────────────────────────────────────
    lines.append("## Project Overview")
    lines.append("")
    lines.append(brief.project_overview)
    lines.append("")

    # ── Mood & Tone ──────────────────────────────────────────────────────────
    lines.append("## Mood & Tone")
    lines.append("")
    lines.append(" · ".join(brief.mood_descriptors))
    lines.append("")

    # ── Colour Palette ───────────────────────────────────────────────────────
    lines.append("## Colour Palette")
    lines.append("")
    lines.append(_md_table_row("Role", "Name", "Hex", "Usage"))
    lines.append(_md_table_separator(12, 20, 9, 30))
    for swatch in brief.color_palette.swatches:
        lines.append(_swatch_md_row(swatch))
    lines.append("")

    # ── Typography ───────────────────────────────────────────────────────────
    typography = brief.typography
    lines.append("## Typography")
    lines.append("")
    lines.append(
        f"- **Display / Headlines:** {typography.display_font}"
        f" — weight {typography.display_weight}"
    )
    lines.append(
        f"- **Body copy:** {typography.body_font}"
        f" — weight {typography.body_weight}"
    )
    if typography.accent_font:
        lines.append(f"- **Accent / Labels:** {typography.accent_font}")
    if typography.notes:
        lines.append(f"- **Notes:** {typography.notes}")
    lines.append("")

    # ── Layout ───────────────────────────────────────────────────────────────
    layout = brief.layout
    lines.append("## Layout")
    lines.append("")
    lines.append(layout.description)
    lines.append("")
    if layout.grid:
        lines.append(f"**Grid:** {layout.grid}")
        lines.append("")
    if layout.sections:
        lines.append("**Page sections (in order):**")
        lines.append("")
        for section in layout.sections:
            lines.append(f"- {section}")
        lines.append("")
    if layout.spacing_notes:
        lines.append(f"**Spacing notes:** {layout.spacing_notes}")
        lines.append("")

    # ── Copy Hierarchy ───────────────────────────────────────────────────────
    lines.append("## Copy Hierarchy")
    lines.append("")
    for i, item in enumerate(brief.copy_hierarchy, start=1):
        lines.append(f"{i}. {item}")
    lines.append("")

    # ── Additional Notes ─────────────────────────────────────────────────────
    if brief.additional_notes:
        lines.append("## Additional Notes")
        lines.append("")
        lines.append(brief.additional_notes)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def format_plain_text(brief: DesignBrief) -> str:
    """Render a :class:`~brief_forge.models.DesignBrief` as plain text.

    No Markdown markup is used.  The output uses simple separators and
    indentation for readability.  Suitable for email, Slack, or any
    plain-text field in a design tool.

    Parameters
    ----------
    brief:
        The design brief to render.

    Returns
    -------
    str
        A clean, plain-text design brief string.
    """
    sep = "=" * 60
    thin_sep = "-" * 60
    lines: list[str] = []

    # ── Title ────────────────────────────────────────────────────────────────
    lines.append(sep)
    lines.append(f"DESIGN BRIEF — {brief.title.upper()}")
    lines.append(sep)
    lines.append("")

    # ── Project Overview ─────────────────────────────────────────────────────
    lines.append("PROJECT OVERVIEW")
    lines.append(thin_sep)
    lines.append(brief.project_overview)
    lines.append("")

    # ── Mood & Tone ──────────────────────────────────────────────────────────
    lines.append("MOOD & TONE")
    lines.append(thin_sep)
    lines.append(" · ".join(brief.mood_descriptors))
    lines.append("")

    # ── Colour Palette ───────────────────────────────────────────────────────
    lines.append("COLOUR PALETTE")
    lines.append(thin_sep)
    for i, swatch in enumerate(brief.color_palette.swatches, start=1):
        lines.append(_swatch_text_line(swatch, i))
    lines.append("")

    # ── Typography ───────────────────────────────────────────────────────────
    typography = brief.typography
    lines.append("TYPOGRAPHY")
    lines.append(thin_sep)
    lines.append(
        f"  Display / Headlines : {typography.display_font}"
        f" (weight {typography.display_weight})"
    )
    lines.append(
        f"  Body copy           : {typography.body_font}"
        f" (weight {typography.body_weight})"
    )
    if typography.accent_font:
        lines.append(f"  Accent / Labels     : {typography.accent_font}")
    if typography.notes:
        lines.append(f"  Notes               : {typography.notes}")
    lines.append("")

    # ── Layout ───────────────────────────────────────────────────────────────
    layout = brief.layout
    lines.append("LAYOUT")
    lines.append(thin_sep)
    lines.append(layout.description)
    if layout.grid:
        lines.append(f"  Grid: {layout.grid}")
    if layout.sections:
        lines.append("  Sections:")
        for section in layout.sections:
            lines.append(f"    - {section}")
    if layout.spacing_notes:
        lines.append(f"  Spacing: {layout.spacing_notes}")
    lines.append("")

    # ── Copy Hierarchy ───────────────────────────────────────────────────────
    lines.append("COPY HIERARCHY")
    lines.append(thin_sep)
    for i, item in enumerate(brief.copy_hierarchy, start=1):
        lines.append(f"  {i}. {item}")
    lines.append("")

    # ── Additional Notes ─────────────────────────────────────────────────────
    if brief.additional_notes:
        lines.append("ADDITIONAL NOTES")
        lines.append(thin_sep)
        lines.append(brief.additional_notes)
        lines.append("")

    lines.append(sep)

    return "\n".join(lines) + "\n"


def format_json(brief: DesignBrief, *, indent: int = 2) -> str:
    """Render a :class:`~brief_forge.models.DesignBrief` as a JSON string.

    Uses the brief's :meth:`~brief_forge.models.DesignBrief.to_dict` helper
    and serialises the result with :func:`json.dumps` for consistent,
    stdlib-based output that is independent of Pydantic's internal serialiser.

    Parameters
    ----------
    brief:
        The design brief to serialise.
    indent:
        JSON indentation width in spaces (default: 2).

    Returns
    -------
    str
        Indented JSON string representation of the design brief.
    """
    return json.dumps(brief.to_dict(), indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def format_brief(brief: DesignBrief, output_format: str) -> str:
    """Dispatch brief rendering to the appropriate formatter function.

    Parameters
    ----------
    brief:
        The design brief to render.
    output_format:
        One of ``"markdown"``, ``"text"``, or ``"json"`` (case-insensitive).

    Returns
    -------
    str
        The rendered brief string in the requested format.

    Raises
    ------
    ValueError
        If *output_format* is not one of the supported format names.

    Examples
    --------
    >>> md = format_brief(brief, "markdown")
    >>> txt = format_brief(brief, "text")
    >>> jsn = format_brief(brief, "JSON")  # case-insensitive
    """
    normalised = output_format.strip().lower()
    if normalised == "markdown":
        return format_markdown(brief)
    if normalised in ("text", "plain", "plain_text", "plain-text"):
        return format_plain_text(brief)
    if normalised == "json":
        return format_json(brief)
    raise ValueError(
        f"Unsupported output format: {output_format!r}. "
        f"Choose one of: {', '.join(_SUPPORTED_FORMATS)}."
    )
