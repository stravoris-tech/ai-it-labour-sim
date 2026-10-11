# reference/

This directory holds the frozen Python prototype that the `aisim` package will port, and golden outputs generated
from it.

- `prototype/`: the Python prototype from the claude.ai project, exported 2026-10-10. It has `code/`, `data/` and
  `spec/`, plus its own `README.md`. Its tree hash (see `tools/hash_tree.py`) is
  `c1f5173e211a599d7a9a040b6adfc61cdc6bb93074bb2cffcdf7651f4442bf90` over 42 files.
- `goldens/`: outputs of the prototype, used by `tests/test_reference.py`.

## Rules

- Everything here is read-only. Never edit, move, reformat, lint or type-check anything under `prototype/`.
  `tests/test_reference.py` checks its tree hash against a hard-coded value.
- Goldens are regenerated only when a slice prompt says so, with `uv run python tools/generate_goldens.py`.
- `.gitattributes` marks `reference/**` as `-text`, so git stores these files byte for byte (including the CRLF line
  endings in the CSVs) and the hashes match on every platform.

## How the goldens are produced

`tools/generate_goldens.py` uses `tools/reference_runner.py`, which runs the prototype without modifying it:

- `base.json` and `ai_off.json`: one in-process base run each, 2024-2040, dt = 1/16, rows recorded every 0.25
  years, with AI on and off. Each run loads a fresh copy of `code/phase7_sim.py` (its parameter dict `P` is
  module-level and mutable), copies the calibrated parameters from `data/calib7.json` into `P` exactly as
  `code/phase7_runs.py` lines 6-11 do, and calls the prototype `run()`. Each file holds `rows`, `final_state` and
  `mins`.
- `phase7_results.json`: a byte copy of the output of the unmodified `code/phase7_runs.py` (tests, scenarios,
  tornado and a 300-run Monte Carlo seeded with `random.Random(7)`), run as a subprocess in a fresh working
  directory holding a copy of `calib7.json`.
- `MANIFEST.json`: the prototype tree hash and per-file hashes, the SHA-256 of each golden file, the Python, platform
  and uv versions, the generation time, the command and the wall time of each part.

JSON is written with `indent=1` and full float precision (Python float repr round-trips exactly).

## Known issues

Found by the slice 1 recon and deliberately not fixed here:

- `calib7.json` predates `DemandGrowthLate` and `LateYear`. The module defaults in `phase7_sim.py` (-1.0 and
  2026.5) supply them.
- `phase7_params.csv` flags 12 parameters as fitted, including `DemandGrowth`, which is set from data. The fit has 11.
- The scripts use working-directory-relative paths and a global mutable `P`.
- `phase7_runs.py` applies no pass or fail thresholds; it prints and records its test metrics and always exits 0.
- Two stock updates read values already updated in the same step: `ClientPRef` after `ClientP`, and `NewD` after
  `NewV`.
- `phase2_sim.py` writes to an absolute `/home/claude` path.
- `phase2_tests.py` and `run_tests2.py` are identical.
- The reference values in `spec/07` are rounded to 2 decimals. Full precision is in the goldens.
