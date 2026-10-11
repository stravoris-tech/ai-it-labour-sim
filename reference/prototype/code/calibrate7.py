"""Phase 7 historical fit. Starting from the 2024 growth-path state (calibrate7_ss), fit seven AI parameters so the
model reproduces observed 2024-2026 indicators, then report validation indicators that were NOT used in the fit."""
import json, math
import numpy as np
from scipy.optimize import least_squares
import phase7_sim as S, calibrate7_ss as C

# ---- observed 2024-2026 targets (model metric, year, value, weight, source) ----
TARGETS = [
    ("A_mean", 2025.0, 0.50, 1.0, "Stack Overflow 2025: 84% use or plan to use AI tools, 51% of professionals daily (2024: 62% using)"),
    ("A_mean", 2026.0, 0.62, 1.0, "DORA 2025: 90% of technologists use AI at work; daily use rising"),
    ("PriceIdx_OIT", 2026.0, 0.96, 1.0, "AI-driven deflation 2-5%/yr on renewed deals (HCL 2-3%, Kotak 3.5%): about -4% on the whole book by 2026"),
    ("HeadOIT_ratio", 2026.0, 1.003, 1.0, "Top-5 Indian IT headcount 1,525,776 (Mar 2024) to 1,530,073 (Mar 2026)"),
    ("MarginOIT_change", 2026.0, 0.0, 1.0, "Indian IT margins flat: TCS 24.6% to 25.0%, Infosys ~21%, HCL 18.2% to 17.2%"),
    ("GCC_ratio", 2026.0, 1.24, 1.0, "NASSCOM/Zinnov: GCC employees 1.9M (FY24) to 2.36M (FY26)"),
    ("GCC_ratio", 2030.0, 1.70, 0.5, "Outlook, not data: GCC workforce to reach ~3.2-3.5M by 2030 (NASSCOM/Zinnov, Nov 2025)"),
    ("JuniorHires_ratio", 2026.0, 0.65, 1.0, "TCS fresher intake 42-44k to ~25k offers; US new-grad hiring down sharply"),
    ("AC_mean", 2026.0, 0.42, 1.0, "McKinsey State of AI: share of firms scaling AI 33% (2024) to ~40%+ (2025-26)"),
    ("Att", 2026.0, 0.065, 0.5, "Microsoft 365 Copilot ~30M+ paid seats on ~450M commercial seats (~6.5%)"),
    ("UnempON_change", 2026.0, 0.0145, 1.0, "US tech unemployment 2.0% (Dec 2024) to 3.3-3.6% (2026)"),
]
SCALE = {"MarginOIT_change": 0.10, "UnempON_change": 0.10}     # point targets: residual per 10 points
FIT = [("p", 0.001, 0.3), ("q", 0.05, 2.0), ("Verif", 0.0, 1.5), ("GCCAppealEnd", 0.0, 6.0),
       ("JuniorCut", 0.0, 1.4), ("GCCMomentum", 0.0, 3.0), ("qC", 0.01, 1.0), ("pAtt", 0.001, 0.5), ("PriceHorizon", 0.0, 8.0),
       ("SeekerExitRate", 0.05, 1.0), ("AICost2024", 2_000.0, 60_000.0)]
X0 = [0.03, 0.5, 0.4, 0.5, 0.5, 1.0, 0.24, 0.012, 3.0, 0.6, 20_000.0]
S.P.update(pC=0.005, GCCRampStart=2024.0, GCCRampEnd=2030.0)   # lasting shift in GCC appeal phased in to 2030
DG_GRID = (0.03,)    # set from data (Gartner IT services +3.8% to +5.6% nominal, ~3% real); not fitted


def with_derived(over):
    o = dict(over)
    pC, qC, AC0 = o.get("pC", S.P["pC"]), o.get("qC", S.P["qC"]), o.get("AC0", S.P["AC0"])
    o["AdoptC0"] = (pC + qC * AC0) * (1 - AC0)        # consumer adoption rate already under way in 2024
    return o


def metrics(init, over, stop=6.5):
    rows, _, _ = S.run(init, ai_on=True, stop=stop, record_every=0.25, **with_derived(over))
    at = {round(r["year"], 2): r for r in rows}
    r0 = at[2024.0]
    jh = lambda r: r["HireJ_IN"] + r["HireJ_ON"]
    out = {}
    out[("GCC_ratio", 2030.0)] = at[2030.0]["Head_GCC"] / r0["Head_GCC"]
    for yv in (2025.0, 2026.0):
        r = at[yv]
        out[("A_mean", yv)] = r["A_mean"]; out[("P_all", yv)] = r["P_all"]; out[("AC_mean", yv)] = r["AC_mean"]; out[("Att", yv)] = r["Att"]
        out[("GCC_ratio", yv)] = r["Head_GCC"] / r0["Head_GCC"]
        out[("PriceIdx_OIT", yv)] = r["AvgIdx_OIT"]; out[("HeadOIT_ratio", yv)] = r["Head_OIT"] / r0["Head_OIT"]
        out[("RevOIT_ratio", yv)] = r["Revenue_OIT"] / r0["Revenue_OIT"]
        out[("MarginOIT_change", yv)] = r["Margin_OIT"] - r0["Margin_OIT"]; out[("UnempON_change", yv)] = r["Unemp_ON"] - r0["Unemp_ON"]
        out[("JuniorHires_ratio", yv)] = (jh(at[yv - 0.25]) + jh(r) + jh(at[yv + 0.25])) / 3 / jh(r0)
    return out, at


