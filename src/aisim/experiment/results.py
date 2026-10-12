"""The results of an experiment: ``(N, T)`` numpy arrays per key, with pandas views on demand.

- ``series[key]`` is ``(N, T)``: runs x recorded years. ``valid`` is ``BatchResult.finite`` (a finite state and no
  crash-site fault). The views (``frame``, ``long``, ``bands``, ``q3``) are built when asked for.
- Percentiles use the prototype's ``pct`` exactly (``phase7_runs.py:151-153``), vectorised over years: sort along
  runs, then ``xs[f] + (xs[c] - xs[f]) * (i - f)``. ``np.quantile`` interpolates from the upper neighbour when the
  fraction is at least 0.5 and so differs from it by 1 ULP on some data (recon 04 D3).
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from aisim.batch.state import BatchState
from aisim.batch.util import B, F
from aisim.dims import VENDORS
from aisim.experiment.derived import ratio_to_base

Q3_LABELS = ("collapse", "equilibrium", "adjusting")
"""The Q3 outcome labels: the first word of the prototype's ``q3`` result."""

Q3_YEARS = tuple(range(2024, 2041))


def pct(a: F, q: float) -> F:
    """The prototype's percentile (``phase7_runs.py:151-153``) of every column of ``a`` (runs x years).

    Same operations in the same order: a stable sort along runs, ``i = (n - 1) * q``, ``f = floor(i)``,
    ``c = min(f + 1, n - 1)``, then ``xs[f] + (xs[c] - xs[f]) * (i - f)``.
    """
    xs = np.sort(a, axis=0, kind="stable")
    n = xs.shape[0]
    i = (n - 1) * q
    f = math.floor(i)
    c = min(f + 1, n - 1)
    out: F = xs[f] + (xs[c] - xs[f]) * (i - f)
    return out


