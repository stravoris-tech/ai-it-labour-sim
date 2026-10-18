"""Validation of perturb-from-year and noise inputs (slice 6, rules 8 and 9 of ``aisim.experiment.validate``)."""

from __future__ import annotations

import re
from dataclasses import replace

import pytest

from aisim import Experiment, Noise, Params, Uniform, ValidationError, domains, run_experiment
from aisim.experiment.results import ExperimentResult
from aisim.scenarios import TORNADO, tornado_levers

KEYS = ["HeadTotal"]


def violations(exp: Experiment, stop: float = 16.0) -> list[tuple[str, str]]:
    """``(family, target)`` of every violation ``run_experiment`` raises for ``exp`` (fails if it raises none)."""
    with pytest.raises(ValidationError) as info:
        run_experiment(exp, outputs=KEYS, stop=stop)
    return [(v.family, v.target) for v in info.value.violations]


def runs(exp: Experiment, stop: float = 3.0) -> ExperimentResult:
    return run_experiment(exp, outputs=KEYS, stop=stop)


def test_level_2024_column() -> None:
    """The flag is boolean; it marks the 2024 levels (with the 2024 level split ``Share0_*``, Addendum A) and the
    stored 2024 calibration constants (recon 06 B4)."""
    df = domains()
    assert df["level_2024"].dtype == bool
    marked = set(df.loc[df["level_2024"], "name"])
    explicit = {"Verif", "AICost2024", "GCCMomentum", "A0", "AC0", "CreditCost2024", "OnsiteShare0", "VisaMix0"}
    explicit |= {"VTBase", "aL_2024", "CostPerBFY0", "CostRef", "Share0_J", "Share0_M", "Share0_S"}
    families = (
        *("LabourCostPB0_", "TypeASC_", "SrcASC_", "NormalMargin_", "PriceMult_", "NormalUnempRate_"),
        *("NormalTTF_", "Budget0_", "LOB0_", "Port0_", "Seats0_", "a2024["),
    )
    expected = explicit | {n for n in df["name"] if n.startswith(families)}
    assert marked == expected
    assert len(marked) == 116
    assert not marked & {"g", "VerifDecline", "JuniorCut", "PriceHorizon", "SrcCostSens", "AdoptC0", "amax[APP]"}


def test_level_2024_sampled_raises() -> None:
    """``Verif`` sampled with ``perturb_from`` raises, naming it as a 2024 level."""
    lo, hi = next((lo, hi) for name, lo, hi, _ in TORNADO if name == "Verif")
    exp = Experiment(sample={"Verif": Uniform(lo, hi)}, n=5, seed=1, perturb_from=2026.5)
    with pytest.raises(ValidationError) as info:
        runs(exp)
    (v,) = info.value.violations
    assert (v.family, v.target) == ("level_2024", "Verif") and "a 2024 level" in v.rule


def test_level_2024_override_and_table_raise() -> None:
    a2024 = Params.baseline().table("a2024")
    exp = Experiment(overrides={"AICost2024": 0.5}, tables={"a2024": {**a2024, "APP": 0.1}}, perturb_from=2026.5)
    assert violations(exp) == [("level_2024", "AICost2024"), ("level_2024", "a2024[APP]")]


def test_level_2024_allowed_at_2024_and_without_perturb() -> None:
    lo, hi = next((lo, hi) for name, lo, hi, _ in TORNADO if name == "Verif")
    exp = Experiment(sample={"Verif": Uniform(lo, hi)}, n=3, seed=1)
    assert runs(exp).valid.all()
    assert runs(Experiment(sample={"Verif": Uniform(lo, hi)}, n=3, seed=1, perturb_from=2024.0)).valid.all()


