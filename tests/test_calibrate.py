"""The calibration tool (``tools/calibrate.py``) and the model-baseline builder (``tools/build_model.py``).

- The targets CSV and the tool's FIT bounds, start and optimiser settings are ``calibrate7.py``'s, read by ``ast``.
- Driving all eleven FIT parameters from ``X0`` reproduces ``calib7.json`` (slow).
- A profile fit records its grid, and its loss is the model's.
- Multi-start: ``--starts 0`` is the single fit from ``X0`` bit for bit; Latin-hypercube starts give the same records
  in one process and in two; ``--warm`` adds a last, clipped start.
- ``build_model.py`` on a spec and fit in ``tmp_path``: reproducible, the spec's and fit's keys are the only ones
  that differ from Phase 7 plus ``EXTENSION_DEFAULTS``, and the tables and inits are equal.
"""

from __future__ import annotations

import ast
import inspect
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from scipy.optimize import least_squares

from aisim import Params
from aisim.params import EXTENSION_DEFAULTS
from aisim.state import baseline_data
from tests.helpers import phase8_platform_matches
from tests.test_openings import C2
from tools.build_model import build, main
from tools.calibrate import (
    DIFF_STEP,
    FIT_BOUNDS,
    MAX_NFEV,
    OBSERVABLES,
    RECORD_EVERY,
    SCIPY_TOL,
    STOP,
    X0,
    X_SCALE,
    Objective,
    lhs_starts,
    load_targets,
    loss,
    run,
)
from tools.reference_runner import CALIB_PATH, CODE

SET = {"PassThrough": 0.75, "AnnuityShare": 0.3, "AnnuityAnchorW": 0.4}
"""The spec values of the test model (the held slice 8 design values)."""


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


# ---- multi-start (slice 9) -------------------------------------------------------------------------------------------

SMALL = ["--model", "phase7", "--fit", "qC,pAtt", "--tol", "0.1"]
"""A short fit for the multi-start tests: two parameters that each move one target (``AC_mean``, ``Att``), with a
loose tolerance so that each start stops after a few evaluations (each one is a batched run to 2030.5)."""
RECORD = ("start", "x0", "x", "loss", "nfev", "njev", "status", "message", "runs", "batches")
"""A start's record without its wall time."""


def test_scipy_tol_is_least_squares_default() -> None:
    """The tolerances used without ``--tol`` are scipy's defaults, so the default fit is ``calibrate7.py``'s."""
    sig = inspect.signature(least_squares)
    assert {k: sig.parameters[k].default for k in ("xtol", "ftol", "gtol")} == dict.fromkeys(
        ("xtol", "ftol", "gtol"), SCIPY_TOL
    )


def test_starts_zero_reproduces_the_phase7_fit_bit_for_bit() -> None:
    """``--starts 0`` is the single fit from ``X0``: on every platform it equals a live default fit bit for bit, and
    records its one start. On the platform the phase 8 fits were made on it lands on recon 08 C2's values (the tool's
    Phase 7 fit before multi-start) bit for bit, with the same evaluation counts; elsewhere the optimiser amplifies
    the last-ulp differences of the C library (2.9e-12 relative on Linux x86-64), so C2 is matched at 1e-9 relative,
    the slow reproduction test's loss tolerance."""
    names = [n for n, _, _ in FIT_BOUNDS]
    argv = ["--model", "phase7", "--fit", ",".join(names), "--out", "unused.json"]
    out, _ = run([*argv, "--starts", "0"])
    default, _ = run(argv)
    same = ("fitted", "loss", "targets", "nfev", "njev", "status", "message", "runs", "batches", "best_start")
    assert {k: out[k] for k in same} == {k: default[k] for k in same}
    if phase8_platform_matches():
        assert out["fitted"] == C2
        assert out["loss"] == 0.0008007856055132186
        assert (out["status"], out["nfev"], out["njev"], out["runs"], out["batches"]) == (3, 18, 8, 107, 27)
    else:
        assert all(math.isclose(out["fitted"][k], v, rel_tol=1e-9) for k, v in C2.items()), out["fitted"]
        assert math.isclose(out["loss"], 0.0008007856055132186, rel_tol=1e-9)
    assert [r["start"] for r in out["starts"]] == [0] and out["best_start"] == 0
    assert out["starts"][0]["x0"] == [min(max(x, lo), hi) for x, (_, lo, hi) in zip(X0, FIT_BOUNDS, strict=True)]
    assert out["settings"] == {
        "starts": 0,
        "warm": None,
        "tol": None,
        "diff_step": DIFF_STEP,
        "max_nfev": MAX_NFEV,
        "procs": 1,
    }


