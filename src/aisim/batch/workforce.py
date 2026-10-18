"""S4, S5 and S7, batched: level mix, visa lever, unit split, desired headcount, vacancies and promotions.

Mirrors ``aisim.scalar.workforce``. Shapes: ``ShareL`` ``(N, employer, level)``; ``denomE``, ``DesiredE``
``(N, employer)``; ``VisaTight``, ``dTight``, ``OnsiteShare``, ``VisaMix`` ``(N,)``; ``UnitIn`` ``(N, unit)``;
``Desired``, ``surplus``, ``cancel``, ``avail``, ``promo`` ``(N, unit, level)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aisim.batch import loops
from aisim.batch.axes import EMP_OF_IX, VENDOR_EMP_IX
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, clamp, csum_axis, ramp


@dataclass(frozen=True, slots=True)
class LevelMix:
    """S4 intermediates."""

    ShareL: F
    denomE: F


@dataclass(frozen=True, slots=True)
class Staffing:
    """S5 intermediates."""

    VisaTight: F
    dTight: F
    OnsiteShare: F
    VisaMix: F
    UnitIn: F
    DesiredE: F
    Desired: F


@dataclass(frozen=True, slots=True)
class Vacancies:
    """S7 intermediates."""

    surplus: F
    cancel: F
    avail: F
    promo: F


def level_mix(pr: BatchParams, st: BatchState, W: F, ai: B) -> LevelMix:
    """S4: level mix per employer (see ``aisim.scalar.workforce.level_mix``)."""
    Aemp = st.A
    above = np.where(ai[:, None], np.maximum(0.0, Aemp - pr["A0"][:, None]), 0.0)
    sJ = pr["Share0_J"][:, None] * np.maximum(0.05, 1 - pr["JuniorCut"][:, None] * above)
    rest0 = (pr["Share0_M"] + pr["Share0_S"])[:, None]
    sM = pr["Share0_M"][:, None] * (1 - sJ) / rest0
    sS = pr["Share0_S"][:, None] * (1 - sJ) / rest0
    ShareL = np.stack([sJ, sM, sS], axis=2)
    denomE = csum_axis(ShareL * W[:, None, :], 2)
    return LevelMix(ShareL=ShareL, denomE=denomE)


def staffing(pr: BatchParams, st: BatchState, y: float, BLe: F, mix: LevelMix) -> Staffing:
    """S5: visa lever, unit split inside employers and desired headcount (see ``aisim.scalar.workforce.staffing``)."""
    ShareL, denomE = mix.ShareL, mix.denomE
    VisaTight = ramp(y, pr["VTRampStart"], pr["VTRampEnd"], pr["VTBase"], pr["VTEnd"])
    dTight = st.TightPerc - pr["VTBase"]
    OnsiteShare = clamp(pr["OnsiteShare0"] * (1 - pr["OffshoreShiftSens"] * dTight), 0.0, 1.0)
    VisaMix = clamp(pr["VisaMix0"] * (1 - pr["VisaMixSens"] * dTight), 0.0, 1.0)
    one = np.ones_like(OnsiteShare)
    UnitIn = np.stack(
        [
            one,
            one,
            1 - OnsiteShare,
            OnsiteShare * VisaMix,
            OnsiteShare * (1 - VisaMix),
            pr["GSIOffshore"] + 0.0,
            1 - pr["GSIOffshore"],
            one,
        ],
        axis=1,
    )
    PerceivedP = st.PerceivedP
    DesiredE = BLe / ((pr["TargetClearanceTime"] * pr["WorkPerPerson"])[:, None] * PerceivedP)
    if np.any(pr["R6e"] != 0.0):  # R6 C2: capacity exit
        cut = DesiredE.copy()
        cut[:, VENDOR_EMP_IX] = DesiredE[:, VENDOR_EMP_IX] * (1 - loops.cut(pr, st))
        DesiredE = np.where((pr["R6e"] != 0.0)[:, None], cut, DesiredE)
    Desired = (
        DesiredE[:, EMP_OF_IX][:, :, None]
        * UnitIn[:, :, None]
        * ShareL[:, EMP_OF_IX, :]
        / denomE[:, EMP_OF_IX][:, :, None]
    )
    return Staffing(
        VisaTight=VisaTight,
        dTight=dTight,
        OnsiteShare=OnsiteShare,
        VisaMix=VisaMix,
        UnitIn=UnitIn,
        DesiredE=DesiredE,
        Desired=Desired,
    )


def vacancies(pr: BatchParams, st: BatchState, Desired: F) -> Vacancies:
    """S7: vacancies and promotions (see ``aisim.scalar.workforce.vacancies``)."""
    H, O, V = st.H, st.O, st.V
    sp = H + O - Desired
    cancel_rate = np.where(sp <= 0, np.maximum(0.0, V + sp), V) / pr["CancelTime"][:, None, None]
    cap = V / pr["MinFillTime"][:, None, None]
    cancel = np.minimum(cancel_rate, cap)
    avail = np.maximum(0.0, cap - cancel)
    pft = pr["PromoFillTime"][:, None]
    promo_M = np.minimum(np.minimum(H[:, :, 0] / pr["TimeInJunior"][:, None], V[:, :, 1] / pft), avail[:, :, 1])
    promo_S = np.minimum(np.minimum(H[:, :, 1] / pr["TimeInMid"][:, None], V[:, :, 2] / pft), avail[:, :, 2])
    promo = np.stack([np.zeros_like(promo_M), promo_M, promo_S], axis=2)
    return Vacancies(surplus=sp, cancel=cancel, avail=avail, promo=promo)
