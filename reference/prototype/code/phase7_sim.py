"""Phase 7 model - the Phase 6b model with three changes needed to calibrate against 2024-2026 history and run scenarios:
1) DemandGrowth: underlying real growth of IT work, budgets and graduate supply (G(t) = (1+DemandGrowth)^(t-2024));
2) AI rebased to 2024: 2024 already contains AI use (A0, AC0). Productivity, junior cut, consumer exposure and AI build
   demand are measured relative to their 2024 levels, so the 2024 state is still the calibrated steady state;
3) Verif: one verification-overhead parameter for all work types (fitted to observed AI price deflation).

Units (employment units)          employer   located   hires from
  IH     consumer in-house        IH         Onshore   Onshore pool
  GCC    consumer captive         GCC        India     India pool
  VI     Indian IT offshore       OIT        India     India pool
  OV     Indian IT onsite visa    OIT        Onshore   India pool (visa holders)
  OL     Indian IT onsite local   OIT        Onshore   Onshore pool
  SI_IN  global SI, India centre  GSI        India     India pool
  SI_ON  global SI, onshore       GSI        Onshore   Onshore pool
  BQ     boutique                 BQ         Onshore   Onshore pool
Euler integration, Year = 2024 + t.
"""
import json, math

UNITS = ("IH", "GCC", "VI", "OV", "OL", "SI_IN", "SI_ON", "BQ")
EMPLOYERS = ("IH", "GCC", "OIT", "GSI", "BQ")
VENDORS = ("OIT", "GSI", "BQ")
EMP_OF = {"IH": "IH", "GCC": "GCC", "VI": "OIT", "OV": "OIT", "OL": "OIT", "SI_IN": "GSI", "SI_ON": "GSI", "BQ": "BQ"}
REGIONS = ("IN", "ON")
LEVELS = ("J", "M", "S")
POOL = {"IH": "ON", "GCC": "IN", "VI": "IN", "OV": "IN", "OL": "ON", "SI_IN": "IN", "SI_ON": "ON", "BQ": "ON"}
LOC = {"IH": "ON", "GCC": "IN", "VI": "IN", "OV": "ON", "OL": "ON", "SI_IN": "IN", "SI_ON": "ON", "BQ": "ON"}
EMP_POOL = {"IH": "ON", "GCC": "IN", "OIT": "IN", "GSI": "IN", "BQ": "ON"}
SWITCHERS = ("IH", "GCC", "VI", "OL", "SI_IN", "SI_ON", "BQ")     # visa holders do not switch
TYPES = ("FP", "TM", "MS", "SA", "OB")
EFFORT = ("TM", "SA")
SECTORS = ("FIN", "LEG", "MED", "GOV", "MFG", "LOG", "RET")
WTYPES = ("APP", "DATA", "SEC", "GOVN", "SUP", "EUS")
E = math.e

P = dict(
    # Phase 1-2
    BaseDemand=100_000.0, WorkPerPerson=1.0, TargetClearanceTime=0.5, MinCompletionTime=0.25,
    AbandonTolerance=1.5, AbandonTime=1.0, LayoffAdjTime=0.25, MinLayoffTime=0.25, HireAdjTime=0.5,
    PerceptionTime=1.0, g=0.10, p=0.03, q=0.40, A0=0.05,
    MinAdoptionTime=0.0625, JevonsEps=0.0, JevonsCap=2.0, DemandStep=0.0, StepYear=2028.0,
    W_J=0.6, W_M=1.0, W_S=1.4, Share0_J=0.19, Share0_M=0.25, Share0_S=0.56, JuniorCut=0.5,
    TimeInJunior=3.0, TimeInMid=5.0, PromoFillTime=0.125,
    QuitRate_J=0.15, QuitRate_M=0.10, QuitRate_S=0.08,
    LeaveITRate_J=0.05, LeaveITRate_M=0.06, LeaveITRate_S=0.04, RetireRate_S=0.033,
    OnboardTime=0.25, OnboardProductivity=0.5, CancelTime=0.25,
    m=4.0, alpha=0.5, MinFillTime=0.0625, RecoveryTime=0.33,
    BaseLeaveFrac_J=0.05, BaseLeaveFrac_M=0.10, BaseLeaveFrac_S=0.20, SeekerExitRate=0.10,
    UnempPerceptionTime=0.5, StudyTime=4.0, StudentPerceptionTime=2.0, EnrolSensitivity=1.0,
    ExtEntryRate_M=0.05, ExtEntryRate_S=0.05, ExtEntryMax=3.0,
    # Phase 3
    BaseEnrolment_IN=3900.0, BaseEnrolment_ON=2000.0,
    NormalUnempRate_IN=0.0495, NormalUnempRate_ON=0.0534,
    NormalTTF_IN_M=0.606, NormalTTF_IN_S=0.354, NormalTTF_ON_M=0.631, NormalTTF_ON_S=0.064,
    GCCRampStart=2027.0, GCCRampEnd=2031.0,
    OnsiteShare0=0.25, OffshoreShiftSens=0.5, VisaMix0=0.6, VisaMixSens=0.8,
    VTBase=0.3, VTEnd=0.3, VTRampStart=2027.0, VTRampEnd=2031.0, TightPerceptionTime=1.0,
    BaseVisaCap=8000.0, VisaTenure=6.0, ConvRate=0.05,
    Wage_IH=1.0, Wage_GCC=1.3, Wage_VI=1.0, Wage_OV=1.0, Wage_OL=0.95, Wage_SI_IN=1.1, Wage_SI_ON=1.05, Wage_BQ=1.1,
    SwitchRate=0.04, SwitchElasticity=2.0, SwitchMax=2.0,
    # Phase 4 (per unit and per vendor)
    BaseWage_IH=125_000.0, BaseWage_GCC=26_000.0, BaseWage_VI=20_000.0, BaseWage_OV=90_000.0, BaseWage_OL=120_000.0,
    BaseWage_SI_IN=22_000.0, BaseWage_SI_ON=130_000.0, BaseWage_BQ=140_000.0,
    WageMult_J=0.6, WageMult_M=1.0, WageMult_S=1.5,
    Price_VI=39_880.0, Price_OV=150_000.0, Price_OL=150_000.0, Price_SI_IN=45_000.0, Price_SI_ON=170_000.0, Price_BQ=190_000.0,
    PriceMult_OIT=1.0, PriceMult_GSI=1.0, PriceMult_BQ=1.0,                 # calibrated
    GSIOffshore=0.5,
    VisaFeePerHire=100_000.0, VisaComplianceCost=5_000.0,
    AICost2024=8_000.0, AICostDecline=0.15, AIShockMult=1.0, AIShockStart=2030.0, AIShockEnd=2032.0,
    OverheadRate_OIT=0.08, OverheadRate_GSI=0.10, OverheadRate_BQ=0.10, OverheadAdjTime=2.0,
    PassThrough=1.0, ClientPerceptionTime=1.5,
    PriceShock_OIT=0.0, PriceShock_GSI=0.0, PriceShock_BQ=0.0, PriceShockYear=2028.0,
    ViabilityTime=2.0, Deadband=0.02, ExitThreshold=0.0,
    TargetMargin_OIT=0.18, TargetMargin_GSI=0.15, TargetMargin_BQ=0.12,
    NormalMargin_OIT=0.18, NormalMargin_GSI=0.15, NormalMargin_BQ=0.12,   # calibrated
    CostProgramSens=1.5, MaxSavings=0.15, CostProgramTime=2.0,
    WagesEndogenous=1.0, WageElasticity=0.25, WageRestraint=1.0, WageAdjTime=2.0, WageMin=0.85, WageMax=1.3,
    # Phase 5 contracts
    BaseDur_FP=2.5, BaseDur_TM=1.5, BaseDur_MS=6.0, BaseDur_SA=1.0, BaseDur_OB=3.0,
    MinDur=0.25, DurPUSens=15.0, DurPowerElast=1.0, TrendTime=2.0,
    MSGlideShare=0.5, OBGainShare=0.5,
    ConsSens=10.0, EffortDistrust=0.5, VendSens=2.0, SATTFSens=0.5, BargainW0=0.5, PowerSens=3.0, PowerMin=0.5, PowerMax=1.2,
    SalesCostRate=0.05,
    # Phase 5 sourcing
    IHReviewTime=4.0, GCCReviewTime=5.0, Contest=0.5, SrcPerceptionTime=1.5,
    SrcCostSens=3.0, GCCOverhead=0.5, CostRef=131_000.0,
    ViabSens=5.0, ExitPenalty=7.5, VisaRiskSens=1.0, CapSens=0.5, GCCAppealEnd=0.0,
    ShareRefTime=4.0, ShareLossSens=0.5, RivalSens=3.0, MaxDisc=0.4, DiscAdjTime=1.0,
    # Phase 6a
    CostAdoptElast=0.3, CEMin=0.5, CEMax=1.5,
    pC=0.02, qC=0.30, AC0=0.05, aL_2024=0.05, aL_max=0.35, LOBAdjTime=2.0,
    CreditCost2024=30_000.0, ReinvestFrac=0.2, ReinvestAdoptSens=0.5,
    RegScenario=1.0, RegStart=2027.9, RegEnd=2028.6,
    AppLife=8.0, AppDisplacement=0.6, RetireAccel=1.0, NewAppWeight=0.5, MigWeight=0.3, SupPortShare=0.8,
    SeatAdjTime=2.0, BaseSeatPrice=1_500.0, AISeatPrice=360.0, pAtt=0.05, qAtt=0.5, Att0=0.02,
    CloudPerBFY=13_000.0, CloudAISens=0.5, Leakage=0.2,
    BuildRate=0.6, RunRate=0.10, GovRegSens=2.0, CostPerceptionTime=1.5,
    CostPerBFY0=84_000.0, NormalUtil=0.95, ApprovalSens=2.0, MinApproval=0.2, BudgetCycle=1.0,
    ITBudgetGrowth=0.0, BudgetShock=0.0, BudgetShockStart=2030.0, BudgetShockEnd=2032.0,
    CyberEnd=1.0, CyberStart=2026.0, CyberRampEnd=2030.0,
    # Phase 6b: delivery adoption per employer (B2 brake, competitive push)
    AdoptMult_IH=0.8, AdoptMult_GCC=1.0, AdoptMult_OIT=1.0, AdoptMult_GSI=1.1, AdoptMult_BQ=1.2,
    TMBrake=0.4, PushSens=2.0,
    # Phase 6b: sourcing by sector
    RegFitSens=1.0, GCCAISens=0.5, FreezeSourcing=0.0,
    # Phase 7
    DemandGrowth=0.03, Verif=0.05, AdoptC0=0.0, PriceHorizon=0.0, GCCMomentum=0.0, GCCFadeEnd=2035.0, GCCAppealKeep=0.5, VerifDecline=0.05, DemandGrowthLate=-1.0, LateYear=2026.5,
    Burn=0.0,   # calibration-only switch: visa cap and IT seats scale with G during the growth-path burn-in
)
P.update(A0=0.35, AC0=0.30, Att0=0.01, GCCRampStart=2024.0, GCCRampEnd=2028.0)
EMPS6 = dict(OffExp={"IH": 0.0, "GCC": 0.3, "OIT": 0.8, "GSI": 0.5, "BQ": 0.0})
MIX0 = {"OIT": {"FP": 0.35, "TM": 0.30, "MS": 0.22, "SA": 0.10, "OB": 0.03},
        "GSI": {"FP": 0.38, "TM": 0.22, "MS": 0.30, "SA": 0.05, "OB": 0.05},
        "BQ": {"FP": 0.30, "TM": 0.45, "MS": 0.05, "SA": 0.17, "OB": 0.03}}
