"""The feedback loops of phase 9 (slice 12), batch engine (see ``aisim.scalar.loops`` for the forms).

Each helper returns the term or the changed array for every run, in the scalar engine's operation order. The call sites
keep today's array per run with ``np.where`` on the strength, so a run whose strength is 0 is bit-identical to today,
and they skip a block that only changes values when every run's strength is 0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from aisim.batch.axes import EFFORT_TYPE, POOL_MASK, UNITS_OF_VENDOR, VENDOR_EMP_IX
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import F, clamp, csum_axis, group_sum, group_sum_ul
from aisim.dims import VENDORS

if TYPE_CHECKING:
    from aisim.batch.step import Step


def col(pr: BatchParams, name: str) -> F:
    """A parameter as an ``(N, 1)`` column."""
    out: F = pr[name][:, None]
    return out


# ---- R6: relative viability ------------------------------------------------------------------------------------------


def vrel(pr: BatchParams, st: BatchState) -> F:
    """``(N, vendor)`` relative viability on the 0.75-year margin signal."""
    out: F = st.VMarg / pr.fam("NormalMargin_", VENDORS)
    return out


def shortfall(pr: BatchParams, st: BatchState) -> F:
    out: F = np.maximum(0.0, col(pr, "R6Theta") - vrel(pr, st))
    return out


def cut(pr: BatchParams, st: BatchState) -> F:
    """C2: ``(N, vendor)`` fraction of desired staff cut."""
    pts = shortfall(pr, st) * pr.fam("NormalMargin_", VENDORS) * 100
    out: F = np.minimum(col(pr, "R6Cap"), col(pr, "R6e") * pts)
    return out


def client_flight(pr: BatchParams, st: BatchState) -> F:
    """C4: ``(N, vendor)`` client-flight term after the fade, at most ``C4Cap`` where ``C4Cap > 0``."""
    t = col(pr, "kViab") * np.maximum(0.0, shortfall(pr, st) - st.C4Hab)
    cap = col(pr, "C4Cap")
    out: F = np.where(cap > 0.0, np.minimum(cap, t), t)
    return out


# ---- R7: GCC scale learning ------------------------------------------------------------------------------------------


def ws(st: BatchState, CS: F) -> F:
    """``(N,)`` economy-wide GCC work share, as ``record``'s ``WorkShare_GCC``."""
    out: F = csum_axis(st.GCCW * CS, 1)
    return out


def r7(pr: BatchParams, st: BatchState, w: F) -> F:
    """R7: ``(N,)`` term, the same in every sector; 0 until ``WS0`` is filled."""
    w0 = st.WS0
    ok = w0 > 0.0
    lg = np.log(np.maximum(w, 1e-12) / np.where(ok, w0, 1.0))
    lc = pr["R7Lcap"]
    out: F = np.where(ok, pr["kR7"] * clamp(lg, -lc, lc), 0.0)
    return out


# ---- R6: the price rules ---------------------------------------------------------------------------------------------


def ceil(pr: BatchParams, Anchor: F) -> F:
    """C6: ``(N, vendor)`` anchor held at or above ``1 - AIDiscCeil``."""
    out: F = np.maximum(Anchor, (1 - pr["AIDiscCeil"])[:, None])
    return out


def floor(pr: BatchParams, st: BatchState, Pe: F, PNew: F) -> F:
    """C5: ``(N, vendor, type)`` new-bid prices held at or above ``PriceFloor x ECost`` (``x Pe`` for effort types)."""
    ec = st.ECost
    pe_v = Pe[:, VENDOR_EMP_IX][:, :, None]
    fl = pr["PriceFloor"][:, None, None] * ec[:, :, None] * np.where(EFFORT_TYPE[None, None, :], pe_v, 1.0)
    out: F = np.where((ec > 0.0)[:, :, None], np.maximum(PNew, fl), PNew)
    return out


# ---- R10: attrition cost ---------------------------------------------------------------------------------------------


def vol_cell(fl: F, sw: F) -> F:
    """``(N, unit, level)`` voluntary exits: quits, leaving the field and switch-outs."""
    out: F = fl[:, :, :, 0] + fl[:, :, :, 1] + sw[:, :, :, 1]
    return out


