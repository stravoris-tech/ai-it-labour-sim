"""Array helpers of the batched engine: ``clamp``, ``ramp`` and ``softmax`` as in ``aisim.util``, plus powers, ordered
sums and the fault record.

The numerics rules of recon 03 C and E2 live here:

- ``pw`` is the only way the engine raises to a power. It hands ``np.power`` a contiguous base and an exponent
  materialised at the full shape, so numpy never takes its scalar-exponent fast paths (``sqrt`` for 0.5, ``x * x``
  for 2.0, each 1 ulp off ``**`` in about 0.04% of inputs) and makes the same choice of loop for every batch size.
- ``softmax`` uses ``np.power(E, x)`` with ``E = math.e``, as the scalar engine uses ``E ** x``; ``np.exp`` differs.
- ``csum`` replicates CPython 3.12's compensated built-in ``sum()`` and is used wherever the scalar engine calls
  ``sum()``; ``nsum`` adds naively, left to right, where the scalar engine accumulates with ``+=``. A naive sum in
  place of ``sum()`` is an ulp or so off, which the 1e-12 tolerance would absorb almost everywhere, but not where the
  model amplifies roundoff: with AI off ``Pe`` is 1 up to roundoff, and ``AICost = ... * (1 - 1 / Pe)`` turns an ulp of
  ``Pe`` into about 1e-7 (slice 3 D-ruling). Matching the scalar engine there needs its sums bit for bit.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np
from numpy.typing import NDArray

F = NDArray[np.float64]
"""A float array; in the engine, its first axis is the run axis."""

B = NDArray[np.bool_]
"""A bool array (a per-run or structural mask)."""

E = math.e


def pw(base: F | float, ex: F | float) -> F:
    """Return ``base ** ex`` element-wise, with both operands broadcast to full, contiguous float64 arrays."""
    shape = np.broadcast_shapes(np.shape(base), np.shape(ex))
    b = np.ascontiguousarray(np.broadcast_to(np.asarray(base, dtype=np.float64), shape))
    e = np.ascontiguousarray(np.broadcast_to(np.asarray(ex, dtype=np.float64), shape))
    out: F = np.power(b, e)
    return out


def clamp(x: F, lo: F | float, hi: F | float) -> F:
    """Return ``x`` limited to ``[lo, hi]``, as ``max(lo, min(hi, x))``."""
    out: F = np.maximum(lo, np.minimum(hi, x))
    return out


def ramp(year: float, start: F, end: F, v0: F | float, v1: F | float) -> F:
    """Return ``v0`` before ``start``, ``v1`` from ``end`` on, and a straight line between them, per run.

    Where ``start == end`` the ramp is a step: ``v0`` before ``start`` and ``v1`` from ``start`` on (the division by
    zero in the unselected branch is masked).
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        line = v0 + (v1 - v0) * clamp((year - start) / (end - start), 0.0, 1.0)
    out: F = np.where(start == end, np.where(year < start, v0, v1), line)
    return out


def softmax(x: F) -> F:
    """Return the logit shares of ``x`` over its last axis, as ``aisim.util.softmax`` computes them.

    ``ez = E ** (x - max(x))`` with ``E = math.e`` (``np.power``, not ``np.exp``), then ``ez / sum(ez)``.
    """
    mx = np.max(x, axis=-1, keepdims=True)
    ez = pw(E, x - mx)
    z = csum_axis(ez, ez.ndim - 1)
    out: F = ez / z[..., None]
    return out


def nsum(terms: Iterable[F]) -> F:
    """Return ``0.0 + t0 + t1 + ...``, added left to right in the order given."""
    it = iter(terms)
    acc: F = next(it) + 0.0
    for t in it:
        acc += t
    return acc


def nsum_axis(a: F, axis: int) -> F:
    """Return ``nsum`` over ``axis`` of ``a``, in index order."""
    return nsum(np.moveaxis(a, axis, 0))


