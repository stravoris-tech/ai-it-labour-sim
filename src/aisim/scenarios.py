"""Named scenarios, tornado ranges and the extreme test case, from ``phase7_runs.py``.

- ``SCENARIOS``: the 14 named scenarios of ``SCEN`` (lines 16-31), as overrides of the baseline parameters.
- ``TORNADO``: the 14 one-at-a-time sensitivity ranges of ``TORNADO`` (lines 32-47), as ``(name, low, high, label)``.
  The ``Verif`` and ``JuniorCut`` ranges are relative to their baseline values, as in the prototype.
- ``EXTREME``: the overrides of integrity test T4 in ``tests()`` (lines 98-99), which exercise abandonment and layoffs.

Spec: 07 (scenarios and the tornado).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from aisim.params import Params


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


def _tornado() -> tuple[tuple[str, float, float, str], ...]:
    base = Params.baseline().scalars
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


TORNADO: Final = _tornado()
"""The 14 tornado parameters: ``(name, low, high, label)``."""

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
