"""S12, batched: delivery AI adoption per employer.

Mirrors ``aisim.scalar.adoption``. Every field is ``(N, employer)``. The division ``AICost2024 / AICostPerUnit`` is a
fault site: the scalar engine raises ``ZeroDivisionError`` there when ``AICostPerUnit`` is 0 (recon 03 B2), while the
array result is clamped to ``CEMax``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aisim.batch.axes import UNITS_OF_EMP
from aisim.batch.finance import VendorBook
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, Faults, clamp, group_sum, pw
from aisim.dims import EMPLOYERS

AI_COST_SITE = "S12 AICost2024 / AICostPerUnit"


@dataclass(frozen=True, slots=True)
class Adoption:
    """S12 intermediates."""

    labpb: F
    CEe: F
    brake: F
    push: F
    AdoptE: F


def adoption(
    pr: BatchParams,
    st: BatchState,
    ai: B,
    EffStaffE: F,
    LabourCost: F,
    AICostPerUnit: F,
    VB: VendorBook,
    faults: Faults,
) -> Adoption:
    """S12: delivery AI adoption per employer (see ``aisim.scalar.adoption.adoption``)."""
    Aemp = st.A
    labpb = group_sum(LabourCost, UNITS_OF_EMP) / np.maximum(EffStaffE, 1e-9)
    faults.flag(AI_COST_SITE, AICostPerUnit == 0)
    cost_ratio = (labpb / pr.fam("LabourCostPB0_", EMPLOYERS)) * (pr["AICost2024"] / AICostPerUnit)[:, None]
    CEe = clamp(pw(cost_ratio, pr["CostAdoptElast"][:, None]), pr["CEMin"][:, None], pr["CEMax"][:, None])
    one = np.ones((st.n, 2))
    brake = np.concatenate([one, 1 - pr["TMBrake"][:, None] * VB.EffortShare], axis=1)
    push = np.concatenate([one, 1 + pr["PushSens"][:, None] * VB.ShareLoss], axis=1)
    bass = (pr["p"][:, None] * pr.fam("AdoptMult_", EMPLOYERS) + pr["q"][:, None] * Aemp) * CEe * brake * push
    AdoptE = np.where(
        ai[:, None],
        np.minimum(bass * (1 - Aemp), (1 - Aemp) / pr["MinAdoptionTime"][:, None]),
        0.0,
    )
    return Adoption(labpb=labpb, CEe=CEe, brake=brake, push=push, AdoptE=AdoptE)
