"""S11a, S13b and S13d, batched: sourcing flows by sector, option costs and risk, sourcing values and targets.

Mirrors ``aisim.scalar.sourcing``. The per-sector dict of ``SectorTurnover`` becomes one dataclass of ``(N, sector)``
and ``(N, sector, vendor)`` arrays. ``AvgWM`` and ``AvgW`` are ``(N, 2)`` over IH and GCC; ``CostOpt`` and ``RiskOpt``
are ``(N, employer)``; ``Val`` and ``SrcTarget`` are ``(N, sector, employer)``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from aisim.batch.axes import EMP_IX, EMP_POOL_IX, VEND_IX, VENDOR_EMP_IX
from aisim.batch.finance import VendorTerms
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, csum_axis, softmax
from aisim.dims import EMPLOYERS, LEVELS, SECTORS


@dataclass(frozen=True, slots=True)
class SectorTurnover:
    """S11a intermediates of every sector (the prototype's ``Src``)."""

    IHTurn: F
    GCCTurn: F
    VExp: F
    Contested: F


@dataclass(frozen=True, slots=True)
class SourcingFlows:
    """S11a intermediates."""

    Src: SectorTurnover
    SignS: F


@dataclass(frozen=True, slots=True)
class OptionCosts:
    """S13b intermediates."""

    AvgWM: F
    AvgW: F
    CostOpt: F
    RiskOpt: F


@dataclass(frozen=True, slots=True)
class SourcingTargets:
    """S13d intermediates."""

    Val: F
    SrcTarget: F


def sourcing_flows(pr: BatchParams, st: BatchState, VF: VendorTerms) -> SourcingFlows:
    """S11a: sourcing flows by sector (see ``aisim.scalar.sourcing.sourcing_flows``)."""
    IHTurn = st.IHW / pr["IHReviewTime"][:, None]
    GCCTurn = st.GCCW / pr["GCCReviewTime"][:, None]
    VExp = st.VW * VF.ExpRate[:, None, :]
    Contest = pr["Contest"][:, None]
    Contested = Contest * (IHTurn + GCCTurn + csum_axis(VExp, 2))
    SignS = (1 - Contest)[:, :, None] * VExp + Contested[:, :, None] * st.SrcPerc[:, :, VENDOR_EMP_IX]
    Src = SectorTurnover(IHTurn=IHTurn, GCCTurn=GCCTurn, VExp=VExp, Contested=Contested)
    return SourcingFlows(Src=Src, SignS=SignS)


def option_costs(pr: BatchParams, st: BatchState, W: F, ShareL: F, AICostPerUnit: F, VF: VendorTerms) -> OptionCosts:
    """S13b: sourcing costs per option and option risk (see ``aisim.scalar.sourcing.option_costs``)."""
    WI, ClientP = st.WI, st.ClientP
    own = [EMP_IX["IH"], EMP_IX["GCC"]]
    share = ShareL[:, own, :]
    AvgWM = csum_axis(share * pr.fam("WageMult_", LEVELS)[:, None, :], 2)
    AvgW = csum_axis(share * W[:, None, :], 2)
    ih, gcc = EMP_IX["IH"], EMP_IX["GCC"]
    cp_ih, cp_gcc = ClientP[:, ih], ClientP[:, gcc]
    cost_ih = pr["BaseWage_IH"] * WI[:, ih] * AvgWM[:, 0] / (AvgW[:, 0] * cp_ih) + AICostPerUnit * (1 - 1 / cp_ih)
    cost_gcc = pr["BaseWage_GCC"] * WI[:, gcc] * AvgWM[:, 1] * (1 + pr["GCCOverhead"]) / (
        AvgW[:, 1] * cp_gcc
    ) + AICostPerUnit * (1 - 1 / cp_gcc)
    cost_v = VF.BasePriceAvg * VF.Anchor * (1 - VF.Disc) * (1 - VF.shock)
    CostOpt = np.concatenate([cost_ih[:, None], cost_gcc[:, None], cost_v], axis=1)
    risk_v = pr["ViabSens"][:, None] * np.minimum(0.0, VF.DevEff) - pr["ExitPenalty"][:, None] * np.maximum(
        0.0, pr["ExitThreshold"][:, None] - VF.Vi
    )
    oit = VEND_IX["OIT"]
    risk_v[:, oit] = risk_v[:, oit] - pr["VisaRiskSens"] * np.maximum(0.0, st.TightPerc - pr["VTBase"])
    zero = np.zeros((st.n, 1))
    RiskOpt = np.concatenate([zero, zero, risk_v], axis=1)
    return OptionCosts(AvgWM=AvgWM, AvgW=AvgW, CostOpt=CostOpt, RiskOpt=RiskOpt)


def sourcing_targets(
    pr: BatchParams, st: BatchState, ai: B, RegDrag: F, GCCAppeal: F, TTFratio: F, opt: OptionCosts
) -> SourcingTargets:
    """S13d: sourcing values and targets per sector (see ``aisim.scalar.sourcing.sourcing_targets``)."""
    CostOpt, RiskOpt = opt.CostOpt[:, None, :], opt.RiskOpt[:, None, :]
    OffExp = pr.table("OffExp")[:, None, :]
    AC = st.AC[:, :, None]
    capacity = pr["CapSens"][:, None] * np.maximum(0.0, TTFratio[:, EMP_POOL_IX] - 1)
    regfit = np.where(ai[:, None, None], pr["RegFitSens"][:, None, None] * RegDrag[:, :, None] * AC * OffExp, 0.0)
    Val = (
        pr.fam("SrcASC_", SECTORS, EMPLOYERS)
        - pr["SrcCostSens"][:, None, None] * CostOpt / pr["CostRef"][:, None, None]
        + RiskOpt
        - capacity[:, None, :]
        - regfit
    )
    gcc = EMP_IX["GCC"]
    gcc_ai = np.where(ai[:, None], pr["GCCAISens"][:, None] * (st.AC - pr["AC0"][:, None]), 0.0)
    Val[:, :, gcc] = Val[:, :, gcc] + (GCCAppeal[:, None] + gcc_ai)
    SrcTarget = softmax(Val)
    return SourcingTargets(Val=Val, SrcTarget=SrcTarget)