def test_scenario_window_before_y() -> None:
    """Visa crackdown's ramp starts at 2025.7: an error at 2026.5, suggesting a perturb year at or before 2025.7, and
    fine at 2025.5."""
    with pytest.raises(ValidationError) as info:
        runs(Experiment(scenario="Visa crackdown", perturb_from=2026.5))
    (v,) = info.value.violations
    assert (v.family, v.target) == ("window", "visa tightness ramp (VTRampStart)")
    assert "perturb_from <= 2025.7" in v.rule
    assert runs(Experiment(scenario="Visa crackdown", perturb_from=2025.5), stop=2.0).valid.all()


def test_window_rule_covers_overrides_and_samples() -> None:
    """The rule reads the final values: an override of a ramp that started before Y, and ``DemandGrowthLate`` sampled
    with Y after ``LateYear`` (2026.5), where ``G`` would jump."""
    assert violations(Experiment(overrides={"CyberEnd": 1.5}, perturb_from=2026.5)) == [
        ("window", "cyber demand ramp (CyberStart)")
    ]
    dgl = Experiment(sample={"DemandGrowthLate": Uniform(0.015, 0.045)}, n=4, seed=2, perturb_from=2027.0)
    assert violations(dgl) == [("window", "late demand growth (LateYear)")]
    assert runs(Experiment(sample={"DemandGrowthLate": Uniform(0.015, 0.045)}, n=4, seed=2, perturb_from=2026.5))


def test_perturb_year_grid_and_range() -> None:
    assert violations(Experiment(perturb_from=2026.3)) == [("perturb", "perturb_from")]
    assert violations(Experiment(perturb_from=2023.5)) == [("perturb", "perturb_from")]
    assert violations(Experiment(perturb_from=2040.0)) == [("perturb", "perturb_from")]
    assert violations(Experiment(perturb_from=2030.0), stop=6.0) == [("perturb", "perturb_from")]
    assert violations(Experiment(perturb_from=2200.0)) == [("perturb", "perturb_from")] * 2
    with pytest.raises(ValidationError, match=re.escape("domain year: [2000, 2100]")):
        runs(Experiment(perturb_from=2200.0))
    assert runs(Experiment(perturb_from=2026.0), stop=3.0).valid.all()


def test_ai_off_with_perturb_raises() -> None:
    """The AI-off counterfactual runs from 2024 (operator ruling): ``ai_on=False`` with a perturb year raises."""
    with pytest.raises(ValidationError) as info:
        runs(Experiment(ai_on=False, perturb_from=2026.5))
    (v,) = info.value.violations
    assert (v.family, v.target) == ("perturb", "ai_on") and "perturb_from=None" in v.rule
    assert runs(Experiment(ai_on=False)).valid.all()


def test_noise_needs_perturb_from() -> None:
    exp = Experiment(noise={"demand": Noise(0.01)}, noise_seed=1)
    assert violations(exp) == [("noise", "demand")]
    assert runs(Experiment(noise={"demand": Noise(0.0)})).valid.all()


def test_noise_seed_required() -> None:
    assert violations(Experiment(noise={"cap": Noise(0.01)}, perturb_from=2026.5)) == [("noise", "cap")]


def test_noise_sigma_and_tau_bounds() -> None:
    bad = {"cap": Noise(0.6), "demand": Noise(-0.1), "budget": Noise(0.01, tau=0.01), "anchor": Noise(0.01, tau=0.0)}
    found = violations(Experiment(noise=bad, perturb_from=2026.5, noise_seed=1))
    assert found == [
        ("noise", "cap sigma"),
        ("noise", "demand sigma"),
        ("noise", "budget tau"),
        ("noise", "anchor tau"),
    ]
    ok = {"cap": Noise(0.5), "aicost": Noise(0.0), "adoption": Noise(0.01, tau=1 / 16)}
    assert runs(Experiment(noise=ok, perturb_from=2026.5, noise_seed=1)).valid.all()


def test_unknown_noise_channel() -> None:
    assert violations(Experiment(noise={"dem": Noise(0.0)})) == [("noise", "dem")]


