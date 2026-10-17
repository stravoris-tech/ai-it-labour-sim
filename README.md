# ai-it-labour-sim

A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India and onshore
(North America and Europe), 2024-2040. It is a Python port of a prototype model, built as a tool for running many
simulations under chosen scenario levers and uncertainty.

## Status

The first public release, 0.1.0. The default model is `phase8` ("Models" below). The frozen Python prototype is in
[`reference/`](reference/README.md).

## Asking a question

A question combines the baseline, an optional named scenario (`aisim.SCENARIOS`), fixed overrides and sampled
uncertain levers. `run_experiment` validates it, runs it across cores and returns the results as numpy arrays with
pandas views. This example asks how onshore IT headcount moves relative to 2024 under the Fast AI scenario, with 1,000
runs sampling the junior cut per unit of adoption `JuniorCut` over the default model's tornado range and the T&M brake
on vendor adoption `TMBrake`:

```python
from aisim import Experiment, Uniform, run_experiment


def main() -> None:
    exp = Experiment(
        scenario="Fast AI",
        sample={"JuniorCut": Uniform(0.38, 1.14), "TMBrake": Uniform(0.2, 0.6)},
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
  12 act from their own start years. `perturb_from` applies them from a chosen year instead (below).

## Perturb from year Y

`perturb_from=Y` runs the calibrated baseline unchanged until Y and applies everything that differs from it (the
scenario, overrides, tables, sampled levers and noise) from Y on. Before Y every run is the baseline, so the bands
there have zero width. This example samples the tornado levers from mid-2026:

```python
from aisim import Experiment, run_experiment
from aisim.scenarios import tornado_levers


def main() -> None:
    exp = Experiment(
        sample=tornado_levers(perturb_from=2026.5), n=1000, method="lhs", seed=20261012, perturb_from=2026.5
    )
    res = run_experiment(exp, outputs=["HeadTotal"])
    print(res.bands("HeadTotal", q=(0.1, 0.5, 0.9), years=(2024, 2032)))


if __name__ == "__main__":
    main()
```

- **How it runs.** A two-phase run: the baseline runs once from 2024 to Y, and every run restarts from its state at Y
  with its own parameters. Y must lie on the step grid (a whole number of 1/16-year steps from 2024) and inside the
  run. There is one Y per experiment, and `run_scenarios` uses it for every scenario. `perturb_from=2024` is the same
  as leaving it unset.
- **Paths stay continuous.** Five exogenous paths are written in closed form from 2024: the automatable share of work
  (rate `g`), the verification overhead (`VerifDecline`), line-of-business automation (`aL_max`, `g`) and the two AI
  cost paths (`AICostDecline`). A run whose rate differs from the baseline continues each path from its baseline
  value at Y at its own rate, so nothing jumps at Y. Levers whose own effect is immediate still step at Y:
  `SrcCostSens`, `JuniorCut`, `PriceHorizon` and `JevonsEps`.
- **2024 levels cannot act from Y.** Some parameters describe 2024 itself: the 2024 verification overhead `Verif`,
  `AICost2024`, `GCCMomentum`, the 2024 adoption levels, the 2024 level split of the workforce (`Share0_*`), and the
  stored calibration constants (the `level_2024` column of `aisim.domains()`). Changing one "from 2026.5" has no
  meaning, so with a perturb year after 2024 it is a validation error. It is also why `PAI0`, the 2024 productivity
  that `Verif` calibrates, needs no pin: `Verif` cannot change.
- **Rates anchored at 2024.** `DemandGrowth`, `ITBudgetGrowth` and the `amax` table drive paths written in closed form
  from 2024 that are not re-anchored at Y, so changing one with a perturb year after 2024 would make its path jump at
  Y. That is a validation error too, until re-anchoring them is built.
- **Windows that start before Y.** A time window or ramp that starts before Y and would change the run before Y is a
  validation error. Visa crackdown's ramp starts at 2025.7, so with `perturb_from=2026.5` it raises and suggests a
  perturb year at or before 2025.7. The scenarios themselves are unchanged.
- **The tornado levers depend on Y.** `tornado_levers(perturb_from=...)` drops every lever whose range fails these
  checks at that Y: all 14 without a perturb year, 13 at 2026.5 (`Verif` is a 2024 level) and 12 at 2027
  (`DemandGrowthLate` too: its window opens at 2026.5, before Y).
- **The tornado ranges depend on the model.** `tornado_levers(model=...)` sets the `Verif` and `JuniorCut` ranges
  from that model's own values, at the prototype's ratios (x0.7 to x1.3 and x0.5 to x1.5); every other range is the
  same in every model. `aisim.scenarios.TORNADO` stays the Phase 7 tornado.
- **AI off.** `ai_on=False` with a perturb year is an error: the AI-off counterfactual runs from 2024.

## Process noise

`noise` adds seeded process noise from Y, off by default. It needs `perturb_from` (noise in the calibration period
would contradict history) and a `noise_seed`:

```python
from aisim import Experiment, Noise, run_experiment


