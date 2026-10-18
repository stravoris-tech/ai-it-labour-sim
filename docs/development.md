# How the model was built

`ai-it-labour-sim` was built in slices, each a feature branch that went through reconnaissance, a build, an
independent conformance check and a squash merge. Every slice exited through the same gate: ruff, ruff format, mypy
strict, pytest and a dash check (`scripts/gate.py`, whose verdict is its exit code), with CI running the same gate.
This page records each slice in merge order: what it was for, its gate and test count at merge, its key decisions with
the reason for each, and what it held or deferred.

The record comes from the slices' ship reports and pull requests in the private development repository. Commit ids
refer to that repository; this public repository starts with a fresh history. The working notes it cites (prompts,
recon reports, ship reports, scratch code) lived in a gitignored `temp/` folder and are not published.

Slice 7, release preparation, was planned before slices 8 and 9 but built last, so it comes last here.

## Slice 01: scaffold (PR #1, merged 2026-10-11, `c7c11c9`)

**Purpose.** An empty but fully gated Python project, before any model code: a uv project (package `aisim`), the gate
with a positive control for the dash check, CI, the repo's commands, the licences and `CITATION.cff`, and the frozen
prototype under `reference/prototype/` with goldens generated from it and tests that reproduce them.

**Gate at merge.** Exit 0, 9 tests (0 before), plus 1 slow test; CI success. The goldens reproduced with a maximum
relative difference of 0.0 on the generating machine, and within 1e-9 on Linux x86-64.

**Key decisions.**
- Build backend `uv_build`, with module name `aisim`: the import name differs from the distribution name.
- No bytecode is ever written into the frozen prototype tree: its tree hash counts every file.
- The goldens are written with `\n` line endings: Windows text mode would make them differ by platform.
- The gate deletes any old JUnit file before it runs: a test count can never come from a previous run.
- The global `/run-slice` .NET gate was not applied; the Python gate is the full gate: the repo has no .NET build.

**Held or deferred.** Making `gate` a required check on `main` was left to the operator. Pinning uv in CI was settled
in slice 02.

## Slice 02: port (PR #2, merged 2026-10-11, `cf0ecdf`)

**Purpose.** Port the Phase 7 prototype into `aisim` as a readable scalar engine that reproduces the prototype bit for
bit. It became the reference (oracle) for the batched engine.

**Gate at merge.** Exit 0, 68 tests (9 before); the slow suite passed; CI success. Parity with the prototype: maximum
relative difference 0.0 in all 23 cases, with a one-ulp positive control (a one-ulp nudge of `AICost2024` shows up).
The port runs at 1.05 times the prototype's time.

**Key decisions.**
- Parameters are stored as floats, and the 2024 state is copied as is: the conversions are exact.
- The S13c sector loop is split into consumer and sourcing parts (a new trace ID, S13d): the halves share no
  accumulator, so no float can change.
- No cache: the baseline file is read on every call, keeping to "no module-level mutable parameter state" at about
  1 ms a call.
- `DemandGrowthLate is None` means "same as `DemandGrowth`", and a ramp whose start equals its end is a step:
  neither changes any parity result.
- CI pins uv 0.12.23, and the golden tolerance tightened from 1e-9 to 1e-12.

**Held or deferred.** Range validation for `DemandGrowthLate` (values of -0.5 or below now mean real negative growth,
unlike the prototype) and an explicit overrides argument for `run()` were left to later slices.

## Slice 03: batched engine (PR #3, merged 2026-10-11, `a7e825a`)

**Purpose.** `aisim.batch`, a numpy engine whose `run_batch()` advances N runs together as arrays with a leading run
axis, checked against the scalar engine at 1e-12.

**Gate at merge.** Exit 0, 98 tests (68 before); CI success. The measured difference from the scalar engine was 0.0
in all 29 end-to-end comparisons and in 1,393,968 intermediate values. Speed: 1,000 runs in 4.3 s (232 runs a second),
against 4.4 runs a second for the scalar engine.