def test_violations_are_reported_together() -> None:
    exp = Experiment(
        scenario="Visa crackdown",
        overrides={"AICost2024": 0.5},
        perturb_from=2026.5,
        noise={"cap": Noise(0.9), "x": Noise(0.0)},
    )
    assert violations(exp) == [
        ("level_2024", "AICost2024"),
        ("window", "visa tightness ramp (VTRampStart)"),
        ("noise", "x"),
        ("noise", "cap sigma"),
        ("noise", "cap"),
    ]


def test_unvalidated_noise_still_needs_seed_and_perturb_from() -> None:
    with pytest.raises(ValueError, match="needs perturb_from"):
        run_experiment(Experiment(noise={"cap": Noise(0.1)}, noise_seed=1), outputs=KEYS, validate=False)
    with pytest.raises(ValueError, match="noise_seed"):
        run_experiment(Experiment(noise={"cap": Noise(0.1)}, perturb_from=2026.5), outputs=KEYS, validate=False)


def test_tornado_levers() -> None:
    """All 14 tornado ranges as ``Uniform``; the set depends on the perturb year: 13 at 2026.5 (``Verif``, a 2024
    level, out) and 12 at 2027.0 (``DemandGrowthLate`` out too: its window opens at ``LateYear``, 2026.5)."""
    full = tornado_levers(model="phase7")
    assert list(full) == [name for name, *_ in TORNADO]
    assert all(
        isinstance(d, Uniform) and (d.lo, d.hi) == (lo, hi)
        for (_, lo, hi, _), d in zip(TORNADO, full.values(), strict=True)
    )
    assert len(full) == 14
    assert list(tornado_levers(2026.5)) == [name for name in full if name != "Verif"]
    assert list(tornado_levers(2027.0)) == [name for name in full if name not in ("Verif", "DemandGrowthLate")]


def test_anchored_rates_raise() -> None:
    """``DemandGrowth``, ``ITBudgetGrowth`` and the ``amax`` table drive paths anchored at 2024 that are not
    re-anchored: changed with a perturb year after 2024 they raise, naming the parameter (Addendum A)."""
    amax = Params.baseline().table("amax")
    exp = Experiment(
        overrides={"DemandGrowth": 0.04, "ITBudgetGrowth": 0.01},
        tables={"amax": {**amax, "APP": amax["APP"] + 0.05}},
        perturb_from=2026.5,
    )
    with pytest.raises(ValidationError) as info:
        runs(exp)
    found = info.value.violations
    assert [(v.family, v.target) for v in found] == [
        ("anchored_rate", "DemandGrowth"),
        ("anchored_rate", "ITBudgetGrowth"),
        ("anchored_rate", "amax[APP]"),
    ]
    assert all("anchored at 2024 and is not re-anchored" in v.rule and "perturb_from=None" in v.rule for v in found)
    assert runs(replace(exp, perturb_from=None)).valid.all()
    assert runs(replace(exp, perturb_from=2024.0)).valid.all()


def test_phase2_without_a_recorded_row_raises() -> None:
    """With ``perturb_from`` set, a ``record_every`` that records no step from Y to the stop raises a clear
    ``ValueError`` in ``execute``, with or without validation (it was a bare ``KeyError``); a recording grid that
    reaches Y still runs."""
    exp = Experiment(sample={"g": Uniform(0.06, 0.15)}, n=2, seed=1, perturb_from=2026.5)
    with pytest.raises(ValueError, match="records no row"):
        run_experiment(exp, outputs=["HeadTotal"], stop=2.5625, record_every=1.0, workers=1)
    with pytest.raises(ValueError, match="records no row"):
        run_experiment(exp, outputs=["HeadTotal"], stop=2.5625, record_every=1.0, workers=1, validate=False)
    ok = run_experiment(exp, outputs=["HeadTotal"], stop=2.5625, record_every=0.25, workers=1)
    assert ok.years[-1] == 2026.5
