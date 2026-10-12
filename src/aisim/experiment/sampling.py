"""Sampling of uncertain levers: distributions, random and Latin hypercube designs, and rank correlation.

- Every draw comes from one ``np.random.default_rng(seed)`` in the parent process, in the order the levers are
  declared, so the samples do not depend on how the runs are later split into chunks or spread over workers.
- Each distribution is drawn by its inverse CDF from uniforms: ``"random"`` takes one ``rng.random(n)`` per lever,
  ``"lhs"`` one ``scipy.stats.qmc.LatinHypercube`` design (seeded from the same generator) with a column per lever.
  ``Fixed`` levers draw nothing.
- An optional Spearman target is imposed with Iman-Conover: van der Waerden scores, the target converted to the
  Pearson correlation of normal scores (``r = 2 sin(pi rho / 6)``), and each lever reordered to the ranks of the
  correlated scores. The marginals are unchanged.

scipy is imported only when a design needs it (``TruncNormal``, ``"lhs"``), to keep ``import aisim`` light.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from aisim.batch.util import F

Method = Literal["random", "lhs"]


@dataclass(frozen=True, slots=True)
class Fixed:
    """The same value in every run."""

    value: float

    def support(self) -> tuple[float, float]:
        return (self.value, self.value)

    def ppf(self, u: F) -> F:
        return np.full(u.shape, float(self.value))


@dataclass(frozen=True, slots=True)
class Uniform:
    """Uniform on ``[lo, hi]``."""

    lo: float
    hi: float

    def __post_init__(self) -> None:
        if not self.lo <= self.hi:
            raise ValueError(f"Uniform needs lo <= hi, not {self.lo}, {self.hi}")

    def support(self) -> tuple[float, float]:
        return (self.lo, self.hi)

    def ppf(self, u: F) -> F:
        out: F = self.lo + (self.hi - self.lo) * u
        return out


@dataclass(frozen=True, slots=True)
class Triangular:
    """Triangular on ``[lo, hi]`` with its peak at ``mode``."""

    lo: float
    mode: float
    hi: float

    def __post_init__(self) -> None:
        if not (self.lo <= self.mode <= self.hi and self.lo < self.hi):
            raise ValueError(f"Triangular needs lo <= mode <= hi and lo < hi, not {self.lo}, {self.mode}, {self.hi}")

    def support(self) -> tuple[float, float]:
        return (self.lo, self.hi)

    def ppf(self, u: F) -> F:
        lo, c, hi = self.lo, self.mode, self.hi
        fc = (c - lo) / (hi - lo)
        left = lo + np.sqrt(u * (hi - lo) * (c - lo))
        right = hi - np.sqrt((1 - u) * (hi - lo) * (hi - c))
        out: F = np.where(u < fc, left, right)
        return out


@dataclass(frozen=True, slots=True)
class TruncNormal:
    """Normal with ``mean`` and ``sd``, truncated to ``[lo, hi]``."""

    mean: float
    sd: float
    lo: float
    hi: float

    def __post_init__(self) -> None:
        if not (self.sd > 0 and self.lo < self.hi):
            raise ValueError(f"TruncNormal needs sd > 0 and lo < hi, not sd={self.sd}, {self.lo}, {self.hi}")

    def support(self) -> tuple[float, float]:
        return (self.lo, self.hi)

    def ppf(self, u: F) -> F:
        from scipy.stats import truncnorm

        a, b = (self.lo - self.mean) / self.sd, (self.hi - self.mean) / self.sd
        out: F = np.asarray(truncnorm.ppf(u, a, b, loc=self.mean, scale=self.sd), dtype=np.float64)
        return np.clip(out, self.lo, self.hi)


@dataclass(frozen=True, slots=True)
class Choice:
    """One of ``values``, with probabilities proportional to ``weights`` (equal if None)."""

    values: Sequence[float]
    weights: Sequence[float] | None = None

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("Choice needs at least one value")
        if self.weights is not None and (
            len(self.weights) != len(self.values) or any(w < 0 for w in self.weights) or sum(self.weights) <= 0
        ):
            raise ValueError("Choice weights must be non-negative, one per value, with a positive sum")

    def support(self) -> tuple[float, float]:
        return (float(min(self.values)), float(max(self.values)))

    def ppf(self, u: F) -> F:
        w = np.ones(len(self.values)) if self.weights is None else np.asarray(self.weights, dtype=np.float64)
        cum = np.cumsum(w) / w.sum()
        idx = np.minimum(np.searchsorted(cum, u, side="right"), len(self.values) - 1)
        out: F = np.asarray(self.values, dtype=np.float64)[idx]
        return out


Distribution = Fixed | Uniform | Triangular | TruncNormal | Choice


def draw(
    sample: Mapping[str, Distribution],
    n: int,
    *,
    seed: int,
    method: Method = "random",
    correlation: Mapping[tuple[str, str], float] | None = None,
) -> pd.DataFrame:
    """Draw ``n`` runs of the levers in ``sample`` (declared order): a DataFrame of runs x levers.

    Raises ``ValueError`` for a bad method, a correlation over unknown or fixed levers, or a correlation matrix that
    is not positive definite.
    """
    if n < 1:
        raise ValueError("n must be at least 1")
    rng = np.random.default_rng(seed)
    random_levers = [name for name, d in sample.items() if not isinstance(d, Fixed)]
    if method == "random":
        u = {name: rng.random(n) for name in random_levers}
    elif method == "lhs":
        u = {}
        if random_levers:
            from scipy.stats import qmc

            design = qmc.LatinHypercube(d=len(random_levers), rng=rng).random(n)
            u = {name: design[:, j] for j, name in enumerate(random_levers)}
    else:
        raise ValueError(f"unknown method {method!r}; use 'random' or 'lhs'")
    cols = {name: (d.ppf(np.zeros(n)) if isinstance(d, Fixed) else d.ppf(u[name])) for name, d in sample.items()}
    if correlation:
        levers = _correlated_levers(correlation, sample)
        target = spearman_matrix(correlation, levers)
        reordered = iman_conover(np.column_stack([cols[name] for name in levers]), target, rng)
        for j, name in enumerate(levers):
            cols[name] = reordered[:, j]
    return pd.DataFrame(cols, index=pd.RangeIndex(n, name="run"))


def _correlated_levers(correlation: Mapping[tuple[str, str], float], sample: Mapping[str, Distribution]) -> list[str]:
    named = {name for pair in correlation for name in pair}
    unknown = sorted(named - set(sample))
    if unknown:
        raise ValueError(f"correlation names levers that are not sampled: {unknown}")
    fixed = sorted(name for name in named if isinstance(sample[name], Fixed))
    if fixed:
        raise ValueError(f"correlation names fixed levers: {fixed}")
    return [name for name in sample if name in named]


def spearman_matrix(correlation: Mapping[tuple[str, str], float], levers: Sequence[str]) -> F:
    """The full Spearman target over ``levers``: 1 on the diagonal, the given pairs (symmetric), 0 elsewhere."""
    ix = {name: i for i, name in enumerate(levers)}
    m = np.eye(len(levers))
    for (a, b), rho in correlation.items():
        if a == b:
            raise ValueError(f"correlation of {a!r} with itself")
        if not -1 <= rho <= 1:
            raise ValueError(f"correlation {a!r}, {b!r} = {rho} is outside [-1, 1]")
        i, j = ix[a], ix[b]
        if m[i, j] != 0 and m[i, j] != rho:
            raise ValueError(f"correlation {a!r}, {b!r} is given twice with different values")
        m[i, j] = m[j, i] = rho
    return m


def iman_conover(x: F, spearman: F, rng: np.random.Generator) -> F:
    """Reorder each column of ``x`` (runs x levers) so that its rank correlation approximates ``spearman``.

    Raises ``ValueError`` if the Pearson-adjusted target is not positive definite.
    """
    n, k = x.shape
    pearson = 2 * np.sin(np.pi * spearman / 6)
    np.fill_diagonal(pearson, 1.0)
    try:
        p = np.linalg.cholesky(pearson)
    except np.linalg.LinAlgError:
        raise ValueError("the correlation matrix is not positive definite") from None
    scores = _van_der_waerden(n)
    m = np.column_stack([rng.permutation(scores) for _ in range(k)])
    e = np.corrcoef(m, rowvar=False) if k > 1 else np.ones((1, 1))
    try:
        q = np.linalg.cholesky(e)
    except np.linalg.LinAlgError:
        raise ValueError("the score correlation is not positive definite; draw more runs") from None
    t = m @ np.linalg.inv(q).T @ p.T
    out = np.empty_like(x)
    for j in range(k):
        ranks = np.argsort(np.argsort(t[:, j], kind="stable"), kind="stable")
        out[:, j] = np.sort(x[:, j], kind="stable")[ranks]
    return out


def _van_der_waerden(n: int) -> F:
    """The normal scores ``Phi^-1(i / (n + 1))``, i = 1..n."""
    from statistics import NormalDist

    nd = NormalDist()
    return np.array([nd.inv_cdf(i / (n + 1)) for i in range(1, n + 1)])


def support_violations(dist: Distribution, lower: float, lower_inc: bool, upper: float, upper_inc: bool) -> str | None:
    """Why ``dist``'s support leaves the domain ``lower``-``upper`` (None if it does not). NaN bounds are absent."""
    lo, hi = dist.support()
    problems = []
    if not math.isnan(lower) and (lo < lower or (lo == lower and not lower_inc)):
        problems.append(f"support starts at {lo}, below the lower bound {lower} ({'in' if lower_inc else 'ex'}clusive)")
    if not math.isnan(upper) and (hi > upper or (hi == upper and not upper_inc)):
        problems.append(f"support ends at {hi}, above the upper bound {upper} ({'in' if upper_inc else 'ex'}clusive)")
    return "; ".join(problems) or None
