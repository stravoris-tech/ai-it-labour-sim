"""Phase 1 core loop prototype - mirrors the AnyLogic build guide exactly.

One sector, one employer, no arrays. Euler integration.
Time: years since 2024 (Year = 2024 + t).
"""
import json


def run(ai_on=True, dt=1/16, stop=16.0, demand_step=0.0, step_year=2028,
        jevons_eps=0.0, a_2024=0.20, a_max=0.60, g=0.10, s=5.0, v=0.05,
        p=0.03, q=0.40, A0=0.05, record_every=1.0):
    # ---- parameters ----
    BaseDemand = 100_000.0        # BFY/yr
    WorkPerPerson = 1.0           # BFY/person/yr at baseline productivity
    TargetClearanceTime = 0.5     # yr
    MinCompletionTime = 0.25      # yr
    AbandonTolerance = 1.5        # yr of throughput the backlog may hold
    AbandonTime = 1.0             # yr
    AvgTenure = 5.0               # yr (voluntary attrition)
    HireAdjTime = 0.5             # yr
    LayoffAdjTime = 0.25          # yr
    MinLayoffTime = 0.25          # yr (first-order cap)
    PerceptionTime = 1.0          # yr
    JevonsCap = 2.0               # max demand multiplier

    # ---- initial values (steady state with P_eff = 1) ----
    Backlog = BaseDemand * TargetClearanceTime
    Headcount = BaseDemand / WorkPerPerson
    A = A0
    PerceivedP = 1.0

    rows = []
    t = 0.0
    n_steps = int(round(stop / dt))
    rec_k = int(round(record_every / dt))
    min_stock = {"Backlog": Backlog, "Headcount": Headcount}
    for k in range(n_steps + 1):
        year = 2024 + t
        # ---- auxiliaries ----
        a = max(0.0, a_max - (a_max - a_2024) * (1 - g) ** (year - 2024))
        P_AI = 1.0 / ((1 - a) + a / s + a * v)
        P_eff = (A * P_AI + (1 - A)) if ai_on else 1.0
        CostIndex = 1.0 / P_eff
        JevonsMult = min(JevonsCap, CostIndex ** (-jevons_eps))
        demand = BaseDemand * (1 + (demand_step if year >= step_year else 0.0)) * JevonsMult
        Capacity = Headcount * WorkPerPerson * P_eff
        Completion = min(Capacity, Backlog / MinCompletionTime)
        Abandonment = max(0.0, Backlog - Completion * AbandonTolerance) / AbandonTime
        Desired = Backlog / (TargetClearanceTime * WorkPerPerson * PerceivedP)
        Attrition = Headcount / AvgTenure
        gap = Desired - Headcount
        Adjustment = gap / HireAdjTime if gap > 0 else gap / LayoffAdjTime
        Hiring = max(0.0, Attrition + Adjustment)
        Layoffs = min(max(0.0, -(Attrition + Adjustment)), Headcount / MinLayoffTime)
        Adoption = (p + q * A) * (1 - A) if ai_on else 0.0
        Adoption = min(Adoption, (1 - A) / dt)  # clamp keeps A <= 1
        PerceptionChange = (P_eff - PerceivedP) / PerceptionTime

        if k % rec_k == 0:
            rows.append({"year": round(year, 3), "Headcount": Headcount, "Backlog": Backlog,
                         "Desired": Desired, "P_eff": P_eff, "A": A, "a": a,
                         "Hiring": Hiring, "Layoffs": Layoffs, "Abandonment": Abandonment,
                         "Demand": demand})
        if k == n_steps:
            break
        # ---- integrate ----
        Backlog += dt * (demand - Completion - Abandonment)
        Headcount += dt * (Hiring - Attrition - Layoffs)
        A += dt * Adoption
        PerceivedP += dt * PerceptionChange
        min_stock["Backlog"] = min(min_stock["Backlog"], Backlog)
        min_stock["Headcount"] = min(min_stock["Headcount"], Headcount)
        t += dt
    return rows, min_stock


def summary(rows, years=(2024, 2026, 2030, 2035, 2040)):
    out = {}
    for r in rows:
        if int(round(r["year"])) in years and abs(r["year"] - round(r["year"])) < 1e-6:
            out[int(round(r["year"]))] = {k: round(v, 3) for k, v in r.items() if k != "year"}
    return out


if __name__ == "__main__":
    results = {}
    tests = {
        "T1_ai_off": dict(ai_on=False),
        "T2_step_ai_off": dict(ai_on=False, demand_step=0.20),
        "T3_ai_on_base": dict(ai_on=True),
        "T4_ai_on_jevons": dict(ai_on=True, jevons_eps=0.5),
        "T5_ai_on_dt32": dict(ai_on=True, dt=1/32),
        "T6_extreme": dict(ai_on=True, a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0),
    }
    for name, kw in tests.items():
        rows, mins = run(**kw)
        results[name] = {"checkpoints": summary(rows), "min_stocks": mins,
                         "series": [{"year": r["year"], "Headcount": round(r["Headcount"], 1),
                                     "P_eff": round(r["P_eff"], 4), "A": round(r["A"], 4)} for r in rows]}
    with open("phase1_results.json", "w") as f:
        json.dump(results, f, indent=1)
    for name, res in results.items():
        cp = res["checkpoints"]
        line = ", ".join(f"{y}: H={cp[y]['Headcount']:,.0f} P={cp[y]['P_eff']:.3f} A={cp[y]['A']:.2f}" for y in cp)
        print(name, "|", line, "| min:", {k: round(v) for k, v in res["min_stocks"].items()})
