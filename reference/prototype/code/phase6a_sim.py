"""Phase 6a prototype - Phase 5 + the demand side: sectors and work types, AI capability by work type,
consumer AI adoption, LOB headcount, application portfolio, seats, platform and cloud spend, one IT budget.

Units (employment units):
  IH  consumer in-house      located Onshore, hires from Onshore pool
  GCC consumer captive       located India,   hires from India pool
  VI  vendor offshore        located India,   hires from India pool
  OV  vendor onsite (visa)   located Onshore, hires from India pool (visa holders)
  OL  vendor onsite (local)  located Onshore, hires from Onshore pool
Regions (labour pools): IN (India), ON (Onshore)
Levels: J, M, S. One sector. Wages constant (ratios drive switching only).
Euler integration, Year = 2024 + t.
"""
import json

UNITS = ("IH", "GCC", "VI", "OV", "OL")
REGIONS = ("IN", "ON")
LEVELS = ("J", "M", "S")
POOL = {"IH": "ON", "GCC": "IN", "VI": "IN", "OV": "IN", "OL": "ON"}      # labour pool a unit hires from / exits to
LOC = {"IH": "ON", "GCC": "IN", "VI": "IN", "OV": "ON", "OL": "ON"}       # where the work is done
PAIRS = (("GCC", "VI"), ("IH", "OL"))                                     # job switching pairs (same region)

