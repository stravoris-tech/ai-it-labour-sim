"""S9, S10 and S11b-S11d, batched: delivery, wages, labour cost, AI cost, vendor contracts and finance, margin, type
choice, competition, wage targets and services spend.

Mirrors ``aisim.scalar.finance``. The per-vendor dicts of dataclasses (``VF``, ``VB``) become one dataclass of arrays,
``(N, vendor)`` or ``(N, vendor, type)``; ``VF.vu`` is the structural ``(vendor, unit)`` mask. The vendor loops are
three vectorised passes (S10, S11a in ``sourcing``, S11b), as recon 03 C3 confirms.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from aisim.batch.axes import (
    EFFORT_TYPE,
    EMP_IX,
    EMP_OF_IX,
    GLIDE_TYPE,
    POOL_IX,
    TYPE_IX,
    UNIT_IX,
    UNITS_OF_VENDOR,
    VEND_IX,
    VENDOR_EMP_IX,
    VENDOR_OF_UNIT_IX,
    VENDOR_UNIT,
)
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import B, F, clamp, csum, csum_axis, group_sum, pw, softmax
from aisim.dims import EFFORT, LEVELS, REGIONS, TYPES, UNITS, VENDORS
from aisim.params import Reanchor


@dataclass(frozen=True, slots=True)
class Costs:
    """S9 intermediates: ``capu``, ``Delivered``, ``LabourCost`` ``(N, unit)``; ``Wage`` ``(N, unit, level)``;
    ``AIShockNow``, ``AICostPerUnit`` ``(N,)``."""

    capu: F
    Delivered: F
    Wage: F
    LabourCost: F
    AIShockNow: F
    AICostPerUnit: F


@dataclass(frozen=True, slots=True)
class VendorTerms:
    """S10 intermediates of every vendor (the prototype's ``VF``): ``(N, vendor)`` or ``(N, vendor, type)``."""

    vu: B
    shock: F
    Anchor: F
    PU: F
    Vi: F
    nm: F
    dev: F
    DevEff: F
    Power: F
    Disc: F
    Book: F
    Glide: F
    Dnew: F
    AvgDur: F
    PNew: F
    AvgP: F
    ExpLeg: F
    ExpNew: F
    ExpRate: F
    IdxVol: F
    AvgIdx: F
    VendDel: F
    BaseRev: F
    BasePriceAvg: F
    Revenue: F
    AICost: F
    VisaCost: F
    VLab: F
    LabRaw: F


@dataclass(frozen=True, slots=True)
class Contracts:
    """S10 intermediates: ``Pass`` ``(N, type)`` and ``VF``."""

    Pass: F
    VF: VendorTerms


@dataclass(frozen=True, slots=True)
class VendorBook:
    """S11b intermediates of every vendor: ``(N, vendor)`` or ``(N, vendor, type)``."""

    SignRate: F
    SalesCost: F
    VendorCost: F
    Margin: F
    CostIdx: F
    wv: F
    TypeShare: F
    Sign: F
    VShare: F
    ShareLoss: F
    Afford: F
    DiscTarget: F
    CostProgTarget: F
    EffortShare: F


@dataclass(frozen=True, slots=True)
class VendorBooks:
    """S11b intermediates."""

    VB: VendorBook


@dataclass(frozen=True, slots=True)
class WageTargets:
    """S11c intermediates: ``WITarget`` ``(N, unit)``."""

    WITarget: F


@dataclass(frozen=True, slots=True)
class Spend:
    """S11d intermediates, each ``(N,)``."""

    RevenueTot: F
    AICostCons: F
    ServicesSpend: F


def costs(
    pr: BatchParams,
    st: BatchState,
    y: float,
    W: F,
    CompE: F,
    EffStaffE: F,
    *,
    reanchor: Reanchor | None = None,
    nz: Mapping[str, F] | None = None,
) -> Costs:
    """S9: delivery, wages and labour cost (see ``aisim.scalar.finance.costs``)."""
    H, O, WI = st.H, st.O, st.WI
    capu = csum_axis(W[:, None, :] * (H + pr["OnboardProductivity"][:, None, None] * O), 2)
    Delivered = CompE[:, EMP_OF_IX] * capu / np.maximum(EffStaffE[:, EMP_OF_IX], 1e-9)
    Wage = pr.fam("BaseWage_", UNITS)[:, :, None] * pr.fam("WageMult_", LEVELS)[:, None, :] * WI[:, :, None]
    LabourCost = csum_axis((H + O) * Wage, 2)
    in_window = (pr["AIShockStart"] <= y) & (y < pr["AIShockEnd"])
    AIShockNow = np.where(in_window, pr["AIShockMult"], 1.0)
    AICostPerUnit = pr["AICost2024"] * pw(1 - pr["AICostDecline"], y - 2024) * AIShockNow
    if reanchor is not None:
        decline_Y = reanchor.cost_decay * pw(1 - pr["AICostDecline"], y - reanchor.Y)
        cost_Y = pr["AICost2024"] * decline_Y * AIShockNow
        AICostPerUnit = np.where(pr["AICostDecline"] != reanchor.AICostDecline, cost_Y, AICostPerUnit)
    if nz is not None and "aicost" in nz:
        AICostPerUnit = AICostPerUnit * nz["aicost"]
    return Costs(
        capu=capu,
        Delivered=Delivered,
        Wage=Wage,
        LabourCost=LabourCost,
        AIShockNow=AIShockNow,
        AICostPerUnit=AICostPerUnit,
    )


def contracts(
    pr: BatchParams,
    st: BatchState,
    y: float,
    Pe: F,
    UnitIn: F,
    hires: F,
    cost: Costs,
    *,
    nz: Mapping[str, F] | None = None,
) -> Contracts:
    """S10: per-vendor contracts and finance (see ``aisim.scalar.finance.contracts``)."""
    H = st.H
    Delivered, LabourCost, AICostPerUnit = cost.Delivered, cost.LabourCost, cost.AICostPerUnit
    n = st.n
    Pass = np.stack([np.zeros(n), np.ones(n), pr["MSGlideShare"] + 0.0, np.ones(n), pr["OBGainShare"] + 0.0], axis=1)
    shock = np.where((y >= pr["PriceShockYear"])[:, None], pr.fam("PriceShock_", VENDORS), 0.0)
    CP = st.ClientP[:, VENDOR_EMP_IX]
    CPRef = st.ClientPRef[:, VENDOR_EMP_IX]
    PU = np.maximum(0.0, (CP - CPRef) / (CPRef * pr["TrendTime"][:, None]))
    Anchor = pw(1 / (CP * (1 + pr["PriceHorizon"][:, None] * PU)), pr["PassThrough"][:, None])
    if nz is not None and "anchor" in nz:
        Anchor = Anchor * nz["anchor"][:, None]
    Vi = st.Viab.copy()
    nm = pr.fam("NormalMargin_", VENDORS)
    dev = Vi - nm
    band = pr["Deadband"][:, None]
    DevEff = np.where(dev > band, dev - band, np.where(dev < -band, dev + band, 0.0))
    Power = clamp(1 + pr["PowerSens"][:, None] * dev, pr["PowerMin"][:, None], pr["PowerMax"][:, None])
    Disc = st.Disc.copy()
    Leg, NV, ND, NP = st.Leg, st.NewV, st.NewD, st.NewP
    Book = csum_axis(Leg + NV, 2)
    Glide = np.where(GLIDE_TYPE[None, None, :], Pass[:, None, :] * PU[:, :, None], 0.0)
    BaseDur = pr.fam("BaseDur_", TYPES)[:, None, :]
    Dnew = np.maximum(
        pr["MinDur"][:, None, None],
        BaseDur
        / (1 + pr["DurPUSens"][:, None, None] * PU[:, :, None])
        * pw(Power, pr["DurPowerElast"][:, None])[:, :, None],
    )
    AvgDur = np.where(NV > 1e-12, ND / NV, Dnew)
    Disc_k = (1 - Disc)[:, :, None]
    PNew = np.where(EFFORT_TYPE[None, None, :], Disc_k, Anchor[:, :, None] * Disc_k)
    AvgP = np.where(NV > 1e-12, NP / NV, PNew)
    ExpLeg = Leg / BaseDur
    ExpNew = NV / AvgDur
    book_floor = np.maximum(Book, 1e-12)
    ExpRate = csum_axis(ExpLeg + ExpNew, 2) / book_floor
    Pe_v = Pe[:, VENDOR_EMP_IX]
    IdxVol = np.where(EFFORT_TYPE[None, None, :], (Leg + NP) / Pe_v[:, :, None], Leg + NP)
    AvgIdx = csum_axis(IdxVol, 2) / book_floor
    VendDel = group_sum(Delivered, UNITS_OF_VENDOR)
    Price = pr.fam("Price_", UNITS)
    PriceMult = pr.fam("PriceMult_", VENDORS)
    unit_mult = PriceMult[:, VENDOR_OF_UNIT_IX]
    BaseRev = group_sum(Delivered * Price * unit_mult, UNITS_OF_VENDOR)
    BasePriceAvg = group_sum(UnitIn * Price, UNITS_OF_VENDOR) * PriceMult / group_sum(UnitIn, UNITS_OF_VENDOR)
    Revenue = BaseRev * AvgIdx * (1 - shock)
    AICost = AICostPerUnit[:, None] * VendDel * (1 - 1 / Pe_v)
    ov, oit = UNIT_IX["OV"], VEND_IX["OIT"]
    visa_oit = (
        csum(hires[:, ov, l] for l in range(len(LEVELS))) * pr["VisaFeePerHire"]
        + csum(H[:, ov, l] for l in range(len(LEVELS))) * pr["VisaComplianceCost"]
    )
    VisaCost = np.zeros((n, len(VENDORS)))
    VisaCost[:, oit] = visa_oit
    LabRaw = group_sum(LabourCost, UNITS_OF_VENDOR)
    VLab = LabRaw * (1 - st.CostProg)
    VF = VendorTerms(
        vu=UNITS_OF_VENDOR,
        shock=shock,
        Anchor=Anchor,
        PU=PU,
        Vi=Vi,
        nm=nm,
        dev=dev,
        DevEff=DevEff,
        Power=Power,
        Disc=Disc,
        Book=Book,
        Glide=Glide,
        Dnew=Dnew,
        AvgDur=AvgDur,
        PNew=PNew,
        AvgP=AvgP,
        ExpLeg=ExpLeg,
        ExpNew=ExpNew,
        ExpRate=ExpRate,
        IdxVol=IdxVol,
        AvgIdx=AvgIdx,
        VendDel=VendDel,
        BaseRev=BaseRev,
        BasePriceAvg=BasePriceAvg,
        Revenue=Revenue,
        AICost=AICost,
        VisaCost=VisaCost,
        VLab=VLab,
        LabRaw=LabRaw,
    )
    return Contracts(Pass=Pass, VF=VF)


def vendor_books(
    pr: BatchParams, st: BatchState, Pe: F, CompS: F, CS: F, TTFratio: F, SignS: F, con: Contracts
) -> VendorBooks:
    """S11b: vendor book turnover, sales cost, margin, type choice and competition (see
    ``aisim.scalar.finance.vendor_books``)."""
    Pass, f = con.Pass, con.VF
    VW, ClientP = st.VW, st.ClientP
    vol = csum_axis(VW * CompS[:, :, None], 1)
    signvol = csum_axis(SignS * CompS[:, :, None], 1)
    SignRate = np.where(vol > 1e-9, signvol / vol, f.ExpRate)
    SalesCost = pr["SalesCostRate"][:, None] * f.Revenue * SignRate
    VendorCost = f.VLab + f.VisaCost + f.AICost + st.Overhead + SalesCost
    Margin = (f.Revenue - VendorCost) / np.maximum(f.Revenue, 1.0)
    del_floor = np.maximum(f.VendDel, 1e-9)
    CostIdx = (VendorCost / del_floor) / np.maximum(f.BaseRev / del_floor, 1e-9)
    wv = clamp(pr["BargainW0"][:, None] * f.Power, 0.1, 0.9)
    wc = 1 - wv
    D = f.Dnew
    PU = f.PU[:, :, None]
    ConsSens = pr["ConsSens"][:, None, None]
    Ucons = -ConsSens * (1 - Pass[:, None, :]) * PU * D / 2
    distrust = ConsSens * pr["EffortDistrust"][:, None, None] * (1 - 1 / ClientP[:, VENDOR_EMP_IX])[:, :, None]
    Ucons = np.where(EFFORT_TYPE[None, None, :], Ucons - distrust, Ucons)
    sa = np.array([k == "SA" for k in TYPES])
    ttf_on = clamp(TTFratio[:, 1] - 1, -1.0, 2.0)
    Ucons = np.where(sa[None, None, :], Ucons + (pr["SATTFSens"] * ttf_on)[:, None, None], Ucons)
    Pe_v = Pe[:, VENDOR_EMP_IX][:, :, None]
    Rterm = np.where(
        EFFORT_TYPE[None, None, :],
        f.PNew / Pe_v * (1 - PU * D / 2),
        f.PNew * (1 - Pass[:, None, :] * PU * D / 2),
    )
    Profit = Rterm - CostIdx[:, :, None] * (1 - PU * D / 2)
    nm = f.nm[:, :, None]
    Uvend = pr["VendSens"][:, None, None] * (Profit - nm) / nm
    Score = pr.fam("TypeASC_", VENDORS, TYPES) + wc[:, :, None] * Ucons + wv[:, :, None] * Uvend
    TypeShare = softmax(Score)
    Sign = (f.Book * SignRate)[:, :, None] * TypeShare
    VShare = csum_axis(VW * CS[:, :, None], 1)
    ShareRef = st.ShareRef
    ShareLoss = np.maximum(0.0, (ShareRef - VShare) / np.maximum(ShareRef, 1e-12))
    Afford = clamp(f.Vi / f.nm, 0.0, 1.0)
    DiscTarget = clamp(
        pr["ShareLossSens"][:, None] * ShareLoss * Afford + pr["RivalSens"][:, None] * np.maximum(0.0, f.DevEff),
        0.0,
        pr["MaxDisc"][:, None],
    )
    CostProgTarget = clamp(pr["CostProgramSens"][:, None] * np.maximum(0.0, -f.DevEff), 0.0, pr["MaxSavings"][:, None])
    held = st.Leg + st.NewV
    EffortShare = csum(held[:, :, TYPE_IX[k]] for k in EFFORT) / np.maximum(f.Book, 1e-12)
    VB = VendorBook(
        SignRate=SignRate,
        SalesCost=SalesCost,
        VendorCost=VendorCost,
        Margin=Margin,
        CostIdx=CostIdx,
        wv=wv,
        TypeShare=TypeShare,
        Sign=Sign,
        VShare=VShare,
        ShareLoss=ShareLoss,
        Afford=Afford,
        DiscTarget=DiscTarget,
        CostProgTarget=CostProgTarget,
        EffortShare=EffortShare,
    )
    return VendorBooks(VB=VB)


def wage_targets(pr: BatchParams, st: BatchState, VF: VendorTerms) -> WageTargets:
    """S11c: wage-index targets (see ``aisim.scalar.finance.wage_targets``)."""
    norm = pr.fam("NormalUnempRate_", REGIONS)[:, POOL_IX]
    tight = pw(norm / np.maximum(st.PUS[:, POOL_IX], 1e-6), pr["WageElasticity"][:, None])
    vendor_dev = VF.DevEff[:, VENDOR_OF_UNIT_IX]
    restraint = np.where(VENDOR_UNIT[None, :], 1 - pr["WageRestraint"][:, None] * np.maximum(0.0, -vendor_dev), 1.0)
    target = clamp(tight * restraint, pr["WageMin"][:, None], pr["WageMax"][:, None])
    WITarget = np.where((pr["WagesEndogenous"] >= 0.5)[:, None], target, 1.0)
    return WageTargets(WITarget=WITarget)


def spend(pr: BatchParams, Pe: F, cost: Costs, VF: VendorTerms) -> Spend:
    """S11d: total vendor revenue and consumer IT services spend (see ``aisim.scalar.finance.spend``)."""
    Delivered, LabourCost = cost.Delivered, cost.LabourCost
    ih, gcc = EMP_IX["IH"], EMP_IX["GCC"]
    uih, ugcc = UNIT_IX["IH"], UNIT_IX["GCC"]
    RevenueTot = csum_axis(VF.Revenue, 1)
    AICostCons = cost.AICostPerUnit * (
        (1 - 1 / Pe[:, ih]) * Delivered[:, uih] + (1 - 1 / Pe[:, gcc]) * Delivered[:, ugcc]
    )
    ServicesSpend = LabourCost[:, uih] + LabourCost[:, ugcc] * (1 + pr["GCCOverhead"]) + RevenueTot + AICostCons
    return Spend(RevenueTot=RevenueTot, AICostCons=AICostCons, ServicesSpend=ServicesSpend)
