"""Phase 4 prototype - Phase 3 + vendor financials, price index, viability, endogenous wages.

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
    InHouseShare=0.30, GCCShare0=0.10, GCCShareEnd=0.10, GCCRampStart=2027.0, GCCRampEnd=2031.0,
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
    Price_VI=32_000.0, Price_OV=150_000.0, Price_OL=150_000.0,   # USD per BFY delivered, before PriceIndex
    VisaFeePerHire=100_000.0, VisaComplianceCost=5_000.0,        # USD per visa hire; USD per visa holder per year
    AICost2024=8_000.0, AICostDecline=0.15, AIShockMult=1.0, AIShockStart=2030.0, AIShockEnd=2032.0,
    OverheadRate=0.08, OverheadAdjTime=2.0,
    PassThrough=1.0, ClientPerceptionTime=1.5, RepricingTime=2.0,
    PriceShock=0.0, PriceShockYear=2028.0,
    ViabilityTime=2.0, NormalMargin=0.18, Deadband=0.02,
    ShareSens=2.0, ExitThreshold=0.0, ExitPenalty=3.0, VSEMin=0.2, VSEMax=1.1, ShareAdjTime=2.0,
    CostProgramSens=1.5, MaxSavings=0.15, CostProgramTime=2.0,
    WagesEndogenous=1.0, WageElasticity=0.25, WageRestraint=1.0, WageAdjTime=2.0, WageMin=0.85, WageMax=1.3,
)
VENDOR = ("VI", "OV", "OL")


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
    for k in range(n + 1):
        y = 2024 + t
        # ---- Phase 1 ----
        a = max(0.0, pr["a_max"] - (pr["a_max"] - pr["a_2024"]) * (1 - pr["g"]) ** (y - 2024))
        P_AI = 1 / ((1 - a) + a / pr["s"] + a * pr["v"])
        A = st["A"]
        P_eff = A * P_AI + (1 - A) if ai_on else 1.0
        Jev = min(pr["JevonsCap"], (1 / P_eff) ** (-pr["JevonsEps"]))
        Demand = pr["BaseDemand"] * (1 + (pr["DemandStep"] if y >= pr["StepYear"] else 0)) * Jev
        H, O, V = st["H"], st["O"], st["V"]
        R, U = st["R"], st["U"]
        W = {l: pr["W_" + l] for l in LEVELS}
        EffStaff = sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for u in UNITS for l in LEVELS)
        Capacity = pr["WorkPerPerson"] * P_eff * EffStaff
        Completion = min(Capacity, st["Backlog"] / pr["MinCompletionTime"])
        Abandon = max(0.0, st["Backlog"] - Completion * pr["AbandonTolerance"]) / pr["AbandonTime"]
        DesiredEff = st["Backlog"] / (pr["TargetClearanceTime"] * pr["WorkPerPerson"] * st["PerceivedP"])
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
        GCCShare = ramp(y, pr["GCCRampStart"], pr["GCCRampEnd"], pr["GCCShare0"], pr["GCCShareEnd"])
        VendorBase = 1 - pr["InHouseShare"] - GCCShare
        VendorShare = VendorBase * st["VSE"]
        Lost = VendorBase - VendorShare
        IHShare = pr["InHouseShare"] + Lost * pr["InHouseShare"] / (pr["InHouseShare"] + GCCShare)
        GCCShareEff = GCCShare + Lost * GCCShare / (pr["InHouseShare"] + GCCShare)
        UShare = {"IH": IHShare, "GCC": GCCShareEff, "VI": VendorShare * (1 - OnsiteShare),
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
        Adoption = min((pr["p"] + pr["q"] * A) * (1 - A), (1 - A) / pr["MinAdoptionTime"]) if ai_on else 0.0

        # ---- Phase 4: finance ----
        capu = {u: sum(W[l] * (H[u][l] + pr["OnboardProductivity"] * O[u][l]) for l in LEVELS) for u in UNITS}
        Delivered = {u: Completion * capu[u] / max(EffStaff, 1e-9) for u in UNITS}
        Wage = {u: {l: pr["BaseWage_" + u] * pr["WageMult_" + l] * st["WI"][u] for l in LEVELS} for u in UNITS}
        LabourCost = {u: sum((H[u][l] + O[u][l]) * Wage[u][l] for l in LEVELS) for u in UNITS}
        PriceTarget = (1 / st["ClientP"]) ** pr["PassThrough"] * (1 - (pr["PriceShock"] if y >= pr["PriceShockYear"] else 0.0))
        Revenue = sum(Delivered[u] * pr["Price_" + u] * st["PriceIndex"] for u in VENDOR)
        AIShock = pr["AIShockMult"] if pr["AIShockStart"] <= y < pr["AIShockEnd"] else 1.0
        AICostPerUnit = pr["AICost2024"] * (1 - pr["AICostDecline"]) ** (y - 2024) * AIShock
        AIShareOfOutput = 1 - 1 / P_eff
        AICost = AICostPerUnit * sum(Delivered[u] for u in VENDOR) * AIShareOfOutput
        VisaCost = sum(hires["OV"][l] for l in LEVELS) * pr["VisaFeePerHire"] + sum(H["OV"][l] for l in LEVELS) * pr["VisaComplianceCost"]
        VendorLabour = sum(LabourCost[u] for u in VENDOR) * (1 - st["CostProg"])
        VendorCost = VendorLabour + VisaCost + AICost + st["Overhead"]
        Margin = (Revenue - VendorCost) / max(Revenue, 1.0)
        V_idx = st["Viability"]
        dev = V_idx - pr["NormalMargin"]
        DevEff = (dev - pr["Deadband"]) if dev > pr["Deadband"] else ((dev + pr["Deadband"]) if dev < -pr["Deadband"] else 0.0)
        VSETarget = clamp(1 + pr["ShareSens"] * DevEff - pr["ExitPenalty"] * max(0.0, pr["ExitThreshold"] - V_idx), pr["VSEMin"], pr["VSEMax"])
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
        ConsumerSpend = LabourCost["IH"] + LabourCost["GCC"] + Revenue

        if k % rk == 0:
            row = {"year": round(y, 4), "P_eff": P_eff, "A": A, "Backlog": st["Backlog"], "VisaTight": VisaTight,
                   "OnsiteShare": OnsiteShare, "VisaMix": VisaMix, "GCCShare": GCCShare, "VisaCap": VisaCap,
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
            row.update(Revenue=Revenue, VendorCost=VendorCost, Margin=Margin, Viability=V_idx, VSE=st["VSE"],
                       PriceIndex=st["PriceIndex"], Overhead=st["Overhead"], CostProg=st["CostProg"],
                       AICost=AICost, VisaCost=VisaCost, VendorLabour=VendorLabour, ConsumerSpend=ConsumerSpend,
                       VendorHead=sum(H[u][l] for u in VENDOR for l in LEVELS),
                       WI_VI=st["WI"]["VI"], WI_GCC=st["WI"]["GCC"], WI_IH=st["WI"]["IH"], VendorShare=VendorShare,
                       Del_VI=Delivered["VI"], RevOnsite=Delivered["OV"] * pr["Price_OV"] * st["PriceIndex"] + Delivered["OL"] * pr["Price_OL"] * st["PriceIndex"],
                       LabourRaw=sum(LabourCost[u] for u in VENDOR))
            rows.append(row)
        if k == n:
            break
        # ---- integrate ----
        d = dt
        st["Backlog"] += d * (Demand - Completion - Abandon)
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
        st["PriceIndex"] += d * (PriceTarget - st["PriceIndex"]) / pr["RepricingTime"]
        st["Overhead"] += d * (pr["OverheadRate"] * Revenue - st["Overhead"]) / pr["OverheadAdjTime"]
        st["Viability"] += d * (Margin - st["Viability"]) / pr["ViabilityTime"]
        st["VSE"] += d * (VSETarget - st["VSE"]) / pr["ShareAdjTime"]
        st["CostProg"] += d * (CostProgTarget - st["CostProg"]) / pr["CostProgramTime"]
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
    return {"Backlog": 50_000.0, "A": P["A0"], "PerceivedP": 1.0, "TightPerc": P["VTBase"],
            "H": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "O": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "V": {u: {l: 0.0 for l in LEVELS} for u in UNITS},
            "R": {r: {l: 0.0 for l in LEVELS} for r in REGIONS},
            "U": {r: {l: 0.0 for l in LEVELS} for r in REGIONS},
            "Pipeline": {r: 4 * P["BaseEnrolment_" + r] for r in REGIONS},
            "LeftField": {r: 0.0 for r in REGIONS}, "Retired": {r: 0.0 for r in REGIONS},
            "PUS": {r: P["NormalUnempRate_" + r] for r in REGIONS},
            "PUL": {r: P["NormalUnempRate_" + r] for r in REGIONS},
            "ClientP": 1.0, "PriceIndex": 1.0, "Overhead": 0.0, "Viability": P["NormalMargin"], "VSE": 1.0,
            "CostProg": 0.0, "WI": {u: 1.0 for u in UNITS}}


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
