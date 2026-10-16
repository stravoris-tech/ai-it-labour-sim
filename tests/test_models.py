"""The model selector (slice 8): named baselines ``phase7`` (the default) and ``phase8``, and the extension parameters.

- ``model="phase7"``, explicit or by default, is today's model bit for bit; ``baseline.json`` keeps its bytes.
- The extension parameters live in code (``EXTENSION_DEFAULTS``), not in ``baseline.json``, and ``parameters.csv``
  classes exactly them as ``extension``.
- An unknown model raises everywhere: ``ValueError`` from the loaders, one ``ValidationError`` from the experiment API.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import replace
from importlib.resources import files

import pytest

from aisim import BatchParams, Experiment, Params, ValidationError, run, run_batch, run_experiment, run_scenarios
from aisim.batch.state import pack
from aisim.params import EXTENSION_DEFAULTS
from aisim.state import MODELS, baseline_data
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
    assert MODELS == ("phase7", "phase8")
    assert dict(EXTENSION_DEFAULTS) == {"AnnuityShare": 0.0, "AnnuityAnchorW": 0.0}
    p = Params.baseline()
    assert p == Params.baseline("phase7")
    names = list(p.scalars)
    assert names[: -len(EXTENSION_DEFAULTS)] == list(baseline_data()["params"])
    assert names[-len(EXTENSION_DEFAULTS) :] == list(EXTENSION_DEFAULTS)
    assert all(p.scalars[k] == v for k, v in EXTENSION_DEFAULTS.items())


def test_parameters_csv_extension_rows_are_the_extension_defaults() -> None:
    text = files("aisim").joinpath("data", "parameters.csv").read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    ext = [r for r in rows if r["kind"] == "extension"]
    assert [r["name"] for r in ext] == list(EXTENSION_DEFAULTS)
    assert all(float(r["value"]) == EXTENSION_DEFAULTS[r["name"]] for r in ext)
    assert all(r["lever"] == "no" and r["fitted"] == "no" for r in ext)


def test_batch_params_model_argument() -> None:
    a, b = BatchParams.baseline(3), BatchParams.baseline(3, model="phase7")
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


def test_experiment_model_phase7_is_the_default() -> None:
    exp = Experiment(scenario="Fast AI", perturb_from=2026.5)
    a = run_experiment(exp, outputs=KEYS, workers=1)
    b = run_experiment(replace(exp, model="phase7"), outputs=KEYS, workers=1)
    for k in KEYS:
        assert (a.series[k] == b.series[k]).all(), k


def test_unknown_model_raises() -> None:
    for call in (
        lambda: baseline_data("phase9"),
        lambda: Params.baseline("phase9"),
        lambda: BatchParams.baseline(1, model="phase9"),
        lambda: run_experiment(Experiment(model="phase9"), outputs=KEYS, validate=False),
    ):
        with pytest.raises(ValueError, match="unknown model 'phase9'"):
            call()


def test_unknown_model_joins_the_single_validation_error() -> None:
    """The model violation is reported with every other violation, checked against phase 7."""
    with pytest.raises(ValidationError) as info:
        run_experiment(Experiment(model="phase9", overrides={"TrendTime": 0.0}), outputs=KEYS)
    found = [(v.family, v.target) for v in info.value.violations]
    assert found[0] == ("model", "model")
    assert len(found) > 1
    with pytest.raises(ValidationError) as info:
        run_scenarios(Experiment(model="phase9"), [None, "Fast AI"], outputs=KEYS)
    assert [(v.family, v.target) for v in info.value.violations] == [("model", "model")]


# ---- phase 8 ---------------------------------------------------------------------------------------------------------


def test_phase8_2024_row_equals_phase7() -> None:
    """Phase 8 adds no stock and is neutral in 2024: its 2024 row equals Phase 7's bit for bit (scalar, with extras),
    and it differs afterwards."""
    p7 = run(Params.baseline("phase7"), record_every=1.0, extras=True)
    p8 = run(Params.baseline("phase8"), record_every=1.0, extras=True)
    assert p7.extras is not None and p8.extras is not None
    assert p7.rows[0] == p8.rows[0] and p7.extras[0] == p8.extras[0]
    assert p7.rows[-1]["RevenueTot"] != p8.rows[-1]["RevenueTot"]


def test_run_scenarios_carry_the_model() -> None:
    """Each block of ``run_scenarios`` runs the requested model: the baseline block equals the solo phase 8 run."""
    exp = Experiment(model="phase8")
    blocks = run_scenarios(exp, [None, "Fast AI"], outputs=KEYS, workers=1)
    solo = run_experiment(exp, outputs=KEYS, workers=1)
    p7 = run_experiment(Experiment(), outputs=KEYS, workers=1)
    for k in KEYS:
        assert (blocks[None].series[k] == solo.series[k]).all(), k
    assert not (solo.series["RevenueTot"] == p7.series["RevenueTot"]).all()
