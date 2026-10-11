"""S3, batched: work allocation by sector, capacity, completion and abandonment.

Mirrors ``aisim.scalar.work``. Shapes: ``EmpShare`` ``(N, sector, employer)``; ``BLs``, ``CompS``, ``CS``
``(N, sector)``; ``BLe``, ``EffE``, ``Pe``, ``EffStaffE``, ``CapE``, ``CompE``, ``RateE`` ``(N, employer)``; ``Comp``,
``Aband`` ``(N, sector, wtype)``; ``Completion``, ``EffortDone``, ``P_all``, ``TotBL`` ``(N,)``. Sums run in the
scalar engine's term order (``EffE`` sector-major over 42 terms), compensated as ``sum()`` is (``util.csum``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aisim.batch.axes import UNITS_OF_EMP
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import F, csum_axis, group_sum_ul


@dataclass(frozen=True, slots=True)
class Work:
    """S3 intermediates."""

    EmpShare: F
    BLs: F
    BLe: F
    EffE: F
    Pe: F
    EffStaffE: F
    CapE: F
    CompE: F
    RateE: F
    Comp: F
    Aband: F
    Completion: F
    EffortDone: F
    P_all: F
    CompS: F
    CS: F
    TotBL: F


def work(pr: BatchParams, st: BatchState, W: F, Pew: F) -> Work:
    """S3: who holds each sector's work, and how much of it each employer completes (see ``aisim.scalar.work``)."""
    n = st.n
    EmpShare = np.concatenate([st.IHW[:, :, None], st.GCCW[:, :, None], st.VW], axis=2)
    BL = st.BL
    BLs = csum_axis(BL, 2)
    BLe = csum_axis(EmpShare * BLs[:, :, None], 1)
    eff_terms = (EmpShare[:, :, None, :] * BL[:, :, :, None]) / np.swapaxes(Pew, 1, 2)[:, None, :, :]
    EffE = csum_axis(eff_terms.reshape(n, -1, eff_terms.shape[3]), 1)
    Pe = np.where(EffE > 0, BLe / EffE, 1.0)
    staff = W[:, None, :] * (st.H + pr["OnboardProductivity"][:, None, None] * st.O)
    EffStaffE = group_sum_ul(staff, UNITS_OF_EMP)
    CapE = pr["WorkPerPerson"][:, None] * Pe * EffStaffE
    CompE = np.minimum(CapE, BLe / pr["MinCompletionTime"][:, None])
    RateE = np.where(BLe > 0, CompE / BLe, 0.0)
    Comp = csum_axis(EmpShare[:, :, None, :] * BL[:, :, :, None] * RateE[:, None, None, :], 3)
    kept = np.maximum(
        0.0, BL[:, :, :, None] * (1 - RateE[:, None, None, :] * pr["AbandonTolerance"][:, None, None, None])
    )
    Aband = csum_axis(EmpShare[:, :, None, :] * kept, 3) / pr["AbandonTime"][:, None, None]
    Completion = csum_axis(CompE, 1)
    EffortDone = csum_axis(CompE / Pe, 1)
    P_all = np.where(EffortDone > 0, Completion / EffortDone, 1.0)
    CompS = csum_axis(Comp, 2)
    CS = np.where(Completion[:, None] > 0, CompS / Completion[:, None], pr.table("SectorShare"))
    TotBL = csum_axis(BLs, 1)
    return Work(
        EmpShare=EmpShare,
        BLs=BLs,
        BLe=BLe,
        EffE=EffE,
        Pe=Pe,
        EffStaffE=EffStaffE,
        CapE=CapE,
        CompE=CompE,
        RateE=RateE,
        Comp=Comp,
        Aband=Aband,
        Completion=Completion,
        EffortDone=EffortDone,
        P_all=P_all,
        CompS=CompS,
        CS=CS,
        TotBL=TotBL,
    )
