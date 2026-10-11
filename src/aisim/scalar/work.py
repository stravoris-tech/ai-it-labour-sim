"""Work allocation by sector, capacity, completion and abandonment.

Prototype: ``phase7_sim.py`` S3, lines 174-193. Spec modules: 1c Work queues (implicit: each sector's backlog is held by
employers in proportion to their work shares, ``EmpShare x BL``), 3 Workforce (capacity, completion) and 1 IT work
demand (abandonment).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EMP_OF, EMPLOYERS, LEVELS, SECTORS, UNITS, VENDORS, WTYPES
from aisim.state import Mat, State, Vec


@dataclass(frozen=True, slots=True)
class Work:
    """S3 intermediates."""

    EmpShare: Mat
    BLs: Vec
    BLe: Vec
    EffE: Vec
    Pe: Vec
    EffStaffE: Vec
    CapE: Vec
    CompE: Vec
    RateE: Vec
    Comp: Mat
    Aband: Mat
    Completion: float
    EffortDone: float
    P_all: float
    CompS: Vec
    CS: Vec
    TotBL: float


def work(
    pr: Mapping[str, float], tb: Mapping[str, Mapping[str, float]], st: State, W: Mapping[str, float], Pew: Mat
) -> Work:
    """S3: who holds each sector's work, and how much of it each employer completes.

    - ``EmpShare[x][e]`` is employer ``e``'s share of sector ``x``'s work (the sourcing stocks ``IHW``, ``GCCW``,
      ``VW``). ``BLe[e]`` is the backlog it holds, and ``EffE[e]`` the same backlog in effort, deflated by ``Pew``.
    - ``Pe[e] = BLe / EffE`` is the employer's work-weighted productivity (1 with no backlog).
    - Capacity ``CapE`` is ``WorkPerPerson x Pe x`` effective staff (level-weighted headcount plus onboarding staff at
      ``OnboardProductivity``). Completion ``CompE`` is capacity, capped by clearing the backlog in
      ``MinCompletionTime``; ``RateE`` is completion per unit of backlog.
    - Each sector and work type completes ``Comp`` at its holders' rates, and abandons ``Aband`` where the rate falls
      short of ``1 / AbandonTolerance``.
    - ``P_all`` is the completion-weighted productivity, ``CompS`` and ``CS`` the completion by sector and its share
      (the base ``SectorShare`` when nothing completes).

    No loop closes here. ``Pe`` feeds B1 (productivity compression) through ``PerceivedP`` and desired headcount (S5).
    """
    IHW, GCCW, VW = st["IHW"], st["GCCW"], st["VW"]
    H, O = st["H"], st["O"]
    EmpShare = {x: {"IH": IHW[x], "GCC": GCCW[x], **{v: VW[x][v] for v in VENDORS}} for x in SECTORS}
    BL = st["BL"]
    BLs = {x: sum(BL[x][w] for w in WTYPES) for x in SECTORS}
    BLe = {e: sum(EmpShare[x][e] * BLs[x] for x in SECTORS) for e in EMPLOYERS}
    EffE = {e: sum(EmpShare[x][e] * BL[x][w] / Pew[e][w] for x in SECTORS for w in WTYPES) for e in EMPLOYERS}
    Pe = {e: (BLe[e] / EffE[e] if EffE[e] > 0 else 1.0) for e in EMPLOYERS}
    EffStaffE = {
        e: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for u in UNITS if EMP_OF[u] == e for l in LEVELS)
        for e in EMPLOYERS
    }
    CapE = {e: pr["WorkPerPerson"] * Pe[e] * EffStaffE[e] for e in EMPLOYERS}
    CompE = {e: min(CapE[e], BLe[e] / pr["MinCompletionTime"]) for e in EMPLOYERS}
    RateE = {e: (CompE[e] / BLe[e] if BLe[e] > 0 else 0.0) for e in EMPLOYERS}
    Comp = {x: {w: sum(EmpShare[x][e] * BL[x][w] * RateE[e] for e in EMPLOYERS) for w in WTYPES} for x in SECTORS}
    Aband = {
        x: {
            w: sum(EmpShare[x][e] * max(0.0, BL[x][w] * (1 - RateE[e] * pr["AbandonTolerance"])) for e in EMPLOYERS)
            / pr["AbandonTime"]
            for w in WTYPES
        }
        for x in SECTORS
    }
    Completion = sum(CompE.values())
    EffortDone = sum(CompE[e] / Pe[e] for e in EMPLOYERS)
    P_all = Completion / EffortDone if EffortDone > 0 else 1.0
    CompS = {x: sum(Comp[x][w] for w in WTYPES) for x in SECTORS}
    CS = {x: (CompS[x] / Completion if Completion > 0 else tb["SectorShare"][x]) for x in SECTORS}
    TotBL = sum(BLs.values())
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
