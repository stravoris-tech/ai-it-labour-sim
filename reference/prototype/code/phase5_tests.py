import json, phase5_sim as S
from calibrate5 import calibrate

st, r1, sigma, PS0 = calibrate(0.18)
init = json.loads(json.dumps(st))
init["SrcPerc"] = {e: round(PS0[e], 4) for e in S.OPTIONS}
init["SrcPerc"]["VEND"] = round(1 - init["SrcPerc"]["IH"] - init["SrcPerc"]["GCC"], 4)

ext = dict(a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0, JuniorCut=0.9)
tests = {
    "T1_steady": dict(ai_on=False),
    "T2_ai_base": dict(ai_on=True),
    "T3a_gap_wide": dict(ai_on=True, ClientPerceptionTime=3.0),
    "T3b_gap_narrow": dict(ai_on=True, ClientPerceptionTime=0.5),
    "T4_no_competition": dict(ai_on=True, RivalSens=0.0, ShareLossSens=0.0),
    "T5_gcc_push": dict(ai_on=False, GCCAppealEnd=1.0),
    "T6_price_war": dict(ai_on=False, PriceShock=0.40),
    "T7_dt32": dict(ai_on=True, dt=1/32),
    "T8_extreme": dict(ai_on=True, PriceShock=0.6, VTEnd=1.0, GCCAppealEnd=3.0, AIShockMult=5.0, ClientPerceptionTime=0.0625, **ext),
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
    for k in S.TYPES:
        for g in ("Leg", "NewV", "NewP", "NewD"):
            if fin[g][k] < -1e-9: neg[f"{g}_{k}"] = fin[g][k]
    wc = [x["WorkCheck"] for x in rows]
    rq = [x for x in rows if abs(x["year"] * 4 - round(x["year"] * 4)) < 1e-6]
    out["tests"][name] = {"rows": rq, "neg": neg, "resid": resid, "workcheck": [min(wc), max(wc)]}
    print(f"\n{name} negatives={neg} residual={None if resid is None else round(resid, 3)} workcheck=[{min(wc):.6f},{max(wc):.6f}]")
    for yv in (2024, 2028, 2030, 2032, 2035, 2040):
        x = min(rq, key=lambda q: abs(q["year"] - yv))
        print(f" {yv}: head {x['HeadTotal']:6,.0f} vend {x['VendorHead']:6,.0f} IH {x['H_IH']:6,.0f} GCC {x['H_GCC']:6,.0f} | shr V {x['VendorShare']:.3f} IH {x['IHWork']:.3f} GCC {x['GCCWork']:.3f}"
              f" | mix " + " ".join(f"{k} {x['Mix_' + k] * 100:4.1f}" for k in S.TYPES)
              + " | sign FP %.1f TM %.1f" % (x["SignShare_FP"] * 100, x["SignShare_TM"] * 100)
              + f" | dur {x['AvgNewDur']:.2f} inforce {x['InForceDur']:.2f} | marg {x['Margin'] * 100:5.1f} viab {x['Viability'] * 100:5.1f} disc {x['Disc']:.3f}"
              f" | rev {x['Revenue'] / 1e9:.2f} spend {x['ConsumerSpend'] / 1e9:.2f}")
json.dump(out, open("phase5_results.json", "w"))
print("\nCALIBRATED", {k: S.P[k] for k in S.P if k.startswith(("Normal", "TypeASC", "SrcASC")) or k in ("Price_VI", "CostRef")})
print("INIT finance", {k: init[k] for k in ("Overhead", "Viability", "SrcPerc", "Leg")})
