"""Phase 7 runs: integrity tests on the calibrated model, scenarios, one-at-a-time sensitivity (tornado) and a
Monte Carlo band, then the answers to Q1-Q3. Reads calib7.json (written by calibrate7.py), writes phase7_results.json."""
import json, math, random
import phase7_sim as S

CAL = json.load(open("calib7.json"))
for k, v in CAL["params"].items():
    if k in S.P or k.startswith(("SrcASC_", "TypeASC_", "LOB0_", "Port0_", "Seats0_", "Budget0_", "LabourCostPB0_")):
        S.P[k] = v
INIT = CAL["init"]
BASE = dict(S.P)

# India scaling (indicative): model units -> people, from NASSCOM FY24
INDIA_SCALE = {"Q1_VendIndia": 3.53e6, "Q1_ConsIndia": 1.90e6}

SCEN = {
    "Base": {},
    "Slow AI": dict(g=0.05, VerifDecline=0.0),
    "Fast AI": dict(g=0.20, VerifDecline=0.10),
    "Strict regulation": dict(RegScenario=1.5),
    "Light regulation": dict(RegScenario=0.5),
    "Compute shock": dict(AIShockMult=3.0, AIShockStart=2027.0, AIShockEnd=2029.5),
    "Visa crackdown": dict(VTEnd=0.8, VTRampStart=2025.7, VTRampEnd=2027.7),
    "Visa relaxation": dict(VTEnd=0.1, VTRampStart=2027.0, VTRampEnd=2028.0),
    "Downturn": dict(BudgetShock=0.15, BudgetShockStart=2027.0, BudgetShockEnd=2029.0),
    "Jevons rebound": dict(JevonsEps=0.5),
    "Demand stalls": dict(DemandGrowthLate=0.0),
    "Demand boom": dict(DemandGrowthLate=0.05),
    "GCC wave persists": dict(GCCAppealKeep=1.0),
    "GCC wave fades": dict(GCCAppealKeep=0.0),
}
TORNADO = [  # parameter, low, high, label
    ("g", 0.06, 0.15, "AI capability growth g"),
    ("DemandGrowthLate", 0.015, 0.045, "Underlying demand growth after 2026"),
    ("Verif", BASE["Verif"] * 0.7, BASE["Verif"] * 1.3, "Verification overhead (2024)"),
    ("VerifDecline", 0.0, 0.10, "Verification decline per year"),
    ("JevonsEps", 0.0, 0.5, "Jevons elasticity"),
    ("GCCAppealKeep", 0.0, 1.0, "GCC appeal kept after 2030"),
    ("JuniorCut", BASE["JuniorCut"] * 0.5, BASE["JuniorCut"] * 1.5, "Junior cut per unit of adoption"),
    ("TMBrake", 0.2, 0.6, "T&M brake on vendor adoption"),
    ("PriceHorizon", 4.0, 8.0, "Client price horizon (years)"),
    ("aL_max", 0.25, 0.45, "Max business-process automation"),
    ("SrcCostSens", 2.0, 4.0, "Sourcing cost sensitivity"),
    ("AICostDecline", 0.08, 0.25, "AI cost decline per year"),
    ("RegScenario", 0.5, 1.5, "Regulation strength"),
    ("EnrolSensitivity", 0.5, 1.5, "Enrolment response to unemployment"),
]
Q1 = ("Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia")
KEEP = Q1 + ("HeadTotal", "VendorHead", "Demand", "P_all", "A_mean", "AC_mean", "Unemp_IN", "Unemp_ON", "RevenueTot",
             "Head_IH", "Head_GCC", "Head_OIT", "Head_GSI", "Head_BQ", "WorkShare_IH", "WorkShare_GCC", "WorkShare_OIT",
             "WorkShare_GSI", "WorkShare_BQ", "Margin_OIT", "Margin_GSI", "Margin_BQ", "Revenue_OIT", "Revenue_GSI", "Revenue_BQ",
             "Vi_OIT", "Vi_GSI", "Vi_BQ", "AvgIdx_OIT", "LOB", "HireJ_IN", "HireJ_ON", "G", "HeadLoc_IN", "HeadLoc_ON",
             "EffortShare_OIT", "EffortShare_GSI", "EffortShare_BQ") + tuple(f"Mix_{v}_{k}" for v in S.VENDORS for k in S.TYPES)


def run(over, **kw):
    pr = dict(over)
    return S.run(INIT, **pr, **kw)


def annual(rows):
    return {int(round(r["year"])): r for r in rows if abs(r["year"] - round(r["year"])) < 1e-6}


def q3(ann, v):
    """Spec outcome test over 2038-2040: collapse, new equilibrium or still adjusting."""
    neg_run, best = 0, 0
    for yv in range(2024, 2041):
        neg_run = neg_run + 1 if ann[yv]["Vi_" + v] < 0 else 0
        best = max(best, neg_run)
    fall = max(1 - ann[yv]["Head_" + v] / max(ann[yv - 1]["Head_" + v], 1e-9) for yv in (2039, 2040))
    if best >= 3 and fall > 0.15:
        return "collapse"
    ch = max(abs(ann[yv][k] / max(ann[yv - 1][k], 1e-9) - 1) for yv in (2039, 2040)
             for k in ("Head_" + v, "Revenue_" + v))
    return "equilibrium" if ch < 0.02 else f"adjusting ({ch * 100:.1f}%/yr)"