**Key decisions.**
- Compensated summation at every scalar `sum()` site: with naive sums AI costs missed by up to 1.7e-7, because a
  productivity of 1 plus or minus 1 ulp is amplified about 1e9.
- Every power gets a full-shape contiguous exponent: numpy's fast paths otherwise depend on the exponent's form and on
  N.
- `finite` marks a run False on a non-finite state, at the known fault sites, or on non-positive parameter-only
  denominators checked once before the loop (operator ruling).
- numpy became the only runtime dependency.

**Held or deferred.** The 300 runs a second target was missed. Zero denominators that arise from the state are not
flagged; input validation was expected to cover the parameter side.

## Slice 03b: CI numerics (PR #4, merged 2026-10-11, `143046c`)

**Purpose.** On x86-64 CI runners with AVX-512, numpy sends float64 `np.power` and `np.log` to SIMD kernels that
differ from the C library by 1 ulp, which broke batch-scalar parity at 1e-12. This slice pins the kernels with
`NPY_DISABLE_CPU_FEATURES` and adds a guard that fails at once and explains why.

**Gate at merge.** Exit 0, 103 tests (98 before); CI success on all four attempts, three of them on AVX-512 runners.

**Key decisions.**
- The feature list is fixed at `X86_V4 AVX512_ICL AVX512_SPR`: numpy 2.5 names plain AVX-512 `X86_V4`, so a rule
  built from the `AVX512` names missed it, and runners without AVX-512 already match the C library.
- The guard prints numpy's current `__cpu_dispatch__` beside the setting: a renamed target shows itself.
- Mismatching inputs found by the probe are kept as fixed regression points for the guard.
- The setting is for x86-64 numpy builds only, never ARM64 or macOS.
- No extra tooling watches numpy upgrades: the lock file pins numpy, so upgrades are deliberate, and the guard prints
  new target names.

**Held or deferred.** A CI proof run of the guard firing was declined: the probe jobs had already shown parity
failing on real AVX-512 runners.

## Slice 04: experiment API (PR #5, merged 2026-10-12, `20615ad`)

**Purpose.** `aisim.Experiment` and `run_experiment` over the batched engine, the layer for asking the model
questions with many runs: validation into one `ValidationError`, sampling (five distributions, Latin hypercube,
Iman-Conover correlation), results as arrays with pandas views, derived outputs and extras, and the `domains.csv` and
`catalogue.csv` package data.

**Gate at merge.** Exit 0, 191 tests (103 before); the slow suite passed; CI success; the conformance check found it
ship-safe.

**Key decisions.**
- The Phase 7 acceptance test is split into API checks, bit-equal on every platform, and golden checks, bit for bit on
  the goldens' own platform and at 1e-12 elsewhere: the goldens were made on Windows ARM64, and CI's Linux libm can
  round differently. "Goldens are platform-bound" became a convention.
- Results are bit-identical whatever the worker count and chunk size (tested for 1 and 4 workers, chunks of 7 and
  500 runs).
- A seed is required whenever levers are sampled: no hidden randomness.
- The calibration identity checks hold at their calibrated residuals: the shipped calibration is rounded, so a plain
  1e-9 check would fail the baseline.
- `validate()` reports support errors together with every other check that does not depend on the draws, in one
  `ValidationError` (a finding of the conformance check).
- scipy is imported lazily: otherwise every spawned worker would pay its import time.

**Held or deferred.** The book value in USD went to the slice 8 backlog; the calibration's rounded values were kept for
prototype parity.

## Slice 05: charts and reports (PR #6, merged 2026-10-12, `b0ebcda`)

**Purpose.** A charts and report layer over experiment results (`aisim.charts`: `bands`, `scenarios`, `lines`,
`drivers` and `save`; `aisim.report.Report`), plus the experiment API fixes that the Q01 and Q02 analyses had to work
around. The model did not change.

**Gate at merge.** Exit 0, 256 tests (191 before); the slow suite passed; CI success on both commits; the conformance
check found it ship-safe.

**Key decisions.**
- `run_scenarios` runs scenarios on the same draws, and an override of a parameter a requested scenario sets is an
  error there.
