"""Sourcing flows by sector, option costs and risk, sourcing values and targets.

Prototype: ``phase7_sim.py`` S11a (lines 362-369), S13b (lines 439-449) and the sourcing part of the S13c sector loop
(lines 482-491), which this port runs as its own section, S13d, after the consumer part (S13c). Spec module: 10 Sourcing
choice.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EMP_POOL, EMPLOYERS, LEVELS, SECTORS, VENDORS
from aisim.scalar import loops
from aisim.scalar.finance import VendorTerms
from aisim.state import Mat, State, Vec
from aisim.util import softmax


@dataclass(frozen=True, slots=True)
class SectorTurnover:
    """S11a intermediates of one sector (the prototype's ``Src[x]``)."""

    IHTurn: float
    GCCTurn: float
    VExp: Vec
    Contested: float


@dataclass(frozen=True, slots=True)
class SourcingFlows:
    """S11a intermediates."""

    Src: dict[str, SectorTurnover]
    SignS: Mat


@dataclass(frozen=True, slots=True)
class OptionCosts:
    """S13b intermediates."""

    AvgWM: Vec
    AvgW: Vec
    CostOpt: Vec
    RiskOpt: Vec
    Vrel: Vec
    """Relative viability on the 0.75-year margin signal (R6; 1 at 2024)."""
    ClientFlight: Vec
    """The C4 client-flight term after the fade and the cap (0 while ``kViab`` is 0)."""


@dataclass(frozen=True, slots=True)
class SourcingTargets:
    """S13d intermediates."""

    Val: Mat
    SrcTarget: Mat
    GCCScaleTerm: float
    """The R7 term added to every sector's GCC value (0 while ``kR7`` is 0, and on step 0)."""


def sourcing_flows(pr: Mapping[str, float], st: State, VF: Mapping[str, VendorTerms]) -> SourcingFlows:
    """S11a: sourcing flows by sector.

    In-house and GCC work comes up for review over ``IHReviewTime`` and ``GCCReviewTime``; vendor work expires at the
    vendor's book expiry rate. A ``Contest`` share of all of it is re-sourced by the perceived shares ``SrcPerc``; the
    rest of each vendor's expiring work is renewed with it. ``SignS[x][v]`` is the vendor's signing flow in the sector.
    """
    IHW, GCCW, VW, SrcPerc = st["IHW"], st["GCCW"], st["VW"], st["SrcPerc"]
    Src: dict[str, SectorTurnover] = {}
    SignS: Mat = {}
    for x in SECTORS:
        IHTurn = IHW[x] / pr["IHReviewTime"]
        GCCTurn = GCCW[x] / pr["GCCReviewTime"]
        VExp = {v: VW[x][v] * VF[v].ExpRate for v in VENDORS}
        Contested = pr["Contest"] * (IHTurn + GCCTurn + sum(VExp.values()))
        SignS[x] = {v: (1 - pr["Contest"]) * VExp[v] + Contested * SrcPerc[x][v] for v in VENDORS}
        Src[x] = SectorTurnover(IHTurn=IHTurn, GCCTurn=GCCTurn, VExp=VExp, Contested=Contested)
    return SourcingFlows(Src=Src, SignS=SignS)


def option_costs(
    pr: Mapping[str, float],
    st: State,
    W: Mapping[str, float],
    ShareL: Mat,
    AICostPerUnit: float,
    VF: Mapping[str, VendorTerms],
) -> OptionCosts:
    """S13b: sourcing costs per option (USD per unit of work) and option risk.

    - In-house and GCC cost: the level-mixed wage per unit of level-weighted staff over client-perceived productivity
      (GCC with ``GCCOverhead``), plus AI cost on the automated share.
    - Vendor cost: the average unit price times the client price anchor, net of discount and any price shock.
    - Vendor risk: margin shortfall below the deadband (``ViabSens``; loop R6, vendor death spiral) and viability
      below ``ExitThreshold``; OIT also carries visa risk from perceived tightness.
    - R6 C4 client flight (``kViab``, off at 0): a vendor below ``R6Theta`` in relative viability loses sourcing
      value (``aisim.scalar.loops.client_flight``). ``Vrel`` and ``ClientFlight`` are recorded for every model.
    """
    WI, ClientP = st["WI"], st["ClientP"]
    AvgWM = {e: sum(ShareL[e][l] * pr["WageMult_" + l] for l in LEVELS) for e in ("IH", "GCC")}
    AvgW = {e: sum(ShareL[e][l] * W[l] for l in LEVELS) for e in ("IH", "GCC")}
    CostOpt = {
        "IH": pr["BaseWage_IH"] * WI["IH"] * AvgWM["IH"] / (AvgW["IH"] * ClientP["IH"])
        + AICostPerUnit * (1 - 1 / ClientP["IH"]),
        "GCC": pr["BaseWage_GCC"] * WI["GCC"] * AvgWM["GCC"] * (1 + pr["GCCOverhead"]) / (AvgW["GCC"] * ClientP["GCC"])
        + AICostPerUnit * (1 - 1 / ClientP["GCC"]),
    }
    for v in VENDORS:
        f = VF[v]
        CostOpt[v] = f.BasePriceAvg * f.Anchor * (1 - f.Disc) * (1 - f.shock)
    RiskOpt = {"IH": 0.0, "GCC": 0.0}
    for v in VENDORS:
        RiskOpt[v] = pr["ViabSens"] * min(0.0, VF[v].DevEff) - pr["ExitPenalty"] * max(
            0.0, pr["ExitThreshold"] - VF[v].Vi
        )
    RiskOpt["OIT"] -= pr["VisaRiskSens"] * max(0.0, st["TightPerc"] - pr["VTBase"])
    Vrel = {v: loops.vrel(pr, st, v) for v in VENDORS}
    ClientFlight = {v: loops.client_flight(pr, st, v) for v in VENDORS}
    if pr["kViab"] != 0.0:  # R6 C4: client flight
        for v in VENDORS:
            RiskOpt[v] -= ClientFlight[v]
    return OptionCosts(AvgWM=AvgWM, AvgW=AvgW, CostOpt=CostOpt, RiskOpt=RiskOpt, Vrel=Vrel, ClientFlight=ClientFlight)


def sourcing_targets(
    pr: Mapping[str, float],
    tb: Mapping[str, Mapping[str, float]],
    st: State,
    ai_on: bool,
    RegDrag: Vec,
    GCCAppeal: float,
    TTFratio: Vec,
    opt: OptionCosts,
    CS: Vec,
) -> SourcingTargets:
    """S13d: sourcing values and targets per sector (the sourcing part of the prototype's S13c loop).

    Each option's value is its sector constant ``SrcASC``, less its cost relative to ``CostRef`` (``SrcCostSens``), plus
    its risk, less a capacity penalty when its pool's time to fill is above normal, less a regulatory-fit penalty on
    offshore exposure. GCC adds the GCC appeal and a term rising with consumer AI adoption. ``SrcTarget`` is the logit.

    Loops: B3 (insourcing) acts through the in-house cost term, R7 (captive learning) through the GCC terms, B12 and
    R6 through vendor cost and risk. R7 GCC scale learning (``kR7``, off at 0) closes R7: every sector's GCC value
    gains ``aisim.scalar.loops.r7`` on the economy-wide GCC work share from the completion shares ``CS``.
    """
    CostOpt, RiskOpt = opt.CostOpt, opt.RiskOpt
    OffExp = tb["OffExp"]
    Val: Mat = {}
    SrcTarget: Mat = {}
    GCCScaleTerm = loops.r7(pr, st, loops.ws(st, CS)) if pr["kR7"] != 0.0 else 0.0
    for x in SECTORS:
        AC = st["AC"][x]
        values: Vec = {}
        for e in EMPLOYERS:
            value = (
                pr[f"SrcASC_{x}_{e}"]
                - pr["SrcCostSens"] * CostOpt[e] / pr["CostRef"]
                + RiskOpt[e]
                - pr["CapSens"] * max(0.0, TTFratio[EMP_POOL[e]] - 1)
                - (pr["RegFitSens"] * RegDrag[x] * AC * OffExp[e] if ai_on else 0.0)
            )
            if e == "GCC":
                value += GCCAppeal + (pr["GCCAISens"] * (AC - pr["AC0"]) if ai_on else 0.0)
                if pr["kR7"] != 0.0:  # R7: GCC scale learning
                    value += GCCScaleTerm
            values[e] = value
        Val[x] = values
        SrcTarget[x] = softmax(values)
    return SourcingTargets(Val=Val, SrcTarget=SrcTarget, GCCScaleTerm=GCCScaleTerm)
