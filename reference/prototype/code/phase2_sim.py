"""Phase 2 prototype - Phase 1 core loop + labour market.

Adds: Junior/Mid/Senior aging chain, vacancies with a matching function,
onboarding, recovering vs active seekers, exits from IT, entrant pipeline
with job-prospect feedback. One sector, one aggregate employer, one region.
Wages held constant (no money in Phase 2).
Euler integration; Year = 2024 + t.
"""
import json
import math

LEVELS = ("J", "M", "S")

P = dict(
    # ---- Phase 1 (unchanged) ----
    BaseDemand=100_000.0, WorkPerPerson=1.0, TargetClearanceTime=0.5,
    MinCompletionTime=0.25, AbandonTolerance=1.5, AbandonTime=1.0,
    LayoffAdjTime=0.25, MinLayoffTime=0.25, HireAdjTime=0.5, PerceptionTime=1.0,
    a_2024=0.20, a_max=0.60, g=0.10, s=5.0, v=0.05, p=0.03, q=0.40, A0=0.05,
    MinAdoptionTime=0.0625, JevonsEps=0.0, JevonsCap=2.0,
    DemandStep=0.0, StepYear=2028.0,
    # ---- Phase 2: levels ----
    W_J=0.6, W_M=1.0, W_S=1.4,                 # output weight per level
    Share0_J=0.19, Share0_M=0.25, Share0_S=0.56,  # desired level mix, no AI (consistent with career flows)
    JuniorCut=0.5,                             # share of junior roles AI removes at full adoption
    TimeInJunior=3.0, TimeInMid=5.0,           # yr until eligible for promotion
    PromoFillTime=0.125,                       # yr, internal candidates fill upper vacancies first
    QuitRate_J=0.15, QuitRate_M=0.10, QuitRate_S=0.08,      # 1/yr, voluntary moves into job search
    LeaveITRate_J=0.05, LeaveITRate_M=0.06, LeaveITRate_S=0.04,  # 1/yr, employed leaving IT
    RetireRate_S=0.033,                        # 1/yr, seniors (employed and unemployed)
    OnboardTime=0.25, OnboardProductivity=0.5,
    CancelTime=0.25,
    # experienced entry from other industries and career breaks (mid and senior only)
    ExtEntryRate_M=0.05, ExtEntryRate_S=0.05,  # 1/yr of headcount per unit of excess time-to-fill
    NormalTTF_M=0.54, NormalTTF_S=0.11,        # yr, calibrated to the steady state
    ExtEntryMax=3.0,                           # cap on the excess ratio
    # matching
    m=4.0, alpha=0.5, MinFillTime=0.0625,
    # unemployment pools
    RecoveryTime=0.33,
    BaseLeaveFrac_J=0.05, BaseLeaveFrac_M=0.10, BaseLeaveFrac_S=0.20,
    SeekerExitRate=0.10,                       # 1/yr, long-term seekers giving up
    UnempPerceptionTime=0.5,                   # yr, smoothing for the leave-IT decision
    # entrants
    BaseEnrolment=10_000.0, StudyTime=4.0,
    StudentPerceptionTime=2.0, EnrolSensitivity=1.0,
    NormalUnempRate=0.06,
)


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def run(init, ai_on=True, dt=1/16, stop=16.0, record_every=0.25, **over):
    pr = dict(P); pr.update(over)
    st = dict(init)
    rows = []
    n = int(round(stop / dt)); rk = int(round(record_every / dt))
    mins = {}
    t = 0.0
    for k in range(n + 1):
        y = 2024 + t
        # ---- productivity (Phase 1) ----
        a = max(0.0, pr["a_max"] - (pr["a_max"] - pr["a_2024"]) * (1 - pr["g"]) ** (y - 2024))
        P_AI = 1 / ((1 - a) + a / pr["s"] + a * pr["v"])
        A = st["A"]
        P_eff = A * P_AI + (1 - A) if ai_on else 1.0
        Jev = min(pr["JevonsCap"], (1 / P_eff) ** (-pr["JevonsEps"]))
        Demand = pr["BaseDemand"] * (1 + (pr["DemandStep"] if y >= pr["StepYear"] else 0)) * Jev
        # ---- capacity ----
        H = {l: st["H_" + l] for l in LEVELS}
        O = {l: st["O_" + l] for l in LEVELS}
        V = {l: st["V_" + l] for l in LEVELS}
        R = {l: st["R_" + l] for l in LEVELS}
        U = {l: st["U_" + l] for l in LEVELS}
        W = {l: pr["W_" + l] for l in LEVELS}
        EffStaff = sum(W[l] * (H[l] + pr["OnboardProductivity"] * O[l]) for l in LEVELS)
        Capacity = pr["WorkPerPerson"] * P_eff * EffStaff
        Completion = min(Capacity, st["Backlog"] / pr["MinCompletionTime"])
        Abandon = max(0.0, st["Backlog"] - Completion * pr["AbandonTolerance"]) / pr["AbandonTime"]
        # ---- desired by level ----
        DesiredEff = st["Backlog"] / (pr["TargetClearanceTime"] * pr["WorkPerPerson"] * st["PerceivedP"])
        sJ = pr["Share0_J"] * (1 - pr["JuniorCut"] * (A if ai_on else 0.0))
        rest0 = pr["Share0_M"] + pr["Share0_S"]
        sM = pr["Share0_M"] * (1 - sJ) / rest0
        sS = pr["Share0_S"] * (1 - sJ) / rest0
        Share = {"J": sJ, "M": sM, "S": sS}
        denom = sum(Share[l] * W[l] for l in LEVELS)
        Desired = {l: DesiredEff * Share[l] / denom for l in LEVELS}
        # ---- unemployment and prospects ----
        Unemployed = sum(R.values()) + sum(U.values())
        LabourForce = sum(H.values()) + sum(O.values()) + Unemployed
        UnempRate = Unemployed / LabourForce
        LeaveEffect = clamp(st["PercUnempShort"] / pr["NormalUnempRate"], 0.5, 3.0)
        # ---- per-level flows ----
        f = {}
        promo = {}
        # vacancy outflows in order: cancellations, then promotions, then external hires,
        # all within V / MinFillTime so vacancies can never go negative
        pre = {}
        for l in LEVELS:
            surplus_l = H[l] + O[l] - Desired[l]
            cancel_l = (max(0.0, V[l] - (-surplus_l)) if surplus_l <= 0 else V[l]) / pr["CancelTime"]
            cap_l = V[l] / pr["MinFillTime"]
            pre[l] = (surplus_l, min(cancel_l, cap_l), cap_l)
        def avail(l):
            return max(0.0, pre[l][2] - pre[l][1])
        promo["M"] = min(H["J"] / pr["TimeInJunior"], V["M"] / pr["PromoFillTime"], avail("M"))
        promo["S"] = min(H["M"] / pr["TimeInMid"], V["S"] / pr["PromoFillTime"], avail("S"))
        promo["J"] = 0.0
        for l in LEVELS:
            promo_in = promo[l]
            promo_out = promo["M"] if l == "J" else (promo["S"] if l == "M" else 0.0)
            quits = H[l] * pr["QuitRate_" + l]
            leave = H[l] * pr["LeaveITRate_" + l]
            retire = H[l] * pr["RetireRate_S"] if l == "S" else 0.0
            netloss = quits + leave + retire + promo_out
            surplus, cancel, cap = pre[l]
            if surplus <= 0:
                openings = max(0.0, netloss + (-surplus - V[l]) / pr["HireAdjTime"])
                layoffs = 0.0
            else:
                openings = 0.0
                layoffs = min(max(0.0, surplus / pr["LayoffAdjTime"] - netloss), H[l] / pr["MinLayoffTime"])
            match = pr["m"] * (U[l] ** pr["alpha"]) * (V[l] ** (1 - pr["alpha"])) if U[l] > 0 and V[l] > 0 else 0.0
            hires = max(0.0, min(match, cap - cancel - promo_in, U[l] / pr["MinFillTime"]))
            fills = hires + promo_in
            ttf = V[l] / max(fills, 1.0)
            if l == "J":
                ext_entry = 0.0
            else:
                ext_entry = pr["ExtEntryRate_" + l] * H[l] * clamp(ttf / pr["NormalTTF_" + l] - 1, 0.0, pr["ExtEntryMax"])
            onboard_done = O[l] / pr["OnboardTime"]
            rec_out = R[l] / pr["RecoveryTime"]
            leave_frac = clamp(pr["BaseLeaveFrac_" + l] * LeaveEffect, 0.0, 0.9)
            rec_to_left = rec_out * leave_frac
            rec_to_seek = rec_out * (1 - leave_frac)
            seek_exit = U[l] * pr["SeekerExitRate"] * LeaveEffect
            seek_retire = U[l] * pr["RetireRate_S"] if l == "S" else 0.0
            rec_retire = R[l] * pr["RetireRate_S"] if l == "S" else 0.0
            f[l] = dict(promo_out=promo_out, promo_in=promo_in, quits=quits, leave=leave, retire=retire, ext_entry=ext_entry, ttf=ttf,
                        openings=openings, cancel=cancel, layoffs=layoffs, hires=hires,
                        onboard_done=onboard_done, rec_to_left=rec_to_left, rec_to_seek=rec_to_seek,
                        seek_exit=seek_exit, seek_retire=seek_retire, rec_retire=rec_retire)
        # ---- entrants ----
        EnrolEffect = clamp(1 - pr["EnrolSensitivity"] * (st["PercUnempLong"] / pr["NormalUnempRate"] - 1), 0.4, 1.3)
        Enrolment = pr["BaseEnrolment"] * EnrolEffect
        Graduation = st["Pipeline"] / pr["StudyTime"]
        # ---- adoption, perception ----
        Adoption = min((pr["p"] + pr["q"] * A) * (1 - A), (1 - A) / pr["MinAdoptionTime"]) if ai_on else 0.0
        TTF = {l: f[l]["ttf"] for l in LEVELS}

        if k % rk == 0:
            row = {"year": round(y, 4), "UnempRate": UnempRate, "Enrolment": Enrolment, "Graduation": Graduation,
                   "P_eff": P_eff, "A": A, "Backlog": st["Backlog"], "Demand": Demand,
                   "HeadTotal": sum(H.values())}
            for l in LEVELS:
                row["H_" + l] = H[l]; row["V_" + l] = V[l]; row["U_" + l] = U[l]; row["R_" + l] = R[l]
                row["O_" + l] = O[l]; row["TTF_" + l] = TTF[l]; row["Desired_" + l] = Desired[l]
                row["Layoffs_" + l] = f[l]["layoffs"]; row["Hires_" + l] = f[l]["hires"]; row["Promo_" + l] = f[l]["promo_in"]; row["Ext_" + l] = f[l]["ext_entry"]
            row["LeftField"] = st["LeftField"]; row["Pipeline"] = st["Pipeline"]
            rows.append(row)
        if k == n:
            break
        # ---- integrate ----
        d = dt
        st["Backlog"] += d * (Demand - Completion - Abandon)
        for l in LEVELS:
            x = f[l]
            st["V_" + l] += d * (x["openings"] - x["cancel"] - x["hires"] - x["promo_in"])
            st["O_" + l] += d * (x["hires"] - x["onboard_done"])
            st["H_" + l] += d * (x["onboard_done"] + x["promo_in"] - x["promo_out"] - x["quits"] - x["leave"] - x["retire"] - x["layoffs"])
            st["R_" + l] += d * (x["layoffs"] - x["rec_to_left"] - x["rec_to_seek"] - x["rec_retire"])
            grad_in = Graduation if l == "J" else 0.0
            st["U_" + l] += d * (grad_in + x["quits"] + x["rec_to_seek"] + x["ext_entry"] - x["hires"] - x["seek_exit"] - x["seek_retire"])
            st["LeftField"] += d * (x["leave"] + x["rec_to_left"] + x["seek_exit"])
        st["Retired"] += d * (f["S"]["retire"] + f["S"]["seek_retire"] + f["S"]["rec_retire"])
        st["Pipeline"] += d * (Enrolment - Graduation)
        st["A"] += d * Adoption
        st["PerceivedP"] += d * (P_eff - st["PerceivedP"]) / pr["PerceptionTime"]
        st["PercUnempShort"] += d * (UnempRate - st["PercUnempShort"]) / pr["UnempPerceptionTime"]
        st["PercUnempLong"] += d * (UnempRate - st["PercUnempLong"]) / pr["StudentPerceptionTime"]
        for kk, vv in st.items():
            mins[kk] = min(mins.get(kk, vv), vv)
        t += dt
    return rows, st, mins


def equilibrium():
    """Burn in with AI off for 200 years to find the steady state."""
    init = dict(Backlog=50_000.0, A=P["A0"], PerceivedP=1.0, Pipeline=40_000.0,
                LeftField=0.0, Retired=0.0, PercUnempShort=0.06, PercUnempLong=0.06)
    for l, h in zip(LEVELS, (16_500.0, 21_800.0, 48_800.0)):
        init.update({"H_" + l: h, "O_" + l: 1_000.0, "V_" + l: 1_000.0, "R_" + l: 0.0, "U_" + l: 2_000.0})
    _, st, _ = run(init, ai_on=False, stop=200.0, record_every=50.0)
    st["A"] = P["A0"]; st["LeftField"] = 0.0; st["Retired"] = 0.0
    return st


if __name__ == "__main__":
    eq = equilibrium()
    print("EQUILIBRIUM")
    for k2, v2 in eq.items():
        print(f"  {k2}: {v2:,.2f}")
    json.dump(eq, open("/home/claude/phase2_eq.json", "w"), indent=1)
