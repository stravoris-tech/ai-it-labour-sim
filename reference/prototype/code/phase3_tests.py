import json, phase3_sim as S
from calibrate3 import steady

ENR_IN, ENR_ON = 3900.0, 2000.0
st, r0 = steady(ENR_IN, ENR_ON, iters=12)
for r in S.REGIONS:
    S.P["NormalUnempRate_" + r] = round(S.P["NormalUnempRate_" + r], 4)
    for l in ("M", "S"):
        S.P[f"NormalTTF_{r}_{l}"] = round(S.P[f"NormalTTF_{r}_{l}"], 3)
# rounded initial values, as typed by a builder
def rnd(x): return round(x) if abs(x) >= 10 else round(x, 4)
init = json.loads(json.dumps(st))
for g in ("H", "O", "V"):
    for u in S.UNITS:
        for l in S.LEVELS: init[g][u][l] = rnd(init[g][u][l])
for g in ("R", "U"):
    for r in S.REGIONS:
        for l in S.LEVELS: init[g][r][l] = rnd(init[g][r][l])
for r in S.REGIONS:
    init["Pipeline"][r] = rnd(init["Pipeline"][r]); init["PUS"][r] = S.P["NormalUnempRate_" + r]; init["PUL"][r] = S.P["NormalUnempRate_" + r]
init["Backlog"] = rnd(init["Backlog"]); init["PerceivedP"] = 1.0; init["A"] = S.P["A0"]; init["TightPerc"] = S.P["VTBase"]

ext = dict(a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0, JuniorCut=0.9)
tests = {
    "T1_steady": dict(ai_on=False),
    "T2_visa_crackdown": dict(ai_on=False, VTEnd=0.8, VTRampStart=2027.0, VTRampEnd=2031.0),
    "T3_visa_relax": dict(ai_on=False, VTEnd=0.1, VTRampStart=2029.0, VTRampEnd=2030.0),
    "T4_gcc_expansion": dict(ai_on=False, GCCShareEnd=0.20, GCCRampStart=2027.0, GCCRampEnd=2031.0),
    "T5_ai_base": dict(ai_on=True),
    "T6_dt32": dict(ai_on=True, dt=1/32),
    "T7_extreme": dict(ai_on=True, VTEnd=1.0, GCCShareEnd=0.35, **ext),
}
def people(s):
    tot = 0.0
    for g in ("H", "O"):
        tot += sum(s[g][u][l] for u in S.UNITS for l in S.LEVELS)
    for g in ("R", "U"):
        tot += sum(s[g][r][l] for r in S.REGIONS for l in S.LEVELS)
    return tot + sum(s["LeftField"].values()) + sum(s["Retired"].values())
out = {"params": {k: S.P[k] for k in S.P}, "init": init, "tests": {}}
for name, kw in tests.items():
    rows, fin, mins = S.run(init, record_every=1/16, **kw)
    dt = kw.get("dt", 1/16)
    rows_q = [x for x in rows if abs(x["year"]*4 - round(x["year"]*4)) < 1e-6]
    inflow = sum((x["Grad_total"] + x["Ext_total"]) * (1/16) for x in rows[:-1]) if dt == 1/16 else None
    resid = people(fin) - people(init) - inflow if inflow is not None else None
    neg = {k: round(v, 2) for k, v in mins.items() if v < -1e-6}
    out["tests"][name] = {"rows": rows_q, "neg": neg, "resid": resid}
    print(f"\n{name} negatives={neg} conservation_residual={resid if resid is None else round(resid, 3)}")
    def at(y): return min(rows_q, key=lambda x: abs(x["year"] - y))
    for y in (2024, 2027, 2029, 2031, 2034, 2037, 2040):
        x = at(y)
        print(f" {y}: IH {x['H_IH']:6,.0f} GCC {x['H_GCC']:6,.0f} VI {x['H_VI']:6,.0f} OV {x['H_OV']:6,.0f} OL {x['H_OL']:6,.0f} "
              f"| loc IN {x['HeadLoc_IN']:6,.0f} ON {x['HeadLoc_ON']:6,.0f} tot {x['HeadTotal']:6,.0f} "
              f"| U% IN {x['Unemp_IN']*100:5.2f} ON {x['Unemp_ON']*100:5.2f} | tight {x['VisaTight']:.2f} onsite {x['OnsiteShare']:.3f} visaMix {x['VisaMix']:.3f} "
              f"visaHires {x['VisaHires']:5,.0f} cap {x['VisaCap']:5,.0f} | swGCC {x['SwitchToGCC']:5,.0f} swVI {x['SwitchFromGCC']:5,.0f} VIturn {x['VI_quit_switch_rate']:.3f} | backlog {x['Backlog']:6,.0f}")
json.dump(out, open("phase3_results.json", "w"))
print("\nNORMALS", {k: S.P[k] for k in S.P if k.startswith("Normal")})
