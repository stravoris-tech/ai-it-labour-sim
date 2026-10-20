# ai-it-labour-sim

A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India and onshore
(North America and Europe), 2024-2040. It is a Python port of a prototype model, built as a tool for running many
simulations under chosen scenario levers and uncertainty.

## Status

Release 0.2.0. The default model is `phase9`, which adds four evidence-based feedback loops to `phase8` ("Models"
below). The model is frozen at this release: it changes only for a defect, and improvements wait for a later version
([`docs/development.md`](docs/development.md), "The freeze"). The frozen Python prototype is in
[`reference/`](reference/README.md).

## What the model gives

The model gives scenario projections, not forecasts. Read every result as "under these assumptions".

- **The path to 2030 is anchored in data.** The model is calibrated to 2024-2026 data and one GCC outlook for 2030.
  Two loop structures fitted to the same data (`phase8` without the loops, `phase9` with them) agree on every
  headcount and revenue headline within 1% to 2030, and on the main shares within about 1 point.
- **After 2030 the structure decides.** The split of work between vendors and companies' own captive centres (GCCs),
  vendor revenue and the onshore/offshore mix rest on structural assumptions and outside evidence, not on the
  calibration data. By 2040 the same two structures differ by 3.2% on vendor headcount and 5.6% on GCC headcount.
- **Results are conditional ranges.** State a result as a range under named scenario levers and uncertain inputs.
  The largest single uncertainty is the GCC wave, the assumed growth of GCCs: within the bounds tested it moves 2040
  GCC headcount by about 34% either way, the largest effect of any structural assumption examined ("Limitations").

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
  12 act from their own start years. Of the eight loop strengths that `phase9` adds as levers, three move the window
  at any value in their range (`kR7`, `R10rc` and `R4a`), and `PriceFloor` does at its high. `perturb_from` applies
  them all from a chosen year instead (below).

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
  `SrcCostSens`, `JuniorCut`, `PriceHorizon` and `JevonsEps`, and on `phase9` the R7 strength `kR7`, which scales the
  GCC scale term from the first step after Y.
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
  checks at that Y. On `phase9` that leaves all 22 without a perturb year (the 14 tornado levers and the eight loop
  strengths), 21 at 2026.5 (`Verif` is a 2024 level) and 20 at 2027 (`DemandGrowthLate` too: its window opens at
  2026.5, before Y). On the models without loops the counts are 14, 13 and 12.
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

Five models are registered. `Experiment.model`, `Params.baseline(model=...)` and `BatchParams.baseline(n, model=...)`
name the calibrated baseline every run starts from; any other name raises. With no model named, runs use `phase9`
(`aisim.state.DEFAULT_MODEL`).

| Model | What it is | Use it for |
| --- | --- | --- |
| `phase9` | `phase8` plus four feedback loops from outside evidence, with a full refit. **The default** | Every question, unless a row below says otherwise |
| `phase9_highadoption` | `phase9` refitted with the adoption parameter `p` fixed at Phase 7's 0.044 | The adoption-speed alternative to `phase9`, for questions that depend on adoption speed |
| `phase8` | Continuous openings, the slice 8 pricing design and a full robust refit, without the loops. The default of release 0.1.0 | The earlier structure: reproducing a phase 8 result, or isolating what the loops change |
| `phase8_highadoption` | `phase8` refitted with `p` fixed at 0.044 | The adoption-speed alternative to `phase8` only |
| `phase7` | The prototype's calibrated model, bit for bit | Prototype parity |

**What `phase9` shows.** These are model units in Base, from deterministic runs, unless stated.
- **Total employment.** Total IT employment moves from 82,654 in 2024 to 80,671 in 2040 (-2.4%). Across 1,000
  uncertain runs from mid-2026 its 2040 range is 70,980-102,640 (p10-p90).
- **Who employs.** The work moves from vendors to GCCs. Vendor headcount falls 36% (48,600 to 31,060), GCC headcount
  triples (8,493 to 25,425), and India's share of the total rises from 44% to 50%.
- **A feedback loop drives part of that shift.** The more work GCCs hold, the easier the next one is to set up (R7).
  Over its evidence range, it moves 2040 vendor headcount by -8% to +6% without changing the total.
