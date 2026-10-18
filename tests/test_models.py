"""The model selector (slice 8): named baselines in one registry, ``phase8`` the default (slice 7,
``DEFAULT_MODEL``) beside ``phase7`` and ``phase8_highadoption`` (slice 9), and the extension parameters.

- ``model="phase7"``, named explicitly, is the prototype's model bit for bit; ``baseline.json`` keeps its bytes.
- The extension parameters live in code (``EXTENSION_DEFAULTS``), not in ``baseline.json``, and ``parameters.csv``
  classes exactly them as ``extension``.
- An unknown model raises everywhere: ``ValueError`` from the loaders, one ``ValidationError``
  from the experiment API.
- A second model comes from the ``register_model`` fixture (``tests/conftest.py``), registered in
  ``aisim.state.BASELINE_FILES``: every site that takes a model (fixed parameters, phase 1, validation, the tornado
  levers, ``run_scenarios``, meta and the report) uses the selected model's baseline.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from importlib.resources import files

import numpy as np
import pytest

from aisim import BatchParams, Experiment, Params, ValidationError, run, run_batch, run_experiment, run_scenarios
from aisim.batch.state import pack
from aisim.experiment import validate as validation
from aisim.experiment.runner import fixed_params, known_model
from aisim.params import EXTENSION_DEFAULTS
from aisim.report import settings_rows
from aisim.scenarios import tornado_levers
from aisim.state import BASELINE_FILES, baseline_data, models
from tests.helpers import FIXTURE_CHANGES, LEVEL_2024_CHANGE, PRICING_CHANGES, SECOND_MODEL, RegisterModel
from tests.test_batch_parity import ALL_CASES, Case
from tests.test_perturb import assert_batches_identical, assert_scalar_identical

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The batch runs here are compared bit for bit (``tests/conftest.py``)."""

BASELINE_SHA256 = "d0e0141604d11456477f40f010bffb6d129de4b3501c3a32a2f0fe0e3d47afae"
"""``src/aisim/data/baseline.json`` on ``main`` at 1285920, before slice 8: its bytes must not change."""

KEYS = ["HeadTotal", "RevenueTot"]


def data_bytes(name: str) -> bytes:
    return files("aisim").joinpath("data", name).read_bytes()


def test_baseline_json_is_byte_identical_to_main() -> None:
    assert hashlib.sha256(data_bytes("baseline.json")).hexdigest() == BASELINE_SHA256
    assert not set(EXTENSION_DEFAULTS) & set(json.loads(data_bytes("baseline.json"))["params"])


def test_models_and_extension_defaults() -> None:
    shipped = ["phase7", "phase8", "phase8_highadoption", "phase9"]
    assert models() == tuple(shipped) and list(BASELINE_FILES) == shipped
    assert dict(EXTENSION_DEFAULTS) == {
        "AnnuityShare": 0.0,
        "AnnuityAnchorW": 0.0,
        "OpeningsContinuous": 0.0,
        "kR7": 0.0,
        "R7Lcap": 1.0,
        "R6Theta": 0.8,
        "R6e": 0.0,
        "R6Cap": 0.08,
        "R6MargTime": 0.75,
        "kViab": 0.0,
        "C4FadeTime": 2.0,
        "C4Cap": 0.0,
        "PriceFloor": 0.0,
        "AIDiscCeil": 0.0,
        "R10rc": 0.0,
        "R4a": 0.0,
        "R4aIN": 0.0,
        "MinSeekTime": 0.25,
    }
    p = Params.baseline("phase7")
    assert Params.baseline() == Params.baseline("phase8")
    names = list(p.scalars)
    assert names[: -len(EXTENSION_DEFAULTS)] == list(baseline_data("phase7")["params"])
    assert names[-len(EXTENSION_DEFAULTS) :] == list(EXTENSION_DEFAULTS)
    assert all(p.scalars[k] == v for k, v in EXTENSION_DEFAULTS.items())


