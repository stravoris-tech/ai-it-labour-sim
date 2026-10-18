"""Regional unemployment, switching, visa flows, exits, openings and layoffs, matching and hires, time to fill, external
entry, pools and enrolment.

Prototype: ``phase7_sim.py`` S6 (lines 210-218) and S8 (lines 232-317), split as recon B1 does: 8a switching (232-251),
8b visa expiry, conversion and cap (252-254), 8c exits, openings and layoffs (255-271), 8d matching and hires (272-291),
8e time to fill and external entry (292-304), 8f pool flows, enrolment and graduation (305-317). Spec modules: 4 Labour
market (unemployment, pools, enrolment, external entry), 3b Hiring pipeline (switching, matching, time to fill),
3 Workforce (exits, layoffs) and 9 Visa policy (expiry, conversion, cap).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypedDict

from aisim.dims import LEVELS, POOL, REGIONS, SWITCHERS, UNITS
from aisim.scalar import loops
from aisim.state import Mat, State, Vec
from aisim.util import clamp

SwitchFlows = TypedDict("SwitchFlows", {"in": float, "out": float})
"""Switching flows of one unit and level: in from and out to other units in the same pool."""


class LevelFlows(TypedDict):
    """Outflows, openings, layoffs and onboarding of one unit and level (a year)."""

    quits: float
    leave: float
    retire: float
    promo_out: float
    openings: float
    layoffs: float
    onboard: float


class PoolFlows(TypedDict):
    """Flows out of the recovering (``R``) and seeking (``U``) pools of one region and level (a year)."""

    rec_to_seek: float
    rec_to_left: float
    seek_exit: float
    rec_retire: float
    seek_retire: float


@dataclass(frozen=True, slots=True)
class Unemployment:
    """S6 intermediates."""

    UnempRate: Vec
    LeaveEffect: Vec
    EnrolEffect: Vec


@dataclass(frozen=True, slots=True)
class Switching:
    """S8a intermediates."""

    sw: dict[str, dict[str, SwitchFlows]]


@dataclass(frozen=True, slots=True)
class VisaFlows:
    """S8b intermediates."""

    expiry: Vec
    conv: Vec
    VisaCap: float


@dataclass(frozen=True, slots=True)
class Exits:
    """S8c intermediates."""

    fl: dict[str, dict[str, LevelFlows]]


@dataclass(frozen=True, slots=True)
class Hiring:
    """S8d intermediates."""

    hires: Mat


@dataclass(frozen=True, slots=True)
class TimeToFill:
    """S8e intermediates."""

    TTFr: Mat
    ext: Mat


@dataclass(frozen=True, slots=True)
class Pools:
    """S8f intermediates."""

    pool: dict[str, dict[str, PoolFlows]]
    Enrol: Vec
    Grad: Vec
    TTFratio: Vec


def unemployment(pr: Mapping[str, float], st: State) -> Unemployment:
    """S6: regional unemployment.

    - ``UnempRate[r]`` is recovering plus seeking people over the labour force of the pool.
    - ``LeaveEffect`` scales leaving the field with perceived (short) unemployment over its normal rate, within
      0.5-3. Longer unemployment drives exits: loop R4 (skill erosion), as far as the code models it.
    - ``EnrolEffect`` cuts enrolment as perceived (long) unemployment rises above normal, within 0.4-1.3: loop B5
      (discouraged entry), closed through ``Enrol`` in S8f.
    """
    H, O, R, U = st["H"], st["O"], st["R"], st["U"]
    UnempRate: Vec = {}
    LeaveEffect: Vec = {}
    EnrolEffect: Vec = {}
    for r in REGIONS:
        unemp = sum(R[r][l] + U[r][l] for l in LEVELS)
        emp = sum(H[u][l] + O[u][l] for u in UNITS if POOL[u] == r for l in LEVELS)
        UnempRate[r] = unemp / (emp + unemp)
        norm = pr["NormalUnempRate_" + r]
        LeaveEffect[r] = clamp(st["PUS"][r] / norm, 0.5, 3.0)
        EnrolEffect[r] = clamp(1 - pr["EnrolSensitivity"] * (st["PUL"][r] / norm - 1), 0.4, 1.3)
    return Unemployment(UnempRate=UnempRate, LeaveEffect=LeaveEffect, EnrolEffect=EnrolEffect)


def switching(pr: Mapping[str, float], st: State, avail: Mat, promo: Mat) -> Switching:
    """S8a: job switching between any two units in the same labour pool (visa holders excluded).

    Staff at level ``l`` of ``src`` switch to ``dst`` at ``SwitchRate``, scaled by the relative wage
    (``Wage_* x WI``) to the power ``SwitchElasticity`` (capped at ``SwitchMax``) and spread over the other units in
    proportion to their vacancies. Each destination's inflow is scaled down to its room (fill capacity left after
    promotions). The wage pull is the poaching half of R10 (talent poaching); the code does not close the loop
    back to vendor bids (recon H).
    """
    H, V, WI = st["H"], st["V"], st["WI"]
    sw: dict[str, dict[str, SwitchFlows]] = {u: {l: {"in": 0.0, "out": 0.0} for l in LEVELS} for u in UNITS}
    for r in REGIONS:
        switchers = [u for u in SWITCHERS if POOL[u] == r]
        for l in LEVELS:
            raw: dict[tuple[str, str], float] = {}
            for src in switchers:
                others = [d_ for d_ in switchers if d_ != src]
                vac_others = sum(V[d_][l] for d_ in others)
                for dst in others:
                    gw = min(
                        pr["SwitchMax"],
                        ((pr["Wage_" + dst] * WI[dst]) / (pr["Wage_" + src] * WI[src])) ** pr["SwitchElasticity"],
                    )
                    raw[(src, dst)] = (
                        H[src][l] * pr["SwitchRate"] * gw * V[dst][l] / vac_others if vac_others > 0 else 0.0
                    )
            for dst in switchers:
                inflow = sum(raw[(src, dst)] for src in switchers if src != dst)
                switch_room = max(0.0, avail[dst][l] - promo[dst][l])
                scale = min(1.0, switch_room / inflow) if inflow > 0 else 0.0
                for src in switchers:
                    if src != dst:
                        flow = raw[(src, dst)] * scale
                        sw[dst][l]["in"] += flow
                        sw[src][l]["out"] += flow
    return Switching(sw=sw)


def visa_flows(pr: Mapping[str, float], st: State, VisaTight: float, G: float) -> VisaFlows:
    """S8b: visa expiry, conversion and the visa cap.

    Visa holders (OV) leave at the end of ``VisaTenure`` into the India seeker pool, and convert to local onshore
    staff (OL) at ``ConvRate``, reduced by tightness. The cap on OV hires is ``BaseVisaCap x (1 - VisaTight)``,
    scaled by ``G`` only under the calibration switch ``Burn``.
    """
    H = st["H"]
    expiry = {l: H["OV"][l] / pr["VisaTenure"] for l in LEVELS}
    conv = {l: H["OV"][l] * pr["ConvRate"] * (1 - VisaTight) for l in LEVELS}
    VisaCap = pr["BaseVisaCap"] * (1 - VisaTight) * (G if pr["Burn"] >= 0.5 else 1.0)
    return VisaFlows(expiry=expiry, conv=conv, VisaCap=VisaCap)


def exits(
    pr: Mapping[str, float], st: State, surplus: Mat, promo: Mat, sw: dict[str, dict[str, SwitchFlows]], visa: VisaFlows
) -> Exits:
    """S8c: exits, openings and layoffs.

    - Quits, leaving the field and senior retirement are fixed rates on headcount. Net loss adds promotions out,
      switching out and (for OV) visa expiry and conversion.
    - In shortfall, new openings replace the net loss plus the shortfall not already covered by vacancies, over
      ``HireAdjTime``. In surplus there are no openings, and layoffs remove the surplus over ``LayoffAdjTime`` net of
      attrition, no faster than ``MinLayoffTime`` allows.
    - With the extension ``OpeningsContinuous`` on (``>= 0.5``), openings follow the shortfall formula for every
      surplus, so they taper to 0 as overstaffing grows instead of dropping to 0 at the sign change. Layoffs are
      unchanged.
    - Onboarding staff become productive over ``OnboardTime``.
    """
    H, O, V = st["H"], st["O"], st["V"]
    expiry, conv = visa.expiry, visa.conv
    fl: dict[str, dict[str, LevelFlows]] = {u: {} for u in UNITS}
    for u in UNITS:
        for l in LEVELS:
            quits = H[u][l] * pr["QuitRate_" + l]
            leave = H[u][l] * pr["LeaveITRate_" + l]
            retire = H[u][l] * pr["RetireRate_S"] if l == "S" else 0.0
            promo_out = promo[u]["M"] if l == "J" else (promo[u]["S"] if l == "M" else 0.0)
            visa_out = (expiry[l] + conv[l]) if u == "OV" else 0.0
            netloss = quits + leave + retire + promo_out + sw[u][l]["out"] + visa_out
            sp = surplus[u][l]
            if pr["OpeningsContinuous"] >= 0.5:
                openings = max(0.0, netloss + (-sp - V[u][l]) / pr["HireAdjTime"])
                if sp <= 0:
                    layoffs = 0.0
                else:
                    layoffs = min(max(0.0, sp / pr["LayoffAdjTime"] - netloss), H[u][l] / pr["MinLayoffTime"])
            elif sp <= 0:
                openings = max(0.0, netloss + (-sp - V[u][l]) / pr["HireAdjTime"])
                layoffs = 0.0
            else:
                openings = 0.0
                layoffs = min(max(0.0, sp / pr["LayoffAdjTime"] - netloss), H[u][l] / pr["MinLayoffTime"])
            fl[u][l] = LevelFlows(
                quits=quits,
                leave=leave,
                retire=retire,
                promo_out=promo_out,
                openings=openings,
                layoffs=layoffs,
                onboard=O[u][l] / pr["OnboardTime"],
            )
    return Exits(fl=fl)


def hiring(
    pr: Mapping[str, float],
    st: State,
    avail: Mat,
    promo: Mat,
    sw: dict[str, dict[str, SwitchFlows]],
    VisaCap: float,
) -> Hiring:
    """S8d: matching and hires.

    - Per pool and level, a matching function ``m x U^alpha x V^(1 - alpha)`` of seekers and vacancies gives the
      matches, spread over units by their vacancies and capped by each unit's room (fill capacity left after
      promotions and switching in).
    - Total hires cannot drain the seeker pool faster than ``MinFillTime``. OV hires are scaled down to the visa cap.

    Hires close loop B13 (hiring delay) through onboarding.
    """
    V, U = st["V"], st["U"]
    hires = {u: {l: 0.0 for l in LEVELS} for u in UNITS}
    for r in REGIONS:
        pool_units = [u for u in UNITS if POOL[u] == r]
        for l in LEVELS:
            vac_pool = sum(V[u][l] for u in pool_units)
            if vac_pool <= 0 or U[r][l] <= 0:
                continue
            match = pr["m"] * U[r][l] ** pr["alpha"] * vac_pool ** (1 - pr["alpha"])
            for u in pool_units:
                hire_room = max(0.0, avail[u][l] - promo[u][l] - sw[u][l]["in"])
                hires[u][l] = min(match * V[u][l] / vac_pool, hire_room)
            total = sum(hires[u][l] for u in pool_units)
            capU = U[r][l] / pr["MinFillTime"]
            if total > capU:
                for u in pool_units:
                    hires[u][l] *= capU / total
    ov_tot = sum(hires["OV"][l] for l in LEVELS)
    if ov_tot > VisaCap:
        for l in LEVELS:
            hires["OV"][l] *= VisaCap / ov_tot
    return Hiring(hires=hires)


def time_to_fill(
    pr: Mapping[str, float], st: State, hires: Mat, promo: Mat, sw: dict[str, dict[str, SwitchFlows]]
) -> TimeToFill:
    """S8e: time to fill and external entry.

    - ``TTFr[r][l]`` is the pool's vacancies over its fills (hires, promotions and switches in; at least 1 a year).
    - When time to fill exceeds its normal value, experienced people enter from outside IT at ``ExtEntryRate`` of
      headcount, scaled by the excess (capped at ``ExtEntryMax``). Juniors do not enter this way.
    """
    H, V = st["H"], st["V"]
    TTFr: Mat = {}
    ext: Mat = {}
    for r in REGIONS:
        pool_units = [u for u in UNITS if POOL[u] == r]
        TTFr[r], ext[r] = {}, {}
        for l in LEVELS:
            vs = sum(V[u][l] for u in pool_units)
            fills = sum(hires[u][l] + promo[u][l] + sw[u][l]["in"] for u in pool_units)
            TTFr[r][l] = vs / max(fills, 1.0)
            if l == "J":
                ext[r][l] = 0.0
            else:
                hsum = sum(H[u][l] for u in pool_units)
                ext[r][l] = (
                    pr["ExtEntryRate_" + l]
                    * hsum
                    * clamp(TTFr[r][l] / pr[f"NormalTTF_{r}_{l}"] - 1, 0.0, pr["ExtEntryMax"])
                )
    return TimeToFill(TTFr=TTFr, ext=ext)


def pools(pr: Mapping[str, float], st: State, G: float, unemp: Unemployment, TTFr: Mat, hires: Mat) -> Pools:
    """S8f: pool flows, enrolment and graduation.

    - The recently laid off recover over ``RecoveryTime``; a fraction (``BaseLeaveFrac`` scaled by ``LeaveEffect``, at
      most 0.9) leaves the field, the rest seek work. Seekers exit at ``SeekerExitRate x LeaveEffect``; seniors in both
      pools retire.
    - Enrolment is ``BaseEnrolment x G x EnrolEffect``: loop B5 (discouraged entry). Students graduate after
      ``StudyTime`` into the junior seeker pool.
    - ``TTFratio`` is the mid-level time to fill over its normal value.
    - R4 skill erosion (``R4a`` onshore, ``R4aIN`` India, off at 0): the seeker exit rises with the spell length
      over its 2024 value, capped at ``U / MinSeekTime`` (``aisim.scalar.loops.seek_exit``).
    """
    R, U = st["R"], st["U"]
    LeaveEffect = unemp.LeaveEffect
    pool: dict[str, dict[str, PoolFlows]] = {r: {} for r in REGIONS}
    for r in REGIONS:
        for l in LEVELS:
            rec_out = R[r][l] / pr["RecoveryTime"]
            lf = clamp(pr["BaseLeaveFrac_" + l] * LeaveEffect[r], 0.0, 0.9)
            pool[r][l] = PoolFlows(
                rec_to_seek=rec_out * (1 - lf),
                rec_to_left=rec_out * lf,
                seek_exit=(  # R4: skill erosion
                    loops.seek_exit(pr, st, hires, r, l, U[r][l] * pr["SeekerExitRate"] * LeaveEffect[r])
                    if (pr["R4a"] != 0.0 or pr["R4aIN"] != 0.0)
                    else U[r][l] * pr["SeekerExitRate"] * LeaveEffect[r]
                ),
                rec_retire=R[r][l] * pr["RetireRate_S"] if l == "S" else 0.0,
                seek_retire=U[r][l] * pr["RetireRate_S"] if l == "S" else 0.0,
            )
    Enrol = {r: pr["BaseEnrolment_" + r] * G * unemp.EnrolEffect[r] for r in REGIONS}
    Grad = {r: st["Pipeline"][r] / pr["StudyTime"] for r in REGIONS}
    TTFratio = {r: TTFr[r]["M"] / pr[f"NormalTTF_{r}_M"] for r in REGIONS}
    return Pools(pool=pool, Enrol=Enrol, Grad=Grad, TTFratio=TTFratio)