- **Revenue, hiring and adoption.** Vendor revenue falls 24% in real terms (5.73 to 4.35 bn USD). Junior hiring ends
  at 0.50 of its 2024 level, and AI adoption reaches 90% of work in 2030.
- **Fast AI and the price rules.** Under the fastest AI path, client price rules bind: an AI discount above 30% is not
  passed on. Vendor margins then rise (OIT 25% in 2040, against 18% in Base), and effort-billed work falls to 17% of
  revenue ("Limitations").
- **Distress.** A vendor under sustained distress loses clients, then recovers as clients habituate. In the named
  stress set (Fast AI plus a 20% price shock on OIT), OIT's distress-attributable revenue loss is 6% after 2 years and
  15% after 5, never near the halving of the Satyam case.
- **Temporary shocks** cost about 21,900 person-years (Compute shock) and 10,200 (Downturn), and overshoot Base by 12%
  and 5% about four years after they end. That rebound comes from hiring delays and is not validated (below).
- **The loop strengths come from outside evidence,** not the 2024-2026 data. The data fit equally well with the loops
  on or off, so the strengths are sampled as eight extra uncertain levers. They carry about 5% of the 2040 GCC
  headcount band, 14% of the effort-share band and 13-21% of the margin bands.
- **Adoption speed.** `phase9_highadoption` adopts faster (`A_mean` 0.958 in 2030 against 0.904; it first reaches
  0.99 in 2031 rather than 2035). In Base by 2040 that moves vendor headcount by -2.2%, GCC headcount by +5.0% and
  revenue by -2.8%, close to the effect within the phase 8 pair (-1.9% and +5.0% on the two headcounts). Compare the
  two models rather than sampling `p`.

**What `phase9` adds.** It closes four feedback loops the specification names: R7 (GCC scale learning), R6 (vendor
capacity exit, client flight, a price floor and an AI-discount ceiling), R10 (attrition cost) and R4 (skill erosion).
Each is set at the base strength of an outside evidence report, with all 11 calibrated parameters refitted (loss
0.000421, against `phase8`'s 0.000423; 28 of the 32 starts land within 5% of the best). Against `phase8`, total
headcount is unchanged; by 2040 work shifts from vendors to GCCs (`VendorHead` -3.2%, `Head_GCC` +5.6% in Base). The
calibration data do not pin the loop strengths, so `tornado_levers(model="phase9")` adds them as eight structural
levers with their evidence ranges. Every loop is off at strength 0, so the other models are unchanged. The design,
forms, ranges and limitations are in [`docs/model-changes-phase9.md`](docs/model-changes-phase9.md).
- **`phase9_highadoption`** is to `phase9` what `phase8_highadoption` is to `phase8` (loss 0.000748; 31 of 32 starts
  within 5%). An adoption-speed question under `phase9` compares `phase9` with it, never with `phase8_highadoption`,
  which differs in structure as well.

**What `phase8` changed.** Three things, each switched on in its baseline file
(`src/aisim/data/baseline_phase8.json`), all kept in `phase9`:
- **The openings fix.** In Phase 7, new openings drop to 0 the moment a unit-level is overstaffed, so the flow jumps
  where the surplus changes sign. That jump made the calibration loss discontinuous and stalled the optimiser. With
  the extension switch `OpeningsContinuous` on, openings follow one formula for every surplus, so they taper to 0 as
  overstaffing grows. Layoffs are unchanged.
- **The pricing design.** `PassThrough` 0.75, `AnnuityShare` 0.3 and `AnnuityAnchorW` 0.4: part of new T&M work is
  annuity work that carries the client price anchor.
- **A robust refit.** All 11 calibrated parameters from a 32-start fit (`tools/calibrate.py --starts 32`), with
  `PriceHorizon` at most 7. 29 of the 32 starts land within 5% of the best loss (0.000423, against Phase 7's
  0.000800).

**What moved from `phase7` to `phase8`, and then to `phase9`,** at 2030 in Base:

| Quantity | Fix | Recalibration | Pricing | Total, to `phase8` |
| --- | --- | --- | --- | --- |
| `HeadTotal` | -0.03% | +3.50% | -0.10% | +3.37% |
| `RevenueTot` | -0.03% | +4.38% | +0.32% | +4.68% |

The fix itself barely moves the headlines. Pricing moves the effort-billed shares: OIT -5.1 points and BQ -8.1
points. The loops and their refit then add +0.05% to `HeadTotal` and +0.07% to `RevenueTot` at 2030; they matter after
2030.

- **What the recalibration means.** The 2025-2026 adoption data favour a far higher innovation rate `p` than Phase
  7's 0.044: the refits put it at 0.250 in both `phase8` and `phase9`. Phase 7's adoption path was an optimiser stall
  on the hiring discontinuity, not a best fit. `phase8` adopts more slowly than `phase7`: `A_mean` 0.800 in 2028 and
  0.904 in 2030, against 0.853 and 0.957, and it first reaches 0.99 in 2035 rather than 2032. `phase9` follows the
  same path.
- **The high-adoption models.** The data identify the early adoption path, not its speed after 2026, so these models
  keep Phase 7's `p` and refit the rest (`phase8_highadoption`: loss 0.000748, `A_mean` 0.853 in 2028 and 0.957 in
  2030). `p` and the 2024 levels it moves cannot change under `perturb_from`, so an adoption comparison has to be
  between models.
