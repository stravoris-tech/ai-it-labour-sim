"""Shared chart plumbing: the lazy matplotlib import, Agg figures, the year axis, calibration shading and y-labels.

Figures are ``matplotlib.figure.Figure`` objects on a ``FigureCanvasAgg``, made without ``pyplot``: no global backend
or figure registry is touched, and a figure is freed when nothing refers to it.
"""

from __future__ import annotations

import importlib
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from aisim.charts.colours import GREY, INK
from aisim.experiment.metadata import catalogue

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

CALIBRATION: Final = (2024.0, 2026.0)
CALIBRATION_LABEL: Final = "calibration period 2024-2026"
WINDOW: Final = (2024.0, 2040.0)
UNIT_INFERRED: Final = " (unit inferred)"
BAND_ALPHA: Final = 0.18
SHADE_ALPHA: Final = 0.12
FONT_SIZE: Final = 9.0


def require_matplotlib() -> None:
    """Import matplotlib, or raise ``ImportError`` naming the ``charts`` extra."""
    try:
        importlib.import_module("matplotlib")
    except ImportError as e:
        raise ImportError(
            "aisim.charts needs matplotlib, which is an optional extra: install 'ai-it-labour-sim[charts]' "
            "(or 'uv sync', whose dev group includes it)"
        ) from e


def new_figure(
    nrows: int = 1, ncols: int = 1, *, figsize: tuple[float, float], sharey: bool = False, sharex: bool = False
) -> tuple[Figure, list[Axes]]:
    """A figure on an Agg canvas with a grid of axes (row-major list), constrained layout."""
    require_matplotlib()
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    fig = Figure(figsize=figsize, layout="constrained")
    FigureCanvasAgg(fig)
    grid = fig.subplots(nrows, ncols, squeeze=False, sharex=sharex, sharey=sharey)
    axes: list[Axes] = list(np.asarray(grid).ravel())
    return fig, axes


def figure_of(ax: Axes) -> Figure:
    """The root figure of ``ax``."""
    fig = ax.get_figure(root=True)
    if fig is None:
        raise ValueError("the axes do not belong to a figure")
    return fig


def style_axes(ax: Axes, ylabel: str | None = None, xlabel: str | None = None) -> None:
    """Light grid behind the data, no top or right spine, axis labels."""
    ax.grid(True, color="#D9D9D4", lw=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if ylabel is not None:
        ax.set_ylabel(ylabel)
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    ax.tick_params(labelsize=FONT_SIZE)


def year_axis(ax: Axes, window: tuple[float, float]) -> None:
    """x limits ``window``, a tick every year up to 10 years or every 2 years beyond."""
    lo, hi = float(window[0]), float(window[1])
    if not lo < hi:
        raise ValueError(f"window must be (start, end) with start < end, not {window}")
    ax.set_xlim(lo, hi)
    step = 1 if hi - lo <= 10 else 2
    ax.set_xticks(np.arange(np.ceil(lo), np.floor(hi) + 1, step))


def perturb_year(meta: Mapping[str, Any]) -> float | None:
    """A result's perturb year (``meta["perturb_from"]``), or None when its levers act from 2024."""
    y = meta.get("perturb_from")
    return None if y is None else float(y)


def shade_of(perturb_from: float | None) -> tuple[tuple[float, float], str]:
    """The shaded span and its label: 2024-2026, ``"calibration period 2024-2026"``, or, with a perturb year Y, 2024 to
    Y, ``"calibrated baseline until <Y>"`` (the runs agree until Y)."""
    if perturb_from is None:
        return CALIBRATION, CALIBRATION_LABEL
    return (2024.0, float(perturb_from)), f"calibrated baseline until {perturb_from:g}"


def shade_calibration(ax: Axes, perturb_from: float | None = None) -> None:
    """Shade 2024-2026 (gid ``shade:calibration``), labelled ``"calibration period 2024-2026"``; with a perturb year
    Y, shade 2024 to Y, labelled ``"calibrated baseline until <Y>"`` (``shade_of``)."""
    span, label = shade_of(perturb_from)
    ax.axvspan(*span, color=GREY, alpha=SHADE_ALPHA, lw=0, gid="shade:calibration", label=label)


def ylabel_for(keys: Sequence[str], ratio_to: float | None = None) -> str | None:
    """The y-label of catalogue keys: their unit(s) from ``catalogue().unit`` (distinct units joined by "; "), with
    " (unit inferred)" if any key's unit is inferred. A ratio to a year is unit-free: ``"ratio to <year>"``. None
    if there are no catalogue keys."""
    if ratio_to is not None:
        return f"ratio to {ratio_to:g}"
    cat = catalogue().set_index("key")
    known = [k for k in keys if k in cat.index]
    if not known:
        return None
    units = list(dict.fromkeys(str(cat.at[k, "unit"]) for k in known))
    inferred = any(bool(cat.at[k, "unit_inferred"]) for k in known)
    return "; ".join(units) + (UNIT_INFERRED if inferred else "")


def end_label(ax: Axes, x: float, y: float, text: str, colour: str, gid: str) -> None:
    """A direct label just right of the line's last point."""
    ax.annotate(
        text,
        (x, y),
        xytext=(5, 0),
        textcoords="offset points",
        va="center",
        fontsize=FONT_SIZE,
        color=colour,
        gid=gid,
        annotation_clip=False,
    )


def style_legend(
    ax: Axes, entries: Sequence[tuple[str, dict[str, Any]]], *, shade: bool, perturb_from: float | None = None
) -> None:
    """A legend of line and patch styles (not series): ``(label, kwargs)``, line kwargs or ``{"patch": alpha}``."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    handles: list[Any] = []
    for label, kw in entries:
        if "patch" in kw:
            handles.append(Patch(color=INK, alpha=kw["patch"], label=label))
        else:
            handles.append(Line2D([], [], color=INK, label=label, **kw))
    if shade:
        handles.append(Patch(color=GREY, alpha=SHADE_ALPHA, label=shade_of(perturb_from)[1]))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.08, 1.0), frameon=False, fontsize=FONT_SIZE)