def test_parameters_csv_extension_rows_are_the_extension_defaults() -> None:
    text = files("aisim").joinpath("data", "parameters.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    ext = [r for r in rows if r["kind"] == "extension"]
    assert [r["name"] for r in ext] == list(EXTENSION_DEFAULTS)
    assert all(float(r["value"]) == EXTENSION_DEFAULTS[r["name"]] for r in ext)
    assert all(r["lever"] == "no" and r["fitted"] == "no" for r in ext)


def test_build_baseline_reproduces_the_committed_data() -> None:
    """``tools/build_baseline.py`` renders ``baseline.json`` and ``parameters.csv`` byte for byte as committed (open
    question 2): the prototype's 330 scalars, then one ``extension`` row per ``EXTENSION_DEFAULTS`` entry."""
    from tools.build_baseline import render

    _, baseline_text, csv_text, n_rows = render()
    assert baseline_text.encode("utf-8") == data_bytes("baseline.json")
    assert csv_text.encode("utf-8") == data_bytes("parameters.csv")
    assert n_rows == 330 + len(EXTENSION_DEFAULTS)


def test_batch_params_model_argument() -> None:
    a, b = BatchParams.baseline(3), BatchParams.baseline(3, model="phase8")
    assert list(a.scalars) == list(b.scalars)
    assert all((a.scalars[k] == b.scalars[k]).all() for k in a.scalars if k != "DemandGrowthLate")


def phase7_explicit(case: Case) -> Params:
    return Params.baseline(model="phase7").with_overrides(**case.overrides)


def test_explicit_phase7_is_bit_identical_on_the_27_cases() -> None:
    """The 27-case batch (26 at dt 1/16 in one batch, the dt-1/32 case alone) built from ``Params.baseline("phase7")``
    equals the default build: rows, final state, mins and ``finite``; and so do three scalar runs."""
    groups = [[c for c in ALL_CASES.values() if c.dt == 1 / 16], [ALL_CASES["base, dt 1/32"]]]
    assert sum(len(g) for g in groups) == 27
    for cases in groups:
        init = pack([c.state() for c in cases])
        ai = [c.ai_on for c in cases]
        dt = cases[0].dt
        default = run_batch(BatchParams.stack([c.params() for c in cases]), init, ai_on=ai, dt=dt)
        explicit = run_batch(BatchParams.stack([phase7_explicit(c) for c in cases]), init, ai_on=ai, dt=dt)
        assert_batches_identical(default, explicit)
    for name in ("scenario Base", "EXTREME", "base, dt 1/32"):
        case = ALL_CASES[name]
        default_run = case.scalar(record_every=1.0)
        explicit_run = run(phase7_explicit(case), case.state(), ai_on=case.ai_on, dt=case.dt, record_every=1.0)
        assert_scalar_identical(default_run, explicit_run)


def test_experiment_model_phase8_is_the_default() -> None:
    exp = Experiment(scenario="Fast AI", perturb_from=2026.5)
    a = run_experiment(exp, outputs=KEYS, workers=1)
    b = run_experiment(replace(exp, model="phase8"), outputs=KEYS, workers=1)
    for k in KEYS:
        assert (a.series[k] == b.series[k]).all(), k


@pytest.mark.parametrize("name", ["phase10", "phase6"])
def test_unknown_model_raises(name: str) -> None:
    """A name that is not registered is unknown to every loader."""
    for call in (
        lambda: baseline_data(name),
        lambda: Params.baseline(name),
        lambda: BatchParams.baseline(1, model=name),
        lambda: run_experiment(Experiment(model=name), outputs=KEYS, validate=False),
    ):
        with pytest.raises(ValueError, match=f"unknown model '{name}'"):
            call()


@pytest.mark.parametrize("name", ["phase10", "phase6"])
def test_unknown_model_joins_the_single_validation_error(name: str) -> None:
    """The model violation is reported with every other violation, checked against phase 7."""
    with pytest.raises(ValidationError) as info:
        run_experiment(Experiment(model=name, overrides={"TrendTime": 0.0}), outputs=KEYS)
    found = [(v.family, v.target) for v in info.value.violations]
    assert found[0] == ("model", "model")
    assert len(found) > 1
    with pytest.raises(ValidationError) as info:
        run_scenarios(Experiment(model=name), [None, "Fast AI"], outputs=KEYS)
    assert [(v.family, v.target) for v in info.value.violations] == [("model", "model")]


# ---- a second model (the register_model fixture) ---------------------------------------------------------------------


def test_registered_model_is_seen_by_every_check(register_model: RegisterModel) -> None:
    """The registry is read at call time, so there is no stale copy: once registered, the fixture model is a known
    model to the state loaders, ``runner.known_model``, ``validate`` and ``tornado_levers``, and it is gone from all of
    them when the test ends (``monkeypatch``)."""
    p = register_model(SECOND_MODEL, FIXTURE_CHANGES)
    assert models() == ("phase7", "phase8", "phase8_highadoption", "phase9", SECOND_MODEL)
    assert baseline_data(SECOND_MODEL)["params"][LEVEL_2024_CHANGE] == FIXTURE_CHANGES[LEVEL_2024_CHANGE]
    exp = Experiment(model=SECOND_MODEL)
    assert known_model(exp) is exp
    validation.validate(p, model=SECOND_MODEL)
    assert set(tornado_levers(2026.5, model=SECOND_MODEL)) == set(tornado_levers(2026.5))


def test_model_baseline_2024_row_equals_phase7(register_model: RegisterModel) -> None:
    """The model extensions add no stock, so every model starts from the same state; a model whose changes are neutral
    in 2024 (the pricing changes) has Phase 7's 2024 row bit for bit (scalar, with extras), and differs afterwards.
    The fixture's ``init`` is Phase 7's."""
    p = register_model(SECOND_MODEL, PRICING_CHANGES)
    assert baseline_data(SECOND_MODEL)["init"] == baseline_data("phase7")["init"]
    p7 = run(Params.baseline("phase7"), record_every=1.0, extras=True)
    p2 = run(p, record_every=1.0, extras=True)
    assert p7.extras is not None and p2.extras is not None
    assert p7.rows[0] == p2.rows[0] and p7.extras[0] == p2.extras[0]
    assert p7.rows[-1]["RevenueTot"] != p2.rows[-1]["RevenueTot"]


def test_fixed_params_use_the_model_baseline(register_model: RegisterModel) -> None:
    """``fixed_params`` and ``design`` build on the selected model: an experiment on the fixture model equals a direct
    ``run_batch`` of its baseline bit for bit, and differs from Phase 7."""
    register_model(SECOND_MODEL, FIXTURE_CHANGES)
    exp = Experiment(model=SECOND_MODEL)
    params, _ = fixed_params(exp)
    assert params.scalars == Params.baseline(SECOND_MODEL).scalars
    res = run_experiment(exp, outputs=KEYS, workers=1)
    direct = run_batch(BatchParams.baseline(1, model=SECOND_MODEL), outputs=KEYS)
    p7 = run_experiment(Experiment(), outputs=KEYS, workers=1)
    for k in KEYS:
        assert np.array_equal(res.series[k], direct.series[k]), k
    assert not np.array_equal(res.series["RevenueTot"], p7.series["RevenueTot"])


def test_phase1_runs_the_model_baseline(register_model: RegisterModel) -> None:
    """Phase 1 of a perturb run is the selected model's baseline: with no levers, ``perturb_from`` 2026.5 on the fixture
    model equals the plain fixture run bit for bit (a restart on the grid is exact), which is not Phase 7's."""
    register_model(SECOND_MODEL, FIXTURE_CHANGES)
    two_phase = run_experiment(Experiment(model=SECOND_MODEL, perturb_from=2026.5), outputs=KEYS, workers=1)
    plain = run_experiment(Experiment(model=SECOND_MODEL), outputs=KEYS, workers=1)
    p7 = run_experiment(Experiment(perturb_from=2026.5), outputs=KEYS, workers=1)
    for k in KEYS:
        assert np.array_equal(two_phase.series[k], plain.series[k]), k
        assert not np.array_equal(two_phase.series[k][:, :3], p7.series[k][:, :3]), k


def test_validation_is_judged_against_the_selected_model(register_model: RegisterModel) -> None:
    """Rules 5 (C8) and 8 compare with the selected model's baseline (original step 4.1, on the fixture model).

    - The fixture baseline under its own model passes, with ``perturb_from`` 2026.5 too.
    - The same values as overrides on Phase 7 are judged against Phase 7: the ``level_2024`` change is rejected at
      2026.5, and the C8 2024 spend ratio no longer matches Phase 7's.
    - The C8 baseline is the selected model's 2024 step.
    """
    p = register_model(SECOND_MODEL, FIXTURE_CHANGES)
    validation.validate(p, model=SECOND_MODEL)
    validation.validate(p, model=SECOND_MODEL, perturb_from=2026.5)
    run_experiment(Experiment(model=SECOND_MODEL, perturb_from=2026.5), outputs=KEYS, workers=1)

    c8 = validation._c8_baseline
    assert c8(SECOND_MODEL)["CostPerBFY0"] != c8("phase7")["CostPerBFY0"]
    assert {k: v for k, v in c8(SECOND_MODEL).items() if k != "CostPerBFY0"} == {
        k: v for k, v in c8("phase7").items() if k != "CostPerBFY0"
    }

    with pytest.raises(ValidationError) as info:
        validation.validate(p, overrides=dict(FIXTURE_CHANGES), model="phase7")
    found = [(v.family, v.target.split(" = ")[0]) for v in info.value.violations]
    assert found == [("calibration", "CostPerBFY0")]

    with pytest.raises(ValidationError) as info:
        run_experiment(Experiment(overrides=dict(FIXTURE_CHANGES), perturb_from=2026.5), outputs=KEYS)
    found = [(v.family, v.target.split(" = ")[0]) for v in info.value.violations]
    assert ("level_2024", LEVEL_2024_CHANGE) in found and ("calibration", "CostPerBFY0") in found


def test_tornado_levers_validate_against_the_model(register_model: RegisterModel) -> None:
    """``tornado_levers(Y, model=)`` applies the bounds to the selected model's baseline: on the fixture model it gives
    Phase 7's lever set and ranges (13 at 2026.5, 12 at 2027.0). Judged against Phase 7 instead, every bound would fail
    on the fixture's ``level_2024`` change."""
    p = register_model(SECOND_MODEL, FIXTURE_CHANGES)
    for Y, count in ((None, 14), (2026.5, 13), (2027.0, 12)):
        levers = tornado_levers(Y, model=SECOND_MODEL)
        assert levers == tornado_levers(Y, model="phase7") and len(levers) == count, Y
    with pytest.raises(ValidationError):
        validation.validate(p.with_overrides(g=0.06), overrides={"g": 0.06}, perturb_from=2026.5, model="phase7")


def test_run_scenarios_carry_the_model(register_model: RegisterModel) -> None:
    """Each block of ``run_scenarios`` runs the requested model: the baseline block equals the solo fixture run."""
    register_model(SECOND_MODEL, FIXTURE_CHANGES)
    exp = Experiment(model=SECOND_MODEL)
    blocks = run_scenarios(exp, [None, "Fast AI"], outputs=KEYS, workers=1)
    solo = run_experiment(exp, outputs=KEYS, workers=1)
    p7 = run_experiment(Experiment(), outputs=KEYS, workers=1)
    for k in KEYS:
        assert (blocks[None].series[k] == solo.series[k]).all(), k
    assert not (solo.series["RevenueTot"] == p7.series["RevenueTot"]).all()


# ---- meta and the report ---------------------------------------------------------------------------------------------


def test_meta_and_report_record_the_model(register_model: RegisterModel) -> None:
    """``meta["experiment"]["model"]`` names the model, in ``run_experiment``, every ``run_scenarios`` block and the
    combined meta; the meta survives ``json.dumps``; the report settings show a "model" row."""
    default = run_experiment(Experiment(), outputs=KEYS, workers=1)
    assert default.meta["experiment"]["model"] == "phase8"
    assert dict(settings_rows(default))["model"] == "phase8"
    register_model(SECOND_MODEL, FIXTURE_CHANGES)
    scen = run_scenarios(Experiment(model=SECOND_MODEL), [None, "Fast AI"], outputs=KEYS, workers=1)
    metas = [scen.meta, *(scen[s].meta for s in scen.scenarios)]
    for meta in metas:
        back = json.loads(json.dumps(meta))
        assert back["experiment"]["model"] == SECOND_MODEL
        assert dict(settings_rows(back))["model"] == SECOND_MODEL
    assert dict(settings_rows({"seed": 1}))["model"] == "n/a (unavailable)"
