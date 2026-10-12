---
description: Answer a question with the model; throwaway code and charts in temp/analysis/, a findings note, nothing merged
argument-hint: <prompt-file-under-temp/prompts/>
---

Read the analysis prompt at `temp/prompts/$ARGUMENTS` (bare names resolve under `temp/prompts/`). If it does not exist, STOP and say so. Let `<name>` be the prompt file name without `.md`.

Rules:

- **Workspace.** All code, data and charts go in `temp/analysis/<name>/`, which is gitignored. Use the public functions of the `aisim` package and do not copy model code into the analysis. If the package does not yet offer what the question needs, say so, and use `tools/reference_runner.py` instead.
- **Running the model.** Ask the question through the experiment API:
  1. Find the outputs in `aisim.catalogue()` (row keys, extras and derived outputs, with units) or `aisim.keys(family=...)`, and the valid parameter ranges in `aisim.domains()`.
  2. Build an `aisim.Experiment`: a scenario from `aisim.SCENARIOS`, fixed `overrides`, sampled levers (`Uniform`, `Triangular`, `TruncNormal`, `Choice`, `Fixed`) with a `seed`, or an explicit `samples` design.
  3. Run it with `aisim.run_experiment(exp, outputs=[...])`, keeping validation on. Put the call under `if __name__ == "__main__":` (Windows starts workers by re-importing the script).
  4. Read the answer from `ExperimentResult`: `bands(key, ratio_to=2024, years=(start, end))` for percentile bands, `frame`, `long`, `ratio`, `q3` and `q3_counts`. Report `n_invalid` from `meta`.
- **Model changes.** If the question needs a change to the model itself:
  1. Create a local branch `analysis/<name>` from the current branch.
  2. Make the change and commit it there, so the analysis is reproducible.
  3. Never push it, never open a PR, never merge it.
  4. Return to the original branch at the end, and name the branch in the findings.

  If the change looks worth keeping, say so as a recommendation. Do not apply it to a feature branch.
- **Reproducibility.** Fix and record every seed, the number of runs, the scenario and lever settings, and the commit and branch the runs used. `ExperimentResult.meta` holds the experiment, seed, outputs, package versions and `NPY_DISABLE_CPU_FEATURES`: save it with the results.
- **Charts.**
  - Years on the x-axis, over the window the prompt asks for (default 2024-2040), with the history years 2024-2026 shaded.
  - For multi-run results, a median line with a 10th-90th percentile band.
  - Units on the y-axis.
  - Save each chart as PNG, with the data behind it as CSV.
- **Honesty.** State what the model cannot answer and which assumptions drive the result. Write "the model shows", never "will happen".
- **Hyphens only.** Never U+2014 or U+2013.

Deliver `temp/analysis/<name>/findings.md` with:

- the question and a short answer
- the evidence, with charts and tables referenced by file name
- the settings and seeds
- caveats
- any model change, with its branch name

Summarise it in chat.
