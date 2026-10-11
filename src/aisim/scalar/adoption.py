"""Delivery AI adoption per employer.

Prototype: ``phase7_sim.py`` S12, lines 415-423. Spec module: 6 Delivery AI.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EMP_OF, EMPLOYERS, UNITS, VENDORS
from aisim.scalar.finance import VendorBook
from aisim.state import State, Vec
from aisim.util import clamp


@dataclass(frozen=True, slots=True)
class Adoption:
    """S12 intermediates."""

    labpb: Vec
    CEe: Vec
    brake: Vec
    push: Vec
    AdoptE: Vec


def adoption(
    pr: Mapping[str, float],
    st: State,
    ai_on: bool,
    EffStaffE: Vec,
    LabourCost: Vec,
    AICostPerUnit: float,
    VB: Mapping[str, VendorBook],
) -> Adoption:
    """S12: delivery AI adoption per employer (Bass diffusion).

    - Cost effect ``CEe``: labour cost per unit of effective staff over its 2024 level, times AI cost relative to
      2024, to the power ``CostAdoptElast``, within ``CEMin``-``CEMax``. Dearer labour or cheaper AI speeds adoption:
      loop R5 (shortage accelerates AI).
    - Vendors brake adoption by their effort-billed share (``TMBrake``): loop B2 (T&M paradox). Share loss pushes
      them to adopt faster (``PushSens``).
    - ``AdoptE`` is the Bass rate ``(p x AdoptMult + q x A) x (1 - A)`` with these multipliers, no faster than
      closing the gap to 1 in ``MinAdoptionTime``. Zero with AI off.
    """
    Aemp = st["A"]
    labpb: Vec = {}
    CEe: Vec = {}
    brake: Vec = {}
    push: Vec = {}
    AdoptE: Vec = {}
    for e in EMPLOYERS:
        labpb[e] = sum(LabourCost[u] for u in UNITS if EMP_OF[u] == e) / max(EffStaffE[e], 1e-9)
        CEe[e] = clamp(
            ((labpb[e] / pr["LabourCostPB0_" + e]) * (pr["AICost2024"] / AICostPerUnit)) ** pr["CostAdoptElast"],
            pr["CEMin"],
            pr["CEMax"],
        )
        brake[e] = (1 - pr["TMBrake"] * VB[e].EffortShare) if e in VENDORS else 1.0
        push[e] = (1 + pr["PushSens"] * VB[e].ShareLoss) if e in VENDORS else 1.0
        Ae = Aemp[e]
        AdoptE[e] = (
            min(
                (pr["p"] * pr["AdoptMult_" + e] + pr["q"] * Ae) * CEe[e] * brake[e] * push[e] * (1 - Ae),
                (1 - Ae) / pr["MinAdoptionTime"],
            )
            if ai_on
            else 0.0
        )
    return Adoption(labpb=labpb, CEe=CEe, brake=brake, push=push, AdoptE=AdoptE)
