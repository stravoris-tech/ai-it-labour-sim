import json, phase6a_sim as S
from calibrate6a import calibrate

st, r0 = calibrate()
init = json.loads(json.dumps(st))
for x in S.SECTORS:
    for w in S.WTYPES:
        init["BL"][x][w] = round(init["BL"][x][w], 1)

ext = dict(a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0, JuniorCut=0.9)
tests = {
    "T1_steady": dict(ai_on=False),
    "T2_ai_base": dict(ai_on=True),
    "T3a_no_app_displacement": dict(ai_on=True, AppDisplacement=0.0, RetireAccel=0.0),
    "T3b_no_ai_build": dict(ai_on=True, BuildRate=0.0, RunRate=0.0),
    "T4_jevons": dict(ai_on=True, JevonsEps=0.5),
    "T5a_strict_regulation": dict(ai_on=True, RegScenario=1.5),
    "T5b_no_regulation": dict(ai_on=True, RegScenario=0.0),
    "T6_budget_downturn": dict(ai_on=True, BudgetShock=0.2),
    "T7_dt32": dict(ai_on=True, dt=1/32),
    "T8_extreme": dict(ai_on=True, pC=0.5, qC=1.0, aL_max=0.9, AIShockMult=5.0, BudgetShock=0.6, CyberEnd=2.0,
                       RegScenario=2.5, JevonsEps=1.0, PriceShock=0.5, **ext),
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
    for x in rows:
        for key in [k for k in x if k.startswith(("LOB_", "Port_", "AC_", "Seats_")) or k.startswith("Dem_")]:
            if x[key] < -1e-9:
                neg[key] = min(neg.get(key, 0), x[key])
    wc = [x["WorkCheck"] for x in rows]
    rq = [x for x in rows if abs(x["year"] * 4 - round(x["year"] * 4)) < 1e-6]
    out["tests"][name] = {"rows": rq, "neg": neg, "resid": resid, "workcheck": [min(wc), max(wc)]}
    print(f"\n{name} negatives={neg} residual={None if resid is None else round(resid, 3)} workcheck=[{min(wc):.6f},{max(wc):.6f}]")
    for yv in (2024, 2028, 2030, 2032, 2035, 2040):
        x = min(rq, key=lambda q: abs(q["year"] - yv))
        print(f" {yv}: demand {x['Demand']:7,.0f} [" + " ".join(f"{w} {x['Dem_' + w] / 1000:4.1f}" for w in S.WTYPES) + f"] AIbuild {x['AIBuild']:6,.0f}"
              f" | head {x['HeadTotal']:6,.0f} vend {x['VendorHead']:6,.0f} IH {x['H_IH']:6,.0f} GCC {x['H_GCC']:5,.0f}"
              f" | AC FIN {x['AC_FIN']:.2f} GOV {x['AC_GOV']:.2f} RET {x['AC_RET']:.2f} | LOB {x['LOB'] / 1e6:.3f}m apps {x['Port']:6,.0f} seats {x['Seats'] / 1e6:.3f}m"
              f" | svc {x['ServicesSpend'] / 1e9:.2f} seat {x['SeatSpend'] / 1e9:.2f} cred {x['CreditSpend'] / 1e9:.2f} cloud {x['CloudSpend'] / 1e9:.2f}"
              f" util {x['Committed'] / x['Budget']:.3f} | margin {x['Margin'] * 100:5.1f} Peff {x['P_eff']:.3f}")
json.dump(out, open("phase6a_results.json", "w"))
print("\nCALIBRATED", {k: S.P[k] for k in S.P if k.startswith(("LOB0", "Port0", "Seats0", "Budget0")) or k in ("CostPerBFY0", "LabourCostPB0")})
