"""Q01 again, with the charts and reports API: how a vendor's contract book shifts between contract types, 2024-2032.

Run from the repo root:

    uv run python examples/q01_contract_mix.py [--n 1000] [--out temp/examples/q01]

It rebuilds the core of the Q01 analysis (``temp/analysis/q01-contract-mix/run.py``, 908 lines) with the package's own
functions:

- the OIT book-mix bands (median and p10-p90 over the 14 tornado levers) with the deterministic baseline run;
- the four scenarios (Baseline, Slow AI, Fast AI, Jevons rebound) on the same draws, with ``run_scenarios``;
- the drivers of the 2032 mix (Spearman rank correlation of each lever);
- one self-contained HTML report.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import aisim
from aisim import charts
from aisim.experiment import dims, drivers, keys, run_scenarios
from aisim.report import Report
from aisim.scenarios import tornado_levers

SEED = 20261012
WINDOW = (2024.0, 2032.0)
VENDOR = "OIT"
SCENARIOS = [None, "Slow AI", "Fast AI", "Jevons rebound"]
EFFORT = "EffortShare_revenue_weighted"


def scenario_table(scen: aisim.ScenarioResult, book: list[str], year: float) -> pd.DataFrame:
    """The book mix in ``year``: one row per scenario, one ``median (p10-p90)`` cell per contract type."""
    rows = []
    for s in scen:
        row = {"scenario": scen.label(s)}
        for k in book:
            b = scen[s].bands(k, years=(year, year)).iloc[0]
            row[dims(k)["type"]] = f"{b[0.5]:.3f} ({b[0.1]:.3f}-{b[0.9]:.3f})"
        rows.append(row)
    return pd.DataFrame(rows)


def main(n: int, out: Path) -> Path:
    book = keys(family="contract mix (book)", vendor=VENDOR)
    fp = keys(family="contract mix (book)", type="FP")
    outputs = list(dict.fromkeys([*book, *fp, EFFORT]))

    # The default model's 14 tornado levers, by Latin hypercube; every scenario runs on the same draws, and pins the
    # levers it sets (Slow and Fast AI set g and VerifDecline, Jevons rebound sets JevonsEps).
    sample = tornado_levers()
    exp = aisim.Experiment(sample=sample, n=n, method="lhs", seed=SEED)
    scen = run_scenarios(exp, SCENARIOS, outputs=outputs)
    mc = scen[None]
    base = aisim.run_experiment(aisim.Experiment(), outputs=outputs)

    report = Report(f"Q01: the {VENDOR} contract book by type, 2024-2032")
    report.add_text(
        f"How does the {VENDOR} contract book shift between fixed price (FP), time and materials (TM), managed "
        f"services (MS), staff augmentation (SA) and outcome-based (OB) contracts? {mc.n:,} runs sample the 14 "
        "tornado levers; each scenario runs on the same draws.\n\n"
        "- The model shows shares of book volume, not revenue.\n"
        "- The shaded years are the calibration period: levers act from 2024, so the bands open there already."
    )
    report.add_chart(
        charts.bands(mc, book, baseline=base, window=WINDOW, title=f"{VENDOR}: book mix by contract type"),
        "Median and p10-p90 of the Monte Carlo runs; dashed: the deterministic baseline run.",
    )
    report.add_chart(
        charts.scenarios(scen, book, window=WINDOW, title=f"{VENDOR}: book mix under four scenarios"),
        "One panel per scenario, on common random numbers.",
    )
    report.add_chart(
        charts.scenarios(scen, EFFORT, layout="overlay", window=WINDOW),
        "Effort-billed share (TM + SA) of the vendor books, weighted by vendor revenue, by scenario.",
    )
    table = drivers(mc, [EFFORT, *fp], 2032)
    report.add_chart(
        charts.drivers(table, title="Drivers of the 2032 mix (Spearman rho)"),
        "Rank correlation of each sampled lever with the 2032 outputs, strongest first.",
    )
    report.add_table(scenario_table(scen, book, 2032.0), f"{VENDOR} book mix in 2032: median (p10-p90).")
    report.add_table(table, "Drivers: Spearman rho with the 2032 outputs.", "{:.3f}")
    report.add_settings(scen)
    out.mkdir(parents=True, exist_ok=True)
    return report.to_html(out / "report.html")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Q01 again, with the charts and reports API.")
    parser.add_argument("--n", type=int, default=1000, help="Monte Carlo runs per scenario (default 1000)")
    parser.add_argument("--out", type=Path, default=Path("temp/examples/q01"), help="output directory")
    args = parser.parse_args()
    path = main(args.n, args.out)
    print(f"wrote {path} ({path.stat().st_size:,} bytes)")
