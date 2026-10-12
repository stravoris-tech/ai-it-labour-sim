"""Saving charts: PNG, SVG or PDF with byte-stable metadata, and SVG text for reports.

- PNG at 150 dpi with ``metadata={"Software": None}``; SVG with ``{"Date": None}``; PDF with
  ``{"CreationDate": None}``. Saved twice on one machine, a chart gives the same bytes (recon 05 D3). Bytes differ
  across platforms (fonts, Agg builds), so tests check the plotted data, never image files.
- SVG keeps text as text (``svg.fonttype = "none"``) and salts its hashed element ids with ``svg.hashsalt`` (the file
  name by default), so two charts on one page do not share hashed ids.
- Saving fixes the layout. Constrained layout re-solves on every draw and does not settle (each save of one figure
  moved the axes by a fraction of a point), so the first save draws once and then turns the layout engine off.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from aisim.charts._base import require_matplotlib

if TYPE_CHECKING:
    from matplotlib.figure import Figure

DPI: Final = 150
METADATA: Final[dict[str, dict[str, Any]]] = {
    "png": {"Software": None},
    "svg": {"Date": None},
    "pdf": {"CreationDate": None},
}


def settle(fig: Figure) -> None:
    """Solve the layout once and fix it (no-op if already fixed), so every later draw gives the same output."""
    if fig.get_layout_engine() is not None:
        fig.draw_without_rendering()
        fig.set_layout_engine("none")


def save(fig: Figure, path: str | Path, *, salt: str | None = None) -> Path:
    """Save ``fig`` to ``path``, the format chosen by the suffix (``.png``, ``.svg`` or ``.pdf``); return the path.

    ``salt`` is the SVG hash salt (default: the file's stem).
    """
    require_matplotlib()
    import matplotlib

    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in METADATA:
        raise ValueError(f"save() writes .png, .svg or .pdf, not {path.name!r}")
    settle(fig)
    with matplotlib.rc_context({"svg.hashsalt": salt if salt is not None else path.stem, "svg.fonttype": "none"}):
        fig.savefig(path, format=fmt, dpi=DPI, metadata=METADATA[fmt], bbox_inches="tight")
    return path


def svg_text(fig: Figure, salt: str) -> str:
    """``fig`` as SVG text (fonttype none, hashed ids salted with ``salt``, no date)."""
    require_matplotlib()
    import matplotlib

    settle(fig)
    buf = io.StringIO()
    with matplotlib.rc_context({"svg.hashsalt": salt, "svg.fonttype": "none"}):
        fig.savefig(buf, format="svg", metadata=METADATA["svg"], bbox_inches="tight")
    return buf.getvalue()