def test_multi_start_is_deterministic_across_process_counts(tmp_path: Path) -> None:
    """Four Latin-hypercube starts give the same records in-process and in two spawned processes, and the best start
    is the top-level fit."""
    argv = [*SMALL, "--starts", "4", "--seed", "7", "--out", str(tmp_path / "fit.json")]
    one, _ = run([*argv, "--procs", "1"])
    two, _ = run([*argv, "--procs", "2"])
    assert [{k: r[k] for k in RECORD} for r in one["starts"]] == [{k: r[k] for k in RECORD} for r in two["starts"]]
    assert [r["start"] for r in one["starts"]] == [0, 1, 2, 3]
    assert one["starts"][0]["x0"] == lhs_starts(4, 7, [0.01, 0.001], [1.0, 0.5])[0]
    best = min(one["starts"], key=lambda r: r["loss"])
    assert one["best_start"] == best["start"] and one["loss"] == best["loss"]
    assert one["fitted"] == dict(zip(["qC", "pAtt"], best["x"], strict=True))
    assert one["seed"] == 7 and one["near_starts"] == [
        r["start"] for r in one["starts"] if r["loss"] <= 1.05 * best["loss"]
    ]
    assert {k: v for k, v in one.items() if k not in ("starts", "settings", "command")} == {
        k: v for k, v in two.items() if k not in ("starts", "settings", "command")
    }


def test_warm_start_is_last_and_clipped(tmp_path: Path) -> None:
    """``--warm`` adds one start after the others from the fit JSON's ``fitted``, clipped to the bounds."""
    warm = tmp_path / "warm.json"
    warm.write_text(json.dumps({"fitted": {"qC": 0.3, "pAtt": 0.9, "p": 0.1}}), "utf-8")
    argv = ["--model", "phase7", "--fit", "pAtt", "--tol", "0.1", "--starts", "1", "--warm", str(warm)]
    out, _ = run([*argv, "--out", str(tmp_path / "fit.json")])
    assert [r["start"] for r in out["starts"]] == [0, 1]
    assert out["starts"][1]["x0"] == [0.5]
    assert out["settings"]["warm"] == warm.as_posix()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"fitted": {"qC": 0.3}}), "utf-8")
    with pytest.raises(ValueError, match="has no fitted"):
        run([*SMALL, "--warm", str(bad), "--out", str(tmp_path / "fit.json")])


def test_profile_excludes_starts(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="excludes --starts and --warm"):
        run(["--profile", "PriceHorizon=6.5,7,0.25", "--starts", "2", "--out", str(tmp_path / "fit.json")])


def test_profile_fit_records_its_grid(tmp_path: Path) -> None:
    """``--profile`` on a small grid (3 points): the fit JSON holds the grid, bounds, the best loss, the command
    provenance, and every target's model value; re-evaluating the fitted value gives the stored loss."""
    fixed = {k: str(v) for k, v in SET.items()}
    argv = ["--model", "phase7", "--profile", "PriceHorizon=6.5,7,0.25"]
    argv += [x for k, v in fixed.items() for x in ("--fix", f"{k}={v}")]
    fit, _ = run([*argv, "--out", str(tmp_path / "fit.json")])
    assert fit["model"] == "phase7" and fit["fixed"] == SET and list(fit["fitted"]) == ["PriceHorizon"]
    grid = fit["profile"]["grid"]
    assert [g["x"] for g in grid] == [6.5, 6.75, 7.0]
    assert fit["bounds"] == {"PriceHorizon": [6.5, 7.0]}
    best = min(g["loss"] for g in grid)
    assert fit["loss"] == min(best, fit["profile"]["refine"]["loss"])
    assert 6.5 <= fit["fitted"]["PriceHorizon"] <= 7.0
    assert fit["git_commit"] and set(fit["versions"]) == {"ai-it-labour-sim", "numpy", "scipy"}
    obj = Objective("phase7", ["PriceHorizon"], fit["fixed"], load_targets())
    r = obj.residuals(np.array([fit["fitted"]["PriceHorizon"]]))
    assert loss(r) == fit["loss"]
    assert [t["model"] for t in fit["targets"]] == [float(v) for v in obj.values([[fit["fitted"]["PriceHorizon"]]])[0]]