def residuals(x, init):
    over = {k: v for (k, _, _), v in zip(FIT, x)}
    m, _ = metrics(init, over)
    return np.array([w * (m[(k, yv)] - val) / SCALE.get(k, val) for k, yv, val, w, _ in TARGETS])


def validation(at):
    r0, r2 = at[2024.0], at[2026.0]
    return {
        "Realised productivity P_all 2026": (r2["P_all"], "derived, not observed: price deflation of 2-5%/yr is often read as ~7% productivity"),
        "Vendor India headcount 2026/2024": (r2["Q1_VendIndia"] / r0["Q1_VendIndia"], "~1.02 (NASSCOM 5.43M to 5.95M minus GCCs)"),
        "OIT revenue 2026/2024 (real)": (r2["Revenue_OIT"] / r0["Revenue_OIT"], "~1.00-1.02 (constant-currency growth ~4% FY25, ~1% FY26, less US inflation)"),
        "India unemployment change (pts)": ((r2["Unemp_IN"] - r0["Unemp_IN"]) * 100, "no direct series; bench and fresher onboarding delays reported"),
        "Onshore IT headcount 2026/2024": (r2["HeadLoc_ON"] / r0["HeadLoc_ON"], "~1.00-1.02 (US OEWS computer and math +1.3% in 2024-25)"),
        "Business (LOB) workforce 2026/2024": (r2["LOB"] / r0["LOB"], "0.98-0.99 (AI-attributed layoffs small vs workforce)"),
    }


def fit_given_growth(dg):
    """Inner fit: growth-path calibration for DemandGrowth = dg, then least squares on the AI parameters."""
    S.P["DemandGrowth"] = dg
    for v in S.VENDORS:
        S.P["PriceMult_" + v] = 1.0
    st, r2, agg = C.calibrate()
    init = json.loads(json.dumps(st))
    res = least_squares(residuals, X0, bounds=([b[1] for b in FIT], [b[2] for b in FIT]), args=(init,), x_scale=[0.01, 0.1, 0.1, 0.5, 0.1, 0.5, 0.05, 0.005, 1.0, 0.1, 5000.0],
                        diff_step=1e-2, max_nfev=300)
    return res, init


def _grid_point(dg):
    res, init = fit_given_growth(dg)
    return dg, res.x.tolist(), float(res.cost), init, dict(S.P)


def fit(verbose=True, grid=DG_GRID):
    """Outer fit: DemandGrowth (underlying real growth of IT work) by profile over a grid; the best cost wins."""
    from multiprocessing import Pool
    out = [_grid_point(dg) for dg in grid]
    best = None
    for dg, x, cost, init, params in out:
        if verbose:
            print(f"DemandGrowth {dg}: cost {cost:.5f}", {k: round(v, 3) for (k, _, _), v in zip(FIT, x)})
        if best is None or cost < best[0]:
            best = (cost, x, init, dg, params)
    cost, x, init, dg, params = best

    class R:  # minimal stand-in for the least_squares result
        pass
    res = R(); res.x = x; res.cost = cost
    best = (res, init, dg, params)
    res, init, dg, params = best
    S.P.clear(); S.P.update(params)
    fitted = {k: round(float(v), 4) for (k, _, _), v in zip(FIT, res.x)}
    fitted["DemandGrowth"] = dg
    S.P.update(fitted)
    S.P["AdoptC0"] = round(with_derived({})["AdoptC0"], 5)
    m, at = metrics(init, {})
    if verbose:
        print("fitted", fitted, "AdoptC0", S.P["AdoptC0"], "cost", res.cost)
        for k, yv, val, w, src in TARGETS:
            print(f"  {k:18s} {yv:.0f} target {val:6.3f} model {m[(k, yv)]:6.3f}")
        for k, (mv, obs) in validation(at).items():
            print(f"  VALID {k:40s} model {mv:7.3f}  observed {obs}")
    return init, fitted, m, at


if __name__ == "__main__":
    init, fitted, m, at = fit()
    json.dump({"params": S.P, "init": init, "fitted": fitted,
               "targets": [dict(metric=k, year=yv, target=val, model=m[(k, yv)], source=src) for k, yv, val, w, src in TARGETS],
               "validation": {k: dict(model=mv, observed=obs) for k, (mv, obs) in validation(at).items()}},
              open("calib7.json", "w"))
