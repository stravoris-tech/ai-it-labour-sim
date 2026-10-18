"""The shipped phase 8 models (slice 9): ``phase8`` and ``phase8_highadoption``.

There is no prototype for them, so the scalar engine is the oracle and batch-scalar parity the cross-check.

- **Built, not hand-edited.** Each baseline file is exactly what ``tools/build_model.py`` writes from
  ``tools/models/<name>/spec.json`` and ``fit.json``, and it reproduces its fit's loss bit for bit (so no derived
  constant is stale).
- **2024.** The 2024 state is Phase 7's (check A) and each model validates clean against its own baseline, the C8
  calibration identities included, from 2024 and with ``perturb_from`` 2026.5 (check B). The pricing design on Phase
  7's values is neutral in 2024: its 2024 row is Phase 7's bit for bit.
- **Parity.** Batch against scalar on Base, ``EXTREME``, AI off and a two-phase run with noise.
- **The experiment API** with a shipped model is bit-equal to a direct ``run_batch``, in-process and in two workers.
- **Integrity** (T1, T2, no negative stocks) for both.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aisim import BatchParams, Experiment, Noise, Params, load_initial_state, run, run_batch, run_experiment
from aisim.experiment.validate import validate
from aisim.noise import ou_factors
from aisim.perturb import run_batch_from, run_from, start_step_of
from aisim.scenarios import EXTREME, SCENARIOS
from aisim.state import BASELINE_FILES, baseline_data
from tests.helpers import TOL, annual, assert_close, people, phase8_platform_matches
from tests.test_batch_parity import compare_run
from tests.test_integrity import MIN_STOCK
from tests.test_noise import assert_bit_identical, scalar_noise
from tools.build_model import build
from tools.calibrate import Objective, load_targets, loss

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The parity tests here need numpy's kernels to match libm (``tests/conftest.py``)."""

ROOT = Path(__file__).resolve().parent.parent
MODELS = ("phase8", "phase8_highadoption")
BUILT_MODELS = (*MODELS, "phase9", "phase9_highadoption")
"""Every shipped model built by ``tools/build_model.py`` (slice 12 adds ``phase9``, slice 13 ``phase9_highadoption``):
the two build checks below run on each; the rest of this module covers the phase 8 models."""
DESIGN = {"OpeningsContinuous": 1.0, "PassThrough": 0.75, "AnnuityShare": 0.3, "AnnuityAnchorW": 0.4}
"""The phase 8 design: continuous openings and the slice 8 pricing values."""
KEYS = ("HeadTotal", "RevenueTot", "A_mean", "AvgIdx_OIT", "EffortShare_OIT", "HireJ_ON")
DT = 1 / 16
Y = 2026.5


@pytest.fixture(scope="module", params=MODELS)
def model(request: pytest.FixtureRequest) -> str:
    name: str = request.param
    return name


def fit_of(model: str) -> dict[str, object]:
    with (ROOT / "tools" / "models" / model / "fit.json").open(encoding="utf-8") as f:
        out: dict[str, object] = json.load(f)
    return out


