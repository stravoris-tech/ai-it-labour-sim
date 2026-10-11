"""S2, batched: AI capability, verification, demand growth and employer productivity by work type.

Mirrors ``aisim.scalar.capability`` expression by expression. Shapes: ``aW``, ``PAI``, ``PAI0`` ``(N, wtype)``;
``VerifNow``, ``G`` ``(N,)``; ``Pew`` ``(N, employer, wtype)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, Faults, pw

POWER_SITE = "S2 (1 - g) ** (y - 2024)"
"""Fault site: a negative base to a non-integer power, which is complex in the scalar engine (it then raises)."""


@dataclass(frozen=True, slots=True)
class Capability:
    """S2 intermediates."""

    aW: F
    VerifNow: F
    PAI: F
    PAI0: F
    G: F
    Pew: F


def capability(pr: BatchParams, st: BatchState, y: float, ai: B, faults: Faults) -> Capability:
    """S2: capability by work type and employer (see ``aisim.scalar.capability.capability``)."""
    amax, a2024, speed_up = pr.table("amax"), pr.table("a2024"), pr.table("SpeedUp")
    one_minus_g = 1 - pr["g"]
    ex = y - 2024
    if not float(ex).is_integer():
        faults.flag(POWER_SITE, one_minus_g < 0)
    decay = pw(one_minus_g, ex)[:, None]
    aW = np.maximum(0.0, amax - (amax - a2024) * decay)
    VerifNow = pr["Verif"] * pw(1 - pr["VerifDecline"], ex)
    PAI = 1 / ((1 - aW) + aW / speed_up + aW * VerifNow[:, None])
    PAI0 = 1 / ((1 - a2024) + a2024 / speed_up + a2024 * pr["Verif"][:, None])
    Aemp = st.A
    dgl = np.where(pr.dgl_is_none, pr["DemandGrowth"], pr["DemandGrowthLate"])
    LateYear = pr["LateYear"]
    G = pw(1 + pr["DemandGrowth"], np.minimum(y, LateYear) - 2024) * pw(1 + dgl, np.maximum(0.0, y - LateYear))
    A0 = pr["A0"][:, None, None]
    Ae = Aemp[:, :, None]
    Pew = np.where(
        ai[:, None, None],
        (Ae * PAI[:, None, :] + (1 - Ae)) / (A0 * PAI0[:, None, :] + (1 - A0)),
        1.0,
    )
    return Capability(aW=aW, VerifNow=VerifNow, PAI=PAI, PAI0=PAI0, G=G, Pew=Pew)