- Okabe-Ito colours, with yellow last: yellow has low contrast as a line.
- Saved charts fix their layout on first save: constrained layout did not converge, and repeat saves differed.
- Reports prefix every SVG id per chart: ids repeated across and within charts.
- The overlay shares y-limits only when its keys share a unit: forced sharing drew a share as a flat line beside a
  headcount.
- CI runs on `ubuntu-24.04`, not `ubuntu-latest`: a new glibc can move cross-platform golden checks.

**Held or deferred.** Keeping the state in `run_scenarios` was left out for now.

## Slice 06: perturb from year Y and process noise (PR #7, merged 2026-10-12, `1285920`)

**Purpose.** `Experiment.perturb_from = Y`: the calibrated baseline runs unchanged from 2024 to Y once, and every run
restarts at Y with its own parameters, so everything that differs acts from Y. Plus optional process noise: exact
Ornstein-Uhlenbeck factors on six channels, off by default, with a seeded stream per run.

**Gate at merge.** Exit 0, 307 tests (256 before); 11 slow tests passed; the goldens stayed bit-exact; CI success on
all three commits; the conformance check found it ship-safe.

**Key decisions.**
- A two-phase run: phase 1 runs once and is tiled, and phase 2 restarts from its state at Y. The row at Y is phase
  2's, because the run's parameters act at Y.
- The five 2024-anchored paths continue from their base value at Y, but only for a run whose rates differ from the
  base, chosen per run on two complete results: unchanged runs stay bit-identical.
- Parameters that describe 2024 itself are flagged `level_2024` and cannot change after 2024 (validation).
- A rate whose path is anchored at 2024 and not re-anchored (`DemandGrowth`, `ITBudgetGrowth`, `amax`) is rejected
  after 2024: changing it would make the path jump at Y.
- `tornado_levers(perturb_from)` drops every lever whose range fails validation at that Y: 14, 13 or 12 levers.
- No noise amplitude is built in.

**Held or deferred.** Re-anchoring the three anchored rates was deferred.

## Slice 08: model selector, pricing term and calibration tool (PR #8, merged 2026-10-16, `87dbf05`)

**Purpose.** The slice set out to build a phase 8 contract pricing model. By operator ruling it shipped only the
groundwork: the model selector with one registry (`aisim.state.BASELINE_FILES`), the annuity pricing term at neutral
defaults, new-signing price extras, the calibration tool `tools/calibrate.py` and `tools/build_model.py`.

**Gate at merge.** Exit 0, 338 tests (307 before), 12 slow deselected; the slow suite passed; CI success.

**Key decisions.**
- Ship the groundwork without a phase 8 model: the build held at its stop check (loss 0.0010397 against a 0.0010
  limit, the OIT book price drift at -3.64% a year outside its band, and `PriceHorizon` ending on its bound of 7).
- One registry, read at call time: no module keeps its own list of models.
- Parameters the prototype does not have live in code at neutral defaults, not in the prototype's baseline file,
  whose bytes stay the prototype's.
- The calibration tool reproduces the prototype's fit, with 4-decimal rounding: the prototype stores its fitted
  values rounded to 4 decimals.

**Held or deferred.** The phase 8 model, its goldens, its tornado lever set and chart labels; a full multi-start
refit and the junior-hiring discontinuity went to the calibration slice.

## Slice 09: phase 8 model and robust calibration (PR #9, merged 2026-10-17, `207b290`)

**Purpose.** Ship the phase 8 model: continuous openings as the extension switch `OpeningsContinuous` (0 runs Phase 7
bit for bit), multi-start calibration, and two models built from a spec and a fit, `phase8` and
`phase8_highadoption`.

**Gate at merge.** Exit 0, 412 tests (338 before), 12 slow deselected; the slow suite passed; CI success on the second
commit.

**Key decisions.**
- `phase8`: a 32-start fit (tolerance 1e-10, seed 20261016) with `PriceHorizon` at most 7. `phase8_highadoption`:
  `p` fixed at Phase 7's 0.044, from 8 Latin hypercube starts plus a warm start.
