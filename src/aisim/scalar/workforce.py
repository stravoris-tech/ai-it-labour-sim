"""Level mix, visa lever, unit split, desired headcount, vacancies and promotions.

Prototype: ``phase7_sim.py`` S4 (lines 194-200), S5 (lines 201-209) and S7 (lines 219-231). Spec modules:
3 Workforce (level mix, junior cut, desired headcount), 9 Visa policy (``VisaTight``, onsite and visa mix) and
3b Hiring pipeline (vacancies, cancellations, promotions).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EMP_OF, EMPLOYERS, LEVELS, UNITS, VENDORS
from aisim.scalar import loops
from aisim.state import Mat, State, Vec
from aisim.util import clamp, ramp


@dataclass(frozen=True, slots=True)
class LevelMix:
    """S4 intermediates."""

    ShareL: Mat
    denomE: Vec


@dataclass(frozen=True, slots=True)
class Staffing:
    """S5 intermediates."""

    VisaTight: float
    dTight: float
    OnsiteShare: float
    VisaMix: float
    UnitIn: Vec
    DesiredE: Vec
    Desired: Mat


@dataclass(frozen=True, slots=True)
class Vacancies:
    """S7 intermediates."""

    surplus: Mat
    cancel: Mat
    avail: Mat
    promo: Mat


def level_mix(pr: Mapping[str, float], st: State, W: Mapping[str, float], ai_on: bool) -> LevelMix:
    """S4: level mix per employer.

    The junior share ``ShareL[e]["J"]`` falls from ``Share0_J`` by ``JuniorCut`` per unit of adoption above the 2024
    level ``A0`` (floored at 5% of ``Share0_J``; no cut with AI off). Mid and senior shares keep their 2024 ratio.
    ``denomE`` is the level-weighted staff per head. This closes the junior-hiring half of B4 (talent pipeline gap).
    """
    Aemp = st["A"]
    ShareL: Mat = {}
    denomE: Vec = {}
    for e in EMPLOYERS:
        sJ = pr["Share0_J"] * max(0.05, 1 - pr["JuniorCut"] * (max(0.0, Aemp[e] - pr["A0"]) if ai_on else 0.0))
        rest0 = pr["Share0_M"] + pr["Share0_S"]
        ShareL[e] = {"J": sJ, "M": pr["Share0_M"] * (1 - sJ) / rest0, "S": pr["Share0_S"] * (1 - sJ) / rest0}
        denomE[e] = sum(ShareL[e][l] * W[l] for l in LEVELS)
    return LevelMix(ShareL=ShareL, denomE=denomE)


def staffing(pr: Mapping[str, float], st: State, y: float, BLe: Vec, mix: LevelMix) -> Staffing:
    """S5: visa lever, unit split inside employers and desired headcount.

    - ``VisaTight`` ramps from ``VTBase`` to ``VTEnd`` over ``VTRampStart``-``VTRampEnd``.
    - Perceived tightness above ``VTBase`` (``dTight``) shifts OIT's work offshore (``OnsiteShare``) and its onsite
      work from visa to local staff (``VisaMix``): loop B7 (local hiring substitution). GSI splits by
      ``GSIOffshore``. ``UnitIn`` is each unit's share of its employer's work.
    - ``DesiredE``: the staff needed to clear the held backlog in ``TargetClearanceTime`` at perceived productivity.
      It is split to units by ``UnitIn`` and to levels by the level mix (``Desired``). Higher perceived productivity
      means fewer heads: loop B1 (productivity compression).
    - R6 C2 capacity exit (``R6e``, off at 0): a vendor below ``R6Theta`` in relative viability cuts its desired
      staff (``aisim.scalar.loops.cut``); the existing openings and layoffs logic executes the cut.
    """
    ShareL, denomE = mix.ShareL, mix.denomE
    VisaTight = ramp(y, pr["VTRampStart"], pr["VTRampEnd"], pr["VTBase"], pr["VTEnd"])
    dTight = st["TightPerc"] - pr["VTBase"]
    OnsiteShare = clamp(pr["OnsiteShare0"] * (1 - pr["OffshoreShiftSens"] * dTight), 0.0, 1.0)
    VisaMix = clamp(pr["VisaMix0"] * (1 - pr["VisaMixSens"] * dTight), 0.0, 1.0)
    UnitIn = {
        "IH": 1.0,
        "GCC": 1.0,
        "VI": 1 - OnsiteShare,
        "OV": OnsiteShare * VisaMix,
        "OL": OnsiteShare * (1 - VisaMix),
        "SI_IN": pr["GSIOffshore"],
        "SI_ON": 1 - pr["GSIOffshore"],
        "BQ": 1.0,
    }
    PerceivedP = st["PerceivedP"]
    DesiredE = {e: BLe[e] / (pr["TargetClearanceTime"] * pr["WorkPerPerson"] * PerceivedP[e]) for e in EMPLOYERS}
    if pr["R6e"] != 0.0:  # R6 C2: capacity exit
        for v in VENDORS:
            DesiredE[v] = DesiredE[v] * (1 - loops.cut(pr, st, v))
    Desired = {
        u: {l: DesiredE[EMP_OF[u]] * UnitIn[u] * ShareL[EMP_OF[u]][l] / denomE[EMP_OF[u]] for l in LEVELS}
        for u in UNITS
    }
    return Staffing(
        VisaTight=VisaTight,
        dTight=dTight,
        OnsiteShare=OnsiteShare,
        VisaMix=VisaMix,
        UnitIn=UnitIn,
        DesiredE=DesiredE,
        Desired=Desired,
    )


def vacancies(pr: Mapping[str, float], st: State, Desired: Mat) -> Vacancies:
    """S7: vacancies and promotions.

    - ``surplus`` is staff (headcount plus onboarding) minus desired staff.
    - Vacancies beyond the shortfall are cancelled over ``CancelTime`` (all vacancies when in surplus), but no faster
      than they could be filled (``MinFillTime``). ``avail`` is the fill capacity left after cancellations.
    - Promotions into mid and senior roles fill vacancies from the level below, at the aging rate (``TimeInJunior``,
      ``TimeInMid``), within ``PromoFillTime`` and the available fill capacity: the aging chain of B4.

    Vacancies are the first stage of loop B13 (hiring delay).
    """
    H, O, V = st["H"], st["O"], st["V"]
    surplus: Mat = {}
    cancel: Mat = {}
    avail: Mat = {}
    for u in UNITS:
        surplus[u], cancel[u], avail[u] = {}, {}, {}
        for l in LEVELS:
            sp = H[u][l] + O[u][l] - Desired[u][l]
            cancel_rate = (max(0.0, V[u][l] + sp) if sp <= 0 else V[u][l]) / pr["CancelTime"]
            cap = V[u][l] / pr["MinFillTime"]
            surplus[u][l] = sp
            cancel[u][l] = min(cancel_rate, cap)
            avail[u][l] = max(0.0, cap - cancel[u][l])
    promo = {
        u: {
            "J": 0.0,
            "M": min(H[u]["J"] / pr["TimeInJunior"], V[u]["M"] / pr["PromoFillTime"], avail[u]["M"]),
            "S": min(H[u]["M"] / pr["TimeInMid"], V[u]["S"] / pr["PromoFillTime"], avail[u]["S"]),
        }
        for u in UNITS
    }
    return Vacancies(surplus=surplus, cancel=cancel, avail=avail, promo=promo)