def people(s):
    return (sum(s[g][u][l] for g in ("H", "O") for u in S.UNITS for l in S.LEVELS)
            + sum(s[g][r][l] for g in ("R", "U") for r in S.REGIONS for l in S.LEVELS)
            + sum(s["LeftField"].values()) + sum(s["Retired"].values()))


def slim(ann):
    return {yv: {k: ann[yv][k] for k in KEEP} for yv in ann}


def tests():
    out = {}
    rows, fin, mins = run({}, ai_on=False, record_every=1.0)
    ratio = [r["HeadTotal"] / rows[0]["HeadTotal"] / r["G"] for r in rows]
    out["T1_ai_off_growth_path"] = dict(max_dev=max(abs(x - 1) for x in ratio), neg=[k for k, v in mins.items() if v < -1e-6])
    rows, fin, mins = run({}, record_every=1 / 16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in rows[:-1])
    out["T2_people_conservation"] = dict(residual=people(fin) - people(INIT) - inflow, people=people(fin),
                                         workcheck=max(x["WorkCheckMax"] for x in rows), neg=[k for k, v in mins.items() if v < -1e-6])
    a16 = annual(rows)[2040]
    rows32, _, _ = run({}, dt=1 / 32, record_every=1.0)
    a32 = annual(rows32)[2040]
    out["T3_dt_check"] = {k: a32[k] / a16[k] - 1 for k in Q1 + ("HeadTotal", "RevenueTot")}
    ext = dict(g=0.5, VerifDecline=0.3, JevonsEps=1.0, AIShockMult=5.0, BudgetShock=0.6, RegScenario=2.5, VTEnd=1.0,
               GCCAppealKeep=2.0, PriceShock_OIT=0.5, DemandGrowthLate=-0.03, aL_max=0.9)
    rows, fin, mins = run(ext, record_every=1.0)
    out["T4_extreme"] = dict(neg={k: v for k, v in mins.items() if v < -1e-6}, head2040=annual(rows)[2040]["HeadTotal"])
    return out


def main():
    res = {"tests": tests()}
    for k, v in res["tests"].items():
        print(k, {a: (round(b, 6) if isinstance(b, float) else b) for a, b in (v.items() if isinstance(v, dict) else [])})
    # scenarios
    res["scenarios"] = {}
    for name, over in SCEN.items():
        rows, fin, mins = run(over, record_every=1.0)
        ann = annual(rows)
        res["scenarios"][name] = dict(over=over, ann=slim(ann), q3={v: q3(ann, v) for v in S.VENDORS},
                                      neg=[k for k, v in mins.items() if v < -1e-6])
        a, z = ann[2024], ann[2040]
        print(f"{name:20s} head35 {ann[2035]['HeadTotal'] / a['HeadTotal']:.3f} head40 {z['HeadTotal'] / a['HeadTotal']:.3f} "
              + " ".join(f"{k[3:]} {ann[2035][k] / a[k]:.2f}/{z[k] / a[k]:.2f}" for k in Q1)
              + f" U {z['Unemp_IN'] * 100:.1f}/{z['Unemp_ON'] * 100:.1f} OITm {z['Margin_OIT'] * 100:.1f} Q3 {res['scenarios'][name]['q3']}")
    # tornado on 2040 outcomes
    base_ann = annual(run({}, record_every=1.0)[0])
    outs = ("HeadTotal",) + Q1
    res["tornado"] = []
    for p, lo, hi, label in TORNADO:
        row = dict(param=p, label=label, lo=lo, hi=hi, base=BASE.get(p))
        for side, val in (("lo", lo), ("hi", hi)):
            ann = annual(run({p: val}, record_every=1.0)[0])
            for k in outs:
                row[f"{side}_{k}"] = ann[2040][k] / base_ann[2040][k] - 1
        res["tornado"].append(row)
        print(f"tornado {label:38s}", " ".join(f"{k[3:] if k.startswith('Q1') else k}: {row['lo_' + k] * 100:+5.1f}/{row['hi_' + k] * 100:+5.1f}" for k in outs))
    # Monte Carlo
    rng = random.Random(7)
    years = list(range(2024, 2041))
    traj = {k: [] for k in outs}
    q3count = {v: {} for v in S.VENDORS}
    N = 300
    for i in range(N):
        over = {p: rng.uniform(lo, hi) for p, lo, hi, _ in TORNADO}
        ann = annual(run(over, record_every=1.0)[0])
        for k in outs:
            traj[k].append([ann[yv][k] / ann[2024][k] for yv in years])
        for v in S.VENDORS:
            o = q3(ann, v).split(" ")[0]
            q3count[v][o] = q3count[v].get(o, 0) + 1

    def pct(xs, q):
        xs = sorted(xs); i = (len(xs) - 1) * q; f = math.floor(i); c = min(f + 1, len(xs) - 1)
        return xs[f] + (xs[c] - xs[f]) * (i - f)
    res["mc"] = {"N": N, "years": years, "q3": q3count,
                 "bands": {k: {q: [pct([t[j] for t in traj[k]], q) for j in range(len(years))] for q in (0.1, 0.5, 0.9)} for k in outs}}
    print("MC 2040 p10/p50/p90", {k: [round(res["mc"]["bands"][k][q][-1], 3) for q in (0.1, 0.5, 0.9)] for k in outs})
    print("MC Q3", q3count)
    json.dump(res, open("phase7_results.json", "w"))


if __name__ == "__main__":
    main()