SRC0 = {"FIN": {"IH": 0.22, "GCC": 0.18, "OIT": 0.35, "GSI": 0.20, "BQ": 0.05},
        "LEG": {"IH": 0.40, "GCC": 0.02, "OIT": 0.15, "GSI": 0.25, "BQ": 0.18},
        "MED": {"IH": 0.35, "GCC": 0.06, "OIT": 0.30, "GSI": 0.20, "BQ": 0.09},
        "GOV": {"IH": 0.45, "GCC": 0.01, "OIT": 0.10, "GSI": 0.36, "BQ": 0.08},
        "MFG": {"IH": 0.25, "GCC": 0.12, "OIT": 0.40, "GSI": 0.18, "BQ": 0.05},
        "LOG": {"IH": 0.30, "GCC": 0.08, "OIT": 0.40, "GSI": 0.17, "BQ": 0.05},
        "RET": {"IH": 0.30, "GCC": 0.10, "OIT": 0.42, "GSI": 0.14, "BQ": 0.04}}
SEC6 = dict(
    SectorShare={"FIN": 0.25, "LEG": 0.03, "MED": 0.12, "GOV": 0.18, "MFG": 0.17, "LOG": 0.08, "RET": 0.17},
    LOBWage={"FIN": 90_000.0, "LEG": 85_000.0, "MED": 65_000.0, "GOV": 70_000.0, "MFG": 55_000.0, "LOG": 50_000.0, "RET": 40_000.0},
    RegDragLevel={"FIN": 0.30, "LEG": 0.20, "MED": 0.30, "GOV": 0.35, "MFG": 0.10, "LOG": 0.10, "RET": 0.05},
)
WT6 = dict(
    Mix={"APP": 0.30, "DATA": 0.12, "SEC": 0.10, "GOVN": 0.05, "SUP": 0.33, "EUS": 0.10},
    a2024={"APP": 0.25, "DATA": 0.35, "SEC": 0.15, "GOVN": 0.10, "SUP": 0.30, "EUS": 0.35},
    amax={"APP": 0.60, "DATA": 0.80, "SEC": 0.45, "GOVN": 0.35, "SUP": 0.70, "EUS": 0.80},
    s={"APP": 5.0, "DATA": 5.0, "SEC": 4.0, "GOVN": 3.0, "SUP": 5.0, "EUS": 5.0},
    v={"APP": 0.05, "DATA": 0.05, "SEC": 0.05, "GOVN": 0.05, "SUP": 0.05, "EUS": 0.05},
    BuildMix={"APP": 0.35, "DATA": 0.35, "SEC": 0.10, "GOVN": 0.15, "SUP": 0.05, "EUS": 0.0},
)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def ramp(year, start, end, v0, v1):
    return v0 + (v1 - v0) * clamp((year - start) / (end - start), 0.0, 1.0)


def softmax(d):
    mx = max(d.values()); ez = {k: E ** (v - mx) for k, v in d.items()}; z = sum(ez.values())
    return {k: ez[k] / z for k in d}


