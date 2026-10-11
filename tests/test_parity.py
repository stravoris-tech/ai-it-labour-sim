"""The port reproduces a fresh prototype run bit for bit, on this machine and interpreter.

Every case compares every row key (names and order), the final state and ``mins``. Required: a maximum relative
difference of exactly 0.0.
"""

from __future__ import annotations

import math
import random
from typing import Any

import pytest

from aisim import SCENARIOS, Params, run
from aisim.scenarios import EXTREME, TORNADO
from tests.helpers import init_state, load_coverage_cases, parity, port_dict
from tools.reference_runner import iter_numeric_pairs, run_base

MAX_REL_DIFF = 0.0


def tornado_draws(n: int = 3, seed: int = 2026) -> list[dict[str, float]]:
    """``n`` draws of every tornado parameter, ``uniform(low, high)`` in ``TORNADO`` order."""
    rng = random.Random(seed)
    return [{p: rng.uniform(lo, hi) for p, lo, hi, _ in TORNADO} for _ in range(n)]


# Any: run keyword arguments mix run options (bool, float) with parameter overrides (float or None).
def cases() -> list[tuple[str, dict[str, Any]]]:
    """Every parity case: its ID and its ``run`` keyword arguments (run options plus parameter overrides)."""
    # Any: as for cases(), the keyword arguments mix bool and float values.
    out: list[tuple[str, dict[str, Any]]] = [
        ("base, every step", {"record_every": 1 / 16}),
        ("AI off, every step", {"ai_on": False, "record_every": 1 / 16}),
        ("base, dt 1/32", {"dt": 1 / 32, "record_every": 0.25}),
    ]
    out += [(f"scenario {name}", {"record_every": 1.0, **over}) for name, over in SCENARIOS.items()]
    out.append(("EXTREME", {"record_every": 1.0, **EXTREME}))
    out.append(("Burn", {"record_every": 1.0, "Burn": 1.0}))
    out.append(("FreezeSourcing", {"record_every": 1.0, "FreezeSourcing": 1.0}))
    out += [(f"tornado draw {i + 1}", {"record_every": 1.0, **d}) for i, d in enumerate(tornado_draws())]
    return out


CASES = cases()


def test_case_count() -> None:
    assert len(CASES) == 3 + 14 + 1 + 2 + 3


@pytest.mark.parametrize("kwargs", [kw for _, kw in CASES], ids=[name for name, _ in CASES])
# Any: as for cases(), the keyword arguments mix bool and float values.
def test_bit_identical(kwargs: dict[str, Any]) -> None:
    diff, where = parity(run(**kwargs), run_base(**kwargs))
    assert diff <= MAX_REL_DIFF, f"max rel diff {diff:.3e} at {where}"


def test_parity_detects_a_one_ulp_change() -> None:
    """Positive control: nudging one parameter by one ulp must show up as a non-zero difference.

    ``AICost2024`` multiplies straight into ``AICostPerUnit``. (A one-ulp nudge of ``g`` would not do: ``g`` only enters
    as ``1 - g``, which rounds to the same double.)
    """
    cost = Params.baseline().scalars["AICost2024"]
    assert cost is not None
    nudged = run(record_every=1.0, AICost2024=math.nextafter(cost, math.inf))
    diff, where = parity(nudged, run_base(record_every=1.0))
    assert diff > 0.0, where


COVERAGE = {case.name: case for case in load_coverage_cases()}


def test_coverage_case_names() -> None:
    assert list(COVERAGE) == ["zero_start", "ai_regress", "lever_extremes", "ramp_step"]


@pytest.mark.parametrize("name", ["zero_start", "ai_regress", "lever_extremes"])
def test_coverage_case_bit_identical(name: str) -> None:
    """The guard-coverage cases (recon 03 B3) bind the 39 sites the 23 cases miss; the port matches the prototype."""
    case = COVERAGE[name]
    port = run(Params.baseline().with_overrides(**case.overrides), init_state(case.init_edits), record_every=1.0)
    # Any: run_base takes parameter overrides through **kwargs next to its typed run options.
    overrides: dict[str, Any] = dict(case.overrides)
    proto = run_base(record_every=1.0, init_edits=case.init_edits, **overrides)
    diff, where = parity(port, proto)
    assert diff <= MAX_REL_DIFF, f"max rel diff {diff:.3e} at {where}"


def test_ramp_step_runs_finite() -> None:
    """``ramp`` with start equal to end is a step in the port; the prototype raises on it, so there is no comparison."""
    case = COVERAGE["ramp_step"]
    result = run(Params.baseline().with_overrides(**case.overrides), init_state(case.init_edits), record_every=1.0)
    assert len(result.rows) == 17
    values = [x for _, x, _ in iter_numeric_pairs(port_dict(result), port_dict(result))]
    assert values
    assert all(math.isfinite(x) for x in values)
