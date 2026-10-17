"""Validation of experiment inputs: domains, no-effect and derived overrides, joint constraints, calibration
identities, time constants against dt and sampled levers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd
import pytest

from aisim import SCENARIOS, Experiment, Params, Uniform, ValidationError, run_experiment
from aisim.experiment.inputs import batch_arrays
from aisim.experiment.runner import design, fixed_params
from aisim.experiment.validate import FAMILIES, Violation, validate
from aisim.params import ADOPTC0_INPUTS

EPS = 1e-9


def violations(
    overrides: Mapping[str, float | None] | None = None,
    tables: Mapping[str, Any] | None = None,
    sampled: Mapping[str, Any] | None = None,
    dt: float = 1 / 16,
) -> list[Violation]:
    """The violations of the baseline with ``overrides``, ``tables`` and per-run ``sampled`` values (none if valid)."""
    p = Params.baseline()
    if overrides:
        p = p.with_overrides(**overrides)
    for name, values in (tables or {}).items():
        p = p.with_table(name, values)
    arrays = {k: np.asarray(v, dtype=np.float64) for k, v in (sampled or {}).items()}
    try:
        validate(p, dt=dt, overrides=overrides or {}, tables=tables or {}, sampled=arrays)
    except ValidationError as e:
        return e.violations
    return []


def targets(vs: list[Violation], family: str | None = None) -> set[str]:
    return {v.target for v in vs if family is None or v.family == family}


# ---- 1. domains: just inside passes, just outside raises -------------------------------------------------------------

DOMAIN_CASES = [
    # (class, parameter, just inside, just outside)
    ("positive", "AIShockMult", EPS, 0.0),
    ("positive", "AIShockMult", EPS, -EPS),
    ("non_negative", "SrcCostSens", 0.0, -EPS),
    ("unit_interval", "BudgetShock", 0.0, -EPS),
    ("unit_interval", "BudgetShock", 1.0, 1 + EPS),
    ("below_one", "g", 1.0, 1 + EPS),
    ("below_one", "AICostDecline", 1 - EPS, 1.0),
    ("year", "PriceShockYear", 2000.0, 2000 - 1e-6),
    ("year", "PriceShockYear", 2100.0, 2100 + 1e-6),
    ("ordered_pair", "AIShockStart", 2000.0, 2000 - 1e-6),
    ("switch", "FreezeSourcing", 1.0, 1 + EPS),
    ("growth", "ITBudgetGrowth", -1 + EPS, -1.0),
    ("free", "ExitThreshold", -1e6, None),
]


@pytest.mark.parametrize(("cls", "name", "inside", "outside"), DOMAIN_CASES)
def test_domain_class(cls: str, name: str, inside: float, outside: float | None) -> None:
    assert violations({name: inside}) == []
    if outside is not None:
        vs = violations({name: outside})
        assert [(v.family, v.target) for v in vs] == [("domain", name)]
        assert cls in vs[0].rule and vs[0].evidence


def test_domain_table_entry() -> None:
    speed = dict(Params.baseline().table("SpeedUp"))
    assert violations(tables={"SpeedUp": {**speed, "APP": EPS}}) == []
    vs = violations(tables={"SpeedUp": {**speed, "APP": 0.0}})
    assert ("domain", "SpeedUp[APP]") in [(v.family, v.target) for v in vs]


def test_non_finite_value() -> None:
    assert targets(violations({"ExitThreshold": float("inf")}), "domain") == {"ExitThreshold"}
    assert violations({"DemandGrowthLate": None}) == []


# ---- 2, 3. no-effect and derived overrides ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Leakage", "Att0", "NormalUtil", "TargetMargin_OIT", "Wage_OV"])
def test_no_effect_scalar(name: str) -> None:
    assert targets(violations({name: 0.5})) == {name}


def test_no_effect_table() -> None:
    mix0 = {k: dict(v) for k, v in Params.baseline().tables["Mix0"].items() if isinstance(v, Mapping)}
    assert targets(violations(tables={"Mix0": mix0}), "no-effect") == {"Mix0"}


def test_adoptc0_override_raises() -> None:
    assert targets(violations({"AdoptC0": 0.1}), "derived") == {"AdoptC0"}


# ---- 4. joint constraints, one per family ----------------------------------------------------------------------------


def test_ordered_pair() -> None:
    assert violations({"VTRampStart": 2030.0, "VTRampEnd": 2030.0}) == []
    vs = violations({"VTRampStart": 2031.0, "VTRampEnd": 2030.0})
    assert targets(vs) == {"VTRampStart <= VTRampEnd"}
    assert "WageMin <= 1" in targets(violations({"WageMin": 1.1, "WageMax": 1.3}), "ordered")


def test_denominator() -> None:
    vs = violations({"Share0_M": 0.0, "Share0_S": 0.0, "Share0_J": 1.0})
    assert "Share0_M + Share0_S > 0" in targets(vs, "denominator")


def test_sums() -> None:
    vs = violations({"Share0_J": 0.2})
    assert "Share0_J + Share0_M + Share0_S = 1" in targets(vs, "sum")
    share = dict(Params.baseline().table("SectorShare"))
    first = next(iter(share))
    vs = violations(tables={"SectorShare": {**share, first: share[first] + 1e-6}})
    assert "sum of SectorShare" in targets(vs, "sum")


def test_table_order() -> None:
    amax = dict(Params.baseline().table("amax"))
    a2024 = dict(Params.baseline().table("a2024"))
    vs = violations(tables={"a2024": {**a2024, "APP": amax["APP"] + 0.01}})
    assert "a2024[APP] <= amax[APP]" in targets(vs, "table order")
    vs = violations({"aL_2024": 0.5, "aL_max": 0.4})
    assert "aL_2024 <= aL_max" in targets(vs, "table order")


def test_budget() -> None:
    assert violations({"BudgetShock": 1.0}) == []
    vs = violations({"BudgetShock": 1.0, "ReinvestFrac": 0.0})
    assert targets(vs) == {"BudgetShock = 1 with ReinvestFrac = 0"}


def test_ranges_by_domain() -> None:
    assert targets(violations({"VTEnd": 1.2})) == {"VTEnd"}
    assert targets(violations({"VTBase": -0.1}), "domain") == {"VTBase"}


# ---- 5. calibration identities ---------------------------------------------------------------------------------------


def test_calibration_identity() -> None:
    vs = violations({"A0": 0.4})
    assert any(v.family == "calibration" and v.target.startswith("A0 = ") for v in vs)


def test_calibration_c8_at_its_calibrated_residual() -> None:
    vs = violations({"CostPerBFY0": 104292.0})
    assert targets(vs, "calibration") == {"CostPerBFY0 = 2024 services spend per BFY"}
    vs = violations({"LabourCostPB0_OIT": 43683.0})
    assert targets(vs, "calibration") == {"LabourCostPB0_OIT = 2024 labour cost per effective staff"}


# ---- 6. time constants against dt ------------------------------------------------------------------------------------


def test_dt_rule() -> None:
    assert targets(violations({"TargetClearanceTime": 1e-6}), "dt") == {"TargetClearanceTime"}
    assert targets(violations({"MinDur": 0.01}), "dt") == {"MinDur"}
    assert targets(violations({"QuitRate_J": 16.0}), "dt") == {"QuitRate_J"}
    assert targets(violations({"CancelTime": 0.05}), "dt") == {"CancelTime"}
    # MinFillTime and MinAdoptionTime are 1/16 in the baseline: they meet dt = 1/16 but not dt = 1/8.
    assert targets(violations(dt=1 / 8), "dt") == {"MinFillTime", "MinAdoptionTime"}


# ---- 7. sampled levers -----------------------------------------------------------------------------------------------


def test_sampled_violations_report_runs() -> None:
    starts = [2027.0, 2028.0, 2029.0, 2030.0]
    ends = [2028.0, 2028.0, 2028.5, 2029.0]
    vs = violations(sampled={"VTRampStart": starts, "VTRampEnd": ends})
    assert len(vs) == 1 and vs[0].target == "VTRampStart <= VTRampEnd"
    assert "runs [2, 3]" in vs[0].value and "(2 of 4" in vs[0].value


def test_sampled_support_checked_before_drawing() -> None:
    exp = Experiment(sample={"SrcCostSens": Uniform(-0.1, 1.0)}, n=10, seed=1)
    with pytest.raises(ValidationError) as e:
        run_experiment(exp, outputs=["HeadTotal"])
    assert [(v.family, v.target) for v in e.value.violations] == [("support", "SrcCostSens")]


def test_support_errors_reported_with_the_fixed_checks() -> None:
    """An invalid support is raised together with the checks on fixed values; the per-run checks are skipped."""
    exp = Experiment(
        overrides={"g": 1.5, "VTRampStart": 2031.0, "VTRampEnd": 2030.0},
        sample={"SrcCostSens": Uniform(-0.1, 1.0)},
        n=10,
        seed=1,
    )
    with pytest.raises(ValidationError) as e:
        run_experiment(exp, outputs=["HeadTotal"])
    found = {(v.family, v.target) for v in e.value.violations}
    assert {("support", "SrcCostSens"), ("domain", "g"), ("ordered", "VTRampStart <= VTRampEnd")} <= found
    assert e.value.note == "per-run checks skipped: invalid support for SrcCostSens"
    assert "per-run checks skipped: invalid support for SrcCostSens" in str(e.value)


def test_several_violations_reported_together() -> None:
    vs = violations({"TargetClearanceTime": 1e-6, "A0": 0.4, "Leakage": 3.0, "g": 1.5, "AdoptC0": 0.1})
    families = {v.family for v in vs}
    assert {"dt", "calibration", "no-effect", "domain", "derived"} <= families
    assert [v.family for v in vs] == sorted((v.family for v in vs), key=FAMILIES.index)
    with pytest.raises(ValidationError, match=r"\d+ validation violation"):
        run_experiment(Experiment(overrides={"TargetClearanceTime": 1e-6, "Leakage": 3.0}), outputs=["HeadTotal"])


def test_validate_false_bypasses_everything() -> None:
    exp = Experiment(overrides={"TargetClearanceTime": -1e-6, "Leakage": 3.0})
    with pytest.raises(ValidationError):
        run_experiment(exp, outputs=["HeadTotal"])
    res = run_experiment(exp, outputs=["HeadTotal"], validate=False)
    assert res.series["HeadTotal"].shape == (1, 17)


def test_baseline_and_every_scenario_pass() -> None:
    assert len(SCENARIOS) == 14
    for name in SCENARIOS:
        p, on_top = fixed_params(Experiment(scenario=name))
        validate(p, overrides=on_top)


# ---- AdoptC0 stays as shipped unless its inputs change ---------------------------------------------------------------


def test_adoptc0_kept_bit_equal_unless_inputs_change() -> None:
    base = Params.baseline("phase7").scalars
    shipped = Params.float_of(base, "AdoptC0")
    pC, qC, AC0 = (Params.float_of(base, k) for k in ("pC", "qC", "AC0"))
    assert shipped != (pC + qC * AC0) * (1 - AC0)  # the shipped value is 4e-6 off its formula
    untouched = [name for name, ov in SCENARIOS.items() if not ADOPTC0_INPUTS & ov.keys()]
    assert len(untouched) == 14
    for name in [None, *untouched]:
        for exp in (
            Experiment(scenario=name, model="phase7"),
            Experiment(scenario=name, overrides={}, model="phase7"),
            Experiment(scenario=name, sample={"g": Uniform(0.06, 0.15)}, n=5, seed=3, model="phase7"),
            Experiment(scenario=name, samples=pd.DataFrame({"JuniorCut": [0.3, 0.6]}), model="phase7"),
        ):
            fixed, _ = fixed_params(exp)
            assert fixed.scalars["AdoptC0"] == shipped
            samples = design(exp)
            sampled = {str(c): samples[c].to_numpy() for c in samples.columns}
            scalars, _, _ = batch_arrays(fixed, sampled, len(samples))
            assert (scalars["AdoptC0"] == shipped).all()
    # Overriding or sampling an input recomputes it.
    fixed, _ = fixed_params(Experiment(overrides={"pC": pC}, model="phase7"))
    assert fixed.scalars["AdoptC0"] == (pC + qC * AC0) * (1 - AC0)
    scalars, _, _ = batch_arrays(Params.baseline("phase7"), {"qC": np.array([qC, qC * 2])}, 2)
    assert scalars["AdoptC0"][0] == (pC + qC * AC0) * (1 - AC0)
    assert scalars["AdoptC0"][1] == (pC + qC * 2 * AC0) * (1 - AC0)
