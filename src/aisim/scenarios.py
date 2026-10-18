"""Named scenarios, tornado ranges and the extreme test case, from ``phase7_runs.py``.

- ``SCENARIOS``: the 14 named scenarios of ``SCEN`` (lines 16-31), as overrides of the baseline parameters.
- ``TORNADO``: the 14 one-at-a-time sensitivity ranges of ``TORNADO`` (lines 32-47), as ``(name, low, high, label)``.
  The ``Verif`` and ``JuniorCut`` ranges are relative to their baseline values, as in the prototype.
- ``EXTREME``: the overrides of integrity test T4 in ``tests()`` (lines 98-99), which exercise abandonment and layoffs.
- ``STRUCTURAL_LEVERS``: per model, the strengths of the model's structural feedback loops with their evidence
  ranges (today ``phase9`` only, the eight loop strengths of slice 12).
- ``tornado_levers(perturb_from, model)``: the tornado ranges, then the model's structural levers, as ``Uniform``
  distributions for a Monte Carlo. The set depends on the perturb year: it drops every lever whose range cannot act
  from that year (``Verif`` from 2026.5; also ``DemandGrowthLate`` from 2027).

Spec: 07 (scenarios and the tornado).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from aisim.params import Params
from aisim.state import DEFAULT_MODEL

if TYPE_CHECKING:
    from aisim.experiment.sampling import Uniform


def _frozen(d: dict[str, float]) -> Mapping[str, float]:
    return MappingProxyType(d)


SCENARIOS: Final[Mapping[str, Mapping[str, float]]] = MappingProxyType(
    {
        "Base": _frozen({}),
        "Slow AI": _frozen({"g": 0.05, "VerifDecline": 0.0}),
        "Fast AI": _frozen({"g": 0.20, "VerifDecline": 0.10}),
        "Strict regulation": _frozen({"RegScenario": 1.5}),
        "Light regulation": _frozen({"RegScenario": 0.5}),
        "Compute shock": _frozen({"AIShockMult": 3.0, "AIShockStart": 2027.0, "AIShockEnd": 2029.5}),
        "Visa crackdown": _frozen({"VTEnd": 0.8, "VTRampStart": 2025.7, "VTRampEnd": 2027.7}),
        "Visa relaxation": _frozen({"VTEnd": 0.1, "VTRampStart": 2027.0, "VTRampEnd": 2028.0}),
        "Downturn": _frozen({"BudgetShock": 0.15, "BudgetShockStart": 2027.0, "BudgetShockEnd": 2029.0}),
        "Jevons rebound": _frozen({"JevonsEps": 0.5}),
        "Demand stalls": _frozen({"DemandGrowthLate": 0.0}),
        "Demand boom": _frozen({"DemandGrowthLate": 0.05}),
        "GCC wave persists": _frozen({"GCCAppealKeep": 1.0}),
        "GCC wave fades": _frozen({"GCCAppealKeep": 0.0}),
    }
)
"""The 14 named scenarios: scenario name to parameter overrides."""


def _tornado(model: str) -> tuple[tuple[str, float, float, str], ...]:
    """The 14 tornado ranges of ``model``: ``Verif`` and ``JuniorCut`` relative to that model's values (the
    prototype's x0.7/x1.3 and x0.5/x1.5), every other range by hand and the same in every model."""
    base = Params.baseline(model).scalars
    verif = Params.float_of(base, "Verif")
    junior_cut = Params.float_of(base, "JuniorCut")
    return (
        ("g", 0.06, 0.15, "AI capability growth g"),
        ("DemandGrowthLate", 0.015, 0.045, "Underlying demand growth after 2026"),
        ("Verif", verif * 0.7, verif * 1.3, "Verification overhead (2024)"),
        ("VerifDecline", 0.0, 0.10, "Verification decline per year"),
        ("JevonsEps", 0.0, 0.5, "Jevons elasticity"),
        ("GCCAppealKeep", 0.0, 1.0, "GCC appeal kept after 2030"),
        ("JuniorCut", junior_cut * 0.5, junior_cut * 1.5, "Junior cut per unit of adoption"),
        ("TMBrake", 0.2, 0.6, "T&M brake on vendor adoption"),
        ("PriceHorizon", 4.0, 8.0, "Client price horizon (years)"),
        ("aL_max", 0.25, 0.45, "Max business-process automation"),
        ("SrcCostSens", 2.0, 4.0, "Sourcing cost sensitivity"),
        ("AICostDecline", 0.08, 0.25, "AI cost decline per year"),
        ("RegScenario", 0.5, 1.5, "Regulation strength"),
        ("EnrolSensitivity", 0.5, 1.5, "Enrolment response to unemployment"),
    )


