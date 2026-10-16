"""JSON-safe metadata: an ``Experiment`` as plain data, and the provenance of a run (git commit, platform).

``ExperimentResult.meta`` must survive ``json.dumps``. ``experiment_dict`` writes the experiment as plain data:

- distributions as ``{"type": "Uniform", "lo": ..., "hi": ...}`` (their fields, sequences as lists);
- correlation keys as ``"a|b"``;
- an explicit ``samples`` design as a reference, not the data: its shape, columns and the SHA-256 of its float64
  values in C order.

``provenance()`` gives ``git_commit``, ``git_dirty`` and ``platform`` (OS, machine, Python), with None for whatever is
unavailable (no git, or a package not in a checkout).
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from aisim.experiment.sampling import Distribution
from aisim.noise import Noise

if TYPE_CHECKING:
    from aisim.experiment.runner import Experiment

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def distribution_dict(d: Distribution) -> dict[str, Any]:
    """``{"type": <class name>, <field>: <value>, ...}``, with sequences as lists."""
    out: dict[str, Any] = {"type": type(d).__name__}
    for f in fields(d):
        v = getattr(d, f.name)
        out[f.name] = [float(x) for x in v] if isinstance(v, list | tuple) else v
    return out


def samples_ref(df: pd.DataFrame) -> dict[str, Any]:
    """A reference to an explicit design: shape, columns and the SHA-256 of its float64 values (C order)."""
    values = np.ascontiguousarray(df.to_numpy(dtype=np.float64))
    return {
        "shape": [int(s) for s in values.shape],
        "columns": [str(c) for c in df.columns],
        "sha256": hashlib.sha256(values.tobytes()).hexdigest(),
    }


def _table(values: Mapping[str, Any]) -> dict[str, Any]:
    return {k: (dict(v) if isinstance(v, Mapping) else v) for k, v in values.items()}


def noise_dict(noise: Mapping[str, Noise]) -> dict[str, dict[str, float]]:
    """The noise spec as ``{channel: {"sigma": ..., "tau": ...}}``."""
    return {name: {"sigma": float(spec.sigma), "tau": float(spec.tau)} for name, spec in noise.items()}


def experiment_dict(exp: Experiment) -> dict[str, Any]:
    """The experiment as plain, JSON-serialisable data."""
    return {
        "scenario": exp.scenario,
        "overrides": dict(exp.overrides),
        "tables": {name: _table(values) for name, values in exp.tables.items()},
        "sample": {name: distribution_dict(d) for name, d in exp.sample.items()},
        "correlation": None if exp.correlation is None else {f"{a}|{b}": r for (a, b), r in exp.correlation.items()},
        "n": exp.n,
        "method": exp.method,
        "seed": exp.seed,
        "samples": None if exp.samples is None else samples_ref(exp.samples),
        "ai_on": exp.ai_on,
        "perturb_from": exp.perturb_from,
        "noise": noise_dict(exp.noise),
        "noise_seed": exp.noise_seed,
        "model": exp.model,
    }


def _git(*args: str) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=PACKAGE_DIR, capture_output=True, text=True, encoding="utf-8", check=False, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def provenance() -> dict[str, Any]:
    """``git_commit`` and ``git_dirty`` of the checkout the package runs from, and ``platform`` (None if unknown)."""
    commit = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain") if commit is not None else None
    return {
        "git_commit": commit,
        "git_dirty": None if status is None else bool(status),
        "platform": {"os": platform.platform(), "machine": platform.machine(), "python": sys.version},
    }