def write_spec(tmp_path: Path, fixed: dict[str, float] | None = None) -> Path:
    """A spec and a minimal fit in ``tmp_path``: the spec sets ``SET``, the fit was made at ``fixed`` (default
    ``SET``) and found ``PriceHorizon`` 7.0."""
    fit = tmp_path / "fit.json"
    fit.write_text(json.dumps({"fixed": SET if fixed is None else fixed, "fitted": {"PriceHorizon": 7.0}}), "utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"model": "test", "set": SET, "fit": fit.as_posix(), "note": "test"}), "utf-8")
    return spec


def test_build_model_is_reproducible(tmp_path: Path) -> None:
    spec = write_spec(tmp_path)
    out = tmp_path / "baseline_test.json"
    assert main(["--spec", str(spec), "--out", str(out)]) == 0
    first = out.read_bytes()
    assert main(["--spec", str(spec), "--out", str(out)]) == 0
    assert out.read_bytes() == first
    assert first.decode("utf-8") == build(spec, out)


def test_build_model_differs_from_phase7_only_in_the_spec_and_fit_keys(tmp_path: Path) -> None:
    spec = write_spec(tmp_path)
    data = json.loads(build(spec))
    p7 = Params.baseline("phase7")
    assert list(data["params"]) == list(p7.scalars)
    assert {k for k in p7.scalars if p7.scalars[k] != data["params"][k]} == {*SET, "PriceHorizon"}
    assert {k: data["params"][k] for k in [*SET, "PriceHorizon"]} == {**SET, "PriceHorizon": 7.0}
    assert {k: p7.scalars[k] for k in EXTENSION_DEFAULTS} == dict(EXTENSION_DEFAULTS)
    assert data["tables"] == baseline_data("phase7")["tables"]
    assert data["init"] == baseline_data("phase7")["init"]
    assert data["meta"]["model"] == "test" and data["meta"]["fitted"] == {"PriceHorizon": 7.0}


def test_build_model_rejects_a_fit_made_at_other_values(tmp_path: Path) -> None:
    spec = write_spec(tmp_path, fixed={**SET, "PassThrough": 0.8})
    with pytest.raises(ValueError, match="the fit was made at"):
        build(spec)


def test_build_model_derives_adoptc0_as_with_overrides(tmp_path: Path) -> None:
    """A fit that moves ``qC`` moves the derived ``AdoptC0`` too, computed by ``Params.with_overrides`` (the fit's
    own parameter set), and the meta records it; a fit that moves no input leaves it at Phase 7's value."""
    fit = tmp_path / "fit.json"
    fit.write_text(json.dumps({"fixed": SET, "fitted": {"qC": 0.25, "PriceHorizon": 7.0}}), "utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"model": "test", "set": SET, "fit": fit.as_posix(), "note": "test"}), "utf-8")
    data = json.loads(build(spec))
    expect = Params.baseline().with_overrides(**SET, qC=0.25, PriceHorizon=7.0).scalars
    assert data["params"]["AdoptC0"] == expect["AdoptC0"] != Params.baseline().scalars["AdoptC0"]
    assert data["meta"]["derived"] == {"AdoptC0": expect["AdoptC0"]}
    assert {k: v for k, v in data["params"].items() if v != expect[k]} == {}
    plain = json.loads(build(write_spec(tmp_path)))
    assert plain["meta"]["derived"] == {} and plain["params"]["AdoptC0"] == Params.baseline().scalars["AdoptC0"]
