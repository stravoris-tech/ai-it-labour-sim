"""Consumer AI, LOB, apps, seats, credits, cloud, budget, approval and demand.

Prototype: ``phase7_sim.py`` S13a (lines 424-438) and the consumer part of the S13c sector loop (lines 450-481 and
492-495). The sourcing part of that loop (lines 482-491) is ``sourcing.sourcing_targets`` (S13d): the two parts share
no accumulator, so running them as two loops leaves every value unchanged. Spec modules: 5 Consumer AI (Bass, LOB),
1b Applications and seats, 7 AI capability (LOB automation, credit cost, regulatory drag, cyber), 8 Finance (budget,
approval: integrity rule 3), 1 IT work demand and 9 GCCs (``GCCAppeal``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import LEVELS, SECTORS, WTYPES
from aisim.state import Mat, State, Vec
from aisim.util import clamp, ramp


@dataclass(frozen=True, slots=True)
class ConsumerDrivers:
    """S13a intermediates."""

    LOBAuto: float
    CreditCostPB: float
    CEc: float
    RegRamp: float
    CyberMult: float
    Att: float
    AttAdopt: float
    CostIdx6: float
    Jev: float
    ConsIT: float
    BudgetGrowth: float
    CloudPB: float
    GCCAppeal: float


@dataclass(frozen=True, slots=True)
class SectorConsumer:
    """S13c intermediates of one sector (the prototype's ``cons[x]``)."""

    AdoptC: float
    LOBTarget: float
    AgentWork: float
    CreditSpend: float
    NetSavings: float
    NewApps: float
    Retire: float
    """Applications retired a year (not people retiring)."""
    Seats: float
    SeatSpend: float
    CloudSpend: float
    Committed: float
    Budget: float
    Approval: float
    RegDrag: float
    AIBuild: float
    """AI build demand in units of work a year (``AIBuild x base``)."""


@dataclass(frozen=True, slots=True)
class Consumer:
    """S13c intermediates."""

    cons: dict[str, SectorConsumer]
    Demand: Mat
    DemandTot: float


def drivers(
    pr: Mapping[str, float],
    st: State,
    y: float,
    ai_on: bool,
    G: float,
    Completion: float,
    P_all: float,
    AIShockNow: float,
    ServicesSpend: float,
) -> ConsumerDrivers:
    """S13a: exogenous consumer drivers and aggregates.

    - ``LOBAuto``, the automatable share of line-of-business work, closes the gap from ``aL_2024`` to ``aL_max`` at
      rate ``g``. AI credits cost ``CreditCostPB``, falling like delivery AI cost; ``CEc`` is the consumer cost effect.
    - ``RegRamp`` and ``CyberMult`` ramp regulation and cyber demand in. ``AttAdopt`` is Bass diffusion of AI seat
      attach.
    - ``CostIdx6`` is services spend per unit of work over its 2024 level; ``Jev = CostPerc^-JevonsEps`` (capped) turns
      the perceived cost fall into more approved demand: loop R3 (Jevons effect).
    - ``BudgetGrowth`` grows budgets with ``G`` and ``ITBudgetGrowth``, less any budget shock. Cloud spend per unit of
      work rises with AI productivity. ``GCCAppeal`` ramps to ``GCCAppealEnd`` by ``GCCRampEnd``, then fades to
      ``GCCAppealKeep`` of it by ``GCCFadeEnd``.
    """
    H = st["H"]
    LOBAuto = max(0.0, pr["aL_max"] - (pr["aL_max"] - pr["aL_2024"]) * (1 - pr["g"]) ** (y - 2024))
    CreditCostPB = pr["CreditCost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShockNow
    CEc = clamp((pr["CreditCost2024"] / CreditCostPB) ** pr["CostAdoptElast"], pr["CEMin"], pr["CEMax"])
    RegRamp = ramp(y, pr["RegStart"], pr["RegEnd"], 0.0, 1.0)
    CyberMult = ramp(y, pr["CyberStart"], pr["CyberRampEnd"], 1.0, pr["CyberEnd"])
    Att = st["Att"]
    AttAdopt = min((pr["pAtt"] + pr["qAtt"] * Att) * (1 - Att), (1 - Att) / pr["MinAdoptionTime"]) if ai_on else 0.0
    CostIdx6 = (ServicesSpend / max(Completion, 1e-9)) / pr["CostPerBFY0"]
    Jev = min(pr["JevonsCap"], st["CostPerc"] ** (-pr["JevonsEps"]))
    ConsIT = sum(H["IH"][l] + H["GCC"][l] for l in LEVELS)
    BudgetGrowth = (
        G
        * (1 + pr["ITBudgetGrowth"]) ** (y - 2024)
        * (1 - (pr["BudgetShock"] if pr["BudgetShockStart"] <= y < pr["BudgetShockEnd"] else 0.0))
    )
    CloudPB = pr["CloudPerBFY"] * (1 + pr["CloudAISens"] * (1 - 1 / P_all))
    GCCAppeal = (
        ramp(y, pr["GCCRampStart"], pr["GCCRampEnd"], 0.0, pr["GCCAppealEnd"])
        if y < pr["GCCRampEnd"]
        else ramp(y, pr["GCCRampEnd"], pr["GCCFadeEnd"], pr["GCCAppealEnd"], pr["GCCAppealEnd"] * pr["GCCAppealKeep"])
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
    pr: Mapping[str, float],
    tb: Mapping[str, Mapping[str, float]],
    st: State,
    y: float,
    ai_on: bool,
    G: float,
    CS: Vec,
    CompS: Vec,
    ServicesSpend: float,
    drv: ConsumerDrivers,
) -> Consumer:
    """S13c: the consumer side of each sector, and IT work demand.

    - Consumer AI adoption ``AdoptC`` is Bass diffusion, slowed by regulatory drag (``RegDrag``, capped at 0.95) and
      sped up by the cost effect and by reinvested savings (``ReinvEff``): loop R1 (savings reinvestment).
    - AI exposure ``AIexp`` above its 2024 level automates line-of-business work: ``LOBTarget`` falls and agent work,
      paid in credits, replaces it. ``NetSavings`` is the LOB wage bill saved less credits.
    - Agents displace new applications and speed retirement: loop B9 (application displacement). Seats follow LOB plus
      consumer IT staff: loop B10 (seat contraction).
    - ``Committed`` spend (services, seats, credits, cloud) against ``Budget`` (grown, plus reinvested savings) sets
      ``Approval`` through the smoothed ``SpendRatio``: loop B11 (budget crowding-out).
    - Demand by work type is base demand (``BaseDemand x G x SectorShare``, plus any ``DemandStep``) times a mix that
      follows the portfolio, seats, cyber and governance, with Jevons and approval on app and data work, plus AI build
      demand from consumer adoption: loop R2 (AI begets IT work).
    """
    SectorShare, LOBWage, RegDragLevel = tb["SectorShare"], tb["LOBWage"], tb["RegDragLevel"]
    WTMix, BuildMix = tb["WTMix"], tb["BuildMix"]
    LOBAuto, CreditCostPB, CEc, RegRamp = drv.LOBAuto, drv.CreditCostPB, drv.CEc, drv.RegRamp
    Att, Jev, ConsIT, BudgetGrowth, CloudPB = drv.Att, drv.Jev, drv.ConsIT, drv.BudgetGrowth, drv.CloudPB
    cons: dict[str, SectorConsumer] = {}
    Demand: Mat = {}
    for x in SECTORS:
        AC = st["AC"][x]
        RegDrag = min(0.95, pr["RegScenario"] * RegDragLevel[x] * RegRamp)
        AIexp = max(0.0, AC * LOBAuto - pr["AC0"] * pr["aL_2024"]) if ai_on else 0.0
        LOB0 = pr["LOB0_" + x]
        LOBTarget = LOB0 * (1 - AIexp)
        AgentWork = LOB0 - LOBTarget
        CreditSpend = AgentWork * CreditCostPB
        NetSavings = (LOB0 - st["LOB"][x]) * LOBWage[x] - CreditSpend
        ReinvEff = 1 + pr["ReinvestAdoptSens"] * clamp(pr["ReinvestFrac"] * NetSavings / pr["Budget0_" + x], 0.0, 1.0)
        kC = CEc * (1 - RegDrag) * ReinvEff
        AdoptC = min((pr["pC"] + pr["qC"] * AC) * kC * (1 - AC), (1 - AC) / pr["MinAdoptionTime"]) if ai_on else 0.0
        Port0 = pr["Port0_" + x]
        NewApps0 = Port0 / pr["AppLife"]
        NewApps = NewApps0 * (1 - pr["AppDisplacement"] * AIexp)
        Retire = st["Port"][x] / pr["AppLife"] * (1 + pr["RetireAccel"] * AIexp)
        Seats = st["LOB"][x] + ConsIT * CS[x] / (G if pr["Burn"] >= 0.5 else 1.0)
        SeatSpend = st["SeatsB"][x] * (pr["BaseSeatPrice"] + Att * pr["AISeatPrice"])
        CloudSpend = CloudPB * CompS[x]
        Committed = ServicesSpend * CS[x] + SeatSpend + CreditSpend + CloudSpend
        Budget = pr["Budget0_" + x] * BudgetGrowth + pr["ReinvestFrac"] * max(0.0, NetSavings)
        Approval = clamp(1 - pr["ApprovalSens"] * max(0.0, st["SpendRatio"][x] - 1), pr["MinApproval"], 1.0)
        base = pr["BaseDemand"] * G * SectorShare[x] * (1 + (pr["DemandStep"] if y >= pr["StepYear"] else 0))
        pr0 = st["Port"][x] / Port0  # portfolio relative to 2024
        dm = {
            "APP": WTMix["APP"]
            * ((1 - pr["NewAppWeight"]) * pr0 + pr["NewAppWeight"] * NewApps / NewApps0)
            * Jev
            * Approval,
            "DATA": WTMix["DATA"] * ((1 - pr["MigWeight"]) + pr["MigWeight"] * Retire / NewApps0) * Jev * Approval,
            "SEC": WTMix["SEC"] * drv.CyberMult,
            "GOVN": WTMix["GOVN"] * (1 + (pr["GovRegSens"] * RegDrag * AC if ai_on else 0.0)),
            "SUP": WTMix["SUP"] * ((1 - pr["SupPortShare"]) + pr["SupPortShare"] * pr0),
            "EUS": WTMix["EUS"] * st["SeatsB"][x] / pr["Seats0_" + x],
        }
        AIBuild = (
            ((pr["BuildRate"] * (AdoptC - pr["AdoptC0"]) + pr["RunRate"] * (AC - pr["AC0"])) if ai_on else 0.0)
            * Jev
            * Approval
        )
        Demand[x] = {w: base * max(0.0, dm[w] + AIBuild * BuildMix[w]) for w in WTYPES}
        cons[x] = SectorConsumer(
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
    DemandTot = sum(Demand[x][w] for x in SECTORS for w in WTYPES)
    return Consumer(cons=cons, Demand=Demand, DemandTot=DemandTot)
