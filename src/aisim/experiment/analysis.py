"""Analysis helpers over results: lever drivers (rank correlation) and the shift-share split of a weighted average.

- ``drivers`` ranks the sampled levers by their Spearman rank correlation with target outputs at one year, over the
  valid runs. The ranks are average ranks (ties share their mean rank), and rho is the Pearson correlation of the
  ranks: the method of ``scipy.stats.spearmanr``, in numpy, agreeing with it within 1e-12 (recon 05 H4).
- ``shift_share`` splits the change of a weighted average ``E = sum_v w_v e_v`` since a base year into within
  (``sum w0 de``), between (``sum dw e0``) and interaction (``sum dw de``) parts, per run, as ``(N, T)`` arrays that
  ``ExperimentResult.bands`` accepts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

import numpy as np
import pandas as pd

from aisim.batch.util import F
from aisim.experiment.results import ExperimentResult
from aisim.scenarios import STRUCTURAL_LEVERS, TORNADO

LABELS: Final[Mapping[str, str]] = MappingProxyType(
    {name: label for name, _, _, label in (*TORNADO, *(row for rows in STRUCTURAL_LEVERS.values() for row in rows))}
)
"""Lever name to its label, from ``TORNADO`` and every model's ``STRUCTURAL_LEVERS`` table (one label per name)."""


def average_ranks(a: F) -> F:
    """Average ranks (1-based, ties share their mean rank) of each column of ``a`` (runs x columns)."""
    n, k = a.shape
    out = np.empty((n, k))
    for j in range(k):
        order = np.argsort(a[:, j], kind="stable")
        xs = a[order, j]
        # Each run of equal values gets the mean of the 1-based positions it spans.
        starts = np.flatnonzero(np.r_[True, xs[1:] != xs[:-1]])
        ends = np.r_[starts[1:], n]
        mean_rank = (starts + ends + 1) / 2.0
        ranks = np.repeat(mean_rank, ends - starts)
        out[order, j] = ranks
    return out


def spearman(x: F, y: F) -> F:
    """Spearman rho of every column of ``x`` with every column of ``y`` (both runs x columns): ``x`` cols x ``y`` cols.

    A constant column gives NaN.
    """
    r = average_ranks(np.column_stack([x, y]))
    r = r - r.mean(axis=0)
    norm = np.sqrt((r * r).sum(axis=0))
    with np.errstate(invalid="ignore", divide="ignore"):
        z = r / norm
    k = x.shape[1]
    out: F = z[:, :k].T @ z[:, k:]
    return out


def drivers(result: ExperimentResult, targets: Sequence[str], year: float) -> pd.DataFrame:
    """Spearman rho of every sampled lever with each target at ``year``, over the valid runs.

    Columns: ``lever``, ``label`` (the ``TORNADO`` or ``STRUCTURAL_LEVERS`` label, ``LABELS``, else the lever name),
    then one per target. Rows are sorted by the absolute rho with the first target, largest first; a lever that does
    not vary gives NaN and sorts last.
    """
    if not targets:
        raise ValueError("drivers() needs at least one target")
    levers = [str(c) for c in result.samples.columns]
    if not levers:
        raise ValueError("drivers() needs sampled levers; this result has none")
    hits = np.flatnonzero(result.years == float(year))
    if hits.size == 0:
        raise KeyError(f"year {year} was not recorded")
    j = int(hits[0])
    ok = result.valid
    x = result.samples.to_numpy(dtype=np.float64)[ok]
    y = np.column_stack([result.series[t][ok, j] for t in targets])
    rho = spearman(x, y)
    df = pd.DataFrame({"lever": levers, "label": [LABELS.get(name, name) for name in levers]})
    for i, t in enumerate(targets):
        df[t] = rho[:, i]
    order = np.argsort(-np.abs(rho[:, 0]), kind="stable")
    order = np.r_[order[~np.isnan(rho[order, 0])], order[np.isnan(rho[order, 0])]]
    return df.take(order).reset_index(drop=True)


def shift_share(weights: Mapping[str, F], values: Mapping[str, F], base_year: float, *, years: F) -> dict[str, F]:
    """Split the change since ``base_year`` of ``E = sum_v weights[v] * values[v]`` into ``within``, ``between`` and
    ``interaction`` parts, plus ``total`` (``E - E[base_year]``); each ``(N, T)`` (or any shape with years last).

    ``within = sum w0 (e - e0)``, ``between = sum (w - w0) e0``, ``interaction = sum (w - w0)(e - e0)``; the three
    sum to ``total`` up to rounding. ``weights`` and ``values`` share their keys; ``years`` are the recorded years.
    """
    if set(weights) != set(values):
        raise ValueError(f"weights and values need the same keys, not {sorted(weights)} and {sorted(values)}")
    hits = np.flatnonzero(np.asarray(years) == float(base_year))
    if hits.size == 0:
        raise ValueError(f"year {base_year} was not recorded")
    j0 = int(hits[0])
    names = list(weights)
    w = {v: np.asarray(weights[v], dtype=np.float64) for v in names}
    e = {v: np.asarray(values[v], dtype=np.float64) for v in names}
    w0 = {v: w[v][..., j0 : j0 + 1] for v in names}
    e0 = {v: e[v][..., j0 : j0 + 1] for v in names}
    zero = np.zeros_like(w[names[0]])
    within, between, interaction, level = zero.copy(), zero.copy(), zero.copy(), zero.copy()
    for v in names:
        within = within + w0[v] * (e[v] - e0[v])
        between = between + (w[v] - w0[v]) * e0[v]
        interaction = interaction + (w[v] - w0[v]) * (e[v] - e0[v])
        level = level + w[v] * e[v]
    total = level - level[..., j0 : j0 + 1]
    return {"within": within, "between": between, "interaction": interaction, "total": total}
