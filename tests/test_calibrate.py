"""The calibration tool (``tools/calibrate.py``), the phase 8 fit and the phase 8 baseline (``tools/build_phase8.py``).

- The targets CSV and the tool's FIT bounds, start and optimiser settings are ``calibrate7.py``'s, read by ``ast``.
- Driving all eleven FIT parameters from ``X0`` reproduces ``calib7.json`` (slow).
- The committed fit records its profile, and its loss is the model's.
- ``baseline_phase8.json`` is reproducible and differs from Phase 7 in exactly four parameters.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from aisim import Params
from aisim.params import EXTENSION_DEFAULTS
from aisim.state import baseline_data
from tools.build_phase8 import OUTPUT, ROOT, SPEC, build
from tools.calibrate import (
    DIFF_STEP,
    FIT_BOUNDS,
    MAX_NFEV,
    OBSERVABLES,
    RECORD_EVERY,
    STOP,
    X0,
    X_SCALE,
    Objective,
    load_targets,
    loss,
    run,
)
from tools.reference_runner import CALIB_PATH, CODE

FIT_JSON = ROOT / "tools" / "fits" / "phase8_pricing.json"
PHASE8_KEYS = {"PassThrough", "AnnuityShare", "AnnuityAnchorW", "PriceHorizon"}


KW = {"least_squares": ("x_scale", "diff_step", "max_nfev"), "run": ("record_every",)}


# Any: values parsed from the prototype's source.
def calibrate7() -> dict[str, Any]:
    """``TARGETS``, ``SCALE``, ``FIT``, ``X0``, the ``least_squares`` keywords, the ``S.run`` ``record_every`` and the
    default ``stop`` of ``metrics``."""
    tree = ast.parse((CODE / "calibrate7.py").read_text(encoding="utf-8"))
    out: dict[str, Any] = {}
    for node in ast.walk(tree):
        target = node.targets[0] if isinstance(node, ast.Assign) and len(node.targets) == 1 else None
        if (
            isinstance(node, ast.Assign)
            and isinstance(target, ast.Name)
            and target.id in ("TARGETS", "SCALE", "FIT", "X0")
        ):
            out[target.id] = ast.literal_eval(node.value)
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
            if name in ("least_squares", "run"):
                kw = {k.arg: ast.literal_eval(k.value) for k in node.keywords if k.arg in KW[name]}
                if kw:
                    out[name] = kw
        if isinstance(node, ast.FunctionDef) and node.name == "metrics":
            names = [a.arg for a in node.args.args][-len(node.args.defaults) :]
            out["metrics"] = {n: ast.literal_eval(d) for n, d in zip(names, node.args.defaults, strict=True)}
    return out


def test_targets_and_settings_equal_calibrate7() -> None:
    c7 = calibrate7()
    targets = load_targets()
    assert [(t.metric, t.year, t.target, t.weight, t.source) for t in targets] == list(c7["TARGETS"])
    assert [t.scale for t in targets] == [c7["SCALE"].get(t.metric, t.target) for t in targets]
    assert all(t.observable == OBSERVABLES[t.metric] for t in targets)
    assert list(FIT_BOUNDS) == list(c7["FIT"])
    assert list(X0) == list(c7["X0"])
    ls = c7["least_squares"]
    assert list(X_SCALE) == ls["x_scale"] and ls["diff_step"] == DIFF_STEP and ls["max_nfev"] == MAX_NFEV
    assert c7["metrics"]["stop"] == STOP and c7["run"]["record_every"] == RECORD_EVERY


@pytest.mark.slow
def test_reproduces_the_phase7_fit() -> None:
    """All eleven FIT parameters from ``X0`` with ``calibrate7.py``'s settings land on ``calib7.json``'s fitted values.

    ``calibrate7.py`` stores them rounded to 4 decimals (its ``fit()``), so the comparison applies that rounding and
    asserts equality; recon 08 C2 measured the unrounded values within 5.7e-11 (relative) of the prototype's own.
    """
    names = [n for n, _, _ in FIT_BOUNDS]
    out, _ = run(["--model", "phase7", "--fit", ",".join(names), "--out", "unused.json"])
    stored = json.loads(Path(CALIB_PATH).read_text(encoding="utf-8"))["fitted"]
    assert {n: round(v, 4) for n, v in out["fitted"].items()} == {n: stored[n] for n in names}
    assert out["status"] == 3 and out["nfev"] == 18 and out["njev"] == 8
    assert out["loss"] == pytest.approx(0.00080078560551, rel=1e-9)


def test_phase8_fit_records_its_profile() -> None:
    fit = json.loads(FIT_JSON.read_text(encoding="utf-8"))
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert fit["model"] == "phase7" and fit["fixed"] == spec["set"] and list(fit["fitted"]) == ["PriceHorizon"]
    grid = fit["profile"]["grid"]
    assert [g["x"] for g in grid] == [float(v) for v in np.linspace(4.0, 7.0, 61)]
    assert fit["bounds"] == {"PriceHorizon": [4.0, 7.0]}
    best = min(g["loss"] for g in grid)
    assert fit["loss"] == min(best, fit["profile"]["refine"]["loss"])
    assert 4.0 <= fit["fitted"]["PriceHorizon"] <= 7.0
    assert fit["git_commit"] and set(fit["versions"]) == {"ai-it-labour-sim", "numpy", "scipy"}
    obj = Objective("phase7", ["PriceHorizon"], fit["fixed"], load_targets())
    r = obj.residuals(np.array([fit["fitted"]["PriceHorizon"]]))
    assert loss(r) == fit["loss"]
    assert [t["model"] for t in fit["targets"]] == [float(v) for v in obj.values([[fit["fitted"]["PriceHorizon"]]])[0]]


def test_build_phase8_is_reproducible() -> None:
    assert build() == OUTPUT.read_text(encoding="utf-8")


def test_phase8_differs_from_phase7_in_exactly_four_parameters() -> None:
    p7, p8 = Params.baseline("phase7"), Params.baseline("phase8")
    assert list(p8.scalars) == list(p7.scalars)
    assert list(baseline_data("phase8")["params"]) == list(p7.scalars)
    assert {k for k in p7.scalars if p7.scalars[k] != p8.scalars[k]} == PHASE8_KEYS
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    fit = json.loads(FIT_JSON.read_text(encoding="utf-8"))
    assert {k: p8.scalars[k] for k in PHASE8_KEYS} == {**spec["set"], **fit["fitted"]}
    assert {k: p7.scalars[k] for k in EXTENSION_DEFAULTS} == dict(EXTENSION_DEFAULTS)
    assert p8.tables == p7.tables
    assert baseline_data("phase8")["init"] == baseline_data("phase7")["init"]


def test_build_phase8_rejects_a_fit_made_at_other_values() -> None:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    spec["set"]["PassThrough"] = 0.8
    path = ROOT / "temp" / "test_build_phase8_spec.json"
    path.parent.mkdir(exist_ok=True)  # temp/ is gitignored scratch
    path.write_text(json.dumps(spec), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="the fit was made at"):
            build(path)
    finally:
        path.unlink()