def attr(st: BatchState, fl: F, sw: F) -> F:
    """``(N, vendor)`` voluntary exits per head."""
    out_ = group_sum_ul(vol_cell(fl, sw), UNITS_OF_VENDOR)
    hh = group_sum_ul(st.H, UNITS_OF_VENDOR)
    a: F = np.where(hh > 0, out_ / np.where(hh > 0, hh, 1.0), 0.0)
    return a


def vol_ratio(st: BatchState, fl: F, sw: F) -> F:
    """``(N, vendor)`` voluntary exits per head over their 2024 value (1 at 2024)."""
    a = attr(st, fl, sw)
    a0 = np.where(st.Attr0 > 0.0, st.Attr0, a)
    out: F = np.where(a0 > 0.0, a / np.where(a0 > 0.0, a0, 1.0), 1.0)
    return out


def r10cost(pr: BatchParams, st: BatchState, fl: F, sw: F, Wage: F) -> F:
    """R10: ``(N, vendor)`` replacement cost of voluntary exits above the 2024 rate."""
    a0 = st.Attr0
    a = attr(st, fl, sw)
    wout = group_sum_ul(Wage * vol_cell(fl, sw), UNITS_OF_VENDOR)
    ok = (a0 > 0) & (a > 0)
    frac = np.where(ok, np.maximum(0.0, 1 - a0 / np.where(ok, a, 1.0)), 0.0)
    out: F = col(pr, "R10rc") * wout * frac
    return out


# ---- R4: skill erosion -----------------------------------------------------------------------------------------------


def dur(pr: BatchParams, st: BatchState, hires: F) -> F:
    """``(N, region, level)`` expected seeker spell length."""
    hU = group_sum(hires, POOL_MASK)
    U = st.U
    den = hU + U * pr["SeekerExitRate"][:, None, None]
    d: F = np.where(den > 0, U / np.where(den > 0, den, 1.0), 0.0)
    return d


def seek_exit(pr: BatchParams, st: BatchState, hires: F, base: F) -> F:
    """R4: ``(N, region, level)`` seeker exit; ``base`` where the region's strength is 0."""
    a = np.stack([pr["R4aIN"], pr["R4a"]], axis=1)[:, :, None]  # REGIONS = (IN, ON)
    on = a != 0.0
    if not np.any(on):
        return base
    D = dur(pr, st, hires)
    D0 = np.where(st.Dur0 <= 0.0, D, st.Dur0)
    m = (1 + a * clamp((D - 0.5) / 0.5, 0.0, 1.0)) / (1 + a * clamp((D0 - 0.5) / 0.5, 0.0, 1.0))
    x = np.minimum(base * m, st.U / pr["MinSeekTime"][:, None, None])
    out: F = np.where(on, x, base)
    return out


# ---- references and signals ------------------------------------------------------------------------------------------


def pre(pr: BatchParams, st: BatchState, s: Step) -> F:
    """Start of ``integrate``: fill the 2024 references where unfilled; return the C4 shortfall ``(N, vendor)``."""
    np.copyto(st.WS0, ws(st, s.work.CS), where=st.WS0 <= 0.0)
    np.copyto(st.Attr0, attr(st, s.exits.fl, s.switching.sw), where=st.Attr0 <= 0.0)
    np.copyto(st.ECost, s.books.VB.CostIdx, where=st.ECost <= 0.0)
    np.copyto(st.Dur0, dur(pr, st, s.hiring.hires), where=st.Dur0 <= 0.0)
    return shortfall(pr, st)


def post(pr: BatchParams, st: BatchState, s: Step, d: float, sf: F) -> None:
    """End of ``integrate``, after every other stock: advance ``VMarg``, ``ECost`` and ``C4Hab``."""
    f, b = s.contracts.VF, s.books.VB
    st.VMarg[...] += d * (b.Margin - st.VMarg) / col(pr, "R6MargTime")
    st.ECost[...] += d * (b.CostIdx - st.ECost) * f.ExpRate
    st.C4Hab[...] += d * (sf - st.C4Hab) / col(pr, "C4FadeTime")
