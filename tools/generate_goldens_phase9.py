"""Generate the goldens of a phase 9 model in ``tests/data/goldens/<model>/`` with the scalar engine (the oracle).

As ``tools/generate_goldens_phase8.py``, whose functions it reuses, for one model of ``MODELS``: ``phase9`` (slice 12,
the default) or ``phase9_highadoption`` (slice 13), named as the one argument:

- ``base.json`` and ``ai_off.json``: rows every quarter year, the final state (the 43 families, the six loop families
  included) and the mins;
- ``results.json``: the 14 ``SCENARIOS`` and a 300-run Monte Carlo with the Phase 7 MC's seed and method
  (``random.Random(7)``, ``rng.uniform(lo, hi)`` over ``tornado_levers(model=...)`` in its order: the 14 tornado
  levers, then the eight structural levers of ``aisim.scenarios.STRUCTURAL_LEVERS``);
- ``MANIFEST.json``: the environment, the command, the git commit, the hash of each golden file and of the baseline
  file, and the wall time of each part.

It is a separate script so that generating phase 9's goldens never rewrites the phase 8 goldens or their manifests,
and one run writes one model's folder only. Run only when a slice prompt says so:
``uv run python tools/generate_goldens_phase9.py [phase9_highadoption]``
"""

from __future__ import annotations

import datetime as dt
import platform
import sys
import time
from pathlib import Path
from typing import Final

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim import Params, run
from aisim.experiment.meta import provenance
from aisim.state import BASELINE_FILES
from tools.generate_goldens import uv_version, write_json
from tools.generate_goldens_phase8 import GOLDENS, ROOT, as_golden, monte_carlo, scenarios
from tools.hash_tree import sha256_file

COMMAND: Final = "uv run python tools/generate_goldens_phase9.py"
MODELS: Final = ("phase9", "phase9_highadoption")


def main(argv: list[str]) -> int:
    """Generate the golden files and manifest of the model named in ``argv`` (default ``phase9``)."""
    if len(argv) > 1 or (argv and argv[0] not in MODELS):
        print(f"usage: generate_goldens_phase9.py [{' | '.join(MODELS)}]", file=sys.stderr)
        return 2
    model = argv[0] if argv else MODELS[0]
    command = COMMAND if model == MODELS[0] else f"{COMMAND} {model}"
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    prov = provenance()
    folder = GOLDENS / model
    folder.mkdir(parents=True, exist_ok=True)
    wall: dict[str, float] = {}
    for name, ai_on in (("base", True), ("ai_off", False)):
        t0 = time.perf_counter()
        write_json(folder / f"{name}.json", as_golden(run(Params.baseline(model), ai_on=ai_on, record_every=0.25)))
        wall[name] = round(time.perf_counter() - t0, 3)
    t0 = time.perf_counter()
    write_json(folder / "results.json", {"scenarios": scenarios(model), "mc": monte_carlo(model)})
    wall["results"] = round(time.perf_counter() - t0, 3)
    names = ["base.json", "ai_off.json", "results.json"]
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
        "command": command,
        "git_commit": prov["git_commit"],
        "git_dirty": prov["git_dirty"],
        "wall_time_s": wall,
    }
    write_json(folder / "MANIFEST.json", manifest)
    print(f"wrote {folder.relative_to(ROOT).as_posix()}: {', '.join(names)}, MANIFEST.json ({wall})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
