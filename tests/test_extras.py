"""The extras: outputs recorded apart from the 317 prototype rows, in both engines.

The batched extras match the scalar extras within 1e-12 on the 27 parity cases; recording extras leaves the rows
bit-identical; and each extras family satisfies an identity with the row keys where one exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pytest

from aisim import Params, run, run_batch
from aisim.batch.params import BatchParams
from aisim.batch.record import EXTRA_KEYS, ROW_KEYS
from aisim.batch.state import pack
from aisim.dims import EMPLOYERS, REGIONS, SECTORS, TYPES, UNITS, VENDORS
from aisim.scalar.record import EXTRA_KEYS as SCALAR_EXTRA_KEYS
from aisim.scenarios import EXTREME
from tests.test_batch_parity import ALL_CASES, Case, Comparison

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""Batch-scalar parity needs numpy's kernels to match libm (``tests/conftest.py``)."""

RECORD_EVERY = 1.0


def batch_extras(cases: Sequence[Case]) -> dict[str, np.ndarray]:
    (dt,) = {c.dt for c in cases}
    params = BatchParams.stack([c.params() for c in cases])
    init = pack([c.state() for c in cases])
    res = run_batch(params, init, ai_on=[c.ai_on for c in cases], dt=dt, record_every=RECORD_EVERY, outputs=EXTRA_KEYS)
    assert tuple(res.series) == EXTRA_KEYS
    return dict(res.series)


def test_extra_keys_agree() -> None:
    assert EXTRA_KEYS == SCALAR_EXTRA_KEYS
    assert len(EXTRA_KEYS) == 81
    assert not set(EXTRA_KEYS) & set(ROW_KEYS)


def test_batch_extras_match_scalar_extras() -> None:
    cases = list(ALL_CASES.values())
    assert len(cases) == 27
    for dt in sorted({c.dt for c in cases}):
        group = [c for c in cases if c.dt == dt]
        series = batch_extras(group)
        for i, case in enumerate(group):
            scalar = run(
                case.params(), case.state(), ai_on=case.ai_on, dt=case.dt, record_every=RECORD_EVERY, extras=True
            )
            assert len(scalar.extras) == len(scalar.rows)
            cmp = Comparison()
            for key in EXTRA_KEYS:
                cmp.check(series[key][i], np.array([e[key] for e in scalar.extras]), f"extras/{key}")
            assert cmp.miss is None, f"{case.name}: {cmp.miss}"


@pytest.mark.parametrize("overrides", [{}, dict(EXTREME)], ids=["base", "extreme"])
def test_rows_unchanged_by_extras(overrides: dict[str, float]) -> None:
    p = Params.baseline().with_overrides(**overrides) if overrides else Params.baseline()
    a = run(p, record_every=0.25)
    b = run(p, record_every=0.25, extras=True)
    assert a.rows == b.rows and a.final_state == b.final_state and a.mins == b.mins
    assert a.extras == [] and len(b.extras) == len(b.rows)
    bp = BatchParams.stack([p])
    plain = run_batch(bp)
    both = run_batch(bp, outputs=[*ROW_KEYS, *EXTRA_KEYS])
    assert tuple(plain.series) == ROW_KEYS
    assert tuple(both.series) == (*ROW_KEYS, *EXTRA_KEYS)
    for key in ROW_KEYS:
        assert np.array_equal(plain.series[key], both.series[key]), key


@pytest.mark.parametrize("overrides", [{}, dict(EXTREME)], ids=["base", "extreme"])
def test_extras_identities(overrides: dict[str, float]) -> None:
    p = Params.baseline().with_overrides(**overrides) if overrides else Params.baseline()
    res = run(p, record_every=0.25, extras=True)
    tol = 1e-12
    prev: dict[str, float] | None = None
    for row, e in zip(res.rows, res.extras, strict=True):
        for v in VENDORS:
            book = sum(e[f"Book_{v}_{k}"] for k in TYPES)
            sign = sum(e[f"SignVol_{v}_{k}"] for k in TYPES)
            for k in TYPES:
                # Book shares are the Mix_ shares, signing shares the Sign_ shares.
                assert e[f"Book_{v}_{k}"] / book == pytest.approx(row[f"Mix_{v}_{k}"], rel=tol, abs=tol)
                assert e[f"SignVol_{v}_{k}"] / sign == pytest.approx(row[f"Sign_{v}_{k}"], rel=tol, abs=tol)
            # The signing-weighted new-contract duration is AvgNewDur_.
            dur = sum(row[f"Sign_{v}_{k}"] * e[f"Dnew_{v}_{k}"] for k in TYPES)
            assert dur == pytest.approx(row["AvgNewDur_" + v], rel=tol)
        # Committed spend less the seat, credit and cloud parts is the services spend.
        services = sum(
            row["Committed_" + x] - e["SeatSpend_" + x] - e["CreditSpend_" + x] - e["CloudSpend_" + x] for x in SECTORS
        )
        assert services == pytest.approx(row["ServicesSpend"], rel=1e-9)
        # Completion is capped by capacity.
        for emp in EMPLOYERS:
            assert row["CompE_" + emp] <= e["CapE_" + emp]
        # The wage index stays inside its clamp (it starts at 1 and moves toward a clamped target).
        lo, hi = min(1.0, p.float_of(p.scalars, "WageMin")), max(1.0, p.float_of(p.scalars, "WageMax"))
        assert all(lo <= e["WI_" + u] <= hi for u in UNITS)
        # People only flow into LeftField.
        if prev is not None:
            assert all(e["LeftField_" + r] >= prev["LeftField_" + r] for r in REGIONS)
        prev = e