- **Pricing what-ifs.** The pricing parameters can be used as overrides or sampled levers on any model:
  - `AnnuityShare`: the annuity share of new T&M signings, which carries `Anchor ** AnnuityAnchorW`;
  - `AnnuityAnchorW`: the weight of the anchor on that share;
  - `PassThrough`: the share of the trend clients pass into prices.

  On `phase7`, `AnnuityShare` and `AnnuityAnchorW` default to 0, which reproduces Phase 7 exactly; in `phase8` and
  `phase9` they are calibrated. Under `perturb_from` they act from Y, like any lever.
- **How a model is built.** `tools/calibrate.py` fits it and `tools/build_model.py` writes its baseline file from
  `tools/models/<name>/spec.json` and `fit.json`. A model is never written by hand. Each baseline file reproduces its
  fit's loss bit for bit, and its 2024 state is Phase 7's.

**Diagrams.** The [model reference](docs/model-reference.md) shows an overview of the eight modules, five
causal-loop panels drawn from the loop inventory (`docs/model/loops.csv`, one row per link, and
`docs/model/loop_summary.csv`, one row per loop) and an article set of five small diagrams for readers outside the
project. Their draw.io sources and SVG and PNG exports are in [`docs/model/diagrams/`](docs/model/diagrams/),
generated by `tools/model_diagrams.py`. The [PDF model reference](docs/model-reference.pdf) prints them with twelve
stock-and-flow module pages, the data dictionary and the spec errata in one file.

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
  override of a parameter a requested scenario sets is an error there. `aisim.STRESS_SCENARIOS` holds one more
  named set, "Fast AI + OIT price shock", the smallest set of overrides in which every `phase9` loop acts: it is not
  in `SCENARIOS`, but `run_experiment` and `run_scenarios` accept its name like a scenario's.
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

Grouped by topic, the largest stakes first. "Without recalibration" means the 2024-2026 calibration was not redone
for the test; each bound is the 2040 change against the same scenario on `phase9`.

### Visa policy

- **Visa enforcement hits every client sector alike.** The win-rate penalty on a vendor under visa enforcement is the
  same in every client sector, where the specification makes it strongest in government and financial services. With
  every sector at twice today's penalty, an upper bound, the Indian vendor's 2040 headcount falls by about 26% in Visa
  crackdown; a sector split of today's average would move it far less. Base is unaffected.
- **Visa policy does not react to unemployment.** US visa tightness is a scenario input and does not respond to US IT
  unemployment. A prototype of that political feedback tightened visas further in every scenario, because onshore
  unemployment stays above its 2024 level, but no evidence sets the sign or the strength of the policy response, so
  its size is not stated here. The visa scenarios span the range of exogenous tightening instead. It limits the
  Indian vendor's headcount, the vendor Q1 lines and the onshore and India totals in visa questions.
- **Onsite visa cost does not rise with tightness.** The cost of an onsite visa worker (fees and compliance) is flat
  in visa tightness. If it rose in proportion to tightness, Visa crackdown would cut the Indian vendor's 2040
  headcount by up to about 16% more. Base is unaffected, because tightness stays at its 2024 level.

