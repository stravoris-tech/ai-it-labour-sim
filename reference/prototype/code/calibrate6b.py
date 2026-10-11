"""Phase 6b calibration. Builds the 2024 steady state for eight employment units and three vendors:
1) seed units from the Phase 6a labour stocks by 2024 sourcing shares; 2) burn in the labour market with
sourcing frozen and finance feedback off, updating the regional 'normal' values; 3) solve each vendor's
price multiplier for its target margin; 4) solve sourcing and contract-type constants, CostRef, adoption
cost bases, seats and budgets so that AI-off 2024 is a steady state."""
import json, math, phase6b_sim as S

p6 = json.load(open("phase6a_results.json"))
i6 = p6["init"]
for k in ("BaseEnrolment_IN", "BaseEnrolment_ON", "NormalUnempRate_IN", "NormalUnempRate_ON",
          "NormalTTF_IN_M", "NormalTTF_IN_S", "NormalTTF_ON_M", "NormalTTF_ON_S", "CostPerBFY0"):
    S.P[k] = p6["params"][k]
for x in S.SECTORS:
    S.P["LOB0_" + x] = p6["params"]["LOB0_" + x]; S.P["Port0_" + x] = p6["params"]["Port0_" + x]
    S.P["Seats0_" + x] = p6["params"]["Seats0_" + x]; S.P["Budget0_" + x] = p6["params"]["Budget0_" + x]
for e in S.EMPLOYERS:
    S.P["LabourCostPB0_" + e] = 1.0
    for x in S.SECTORS:
        S.P[f"SrcASC_{x}_{e}"] = 0.0
OFF = dict(FreezeSourcing=1.0, ApprovalSens=0.0, WagesEndogenous=0.0, CostProgramSens=0.0, RivalSens=0.0, ShareLossSens=0.0, PowerSens=0.0)


def type_constants():
    for v in S.VENDORS:
        sig = {k: S.MIX0[v][k] / S.P["BaseDur_" + k] for k in S.TYPES}
        z = sum(sig.values())
        for k in S.TYPES:
            S.P[f"TypeASC_{v}_{k}"] = round(math.log(sig[k] / z), 4)


def exp_rate0(v):
    return sum(S.MIX0[v][k] / S.P["BaseDur_" + k] for k in S.TYPES)


def decision_shares():
    PS = {}
    for x in S.SECTORS:
        turn = {"IH": S.SRC0[x]["IH"] / S.P["IHReviewTime"], "GCC": S.SRC0[x]["GCC"] / S.P["GCCReviewTime"]}
        for v in S.VENDORS:
            turn[v] = S.SRC0[x][v] * exp_rate0(v)
        z = sum(turn.values())
        PS[x] = {e: turn[e] / z for e in S.EMPLOYERS}
    return PS


def unit_weights():
    agg = {e: sum(S.SEC6["SectorShare"][x] * S.SRC0[x][e] for x in S.SECTORS) for e in S.EMPLOYERS}
    within = {"IH": 1.0, "GCC": 1.0, "VI": 1 - S.P["OnsiteShare0"], "OV": S.P["OnsiteShare0"] * S.P["VisaMix0"],
              "OL": S.P["OnsiteShare0"] * (1 - S.P["VisaMix0"]), "SI_IN": S.P["GSIOffshore"], "SI_ON": 1 - S.P["GSIOffshore"], "BQ": 1.0}
    return {u: agg[S.EMP_OF[u]] * within[u] for u in S.UNITS}, agg


def seed():
    st = S.blank_state()
    wts, agg = unit_weights()
    for g in ("H", "O", "V"):
        tot = {l: sum(i6[g][u][l] for u in i6[g]) for l in S.LEVELS}
        for u in S.UNITS:
            for l in S.LEVELS:
                st[g][u][l] = tot[l] * wts[u]
    for g in ("R", "U", "Pipeline", "PUS", "PUL"):
        st[g] = json.loads(json.dumps(i6[g]))
    st["BL"] = json.loads(json.dumps(i6["BL"]))
    for x in S.SECTORS:
        st["LOB"][x] = S.P["LOB0_" + x]; st["Port"][x] = S.P["Port0_" + x]; st["SeatsB"][x] = S.P["Seats0_" + x]
    st["SrcPerc"] = decision_shares()
    return st, agg


def reset_finance(st):
    st["A"] = {e: S.P["A0"] for e in S.EMPLOYERS}
    for k in ("PerceivedP", "ClientP", "ClientPRef"):
        st[k] = {e: 1.0 for e in S.EMPLOYERS}
    st["WI"] = {u: 1.0 for u in S.UNITS}
    st["CostProg"] = {v: 0.0 for v in S.VENDORS}; st["Disc"] = {v: 0.0 for v in S.VENDORS}
    st["Leg"] = {v: dict(S.MIX0[v]) for v in S.VENDORS}
    for g in ("NewV", "NewD", "NewP"):
        st[g] = {v: {k: 0.0 for k in S.TYPES} for v in S.VENDORS}
    st["LeftField"] = {r: 0.0 for r in S.REGIONS}; st["Retired"] = {r: 0.0 for r in S.REGIONS}
    st["TightPerc"] = S.P["VTBase"]; st["Att"] = S.P["Att0"]; st["CostPerc"] = 1.0
    st["AC"] = {x: S.P["AC0"] for x in S.SECTORS}
    st["SpendRatio"] = {x: S.P["NormalUtil"] for x in S.SECTORS}
    return st


