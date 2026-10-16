"""Delivery, wages, labour cost, AI cost per unit, per-vendor contracts and finance, margin, type choice, competition,
wage targets and services spend.

Prototype: ``phase7_sim.py`` S9 (lines 318-324), S10 (lines 325-361), S11b (lines 370-401), S11c (lines 402-411) and
S11d (lines 412-414). Spec modules: 8 Finance (delivered work, wages, labour cost, revenue, margin, services spend),
7 AI capability (``AICostPerUnit``), 2 Contracts (vintages, durations, price index, type choice, signings) and
4 Labour market (wage-index targets).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EFFORT, EMP_OF, LEVELS, POOL, SECTORS, TYPES, UNITS, VENDORS
from aisim.params import Reanchor
from aisim.state import Mat, State, Vec
from aisim.util import clamp, softmax


@dataclass(frozen=True, slots=True)
class Costs:
    """S9 intermediates."""

    capu: Vec
    Delivered: Vec
    Wage: Mat
    LabourCost: Vec
    AIShockNow: float
    AICostPerUnit: float


@dataclass(frozen=True, slots=True)
class VendorTerms:
    """S10 intermediates of one vendor (the prototype's ``VF[v]`` as S10 leaves it)."""

    vu: tuple[str, ...]
    shock: float
    Anchor: float
    PU: float
    Vi: float
    nm: float
    dev: float
    DevEff: float
    Power: float
    Disc: float
    Book: float
    Glide: Vec
    Dnew: Vec
    AvgDur: Vec
    PNew: Vec
    AvgP: Vec
    ExpLeg: Vec
    ExpNew: Vec
    ExpRate: float
    IdxVol: Vec
    AvgIdx: float
    VendDel: float
    BaseRev: float
    BasePriceAvg: float
    Revenue: float
    AICost: float
    VisaCost: float
    VLab: float
    LabRaw: float


@dataclass(frozen=True, slots=True)
class Contracts:
    """S10 intermediates."""

    Pass: Vec
    VF: dict[str, VendorTerms]


@dataclass(frozen=True, slots=True)
class VendorBook:
    """S11b intermediates of one vendor (the fields the prototype adds to ``VF[v]`` in S11b)."""

    SignRate: float
    SalesCost: float
    VendorCost: float
    Margin: float
    CostIdx: float
    wv: float
    TypeShare: Vec
    Sign: Vec
    VShare: float
    ShareLoss: float
    Afford: float
    DiscTarget: float
    CostProgTarget: float
    EffortShare: float


@dataclass(frozen=True, slots=True)
class VendorBooks:
    """S11b intermediates."""

    VB: dict[str, VendorBook]


@dataclass(frozen=True, slots=True)
class WageTargets:
    """S11c intermediates."""

    WITarget: Vec


@dataclass(frozen=True, slots=True)
class Spend:
    """S11d intermediates."""

    RevenueTot: float
    AICostCons: float
    ServicesSpend: float


def costs(
    pr: Mapping[str, float],
    st: State,
    y: float,
    W: Mapping[str, float],
    CompE: Vec,
    EffStaffE: Vec,
    *,
    reanchor: Reanchor | None = None,
    nz: Mapping[str, float] | None = None,
) -> Costs:
    """S9: delivery, wages and labour cost.

    - ``Delivered[u]`` splits the employer's completion over its units by effective staff ``capu``.
    - ``Wage[u][l]`` is ``BaseWage_u x WageMult_l x WI[u]`` (USD a year); ``LabourCost[u]`` charges it on headcount
      plus onboarding staff.
    - ``AICostPerUnit`` falls from ``AICost2024`` at ``AICostDecline`` a year, times ``AIShockMult`` inside the
      half-open shock window.

    Two-phase runs (``aisim.perturb``): with ``reanchor``, ``AICostPerUnit`` continues from its base value at
    ``reanchor.Y`` when ``AICostDecline`` differs from the base. The noise factor ``nz["aicost"]`` multiplies it.
    """
    H, O, WI = st["H"], st["O"], st["WI"]
    capu = {u: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for l in LEVELS) for u in UNITS}
    Delivered = {u: CompE[EMP_OF[u]] * capu[u] / max(EffStaffE[EMP_OF[u]], 1e-9) for u in UNITS}
    Wage = {u: {l: pr["BaseWage_" + u] * pr["WageMult_" + l] * WI[u] for l in LEVELS} for u in UNITS}
    LabourCost = {u: sum((H[u][l] + O[u][l]) * Wage[u][l] for l in LEVELS) for u in UNITS}
    AIShockNow = pr["AIShockMult"] if pr["AIShockStart"] <= y < pr["AIShockEnd"] else 1.0
    if reanchor is not None and pr["AICostDecline"] != reanchor.AICostDecline:
        decline = reanchor.cost_decay * (1 - pr["AICostDecline"]) ** (y - reanchor.Y)
        AICostPerUnit = pr["AICost2024"] * decline * AIShockNow
    else:
        AICostPerUnit = pr["AICost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShockNow
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
    pr: Mapping[str, float],
    st: State,
    y: float,
    Pe: Vec,
    UnitIn: Vec,
    hires: Mat,
    cost: Costs,
    *,
    nz: Mapping[str, float] | None = None,
) -> Contracts:
    """S10: per-vendor contracts and finance.

    - ``Pass[k]`` is the share of AI gains contract type ``k`` passes to the client (fixed price none, effort-billed
      all, managed services ``MSGlideShare``, outcome-based ``OBGainShare``).
    - Price uncertainty ``PU`` is the client-perceived productivity trend; clients anchor new prices on
      ``1 / (ClientP x (1 + PriceHorizon x PU))`` (``Anchor``).
    - Vendor margin deviation from normal, beyond a ``Deadband``, is ``DevEff``; bargaining ``Power`` rises with it.
    - New contract durations ``Dnew`` shorten with ``PU`` and lengthen with ``Power`` (floored at ``MinDur``). Shorter
      terms reprice faster: loop R8 (repricing acceleration).
    - Contract vintages: legacy contracts expire over their base durations, new ones over their average duration;
      ``ExpRate`` is total expiry over the book. ``AvgIdx`` is the book's price index (effort-billed volume deflated
      by productivity), so T&M revenue falls as productivity rises (B2).
    - Revenue is delivered work at unit prices times ``AvgIdx``, less any price shock. Costs: AI on the automated
      share of delivered work, visa fees and compliance (OIT only), and labour net of the cost programme.

    The noise factor ``nz["anchor"]`` (two-phase runs, ``aisim.perturb``) multiplies ``Anchor``.
    """
    H = st["H"]
    Delivered, LabourCost, AICostPerUnit = cost.Delivered, cost.LabourCost, cost.AICostPerUnit
    Pass = {"FP": 0.0, "TM": 1.0, "MS": pr["MSGlideShare"], "SA": 1.0, "OB": pr["OBGainShare"]}
    VF: dict[str, VendorTerms] = {}
    for v in VENDORS:
        vu = tuple(u for u in UNITS if EMP_OF[u] == v)
        shock = pr["PriceShock_" + v] if y >= pr["PriceShockYear"] else 0.0
        CP = st["ClientP"][v]
        PU = max(0.0, (CP - st["ClientPRef"][v]) / (st["ClientPRef"][v] * pr["TrendTime"]))
        Anchor = (1 / (CP * (1 + pr["PriceHorizon"] * PU))) ** pr["PassThrough"]  # clients price in the trend
        if nz is not None and "anchor" in nz:
            Anchor = Anchor * nz["anchor"]
        # Phase 8 (E2a): the annuity share of new TM signings carries Anchor ** AnnuityAnchorW. At AnnuityShare 0 this
        # is exactly 1.0 (Anchor ** w is finite, 0 x it is 0.0), so PNew_TM is Phase 7's bit for bit.
        EffMult_TM = (1 - pr["AnnuityShare"]) + pr["AnnuityShare"] * Anchor ** pr["AnnuityAnchorW"]
        Vi = st["Viab"][v]
        nm = pr["NormalMargin_" + v]
        dev = Vi - nm
        DevEff = (
            (dev - pr["Deadband"])
            if dev > pr["Deadband"]
            else ((dev + pr["Deadband"]) if dev < -pr["Deadband"] else 0.0)
        )
        Power = clamp(1 + pr["PowerSens"] * dev, pr["PowerMin"], pr["PowerMax"])
        Disc = st["Disc"][v]
        Leg, NV, ND, NP = st["Leg"][v], st["NewV"][v], st["NewD"][v], st["NewP"][v]
        Book = sum(Leg[k] + NV[k] for k in TYPES)
        Glide = {k: (Pass[k] * PU if k in ("MS", "OB") else 0.0) for k in TYPES}
        Dnew = {
            k: max(pr["MinDur"], pr["BaseDur_" + k] / (1 + pr["DurPUSens"] * PU) * Power ** pr["DurPowerElast"])
            for k in TYPES
        }
        AvgDur = {k: (ND[k] / NV[k] if NV[k] > 1e-12 else Dnew[k]) for k in TYPES}
        PNew = {
            k: (EffMult_TM * (1 - Disc) if k == "TM" else (1 - Disc) if k in EFFORT else Anchor * (1 - Disc))
            for k in TYPES
        }
        AvgP = {k: (NP[k] / NV[k] if NV[k] > 1e-12 else PNew[k]) for k in TYPES}
        ExpLeg = {k: Leg[k] / pr["BaseDur_" + k] for k in TYPES}
        ExpNew = {k: NV[k] / AvgDur[k] for k in TYPES}
        ExpRate = sum(ExpLeg[k] + ExpNew[k] for k in TYPES) / max(Book, 1e-12)
        IdxVol = {k: ((Leg[k] + NP[k]) / Pe[v] if k in EFFORT else Leg[k] + NP[k]) for k in TYPES}
        AvgIdx = sum(IdxVol.values()) / max(Book, 1e-12)
        VendDel = sum(Delivered[u] for u in vu)
        BaseRev = sum(Delivered[u] * pr["Price_" + u] * pr["PriceMult_" + v] for u in vu)
        BasePriceAvg = sum(UnitIn[u] * pr["Price_" + u] for u in vu) * pr["PriceMult_" + v] / sum(UnitIn[u] for u in vu)
        Revenue = BaseRev * AvgIdx * (1 - shock)
        AICost = AICostPerUnit * VendDel * (1 - 1 / Pe[v])
        VisaCost = (
            (
                sum(hires["OV"][l] for l in LEVELS) * pr["VisaFeePerHire"]
                + sum(H["OV"][l] for l in LEVELS) * pr["VisaComplianceCost"]
            )
            if v == "OIT"
            else 0.0
        )
        VLab = sum(LabourCost[u] for u in vu) * (1 - st["CostProg"][v])
        VF[v] = VendorTerms(
            vu=vu,
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
            LabRaw=sum(LabourCost[u] for u in vu),
        )
    return Contracts(Pass=Pass, VF=VF)


