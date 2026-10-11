import json, phase6b_sim as S
from calibrate6b import calibrate

st, r2, agg = calibrate()
init = json.loads(json.dumps(st))

ext = dict(g=0.5, p=0.5, q=1.0, JuniorCut=0.9)
tests = {
    "T1_steady": dict(ai_on=False),
    "T2_ai_base": dict(ai_on=True),
    "T3a_no_tm_brake": dict(ai_on=True, TMBrake=0.0),
    "T3b_strong_tm_brake": dict(ai_on=True, TMBrake=0.8),
    "T4_gcc_push": dict(ai_on=True, GCCAppealEnd=1.0),
    "T5_oit_price_war": dict(ai_on=False, PriceShock_OIT=0.40),
    "T6_strict_regulation": dict(ai_on=True, RegScenario=1.5),
    "T7_dt32": dict(ai_on=True, dt=1/32),
    "T8_extreme": dict(ai_on=True, pC=0.5, qC=1.0, aL_max=0.9, AIShockMult=5.0, BudgetShock=0.6, RegScenario=2.5, JevonsEps=1.0,
                       PriceShock_OIT=0.5, PriceShock_GSI=0.3, VTEnd=1.0, GCCAppealEnd=3.0, TMBrake=1.0, **ext),
}


def people(s):
    return (sum(s[g][u][l] for g in ("H", "O") for u in S.UNITS for l in S.LEVELS)
            + sum(s[g][r][l] for g in ("R", "U") for r in S.REGIONS for l in S.LEVELS)
            + sum(s["LeftField"].values()) + sum(s["Retired"].values()))


def q3(rows, v):
    """Spec outcome test over 2038-2040: collapse, new equilibrium or still adjusting."""
    ann = {int(round(r["year"])): r for r in rows if abs(r["year"] - round(r["year"])) < 1e-6}
    neg_run, best = 0, 0
    for yv in range(2024, 2041):
        neg_run = neg_run + 1 if ann[yv]["Vi_" + v] < 0 else 0
        best = max(best, neg_run)
    fall = max(1 - ann[yv]["Head_" + v] / max(ann[yv - 1]["Head_" + v], 1e-9) for yv in (2039, 2040))
    if best >= 3 and fall > 0.15:
        return "collapse"
    ch = max(abs(ann[yv][k] / max(ann[yv - 1][k], 1e-9) - 1) for yv in (2039, 2040)
             for k in ("Head_" + v, "Revenue_" + v, "Head_IH", "Head_GCC", "Demand"))
    return "equilibrium" if ch < 0.02 else f"adjusting ({ch * 100:.1f}%/yr)"


out = {"params": dict(S.P), "init": init, "tests": {}}
for name, kw in tests.items():
    rows, fin, mins = S.run(init, record_every=1/16, **kw)
    dt = kw.get("dt", 1/16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in rows[:-1]) if dt == 1/16 else None
    resid = (people(fin) - people(init) - inflow) if inflow is not None else None
    neg = {k: round(v, 3) for k, v in mins.items() if v < -1e-6}
    wc = max(x["WorkCheckMax"] for x in rows)
    rq = [x for x in rows if abs(x["year"] * 4 - round(x["year"] * 4)) < 1e-6]
    outcome = {v: q3(rq, v) for v in S.VENDORS}
    out["tests"][name] = {"rows": rq, "neg": neg, "resid": resid, "workcheck": wc, "q3": outcome}
    print(f"\n{name} negatives={neg} residual={None if resid is None else round(resid, 3)} workcheck={wc:.2e} Q3={outcome}")
    for yv in (2024, 2028, 2030, 2032, 2035, 2040):
        x = min(rq, key=lambda q: abs(q["year"] - yv))
        print(f" {yv}: dem {x['Demand'] / 1000:5.1f} head {x['HeadTotal']:6,.0f} [" + " ".join(f"{e} {x['Head_' + e]:6,.0f}" for e in S.EMPLOYERS) + "]"
              + " work% [" + " ".join(f"{x['WorkShare_' + e] * 100:4.1f}" for e in S.EMPLOYERS) + "]"
              + " A [" + " ".join(f"{x['A_' + e]:.2f}" for e in S.EMPLOYERS) + "]"
              + " margin% [" + " ".join(f"{x['Margin_' + v] * 100:5.1f}" for v in S.VENDORS) + "]"
              + " effort% [" + " ".join(f"{x['EffortShare_' + v] * 100:4.1f}" for v in S.VENDORS) + "]"
              + f" Q1 [{x['Q1_ConsOnshore']:,.0f} {x['Q1_ConsIndia']:,.0f} {x['Q1_VendOnshore']:,.0f} {x['Q1_VendIndia']:,.0f}]"
              + f" U% {x['Unemp_IN'] * 100:4.1f}/{x['Unemp_ON'] * 100:4.1f}")
json.dump(out, open("phase6b_results.json", "w"))
print("\nCALIBRATED", {k: S.P[k] for k in S.P if k.startswith(("Normal", "PriceMult", "LabourCostPB0", "BaseEnrolment", "Seats0", "Budget0")) or k in ("CostRef", "CostPerBFY0")})
