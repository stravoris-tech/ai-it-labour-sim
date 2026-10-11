import json, phase4_sim as S
from calibrate4 import CAL, base_state, calibrate

S.P.update(CAL)
st, _ = calibrate(0.18)          # sets Price_VI and a first NormalMargin
for it in range(8):              # joint fixed point: labour + finance steady state and its 'normal' values
    _, st, _ = S.run(st, ai_on=False, stop=60.0, record_every=60.0)
    r = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    for rg in S.REGIONS:
        S.P["NormalUnempRate_" + rg] = r["Unemp_" + rg]
        st["PUS"][rg] = st["PUL"][rg] = r["Unemp_" + rg]
        for l in ("M", "S"):
            S.P[f"NormalTTF_{rg}_{l}"] = r[f"TTF_{rg}_{l}"]
    S.P["NormalMargin"] = r["Margin"]; st["Viability"] = r["Margin"]
    st["VSE"] = 1.0; st["CostProg"] = 0.0; st["WI"] = {u: 1.0 for u in S.UNITS}
    st["A"] = S.P["A0"]; st["LeftField"] = {x: 0.0 for x in S.REGIONS}; st["Retired"] = {x: 0.0 for x in S.REGIONS}
for rg in S.REGIONS:
    S.P["NormalUnempRate_" + rg] = round(S.P["NormalUnempRate_" + rg], 4)
    for l in ("M", "S"):
        S.P[f"NormalTTF_{rg}_{l}"] = round(S.P[f"NormalTTF_{rg}_{l}"], 3)
S.P["NormalMargin"] = round(S.P["NormalMargin"], 4)

def rnd(x): return round(x) if abs(x) >= 10 else round(x, 4)
init = json.loads(json.dumps(st))
for g in ("H", "O", "V"):
    for u in S.UNITS:
        for l in S.LEVELS: init[g][u][l] = rnd(init[g][u][l])
for g in ("R", "U"):
    for rg in S.REGIONS:
        for l in S.LEVELS: init[g][rg][l] = rnd(init[g][rg][l])
for rg in S.REGIONS:
    init["Pipeline"][rg] = rnd(init["Pipeline"][rg])
    init["PUS"][rg] = init["PUL"][rg] = S.P["NormalUnempRate_" + rg]
init["Backlog"] = rnd(init["Backlog"]); init["Overhead"] = round(init["Overhead"], -3)
init["Viability"] = S.P["NormalMargin"]; init["PriceIndex"] = 1.0; init["ClientP"] = 1.0; init["PerceivedP"] = 1.0
init["TightPerc"] = S.P["VTBase"]; init["A"] = S.P["A0"]

ext = dict(a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0, JuniorCut=0.9)
tests = {
    "T1_steady": dict(ai_on=False),
    "T2_moderate_shock": dict(ai_on=False, PriceShock=0.10),
    "T3_severe_shock": dict(ai_on=False, PriceShock=0.40),
    "T4_ai_base": dict(ai_on=True),
    "T5_ai_const_wages": dict(ai_on=True, WagesEndogenous=0.0),
    "T6_dt32": dict(ai_on=True, dt=1/32),
    "T7_extreme": dict(ai_on=True, PriceShock=0.6, VTEnd=1.0, GCCShareEnd=0.35, AIShockMult=5.0, **ext),
}
def people(s):
    return (sum(s[g][u][l] for g in ("H", "O") for u in S.UNITS for l in S.LEVELS)
            + sum(s[g][r][l] for g in ("R", "U") for r in S.REGIONS for l in S.LEVELS)
            + sum(s["LeftField"].values()) + sum(s["Retired"].values()))
out = {"params": dict(S.P), "init": init, "tests": {}}
for name, kw in tests.items():
    rows, fin, mins = S.run(init, record_every=1/16, **kw)
    dt = kw.get("dt", 1/16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in rows[:-1]) if dt == 1/16 else None
    resid = (people(fin) - people(init) - inflow) if inflow is not None else None
    neg = {k: round(v, 2) for k, v in mins.items() if v < -1e-6}
    rq = [x for x in rows if abs(x["year"] * 4 - round(x["year"] * 4)) < 1e-6]
    out["tests"][name] = {"rows": rq, "neg": neg, "resid": resid}
    print(f"\n{name} negatives={neg} residual={None if resid is None else round(resid, 3)}")
    for yv in (2024, 2027, 2028, 2029, 2030, 2032, 2034, 2037, 2040):
        x = min(rq, key=lambda q: abs(q["year"] - yv))
        print(f" {yv}: head {x['HeadTotal']:7,.0f} vendor {x['VendorHead']:7,.0f} VI {x['H_VI']:6,.0f} GCC {x['H_GCC']:6,.0f} IH {x['H_IH']:6,.0f} "
              f"| rev ${x['Revenue']/1e9:5.2f}bn margin {x['Margin']*100:6.2f}% viab {x['Viability']*100:6.2f}% VSE {x['VSE']:.3f} "
              f"price {x['PriceIndex']:.3f} costprog {x['CostProg']:.3f} OH ${x['Overhead']/1e6:5.0f}m AI ${x['AICost']/1e6:5.0f}m "
              f"| WI VI {x['WI_VI']:.3f} IH {x['WI_IH']:.3f} | U% IN {x['Unemp_IN']*100:5.2f} ON {x['Unemp_ON']*100:5.2f}")
json.dump(out, open("phase4_results.json", "w"))
print("\nCALIBRATED", {k: S.P[k] for k in S.P if k.startswith("Normal") or k == "Price_VI"})
print("OVERHEAD init", init["Overhead"], "BACKLOG", init["Backlog"])
