"""Integrity checks on the port: T1 growth path, T2 people conservation, no negative stocks."""

from __future__ import annotations

import pytest

from aisim import Params, load_initial_state, run
from aisim.scenarios import EXTREME
from tests.helpers import annual, people

# Recon H: the base run's V_OL_S reaches -3.55e-15, so the floor allows roundoff below zero.
MIN_STOCK = -1e-12


def test_t1_ai_off_growth_path() -> None:
    rows = run(ai_on=False, record_every=1.0).rows
    ann = annual(rows)
    h2024 = ann[2024]["HeadTotal"]
    max_dev = max(abs(r["HeadTotal"] / h2024 / r["G"] - 1) for r in ann.values())
    assert max_dev < 0.012


def test_t2_people_conservation() -> None:
    """Everyone is accounted for: the change in people equals graduates plus external entrants (``phase7_runs.py``)."""
    result = run(record_every=1 / 16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in result.rows[:-1])
    total = people(result.final_state)
    residual = total - people(load_initial_state()) - inflow
    assert abs(residual) <= 1e-9 * total


@pytest.mark.parametrize("case", ["base", "EXTREME"])
def test_no_negative_stocks(case: str) -> None:
    params = Params.baseline().with_overrides(**(EXTREME if case == "EXTREME" else {}))
    mins = run(params, record_every=1.0).mins
    assert len(mins) == 3 * 8 * 3 + 2 * 2 * 3 + 7 * 5 + 3 * 5 * 4
    worst = min(mins, key=lambda k: mins[k])
    assert mins[worst] >= MIN_STOCK, f"{worst} = {mins[worst]!r}"
