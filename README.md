# ai-it-labour-sim

A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India and onshore
(North America and Europe), 2024-2040. It is a Python port of a prototype model, built as a tool for running many
simulations under chosen scenario levers and uncertainty.

## Status

Charts and reports built; noise and perturb-from-year next. The frozen Python prototype is in
[`reference/`](reference/README.md).

## Asking a question

A question combines the baseline, an optional named scenario (`aisim.SCENARIOS`), fixed overrides and sampled
uncertain levers. `run_experiment` validates it, runs it across cores and returns the results as numpy arrays with
pandas views. This example asks how onshore IT headcount moves relative to 2024 under the Fast AI scenario, with 1,000
runs sampling the junior cut per unit of adoption `JuniorCut` and the T&M brake on vendor adoption `TMBrake`:

```python
from aisim import Experiment, Uniform, run_experiment


def main() -> None:
    exp = Experiment(
        scenario="Fast AI",
        sample={"JuniorCut": Uniform(0.29, 0.87), "TMBrake": Uniform(0.2, 0.6)},
        n=1000,
        seed=2024,
    )
    res = run_experiment(exp, outputs=["OnshoreTotal"])
    print(res.bands("OnshoreTotal", q=(0.1, 0.5, 0.9), ratio_to=2024, years=(2024, 2032)))


if __name__ == "__main__":
    main()
```

- **Layers.** Values apply lowest to highest: baseline, scenario, `overrides`, then sampled (or explicit `samples`)
  values. An override may replace a scenario's value, but a parameter that `overrides` or the scenario fixes cannot
  also be sampled: sampling Fast AI's `g` here would raise. To compare scenarios on the same samples, use
  `run_scenarios` (below).
- **Outputs.** `outputs` names row keys, extras or derived outputs (such as `OnshoreTotal`, the sum of the two onshore
  Q1 lines). `aisim.catalogue()` lists them all with units and descriptions; `aisim.keys(family=..., vendor=...)`
  filters them by family and dimension, and `aisim.experiment.dims(key)` gives a key's dimensions.
  `aisim.domains()` gives every parameter's valid range.
- **Results.** `bands` gives per-year percentiles over the valid runs, here as ratios to each run's 2024 value; it
  also takes an `(runs, years)` array computed from the series. `single(key)` gives a one-run result's series.
  `frame`, `long`, `ratio`, `q3` and `q3_counts` give the other views; `series` holds the raw `(runs, years)` arrays.
  `save(path)` and `ExperimentResult.load(path)` keep a result on disk (`.npz` plus a JSON sidecar), and `meta` is
  JSON-safe, with the git commit and platform.
- **Reproducible.** The same seed gives the same samples and the same results, whatever the number of worker
  processes or the chunk size. By default the chunk size is chosen for you: up to 200 runs run in this process, larger
  experiments in chunks of `ceil(n / workers)` between 50 and 625 runs.
- **Validation.** Invalid inputs raise one `ValidationError` listing every problem before any run starts:
  out-of-range values, overrides that have no effect, broken calibration identities and time constants shorter than
  the step. `validate=False` skips the checks.
- **Windows.** Worker processes are started by re-importing your script, so a script that calls `run_experiment`
  must guard its entry point with `if __name__ == "__main__":`, as above.
- **Levers act from 2024.** As in the prototype, a lever changes the model from the first step, so 11 of the 23
  scenario and tornado levers also move the 2024-2026 calibration window: `g`, `Verif`, `VerifDecline`, `JevonsEps`,
  `JuniorCut`, `TMBrake`, `PriceHorizon`, `aL_max`, `SrcCostSens`, `AICostDecline` and `EnrolSensitivity`. The other
  12 act from their own start years. A later slice adds an option to apply levers from a chosen year.

## Charts and reports

Charts need matplotlib, an optional extra: `pip install "ai-it-labour-sim[charts]"` (with uv, `uv sync` installs it
in the dev group). `run_scenarios` runs several scenarios on the same draws in one batch, `aisim.charts` draws the
results with years on the x-axis, and `Report` writes them into one self-contained HTML page:

```python
from aisim import Experiment, Uniform, charts, run_experiment, run_scenarios
from aisim.experiment import drivers, keys
from aisim.report import Report


def main() -> None:
    book = keys(family="contract mix (book)", vendor="OIT")
    exp = Experiment(sample={"g": Uniform(0.06, 0.15), "TMBrake": Uniform(0.2, 0.6)}, n=500, method="lhs", seed=1)
    scen = run_scenarios(exp, [None, "Slow AI", "Fast AI"], outputs=book)
    base = run_experiment(Experiment(), outputs=book)

    report = Report("OIT contract book mix")
    report.add_chart(charts.bands(scen[None], book, baseline=base), "Median and p10-p90; dashed: baseline run.")
    report.add_chart(charts.scenarios(scen, book), "One panel per scenario, on the same draws.")
    report.add_table(drivers(scen[None], book, 2032), "Spearman rho of each lever with the 2032 shares.")
    report.add_settings(scen)
    report.to_html("report.html")


if __name__ == "__main__":
    main()
```

- **Scenarios on common random numbers.** Every scenario in `run_scenarios` runs on the same samples, so the
  differences come from the scenarios alone. A scenario that sets a sampled lever pins it: Slow and Fast AI set `g`,
  so their blocks run with their own `g` and the other levers as drawn. `scen.pinned` lists the pinned levers. An
  override of a parameter a requested scenario sets is an error there.
- **Charts.** `bands` (median and band per key, optional dashed baseline run), `scenarios` (small multiples or an
  overlay), `lines` (one-run results, or any x such as a parameter sweep) and `drivers` (rank-correlation bars). The
  window is 2024-2040 unless `window=` says otherwise; y-labels come from the catalogue units, and colours are fixed
  per vendor, contract type, scenario and so on. `charts.save(fig, "chart.svg")` writes PNG, SVG or PDF.
- **The calibration period.** The years 2024-2026 are shaded as the calibration period: the model is fitted to data
  for those years, but the runs already disagree there, because levers act from 2024. The bands in that period show
  the lever uncertainty applied from 2024. `shade=False` turns the shading off.
- **Reports.** `Report.to_html(path)` writes one file with the charts as inline SVG and nothing loaded from outside;
  `to_markdown(dir)` writes `report.md` and PNG files. `aisim.report.to_markdown_table(df)` formats a table for
  markdown notes. [`examples/q01_contract_mix.py`](examples/q01_contract_mix.py) rebuilds the Q01 analysis in about
  100 lines.

## Reproducibility

- Results are bit-for-bit reproducible on the same platform and numpy build.
- On x86-64 CPUs with AVX-512, numpy's faster maths kernels round `np.power` and `np.log` differently from the C
  library in about 5% and 0.03% of calls, by 1 ulp each. These are rounding effects, not differences in the model.
  Over a run they move:
  - the head counts and the Q1 lines at 2040 by at most about 7e-16 relative (about 3 ulp);
  - some intermediate and other ordinary values by up to about 1.5e-12 relative (for example the S7 cancellations,
    `S7.cancel`);
  - values that should be exactly 0, such as AI costs with AI off, by up to about 2e-7 (roundoff in place of 0).
- To reproduce the reference numbers exactly on such a CPU, set
  `NPY_DISABLE_CPU_FEATURES="X86_V4 AVX512_ICL AVX512_SPR"`. CI does. The list is for x86-64 builds of numpy only (it
  names numpy 2.5's x86 targets); do not set it on ARM64 or macOS. `uv run python tools/numerics_probe.py` reports
  whether this machine's kernels match.

## Licence

- Code is under the MIT licence ([`LICENSE`](LICENSE)): all code under `src/` except `src/aisim/data/`, `tests/`,
  `tools/`, `scripts/`, `examples/`, `.claude/` and `reference/prototype/code/`.
- Documentation and data are under CC BY 4.0 ([`LICENSE-DOCS`](LICENSE-DOCS)): `docs/`, `reference/prototype/spec/`,
  `reference/prototype/data/`, `reference/goldens/`, `src/aisim/data/` and the text of this README.

## How to cite

See [`CITATION.cff`](CITATION.cff).
