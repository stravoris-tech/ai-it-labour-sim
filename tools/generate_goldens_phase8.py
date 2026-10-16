"""Generate the goldens of the phase 8 models in ``tests/data/goldens/<model>/`` with the scalar engine (the oracle).

There is no prototype for phase 8, so the port's scalar engine (``aisim.run``) is the reference, and these goldens pin
it; the batched engine is checked against them and against live scalar runs. For each model in ``MODELS``:

- ``base.json`` and ``ai_off.json``: rows every quarter year, the final state and the mins, as
  ``reference/goldens/base.json``;
- for ``phase8`` only, ``results.json``: the 14 ``SCENARIOS`` (annual rows of ``KEEP``, Q3 outcomes and the stocks
  below -1e-6, as ``phase7_results.json``) and a 300-run Monte Carlo with the Phase 7 MC's method
  (``phase7_runs.py:136-160``): ``random.Random(7)``, ``rng.uniform(lo, hi)`` over the model's tornado levers
  (``tornado_levers(model=...)``) in their order, annual runs, bands of the ratio to 2024 at 0.1, 0.5 and 0.9 by the
  prototype's ``pct``, and the Q3 counts;
- ``MANIFEST.json``: the environment, the command, the git commit (the tree the goldens were generated from), the
  hash of each golden file and of the model's baseline file, and the wall time of each part.

Run only when a slice prompt says so: ``uv run python tools/generate_goldens_phase8.py``
"""

from __future__ import annotations

import datetime as dt
import math
import platform
import random
import sys
import time
from pathlib import Path
from typing import Any, Final

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim import Params, run
from aisim.dims import TYPES, VENDORS
from aisim.experiment.meta import provenance
from aisim.scalar.engine import RunResult
from aisim.scenarios import SCENARIOS, tornado_levers
from aisim.state import BASELINE_FILES
from tools.generate_goldens import uv_version, write_json
from tools.hash_tree import sha256_file

ROOT: Final = Path(__file__).resolve().parent.parent
GOLDENS: Final = ROOT / "tests" / "data" / "goldens"
COMMAND: Final = "uv run python tools/generate_goldens_phase8.py"
MODELS: Final = ("phase8", "phase8_highadoption")
MC_MODEL: Final = "phase8"
N_MC: Final = 300
YEARS: Final = tuple(range(2024, 2041))
QS: Final = (0.1, 0.5, 0.9)

Q1: Final = ("Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia")
OUTS: Final = ("HeadTotal", *Q1)
"""The Monte Carlo outputs (``phase7_runs.py`` ``outs``)."""
KEEP: Final = (
    *Q1,
    "HeadTotal",
    "VendorHead",
    "Demand",
    "P_all",
    "A_mean",
    "AC_mean",
    "Unemp_IN",
    "Unemp_ON",
    "RevenueTot",
    "Head_IH",
    "Head_GCC",
    "Head_OIT",
    "Head_GSI",
    "Head_BQ",
    "WorkShare_IH",
    "WorkShare_GCC",
    "WorkShare_OIT",
    "WorkShare_GSI",
    "WorkShare_BQ",
    "Margin_OIT",
    "Margin_GSI",
    "Margin_BQ",
    "Revenue_OIT",
    "Revenue_GSI",
    "Revenue_BQ",
    "Vi_OIT",
    "Vi_GSI",
    "Vi_BQ",
    "AvgIdx_OIT",
    "LOB",
    "HireJ_IN",
    "HireJ_ON",
    "G",
    "HeadLoc_IN",
    "HeadLoc_ON",
    "EffortShare_OIT",
    "EffortShare_GSI",
    "EffortShare_BQ",
    *(f"Mix_{v}_{k}" for v in VENDORS for k in TYPES),
)
"""The row keys a scenario's annual rows keep (``phase7_runs.py:49-53`` ``KEEP``)."""

Ann = dict[int, dict[str, float]]


def annual(rows: list[dict[str, float]]) -> Ann:  # phase7_runs.py:61-62
    return {round(r["year"]): r for r in rows if abs(r["year"] - round(r["year"])) < 1e-6}


def q3(ann: Ann, v: str) -> str:  # phase7_runs.py:65-76, verbatim
    """Spec outcome test over 2038-2040: collapse, new equilibrium or still adjusting."""
    neg_run, best = 0, 0
    for yv in range(2024, 2041):
        neg_run = neg_run + 1 if ann[yv]["Vi_" + v] < 0 else 0
        best = max(best, neg_run)
    fall = max(1 - ann[yv]["Head_" + v] / max(ann[yv - 1]["Head_" + v], 1e-9) for yv in (2039, 2040))
    if best >= 3 and fall > 0.15:
        return "collapse"
    ch = max(
        abs(ann[yv][k] / max(ann[yv - 1][k], 1e-9) - 1) for yv in (2039, 2040) for k in ("Head_" + v, "Revenue_" + v)
    )
    return "equilibrium" if ch < 0.02 else f"adjusting ({ch * 100:.1f}%/yr)"


