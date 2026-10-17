---
description: Answer a question with the model; throwaway code and charts in temp/analysis/, a findings note, nothing merged
argument-hint: <prompt-file-under-temp/prompts/>
---

Read the analysis prompt at `temp/prompts/$ARGUMENTS` (bare names resolve under `temp/prompts/`). If it does not exist, STOP and say so. Let `<name>` be the prompt file name without `.md`.

Rules:

- **Workspace.** All code, data and charts go in `temp/analysis/<name>/`, which is gitignored. Use the public functions of the `aisim` package and do not copy model code into the analysis. If the package does not yet offer what the question needs, say so, and use `tools/reference_runner.py` instead.
- **Running the model.** Ask the question through the experiment API:
  1. Find the outputs in `aisim.catalogue()` (row keys, extras and derived outputs, with units) or `aisim.keys(family=..., vendor=..., type=...)` (`aisim.experiment.dims(key)` parses a key's dimensions), and the valid parameter ranges in `aisim.domains()`.
  2. Build an `aisim.Experiment` with `model="phase8"` (README "Models"; it is the library default, but set it explicitly and record it): a scenario from `aisim.SCENARIOS`, fixed `overrides`, sampled levers (`Uniform`, `Triangular`, `TruncNormal`, `Choice`, `Fixed`) with a `seed`, or an explicit `samples` design. A scenario plus a sampled lever it sets is an error.
  3. Set `perturb_from=2026.5` by default, so the calibrated baseline runs unchanged until mid-2026 and the levers act from there; leave it unset only when the question needs levers acting from 2024, and say why. A Monte Carlo over the tornado levers samples `aisim.scenarios.tornado_levers(perturb_from=..., model="phase8")` (the set depends on Y: 13 levers at 2026.5, without the 2024 level `Verif`; 12 at 2027, without `DemandGrowthLate` too). Use `noise` only when the question is about volatility, with each channel's `sigma` and `tau` stated and justified (README "Process noise"); never as a default.
     - **Adoption-sensitive questions** (anything that depends on the AI adoption path after 2026: adoption, productivity, hours, headcount, revenue, the `AvgIdx` drift) run on both `phase8` and `phase8_highadoption` with the same draws and report both. They differ in adoption speed (`A_mean` 2030 0.904 against 0.957). Compare the models; do not sample `p`, which with the 2024 levels it moves cannot change under `perturb_from`.
     - **Pricing questions** may override or sample `AnnuityShare` (0.2-0.5), `AnnuityAnchorW` (0.3-0.5) and `PassThrough` (0.7-0.8) (README "Models"). These are evidence ranges from the slice 8 research report (`docs/research/ai-pricing-automation-analogues.md`). The levers are now calibrated in phase 8, at `AnnuityShare` 0.3, `AnnuityAnchorW` 0.4 and `PassThrough` 0.75: a sample over the ranges is a sensitivity around the calibrated values, and the findings say so. Under `perturb_from` they act from Y.
  4. Run it with `aisim.run_experiment(exp, outputs=[...])`, keeping validation on and the default (auto) chunking. To compare scenarios, use `aisim.run_scenarios(exp, [None, "Slow AI", ...], outputs=[...])`: one batch, the same draws for every scenario, with the levers a scenario sets pinned per block (`ScenarioResult.pinned`; say so in the findings). Put the call under `if __name__ == "__main__":` (Windows starts workers by re-importing the script).
  5. Read the answer from `ExperimentResult`: `bands(key or (N, T) array, ratio_to=2024, years=(start, end))` for percentile bands, `single(key)` for a one-run result, `frame`, `long`, `ratio`, `q3` and `q3_counts`. Use `aisim.experiment.drivers(result, targets, year)` for lever drivers and `shift_share` for a weighted average's change. Report `n_invalid` from `meta`.
- **Model changes.** If the question needs a change to the model itself:
  1. Create a local branch `analysis/<name>` from the current branch.
  2. Make the change and commit it there, so the analysis is reproducible.
  3. Never push it, never open a PR, never merge it.
  4. Return to the original branch at the end, and name the branch in the findings.

  If the change looks worth keeping, say so as a recommendation. Do not apply it to a feature branch.
- **Reproducibility.** Fix and record every seed (and the `noise_seed`, `perturb_from` and noise spec), the number of runs, the scenario and lever settings, and the commit and branch the runs used. `ExperimentResult.meta` is JSON-safe and holds the experiment, seed, outputs, package versions, `NPY_DISABLE_CPU_FEATURES`, `git_commit`, `git_dirty` and the platform: save it with the results (`json.dumps(result.meta)`, or `result.save(path)`).
- **Charts.** Use `aisim.charts`, not hand-written matplotlib:
  - `charts.bands` (median and p10-p90 band, `baseline=` for the dashed one-run line), `charts.scenarios` (small multiples or `layout="overlay"`), `charts.lines` (one-run results or a sweep with `x=`) and `charts.drivers`; save with `charts.save`.
  - Years on the x-axis, over the window the prompt asks for (`window=`, default 2024-2040). With `perturb_from` the charts shade 2024 to Y as "calibrated baseline until <Y>"; without it, 2024-2026 as the "calibration period 2024-2026" (never "history": levers act from 2024, so the runs already disagree there).
  - Units on the y-axis come from the catalogue; colours are fixed per dimension value and scenario.
  - Save each chart as PNG, with the data behind it as CSV.
- **Report.** Build the charts, tables (`add_table`) and settings (`add_settings(result)`) into an `aisim.report.Report` and write `report.html` next to the findings. Use `aisim.report.to_markdown_table(df)` for tables in `findings.md`.
- **Honesty.** State what the model cannot answer and which assumptions drive the result. Write "the model shows", never "will happen".
- **Calibration caveat.** When a result depends on the AI adoption path after 2026, state that the 2024-2026 data identify the early adoption path but not its speed after 2026, which is why the result is shown on both `phase8` and `phase8_highadoption` (README "Models"). A result on `phase7` also carries Phase 7's caveat: its optimiser stalled on a junior-hiring discontinuity that phase 8 removes.
- **Hyphens only.** Never U+2014 or U+2013.

Deliver `temp/analysis/<name>/findings.md`, plus `temp/analysis/<name>/report.html`, with:

- the question and a short answer
- the evidence, with charts and tables referenced by file name
- the settings and seeds
- caveats
- any model change, with its branch name

Summarise it in chat.