def vendor_books(
    pr: Mapping[str, float],
    st: State,
    Pe: Vec,
    CompS: Vec,
    CS: Vec,
    TTFratio: Vec,
    SignS: Mat,
    con: Contracts,
) -> VendorBooks:
    """S11b: vendor book turnover, sales cost, margin, type choice and competition.

    - ``SignRate`` is the completion-weighted rate at which the vendor's sector work is re-signed (S11a). Sales cost is
      ``SalesCostRate`` of revenue per unit of signing rate. ``Margin`` is revenue less all costs over revenue; it feeds
      ``Viab``: loop R6 (vendor death spiral) through sourcing risk, and B6 (right-sizing) through the cost programme.
    - Type choice: each contract type's score blends the client utility (price uncertainty over the term, distrust of
      effort billing (B2, client side), and for staff augmentation the onshore time to fill) and the vendor's profit
      utility, weighted by bargaining power; ``TypeShare`` is the logit and ``Sign`` the signings by type.
    - ``ShareLoss`` against the reference share, and excess margin, set the discount target: loop B12 (price
      competition). Margin below normal sets the cost programme target: loop B6 (right-sizing).
    - ``EffortShare`` is the effort-billed share of the book (it brakes adoption in S12).
    """
    Pass, VF = con.Pass, con.VF
    VW, ClientP = st["VW"], st["ClientP"]
    VB: dict[str, VendorBook] = {}
    for v in VENDORS:
        f = VF[v]
        vol = sum(VW[x][v] * CompS[x] for x in SECTORS)
        signvol = sum(SignS[x][v] * CompS[x] for x in SECTORS)
        SignRate = signvol / vol if vol > 1e-9 else f.ExpRate
        SalesCost = pr["SalesCostRate"] * f.Revenue * SignRate
        VendorCost = f.VLab + f.VisaCost + f.AICost + st["Overhead"][v] + SalesCost
        Margin = (f.Revenue - VendorCost) / max(f.Revenue, 1.0)
        CostIdx = (VendorCost / max(f.VendDel, 1e-9)) / max(f.BaseRev / max(f.VendDel, 1e-9), 1e-9)
        wv = clamp(pr["BargainW0"] * f.Power, 0.1, 0.9)
        wc = 1 - wv
        Score: Vec = {}
        for k in TYPES:
            D = f.Dnew[k]
            PU = f.PU
            Ucons = -pr["ConsSens"] * (1 - Pass[k]) * PU * D / 2
            if k in EFFORT:
                Ucons -= pr["ConsSens"] * pr["EffortDistrust"] * (1 - 1 / ClientP[v])
            if k == "SA":
                Ucons += pr["SATTFSens"] * clamp(TTFratio["ON"] - 1, -1.0, 2.0)
            Rterm = (f.PNew[k] / Pe[v] * (1 - PU * D / 2)) if k in EFFORT else (f.PNew[k] * (1 - Pass[k] * PU * D / 2))
            Profit = Rterm - CostIdx * (1 - PU * D / 2)
            Uvend = pr["VendSens"] * (Profit - f.nm) / f.nm
            Score[k] = pr[f"TypeASC_{v}_{k}"] + wc * Ucons + wv * Uvend
        TypeShare = softmax(Score)
        Sign = {k: f.Book * SignRate * TypeShare[k] for k in TYPES}
        VShare = sum(VW[x][v] * CS[x] for x in SECTORS)
        ShareLoss = max(0.0, (st["ShareRef"][v] - VShare) / max(st["ShareRef"][v], 1e-12))
        Afford = clamp(f.Vi / f.nm, 0.0, 1.0)
        DiscTarget = clamp(
            pr["ShareLossSens"] * ShareLoss * Afford + pr["RivalSens"] * max(0.0, f.DevEff), 0.0, pr["MaxDisc"]
        )
        CostProgTarget = clamp(pr["CostProgramSens"] * max(0.0, -f.DevEff), 0.0, pr["MaxSavings"])
        EffortShare = sum(st["Leg"][v][k] + st["NewV"][v][k] for k in EFFORT) / max(f.Book, 1e-12)
        VB[v] = VendorBook(
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


def wage_targets(pr: Mapping[str, float], st: State, VF: Mapping[str, VendorTerms]) -> WageTargets:
    """S11c: wage-index targets.

    With endogenous wages, each unit's target rises with labour-market tightness (normal over perceived unemployment,
    to the power ``WageElasticity``) and, for vendors with margin below normal, falls with wage restraint; it is kept
    within ``WageMin``-``WageMax``. Tight markets raise wages and so make AI relatively cheaper: the wage half of
    loop R5 (shortage accelerates AI), closed in S12. With ``WagesEndogenous`` off the target is 1.
    """
    WITarget: Vec = {}
    for u in UNITS:
        if pr["WagesEndogenous"] >= 0.5:
            rgn = POOL[u]
            tight = (pr["NormalUnempRate_" + rgn] / max(st["PUS"][rgn], 1e-6)) ** pr["WageElasticity"]
            e = EMP_OF[u]
            restraint = (1 - pr["WageRestraint"] * max(0.0, -VF[e].DevEff)) if e in VENDORS else 1.0
            WITarget[u] = clamp(tight * restraint, pr["WageMin"], pr["WageMax"])
        else:
            WITarget[u] = 1.0
    return WageTargets(WITarget=WITarget)


def spend(pr: Mapping[str, float], Pe: Vec, cost: Costs, VF: Mapping[str, VendorTerms]) -> Spend:
    """S11d: total vendor revenue and consumer IT services spend.

    Services spend is in-house labour cost, GCC labour cost plus ``GCCOverhead``, vendor revenue, and the AI cost of
    the consumers' own automated work.
    """
    Delivered, LabourCost = cost.Delivered, cost.LabourCost
    RevenueTot = sum(VF[v].Revenue for v in VENDORS)
    AICostCons = cost.AICostPerUnit * ((1 - 1 / Pe["IH"]) * Delivered["IH"] + (1 - 1 / Pe["GCC"]) * Delivered["GCC"])
    ServicesSpend = LabourCost["IH"] + LabourCost["GCC"] * (1 + pr["GCCOverhead"]) + RevenueTot + AICostCons
    return Spend(RevenueTot=RevenueTot, AICostCons=AICostCons, ServicesSpend=ServicesSpend)
