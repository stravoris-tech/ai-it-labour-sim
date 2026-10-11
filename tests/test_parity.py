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
from tests.helpers import parity
from tools.reference_runner import run_base

MAX_REL_DIFF = 0.0


def tornado_draws(n: int = 3, seed: int = 2026) -> list[dict[str, float]]:
    """``n`` draws of every tornado parameter, ``uniform(low, high)`` in ``TORNADO`` order."""
    rng = random.Random(seed)
    return [{p: rng.uniform(lo, hi) for p, lo, hi, _ in TORNADO} for _ in range(n)]


def cases() -> list[tuple[str, dict[str, Any]]]:
    """Every parity case: its ID and its ``run`` keyword arguments (run options plus parameter overrides)."""
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
