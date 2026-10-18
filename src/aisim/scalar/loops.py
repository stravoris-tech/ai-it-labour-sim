"""The feedback loops of phase 9 (slice 12), scalar engine: R7, R6 (C2, C4, C5, C6), R10 and R4.

Forms are recon 12b's, settled by the operator (2026-10-18); ``docs/model-changes-phase9.md`` gives each one's
mechanism and evidence. Each term is gated by its own strength at its call site, so at strength 0 today's code runs
unchanged:

- **R7, GCC scale learning** (``kR7``): every sector's GCC sourcing value gains ``kR7 x clamp(ln(WS / WS_2024), -R7Lcap,
  R7Lcap)``, with ``WS`` the economy-wide GCC work share (the recorded ``WorkShare_GCC``). Call site: S13d
  ``sourcing_targets``.
- **R6, vendor stress**, on relative viability ``Vrel = VMarg / NormalMargin`` (the 0.75-year margin signal):
  - C2 capacity exit (``R6e``): the vendor's desired staff is cut by ``min(R6Cap, R6e x points below R6Theta)``. Call
    site: S5 ``staffing``.
  - C4 client flight (``kViab``): the vendor's sourcing value falls by ``kViab x max(0, s - C4Hab)``, ``s = max(0,
    R6Theta - Vrel)``, with ``C4Hab`` the shortfall smoothed over ``C4FadeTime`` (the fade), at most ``C4Cap`` when
    ``C4Cap > 0``. Call site: S13b ``option_costs``.
  - C5 price floor (``PriceFloor``): new-bid prices are at least ``PriceFloor x ECost`` (times ``Pe`` for effort
    types). Call site: S10 ``contracts``.
  - C6 AI-discount ceiling (``AIDiscCeil``): the client price anchor is at least ``1 - AIDiscCeil``, after noise. Call
    site: S10 ``contracts``.
- **R10, attrition cost** (``R10rc``): vendor cost gains ``R10rc x wage x voluntary exits x max(0, 1 - VA_2024 /
  VA)``, voluntary exits being quits, leaving the field and switch-outs. Call site: S11b ``vendor_books``.
- **R4, skill erosion** (``R4a`` onshore, ``R4aIN`` India): the seeker exit is multiplied by ``1 + a x clamp((Dur -
  0.5) / 0.5, 0, 1)`` over its 2024 value and capped at ``U / MinSeekTime``. Call site: S8f ``pools``.

The 2024 references and smoothed signals are state families (``aisim.state.LOOP_FAMILIES``): ``pre`` fills the
references at the start of ``integrate`` on the first step, and ``post`` advances the signals after every other
stock. Both run for every model; with every strength at 0 nothing reads them.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import TYPE_CHECKING

from aisim.dims import EFFORT, EMP_OF, LEVELS, POOL, REGIONS, SECTORS, TYPES, UNITS, VENDORS
from aisim.state import Mat, State, Vec
from aisim.util import clamp

if TYPE_CHECKING:
    from aisim.scalar.labour_market import LevelFlows, SwitchFlows
    from aisim.scalar.step import Step

Flows = Mapping[str, Mapping[str, "LevelFlows"]]
Switches = Mapping[str, Mapping[str, "SwitchFlows"]]


# ---- R6: relative viability ------------------------------------------------------------------------------------------


def vrel(pr: Mapping[str, float], st: State, v: str) -> float:
    """Relative viability of vendor ``v``: the 0.75-year margin signal over the normal margin (1 at 2024)."""
    return st["VMarg"][v] / pr["NormalMargin_" + v]


def shortfall(pr: Mapping[str, float], st: State, v: str) -> float:
    """The relative-viability shortfall below ``R6Theta`` (0 when above it)."""
    return max(0.0, pr["R6Theta"] - vrel(pr, st, v))


def cut(pr: Mapping[str, float], st: State, v: str) -> float:
    """C2: the fraction of desired staff cut, ``min(R6Cap, R6e x margin points below theta)``."""
    pts = shortfall(pr, st, v) * pr["NormalMargin_" + v] * 100
    return min(pr["R6Cap"], pr["R6e"] * pts)


def client_flight(pr: Mapping[str, float], st: State, v: str) -> float:
    """C4: ``kViab x`` the shortfall less its habituated part (the fade), at most ``C4Cap`` when ``C4Cap > 0``."""
    t = pr["kViab"] * max(0.0, shortfall(pr, st, v) - st["C4Hab"][v])
    if pr["C4Cap"] > 0.0:
        t = min(pr["C4Cap"], t)
    return t


# ---- R7: GCC scale learning ------------------------------------------------------------------------------------------


def ws(st: State, CS: Vec) -> float:
    """The economy-wide GCC work share, as ``record`` computes ``WorkShare_GCC``: the sum over sectors of ``GCCW x
    CS``, in sector order."""
    return sum(st["GCCW"][x] * CS[x] for x in SECTORS)


def r7(pr: Mapping[str, float], st: State, w: float) -> float:
    """R7: ``kR7 x clamp(ln(WS / WS_2024), -R7Lcap, R7Lcap)``; 0 until ``WS0`` is filled (step 0, where WS =
    WS_2024)."""
    w0 = st["WS0"]
    if w0 <= 0.0:
        return 0.0
    lg = math.log(max(w, 1e-12) / w0)
    return pr["kR7"] * clamp(lg, -pr["R7Lcap"], pr["R7Lcap"])


# ---- R6: the price rules ---------------------------------------------------------------------------------------------


def ceil(pr: Mapping[str, float], Anchor: float) -> float:
    """C6: the implied AI discount ``1 - Anchor`` is at most ``AIDiscCeil``."""
    return max(Anchor, 1 - pr["AIDiscCeil"])


def floor(pr: Mapping[str, float], st: State, v: str, Pe: float, PNew: Vec) -> Vec:
    """C5: each new-bid price is at least ``PriceFloor x ECost`` (``x Pe`` for effort types); none until ``ECost`` is
    filled."""
    ec = st["ECost"][v]
    if ec <= 0.0:
        return PNew
    return {k: max(PNew[k], pr["PriceFloor"] * ec * (Pe if k in EFFORT else 1.0)) for k in TYPES}


# ---- R10: attrition cost ---------------------------------------------------------------------------------------------


def vol_cell(fl: Flows, sw: Switches, u: str, l: str) -> float:
    """Voluntary exits of one unit and level: quits, leaving the field and switch-outs (a year)."""
    f = fl[u][l]
    return f["quits"] + f["leave"] + sw[u][l]["out"]


def attr(st: State, fl: Flows, sw: Switches, v: str) -> float:
    """Voluntary exits per head of vendor ``v`` (a year)."""
    us = [u for u in UNITS if EMP_OF[u] == v]
    out = sum(vol_cell(fl, sw, u, l) for u in us for l in LEVELS)
    hh = sum(st["H"][u][l] for u in us for l in LEVELS)
    return out / hh if hh > 0 else 0.0


def vol_ratio(st: State, fl: Flows, sw: Switches, v: str) -> float:
    """Voluntary exits per head over their 2024 value (1 at 2024: before ``Attr0`` is filled, this step's own rate is
    the reference)."""
    a = attr(st, fl, sw, v)
    a0 = st["Attr0"][v] if st["Attr0"][v] > 0.0 else a
    return a / a0 if a0 > 0.0 else 1.0


def r10cost(pr: Mapping[str, float], st: State, fl: Flows, sw: Switches, wage: Mat, v: str) -> float:
    """R10: ``R10rc x`` the wage of voluntary exits ``x max(0, 1 - VA_2024 / VA)`` (USD a year)."""
    a0 = st["Attr0"][v]
    a = attr(st, fl, sw, v)
    us = [u for u in UNITS if EMP_OF[u] == v]
    wout = sum(wage[u][l] * vol_cell(fl, sw, u, l) for u in us for l in LEVELS)
    frac = max(0.0, 1 - a0 / a) if (a0 > 0 and a > 0) else 0.0
    return pr["R10rc"] * wout * frac


# ---- R4: skill erosion -----------------------------------------------------------------------------------------------


def dur(pr: Mapping[str, float], st: State, hires: Mat, r: str, l: str) -> float:
    """The expected seeker spell length of a region and level: seekers over their outflows (years)."""
    hU = sum(hires[u][l] for u in UNITS if POOL[u] == r)
    U = st["U"][r][l]
    den = hU + U * pr["SeekerExitRate"]
    return U / den if den > 0 else 0.0


def r4mult(pr: Mapping[str, float], st: State, hires: Mat, r: str, l: str) -> float:
    """R4's multiplier ``(1 + a x clamp((Dur - 0.5) / 0.5, 0, 1))`` over its 2024 value; 1.0 where the region's
    strength is 0."""
    a = pr["R4aIN"] if r == "IN" else pr["R4a"]
    if a == 0.0:
        return 1.0
    D = dur(pr, st, hires, r, l)
    D0 = st["Dur0"][r][l]
    if D0 <= 0.0:
        D0 = D
    return (1 + a * clamp((D - 0.5) / 0.5, 0.0, 1.0)) / (1 + a * clamp((D0 - 0.5) / 0.5, 0.0, 1.0))


def seek_exit(pr: Mapping[str, float], st: State, r: str, l: str, base: float, m: float) -> float:
    """R4: the seeker exit ``base x m`` (``m`` from ``r4mult``), at most ``U / MinSeekTime``; ``base`` where the
    region's strength is 0."""
    a = pr["R4aIN"] if r == "IN" else pr["R4a"]
    if a == 0.0:
        return base
    return min(base * m, st["U"][r][l] / pr["MinSeekTime"])


