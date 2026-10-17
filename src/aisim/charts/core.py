"""The charts: ``bands``, ``scenarios``, ``lines`` and ``drivers``. Each returns a ``matplotlib.figure.Figure``.

Every plotted artist carries a ``gid`` naming what it shows, so tests (and readers of an SVG) can find it:

- ``median:<key>``, ``band:<key>`` (the p10-p90 band), ``baseline:<key>`` (dashed one-run line), ``label:<key>``
  (direct end label), ``line:<name>`` (``lines``) and ``shade:calibration``;
- ``scenarios`` sets the axes' gid to ``scenario:<label>`` (small multiples) or ``key:<key>`` (overlay), and names
  overlay artists ``median:<key>@<scenario label>``; ``drivers`` names each bar ``bar:<target>:<lever>``.

``<key>`` is the catalogue key, or the label given for a computed ``(N, T)`` array.

Shading. The 2024-2026 calibration period is shaded by default (``shade=False`` turns it off). The runs are fitted to
2024-2026 data but do not agree there: levers act from 2024 (11 of the 23 scenario and tornado levers move 2025-2026),
so a band in that period reflects lever uncertainty applied from 2024. A result run with ``perturb_from = Y`` is the
calibrated baseline until Y: ``bands``, ``scenarios`` and ``lines`` (of a result) then shade 2024 to Y, labelled
"calibrated baseline until <Y>", and the bands there have zero width.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal

import numpy as np
import pandas as pd

from aisim.batch.util import F
from aisim.charts._base import (
    BAND_ALPHA,
    FONT_SIZE,
    WINDOW,
    end_label,
    figure_of,
    new_figure,
    perturb_year,
    shade_calibration,
    shade_of,
    style_axes,
    style_legend,
    year_axis,
    ylabel_for,
)
from aisim.charts.colours import GREY, INK, LOWERS, RAISES, key_colours, key_styles, scenario_colour, scenario_style
from aisim.experiment.derived import ratio_to_base
from aisim.experiment.results import ExperimentResult
from aisim.experiment.scenarios import ScenarioResult, scenario_label

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

Keys = str | Sequence[str] | Mapping[str, str | F]
"""Keys to chart: one key, a list of keys, or ``{label: key or (N, T) array}``."""


def _entries(keys: Keys, labels: Mapping[str, str] | None) -> list[tuple[str, str, str | F]]:
    """``(name, label, source)`` per series: the name goes in gids, the source is a key or an array."""
    if isinstance(keys, str):
        keys = [keys]
    if isinstance(keys, Mapping):
        return [(name, name, src) for name, src in keys.items()]
    lab = labels or {}
    return [(k, lab.get(k, k), k) for k in keys]


def _band_label(q: tuple[float, float], n_valid: int) -> str:
    return f"p{q[0] * 100:g}-p{q[1] * 100:g} ({n_valid:,} runs)"


def _in_window(years: F, window: tuple[float, float]) -> np.ndarray[Any, np.dtype[np.bool_]]:
    return (years >= window[0]) & (years <= window[1])


def bands(
    result: ExperimentResult,
    keys: Keys,
    *,
    baseline: ExperimentResult | None = None,
    ratio_to: float | None = None,
    q: tuple[float, float] = (0.1, 0.9),
    labels: Mapping[str, str] | None = None,
    ylabel: str | None = None,
    title: str | None = None,
    window: tuple[float, float] = WINDOW,
    shade: bool = True,
    ax: Axes | None = None,
) -> Figure:
    """One panel: per key, the median line and the ``q`` band over the valid runs, with direct end labels.

    - ``keys``: a key, keys, or ``{label: key or (N, T) array}`` for computed series (``ExperimentResult.bands``
      takes the arrays with the same filter, window and ``pct``).
    - ``baseline``: a one-run result drawn as a dashed line for each key entry (not for arrays).
    - ``ratio_to``: each run (and the baseline) divided by its own value in that year.
    - The y-label comes from the catalogue unit (``ylabel`` overrides it); the calibration period is shaded unless
      ``shade=False``. Draws on ``ax`` if given.
    """
    if ax is None:
        fig, (ax,) = new_figure(figsize=(8.5, 5.0))
    else:
        fig = figure_of(ax)
    entries = _entries(keys, labels)
    colours = key_colours([name for name, _, _ in entries])
    styles = key_styles([name for name, _, _ in entries])
    qs = (q[0], 0.5, q[1])
    for name, label, src in entries:
        b = result.bands(src, q=qs, ratio_to=ratio_to, years=window)
        x = b.index.to_numpy(dtype=np.float64)
        c = colours[name]
        ax.fill_between(x, b[q[0]].to_numpy(), b[q[1]].to_numpy(), color=c, alpha=BAND_ALPHA, lw=0, gid=f"band:{name}")
        median = b[0.5].to_numpy()
        ax.plot(x, median, color=c, lw=2, ls=styles[name], gid=f"median:{name}")
        if baseline is not None and isinstance(src, str):
            y = baseline.single(src)
            if ratio_to is not None:
                y = ratio_to_base(y[None, :], baseline.years, float(ratio_to))[0]
            keep = _in_window(baseline.years, window)
            ax.plot(baseline.years[keep], y[keep], color=c, lw=1.4, ls="--", gid=f"baseline:{name}")
        end_label(ax, float(x[-1]), float(median[-1]), label, c, f"label:{name}")
    y0 = perturb_year(result.meta)
    if shade:
        shade_calibration(ax, y0)
    year_axis(ax, window)
    key_names = [src for _, _, src in entries if isinstance(src, str)]
    style_axes(ax, ylabel if ylabel is not None else ylabel_for(key_names, ratio_to), "Year")
    legend: list[tuple[str, dict[str, Any]]] = [
        ("median", {"lw": 2}),
        (_band_label(q, result.n - result.n_invalid), {"patch": BAND_ALPHA}),
    ]
    if baseline is not None:
        legend.append(("baseline run", {"lw": 1.4, "ls": "--"}))
    style_legend(ax, legend, shade=shade, perturb_from=y0)
    if title is not None:
        ax.set_title(title)
    return fig


def scenarios(
    scen_result: ScenarioResult,
    keys: str | Sequence[str],
    *,
    layout: Literal["small_multiples", "overlay"] = "small_multiples",
    q: tuple[float, float] = (0.1, 0.9),
    ratio_to: float | None = None,
    labels: Mapping[str, str] | None = None,
    ylabel: str | None = None,
    title: str | None = None,
    window: tuple[float, float] = WINDOW,
    shade: bool = True,
) -> Figure:
    """Compare scenarios, with common y-limits across panels.

    - ``"small_multiples"``: one panel per scenario, a median line (and band, for more than one run) per key.
    - ``"overlay"``: one panel per key, a median line and band per scenario, in the scenario colours. The panels
      share y-limits when the keys share a catalogue unit (or with ``ratio_to``); keys in different units keep their
      own limits and y-labels.
    """
    names = [keys] if isinstance(keys, str) else list(keys)
    lab = labels or {}
    if layout == "small_multiples":
        panels: list[Any] = list(scen_result.scenarios)
    elif layout == "overlay":
        panels = names
    else:
        raise ValueError(f"layout must be 'small_multiples' or 'overlay', not {layout!r}")
    ncols = len(panels) if len(panels) <= 2 else (2 if len(panels) == 4 else 3)
    nrows = -(-len(panels) // ncols)
    units = {ylabel_for([k], ratio_to) for k in names}
    share = layout == "small_multiples" or len(units) == 1
    fig, axes = new_figure(nrows, ncols, figsize=(4.6 * ncols + 2.2, 3.4 * nrows + 0.6), sharex=True, sharey=share)
    qs = (q[0], 0.5, q[1])
    handles: list[tuple[str, str, str]] = []

    def draw(ax: Axes, res: ExperimentResult, key: str, colour: str, style: str, gid: str) -> None:
        b = res.bands(key, q=qs, ratio_to=ratio_to, years=window)
        x = b.index.to_numpy(dtype=np.float64)
        if res.n > 1:
            ax.fill_between(
                x, b[q[0]].to_numpy(), b[q[1]].to_numpy(), color=colour, alpha=BAND_ALPHA, lw=0, gid=f"band:{gid}"
            )
        ax.plot(x, b[0.5].to_numpy(), color=colour, lw=2, ls=style, gid=f"median:{gid}")

    if layout == "small_multiples":
        colours, styles = key_colours(names), key_styles(names)
        for ax, s in zip(axes, scen_result.scenarios, strict=False):
            ax.set_gid(f"scenario:{scenario_label(s)}")
            for k in names:
                draw(ax, scen_result[s], k, colours[k], styles[k], k)
            ax.set_title(scenario_label(s), fontsize=FONT_SIZE + 1)
        handles = [(lab.get(k, k), colours[k], styles[k]) for k in names]
    else:
        for ax, k in zip(axes, names, strict=False):
            ax.set_gid(f"key:{k}")
            for i, s in enumerate(scen_result.scenarios):
                name = scenario_label(s)
                draw(ax, scen_result[s], k, scenario_colour(name, i), scenario_style(name, i), f"{k}@{name}")
            ax.set_title(lab.get(k, k), fontsize=FONT_SIZE + 1)
        handles = [
            (scenario_label(s), scenario_colour(scenario_label(s), i), scenario_style(scenario_label(s), i))
            for i, s in enumerate(scen_result)
        ]
    label = ylabel if ylabel is not None else ylabel_for(names, ratio_to)
    y0 = perturb_year(scen_result.meta)
    for i, ax in enumerate(axes):
        if i >= len(panels):
            ax.set_visible(False)
            continue
        if shade:
            shade_calibration(ax, y0)
        year_axis(ax, window)
        if share:
            panel_label = label if i % ncols == 0 else None
        else:
            panel_label = ylabel if ylabel is not None else ylabel_for([panels[i]], ratio_to)
        style_axes(ax, panel_label, "Year" if i >= len(panels) - ncols else None)
    _figure_legend(fig, handles, scen_result, q, shade, y0)
    if title is not None:
        fig.suptitle(title)
    return fig


def _figure_legend(
    fig: Figure,
    handles: Sequence[tuple[str, str, str]],
    scen_result: ScenarioResult,
    q: tuple[float, float],
    shade: bool,
    perturb_from: float | None,
) -> None:
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    from aisim.charts._base import SHADE_ALPHA

    items: list[Any] = [Line2D([], [], color=c, lw=2, ls=style, label=text) for text, c, style in handles]
    first = scen_result[scen_result.scenarios[0]]
    if first.n > 1:
        items.append(Patch(color=INK, alpha=BAND_ALPHA, label=_band_label(q, first.n) + " per scenario"))
    if shade:
        items.append(Patch(color=GREY, alpha=SHADE_ALPHA, label=shade_of(perturb_from)[1]))
    fig.legend(handles=items, loc="outside right upper", frameon=False, fontsize=FONT_SIZE)


def lines(
    series: ExperimentResult | Mapping[str, F],
    *,
    keys: str | Sequence[str] | None = None,
    years: F | None = None,
    x: F | None = None,
    xlabel: str | None = None,
    labels: Mapping[str, str] | None = None,
    ylabel: str | None = None,
    title: str | None = None,
    window: tuple[float, float] = WINDOW,
    shade: bool = True,
    ax: Axes | None = None,
) -> Figure:
    """Plain lines: a one-run result (its ``keys``, all if None) or ``{label: (T,) array}`` over ``years``.

    With ``x=`` (a sweep, say) the x-axis is that array, labelled ``xlabel``: no window and no shading. A result's
    shading follows its ``perturb_from``, as in ``bands``; a mapping has no meta, so it shades the calibration period.
    """
    y0 = None
    if isinstance(series, ExperimentResult):
        y0 = perturb_year(series.meta)
        names = list(series.series) if keys is None else ([keys] if isinstance(keys, str) else list(keys))
        data = {k: series.single(k) for k in names}
        xs = series.years if x is None else np.asarray(x, dtype=np.float64)
        default_ylabel = ylabel_for(names)
    else:
        names = list(series)
        data = {k: np.asarray(v, dtype=np.float64) for k, v in series.items()}
        if x is None and years is None:
            raise ValueError("lines() with a mapping needs years= (or x= for a non-year axis)")
        xs = np.asarray(x if x is not None else years, dtype=np.float64)
        default_ylabel = None
    if ax is None:
        fig, (ax,) = new_figure(figsize=(8.5, 5.0))
    else:
        fig = figure_of(ax)
    keep = np.ones(len(xs), dtype=np.bool_) if x is not None else _in_window(xs, window)
    colours, styles = key_colours(names), key_styles(names)
    lab = labels or {}
    for k in names:
        y = data[k]
        if y.shape != xs.shape:
            raise ValueError(f"{k}: {y.shape} values for {xs.shape} x values")
        ax.plot(xs[keep], y[keep], color=colours[k], lw=2, ls=styles[k], gid=f"line:{k}")
        end_label(ax, float(xs[keep][-1]), float(y[keep][-1]), lab.get(k, k), colours[k], f"label:{k}")
    if x is None:
        if shade:
            shade_calibration(ax, y0)
        year_axis(ax, window)
        style_axes(ax, ylabel if ylabel is not None else default_ylabel, xlabel or "Year")
        if shade:
            style_legend(ax, [], shade=True, perturb_from=y0)
    else:
        style_axes(ax, ylabel if ylabel is not None else default_ylabel, xlabel)
    if title is not None:
        ax.set_title(title)
    return fig


def drivers(df: pd.DataFrame, *, targets: Sequence[str] | None = None, title: str | None = None) -> Figure:
    """Horizontal bars of ``aisim.experiment.drivers`` output: one panel per target, the levers in the frame's order
    (strongest first, at the top) in every panel, blue where a lever raises the target and vermillion where it
    lowers it."""
    from matplotlib.patches import Patch

    cols = [c for c in df.columns if c not in ("lever", "label")] if targets is None else list(targets)
    if not cols:
        raise ValueError("no target columns to chart")
    levers = [str(v) for v in df["lever"]]
    names = [str(v) for v in df["label"]] if "label" in df.columns else levers
    ypos = np.arange(len(levers))[::-1].astype(np.float64)
    fig, axes = new_figure(1, len(cols), figsize=(3.4 * len(cols) + 2.6, 0.32 * len(levers) + 1.6), sharey=True)
    for ax, t in zip(axes, cols, strict=True):
        rho = df[t].to_numpy(dtype=np.float64)
        colours = [GREY if np.isnan(r) else (RAISES if r >= 0 else LOWERS) for r in rho]
        bars = ax.barh(ypos, np.nan_to_num(rho), color=colours, height=0.7)
        for patch, lever in zip(bars.patches, levers, strict=True):
            patch.set_gid(f"bar:{t}:{lever}")
        ax.axvline(0, color=INK, lw=0.8)
        ax.set_xlim(-1, 1)
        ax.set_xticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        ax.set_title(str(t), fontsize=FONT_SIZE + 1)
        style_axes(ax, None, "Spearman rho (unitless)")
        ax.grid(False, axis="y")
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(names)
    fig.legend(
        handles=[Patch(color=RAISES, label="raises"), Patch(color=LOWERS, label="lowers")],
        loc="outside lower center",
        ncols=2,
        frameon=False,
        fontsize=FONT_SIZE,
    )
    if title is not None:
        fig.suptitle(title)
    return fig