### GCC growth

- **The GCC wave is an assumption.** The rise of GCCs in India is mostly an assumed trend, fitted to GCC headcount up
  to 2026 and one outlook for 2030; since `phase9` a scale effect (R7) carries part of it. Halving the trend's end
  level, or raising it by half, without recalibration moves 2040 GCC headcount by about 34% and vendor headcount by
  about 19-21%. It limits every split of work between vendors and GCCs after 2030: GCC and vendor headcount, vendor
  revenue and the GCC work share.
- **GCC set-up has no delay of its own.** Clients see sourcing options with a general delay of 1.5 years, but a new
  GCC takes no extra set-up time, and set-up does not speed up when vendors get dearer or riskier. Doubling that
  delay, as a stand-in for a 1-2 year set-up, moves 2040 headcounts by up to about 4% (BQ's); halving it moves them by
  under 2%. It limits the timing of the shift to GCCs.

### The feedback loops

- **The loop strengths come from outside evidence, not the calibration window.** The 2024-2026 data fit equally well
  with the loops on (`phase9`, loss 0.000421) or off (`phase8`, 0.000423), so the data cannot test the strengths.
  Each base value translates case data and industry series into model units, and its uncertainty enters only as one
  of the eight structural levers.
- **The R7 cap is a design judgement.** R7's term is capped at `R7Lcap` (1.0) times `kR7`, a level with no evidence
  range; it is not needed for stability. The cap binds from about 2032 (2031.1-2033.6 by scenario and strength) and
  at base strength trims the 2040 term from 0.474 to 0.400: lifting it moves 2040 vendor headcount by -0.9%, GCC
  headcount by +1.4% and revenue by -0.9% in Base. At the high strength `kR7` 0.75, lifting it moves vendor headcount
  by -3.6% in Base and by -6.6% in GCC wave persists.
- **The Fast AI margin result rests on the AI-discount ceiling.** In Fast AI, vendor margins rise only because
  clients cannot extract more than a 30% AI discount on new contracts (`AIDiscCeil` 0.30, from current client asks of
  20-30%, not from calibration data). OIT's 2040 margin is 25% at that ceiling and 27% at 20%; at 45% the ceiling
  never binds, and the margin is 19%, the same as with no ceiling. Across 1,000 runs from mid-2026 it is 18-27%
  (p10-p90, median 23%), and the ceiling binds for some vendor by 2035 in 59% of the runs (71% by 2040).
- **Monte Carlo bands from different lever sets do not share draws.** `phase9` samples 21 levers from 2026.5 where
  the other models sample 13. A Latin hypercube over 21 levers draws the 13 shared ones differently, even with one
  seed, and re-drawing alone moves the 2040 band widths of headcount and revenue by 3-6%. To compare models, run them
  on one samples frame (`Experiment(samples=...)`), with the extra levers as columns.

### Adoption, pricing and calibration

- **Adoption speed is not in the uncertainty bands.** `p` and the `level_2024` parameters it moves cannot change
  after the perturb year. Compare `phase9` with `phase9_highadoption` instead (`A_mean` 2030: 0.904 against 0.958).
- **`PriceHorizon` sits at its fit bound of 7.** Refitting `phase9` with it fixed above 7 lowers the loss steadily
  (0.9% at 7.5, 7.6% at 12, no minimum up to 12), and every core target still passes. Headcount moves by under 0.3%
  and revenue by up to 1.5%, but the 2040 revenue-weighted effort-billed share rises from 0.297 to 0.334. The bound
  is a modelling choice, and effort-share results depend on it.
- **Missed targets.** `phase9`, like `phase8`, misses two of the pricing evidence targets of the
  [pricing research report](docs/research/ai-pricing-automation-analogues.md):
  - **The renewal step-down on annuity contracts**, about 20% (HCLTech: a deal that would have been $100M now closes
    at about $80M; Persistent: clients ask for the same work for 25-30% less). `phase9` gives 4.2% at 2030 (OIT, the
    price step on expiring MS and TM work, weighted by expiring volume). No model meets it: in the model, effort
    volume falls continuously rather than at renewal.
  - **The per-unit discount**, 25-40% within 3-5 years once a usable output proxy exists (translation, 2014-2026;
    medium confidence for the direction, low for the size in IT). `phase9` gives 21.6% at 2030 (one minus OIT's new
    fixed-price signing price), where `phase7` gives 33.4%.
- **The core 4 band.** One of the pricing checks is the OIT book price drift, the `AvgIdx_OIT` CAGR over 2026-2030.
  Its band is [-3.5%, -2%] a year. It was widened from [-3%, -2%] by an operator ruling on 2026-10-16, made after
  recon 09's results were seen. The evidence is HCLTech's 2-3% a year for its own portfolio and Kotak's 3.5% base
  case for Indian IT. `phase9` gives -2.96% a year, inside both bands; `phase9_highadoption` gives -3.23%.
- **Lever ranges were set by hand in the prototype,** with no cited evidence. `Verif` and `JuniorCut` scale with
  each model's value. `JevonsEps` is one-sided from 0, and `PriceHorizon` sits at 0.75 of its range on `phase9`.

### Labour-market timing and costs

- **The size of the post-shock rebound is not validated** (see "Temporary shocks").
- **Hire and fire together.** Under continuous openings, a unit-level can have openings and layoffs in the same
  step. `phase9` Base has no step with both. In Fast AI, onshore seniors see both after 2030, at up to 2.71% of staff
  a year. On Phase 7's values with the switch on, onshore seniors see both at up to 1.53% of staff a year in Base,
  all after 2030 (peak at 2031.75), and up to 4.05% in Fast AI (peak at 2031.375), where 21 of the 96 steps with
  both are before 2030. No calibration target sees it.
- **No notice periods.** People who quit or switch jobs leave at once, while real notice periods run 60-90 days in
  India. A stand-in that slows hiring adjustment by three months raises the rebound after Compute shock from 12% to
  14%, and lowers onshore unemployment in 2040 by about 6% (0.4 points) in that scenario; it is a proxy, not a bound.
  It limits the size and timing of rebounds after shocks.
- **No agency fees.** Recruiting agencies' share of hires and their fees are not modelled. Their 2024 cost is part of
  the vendors' observed margins, so only a change in agency use over time would matter: raising vendor costs by 2% of
  revenue without recalibration would cut 2040 vendor headcount by about 4%. It limits vendor margins and headcount
  if agency use changes.
- **No separate bench.** The model does not report staff between assignments (the bench) separately. Labour cost
  counts every head, billed or not, so costs and headcounts are unaffected.
- **AI does not shorten onboarding.** Even halving onboarding time moves 2040 headcounts by under 3%.

### Consumer budgets and AI spend

- **Agent work ignores the budget.** The work clients hand to AI agents follows their automation of business-process
  work: it does not respond to budget pressure, and agents' IT work counts as delivery productivity rather than as
  credit spend. Doubling all credit spend, an upper bound on both, moves 2040 headcounts by under 0.5% in Base and by
  up to about 3.6% (in-house IT) after a budget downturn. It limits consumer AI spend and the in-house and vendor
  split in downturn scenarios.
- **Seat savings and seat floors.** Savings on software seats do not feed the AI budget, and agentic products set no
  floor on seat counts. Reinvesting all savings, or raising seat spend by half, moves 2040 headlines by about 1% at
  most, because the IT budget ceiling rarely binds. It limits consumer seat and AI spend, not headcount.

### Contract types, outputs and start-ups

- **Insourcing is not concentrated on staff augmentation.** When clients bring work in-house, staff augmentation is
  not hit harder than other contract types. A neighbouring lever on staff augmentation's appeal moves the Indian
  vendor's 2040 headcount by 3-4%, which shows the size of contract-mix effects but does not measure this link. It
  limits the contract mix and the vendors' effort-billed share.
- **No provider split.** The model does not split spend by provider (cloud, software platforms, AI model providers),
  so the specification's secondary output on spend flowing to providers is not available. Nothing else depends on it.
- **No 'mix balances' test.** The specification's test of whether the contract mix has settled (shares changing by
  under 2 points a year before 2040) is not computed. The mix shares are reported, and the test can be applied to
  them.
- **No start-ups.** People who leave IT do not found start-ups or return through them. No existing setting bounds
  this. The stock of people who have left the field reaches about 1.6 times the IT workforce by 2040, so the effect
  on unemployment and senior supply is unknown.

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