# ---- references and signals ------------------------------------------------------------------------------------------


def pre(pr: Mapping[str, float], st: State, s: Step) -> Vec:
    """Start of ``integrate`` (pre-update state): fill the 2024 references on the first step; return each vendor's
    C4 shortfall, which ``post`` smooths into ``C4Hab``."""
    if st["WS0"] <= 0.0:
        st["WS0"] = ws(st, s.work.CS)
    sf: Vec = {}
    for v in VENDORS:
        if st["Attr0"][v] <= 0.0:
            st["Attr0"][v] = attr(st, s.exits.fl, s.switching.sw, v)
        if st["ECost"][v] <= 0.0:
            st["ECost"][v] = s.books.VB[v].CostIdx
        sf[v] = shortfall(pr, st, v)
    for r in REGIONS:
        for l in LEVELS:
            if st["Dur0"][r][l] <= 0.0:
                st["Dur0"][r][l] = dur(pr, st, s.hiring.hires, r, l)
    return sf


def post(pr: Mapping[str, float], st: State, s: Step, d: float, sf: Vec) -> None:
    """End of ``integrate``, after every other stock: advance ``VMarg``, ``ECost`` and ``C4Hab``."""
    VF, VB = s.contracts.VF, s.books.VB
    for v in VENDORS:
        st["VMarg"][v] += d * (VB[v].Margin - st["VMarg"][v]) / pr["R6MargTime"]
        st["ECost"][v] += d * (VB[v].CostIdx - st["ECost"][v]) * VF[v].ExpRate
        st["C4Hab"][v] += d * (sf[v] - st["C4Hab"][v]) / pr["C4FadeTime"]
