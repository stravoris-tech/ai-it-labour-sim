# AI and the IT Job Market - SD model: project files

System Dynamics model (built in AnyLogic, prototyped in Python) of AI's impact on IT employment, contracts and vendor viability, 2024-2040, for India and onshore. The live spec with charts is the Claude Docs artifact "AI and the IT Job Market - SD Model Spec"; the `spec/` files here are markdown exports of its tabs (charts appear as placeholders).

## spec/ (exported 2026-10-10)

| File | Content |
|---|---|
| 00_model_spec.md | Model spec: questions Q1-Q3, modules, loops, equations, build plan, change log |
| 01-07_*_build_guide.md | Step-by-step AnyLogic build guides with equations, parameters, tests and reference results for Phases 1, 2, 3, 4, 5, 6a, 6b and 7 |
| 08_sources.md | Every external source consulted (133 links), grouped by fit, validation, scenarios, context and spec citations |

## code/ (Python prototypes, Euler, dt = 1/16 yr)

Each phase has a model (`phaseN_sim.py`), a calibration of its 2024 starting state (`calibrateN.py`) and a test runner (`phaseN_tests.py`) that writes `phaseN_results.json`. Calibrations chain: each phase seeds from the previous phase's results file.

| Phase | Files | Reads |
|---|---|---|
| 1 Core loop | phase1_sim.py | - |
| 2 Labour market | phase2_sim.py, calibrate2.py, phase2_tests.py, run_tests2.py | - |
| 3 Regions, GCC, visas | phase3_sim.py, calibrate3.py, phase3_tests.py | - |
| 4 Vendor finance | phase4_sim.py, calibrate4.py, phase4_tests.py, scan4.py | phase3_results.json |
| 5 Contracts, sourcing | phase5_sim.py, calibrate5.py, phase5_tests.py, scan5.py | phase4_results.json |
| 6a Demand side | phase6a_sim.py, calibrate6a.py, phase6a_tests.py | phase5_results.json |
| 6b Supply side | phase6b_sim.py, calibrate6b.py, phase6b_tests.py | phase6a_results.json |
| 7 Calibration, scenarios | phase7_sim.py, calibrate7_ss.py (2024 growth-path state), calibrate7.py (2024-2026 fit, writes calib7.json), phase7_runs.py (tests, 14 scenarios, tornado, 300-run Monte Carlo, writes phase7_results.json) | phase6a_results.json, calib7.json |

To rebuild everything from scratch, run the tests scripts in phase order (2, 3, 4, 5, 6a, 6b), then `calibrate7.py`, then `phase7_runs.py`. The large `phaseN_results.json` outputs (0.4-6 MB each) are not stored in the project because they regenerate in seconds to minutes.

## data/

| File | Content |
|---|---|
| calib7.json | Phase 7 calibrated parameters, 2024 starting state, fit targets with sources, validation |
| phase7_init.csv | Every stock's 2024 starting value by index, for loading into AnyLogic |
| phase7_params.csv | Every Phase 7 parameter value, with the eleven fitted ones flagged |
| phase2_eq.json, phase1_results.json | Small Phase 1-2 reference outputs |