def main() -> None:
    exp = Experiment(n=500, perturb_from=2026.5, noise={"demand": Noise(sigma=0.009, tau=1.0)}, noise_seed=7)
    res = run_experiment(exp, outputs=["HeadTotal"])
    print(res.bands("HeadTotal", q=(0.1, 0.5, 0.9), years=(2026, 2034)))


if __name__ == "__main__":
    main()
```

- **Channels.** Six, each a factor at one point of the model: `cap` (the productivity of AI-assisted work), `demand`
  (the underlying demand index, which also drives budgets, enrolment, the visa cap and seats), `budget` (IT budget
  growth), `aicost` (AI cost per automated unit), `adoption` (the consumer AI adoption flow) and `anchor` (the client
  price anchor on new FP, MS and OB prices, and on the annuity share of new TM prices when `AnnuityShare` > 0).
- **Process.** Each factor is `exp(x)`, with `x` an exact Ornstein-Uhlenbeck process: stationary sd `sigma`, one-year
  autocorrelation `exp(-1 / tau)` at any step size. `x` starts at 0 at Y, so the noise is exactly 0 up to and
  including Y, and the factor is always positive. `sigma` must be in [0, 0.5] and `tau` at least one step.
- **Streams.** Run i draws from its own stream, `SeedSequence(noise_seed, spawn_key=(i,))`, so its noise does not
  depend on the worker count, the chunking or the other channels, and never touches the lever samples. In
  `run_scenarios` run i has the same noise in every scenario.
- **Amplitudes.** None is built in: choose `sigma` and `tau` per channel and justify them. The only year-to-year
  series in the model's sources is Gartner's IT services growth (+5.6%, +3.8% and +5.3% for 2024-2026), with a
  year-to-year sd of about 1 point. The sd of the one-year change in a factor is `sigma sqrt(2 (1 - exp(-1 / tau)))`,
  so with `tau` = 1 year that point corresponds to a `demand` `sigma` of about 0.009. `sigma = 0.05` is about 6 times
  that. Nothing in the repo sets the other channels.

## Models

Three models are registered. `Experiment.model`, `Params.baseline(model=...)` and `BatchParams.baseline(n, model=...)`
name the calibrated baseline every run starts from; any other name raises. With no model named, runs use `phase8`
(`aisim.state.DEFAULT_MODEL`).

| Model | What it is |
| --- | --- |
| `phase7` | The prototype's calibrated model, bit for bit, kept as the prototype-parity reference |
| `phase8` | Continuous openings, the slice 8 pricing design and a full robust refit. **The default** |
| `phase8_highadoption` | `phase8` refitted with the adoption parameter `p` fixed at Phase 7's 0.044: the adoption-speed alternative |

- **What `phase8` changes.** Three things, each switched on in its baseline file
  (`src/aisim/data/baseline_phase8.json`):
  - **The openings fix.** In Phase 7, new openings drop to 0 the moment a unit-level is overstaffed, so the flow jumps
    where the surplus changes sign. That jump made the calibration loss discontinuous and stalled the optimiser. With
    the extension switch `OpeningsContinuous` on, openings follow one formula for every surplus, so they taper to 0
    as overstaffing grows. Layoffs are unchanged.
  - **The pricing design.** `PassThrough` 0.75, `AnnuityShare` 0.3 and `AnnuityAnchorW` 0.4: part of new T&M work is
    annuity work that carries the client price anchor.
  - **A robust refit.** All 11 calibrated parameters from a 32-start fit (`tools/calibrate.py --starts 32`), with
    `PriceHorizon` at most 7. 29 of the 32 starts land within 5% of the best loss (0.000423, against Phase 7's
    0.000800).
- **What moves, at 2030 in Base.**

  | Quantity | Fix | Recalibration | Pricing | Total |
  | --- | --- | --- | --- | --- |
  | `HeadTotal` | -0.03% | +3.50% | -0.10% | +3.37% |
  | `RevenueTot` | -0.03% | +4.38% | +0.32% | +4.68% |

  The fix itself barely moves the headlines. Pricing moves the effort-billed shares: OIT -5.1 points and BQ -8.1
  points.
- **What the recalibration means.** The 2025-2026 adoption data favour a higher innovation rate `p`: the loss falls
  steadily from `p` 0.02 to 0.25 when the other parameters are refitted at each value. Phase 7's adoption path (`p`
  0.044) was an optimiser stall on the hiring discontinuity, not a best fit. `phase8` adopts more slowly than
  `phase7`: `A_mean` 0.800 in 2028 and 0.904 in 2030, against 0.853 and 0.957, and it first reaches 0.99 in 2035
  rather than 2032.
- **`phase8_highadoption`.** The data identify the early adoption path, not its speed after 2026, so this model keeps
  Phase 7's `p` and refits the rest (loss 0.000748). Its adoption runs higher later: `A_mean` 0.853 in 2028 and 0.957
  in 2030. For a question that depends on adoption speed, compare the two models rather than sampling `p`. `p` and
  the 2024 levels it moves cannot change under `perturb_from`, so the comparison has to be between models.
- **Pricing what-ifs.** The pricing parameters can be used as overrides or sampled levers on any model:
  - `AnnuityShare`: the annuity share of new T&M signings, which carries `Anchor ** AnnuityAnchorW`;
  - `AnnuityAnchorW`: the weight of the anchor on that share;
  - `PassThrough`: the share of the trend clients pass into prices.

  On `phase7`, `AnnuityShare` and `AnnuityAnchorW` default to 0, which reproduces Phase 7 exactly; in `phase8` they
  are calibrated. Under `perturb_from` they act from Y, like any lever.
- **How a model is built.** `tools/calibrate.py` fits it and `tools/build_model.py` writes its baseline file from
  `tools/models/<name>/spec.json` and `fit.json`. A model is never written by hand. Each baseline file reproduces its
  fit's loss bit for bit, and its 2024 state is Phase 7's.

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
  per vendor, contract type, scenario and so on. Past 10 series the colours repeat with dashed and then dotted lines,
  and each scenario has its own colour and line style. `charts.save(fig, "chart.svg")` writes PNG, SVG or PDF.
- **The calibration period.** The years 2024-2026 are shaded as the calibration period: the model is fitted to data
  for those years, but the runs already disagree there, because levers act from 2024. The bands in that period show
  the lever uncertainty applied from 2024. A result run with `perturb_from` shades 2024 to Y instead, labelled
  "calibrated baseline until 2026.5" (say), where its bands have zero width. `shade=False` turns the shading off.
- **Reports.** `Report.to_html(path)` writes one file with the charts as inline SVG and nothing loaded from outside;
  `to_markdown(dir)` writes `report.md` and PNG files. `aisim.report.to_markdown_table(df)` formats a table for
  markdown notes. [`examples/q01_contract_mix.py`](examples/q01_contract_mix.py) rebuilds the Q01 analysis in about
  100 lines. It runs on `phase7`, to reproduce [`docs/analyses/q01-contract-mix.md`](docs/analyses/q01-contract-mix.md).

### Temporary shocks

Compute shock (2027 to mid-2029) and Downturn (2027 to 2029) are temporary. Over the shock window plus five years,
Compute shock costs about 21,900 person-years (model units) of IT employment against Base (3.5% of Base over that
span) and Downturn about 10,200 (1.8%). Headcount is back at Base by about 2032 in both, then rises above it for a few
years before settling. When demand returns, the backlog of work builds faster than hiring can follow, and hiring then
catches up past the need. This hiring-delay loop is part of the model's design, but its size depends on two adjustment
times (`TargetClearanceTime` and `HireAdjTime`) that no calibration target constrains, so read the rebound's size as
illustrative. Compute shock acts mainly through client budgets.

## Limitations

1. **Adoption speed is not in the uncertainty bands.** `p` and the `level_2024` parameters it moves cannot change
   after the perturb year. Compare `phase8` with `phase8_highadoption` instead (`A_mean` 2030: 0.904 against 0.957).
2. **`PriceHorizon` sits at its fit bound of 7.** Refitting with it above 7 lowers the loss steadily (0.9% at 7.5,
   7.5% at 12, no minimum up to 12), and every core target still passes. Headcount moves by under 0.3%, and revenue
   is up to 2.1% lower in 2040, but the 2040 revenue-weighted effort-billed share rises from 0.297 to 0.355. The bound
   is a modelling choice, and effort-share results depend on it.
3. **The size of the post-shock rebound is not validated** (see "Temporary shocks").
4. **Hire and fire together.** Under continuous openings, a unit-level can have openings and layoffs in the same
   step. `phase8` Base has no step with both. In Fast AI, onshore seniors see both after 2030, at up to 2.85% of staff
   a year. On Phase 7's values with the switch on, onshore seniors see both at up to 1.53% of staff a year in Base,
   all after 2030 (peak at 2031.75), and up to 4.05% in Fast AI (peak at 2031.375), where 21 of the 96 steps with
   both are before 2030. No calibration target sees it.
5. **Missed targets.** `phase8` misses two of the pricing evidence targets of the
   [pricing research report](docs/research/ai-pricing-automation-analogues.md):
   - **The renewal step-down on annuity contracts**, about 20% (HCLTech: a deal that would have been $100M now closes
     at about $80M; Persistent: clients ask for the same work for 25-30% less). `phase8` gives 4.3% at 2030 (OIT, the
     price step on expiring MS and TM work, weighted by expiring volume). No model meets it: in the model, effort
     volume falls continuously rather than at renewal.
   - **The per-unit discount**, 25-40% within 3-5 years once a usable output proxy exists (translation, 2014-2026;
     medium confidence for the direction, low for the size in IT). `phase8` gives 21.7% at 2030 (one minus OIT's new
     fixed-price signing price), where `phase7` gives 33.4%.
6. **The core 4 band.** One of the pricing checks is the OIT book price drift, the `AvgIdx_OIT` CAGR over 2026-2030.
   Its band is [-3.5%, -2%] a year. It was widened from [-3%, -2%] by an operator ruling on 2026-10-16, made after
   recon 09's results were seen. The evidence is HCLTech's 2-3% a year for its own portfolio and Kotak's 3.5% base
   case for Indian IT. `phase8` gives -2.96% a year, inside both bands; `phase8_highadoption` gives -3.23%.
7. **Lever ranges were set by hand in the prototype,** with no cited evidence. `Verif` and `JuniorCut` scale with
   each model's value. `JevonsEps` is one-sided from 0, and `PriceHorizon` sits at 0.75 of its range on `phase8`.

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
- This repository starts with a fresh history. Commit ids recorded in its files (`git_commit` in each
  `tools/models/<name>/fit.json`, the golden manifests and the docs) refer to the private development repository.

## Development

- [`docs/development.md`](docs/development.md): how the model was built, slice by slice, with each slice's gate,
  test count and key decisions.
- [`docs/analyses/`](docs/analyses/): the four analyses (Q01-Q04) asked of the model during development.
- [`docs/research/`](docs/research/): the research report on AI pricing and automation analogues behind the pricing
  design.

## Licence

The split is exhaustive:

- **MIT** ([`LICENSE`](LICENSE)): everything not listed below, including the code blocks inside the documentation.
- **CC BY 4.0** ([`LICENSE-DOCS`](LICENSE-DOCS)): `docs/`, `reference/prototype/spec/`, `reference/prototype/data/`,
  `reference/goldens/`, `src/aisim/data/`, `tests/data/`, `tools/models/`, `tools/calibration_targets.csv` and the
  prose of this README.

The package metadata declares `MIT AND CC-BY-4.0`, with both licence files.

## How to cite

See [`CITATION.cff`](CITATION.cff).