# ---- built by the tools ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("model", BUILT_MODELS)
def test_baseline_is_build_model_output(model: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped file is byte for byte what ``build_model.py`` writes from the committed spec and fit."""
    monkeypatch.chdir(ROOT)
    out = Path("src") / "aisim" / "data" / f"baseline_{model}.json"
    assert Path(str(BASELINE_FILES[model])).resolve() == out.resolve()
    text = build(Path("tools") / "models" / model / "spec.json", out)
    assert out.read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize("model", BUILT_MODELS)
def test_baseline_reproduces_its_fit_loss(model: str) -> None:
    """The model's own baseline gives its fit's loss and target values: every value the fit evaluated, derived
    constants included (``AdoptC0``), is in the file. Bit for bit on the platform the fits were made on (the phase 8
    golden manifest's); within ``TOL`` elsewhere, where the C library may round the last ulp differently."""
    fit = fit_of(model)
    obj = Objective(model, [], {}, load_targets())
    fresh_loss, fresh_values = loss(obj.evaluate([[]])[0]), obj.values([[]])[0]
    targets = fit["targets"]
    assert isinstance(targets, list) and isinstance(fit["loss"], float)
    stored = [t["model"] for t in targets]
    if phase8_platform_matches():
        assert fresh_loss == fit["loss"]
        assert fresh_values == stored
    else:
        assert math.isclose(fresh_loss, fit["loss"], rel_tol=TOL, abs_tol=TOL)
        assert_close(fresh_values, stored, TOL, TOL)


def test_spec_and_fit_agree(model: str) -> None:
    spec = json.loads((ROOT / "tools" / "models" / model / "spec.json").read_text(encoding="utf-8"))
    fit = fit_of(model)
    assert spec["model"] == model and spec["fit"] == f"tools/models/{model}/fit.json"
    assert spec["set"] == fit["fixed"]
    assert {k: v for k, v in spec["set"].items() if k in DESIGN} == DESIGN
    p = Params.baseline(model)
    fitted = fit["fitted"]
    assert isinstance(fitted, dict)
    assert {k: p.scalars[k] for k in [*spec["set"], *fitted]} == {**spec["set"], **fitted}


# ---- 2024 ------------------------------------------------------------------------------------------------------------


def test_init_is_phase7(model: str) -> None:
    """Check A: the model's 2024 state is Phase 7's."""
    assert baseline_data(model)["init"] == baseline_data("phase7")["init"]
    assert baseline_data(model)["tables"] == baseline_data("phase7")["tables"]


@pytest.mark.parametrize("perturb_from", [None, Y])
def test_validates_clean_against_its_own_baseline(model: str, perturb_from: float | None) -> None:
    """Check B: no violation (C8 calibration identities, ``level_2024``, domains) for the model's own baseline."""
    validate(Params.baseline(model), model=model, perturb_from=perturb_from)


def test_experiment_with_perturb_from_validates() -> None:
    """``model="phase8"`` with ``perturb_from`` 2026.5 and a sampled lever passes validation: the refitted 2024
    levels are judged against phase 8's own baseline, so there is no ``level_2024`` violation."""
    exp = Experiment(model="phase8", perturb_from=Y, samples=pd.DataFrame({"g": [0.18, 0.22]}))
    res = run_experiment(exp, outputs=["HeadTotal"], workers=1)
    assert res.valid.all()


def test_design_on_phase7_is_neutral_in_2024() -> None:
    """The phase 8 design on Phase 7's values: the 2024 row is Phase 7's bit for bit, in both engines."""
    p7, pd8 = Params.baseline("phase7"), Params.baseline("phase7").with_overrides(**DESIGN)
    assert run(p7, record_every=1.0).rows[0] == run(pd8, record_every=1.0).rows[0]
    b = run_batch(BatchParams.stack([p7, pd8]), record_every=1.0)
    for key, s in b.series.items():
        assert s[0, 0] == s[1, 0], key


# ---- parity ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("case", ["Base", "Fast AI", "EXTREME", "AI off"])
def test_parity(model: str, case: str) -> None:
    """Batch against the scalar oracle within 1e-12: rows every quarter, final state, mins."""
    base = Params.baseline(model)
    p = base.with_overrides(**(EXTREME if case == "EXTREME" else SCENARIOS.get(case, {})))
    ai_on = case != "AI off"
    batch = run_batch(BatchParams.stack([p]), ai_on=ai_on, record_every=0.25)
    assert batch.finite.all()
    cmp = compare_run(batch, 0, run(p, ai_on=ai_on, record_every=0.25))
    assert cmp.miss is None, cmp.miss


def test_parity_two_phase_with_noise(model: str) -> None:
    """Two-phase runs from the model's baseline at Y = 2026.5, with demand and anchor noise: bit-identical."""
    base = Params.baseline(model)
    runs = [base, base.with_overrides(g=0.22, PriceHorizon=6.0), base.with_overrides(**SCENARIOS["Slow AI"])]
    noise = {"anchor": Noise(0.1, 1.0), "demand": Noise(0.05, 2.0)}
    factors = ou_factors(noise, 47, range(len(runs)), start_step=start_step_of(Y, DT), steps=256, dt=DT)
    batch = run_batch_from(BatchParams.stack(runs), Y=Y, record_every=0.25, noise=factors, base=base)
    assert batch.finite.all()
    for i, p in enumerate(runs):
        assert_bit_identical(batch, i, run_from(base, p, Y=Y, record_every=0.25, noise=scalar_noise(factors, i)))


# ---- the experiment API with a shipped model -------------------------------------------------------------------------


@pytest.mark.parametrize("workers", [1, 2])
def test_experiment_equals_direct_run_batch(workers: int) -> None:
    """``run_experiment`` with ``model="phase8"`` equals ``run_batch`` on the same per-run values bit for bit; with two
    spawned workers too, since a shipped model is a package file in every process."""
    values = {"g": [0.16, 0.2, 0.24, 0.28], "PriceHorizon": [5.0, 6.0, 6.5, 7.0]}
    exp = Experiment(model="phase8", samples=pd.DataFrame(values))
    res = run_experiment(exp, outputs=list(KEYS), workers=workers, chunk_size=2)
    direct = run_batch(BatchParams.baseline(4, model="phase8", **values), outputs=list(KEYS))
    for k in KEYS:
        assert np.array_equal(res.series[k], direct.series[k]), k
    assert res.meta["experiment"]["model"] == "phase8"


# ---- integrity -------------------------------------------------------------------------------------------------------


def test_t1_ai_off_growth_path(model: str) -> None:
    ann = annual(run(Params.baseline(model), ai_on=False, record_every=1.0).rows)
    h2024 = ann[2024]["HeadTotal"]
    assert max(abs(r["HeadTotal"] / h2024 / r["G"] - 1) for r in ann.values()) < 0.012


def test_t2_people_conservation(model: str) -> None:
    result = run(Params.baseline(model), record_every=1 / 16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in result.rows[:-1])
    total = people(result.final_state)
    assert abs(total - people(load_initial_state()) - inflow) <= 1e-9 * total


@pytest.mark.parametrize("case", ["base", "EXTREME"])
def test_no_negative_stocks(model: str, case: str) -> None:
    params = Params.baseline(model).with_overrides(**(EXTREME if case == "EXTREME" else {}))
    mins = run(params, record_every=1.0).mins
    worst = min(mins, key=lambda k: mins[k])
    assert mins[worst] >= MIN_STOCK, f"{worst} = {mins[worst]!r}"