def calibrate(verbose=False, rounds=10):
    type_constants()
    st, agg = seed()
    target = {"IN": 0.05, "ON": 0.055}
    for rg in S.REGIONS:
        S.P["NormalUnempRate_" + rg] = target[rg]; st["PUS"][rg] = st["PUL"][rg] = target[rg]
    for it in range(rounds):
        _, st, _ = S.run(st, ai_on=False, stop=40.0, record_every=40.0, **OFF)
        r = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
        for rg in S.REGIONS:
            S.P["BaseEnrolment_" + rg] *= math.exp(3.0 * (target[rg] - r["Unemp_" + rg]) / target[rg] * 0.5)
            for l in ("M", "S"):
                S.P[f"NormalTTF_{rg}_{l}"] = r[f"TTF_{rg}_{l}"]
        if verbose:
            print("burn-in", it, round(r["HeadTotal"]), {rg: round(r["Unemp_" + rg], 4) for rg in S.REGIONS},
                  {rg: round(S.P["BaseEnrolment_" + rg]) for rg in S.REGIONS})
    for rg in S.REGIONS:
        S.P["BaseEnrolment_" + rg] = round(S.P["BaseEnrolment_" + rg], -1)
    for it in range(3):
        _, st, _ = S.run(st, ai_on=False, stop=60.0, record_every=60.0, **OFF)
        r = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
        for rg in S.REGIONS:
            S.P["NormalUnempRate_" + rg] = r["Unemp_" + rg]; st["PUS"][rg] = st["PUL"][rg] = r["Unemp_" + rg]
            for l in ("M", "S"):
                S.P[f"NormalTTF_{rg}_{l}"] = r[f"TTF_{rg}_{l}"]
        if verbose:
            print("settle", it, round(r["HeadTotal"]), {rg: round(r["Unemp_" + rg], 4) for rg in S.REGIONS})
    for rg in S.REGIONS:
        S.P["NormalUnempRate_" + rg] = round(S.P["NormalUnempRate_" + rg], 4)
        st["PUS"][rg] = st["PUL"][rg] = S.P["NormalUnempRate_" + rg]
        for l in ("M", "S"):
            S.P[f"NormalTTF_{rg}_{l}"] = round(S.P[f"NormalTTF_{rg}_{l}"], 3)
    st = reset_finance(st)
    # prices per vendor
    r0 = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
    for v in S.VENDORS:
        cost_wo = r0["LabRaw_" + v] + r0["VisaCost_" + v] + r0["AICost_" + v]
        rev = cost_wo / (1 - S.P["OverheadRate_" + v] - S.P["SalesCostRate"] * r0["SignRate_" + v] - S.P["TargetMargin_" + v])
        S.P["PriceMult_" + v] = round(rev / r0["BaseRev_" + v], 4)
        st["Overhead"][v] = round(S.P["OverheadRate_" + v] * r0["BaseRev_" + v] * S.P["PriceMult_" + v], -3)
    r1 = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
    for v in S.VENDORS:
        S.P["NormalMargin_" + v] = round(r1["Margin_" + v], 4); st["Viab"][v] = S.P["NormalMargin_" + v]
        st["ShareRef"][v] = r1["VShare_" + v]
    r1 = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
    # sourcing constants, cost bases, seats, budgets
    S.P["CostRef"] = round(r1["Cost_IH"], -3)
    PS = st["SrcPerc"]
    for x in S.SECTORS:
        asc = {e: math.log(PS[x][e]) + S.P["SrcCostSens"] * r1["Cost_" + e] / S.P["CostRef"] for e in S.EMPLOYERS}
        for e in S.EMPLOYERS:
            S.P[f"SrcASC_{x}_{e}"] = round(asc[e] - asc["OIT"], 4)
    for e in S.EMPLOYERS:
        S.P["LabourCostPB0_" + e] = round(r1["LabPB_" + e], -1)
    S.P["CostPerBFY0"] = round(r1["ServicesSpend"] / r1["Completion"], -1)
    for x in S.SECTORS:
        S.P["Seats0_" + x] = round(S.P["LOB0_" + x] + r1["ConsIT"] * r1["CompS_" + x] / r1["Completion"])
        st["SeatsB"][x] = S.P["Seats0_" + x]
    r2 = S.run(st, ai_on=False, stop=0.0, record_every=1.0, **OFF)[0][0]
    for x in S.SECTORS:
        S.P["Budget0_" + x] = round(r2["Committed_" + x] / S.P["NormalUtil"], -5)
    return st, r2, agg


if __name__ == "__main__":
    st, r2, agg = calibrate(verbose=True)
    print("agg shares", {e: round(a, 4) for e, a in agg.items()})
    print({k: S.P[k] for k in S.P if k.startswith(("Normal", "PriceMult", "LabourCostPB0", "CostRef", "CostPerBFY0"))})
    rows, fin, mins = S.run(st, ai_on=False, stop=16.0, record_every=4.0)
    for x in rows:
        print(int(x["year"]), "head", round(x["HeadTotal"]), {e: round(x["Head_" + e]) for e in S.EMPLOYERS},
              "margins", {v: round(x["Margin_" + v], 4) for v in S.VENDORS}, "work", {e: round(x["WorkShare_" + e], 4) for e in S.EMPLOYERS},
              "rev", round(x["RevenueTot"] / 1e9, 3), "U", {r: round(x["Unemp_" + r], 4) for r in S.REGIONS}, "wc", x["WorkCheckMax"])