STRUCTURAL_LEVERS: Final[Mapping[str, tuple[tuple[str, float, float, str], ...]]] = MappingProxyType(
    {
        "phase9": (
            ("kR7", 0.15, 0.75, "R7 GCC scale-learning strength"),
            ("R6Theta", 0.65, 0.92, "R6 relative-viability threshold"),
            ("R6e", 0.002, 0.012, "R6 capacity exit per margin point"),
            ("kViab", 0.0, 10.6511, "R6 client-flight strength"),
            ("PriceFloor", 0.85, 1.08, "R6 new-bid price floor (x expected cost)"),
            ("AIDiscCeil", 0.20, 0.45, "R6 AI-discount ceiling"),
            ("R10rc", 0.0748, 0.3223, "R10 replacement cost per excess voluntary exit (years of wage)"),
            ("R4a", 0.0, 0.25, "R4 skill-erosion strength (onshore)"),
        ),
    }
)
"""Per model, the structural levers ``tornado_levers`` appends after the tornado: ``(name, low, high, label)``.

A model is listed here only if its structure has strengths that the calibration data do not pin, so that their
uncertainty enters a Monte Carlo through these ranges. Today that is ``phase9``, whose eight loop strengths (slice 12;
``docs/model-changes-phase9.md``) come with the low and high values of the loop-strength evidence report
(``docs/research/loop-strength-evidence.md``) by section:

- ``kR7`` 0.15-0.75: section R7 ("Translating share drift into kR7"), the low 0.15 and base 0.4; the high is 0.75, not
  the report's 0.8, so that the stability measure ``kR7 x (1 - WS_2024)`` stays below the report's 0.7 ("Divestitures
  and parent stress argue for a capped, reversible form"): 0.676 at WS_2024 = 0.0984.
- ``R6Theta`` 0.65-0.92 and ``R6e`` 0.002-0.012: section R6 ("Cuts start on relative shortfall").
- ``kViab`` 0-10.6511: section R6 (client flight as the dominant channel; Atos's bookings), translated by recon 12b C3:
  0 is no client flight, and 5.8562 (the base) and 10.6511 reproduce Atos's -21.5% signings at OIT's relative-
  viability trough 0.25 and 0.47 with the 2-year fade.
- ``PriceFloor`` 0.85-1.08 and ``AIDiscCeil`` 0.20-0.45: section R6 ("Price floors bend toward expected cost, and AI
  discount asks cluster at 20-30%").
- ``R10rc`` 0.0748-0.3223: section R10 ("a 100-200 bps margin cost per doubling"), translated by recon 12b D: OIT's
  margin falls 100, 150 and 200 bps at voluntary-attrition ratios of 2.3, 1.8 and 1.6.
- ``R4a`` 0-0.25: section R4 ("kR4 belongs near 0.1, ideally inside a threshold-saturation form"). ``R4aIN`` is held at
  its base 0.10, at or below onshore.

The shape parameters (``R7Lcap``, ``R6Cap``, ``R6MargTime``, ``C4FadeTime``, ``C4Cap``, ``MinSeekTime``) are held at
the model's values. Every other model has no structural levers, so its ``tornado_levers`` is the tornado alone.
"""


TORNADO: Final = _tornado("phase7")
"""The Phase 7 tornado, the prototype's 14 parameters: ``(name, low, high, label)``.

It is built from ``Params.baseline("phase7")`` explicitly, not from the default model, so it stays the prototype's
ranges (``phase7_runs.py:32-47``) whatever the default. For another model's ranges use ``tornado_levers(model=...)``.
"""


def tornado_levers(perturb_from: float | None = None, model: str = DEFAULT_MODEL) -> dict[str, Uniform]:
    """The tornado ranges of ``model`` as ``{name: Uniform(low, high)}``, in ``TORNADO`` order, then the model's
    structural levers (``STRUCTURAL_LEVERS``) in their table order.

    **The ranges are computed per model.** ``Verif`` and ``JuniorCut`` are x0.7/x1.3 and x0.5/x1.5 of the model's own
    values, the prototype's ratios; every other range is the prototype's hand-set range, the same in every model. So
    ``tornado_levers(model="phase7")`` gives exactly ``TORNADO``'s ranges. Two ranges are not re-centred, by choice:
    ``PriceHorizon`` (4-8) sits at 0.75 of its range on ``phase8``, and ``JevonsEps`` (0-0.5) is one-sided from 0 by
    design (a centred range would cross its lower bound 0).

    **The lever set depends on the perturb year.** With ``perturb_from`` set, a lever is dropped when its lower or upper
    bound, applied as an override with that perturb year, fails validation (``aisim.experiment.validate``, at dt = 1/16
    and stop = 16): a 2024 level such as ``Verif`` cannot act from a later year, and a lever whose window starts
    before Y, such as ``DemandGrowthLate`` (after ``LateYear``, 2026.5), would change the run before Y. All 14 remain
    with None, 13 at 2026.5 (``Verif`` out) and 12 at 2027.0 (``Verif`` and ``DemandGrowthLate`` out). The structural
    levers pass the same test.

    ``model`` (``aisim.state.BASELINE_FILES``) is the baseline the bounds are applied to and validated against.
    """
    from aisim.experiment.sampling import Uniform
    from aisim.experiment.validate import ValidationError, validate

    out: dict[str, Uniform] = {}
    base = Params.baseline(model)
    for name, lo, hi, _ in (*_tornado(model), *STRUCTURAL_LEVERS.get(model, ())):
        if perturb_from is not None:
            try:
                for v in (lo, hi):
                    validate(
                        base.with_overrides(**{name: v}), overrides={name: v}, perturb_from=perturb_from, model=model
                    )
            except ValidationError:
                continue
        out[name] = Uniform(lo, hi)
    return out


EXTREME: Final[Mapping[str, float]] = MappingProxyType(
    {
        "g": 0.5,
        "VerifDecline": 0.3,
        "JevonsEps": 1.0,
        "AIShockMult": 5.0,
        "BudgetShock": 0.6,
        "RegScenario": 2.5,
        "VTEnd": 1.0,
        "GCCAppealKeep": 2.0,
        "PriceShock_OIT": 0.5,
        "DemandGrowthLate": -0.03,
        "aL_max": 0.9,
    }
)
"""The overrides of integrity test T4 (extreme case)."""
