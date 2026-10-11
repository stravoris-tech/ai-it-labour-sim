"""Run the frozen prototype in ``reference/prototype/`` without modifying it.

The prototype keeps its parameters in a module-level mutable dict ``P`` and its scripts open CWD-relative paths, so
this module loads a fresh copy of ``phase7_sim.py`` for every run, applies the calibration the way ``phase7_runs.py``
does, and runs the unmodified ``phase7_runs.py`` as a subprocess in a working directory of its own.

Python is told not to write bytecode while it loads prototype code, so no ``__pycache__`` appears inside the frozen
tree and its tree hash stays fixed.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PROTOTYPE = ROOT / "reference" / "prototype"
CODE = PROTOTYPE / "code"
SIM_PATH = CODE / "phase7_sim.py"
RUNS_PATH = CODE / "phase7_runs.py"
CALIB_PATH = PROTOTYPE / "data" / "calib7.json"

# Verbatim from phase7_runs.py line 8.
CALIB_PREFIXES = ("SrcASC_", "TypeASC_", "LOB0_", "Port0_", "Seats0_", "Budget0_", "LabourCostPB0_")

Path_ = tuple[str | int, ...]
RunResult = tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]

_module_ids = itertools.count()


def load_prototype_sim() -> ModuleType:
    """Load ``phase7_sim.py`` as a new module under a unique name, so no run sees another run's ``P``."""
    name = f"_reference_phase7_sim_{os.getpid()}_{next(_module_ids)}"
    spec = importlib.util.spec_from_file_location(name, SIM_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {SIM_PATH}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def apply_calibration(sim: ModuleType) -> dict[str, Any]:
    """Copy the calibrated parameters into ``sim.P`` as ``phase7_runs.py`` lines 6-10 do, and return the init state.

    ``BASE = dict(S.P)`` (line 11) is deliberately not reproduced: it only snapshots ``P`` for the tornado ranges.
    """
    with CALIB_PATH.open() as f:
        cal = json.load(f)
    for k, v in cal["params"].items():
        if k in sim.P or k.startswith(CALIB_PREFIXES):
            sim.P[k] = v
    init: dict[str, Any] = cal["init"]
    return init


def run_base(ai_on: bool = True, dt: float = 1 / 16, record_every: float = 0.25, **overrides: Any) -> RunResult:
    """Run the calibrated prototype once on a fresh module and return its ``(rows, final_state, mins)``."""
    sim = load_prototype_sim()
    init = apply_calibration(sim)
    result: RunResult = sim.run(init, ai_on=ai_on, dt=dt, record_every=record_every, **overrides)
    return result


def run_full_suite(workdir: Path) -> Path:
    """Run the unmodified ``phase7_runs.py`` in ``workdir`` and return the ``phase7_results.json`` it writes.

    ``workdir`` gets a copy of ``calib7.json``, because the script reads it from the working directory. The prototype
    ``code/`` directory goes on ``PYTHONPATH``. Raises ``RuntimeError`` if the script exits non-zero.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CALIB_PATH, workdir / CALIB_PATH.name)
    env = dict(os.environ, PYTHONPATH=str(CODE), PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(
        [sys.executable, str(RUNS_PATH)], cwd=workdir, env=env, capture_output=True, text=True, check=False
    )
    (workdir / "phase7_runs.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"phase7_runs.py exited {proc.returncode}:\n{proc.stderr}")
    return workdir / "phase7_results.json"


def _is_number(x: object) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def iter_numeric_pairs(a: Any, b: Any, path: Path_ = ()) -> Iterator[tuple[Path_, float, float]]:
    """Yield ``(path, a_leaf, b_leaf)`` for every numeric leaf of two nested structures of dicts, lists and numbers.

    Raises ``ValueError`` if the structures differ: different keys, lengths or types, or unequal non-numeric leaves.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            only_a = sorted(map(str, a.keys() - b.keys()))[:5]
            only_b = sorted(map(str, b.keys() - a.keys()))[:5]
            raise ValueError(f"keys differ at {path}: only in a {only_a}, only in b {only_b}")
        for k in a:
            yield from iter_numeric_pairs(a[k], b[k], (*path, k))
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            raise ValueError(f"lengths differ at {path}: {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            yield from iter_numeric_pairs(x, y, (*path, i))
    elif _is_number(a) and _is_number(b):
        yield path, float(a), float(b)
    elif type(a) is not type(b) or a != b:
        raise ValueError(f"leaves differ at {path}: {a!r} vs {b!r}")


def rel_diff(x: float, y: float) -> float:
    """Return ``|x - y| / max(|x|, |y|)``, or 0 when the two are equal."""
    if x == y:
        return 0.0
    return abs(x - y) / max(abs(x), abs(y))


def max_rel_diff(a: Any, b: Any) -> tuple[float, Path_]:
    """Return the largest relative difference between two nested structures and the path where it occurs.

    Raises ``ValueError`` if keys, lengths or non-numeric leaves differ. Returns ``(0.0, ())`` if nothing differs.
    """
    worst: tuple[float, Path_] = (0.0, ())
    for path, x, y in iter_numeric_pairs(a, b):
        d = rel_diff(x, y)
        if d > worst[0] or (math.isnan(d) and not math.isnan(worst[0])):
            worst = (d, path)
    return worst