def csum(terms: Iterable[F]) -> F:
    """Return the sum of ``terms`` exactly as CPython 3.12's built-in ``sum()`` computes it for floats, element-wise.

    ``sum()`` adds left to right and accumulates each addition's rounding error (Neumaier's variant of Kahan
    summation), then adds the accumulated error at the end if it is non-zero and finite (recon 03 E1, variant C).
    The rounding error of ``s + x`` is computed here with Knuth's TwoSum, which gives the same exact error as
    Neumaier's branch on ``|s| >= |x|`` without the branch, so the result is the same double.

    With one or two terms the compensation cannot change the result (``t + c`` is the exact sum, which rounds back to
    ``t``), so ``0.0 + t0 + t1`` is returned directly.
    """
    it = iter(terms)
    s: F = next(it) + 0.0
    x = next(it, None)
    if x is None:
        return s
    t: F = s + x
    x2 = next(it, None)
    if x2 is None:
        return t
    z = t - s
    c: F = (s - (t - z)) + (x - z)
    s, t = t, np.empty_like(t)
    e = np.empty_like(t)
    for x in (x2, *it):
        np.add(s, x, out=t)
        np.subtract(t, s, out=z)
        np.subtract(t, z, out=e)
        np.subtract(s, e, out=e)
        np.subtract(x, z, out=z)
        np.add(e, z, out=e)
        c += e
        s, t = t, s
    out: F = np.where((c != 0.0) & np.isfinite(c), s + c, s)
    return out


def csum_axis(a: F, axis: int) -> F:
    """Return ``csum`` over ``axis`` of ``a``, in index order (each term a contiguous slice of one copy of ``a``)."""
    return csum(np.ascontiguousarray(np.moveaxis(a, axis, 0)))


def group_sum(terms: F, members: B) -> F:
    """Sum ``terms`` over its unit axis (axis 1) within each group, as ``sum()`` over the group's units in unit order.

    ``terms`` is ``(N, units, ...)`` and ``members`` is ``(groups, units)``; the result is ``(N, groups, ...)``. Each
    group is summed over its members only (``csum``), which is the masked sum with exact zeros for non-members, without
    the zeros (an exact 0.0 changes neither the running sum nor its compensation).
    """
    parts = [_members_sum([terms[:, u] for u in np.flatnonzero(row)], terms[:, 0]) for row in members]
    return np.stack(parts, axis=1)


def group_sum_ul(terms: F, members: B) -> F:
    """As ``group_sum`` for ``(N, units, levels)`` terms, summing each group over its units and then their levels.

    The term order is the scalar engine's ``for u in UNITS if member for l in LEVELS``: unit-major, level-minor.
    """
    parts = [
        _members_sum([terms[:, u, l] for u in np.flatnonzero(row) for l in range(terms.shape[2])], terms[:, 0, 0])
        for row in members
    ]
    return np.stack(parts, axis=1)


def _members_sum(terms: list[F], like: F) -> F:
    """``csum`` of ``terms``, or zeros shaped like ``like`` for an empty group (``sum([])`` is 0)."""
    return csum(terms) if terms else np.zeros_like(like)


class Faults:
    """Per-run fault masks, by site: the places where the scalar engine would raise (recon 03 B2).

    The engine flags a run at a site when that site's denominator is zero or its power would be complex. ``any()``
    combines the sites. Internal: ``run_batch`` folds it into ``BatchResult.finite``.
    """

    def __init__(self, n: int) -> None:
        self.n = n
        self.sites: dict[str, B] = {}

    def flag(self, site: str, mask: B) -> None:
        """Add the runs in ``mask`` (shape ``(N,)``) to ``site``."""
        prev = self.sites.get(site)
        self.sites[site] = mask.copy() if prev is None else prev | mask

    def any(self) -> B:
        """The runs flagged at any site."""
        out: B = np.zeros(self.n, dtype=np.bool_)
        for mask in self.sites.values():
            out |= mask
        return out