P = dict(
    # Phase 1
    BaseDemand=100_000.0, WorkPerPerson=1.0, TargetClearanceTime=0.5, MinCompletionTime=0.25,
    AbandonTolerance=1.5, AbandonTime=1.0, LayoffAdjTime=0.25, MinLayoffTime=0.25, HireAdjTime=0.5,
    PerceptionTime=1.0, a_2024=0.20, a_max=0.60, g=0.10, s=5.0, v=0.05, p=0.03, q=0.40, A0=0.05,
    MinAdoptionTime=0.0625, JevonsEps=0.0, JevonsCap=2.0, DemandStep=0.0, StepYear=2028.0,
    # Phase 2 (labour)
    W_J=0.6, W_M=1.0, W_S=1.4, Share0_J=0.19, Share0_M=0.25, Share0_S=0.56, JuniorCut=0.5,
    TimeInJunior=3.0, TimeInMid=5.0, PromoFillTime=0.125,
    QuitRate_J=0.15, QuitRate_M=0.10, QuitRate_S=0.08,
    LeaveITRate_J=0.05, LeaveITRate_M=0.06, LeaveITRate_S=0.04, RetireRate_S=0.033,
    OnboardTime=0.25, OnboardProductivity=0.5, CancelTime=0.25,
    m=4.0, alpha=0.5, MinFillTime=0.0625, RecoveryTime=0.33,
    BaseLeaveFrac_J=0.05, BaseLeaveFrac_M=0.10, BaseLeaveFrac_S=0.20, SeekerExitRate=0.10,
    UnempPerceptionTime=0.5, StudyTime=4.0, StudentPerceptionTime=2.0, EnrolSensitivity=1.0,
    ExtEntryRate_M=0.05, ExtEntryRate_S=0.05, ExtEntryMax=3.0,
    # Phase 3: regions and work allocation
    BaseEnrolment_IN=3400.0, BaseEnrolment_ON=2800.0,
    NormalUnempRate_IN=0.06, NormalUnempRate_ON=0.06,
    NormalTTF_IN_M=0.5, NormalTTF_IN_S=0.1, NormalTTF_ON_M=0.5, NormalTTF_ON_S=0.1,
    InHouseShare0=0.30, GCCShare0=0.10, GCCRampStart=2027.0, GCCRampEnd=2031.0,
    OnsiteShare0=0.25, OffshoreShiftSens=0.5, VisaMix0=0.6, VisaMixSens=0.8,
    # visa policy lever
    VTBase=0.3, VTEnd=0.3, VTRampStart=2027.0, VTRampEnd=2031.0, TightPerceptionTime=1.0,
    BaseVisaCap=8000.0, VisaTenure=6.0, ConvRate=0.05,
    # job switching
    Wage_IH=1.0, Wage_GCC=1.3, Wage_VI=1.0, Wage_OV=1.0, Wage_OL=0.95,
    SwitchRate=0.04, SwitchElasticity=2.0, SwitchMax=2.0,
    # Phase 4: money (USD, real 2026)
    BaseWage_IH=125_000.0, BaseWage_GCC=26_000.0, BaseWage_VI=20_000.0, BaseWage_OV=90_000.0, BaseWage_OL=120_000.0,
    WageMult_J=0.6, WageMult_M=1.0, WageMult_S=1.5,
    Price_VI=32_000.0, Price_OV=150_000.0, Price_OL=150_000.0,   # USD per BFY delivered at price index 1
    VisaFeePerHire=100_000.0, VisaComplianceCost=5_000.0,        # USD per visa hire; USD per visa holder per year
    AICost2024=8_000.0, AICostDecline=0.15, AIShockMult=1.0, AIShockStart=2030.0, AIShockEnd=2032.0,
    OverheadRate=0.08, OverheadAdjTime=2.0,
    PassThrough=1.0, ClientPerceptionTime=1.5,
    PriceShock=0.0, PriceShockYear=2028.0,
    ViabilityTime=2.0, NormalMargin=0.18, Deadband=0.02,
    ExitThreshold=0.0,
    CostProgramSens=1.5, MaxSavings=0.15, CostProgramTime=2.0,
    WagesEndogenous=1.0, WageElasticity=0.25, WageRestraint=1.0, WageAdjTime=2.0, WageMin=0.85, WageMax=1.3,
    # Phase 5: contracts (types FP, TM, MS, SA, OB)
    Mix0_FP=0.35, Mix0_TM=0.30, Mix0_MS=0.22, Mix0_SA=0.10, Mix0_OB=0.03,      # 2024 in-force volume mix
    BaseDur_FP=2.5, BaseDur_TM=1.5, BaseDur_MS=6.0, BaseDur_SA=1.0, BaseDur_OB=3.0,  # yr, also legacy durations
    MinDur=0.25, DurPUSens=15.0, DurPowerElast=1.0, TrendTime=2.0,
    MSGlideShare=0.5, OBGainShare=0.5,
    ConsSens=10.0, EffortDistrust=0.5, VendSens=2.0, SATTFSens=0.5, BargainW0=0.5, PowerSens=3.0, PowerMin=0.5, PowerMax=1.2,
    TypeASC_FP=0.0, TypeASC_TM=0.0, TypeASC_MS=0.0, TypeASC_SA=0.0, TypeASC_OB=0.0,   # calibrated
    SalesCostRate=0.05,
    # Phase 5: sourcing (options IH, GCC, VEND)
    IHReviewTime=4.0, GCCReviewTime=5.0, Contest=0.5, SrcPerceptionTime=1.5,
    SrcCostSens=3.0, GCCOverhead=0.5, CostRef=131_000.0,                      # CostRef calibrated
    SrcASC_IH=0.0, SrcASC_GCC=0.0, SrcASC_VEND=0.0,                          # calibrated
    ViabSens=5.0, ExitPenalty=7.5, VisaRiskSens=1.0, CapSens=0.5, GCCAppealEnd=0.0,
    # Phase 5: price competition (B12)
    ShareRefTime=4.0, ShareLossSens=0.5, RivalSens=3.0, MaxDisc=0.4, DiscAdjTime=1.0,
    # Phase 6a: delivery AI cost effect (R5)
    CostAdoptElast=0.3, CEMin=0.5, CEMax=1.5, LabourCostPB0=125_000.0,     # LabourCostPB0 calibrated
    # Phase 6a: consumer AI and LOB
    pC=0.02, qC=0.30, AC0=0.05, aL_2024=0.05, aL_max=0.35, LOBAdjTime=2.0,
    CreditCost2024=30_000.0, ReinvestFrac=0.2, ReinvestAdoptSens=0.5,
    RegScenario=1.0, RegStart=2027.9, RegEnd=2028.6,
    # Phase 6a: applications and seats
    AppLife=8.0, AppDisplacement=0.6, RetireAccel=1.0, NewAppWeight=0.5, MigWeight=0.3, SupPortShare=0.8,
    SeatAdjTime=2.0, BaseSeatPrice=1_500.0, AISeatPrice=360.0, pAtt=0.05, qAtt=0.5, Att0=0.02,
    CloudPerBFY=13_000.0, CloudAISens=0.5, Leakage=0.2,
    # Phase 6a: AI-driven demand, Jevons and the budget
    BuildRate=0.6, RunRate=0.10, GovRegSens=2.0, CostPerceptionTime=1.5,
    CostPerBFY0=84_000.0, NormalUtil=0.95, ApprovalSens=2.0, MinApproval=0.2, BudgetCycle=1.0,
    ITBudgetGrowth=0.0, BudgetShock=0.0, BudgetShockStart=2030.0, BudgetShockEnd=2032.0,
    CyberEnd=1.0, CyberStart=2026.0, CyberRampEnd=2030.0,
)
VENDOR = ("VI", "OV", "OL")
TYPES = ("FP", "TM", "MS", "SA", "OB")
EFFORT = ("TM", "SA")
OPTIONS = ("IH", "GCC", "VEND")
OPT_POOL = {"IH": "ON", "GCC": "IN", "VEND": "IN"}
SECTORS = ("FIN", "LEG", "MED", "GOV", "MFG", "LOG", "RET")
WTYPES = ("APP", "DATA", "SEC", "GOVN", "SUP", "EUS")
DISCRETIONARY = ("APP", "DATA")
SEC6 = dict(
    SectorShare={"FIN": 0.25, "LEG": 0.03, "MED": 0.12, "GOV": 0.18, "MFG": 0.17, "LOG": 0.08, "RET": 0.17},
    ITIntensity={"FIN": 0.10, "LEG": 0.04, "MED": 0.04, "GOV": 0.05, "MFG": 0.03, "LOG": 0.03, "RET": 0.025},
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


def run(init, ai_on=True, dt=1/16, stop=16.0, record_every=0.25, **over):
    pr = dict(P); pr.update(over)
    st = json.loads(json.dumps(init))
    rows = []; n = int(round(stop / dt)); rk = max(1, int(round(record_every / dt)))
    mins = {}
    t = 0.0
    for step in range(n + 1):
        y = 2024 + t
        # ---- Phase 1 + 6a: capability by work type, backlog by sector and work type ----
        aW = {w: max(0.0, WT6["amax"][w] - (WT6["amax"][w] - WT6["a2024"][w]) * (1 - pr["g"]) ** (y - 2024)) for w in WTYPES}
        PAI = {w: 1 / ((1 - aW[w]) + aW[w] / WT6["s"][w] + aW[w] * WT6["v"][w]) for w in WTYPES}
        A = st["A"]
        Pw = {w: (A * PAI[w] + (1 - A)) if ai_on else 1.0 for w in WTYPES}
        BL = st["BL"]
        TotBL = sum(BL[x][w] for x in SECTORS for w in WTYPES)
        EffortBL = sum(BL[x][w] / Pw[w] for x in SECTORS for w in WTYPES)
        P_eff = TotBL / EffortBL if EffortBL > 0 else 1.0
        H, O, V = st["H"], st["O"], st["V"]
        R, U = st["R"], st["U"]
        W = {l: pr["W_" + l] for l in LEVELS}
        EffStaff = sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for u in UNITS for l in LEVELS)
        Capacity = pr["WorkPerPerson"] * P_eff * EffStaff
        Completion = min(Capacity, TotBL / pr["MinCompletionTime"])
        ClearRate = Completion / TotBL if TotBL > 0 else 0.0
        Comp = {x: {w: BL[x][w] * ClearRate for w in WTYPES} for x in SECTORS}
        Aband = {x: {w: max(0.0, BL[x][w] * (1 - ClearRate * pr["AbandonTolerance"])) / pr["AbandonTime"] for w in WTYPES} for x in SECTORS}
        DesiredEff = TotBL / (pr["TargetClearanceTime"] * pr["WorkPerPerson"] * st["PerceivedP"])
        CompS = {x: sum(Comp[x][w] for w in WTYPES) for x in SECTORS}
        CS = {x: (CompS[x] / Completion if Completion > 0 else SEC6["SectorShare"][x]) for x in SECTORS}
        # ---- level mix ----
        sJ = pr["Share0_J"] * (1 - pr["JuniorCut"] * (A if ai_on else 0.0))
        rest0 = pr["Share0_M"] + pr["Share0_S"]
        Share = {"J": sJ, "M": pr["Share0_M"] * (1 - sJ) / rest0, "S": pr["Share0_S"] * (1 - sJ) / rest0}
        denom = sum(Share[l] * W[l] for l in LEVELS)
        # ---- policy lever and work allocation ----
        VisaTight = ramp(y, pr["VTRampStart"], pr["VTRampEnd"], pr["VTBase"], pr["VTEnd"])
        dTight = st["TightPerc"] - pr["VTBase"]
        OnsiteShare = clamp(pr["OnsiteShare0"] * (1 - pr["OffshoreShiftSens"] * dTight), 0.0, 1.0)
        VisaMix = clamp(pr["VisaMix0"] * (1 - pr["VisaMixSens"] * dTight), 0.0, 1.0)
        VendorShare = sum(st["Leg"][k] + st["NewV"][k] for k in TYPES)
        UShare = {"IH": st["IHWork"], "GCC": st["GCCWork"], "VI": VendorShare * (1 - OnsiteShare),
                  "OV": VendorShare * OnsiteShare * VisaMix, "OL": VendorShare * OnsiteShare * (1 - VisaMix)}
        Desired = {u: {l: DesiredEff * UShare[u] * Share[l] / denom for l in LEVELS} for u in UNITS}
        # ---- regional unemployment ----
        UnempRate, LeaveEffect, EnrolEffect = {}, {}, {}
        for r in REGIONS:
            unemp = sum(R[r][l] + U[r][l] for l in LEVELS)
            emp = sum(H[u][l] + O[u][l] for u in UNITS if POOL[u] == r for l in LEVELS)
            UnempRate[r] = unemp / (emp + unemp)
            norm = pr["NormalUnempRate_" + r]
            LeaveEffect[r] = clamp(st["PUS"][r] / norm, 0.5, 3.0)
            EnrolEffect[r] = clamp(1 - pr["EnrolSensitivity"] * (st["PUL"][r] / norm - 1), 0.4, 1.3)
        # ---- vacancy pre-processing ----
        surplus, cancel, avail = {}, {}, {}
        for u in UNITS:
            surplus[u], cancel[u], avail[u] = {}, {}, {}
            for l in LEVELS:
                sp = H[u][l] + O[u][l] - Desired[u][l]
                c = (max(0.0, V[u][l] + sp) if sp <= 0 else V[u][l]) / pr["CancelTime"]
                cap = V[u][l] / pr["MinFillTime"]
                surplus[u][l] = sp; cancel[u][l] = min(c, cap); avail[u][l] = max(0.0, cap - cancel[u][l])
        # ---- promotions within each unit ----
        promo = {u: {"J": 0.0,
                     "M": min(H[u]["J"] / pr["TimeInJunior"], V[u]["M"] / pr["PromoFillTime"], avail[u]["M"]),
                     "S": min(H[u]["M"] / pr["TimeInMid"], V[u]["S"] / pr["PromoFillTime"], avail[u]["S"])}
                 for u in UNITS}
        # ---- job switching between paired employers (same region, same level) ----
        sw = {u: {l: {"in": 0.0, "out": 0.0} for l in LEVELS} for u in UNITS}
        for i, j in PAIRS:
            for l in LEVELS:
                vsum = V[i][l] + V[j][l]
                for src, dst in ((i, j), (j, i)):
                    if vsum <= 0:
                        continue
                    gw = min(pr["SwitchMax"], ((pr["Wage_" + dst] * st["WI"][dst]) / (pr["Wage_" + src] * st["WI"][src])) ** pr["SwitchElasticity"])
                    raw = H[src][l] * pr["SwitchRate"] * gw * V[dst][l] / vsum
                    room = max(0.0, avail[dst][l] - promo[dst][l] - sw[dst][l]["in"])
                    f = min(raw, room)
                    sw[dst][l]["in"] += f; sw[src][l]["out"] += f
        # ---- visa-specific flows ----
        expiry = {l: H["OV"][l] / pr["VisaTenure"] for l in LEVELS}
        conv = {l: H["OV"][l] * pr["ConvRate"] * (1 - VisaTight) for l in LEVELS}
        VisaCap = pr["BaseVisaCap"] * (1 - VisaTight)
        # ---- openings, layoffs, quits ----
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
        # ---- external hiring: regional matching, allocated to units by vacancies ----
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
        # ---- time to fill, experienced entry ----
        TTF = {u: {l: V[u][l] / max(hires[u][l] + promo[u][l] + sw[u][l]["in"], 1.0) for l in LEVELS} for u in UNITS}
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
        # ---- pools ----
        pool = {r: {} for r in REGIONS}
        for r in REGIONS:
            for l in LEVELS:
                rec_out = R[r][l] / pr["RecoveryTime"]
                lf = clamp(pr["BaseLeaveFrac_" + l] * LeaveEffect[r], 0.0, 0.9)
                pool[r][l] = dict(rec_to_seek=rec_out * (1 - lf), rec_to_left=rec_out * lf,
                                  seek_exit=U[r][l] * pr["SeekerExitRate"] * LeaveEffect[r],
                                  rec_retire=R[r][l] * pr["RetireRate_S"] if l == "S" else 0.0,
                                  seek_retire=U[r][l] * pr["RetireRate_S"] if l == "S" else 0.0)
        Enrol = {r: pr["BaseEnrolment_" + r] * EnrolEffect[r] for r in REGIONS}
        Grad = {r: st["Pipeline"][r] / pr["StudyTime"] for r in REGIONS}

        # ---- Phase 4: finance ----
        capu = {u: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for l in LEVELS) for u in UNITS}
        Delivered = {u: Completion * capu[u] / max(EffStaff, 1e-9) for u in UNITS}
        Wage = {u: {l: pr["BaseWage_" + u] * pr["WageMult_" + l] * st["WI"][u] for l in LEVELS} for u in UNITS}
        LabourCost = {u: sum((H[u][l] + O[u][l]) * Wage[u][l] for l in LEVELS) for u in UNITS}
        shockNow = pr["PriceShock"] if y >= pr["PriceShockYear"] else 0.0
        Anchor = (1 / st["ClientP"]) ** pr["PassThrough"]
        PU = max(0.0, (st["ClientP"] - st["ClientPRef"]) / (st["ClientPRef"] * pr["TrendTime"]))
        V_idx = st["Viability"]
        dev = V_idx - pr["NormalMargin"]
        DevEff = (dev - pr["Deadband"]) if dev > pr["Deadband"] else ((dev + pr["Deadband"]) if dev < -pr["Deadband"] else 0.0)
        Power = clamp(1 + pr["PowerSens"] * dev, pr["PowerMin"], pr["PowerMax"])
        Disc = st["Disc"]
        # contract stocks: average attributes of the new vintage
        Pass = {"FP": 0.0, "TM": 1.0, "MS": pr["MSGlideShare"], "SA": 1.0, "OB": pr["OBGainShare"]}
        Glide = {k: (Pass[k] * PU if k in ("MS", "OB") else 0.0) for k in TYPES}
        Dnew = {k: max(pr["MinDur"], pr["BaseDur_" + k] / (1 + pr["DurPUSens"] * PU) * Power ** pr["DurPowerElast"]) for k in TYPES}
        AvgDur = {k: (st["NewD"][k] / st["NewV"][k] if st["NewV"][k] > 1e-12 else Dnew[k]) for k in TYPES}
        PNew = {k: ((1 - Disc) if k in EFFORT else Anchor * (1 - Disc)) for k in TYPES}
        AvgP = {k: (st["NewP"][k] / st["NewV"][k] if st["NewV"][k] > 1e-12 else PNew[k]) for k in TYPES}
        ExpLeg = {k: st["Leg"][k] / pr["BaseDur_" + k] for k in TYPES}
        ExpNew = {k: st["NewV"][k] / AvgDur[k] for k in TYPES}
        Expiry = sum(ExpLeg[k] + ExpNew[k] for k in TYPES)
        # revenue: price index by type and vintage (effort types bill hours, so divide by productivity)
        TypeIdxVol = {k: ((st["Leg"][k] + st["NewP"][k]) / P_eff if k in EFFORT else st["Leg"][k] + st["NewP"][k]) for k in TYPES}
        AvgIdx = sum(TypeIdxVol.values()) / max(VendorShare, 1e-12)
        VendDel = sum(Delivered[u] for u in VENDOR)
        BaseRev = sum(Delivered[u] * pr["Price_" + u] for u in VENDOR)
        BasePriceAvg = BaseRev / max(VendDel, 1e-9)
        Revenue = BaseRev * AvgIdx * (1 - shockNow)
        AIShock = pr["AIShockMult"] if pr["AIShockStart"] <= y < pr["AIShockEnd"] else 1.0
        AICostPerUnit = pr["AICost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShock
        AIShareOfOutput = 1 - 1 / P_eff
        AICost = AICostPerUnit * VendDel * AIShareOfOutput
        VisaCost = sum(hires["OV"][l] for l in LEVELS) * pr["VisaFeePerHire"] + sum(H["OV"][l] for l in LEVELS) * pr["VisaComplianceCost"]
        VendorLabour = sum(LabourCost[u] for u in VENDOR) * (1 - st["CostProg"])
        # sourcing flows
        IHTurn = st["IHWork"] / pr["IHReviewTime"]; GCCTurn = st["GCCWork"] / pr["GCCReviewTime"]
        Contested = pr["Contest"] * (Expiry + IHTurn + GCCTurn)
        VendSign = (1 - pr["Contest"]) * Expiry + Contested * st["SrcPerc"]["VEND"]
        BookTurnover = VendSign / max(VendorShare, 1e-12)
        SalesCost = pr["SalesCostRate"] * Revenue * BookTurnover
        VendorCost = VendorLabour + VisaCost + AICost + st["Overhead"] + SalesCost
        Margin = (Revenue - VendorCost) / max(Revenue, 1.0)
        # contract-type logit
        CostIdx = (VendorCost / max(VendDel, 1e-9)) / max(BasePriceAvg, 1e-9)
        Profit0 = pr["NormalMargin"]
        wv = clamp(pr["BargainW0"] * Power, 0.1, 0.9); wc = 1 - wv
        TTFratio = {r: TTFr[r]["M"] / pr[f"NormalTTF_{r}_M"] for r in REGIONS}
        Score = {}
        for k in TYPES:
            D = Dnew[k]
            Ucons = -pr["ConsSens"] * (1 - Pass[k]) * PU * D / 2
            if k in EFFORT:
                Ucons -= pr["ConsSens"] * pr["EffortDistrust"] * (1 - 1 / st["ClientP"])
            if k == "SA":
                Ucons += pr["SATTFSens"] * clamp(TTFratio["ON"] - 1, -1.0, 2.0)
            Rterm = (PNew[k] / P_eff * (1 - PU * D / 2)) if k in EFFORT else (PNew[k] * (1 - Pass[k] * PU * D / 2))
            Profit = Rterm - CostIdx * (1 - PU * D / 2)
            Uvend = pr["VendSens"] * (Profit - Profit0) / Profit0
            Score[k] = pr["TypeASC_" + k] + wc * Ucons + wv * Uvend
        mx = max(Score.values()); ez = {k: pow(2.718281828459045, Score[k] - mx) for k in TYPES}; zs = sum(ez.values())
        TypeShare = {k: ez[k] / zs for k in TYPES}
        Sign = {k: VendSign * TypeShare[k] for k in TYPES}
        # sourcing logit
        AvgWM = sum(Share[l] * pr["WageMult_" + l] for l in LEVELS); AvgW = sum(Share[l] * W[l] for l in LEVELS)
        AICostPB = AICostPerUnit * (1 - 1 / st["ClientP"])
        Cost = {"IH": pr["BaseWage_IH"] * st["WI"]["IH"] * AvgWM / (AvgW * st["ClientP"]) + AICostPB,
                "GCC": pr["BaseWage_GCC"] * st["WI"]["GCC"] * AvgWM * (1 + pr["GCCOverhead"]) / (AvgW * st["ClientP"]) + AICostPB,
                "VEND": BasePriceAvg * Anchor * (1 - Disc) * (1 - shockNow)}
        Risk = {"IH": 0.0, "GCC": 0.0,
                "VEND": pr["ViabSens"] * min(0.0, DevEff) - pr["ExitPenalty"] * max(0.0, pr["ExitThreshold"] - V_idx)
                        - pr["VisaRiskSens"] * max(0.0, st["TightPerc"] - pr["VTBase"])}
        GCCAppeal = ramp(y, pr["GCCRampStart"], pr["GCCRampEnd"], 0.0, pr["GCCAppealEnd"])
        Val = {e: pr["SrcASC_" + e] - pr["SrcCostSens"] * Cost[e] / pr["CostRef"] + Risk[e]
                  - pr["CapSens"] * max(0.0, TTFratio[OPT_POOL[e]] - 1) + (GCCAppeal if e == "GCC" else 0.0) for e in OPTIONS}
        mx = max(Val.values()); ez = {e: pow(2.718281828459045, Val[e] - mx) for e in OPTIONS}; zs = sum(ez.values())
        SrcTarget = {e: ez[e] / zs for e in OPTIONS}
        # price competition and responses
        ShareLoss = max(0.0, (st["ShareRef"] - VendorShare) / max(st["ShareRef"], 1e-12))
        Afford = clamp(V_idx / pr["NormalMargin"], 0.0, 1.0)      # vendors defend share with price only while they make money
        DiscTarget = clamp(pr["ShareLossSens"] * ShareLoss * Afford + pr["RivalSens"] * max(0.0, DevEff), 0.0, pr["MaxDisc"])
        CostProgTarget = clamp(pr["CostProgramSens"] * max(0.0, -DevEff), 0.0, pr["MaxSavings"])
        WITarget = {}
        for u in UNITS:
            if pr["WagesEndogenous"] >= 0.5:
                rgn = POOL[u]
                tight = (pr["NormalUnempRate_" + rgn] / max(st["PUS"][rgn], 1e-6)) ** pr["WageElasticity"]
                restraint = (1 - pr["WageRestraint"] * max(0.0, -DevEff)) if u in VENDOR else 1.0
                WITarget[u] = clamp(tight * restraint, pr["WageMin"], pr["WageMax"])
            else:
                WITarget[u] = 1.0
        ConsumerSpend = (LabourCost["IH"] + LabourCost["GCC"] * (1 + pr["GCCOverhead"]) + Revenue
                         + AICostPerUnit * AIShareOfOutput * (Delivered["IH"] + Delivered["GCC"]))
        # ---- Phase 6a: delivery adoption with the AI cost effect (R5) ----
        LabourCostPB = sum(LabourCost[u] for u in UNITS) / max(EffStaff, 1e-9)
        CE = clamp(((LabourCostPB / pr["LabourCostPB0"]) * (pr["AICost2024"] / AICostPerUnit)) ** pr["CostAdoptElast"], pr["CEMin"], pr["CEMax"])
        Adoption = min((pr["p"] + pr["q"] * A) * CE * (1 - A), (1 - A) / pr["MinAdoptionTime"]) if ai_on else 0.0
        # ---- Phase 6a: consumer AI, LOB, apps, seats, spend ----
        LOBAuto = max(0.0, pr["aL_max"] - (pr["aL_max"] - pr["aL_2024"]) * (1 - pr["g"]) ** (y - 2024))
        CreditCostPB = pr["CreditCost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShock
        CEc = clamp((pr["CreditCost2024"] / CreditCostPB) ** pr["CostAdoptElast"], pr["CEMin"], pr["CEMax"])
        RegRamp = ramp(y, pr["RegStart"], pr["RegEnd"], 0.0, 1.0)
        CyberMult = ramp(y, pr["CyberStart"], pr["CyberRampEnd"], 1.0, pr["CyberEnd"])
        Att = st["Att"]
        AttAdopt = min((pr["pAtt"] + pr["qAtt"] * Att) * (1 - Att), (1 - Att) / pr["MinAdoptionTime"]) if ai_on else 0.0
        ServicesSpend = ConsumerSpend
        CostIdx = (ServicesSpend / max(Completion, 1e-9)) / pr["CostPerBFY0"]
        Jev6 = min(pr["JevonsCap"], st["CostPerc"] ** (-pr["JevonsEps"]))
        ConsIT = sum(H["IH"][l] + H["GCC"][l] for l in LEVELS)
        BudgetGrowth = (1 + pr["ITBudgetGrowth"]) ** (y - 2024) * (1 - (pr["BudgetShock"] if pr["BudgetShockStart"] <= y < pr["BudgetShockEnd"] else 0.0))
        CloudPB = pr["CloudPerBFY"] * (1 + pr["CloudAISens"] * (1 - 1 / P_eff))
        cons = {}; Demand = {}
        for x in SECTORS:
            AC = st["AC"][x]
            RegDrag = min(0.95, pr["RegScenario"] * SEC6["RegDragLevel"][x] * RegRamp)
            AIexp = AC * LOBAuto if ai_on else 0.0
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
            Seats = st["LOB"][x] + ConsIT * CS[x]
            SeatSpend = st["SeatsB"][x] * (pr["BaseSeatPrice"] + Att * pr["AISeatPrice"])
            CloudSpend = CloudPB * CompS[x]
            Committed = ServicesSpend * CS[x] + SeatSpend + CreditSpend + CloudSpend
            Budget = pr["Budget0_" + x] * BudgetGrowth + pr["ReinvestFrac"] * max(0.0, NetSavings)
            Approval = clamp(1 - pr["ApprovalSens"] * max(0.0, st["SpendRatio"][x] - 1), pr["MinApproval"], 1.0)
            base = pr["BaseDemand"] * SEC6["SectorShare"][x] * (1 + (pr["DemandStep"] if y >= pr["StepYear"] else 0))
            pr0 = st["Port"][x] / Port0
            dm = {"APP": WT6["Mix"]["APP"] * ((1 - pr["NewAppWeight"]) * pr0 + pr["NewAppWeight"] * NewApps / NewApps0) * Jev6 * Approval,
                  "DATA": WT6["Mix"]["DATA"] * ((1 - pr["MigWeight"]) + pr["MigWeight"] * Retire / NewApps0) * Jev6 * Approval,
                  "SEC": WT6["Mix"]["SEC"] * CyberMult,
                  "GOVN": WT6["Mix"]["GOVN"] * (1 + (pr["GovRegSens"] * RegDrag * AC if ai_on else 0.0)),
                  "SUP": WT6["Mix"]["SUP"] * ((1 - pr["SupPortShare"]) + pr["SupPortShare"] * pr0),
                  "EUS": WT6["Mix"]["EUS"] * st["SeatsB"][x] / pr["Seats0_" + x]}
            AIBuild = ((pr["BuildRate"] * AdoptC + pr["RunRate"] * AC) if ai_on else 0.0) * Jev6 * Approval
            Demand[x] = {w: base * (dm[w] + AIBuild * WT6["BuildMix"][w]) for w in WTYPES}
            cons[x] = dict(AdoptC=AdoptC, LOBTarget=LOBTarget, AgentWork=AgentWork, CreditSpend=CreditSpend, NetSavings=NetSavings,
                           NewApps=NewApps, Retire=Retire, Seats=Seats, SeatSpend=SeatSpend, CloudSpend=CloudSpend,
                           Committed=Committed, Budget=Budget, Approval=Approval, RegDrag=RegDrag, AIBuild=AIBuild * base)
        DemandTot = sum(Demand[x][w] for x in SECTORS for w in WTYPES)

        if step % rk == 0:
            row = {"year": round(y, 4), "P_eff": P_eff, "A": A, "Backlog": TotBL, "VisaTight": VisaTight, "Demand": DemandTot, "CE": CE, "CEc": CEc, "Completion": Completion, "LabourCostPB": LabourCostPB,
                   "OnsiteShare": OnsiteShare, "VisaMix": VisaMix, "VisaCap": VisaCap,
                   "VisaHires": sum(hires["OV"][l] for l in LEVELS)}
            for u in UNITS:
                row["H_" + u] = sum(H[u][l] for l in LEVELS)
                row["V_" + u] = sum(V[u][l] for l in LEVELS)
                for l in LEVELS:
                    row[f"H_{u}_{l}"] = H[u][l]; row[f"TTF_{u}_{l}"] = TTF[u][l]
            for r in REGIONS:
                row["Unemp_" + r] = UnempRate[r]; row["Enrol_" + r] = Enrol[r]; row["Grad_" + r] = Grad[r]
                row["HeadLoc_" + r] = sum(H[u][l] for u in UNITS if LOC[u] == r for l in LEVELS)
                for l in LEVELS:
                    row[f"TTF_{r}_{l}"] = TTFr[r][l]; row[f"Ext_{r}_{l}"] = ext[r][l]
            row["SwitchToGCC"] = sum(sw["GCC"][l]["in"] for l in LEVELS)
            row["SwitchFromGCC"] = sum(sw["VI"][l]["in"] for l in LEVELS)
            row["VI_quit_switch_rate"] = (sum(fl["VI"][l]["quits"] + sw["VI"][l]["out"] for l in LEVELS) / max(row["H_VI"], 1))
            row["Conversions"] = sum(conv.values()); row["Expiry"] = sum(expiry.values())
            row["Grad_total"] = sum(Grad.values()); row["Ext_total"] = sum(ext[r][l] for r in REGIONS for l in LEVELS)
            row["HeadTotal"] = sum(H[u][l] for u in UNITS for l in LEVELS)
            row.update(Revenue=Revenue, VendorCost=VendorCost, Margin=Margin, Viability=V_idx, Disc=Disc, AvgIdx=AvgIdx,
                       Overhead=st["Overhead"], CostProg=st["CostProg"], AICost=AICost, VisaCost=VisaCost, SalesCost=SalesCost,
                       VendorLabour=VendorLabour, ConsumerSpend=ConsumerSpend, PU=PU, Power=Power,
                       VendorHead=sum(H[u][l] for u in VENDOR for l in LEVELS),
                       WI_VI=st["WI"]["VI"], WI_GCC=st["WI"]["GCC"], WI_IH=st["WI"]["IH"],
                       VendorShare=VendorShare, IHWork=st["IHWork"], GCCWork=st["GCCWork"],
                       Del_VI=Delivered["VI"], RevOnsite=(Delivered["OV"] * pr["Price_OV"] + Delivered["OL"] * pr["Price_OL"]) * AvgIdx,
                       LabourRaw=sum(LabourCost[u] for u in VENDOR), BookTurnover=BookTurnover, Expiry=Expiry,
                       ClientP=st["ClientP"], WorkCheck=st["IHWork"] + st["GCCWork"] + VendorShare,
                       AvgNewDur=sum(TypeShare[k] * Dnew[k] for k in TYPES),
                       InForceDur=VendorShare / max(Expiry, 1e-12))
            for k in TYPES:
                vol = st["Leg"][k] + st["NewV"][k]
                row["Mix_" + k] = vol / max(VendorShare, 1e-12)
                row["RevMix_" + k] = TypeIdxVol[k] / max(sum(TypeIdxVol.values()), 1e-12)
                row["SignShare_" + k] = TypeShare[k]; row["Dur_" + k] = Dnew[k]
            for e in OPTIONS:
                row["SrcTarget_" + e] = SrcTarget[e]; row["SrcPerc_" + e] = st["SrcPerc"][e]; row["Cost_" + e] = Cost[e]
            for w in WTYPES:
                row["Dem_" + w] = sum(Demand[x][w] for x in SECTORS); row["P_" + w] = Pw[w]
            for x in SECTORS:
                c = cons[x]
                row["Dem_" + x] = sum(Demand[x][w] for w in WTYPES); row["AC_" + x] = st["AC"][x]; row["LOB_" + x] = st["LOB"][x]
                row["Port_" + x] = st["Port"][x]; row["SpendRatio_" + x] = st["SpendRatio"][x]; row["Approval_" + x] = c["Approval"]
                row["Seats_" + x] = c["Seats"]; row["Budget_" + x] = c["Budget"]; row["Committed_" + x] = c["Committed"]
            row["LOB"] = sum(st["LOB"][x] for x in SECTORS); row["Seats"] = sum(cons[x]["Seats"] for x in SECTORS)
            row["Port"] = sum(st["Port"][x] for x in SECTORS); row["AgentWork"] = sum(cons[x]["AgentWork"] for x in SECTORS)
            row["SeatSpend"] = sum(cons[x]["SeatSpend"] for x in SECTORS); row["CreditSpend"] = sum(cons[x]["CreditSpend"] for x in SECTORS)
            row["BaseSeatSpend"] = sum(st["SeatsB"][x] for x in SECTORS) * pr["BaseSeatPrice"]
            row["AISeatSpend"] = row["SeatSpend"] - row["BaseSeatSpend"]
            row["CloudSpend"] = sum(cons[x]["CloudSpend"] for x in SECTORS); row["ServicesSpend"] = ServicesSpend
            row["Committed"] = sum(cons[x]["Committed"] for x in SECTORS); row["Budget"] = sum(cons[x]["Budget"] for x in SECTORS)
            row["Platform"] = row["SeatSpend"] + row["CreditSpend"] * (1 - pr["Leakage"])
            row["AIProviders"] = row["CreditSpend"] * pr["Leakage"] + AICost + AICostPerUnit * AIShareOfOutput * (Delivered["IH"] + Delivered["GCC"])
            row["AIBuild"] = sum(cons[x]["AIBuild"] for x in SECTORS); row["Att"] = Att; row["CostIdx"] = CostIdx; row["CostPerc"] = st["CostPerc"]
            row["ConsIT"] = ConsIT; row["LOBAuto"] = LOBAuto
            rows.append(row)
        if step == n:
            break
        # ---- integrate ----
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
        st["Att"] += d * AttAdopt
        st["CostPerc"] += d * (CostIdx - st["CostPerc"]) / pr["CostPerceptionTime"]
        for u in UNITS:
            r = POOL[u]
            for l in LEVELS:
                x = fl[u][l]
                promo_in = promo[u][l]
                conv_in = conv[l] if u == "OL" else 0.0
                visa_out = (expiry[l] + conv[l]) if u == "OV" else 0.0
                st["V"][u][l] += d * (x["openings"] - cancel[u][l] - promo_in - sw[u][l]["in"] - hires[u][l])
                st["O"][u][l] += d * (hires[u][l] - x["onboard"])
                st["H"][u][l] += d * (x["onboard"] + promo_in + sw[u][l]["in"] + conv_in - x["promo_out"] - x["quits"]
                                       - x["leave"] - x["retire"] - x["layoffs"] - sw[u][l]["out"] - visa_out)
                st["R"][r][l] += d * x["layoffs"]
                st["U"][r][l] += d * (x["quits"] - hires[u][l])
                st["LeftField"][r] += d * x["leave"]
                st["Retired"][r] += d * x["retire"]
            if u == "OV":
                for l in LEVELS:
                    st["U"]["IN"][l] += d * expiry[l]   # visa holders return to the India pool
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
        st["A"] += d * Adoption
        st["PerceivedP"] += d * (P_eff - st["PerceivedP"]) / pr["PerceptionTime"]
        st["TightPerc"] += d * (VisaTight - st["TightPerc"]) / pr["TightPerceptionTime"]
        st["ClientP"] += d * (P_eff - st["ClientP"]) / pr["ClientPerceptionTime"]
        st["ClientPRef"] += d * (st["ClientP"] - st["ClientPRef"]) / pr["TrendTime"]
        st["Overhead"] += d * (pr["OverheadRate"] * Revenue - st["Overhead"]) / pr["OverheadAdjTime"]
        st["Viability"] += d * (Margin - st["Viability"]) / pr["ViabilityTime"]
        st["CostProg"] += d * (CostProgTarget - st["CostProg"]) / pr["CostProgramTime"]
        st["Disc"] += d * (DiscTarget - st["Disc"]) / pr["DiscAdjTime"]
        st["ShareRef"] += d * (VendorShare - st["ShareRef"]) / pr["ShareRefTime"]
        for k in TYPES:
            st["Leg"][k] += d * (-ExpLeg[k])
            st["NewV"][k] += d * (Sign[k] - ExpNew[k])
            st["NewD"][k] += d * (Sign[k] * Dnew[k] - st["NewV"][k])
            st["NewP"][k] += d * (Sign[k] * PNew[k] - ExpNew[k] * AvgP[k] - st["NewP"][k] * Glide[k])
        st["IHWork"] += d * (Contested * st["SrcPerc"]["IH"] - pr["Contest"] * IHTurn)
        st["GCCWork"] += d * (Contested * st["SrcPerc"]["GCC"] - pr["Contest"] * GCCTurn)
        for e in OPTIONS:
            st["SrcPerc"][e] += d * (SrcTarget[e] - st["SrcPerc"][e]) / pr["SrcPerceptionTime"]
        for u in UNITS:
            st["WI"][u] += d * (WITarget[u] - st["WI"][u]) / pr["WageAdjTime"]
        # minimum tracking
        for grp in ("H", "O", "V"):
            for u in UNITS:
                for l in LEVELS:
                    key = f"{grp}_{u}_{l}"; mins[key] = min(mins.get(key, 1e18), st[grp][u][l])
        for grp in ("R", "U"):
            for r in REGIONS:
                for l in LEVELS:
                    key = f"{grp}_{r}_{l}"; mins[key] = min(mins.get(key, 1e18), st[grp][r][l])
        t += dt
    return rows, st, mins


def blank_state():
    return {"BL": {x: {w: 50_000.0 * SEC6["SectorShare"][x] * WT6["Mix"][w] for w in WTYPES} for x in SECTORS}, "A": P["A0"], "PerceivedP": 1.0, "TightPerc": P["VTBase"],
            "H": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "O": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "V": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "R": {r: {l: 0.0 for l in LEVELS} for r in REGIONS},
            "U": {r: {l: 0.0 for l in LEVELS} for r in REGIONS},
            "Pipeline": {r: 4 * P["BaseEnrolment_" + r] for r in REGIONS},
            "LeftField": {r: 0.0 for r in REGIONS}, "Retired": {r: 0.0 for r in REGIONS},
            "PUS": {r: P["NormalUnempRate_" + r] for r in REGIONS},
            "PUL": {r: P["NormalUnempRate_" + r] for r in REGIONS},
            "ClientP": 1.0, "ClientPRef": 1.0, "Overhead": 0.0, "Viability": P["NormalMargin"],
            "CostProg": 0.0, "WI": {u: 1.0 for u in UNITS}, "Disc": 0.0, "ShareRef": 0.6,
            "Leg": {k: 0.6 * P["Mix0_" + k] for k in TYPES}, "NewV": {k: 0.0 for k in TYPES},
            "NewD": {k: 0.0 for k in TYPES}, "NewP": {k: 0.0 for k in TYPES},
            "IHWork": P["InHouseShare0"], "GCCWork": P["GCCShare0"],
            "SrcPerc": {"IH": 0.107, "GCC": 0.057, "VEND": 0.836},
            "AC": {x: P["AC0"] for x in SECTORS}, "LOB": {x: P.get("LOB0_" + x, 0.0) for x in SECTORS},
            "Port": {x: P.get("Port0_" + x, 0.0) for x in SECTORS}, "SeatsB": {x: P.get("Seats0_" + x, 0.0) for x in SECTORS},
            "SpendRatio": {x: P["NormalUtil"] for x in SECTORS}, "Att": P["Att0"], "CostPerc": 1.0}


def seed_state():
    st = blank_state()
    share = {"IH": 0.30, "GCC": 0.10, "VI": 0.45, "OV": 0.09, "OL": 0.06}
    for u in UNITS:
        for l, h in zip(LEVELS, (16_500.0, 21_800.0, 48_800.0)):
            st["H"][u][l] = h * share[u]; st["V"][u][l] = 0.03 * h * share[u]
    for r in REGIONS:
        for l in LEVELS:
            st["U"][r][l] = 1000.0
    return st


def equilibrium(years=200.0, state=None):
    st0 = state or seed_state()
    _, st, _ = run(st0, ai_on=False, stop=years, record_every=years)
    st["A"] = P["A0"]; st["LeftField"] = {r: 0.0 for r in REGIONS}; st["Retired"] = {r: 0.0 for r in REGIONS}
    return st
