"""S13a and S13c, batched: consumer drivers, consumer AI, LOB, apps, seats, credits, cloud, budget, approval and demand.

Mirrors ``aisim.scalar.consumer``. ``ConsumerDrivers`` fields are ``(N,)``; the per-sector dict of ``SectorConsumer``
becomes one dataclass of ``(N, sector)`` arrays; ``Demand`` is ``(N, sector, wtype)`` and ``DemandTot`` ``(N,)``. The
division ``CreditCost2024 / CreditCostPB`` (S13a) is a fault site (recon 03 B2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from aisim.batch.axes import UNIT_IX, WT_IX
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, Faults, clamp, csum, csum_axis, pw, ramp
from aisim.dims import LEVELS, SECTORS
from aisim.params import Reanchor

CREDIT_COST_SITE = "S13a CreditCost2024 / CreditCostPB"


@dataclass(frozen=True, slots=True)
class ConsumerDrivers:
    """S13a intermediates."""

    LOBAuto: F
    CreditCostPB: F
    CEc: F
    RegRamp: F
    CyberMult: F
    Att: F
    AttAdopt: F
    CostIdx6: F
    Jev: F
    ConsIT: F
    BudgetGrowth: F
    CloudPB: F
    GCCAppeal: F


@dataclass(frozen=True, slots=True)
class SectorConsumer:
    """S13c intermediates of every sector (the prototype's ``cons``)."""

    AdoptC: F
    LOBTarget: F
    AgentWork: F
    CreditSpend: F
    NetSavings: F
    NewApps: F
    Retire: F
    """Applications retired a year (not people retiring)."""
    Seats: F
    SeatSpend: F
    CloudSpend: F
    Committed: F
    Budget: F
    Approval: F
    RegDrag: F
    AIBuild: F
    """AI build demand in units of work a year (``AIBuild x base``)."""


@dataclass(frozen=True, slots=True)
class Consumer:
    """S13c intermediates."""

    cons: SectorConsumer
    Demand: F
    DemandTot: F


def drivers(
    pr: BatchParams,
    st: BatchState,
    y: float,
    ai: B,
    G: F,
    Completion: F,
    P_all: F,
    AIShockNow: F,
    ServicesSpend: F,
    faults: Faults,
    *,
    reanchor: Reanchor | None = None,
    nz: Mapping[str, F] | None = None,
) -> ConsumerDrivers:
    """S13a: exogenous consumer drivers and aggregates (see ``aisim.scalar.consumer.drivers``)."""
    H = st.H
    ex = y - 2024
    aL_max = pr["aL_max"]
    LOBAuto = np.maximum(0.0, aL_max - (aL_max - pr["aL_2024"]) * pw(1 - pr["g"], ex))
    decline = pw(1 - pr["AICostDecline"], ex)
    CreditCostPB = pr["CreditCost2024"] * decline * AIShockNow
    if reanchor is not None:
        g_Y = pw(1 - pr["g"], y - reanchor.Y)
        LOB_Y = np.maximum(0.0, aL_max - (aL_max - reanchor.lob_Y) * g_Y)
        LOBAuto = np.where((aL_max != reanchor.aL_max) | (pr["g"] != reanchor.g), LOB_Y, LOBAuto)
        decline_Y = reanchor.cost_decay * pw(1 - pr["AICostDecline"], y - reanchor.Y)
        credit_Y = pr["CreditCost2024"] * decline_Y * AIShockNow
        CreditCostPB = np.where(pr["AICostDecline"] != reanchor.AICostDecline, credit_Y, CreditCostPB)
    faults.flag(CREDIT_COST_SITE, CreditCostPB == 0)
    CEc = clamp(pw(pr["CreditCost2024"] / CreditCostPB, pr["CostAdoptElast"]), pr["CEMin"], pr["CEMax"])
    RegRamp = ramp(y, pr["RegStart"], pr["RegEnd"], 0.0, 1.0)
    CyberMult = ramp(y, pr["CyberStart"], pr["CyberRampEnd"], 1.0, pr["CyberEnd"])
    Att = st.Att.copy()
    AttAdopt = np.where(
        ai, np.minimum((pr["pAtt"] + pr["qAtt"] * Att) * (1 - Att), (1 - Att) / pr["MinAdoptionTime"]), 0.0
    )
    CostIdx6 = (ServicesSpend / np.maximum(Completion, 1e-9)) / pr["CostPerBFY0"]
    Jev = np.minimum(pr["JevonsCap"], pw(st.CostPerc, -pr["JevonsEps"]))
    ih, gcc = UNIT_IX["IH"], UNIT_IX["GCC"]
    ConsIT = csum(H[:, ih, l] + H[:, gcc, l] for l in range(len(LEVELS)))
    in_window = (pr["BudgetShockStart"] <= y) & (y < pr["BudgetShockEnd"])
    BudgetGrowth = G * pw(1 + pr["ITBudgetGrowth"], ex) * (1 - np.where(in_window, pr["BudgetShock"], 0.0))
    if nz is not None and "budget" in nz:
        BudgetGrowth = BudgetGrowth * nz["budget"]
    CloudPB = pr["CloudPerBFY"] * (1 + pr["CloudAISens"] * (1 - 1 / P_all))
    end = pr["GCCAppealEnd"]
    GCCAppeal = np.where(
        y < pr["GCCRampEnd"],
        ramp(y, pr["GCCRampStart"], pr["GCCRampEnd"], 0.0, end),
        ramp(y, pr["GCCRampEnd"], pr["GCCFadeEnd"], end, end * pr["GCCAppealKeep"]),
    )
    return ConsumerDrivers(
        LOBAuto=LOBAuto,
        CreditCostPB=CreditCostPB,
        CEc=CEc,
        RegRamp=RegRamp,
        CyberMult=CyberMult,
        Att=Att,
        AttAdopt=AttAdopt,
        CostIdx6=CostIdx6,
        Jev=Jev,
        ConsIT=ConsIT,
        BudgetGrowth=BudgetGrowth,
        CloudPB=CloudPB,
        GCCAppeal=GCCAppeal,
    )


def consumer(
    pr: BatchParams,
    st: BatchState,
    y: float,
    ai: B,
    G: F,
    CS: F,
    CompS: F,
    ServicesSpend: F,
    drv: ConsumerDrivers,
    *,
    nz: Mapping[str, F] | None = None,
) -> Consumer:
    """S13c: the consumer side of each sector, and IT work demand (see ``aisim.scalar.consumer.consumer``)."""
    SectorShare, LOBWage, RegDragLevel = pr.table("SectorShare"), pr.table("LOBWage"), pr.table("RegDragLevel")
    WTMix, BuildMix = pr.table("WTMix"), pr.table("BuildMix")
    c = {name: pr[name][:, None] for name in _SCALARS}
    ai_x = ai[:, None]
    AC = st.AC
    RegDrag = np.minimum(0.95, c["RegScenario"] * RegDragLevel * drv.RegRamp[:, None])
    AIexp = np.where(ai_x, np.maximum(0.0, AC * drv.LOBAuto[:, None] - c["AC0"] * c["aL_2024"]), 0.0)
    LOB0 = pr.fam("LOB0_", SECTORS)
    LOBTarget = LOB0 * (1 - AIexp)
    AgentWork = LOB0 - LOBTarget
    CreditSpend = AgentWork * drv.CreditCostPB[:, None]
    NetSavings = (LOB0 - st.LOB) * LOBWage - CreditSpend
    Budget0 = pr.fam("Budget0_", SECTORS)
    ReinvEff = 1 + c["ReinvestAdoptSens"] * clamp(c["ReinvestFrac"] * NetSavings / Budget0, 0.0, 1.0)
    kC = drv.CEc[:, None] * (1 - RegDrag) * ReinvEff
    AdoptC = np.where(
        ai_x,
        np.minimum((c["pC"] + c["qC"] * AC) * kC * (1 - AC), (1 - AC) / c["MinAdoptionTime"]),
        0.0,
    )
    if nz is not None and "adoption" in nz:
        AdoptC = AdoptC * nz["adoption"][:, None]
    Port0 = pr.fam("Port0_", SECTORS)
    NewApps0 = Port0 / c["AppLife"]
    NewApps = NewApps0 * (1 - c["AppDisplacement"] * AIexp)
    Retire = st.Port / c["AppLife"] * (1 + c["RetireAccel"] * AIexp)
    Seats = st.LOB + drv.ConsIT[:, None] * CS / np.where(pr["Burn"] >= 0.5, G, 1.0)[:, None]
    SeatSpend = st.SeatsB * (c["BaseSeatPrice"] + drv.Att[:, None] * c["AISeatPrice"])
    CloudSpend = drv.CloudPB[:, None] * CompS
    Committed = ServicesSpend[:, None] * CS + SeatSpend + CreditSpend + CloudSpend
    Budget = Budget0 * drv.BudgetGrowth[:, None] + c["ReinvestFrac"] * np.maximum(0.0, NetSavings)
    Approval = clamp(1 - c["ApprovalSens"] * np.maximum(0.0, st.SpendRatio - 1), c["MinApproval"], 1.0)
    step = np.where(y >= pr["StepYear"], pr["DemandStep"], 0.0)[:, None]
    base = pr["BaseDemand"][:, None] * G[:, None] * SectorShare * (1 + step)
    pr0 = st.Port / Port0
    Jev, Approval_ = drv.Jev[:, None], Approval
    w = {k: WTMix[:, WT_IX[k]][:, None] for k in WT_IX}
    dm_app = w["APP"] * ((1 - c["NewAppWeight"]) * pr0 + c["NewAppWeight"] * NewApps / NewApps0) * Jev * Approval_
    dm_data = w["DATA"] * ((1 - c["MigWeight"]) + c["MigWeight"] * Retire / NewApps0) * Jev * Approval_
    dm_sec = np.broadcast_to(w["SEC"] * drv.CyberMult[:, None], AC.shape)
    dm_govn = w["GOVN"] * (1 + np.where(ai_x, c["GovRegSens"] * RegDrag * AC, 0.0))
    dm_sup = w["SUP"] * ((1 - c["SupPortShare"]) + c["SupPortShare"] * pr0)
    dm_eus = w["EUS"] * st.SeatsB / pr.fam("Seats0_", SECTORS)
    dm = np.stack([dm_app, dm_data, dm_sec, dm_govn, dm_sup, dm_eus], axis=2)
    AIBuild = (
        np.where(ai_x, c["BuildRate"] * (AdoptC - c["AdoptC0"]) + c["RunRate"] * (AC - c["AC0"]), 0.0) * Jev * Approval_
    )
    Demand = base[:, :, None] * np.maximum(0.0, dm + AIBuild[:, :, None] * BuildMix[:, None, :])
    cons = SectorConsumer(
        AdoptC=AdoptC,
        LOBTarget=LOBTarget,
        AgentWork=AgentWork,
        CreditSpend=CreditSpend,
        NetSavings=NetSavings,
        NewApps=NewApps,
        Retire=Retire,
        Seats=Seats,
        SeatSpend=SeatSpend,
        CloudSpend=CloudSpend,
        Committed=Committed,
        Budget=Budget,
        Approval=Approval,
        RegDrag=RegDrag,
        AIBuild=AIBuild * base,
    )
    DemandTot = csum_axis(Demand.reshape(st.n, -1), 1)
    return Consumer(cons=cons, Demand=Demand, DemandTot=DemandTot)


_SCALARS = (
    "RegScenario",
    "AC0",
    "aL_2024",
    "ReinvestAdoptSens",
    "ReinvestFrac",
    "pC",
    "qC",
    "MinAdoptionTime",
    "AppLife",
    "AppDisplacement",
    "RetireAccel",
    "BaseSeatPrice",
    "AISeatPrice",
    "ApprovalSens",
    "MinApproval",
    "NewAppWeight",
    "MigWeight",
    "GovRegSens",
    "SupPortShare",
    "BuildRate",
    "RunRate",
    "AdoptC0",
)
"""The scalars ``consumer`` reads per sector, broadcast as ``(N, 1)`` columns."""