def pct(xs: list[float], q: float) -> float:  # phase7_runs.py:151-153, verbatim
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    f = math.floor(i)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (i - f)


def as_golden(result: RunResult) -> dict[str, Any]:
    """Name the parts of a run result as the goldens do. ``Any``: JSON-ready values."""
    return {"rows": result.rows, "final_state": dict(result.final_state), "mins": result.mins}


def mc_levers(model: str = MC_MODEL) -> list[tuple[str, float, float]]:
    """The Monte Carlo's levers in draw order: the model's tornado levers from 2024."""
    return [(name, u.lo, u.hi) for name, u in tornado_levers(model=model).items()]


def mc_draws(model: str = MC_MODEL) -> list[dict[str, float]]:
    """The 300 Monte Carlo samples, drawn as ``phase7_runs.py:139-143`` draws them."""
    rng = random.Random(7)
    levers = mc_levers(model)
    return [{p: rng.uniform(lo, hi) for p, lo, hi in levers} for _ in range(N_MC)]


def scenarios(model: str) -> dict[str, Any]:
    """Each scenario's annual ``KEEP`` rows, Q3 outcomes and stocks below -1e-6 (``phase7_runs.py:114-119``)."""
    base = Params.baseline(model)
    out = {}
    for name, over in SCENARIOS.items():
        res = run(base.with_overrides(**over), record_every=1.0)
        ann = annual(res.rows)
        out[name] = {
            "over": dict(over),
            "ann": {yv: {k: ann[yv][k] for k in KEEP} for yv in ann},
            "q3": {v: q3(ann, v) for v in VENDORS},
            "neg": [k for k, v in res.mins.items() if v < -1e-6],
        }
    return out


def monte_carlo(model: str) -> dict[str, Any]:
    """The 300-run Monte Carlo (``phase7_runs.py:136-160``) on the scalar engine."""
    base = Params.baseline(model)
    traj: dict[str, list[list[float]]] = {k: [] for k in OUTS}
    q3count: dict[str, dict[str, int]] = {v: {} for v in VENDORS}
    for over in mc_draws(model):
        ann = annual(run(base.with_overrides(**over), record_every=1.0).rows)
        for k in OUTS:
            traj[k].append([ann[yv][k] / ann[2024][k] for yv in YEARS])
        for v in VENDORS:
            o = q3(ann, v).split(" ")[0]
            q3count[v][o] = q3count[v].get(o, 0) + 1
    return {
        "N": N_MC,
        "years": list(YEARS),
        "levers": [list(lever) for lever in mc_levers(model)],
        "q3": q3count,
        "bands": {k: {q: [pct([t[j] for t in traj[k]], q) for j in range(len(YEARS))] for q in QS} for k in OUTS},
    }


def main() -> int:
    """Generate every golden file and the manifest of each model."""
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    prov = provenance()
    for model in MODELS:
        folder = GOLDENS / model
        folder.mkdir(parents=True, exist_ok=True)
        wall: dict[str, float] = {}
        names = ["base.json", "ai_off.json"]
        for name, ai_on in (("base", True), ("ai_off", False)):
            t0 = time.perf_counter()
            write_json(folder / f"{name}.json", as_golden(run(Params.baseline(model), ai_on=ai_on, record_every=0.25)))
            wall[name] = round(time.perf_counter() - t0, 3)
        if model == MC_MODEL:
            t0 = time.perf_counter()
            write_json(folder / "results.json", {"scenarios": scenarios(model), "mc": monte_carlo(model)})
            wall["results"] = round(time.perf_counter() - t0, 3)
            names.append("results.json")
        baseline = Path(str(BASELINE_FILES[model]))
        manifest = {
            "model": model,
            "baseline": {"path": baseline.relative_to(ROOT).as_posix(), "sha256": sha256_file(baseline)},
            "goldens": {name: sha256_file(folder / name) for name in names},
            "environment": {
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "platform": platform.platform(),
                "machine": platform.machine(),
                "uv_version": uv_version(),
            },
            "generated_utc": started,
            "command": COMMAND,
            "git_commit": prov["git_commit"],
            "git_dirty": prov["git_dirty"],
            "wall_time_s": wall,
        }
        write_json(folder / "MANIFEST.json", manifest)
        print(f"wrote {folder.relative_to(ROOT).as_posix()}: {', '.join(names)}, MANIFEST.json ({wall})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