- The OIT book price drift band was widened to [-3.5%, -2%] a year (operator ruling of 2026-10-16).
- The committed tool reproduces both fits bit for bit, every start included.
- `build_model.py` derives `AdoptC0` from the fitted values: slice 8's tool had kept Phase 7's stored value, so the
  baseline was not the fitted model.
- Fit and golden checks are platform-aware: bit-exact on the goldens' platform; off it, at the golden tolerance,
  with values that should be 0 compared at 1e-6 absolute (CI on Linux x86-64 failed the bit-exact checks made on
  Windows ARM64).

**Held or deferred.** The tornado ranges were not re-centred for phase 8 (done in slice 7). `phase8` misses the
per-unit discount and renewal step-down targets. In Fast AI, onshore seniors hire and lay off together after 2030
(documented, not resolved). The library default stayed `phase7`, for the public release slice.

## Slice 07: release preparation (built last)

**Purpose.** Prepare the public release: `phase8` as the library default, with tornado ranges computed per model;
chart colours that stay distinct beyond eight series; the source citations in `domains.csv` re-anchored and guarded
by a gate test and a tool; an exhaustive licence split; and these docs.

**Gate at the build.** Exit 0, 477 tests (412 before), 12 slow deselected. With `phase7` named, every Phase 7
parity, golden and experiment test passes with no expected value changed; only the `mc` part of the phase 8
Monte Carlo golden was regenerated, because its levers moved.

**Key decisions.**
- One constant, `aisim.state.DEFAULT_MODEL = "phase8"`, named by every library default and unknown-model fallback;
  `tools/calibrate.py --model` stays `phase7`, because a phase 8 fit is Phase 7 plus fixes.
- `tornado_levers(model=)` sets the `Verif` and `JuniorCut` ranges from that model's values at the prototype's ratios;
  `TORNADO` stays the Phase 7 tornado, so Phase 7 results stay bit-identical when `phase7` is named.
- The palette grows to 10 colours, and colours repeat with dashed and then dotted lines, so up to 30 series stay
  distinct; each of the 15 scenario labels has its own colour and line style.
- Each citation's text is stored beside `domains.csv` (`tests/data/domains_cites.json`); `tools/cites.py --check`
  fails on a stale cite and `--fix` re-anchors one only by a unique exact match, never by guessing.
- Code is MIT and documentation and data CC BY 4.0, with `pyproject.toml` declaring `MIT AND CC-BY-4.0`.

**Held or deferred.**
- Making the repository public, Zenodo and the release are operator steps after the merge.
- 247 citations with aptness not verified by `tools/cites.py --apt` (mostly multi-suffix names); a later pass could
  teach `--apt` those names.

## Slice 12: the phase 9 model, four feedback loops from outside evidence (PR #11, merged 2026-10-18, `9d7eee4`)

**Basis.** Recon 11 (the gap review: the loops the specification names but the engine leaves open, and prototypes
showing the calibration data constrain none of their strengths), recon 12 (the four loops in their evidence forms,
a joint refit and the structural uncertainty) and recon 12b (the settled forms: R7 on the economy-wide GCC work
share, R10 on total voluntary exits, client flight with a fade; the proof battery and the refits). The evidence is
[`research/loop-strength-evidence.md`](research/loop-strength-evidence.md).

**Purpose.** Close R7, R6, R10 and R4 as extension parameters in both engines, off by default, and register `phase9`:
`phase8` with every loop at its evidence base value and a full 32-start refit. The library default stays `phase8`.
The design note is [`model-changes-phase9.md`](model-changes-phase9.md).

**Gate at the build.** Exit 0, 519 tests (477 before), 12 slow deselected; the slow suite passed. With every loop off,
the 27 parity cases are bit-identical to `main` in both engines, and every existing baseline file and golden is
unchanged.

**Key decisions.**
- The six loop references and signals are state families, filled on the first step or started from their 2024
  values, so a restart at Y is exact; `mins` gain nothing.