def run(init, ai_on=True, dt=1/16, stop=16.0, record_every=0.25, **over):
    pr = dict(P); pr.update(over)
    st = json.loads(json.dumps(init))
    if pr["GCCMomentum"] != 0.0:     # GCC build-out decided before 2024 and still being executed: tilt the perceived shares
        for x in SECTORS:
            lg = {e: math.log(max(st["SrcPerc"][x][e], 1e-12)) + (pr["GCCMomentum"] if e == "GCC" else 0.0) for e in EMPLOYERS}
            st["SrcPerc"][x] = softmax(lg)
    rows = []; n = int(round(stop / dt)); rk = max(1, int(round(record_every / dt)))
    mins = {}
    t = 0.0
    for step in range(n + 1):
        y = 2024 + t
        H, O, V, R, U = st["H"], st["O"], st["V"], st["R"], st["U"]
        W = {l: pr["W_" + l] for l in LEVELS}
        # ---- capability by work type and employer ----
        aW = {w: max(0.0, WT6["amax"][w] - (WT6["amax"][w] - WT6["a2024"][w]) * (1 - pr["g"]) ** (y - 2024)) for w in WTYPES}
        VerifNow = pr["Verif"] * (1 - pr["VerifDecline"]) ** (y - 2024)          # verification overhead falls as models get more reliable
        PAI = {w: 1 / ((1 - aW[w]) + aW[w] / WT6["s"][w] + aW[w] * VerifNow) for w in WTYPES}
        PAI0 = {w: 1 / ((1 - WT6["a2024"][w]) + WT6["a2024"][w] / WT6["s"][w] + WT6["a2024"][w] * pr["Verif"]) for w in WTYPES}
        Aemp = st["A"]
        dgl = pr["DemandGrowthLate"] if pr["DemandGrowthLate"] > -0.5 else pr["DemandGrowth"]     # scenario lever after LateYear
        G = (1 + pr["DemandGrowth"]) ** (min(y, pr["LateYear"]) - 2024) * (1 + dgl) ** max(0.0, y - pr["LateYear"])
        Pew = {e: {w: (Aemp[e] * PAI[w] + (1 - Aemp[e])) / (pr["A0"] * PAI0[w] + (1 - pr["A0"])) if ai_on else 1.0 for w in WTYPES}
               for e in EMPLOYERS}
        # ---- work allocation by sector: who holds each sector's work ----
        EmpShare = {x: {"IH": st["IHW"][x], "GCC": st["GCCW"][x], **{v: st["VW"][x][v] for v in VENDORS}} for x in SECTORS}
        BL = st["BL"]
        BLs = {x: sum(BL[x][w] for w in WTYPES) for x in SECTORS}
        BLe = {e: sum(EmpShare[x][e] * BLs[x] for x in SECTORS) for e in EMPLOYERS}
        EffE = {e: sum(EmpShare[x][e] * BL[x][w] / Pew[e][w] for x in SECTORS for w in WTYPES) for e in EMPLOYERS}
        Pe = {e: (BLe[e] / EffE[e] if EffE[e] > 0 else 1.0) for e in EMPLOYERS}
        EffStaffE = {e: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for u in UNITS if EMP_OF[u] == e for l in LEVELS) for e in EMPLOYERS}
        CapE = {e: pr["WorkPerPerson"] * Pe[e] * EffStaffE[e] for e in EMPLOYERS}
        CompE = {e: min(CapE[e], BLe[e] / pr["MinCompletionTime"]) for e in EMPLOYERS}
        RateE = {e: (CompE[e] / BLe[e] if BLe[e] > 0 else 0.0) for e in EMPLOYERS}
        Comp = {x: {w: sum(EmpShare[x][e] * BL[x][w] * RateE[e] for e in EMPLOYERS) for w in WTYPES} for x in SECTORS}
        Aband = {x: {w: sum(EmpShare[x][e] * max(0.0, BL[x][w] * (1 - RateE[e] * pr["AbandonTolerance"])) for e in EMPLOYERS) / pr["AbandonTime"]
                     for w in WTYPES} for x in SECTORS}
        Completion = sum(CompE.values())
        EffortDone = sum(CompE[e] / Pe[e] for e in EMPLOYERS)
        P_all = Completion / EffortDone if EffortDone > 0 else 1.0
        CompS = {x: sum(Comp[x][w] for w in WTYPES) for x in SECTORS}
        CS = {x: (CompS[x] / Completion if Completion > 0 else SEC6["SectorShare"][x]) for x in SECTORS}
        TotBL = sum(BLs.values())
        # ---- level mix per employer ----
        ShareL, denomE = {}, {}
        for e in EMPLOYERS:
            sJ = pr["Share0_J"] * max(0.05, 1 - pr["JuniorCut"] * (max(0.0, Aemp[e] - pr["A0"]) if ai_on else 0.0))
            rest0 = pr["Share0_M"] + pr["Share0_S"]
            ShareL[e] = {"J": sJ, "M": pr["Share0_M"] * (1 - sJ) / rest0, "S": pr["Share0_S"] * (1 - sJ) / rest0}
            denomE[e] = sum(ShareL[e][l] * W[l] for l in LEVELS)
        # ---- visa lever, unit split inside employers, desired headcount ----
        VisaTight = ramp(y, pr["VTRampStart"], pr["VTRampEnd"], pr["VTBase"], pr["VTEnd"])
        dTight = st["TightPerc"] - pr["VTBase"]
        OnsiteShare = clamp(pr["OnsiteShare0"] * (1 - pr["OffshoreShiftSens"] * dTight), 0.0, 1.0)
        VisaMix = clamp(pr["VisaMix0"] * (1 - pr["VisaMixSens"] * dTight), 0.0, 1.0)
        UnitIn = {"IH": 1.0, "GCC": 1.0, "VI": 1 - OnsiteShare, "OV": OnsiteShare * VisaMix, "OL": OnsiteShare * (1 - VisaMix),
                  "SI_IN": pr["GSIOffshore"], "SI_ON": 1 - pr["GSIOffshore"], "BQ": 1.0}
        DesiredE = {e: BLe[e] / (pr["TargetClearanceTime"] * pr["WorkPerPerson"] * st["PerceivedP"][e]) for e in EMPLOYERS}
        Desired = {u: {l: DesiredE[EMP_OF[u]] * UnitIn[u] * ShareL[EMP_OF[u]][l] / denomE[EMP_OF[u]] for l in LEVELS} for u in UNITS}
        # ---- regional unemployment ----
        UnempRate, LeaveEffect, EnrolEffect = {}, {}, {}
        for r in REGIONS:
            unemp = sum(R[r][l] + U[r][l] for l in LEVELS)
            emp = sum(H[u][l] + O[u][l] for u in UNITS if POOL[u] == r for l in LEVELS)
            UnempRate[r] = unemp / (emp + unemp)
            norm = pr["NormalUnempRate_" + r]
            LeaveEffect[r] = clamp(st["PUS"][r] / norm, 0.5, 3.0)
            EnrolEffect[r] = clamp(1 - pr["EnrolSensitivity"] * (st["PUL"][r] / norm - 1), 0.4, 1.3)
        # ---- vacancies, promotions ----
        surplus, cancel, avail = {}, {}, {}
        for u in UNITS:
            surplus[u], cancel[u], avail[u] = {}, {}, {}
            for l in LEVELS:
                sp = H[u][l] + O[u][l] - Desired[u][l]
                c = (max(0.0, V[u][l] + sp) if sp <= 0 else V[u][l]) / pr["CancelTime"]
                cap = V[u][l] / pr["MinFillTime"]
                surplus[u][l] = sp; cancel[u][l] = min(c, cap); avail[u][l] = max(0.0, cap - cancel[u][l])
        promo = {u: {"J": 0.0,
                     "M": min(H[u]["J"] / pr["TimeInJunior"], V[u]["M"] / pr["PromoFillTime"], avail[u]["M"]),
                     "S": min(H[u]["M"] / pr["TimeInMid"], V[u]["S"] / pr["PromoFillTime"], avail[u]["S"])}
                 for u in UNITS}
        # ---- job switching: any two units in the same labour pool (visa holders excluded) ----
        sw = {u: {l: {"in": 0.0, "out": 0.0} for l in LEVELS} for u in UNITS}
        for r in REGIONS:
            us = [u for u in SWITCHERS if POOL[u] == r]
            for l in LEVELS:
                raw = {}
                for src in us:
                    others = [d_ for d_ in us if d_ != src]
                    vsum = sum(V[d_][l] for d_ in others)
                    for dst in others:
                        gw = min(pr["SwitchMax"], ((pr["Wage_" + dst] * st["WI"][dst]) / (pr["Wage_" + src] * st["WI"][src])) ** pr["SwitchElasticity"])
                        raw[(src, dst)] = H[src][l] * pr["SwitchRate"] * gw * V[dst][l] / vsum if vsum > 0 else 0.0
                for dst in us:
                    tot = sum(raw[(src, dst)] for src in us if src != dst)
                    room = max(0.0, avail[dst][l] - promo[dst][l])
                    scale = min(1.0, room / tot) if tot > 0 else 0.0
                    for src in us:
                        if src != dst:
                            f = raw[(src, dst)] * scale
                            sw[dst][l]["in"] += f; sw[src][l]["out"] += f
        expiry = {l: H["OV"][l] / pr["VisaTenure"] for l in LEVELS}
        conv = {l: H["OV"][l] * pr["ConvRate"] * (1 - VisaTight) for l in LEVELS}
        VisaCap = pr["BaseVisaCap"] * (1 - VisaTight) * (G if pr["Burn"] >= 0.5 else 1.0)
        fl = {u: {} for u in UNITS}
        for u in UNITS:
            for l in LEVELS:
                quits = H[u][l] * pr["QuitRate_" + l]
                leave = H[u][l] * pr["LeaveITRate_" + l]
                retire = H[u][l] * pr["RetireRate_S"] if l == "S" else 0.0
                promo_out = promo[u]["M"] if l == "J" else (promo[u]["S"] if l == "M" else 0.0)
                visa_out = (expiry[l] + conv[l]) if u == "OV" else 0.0
                netloss = quits + leave + retire + promo_out + sw[u][l]["out"] + visa_out
                sp = surplus[u][l]
                if sp <= 0:
                    openings = max(0.0, netloss + (-sp - V[u][l]) / pr["HireAdjTime"]); layoffs = 0.0
                else:
                    openings = 0.0
                    layoffs = min(max(0.0, sp / pr["LayoffAdjTime"] - netloss), H[u][l] / pr["MinLayoffTime"])
                fl[u][l] = dict(quits=quits, leave=leave, retire=retire, promo_out=promo_out, openings=openings,
                                layoffs=layoffs, onboard=O[u][l] / pr["OnboardTime"])
        hires = {u: {l: 0.0 for l in LEVELS} for u in UNITS}
        for r in REGIONS:
            us = [u for u in UNITS if POOL[u] == r]
            for l in LEVELS:
                vsum = sum(V[u][l] for u in us)
                if vsum <= 0 or U[r][l] <= 0:
                    continue
                match = pr["m"] * U[r][l] ** pr["alpha"] * vsum ** (1 - pr["alpha"])
                for u in us:
                    room = max(0.0, avail[u][l] - promo[u][l] - sw[u][l]["in"])
                    hires[u][l] = min(match * V[u][l] / vsum, room)
                tot = sum(hires[u][l] for u in us)
                capU = U[r][l] / pr["MinFillTime"]
                if tot > capU:
                    for u in us:
                        hires[u][l] *= capU / tot
        ov_tot = sum(hires["OV"][l] for l in LEVELS)
        if ov_tot > VisaCap:
            for l in LEVELS:
                hires["OV"][l] *= VisaCap / ov_tot
        TTFr, ext = {}, {}
        for r in REGIONS:
            us = [u for u in UNITS if POOL[u] == r]
            TTFr[r], ext[r] = {}, {}
            for l in LEVELS:
                vs = sum(V[u][l] for u in us)
                fills = sum(hires[u][l] + promo[u][l] + sw[u][l]["in"] for u in us)
                TTFr[r][l] = vs / max(fills, 1.0)
                if l == "J":
                    ext[r][l] = 0.0
                else:
                    hsum = sum(H[u][l] for u in us)
                    ext[r][l] = pr["ExtEntryRate_" + l] * hsum * clamp(TTFr[r][l] / pr[f"NormalTTF_{r}_{l}"] - 1, 0.0, pr["ExtEntryMax"])
        pool = {r: {} for r in REGIONS}
        for r in REGIONS:
            for l in LEVELS:
                rec_out = R[r][l] / pr["RecoveryTime"]
                lf = clamp(pr["BaseLeaveFrac_" + l] * LeaveEffect[r], 0.0, 0.9)
                pool[r][l] = dict(rec_to_seek=rec_out * (1 - lf), rec_to_left=rec_out * lf,
                                  seek_exit=U[r][l] * pr["SeekerExitRate"] * LeaveEffect[r],
                                  rec_retire=R[r][l] * pr["RetireRate_S"] if l == "S" else 0.0,
                                  seek_retire=U[r][l] * pr["RetireRate_S"] if l == "S" else 0.0)
        Enrol = {r: pr["BaseEnrolment_" + r] * G * EnrolEffect[r] for r in REGIONS}
        Grad = {r: st["Pipeline"][r] / pr["StudyTime"] for r in REGIONS}
        TTFratio = {r: TTFr[r]["M"] / pr[f"NormalTTF_{r}_M"] for r in REGIONS}

        # ---- finance: delivery, wages, labour cost ----
        capu = {u: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for l in LEVELS) for u in UNITS}
        Delivered = {u: CompE[EMP_OF[u]] * capu[u] / max(EffStaffE[EMP_OF[u]], 1e-9) for u in UNITS}
        Wage = {u: {l: pr["BaseWage_" + u] * pr["WageMult_" + l] * st["WI"][u] for l in LEVELS} for u in UNITS}
        LabourCost = {u: sum((H[u][l] + O[u][l]) * Wage[u][l] for l in LEVELS) for u in UNITS}
        AIShockNow = pr["AIShockMult"] if pr["AIShockStart"] <= y < pr["AIShockEnd"] else 1.0
        AICostPerUnit = pr["AICost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShockNow
        # ---- per-vendor contracts and finance ----
        Pass = {"FP": 0.0, "TM": 1.0, "MS": pr["MSGlideShare"], "SA": 1.0, "OB": pr["OBGainShare"]}
        VF = {}
        for v in VENDORS:
            vu = [u for u in UNITS if EMP_OF[u] == v]
            shock = pr["PriceShock_" + v] if y >= pr["PriceShockYear"] else 0.0
            CP = st["ClientP"][v]
            PU = max(0.0, (CP - st["ClientPRef"][v]) / (st["ClientPRef"][v] * pr["TrendTime"]))
            Anchor = (1 / (CP * (1 + pr["PriceHorizon"] * PU))) ** pr["PassThrough"]   # clients price in the productivity trend
            Vi = st["Viab"][v]; nm = pr["NormalMargin_" + v]
            dev = Vi - nm
            DevEff = (dev - pr["Deadband"]) if dev > pr["Deadband"] else ((dev + pr["Deadband"]) if dev < -pr["Deadband"] else 0.0)
            Power = clamp(1 + pr["PowerSens"] * dev, pr["PowerMin"], pr["PowerMax"])
            Disc = st["Disc"][v]
            Leg, NV, ND, NP = st["Leg"][v], st["NewV"][v], st["NewD"][v], st["NewP"][v]
            Book = sum(Leg[k] + NV[k] for k in TYPES)
            Glide = {k: (Pass[k] * PU if k in ("MS", "OB") else 0.0) for k in TYPES}
            Dnew = {k: max(pr["MinDur"], pr["BaseDur_" + k] / (1 + pr["DurPUSens"] * PU) * Power ** pr["DurPowerElast"]) for k in TYPES}
            AvgDur = {k: (ND[k] / NV[k] if NV[k] > 1e-12 else Dnew[k]) for k in TYPES}
            PNew = {k: ((1 - Disc) if k in EFFORT else Anchor * (1 - Disc)) for k in TYPES}
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
            VisaCost = (sum(hires["OV"][l] for l in LEVELS) * pr["VisaFeePerHire"] + sum(H["OV"][l] for l in LEVELS) * pr["VisaComplianceCost"]) if v == "OIT" else 0.0
            VLab = sum(LabourCost[u] for u in vu) * (1 - st["CostProg"][v])
            VF[v] = dict(vu=vu, shock=shock, Anchor=Anchor, PU=PU, Vi=Vi, nm=nm, dev=dev, DevEff=DevEff, Power=Power, Disc=Disc,
                         Book=Book, Glide=Glide, Dnew=Dnew, AvgDur=AvgDur, PNew=PNew, AvgP=AvgP, ExpLeg=ExpLeg, ExpNew=ExpNew,
                         ExpRate=ExpRate, IdxVol=IdxVol, AvgIdx=AvgIdx, VendDel=VendDel, BaseRev=BaseRev, BasePriceAvg=BasePriceAvg,
                         Revenue=Revenue, AICost=AICost, VisaCost=VisaCost, VLab=VLab, LabRaw=sum(LabourCost[u] for u in vu))
        # ---- sourcing flows by sector (need vendor expiry rates) ----
        Src, SignS = {}, {}
        for x in SECTORS:
            IHTurn = st["IHW"][x] / pr["IHReviewTime"]; GCCTurn = st["GCCW"][x] / pr["GCCReviewTime"]
            VExp = {v: st["VW"][x][v] * VF[v]["ExpRate"] for v in VENDORS}
            Contested = pr["Contest"] * (IHTurn + GCCTurn + sum(VExp.values()))
            SignS[x] = {v: (1 - pr["Contest"]) * VExp[v] + Contested * st["SrcPerc"][x][v] for v in VENDORS}
            Src[x] = dict(IHTurn=IHTurn, GCCTurn=GCCTurn, VExp=VExp, Contested=Contested)
        # vendor book turnover, sales cost, margin, type choice, competition
        for v in VENDORS:
            f = VF[v]
            vol = sum(st["VW"][x][v] * CompS[x] for x in SECTORS)
            signvol = sum(SignS[x][v] * CompS[x] for x in SECTORS)
            f["SignRate"] = signvol / vol if vol > 1e-9 else f["ExpRate"]
            f["SalesCost"] = pr["SalesCostRate"] * f["Revenue"] * f["SignRate"]
            f["VendorCost"] = f["VLab"] + f["VisaCost"] + f["AICost"] + st["Overhead"][v] + f["SalesCost"]
            f["Margin"] = (f["Revenue"] - f["VendorCost"]) / max(f["Revenue"], 1.0)
            CostIdx = (f["VendorCost"] / max(f["VendDel"], 1e-9)) / max(f["BaseRev"] / max(f["VendDel"], 1e-9), 1e-9)
            wv = clamp(pr["BargainW0"] * f["Power"], 0.1, 0.9); wc = 1 - wv
            Score = {}
            for k in TYPES:
                D = f["Dnew"][k]; PU = f["PU"]
                Ucons = -pr["ConsSens"] * (1 - Pass[k]) * PU * D / 2
                if k in EFFORT:
                    Ucons -= pr["ConsSens"] * pr["EffortDistrust"] * (1 - 1 / st["ClientP"][v])
                if k == "SA":
                    Ucons += pr["SATTFSens"] * clamp(TTFratio["ON"] - 1, -1.0, 2.0)
                Rterm = (f["PNew"][k] / Pe[v] * (1 - PU * D / 2)) if k in EFFORT else (f["PNew"][k] * (1 - Pass[k] * PU * D / 2))
                Profit = Rterm - CostIdx * (1 - PU * D / 2)
                Uvend = pr["VendSens"] * (Profit - f["nm"]) / f["nm"]
                Score[k] = pr[f"TypeASC_{v}_{k}"] + wc * Ucons + wv * Uvend
            f["TypeShare"] = softmax(Score)
            f["Sign"] = {k: f["Book"] * f["SignRate"] * f["TypeShare"][k] for k in TYPES}
            f["VShare"] = sum(st["VW"][x][v] * CS[x] for x in SECTORS)
            ShareLoss = max(0.0, (st["ShareRef"][v] - f["VShare"]) / max(st["ShareRef"][v], 1e-12))
            Afford = clamp(f["Vi"] / f["nm"], 0.0, 1.0)
            f["ShareLoss"] = ShareLoss
            f["DiscTarget"] = clamp(pr["ShareLossSens"] * ShareLoss * Afford + pr["RivalSens"] * max(0.0, f["DevEff"]), 0.0, pr["MaxDisc"])
            f["CostProgTarget"] = clamp(pr["CostProgramSens"] * max(0.0, -f["DevEff"]), 0.0, pr["MaxSavings"])
            f["EffortShare"] = sum(st["Leg"][v][k] + st["NewV"][v][k] for k in EFFORT) / max(f["Book"], 1e-12)
        WITarget = {}
        for u in UNITS:
            if pr["WagesEndogenous"] >= 0.5:
                rgn = POOL[u]
                tight = (pr["NormalUnempRate_" + rgn] / max(st["PUS"][rgn], 1e-6)) ** pr["WageElasticity"]
                e = EMP_OF[u]
                restraint = (1 - pr["WageRestraint"] * max(0.0, -VF[e]["DevEff"])) if e in VENDORS else 1.0
                WITarget[u] = clamp(tight * restraint, pr["WageMin"], pr["WageMax"])
            else:
                WITarget[u] = 1.0
        RevenueTot = sum(VF[v]["Revenue"] for v in VENDORS)
        AICostCons = AICostPerUnit * ((1 - 1 / Pe["IH"]) * Delivered["IH"] + (1 - 1 / Pe["GCC"]) * Delivered["GCC"])
        ServicesSpend = LabourCost["IH"] + LabourCost["GCC"] * (1 + pr["GCCOverhead"]) + RevenueTot + AICostCons
        # ---- delivery adoption per employer: cost effect (R5), T&M brake (B2), competitive push ----
        AdoptE, CEe = {}, {}
        for e in EMPLOYERS:
            labpb = sum(LabourCost[u] for u in UNITS if EMP_OF[u] == e) / max(EffStaffE[e], 1e-9)
            CEe[e] = clamp(((labpb / pr["LabourCostPB0_" + e]) * (pr["AICost2024"] / AICostPerUnit)) ** pr["CostAdoptElast"], pr["CEMin"], pr["CEMax"])
            brake = (1 - pr["TMBrake"] * VF[e]["EffortShare"]) if e in VENDORS else 1.0
            push = (1 + pr["PushSens"] * VF[e]["ShareLoss"]) if e in VENDORS else 1.0
            Ae = Aemp[e]
            AdoptE[e] = min((pr["p"] * pr["AdoptMult_" + e] + pr["q"] * Ae) * CEe[e] * brake * push * (1 - Ae), (1 - Ae) / pr["MinAdoptionTime"]) if ai_on else 0.0
        # ---- consumer side (6a) ----
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
        BudgetGrowth = G * (1 + pr["ITBudgetGrowth"]) ** (y - 2024) * (1 - (pr["BudgetShock"] if pr["BudgetShockStart"] <= y < pr["BudgetShockEnd"] else 0.0))
        CloudPB = pr["CloudPerBFY"] * (1 + pr["CloudAISens"] * (1 - 1 / P_all))
        GCCAppeal = ramp(y, pr["GCCRampStart"], pr["GCCRampEnd"], 0.0, pr["GCCAppealEnd"]) \
            if y < pr["GCCRampEnd"] else ramp(y, pr["GCCRampEnd"], pr["GCCFadeEnd"], pr["GCCAppealEnd"], pr["GCCAppealEnd"] * pr["GCCAppealKeep"])
        # sourcing costs per option (USD per BFY)
        AvgWM = {e: sum(ShareL[e][l] * pr["WageMult_" + l] for l in LEVELS) for e in ("IH", "GCC")}
        AvgW = {e: sum(ShareL[e][l] * W[l] for l in LEVELS) for e in ("IH", "GCC")}
        CostOpt = {"IH": pr["BaseWage_IH"] * st["WI"]["IH"] * AvgWM["IH"] / (AvgW["IH"] * st["ClientP"]["IH"]) + AICostPerUnit * (1 - 1 / st["ClientP"]["IH"]),
                   "GCC": pr["BaseWage_GCC"] * st["WI"]["GCC"] * AvgWM["GCC"] * (1 + pr["GCCOverhead"]) / (AvgW["GCC"] * st["ClientP"]["GCC"]) + AICostPerUnit * (1 - 1 / st["ClientP"]["GCC"])}
        for v in VENDORS:
            CostOpt[v] = VF[v]["BasePriceAvg"] * VF[v]["Anchor"] * (1 - VF[v]["Disc"]) * (1 - VF[v]["shock"])
        RiskOpt = {"IH": 0.0, "GCC": 0.0}
        for v in VENDORS:
            RiskOpt[v] = pr["ViabSens"] * min(0.0, VF[v]["DevEff"]) - pr["ExitPenalty"] * max(0.0, pr["ExitThreshold"] - VF[v]["Vi"])
        RiskOpt["OIT"] -= pr["VisaRiskSens"] * max(0.0, st["TightPerc"] - pr["VTBase"])
        cons, Demand, SrcTarget = {}, {}, {}
        for x in SECTORS:
            AC = st["AC"][x]
            RegDrag = min(0.95, pr["RegScenario"] * SEC6["RegDragLevel"][x] * RegRamp)
            AIexp = max(0.0, AC * LOBAuto - pr["AC0"] * pr["aL_2024"]) if ai_on else 0.0
            LOB0 = pr["LOB0_" + x]
            LOBTarget = LOB0 * (1 - AIexp)
            AgentWork = LOB0 - LOBTarget
            CreditSpend = AgentWork * CreditCostPB
            NetSavings = (LOB0 - st["LOB"][x]) * SEC6["LOBWage"][x] - CreditSpend
            ReinvEff = 1 + pr["ReinvestAdoptSens"] * clamp(pr["ReinvestFrac"] * NetSavings / pr["Budget0_" + x], 0.0, 1.0)
            kC = CEc * (1 - RegDrag) * ReinvEff
            AdoptC = min((pr["pC"] + pr["qC"] * AC) * kC * (1 - AC), (1 - AC) / pr["MinAdoptionTime"]) if ai_on else 0.0
            Port0 = pr["Port0_" + x]; NewApps0 = Port0 / pr["AppLife"]
            NewApps = NewApps0 * (1 - pr["AppDisplacement"] * AIexp)
            Retire = st["Port"][x] / pr["AppLife"] * (1 + pr["RetireAccel"] * AIexp)
            Seats = st["LOB"][x] + ConsIT * CS[x] / (G if pr["Burn"] >= 0.5 else 1.0)
            SeatSpend = st["SeatsB"][x] * (pr["BaseSeatPrice"] + Att * pr["AISeatPrice"])
            CloudSpend = CloudPB * CompS[x]
            Committed = ServicesSpend * CS[x] + SeatSpend + CreditSpend + CloudSpend
            Budget = pr["Budget0_" + x] * BudgetGrowth + pr["ReinvestFrac"] * max(0.0, NetSavings)
            Approval = clamp(1 - pr["ApprovalSens"] * max(0.0, st["SpendRatio"][x] - 1), pr["MinApproval"], 1.0)
            base = pr["BaseDemand"] * G * SEC6["SectorShare"][x] * (1 + (pr["DemandStep"] if y >= pr["StepYear"] else 0))
            pr0 = st["Port"][x] / Port0
            dm = {"APP": WT6["Mix"]["APP"] * ((1 - pr["NewAppWeight"]) * pr0 + pr["NewAppWeight"] * NewApps / NewApps0) * Jev * Approval,
                  "DATA": WT6["Mix"]["DATA"] * ((1 - pr["MigWeight"]) + pr["MigWeight"] * Retire / NewApps0) * Jev * Approval,
                  "SEC": WT6["Mix"]["SEC"] * CyberMult,
                  "GOVN": WT6["Mix"]["GOVN"] * (1 + (pr["GovRegSens"] * RegDrag * AC if ai_on else 0.0)),
                  "SUP": WT6["Mix"]["SUP"] * ((1 - pr["SupPortShare"]) + pr["SupPortShare"] * pr0),
                  "EUS": WT6["Mix"]["EUS"] * st["SeatsB"][x] / pr["Seats0_" + x]}
            AIBuild = ((pr["BuildRate"] * (AdoptC - pr["AdoptC0"]) + pr["RunRate"] * (AC - pr["AC0"])) if ai_on else 0.0) * Jev * Approval
            Demand[x] = {w: base * max(0.0, dm[w] + AIBuild * WT6["BuildMix"][w]) for w in WTYPES}
            # sourcing values for this sector
            Val = {}
            for e in EMPLOYERS:
                val = pr[f"SrcASC_{x}_{e}"] - pr["SrcCostSens"] * CostOpt[e] / pr["CostRef"] + RiskOpt[e] \
                    - pr["CapSens"] * max(0.0, TTFratio[EMP_POOL[e]] - 1) \
                    - (pr["RegFitSens"] * RegDrag * AC * EMPS6["OffExp"][e] if ai_on else 0.0)
                if e == "GCC":
                    val += GCCAppeal + (pr["GCCAISens"] * (AC - pr["AC0"]) if ai_on else 0.0)
                Val[e] = val
            SrcTarget[x] = softmax(Val)
            cons[x] = dict(AdoptC=AdoptC, LOBTarget=LOBTarget, AgentWork=AgentWork, CreditSpend=CreditSpend, NetSavings=NetSavings,
                           NewApps=NewApps, Retire=Retire, Seats=Seats, SeatSpend=SeatSpend, CloudSpend=CloudSpend,
                           Committed=Committed, Budget=Budget, Approval=Approval, RegDrag=RegDrag, AIBuild=AIBuild * base)
        DemandTot = sum(Demand[x][w] for x in SECTORS for w in WTYPES)

        if step % rk == 0:
            row = {"year": round(y, 4), "P_all": P_all, "Demand": DemandTot, "Completion": Completion, "Backlog": TotBL,
                   "VisaTight": VisaTight, "ServicesSpend": ServicesSpend, "RevenueTot": RevenueTot, "ConsIT": ConsIT,
                   "Grad_total": sum(Grad.values()), "Ext_total": sum(ext[r][l] for r in REGIONS for l in LEVELS),
                   "G": G, "Att": Att, "A_mean": sum(Aemp[e] * CompE[e] for e in EMPLOYERS) / max(Completion, 1e-9),
                   "HireJ_IN": sum(hires[u]["J"] for u in UNITS if POOL[u] == "IN"),
                   "HireJ_ON": sum(hires[u]["J"] for u in UNITS if POOL[u] == "ON"),
                   "AC_mean": sum(st["AC"][x] * SEC6["SectorShare"][x] for x in SECTORS)}
            for u in UNITS:
                row["H_" + u] = sum(H[u][l] for l in LEVELS)
                row["LabCost_" + u] = LabourCost[u]; row["Del_" + u] = Delivered[u]
            for e in EMPLOYERS:
                row["Head_" + e] = sum(row["H_" + u] for u in UNITS if EMP_OF[u] == e)
                row["A_" + e] = Aemp[e]; row["P_" + e] = Pe[e]; row["Cost_" + e] = CostOpt[e]; row["CompE_" + e] = CompE[e]
                row["LabPB_" + e] = sum(LabourCost[u] for u in UNITS if EMP_OF[u] == e) / max(EffStaffE[e], 1e-9)
                row["WorkShare_" + e] = sum(EmpShare[x][e] * CS[x] for x in SECTORS)
            for v in VENDORS:
                f = VF[v]
                for key in ("Revenue", "Margin", "Vi", "Disc", "Power", "PU", "AvgIdx", "SignRate", "ExpRate", "SalesCost", "AICost",
                            "VisaCost", "VLab", "LabRaw", "BaseRev", "VendDel", "EffortShare", "VShare", "ShareLoss", "VendorCost"):
                    row[f"{key}_{v}"] = f[key]
                for k in TYPES:
                    row[f"Mix_{v}_{k}"] = (st["Leg"][v][k] + st["NewV"][v][k]) / max(f["Book"], 1e-12)
                    row[f"Sign_{v}_{k}"] = f["TypeShare"][k]
                row["AvgNewDur_" + v] = sum(f["TypeShare"][k] * f["Dnew"][k] for k in TYPES)
                row["Overhead_" + v] = st["Overhead"][v]
            for x in SECTORS:
                c = cons[x]
                row["Dem_" + x] = sum(Demand[x][w] for w in WTYPES); row["AC_" + x] = st["AC"][x]; row["LOB_" + x] = st["LOB"][x]
                row["Committed_" + x] = c["Committed"]; row["Budget_" + x] = c["Budget"]; row["CompS_" + x] = CompS[x]
                row["WorkCheck_" + x] = st["IHW"][x] + st["GCCW"][x] + sum(st["VW"][x][v] for v in VENDORS)
                for e in EMPLOYERS:
                    row[f"Src_{x}_{e}"] = EmpShare[x][e]; row[f"SrcT_{x}_{e}"] = SrcTarget[x][e]
            for w in WTYPES:
                row["Dem_" + w] = sum(Demand[x][w] for x in SECTORS)
            for r in REGIONS:
                row["Unemp_" + r] = UnempRate[r]
                row["HeadLoc_" + r] = sum(H[u][l] for u in UNITS if LOC[u] == r for l in LEVELS)
                for l in LEVELS:
                    row[f"TTF_{r}_{l}"] = TTFr[r][l]
            row["HeadTotal"] = sum(H[u][l] for u in UNITS for l in LEVELS)
            row["VendorHead"] = sum(row["Head_" + v] for v in VENDORS)
            row["Q1_ConsOnshore"] = row["H_IH"]; row["Q1_ConsIndia"] = row["H_GCC"]
            row["Q1_VendOnshore"] = row["H_OV"] + row["H_OL"] + row["H_SI_ON"] + row["H_BQ"]
            row["Q1_VendIndia"] = row["H_VI"] + row["H_SI_IN"]
            row["LOB"] = sum(st["LOB"][x] for x in SECTORS); row["Committed"] = sum(cons[x]["Committed"] for x in SECTORS)
            row["Budget"] = sum(cons[x]["Budget"] for x in SECTORS)
            row["WorkCheckMax"] = max(abs(row["WorkCheck_" + x] - 1) for x in SECTORS)
            rows.append(row)
        if step == n:
            break
        # ---------------- integrate ----------------
        d = dt
        for x in SECTORS:
            c = cons[x]
            for w in WTYPES:
                st["BL"][x][w] += d * (Demand[x][w] - Comp[x][w] - Aband[x][w])
            st["AC"][x] += d * c["AdoptC"]
            st["LOB"][x] += d * (c["LOBTarget"] - st["LOB"][x]) / pr["LOBAdjTime"]
            st["Port"][x] += d * (c["NewApps"] - c["Retire"])
            st["SeatsB"][x] += d * (c["Seats"] - st["SeatsB"][x]) / pr["SeatAdjTime"]
            st["SpendRatio"][x] += d * (c["Committed"] / c["Budget"] - st["SpendRatio"][x]) / pr["BudgetCycle"]
            if pr["FreezeSourcing"] < 0.5:
                s_ = Src[x]
                st["IHW"][x] += d * (s_["Contested"] * st["SrcPerc"][x]["IH"] - pr["Contest"] * s_["IHTurn"])
                st["GCCW"][x] += d * (s_["Contested"] * st["SrcPerc"][x]["GCC"] - pr["Contest"] * s_["GCCTurn"])
                for v in VENDORS:
                    st["VW"][x][v] += d * (SignS[x][v] - s_["VExp"][v])
                for e in EMPLOYERS:
                    st["SrcPerc"][x][e] += d * (SrcTarget[x][e] - st["SrcPerc"][x][e]) / pr["SrcPerceptionTime"]
        st["Att"] += d * AttAdopt
        st["CostPerc"] += d * (CostIdx6 - st["CostPerc"]) / pr["CostPerceptionTime"]
        for u in UNITS:
            r = POOL[u]
            for l in LEVELS:
                x_ = fl[u][l]
                promo_in = promo[u][l]
                conv_in = conv[l] if u == "OL" else 0.0
                visa_out = (expiry[l] + conv[l]) if u == "OV" else 0.0
                st["V"][u][l] += d * (x_["openings"] - cancel[u][l] - promo_in - sw[u][l]["in"] - hires[u][l])
                st["O"][u][l] += d * (hires[u][l] - x_["onboard"])
                st["H"][u][l] += d * (x_["onboard"] + promo_in + sw[u][l]["in"] + conv_in - x_["promo_out"] - x_["quits"]
                                       - x_["leave"] - x_["retire"] - x_["layoffs"] - sw[u][l]["out"] - visa_out)
                st["R"][r][l] += d * x_["layoffs"]
                st["U"][r][l] += d * (x_["quits"] - hires[u][l])
                st["LeftField"][r] += d * x_["leave"]
                st["Retired"][r] += d * x_["retire"]
            if u == "OV":
                for l in LEVELS:
                    st["U"]["IN"][l] += d * expiry[l]
        for r in REGIONS:
            for l in LEVELS:
                pz = pool[r][l]
                grad_in = Grad[r] if l == "J" else 0.0
                st["R"][r][l] += d * (-pz["rec_to_seek"] - pz["rec_to_left"] - pz["rec_retire"])
                st["U"][r][l] += d * (grad_in + pz["rec_to_seek"] + ext[r][l] - pz["seek_exit"] - pz["seek_retire"])
                st["LeftField"][r] += d * (pz["rec_to_left"] + pz["seek_exit"])
                st["Retired"][r] += d * (pz["rec_retire"] + pz["seek_retire"])
            st["Pipeline"][r] += d * (Enrol[r] - Grad[r])
            st["PUS"][r] += d * (UnempRate[r] - st["PUS"][r]) / pr["UnempPerceptionTime"]
            st["PUL"][r] += d * (UnempRate[r] - st["PUL"][r]) / pr["StudentPerceptionTime"]
        for e in EMPLOYERS:
            st["A"][e] += d * AdoptE[e]
            st["PerceivedP"][e] += d * (Pe[e] - st["PerceivedP"][e]) / pr["PerceptionTime"]
            st["ClientP"][e] += d * (Pe[e] - st["ClientP"][e]) / pr["ClientPerceptionTime"]
            st["ClientPRef"][e] += d * (st["ClientP"][e] - st["ClientPRef"][e]) / pr["TrendTime"]
        st["TightPerc"] += d * (VisaTight - st["TightPerc"]) / pr["TightPerceptionTime"]
        for v in VENDORS:
            f = VF[v]
            st["Overhead"][v] += d * (pr["OverheadRate_" + v] * f["Revenue"] - st["Overhead"][v]) / pr["OverheadAdjTime"]
            st["Viab"][v] += d * (f["Margin"] - st["Viab"][v]) / pr["ViabilityTime"]
            st["CostProg"][v] += d * (f["CostProgTarget"] - st["CostProg"][v]) / pr["CostProgramTime"]
            st["Disc"][v] += d * (f["DiscTarget"] - st["Disc"][v]) / pr["DiscAdjTime"]
            st["ShareRef"][v] += d * (f["VShare"] - st["ShareRef"][v]) / pr["ShareRefTime"]
            for k in TYPES:
                st["Leg"][v][k] += d * (-f["ExpLeg"][k])
                st["NewV"][v][k] += d * (f["Sign"][k] - f["ExpNew"][k])
                st["NewD"][v][k] += d * (f["Sign"][k] * f["Dnew"][k] - st["NewV"][v][k])
                st["NewP"][v][k] += d * (f["Sign"][k] * f["PNew"][k] - f["ExpNew"][k] * f["AvgP"][k] - st["NewP"][v][k] * f["Glide"][k])
        for u in UNITS:
            st["WI"][u] += d * (WITarget[u] - st["WI"][u]) / pr["WageAdjTime"]
        for grp in ("H", "O", "V"):
            for u in UNITS:
                for l in LEVELS:
                    key = f"{grp}_{u}_{l}"; mins[key] = min(mins.get(key, 1e18), st[grp][u][l])
        for grp in ("R", "U"):
            for r in REGIONS:
                for l in LEVELS:
                    key = f"{grp}_{r}_{l}"; mins[key] = min(mins.get(key, 1e18), st[grp][r][l])
        for x in SECTORS:
            for key, val in (("IHW", st["IHW"][x]), ("GCCW", st["GCCW"][x])):
                mins[f"{key}_{x}"] = min(mins.get(f"{key}_{x}", 1e18), val)
            for v in VENDORS:
                mins[f"VW_{x}_{v}"] = min(mins.get(f"VW_{x}_{v}", 1e18), st["VW"][x][v])
        for v in VENDORS:
            for k in TYPES:
                for g_ in ("Leg", "NewV", "NewP", "NewD"):
                    mins[f"{g_}_{v}_{k}"] = min(mins.get(f"{g_}_{v}_{k}", 1e18), st[g_][v][k])
        t += dt
    return rows, st, mins


def blank_state():
    return {"BL": {x: {w: 0.0 for w in WTYPES} for x in SECTORS},
            "A": {e: P["A0"] for e in EMPLOYERS}, "PerceivedP": {e: 1.0 for e in EMPLOYERS},
            "ClientP": {e: 1.0 for e in EMPLOYERS}, "ClientPRef": {e: 1.0 for e in EMPLOYERS},
            "TightPerc": P["VTBase"],
            "H": {u: {l: 0.0 for l in LEVELS} for u in UNITS}, "O": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "V": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "R": {r: {l: 0.0 for l in LEVELS} for r in REGIONS}, "U": {r: {l: 0.0 for l in LEVELS} for r in REGIONS},
            "Pipeline": {r: 4 * P["BaseEnrolment_" + r] for r in REGIONS},
            "LeftField": {r: 0.0 for r in REGIONS}, "Retired": {r: 0.0 for r in REGIONS},
            "PUS": {r: P["NormalUnempRate_" + r] for r in REGIONS}, "PUL": {r: P["NormalUnempRate_" + r] for r in REGIONS},
            "WI": {u: 1.0 for u in UNITS},
            "Overhead": {v: 0.0 for v in VENDORS}, "Viab": {v: P["NormalMargin_" + v] for v in VENDORS},
            "CostProg": {v: 0.0 for v in VENDORS}, "Disc": {v: 0.0 for v in VENDORS}, "ShareRef": {v: 0.0 for v in VENDORS},
            "Leg": {v: dict(MIX0[v]) for v in VENDORS}, "NewV": {v: {k: 0.0 for k in TYPES} for v in VENDORS},
            "NewD": {v: {k: 0.0 for k in TYPES} for v in VENDORS}, "NewP": {v: {k: 0.0 for k in TYPES} for v in VENDORS},
            "IHW": {x: SRC0[x]["IH"] for x in SECTORS}, "GCCW": {x: SRC0[x]["GCC"] for x in SECTORS},
            "VW": {x: {v: SRC0[x][v] for v in VENDORS} for x in SECTORS},
            "SrcPerc": {x: dict(SRC0[x]) for x in SECTORS},
            "AC": {x: P["AC0"] for x in SECTORS}, "LOB": {x: 0.0 for x in SECTORS}, "Port": {x: 0.0 for x in SECTORS},
            "SeatsB": {x: 0.0 for x in SECTORS}, "SpendRatio": {x: P["NormalUtil"] for x in SECTORS},
            "Att": P["Att0"], "CostPerc": 1.0}
