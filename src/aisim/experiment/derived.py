"""Derived outputs: quantities computed per run from recorded series, requested by name like row keys.

Each one is computed per run, before any percentile, from series the runner records for it (``Derived.deps``), with
the formulas of recon 04 G2. Totals are sums of lines, so their ratio to 2024 is the ratio of the sum, never the mean
of the lines' ratios.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

import numpy as np

from aisim.batch.util import F
from aisim.dims import VENDORS

INDIA_SCALE: Final[Mapping[str, float]] = MappingProxyType({"Q1_VendIndia": 3.53e6, "Q1_ConsIndia": 1.90e6})
"""People per unit of a Q1 India line's ratio to 2024 (``phase7_runs.py:14``): 2024 people in the line."""

BASE_YEAR: Final = 2024.0


@dataclass(frozen=True, slots=True)
class Derived:
    """A derived output: the keys it needs, how to compute it, and its catalogue entry."""

    name: str
    deps: tuple[str, ...]
    unit: str
    formula: str
    compute: Callable[[Mapping[str, F], F], F]
    max_record_every: float | None = None


def ratio_to_base(a: F, years: F, base_year: float = BASE_YEAR) -> F:
    """Each run's series divided by its own value in ``base_year``. Raises ``ValueError`` if that year is missing."""
    hits = np.flatnonzero(years == base_year)
    if hits.size == 0:
        raise ValueError(f"year {base_year} was not recorded")
    out: F = a / a[:, hits[0] : hits[0] + 1]
    return out


def _onshore(s: Mapping[str, F], years: F) -> F:
    out: F = s["Q1_ConsOnshore"] + s["Q1_VendOnshore"]
    return out


def _india(s: Mapping[str, F], years: F) -> F:
    out: F = s["Q1_ConsIndia"] + s["Q1_VendIndia"]
    return out


def _india_people(line: str) -> Callable[[Mapping[str, F], F], F]:
    def compute(s: Mapping[str, F], years: F) -> F:
        out: F = INDIA_SCALE[line] * ratio_to_base(s[line], years)
        return out

    return compute


def _india_people_total(s: Mapping[str, F], years: F) -> F:
    out: F = _india_people("Q1_VendIndia")(s, years) + _india_people("Q1_ConsIndia")(s, years)
    return out


def _vendor_work_share(s: Mapping[str, F], years: F) -> F:
    out: F = s["WorkShare_OIT"] + s["WorkShare_GSI"] + s["WorkShare_BQ"]
    return out


def _effort_share_revenue_weighted(s: Mapping[str, F], years: F) -> F:
    weighted = s["EffortShare_OIT"] * s["Revenue_OIT"] + s["EffortShare_GSI"] * s["Revenue_GSI"]
    weighted = weighted + s["EffortShare_BQ"] * s["Revenue_BQ"]
    out: F = weighted / s["RevenueTot"]
    return out


def _junior_hiring_ratio(s: Mapping[str, F], years: F) -> F:
    return ratio_to_base(s["HireJ_IN"] + s["HireJ_ON"], years)


_EFFORT = tuple(f"EffortShare_{v}" for v in VENDORS)
_REVENUE = tuple(f"Revenue_{v}" for v in VENDORS)

DERIVED: Final[Mapping[str, Derived]] = MappingProxyType(
    {
        d.name: d
        for d in (
            Derived(
                "OnshoreTotal",
                ("Q1_ConsOnshore", "Q1_VendOnshore"),
                "model-unit persons",
                "Q1_ConsOnshore + Q1_VendOnshore (= HeadLoc_ON)",
                _onshore,
            ),
            Derived(
                "IndiaTotal",
                ("Q1_ConsIndia", "Q1_VendIndia"),
                "model-unit persons",
                "Q1_ConsIndia + Q1_VendIndia (= HeadLoc_IN)",
                _india,
            ),
            Derived(
                "IndiaPeople_ConsIndia",
                ("Q1_ConsIndia",),
                "persons",
                "1.90e6 * Q1_ConsIndia / Q1_ConsIndia[2024] (INDIA_SCALE, phase7_runs.py:14)",
                _india_people("Q1_ConsIndia"),
            ),
            Derived(
                "IndiaPeople_VendIndia",
                ("Q1_VendIndia",),
                "persons",
                "3.53e6 * Q1_VendIndia / Q1_VendIndia[2024] (INDIA_SCALE, phase7_runs.py:14)",
                _india_people("Q1_VendIndia"),
            ),
            Derived(
                "IndiaPeople",
                ("Q1_VendIndia", "Q1_ConsIndia"),
                "persons",
                "IndiaPeople_VendIndia + IndiaPeople_ConsIndia (each line scaled by its own ratio to 2024)",
                _india_people_total,
            ),
            Derived(
                "VendorWorkShare",
                tuple(f"WorkShare_{v}" for v in VENDORS),
                "share",
                "WorkShare_OIT + WorkShare_GSI + WorkShare_BQ (= 1 - WorkShare_IH - WorkShare_GCC)",
                _vendor_work_share,
            ),
            Derived(
                "EffortShare_revenue_weighted",
                (*_EFFORT, *_REVENUE, "RevenueTot"),
                "share",
                "sum_v EffortShare_v * Revenue_v / RevenueTot: effort-billed share of the vendor books, weighted by "
                "vendor revenue (the books are volumes normalised per vendor, so they cannot weight across vendors)",
                _effort_share_revenue_weighted,
            ),
            Derived(
                "JuniorHiringRatio",
                ("HireJ_IN", "HireJ_ON"),
                "ratio (2024 = 1)",
                "(HireJ_IN + HireJ_ON) / (HireJ_IN + HireJ_ON)[2024]; needs record_every <= 0.25 (the calibration "
                "target averages the 2025.75, 2026.0 and 2026.25 rows)",
                _junior_hiring_ratio,
                max_record_every=0.25,
            ),
        )
    }
)
"""The derived outputs, by name."""