- Client flight uses the 2-year fade alone (`kViab` 5.8562 / 10.6511); the cap stays as `C4Cap`, off. R7's high is
  0.75, inside the evidence's stability rule.
- `tools/build_model.py` writes the three earlier extension keys always and a later one only when the spec or fit
  names it, so the phase 8 baseline files stay byte-identical.
- Structural levers are per model (`aisim.scenarios.STRUCTURAL_LEVERS`): `tornado_levers(model="phase9")` adds the
  eight loop strengths; every other model's levers are unchanged.
- Four loop extras (`Vrel_<v>`, `ClientFlight_<v>`, `GCCScaleTerm`, `VoluntaryAttrition_<v>`) are recorded for every
  model.

**Held or deferred.** The default flip, after a first-look analysis (Q05). B8 stays a scenario input. Re-anchoring the
2024-anchored rates under `perturb_from` is still deferred. Line references in catalogue.csv descriptions and the
scalar/record.py docstring that the new code moved; to be removed with slice 10 (model documentation), as its plan
already intends.

## Slice 13: phase 9 completion

**Basis.** Recon 13 (the R7 cap's role and stakes, the Fast AI price-rule result, a trial `phase9_highadoption`, the
stress set's placement, and the small fixes), the Q05 first look at `phase9` (loop activity, the stress set, persistent
client flight) and recon 13g (recon 11's gaps checked against `phase9`: no Build candidate, so every open row is
documented, not built).

**Purpose.** Finish `phase9` before the default changes: the small fixes Q05 found, recorded outputs for when the price
rules bind and for R4's multiplier, the like-for-like adoption alternative `phase9_highadoption`, the Q05 stress set
in code, and the documentation of the R7 cap and of the Fast AI price-rule result. The library default stays `phase8`.

**Gate at the build.** Exit 0, 562 tests (519 before), 12 slow deselected; the slow suite passed. The 27 parity
cases are bit-identical to `main` in both engines (rows, the 43 families, mins), and every existing baseline file and
golden is unchanged.

**Key decisions.**
- The R7 cap stays at 1.0 and is documented: a design judgement with no evidence range, not a stability device in
  the log form, binding from about 2032 and worth about 1% on the 2040 headlines at base strength.
- Three extras families, 24 keys: `PriceFloorBinds_<v>_<k>` (C5, by vendor and type, the shape of `PNew_<v>_<k>`),
  `AIDiscCeilBinds_<v>` (C6) and `SkillErosionMult_<r>_<l>` (R4). Each reads a value the step already computes; R4's
  multiplier was split out of the seeker exit with the same operations in the same order.
- `phase9_highadoption` uses `phase9`'s fit settings with `p` fixed at 0.044, and passed a STOP check set in advance,
  including a like-for-like test: its adoption effect is within 1 point of `phase8_highadoption`'s on the four
  headlines.
- The stress set is `STRESS_SCENARIOS`, outside `SCENARIOS` (the `EXTREME` precedent), so no scenario count or
  golden moves; `run_experiment` and `run_scenarios` accept its names, and it has its own chart colour.
- A perturbed run that records no row after Y now raises a clear `ValueError` in `execute`, with or without
  validation, instead of a bare `KeyError`.
- `drivers` labels the structural levers from `STRUCTURAL_LEVERS`.

**Held or deferred.** The default flip to `phase9`, the README story and the limitations, for slice 14.
`run_batch_from` called directly still returns an empty series when phase 2 records no row.

## Analyses

Four analyses were asked of the model during development, each in a throwaway workspace with nothing merged:

- [Q01](analyses/q01-contract-mix.md): how the vendors' contract book shifts between contract types, 2024-2032
  (`phase7`).
- [Q02](analyses/q02-contract-mix-diagnosis.md): why the contract mix moves the way it does, a diagnosis of Q01
  (`phase7`).
- [Q03](analyses/q03-phase8-first-look.md): a first look at the phase 8 model.
- [Q04](analyses/q04-shock-overshoot.md): why headcount overshoots Base after the temporary shocks.
