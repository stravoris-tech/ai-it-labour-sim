"""The default model (slice 7): ``DEFAULT_MODEL`` is ``phase8``, and every library default and unknown-model fallback
names it; the tornado ranges are computed per model.

- The 8 sites of recon 07 B1: 6 signature defaults (``baseline_data``, ``Params.baseline``, ``BatchParams.baseline``,
  ``Experiment.model``, ``validate`` and ``tornado_levers``) and 2 unknown-model fallbacks (``known_model`` and the
  one inside ``validate``). ``tools/calibrate.py --model`` stays ``phase7``.
- ``tornado_levers(model="phase7")`` is ``TORNADO`` exactly; on another model ``Verif`` and ``JuniorCut`` are
  x0.7/x1.3 and x0.5/x1.5 of that model's values, and every other lever is Phase 7's.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable

import pytest

from aisim import BatchParams, Experiment, Params, ValidationError
from aisim.experiment import validate as validation
from aisim.experiment.runner import known_model
from aisim.scenarios import TORNADO, tornado_levers
from aisim.state import DEFAULT_MODEL, baseline_data
from tools import calibrate

PERTURB_YEARS = (None, 2023.5, 2024.0, 2025.5, 2026.0, 2026.3, 2026.5, 2027.0, 2030.0, 2040.0, 2200.0)
"""Every ``perturb_from`` the tests use (a grep of ``tests/``), and None."""

RELATIVE = {"Verif": (0.7, 1.3), "JuniorCut": (0.5, 1.5)}
"""The prototype's ratios for the two ranges relative to the model's value (``phase7_runs.py:35,39``)."""

MODELS = ("phase7", "phase8", "phase8_highadoption")


def default_of(func: Callable[..., object], name: str = "model") -> object:
    return inspect.signature(func).parameters[name].default


def test_default_model_is_phase8() -> None:
    assert DEFAULT_MODEL == "phase8"


def test_the_six_signature_defaults_name_default_model() -> None:
    defaults = {
        "baseline_data": default_of(baseline_data),
        "Params.baseline": default_of(Params.baseline),
        "BatchParams.baseline": default_of(BatchParams.baseline),
        "Experiment.model": next(f.default for f in dataclasses.fields(Experiment) if f.name == "model"),
        "validate": default_of(validation.validate),
        "tornado_levers": default_of(tornado_levers),
    }
    assert defaults == dict.fromkeys(defaults, DEFAULT_MODEL)
    assert Params.baseline() == Params.baseline(DEFAULT_MODEL)
    assert Experiment().model == DEFAULT_MODEL


def test_the_two_fallbacks_use_default_model() -> None:
    """An unknown model is validated as the default model: a ``level_2024`` value equal to phase8's passes rule 8 (only
    the model is reported), one equal to phase7's does not."""
    assert known_model(Experiment(model="nope")).model == DEFAULT_MODEL
    for model, extra in (("phase8", []), ("phase7", [("level_2024", "Verif")])):
        v = Params.baseline(model).scalars["Verif"]
        params = Params.baseline(DEFAULT_MODEL).with_overrides(Verif=v)
        with pytest.raises(ValidationError) as info:
            validation.validate(params, overrides={"Verif": v}, perturb_from=2026.5, model="nope")
        assert [(x.family, x.target) for x in info.value.violations] == [("model", "model"), *extra]


def test_calibrate_model_flag_stays_phase7() -> None:
    """A phase 8 fit is phase 7 plus fixes (recon 07 D1), so the tool's flag keeps its own default."""
    assert 'ap.add_argument("--model", default="phase7")' in inspect.getsource(calibrate.run)


@pytest.mark.parametrize("Y", PERTURB_YEARS)
def test_tornado_levers_phase7_is_tornado(Y: float | None) -> None:
    levers = tornado_levers(Y, model="phase7")
    names = [name for name, _, _, _ in TORNADO]
    assert list(levers) == [n for n in names if n in levers]
    for name, lo, hi, _ in TORNADO:
        if name in levers:
            assert (levers[name].lo, levers[name].hi) == (lo, hi), name
    if Y is None:
        assert list(levers) == names


@pytest.mark.parametrize("model", ["phase8", "phase8_highadoption"])
def test_tornado_levers_relative_ranges_follow_the_model(model: str) -> None:
    base = Params.baseline(model).scalars
    levers = tornado_levers(model=model)
    phase7 = {name: (lo, hi) for name, lo, hi, _ in TORNADO}
    assert list(levers) == list(phase7)
    for name, u in levers.items():
        if name in RELATIVE:
            v = Params.float_of(base, name)
            assert (u.lo, u.hi) == (v * RELATIVE[name][0], v * RELATIVE[name][1]), name
            assert (u.lo, u.hi) != phase7[name], name
        else:
            assert (u.lo, u.hi) == phase7[name], name


@pytest.mark.parametrize("model", MODELS)
def test_every_range_contains_its_model_value(model: str) -> None:
    """``DemandGrowthLate`` None means ``DemandGrowth`` (0.03)."""
    base = Params.baseline(model).scalars
    for name, u in tornado_levers(model=model).items():
        value = base[name]
        v = Params.float_of(base, "DemandGrowth") if value is None else float(value)
        assert u.lo <= v <= u.hi, (model, name, v, u)
