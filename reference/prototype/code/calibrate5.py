"""Phase 5 calibration: start from the Phase 4 steady state; solve Price_VI (margin incl. sales cost),
NormalMargin, contract-type constants, sourcing constants and CostRef so that AI-off is a steady state."""
import json, math, phase5_sim as S

p4 = json.load(open("phase4_results.json"))
for k, v in p4["params"].items():
    if k.startswith("Normal") or k.startswith("BaseEnrolment"):
        S.P[k] = v
S.P["Price_VI"] = p4["params"]["Price_VI"]


def base_state():
    i4 = p4["init"]
    st = S.blank_state()
    for k in ("Backlog", "A", "PerceivedP", "TightPerc", "H", "O", "V", "R", "U", "Pipeline", "PUS", "PUL", "Overhead", "Viability"):
        st[k] = json.loads(json.dumps(i4[k]))
    st["LeftField"] = {r: 0.0 for r in S.REGIONS}; st["Retired"] = {r: 0.0 for r in S.REGIONS}
    return st


def type_constants():
    sig = {k: S.P["Mix0_" + k] / S.P["BaseDur_" + k] for k in S.TYPES}
    z = sum(sig.values())
    for k in S.TYPES:
        S.P["TypeASC_" + k] = round(math.log(sig[k] / z), 4)
    return {k: sig[k] / z for k in S.TYPES}


def decision_shares():
    vend0 = 1 - S.P["InHouseShare0"] - S.P["GCCShare0"]
    exp_v = sum(vend0 * S.P["Mix0_" + k] / S.P["BaseDur_" + k] for k in S.TYPES)
    turn = {"IH": S.P["InHouseShare0"] / S.P["IHReviewTime"], "GCC": S.P["GCCShare0"] / S.P["GCCReviewTime"], "VEND": exp_v}
    z = sum(turn.values())
    return {e: turn[e] / z for e in S.OPTIONS}


def calibrate(target=0.18):
    sigma = type_constants()
    PS0 = decision_shares()
    st = base_state()
    st["SrcPerc"] = dict(PS0)
    # Price_VI: revenue needed for the target margin including sales cost
    r0 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    turnover = r0["BookTurnover"]
    cost_wo = r0["LabourRaw"] + r0["VisaCost"] + r0["AICost"]
    rev = cost_wo / (1 - S.P["OverheadRate"] - S.P["SalesCostRate"] * turnover - target)
    S.P["Price_VI"] = round((rev - r0["RevOnsite"]) / r0["Del_VI"], -1)
    st["Overhead"] = round(S.P["OverheadRate"] * (r0["Del_VI"] * S.P["Price_VI"] + r0["RevOnsite"]), -3)
    r1 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    S.P["NormalMargin"] = round(r1["Margin"], 4); st["Viability"] = S.P["NormalMargin"]
    r1 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    # sourcing constants: logit target equals the steady-state decision shares
    S.P["CostRef"] = round(r1["Cost_IH"], -3)
    asc = {e: math.log(PS0[e]) + S.P["SrcCostSens"] * r1["Cost_" + e] / S.P["CostRef"] for e in S.OPTIONS}
    for e in S.OPTIONS:
        S.P["SrcASC_" + e] = round(asc[e] - asc["VEND"], 4)
    return st, r1, sigma, PS0


if __name__ == "__main__":
    st, r1, sigma, PS0 = calibrate()
    print("Price_VI", S.P["Price_VI"], "NormalMargin", S.P["NormalMargin"], "CostRef", S.P["CostRef"], "Overhead", st["Overhead"])
    print("sigma", {k: round(v, 4) for k, v in sigma.items()}, "PS0", {k: round(v, 4) for k, v in PS0.items()})
    print("TypeASC", {k: S.P["TypeASC_" + k] for k in S.TYPES}, "SrcASC", {e: S.P["SrcASC_" + e] for e in S.OPTIONS})
    print("costs", {e: round(r1["Cost_" + e]) for e in S.OPTIONS}, "turnover", round(r1["BookTurnover"], 4), "sales", round(r1["SalesCost"] / 1e6, 1))
    rows, fin, mins = S.run(st, ai_on=False, stop=16.0, record_every=2.0)
    for x in rows:
        print(int(x["year"]), "head", round(x["HeadTotal"]), "vendor", round(x["VendorHead"]), "IH", round(x["H_IH"]), "margin", round(x["Margin"], 4),
              "vshare", round(x["VendorShare"], 4), "IHw", round(x["IHWork"], 4), "mix", [round(x["Mix_" + k], 3) for k in S.TYPES],
              "src", [round(x["SrcTarget_" + e], 4) for e in S.OPTIONS], "rev", round(x["Revenue"] / 1e9, 3), "chk", round(x["WorkCheck"], 6))