@dataclass(frozen=True)
class ExperimentResult:
    """The output of ``run_experiment``.

    - ``samples``: runs x the parameters that vary (the sampled levers or the explicit design).
    - ``years``: ``(T,)``, the recorded years.
    - ``series``: key to ``(N, T)`` array, for every recorded key (requested, plus those a derived output needs) and
      every requested derived output.
    - ``valid``: ``(N,)``, ``BatchResult.finite``: a finite state and no crash-site fault.
    - ``meta``: the experiment, seed, outputs, record_every, dt, stop, package versions, ``NPY_DISABLE_CPU_FEATURES``
      and ``n_invalid``.
    - ``final_state`` and ``mins``: only with ``keep_state=True``.
    """

    samples: pd.DataFrame
    years: F
    series: Mapping[str, F]
    valid: B
    meta: Mapping[str, Any]
    final_state: BatchState | None = None
    mins: Mapping[str, F] | None = None
    _year_index: dict[float, int] = field(default_factory=dict, repr=False, compare=False)

    @property
    def n(self) -> int:
        """The number of runs."""
        return int(self.valid.shape[0])

    @property
    def n_invalid(self) -> int:
        """The number of runs that are not valid."""
        return int((~self.valid).sum())

    def _get(self, key: str) -> F:
        try:
            return self.series[key]
        except KeyError:
            raise KeyError(f"{key!r} was not recorded; recorded: {sorted(self.series)}") from None

    def _col(self, year: float) -> int:
        if not self._year_index:
            self._year_index.update({float(y): j for j, y in enumerate(self.years)})
        try:
            return self._year_index[float(year)]
        except KeyError:
            raise KeyError(f"year {year} was not recorded") from None

    def frame(self, key: str) -> pd.DataFrame:
        """``key`` as a DataFrame: index ``run``, one column per recorded year."""
        return pd.DataFrame(
            self._get(key), index=pd.RangeIndex(self.n, name="run"), columns=pd.Index(self.years, name="year")
        )

    def long(self, keys: Sequence[str] | None = None) -> pd.DataFrame:
        """A long table with columns ``run, year, key, value`` (``key`` categorical), for ``keys`` (all if None)."""
        names = list(self.series) if keys is None else list(keys)
        t = len(self.years)
        run = np.tile(np.repeat(np.arange(self.n, dtype=np.int32), t), len(names))
        year = np.tile(self.years, self.n * len(names))
        codes = np.repeat(np.arange(len(names), dtype=np.int32), self.n * t)
        value = np.concatenate([self._get(k).ravel() for k in names]) if names else np.empty(0)
        return pd.DataFrame(
            {
                "run": run,
                "year": year,
                "key": pd.Categorical.from_codes(codes, categories=pd.Index(names)),
                "value": value,
            }
        )

    def ratio(self, key: str, base_year: float = 2024) -> F:
        """``(N, T)``: each run's ``key`` divided by its own value in ``base_year``."""
        return ratio_to_base(self._get(key), self.years, float(base_year))

    def bands(
        self,
        key: str,
        q: Sequence[float] = (0.1, 0.5, 0.9),
        ratio_to: float | None = None,
        years: tuple[float, float] | None = None,
    ) -> pd.DataFrame:
        """Per-year percentiles of ``key`` over the valid runs: a DataFrame of years x ``q``, with the exact ``pct``.

        ``ratio_to`` divides each run by its own value in that year first (a ratio band), ``years = (start, end)``
        keeps that window (inclusive). ``attrs["n_invalid"]`` holds the number of runs left out; a warning is issued
        when it is above 0.
        """
        a = self.ratio(key, ratio_to) if ratio_to is not None else self._get(key)
        cols = np.ones(len(self.years), dtype=np.bool_)
        if years is not None:
            cols = (self.years >= years[0]) & (self.years <= years[1])
        a = a[self.valid][:, cols]
        if a.shape[0] == 0:
            raise ValueError("no valid runs to take percentiles over")
        out = pd.DataFrame(
            {qq: pct(a, qq) for qq in q}, index=pd.Index(self.years[cols], name="year"), columns=pd.Index(q, name="q")
        )
        out.attrs["n_invalid"] = self.n_invalid
        if self.n_invalid:
            warnings.warn(f"bands: {self.n_invalid} invalid run(s) left out", stacklevel=2)
        return out

    def q3(self) -> pd.DataFrame:
        """The Q3 outcome per run and vendor: ``collapse``, ``equilibrium`` or ``adjusting`` (NA for an invalid run).

        A vectorised ``q3`` of ``phase7_runs.py:65-76``, on annual ``Vi_v``, ``Head_v`` and ``Revenue_v``:

        - collapse: a streak of at least 3 years with ``Vi_v < 0`` anywhere in 2024-2040, and a headcount fall of
          more than 15% in 2039 or 2040;
        - equilibrium: otherwise, if ``Head_v`` and ``Revenue_v`` changed less than 2% in each of 2039 and 2040;
        - adjusting: otherwise (the prototype appends the change rate; the label keeps the first word).

        This is the code's test, which is the reference. It differs from the spec's (00:345-351): the negative streak
        may lie anywhere in the run, not in the last years, and the equilibrium test checks ``Head_v`` and
        ``Revenue_v`` only, not every major stock (recon 04 G2). Needs integer years 2024-2040 recorded.
        """
        idx = [self._col(y) for y in Q3_YEARS]
        out: dict[str, Any] = {}
        for v in VENDORS:
            vi = self._get("Vi_" + v)[:, idx]
            head = self._get("Head_" + v)[:, idx]
            rev = self._get("Revenue_" + v)[:, idx]
            neg_run = np.zeros(self.n, dtype=np.int64)
            best = np.zeros(self.n, dtype=np.int64)
            for j in range(len(Q3_YEARS)):
                neg_run = np.where(vi[:, j] < 0, neg_run + 1, 0)
                best = np.maximum(best, neg_run)
            fall = np.maximum.reduce([1 - head[:, j] / np.maximum(head[:, j - 1], 1e-9) for j in (15, 16)])
            ch = np.maximum.reduce(
                [np.abs(x[:, j] / np.maximum(x[:, j - 1], 1e-9) - 1) for j in (15, 16) for x in (head, rev)]
            )
            codes = np.where((best >= 3) & (fall > 0.15), 0, np.where(ch < 0.02, 1, 2))
            codes = np.where(self.valid, codes, -1)
            out[v] = pd.Categorical.from_codes(codes.astype(np.int64), categories=pd.Index(Q3_LABELS))
        return pd.DataFrame(out, index=pd.RangeIndex(self.n, name="run"))

    def q3_counts(self) -> pd.DataFrame:
        """The number of valid runs with each Q3 label: labels x vendors."""
        q = self.q3()
        counts = {v: q[v].value_counts(sort=False).reindex(list(Q3_LABELS), fill_value=0) for v in VENDORS}
        out = pd.DataFrame(counts)
        out.index.name = "label"
        return out.astype(np.int64)
