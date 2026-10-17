"""The E2a annuity pricing term (slice 8) and the ``PNew`` extras, in both engines.

``PNew_TM = ((1 - AnnuityShare) + AnnuityShare x Anchor ** AnnuityAnchorW) x (1 - Disc)``; FP, MS, OB and SA prices
are unchanged. There is no prototype for it, so the scalar engine is the oracle and batch-scalar parity the
cross-check.

- At ``AnnuityShare`` 0 the term is exactly 1.0, whatever ``AnnuityAnchorW``: tested, not assumed.
- At 0.3 / 0.4 the engines agree on ten mixed runs, from 2024 and two-phase with anchor noise.
- Integrity holds at the domain extremes (0 and 1) of both parameters.
- ``PNew_<v>_TM`` is exactly ``1 - Disc_<v>`` at the defaults.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from aisim import BatchParams, Experiment, Noise, Params, run, run_batch, run_experiment
from aisim.batch.state import pack, unpack
from aisim.dims import TYPES, VENDORS
from aisim.noise import ou_factors
from aisim.perturb import run_batch_from, run_from, start_step_of
from aisim.scenarios import EXTREME, SCENARIOS
from aisim.state import load_initial_state
from tests.helpers import people
from tests.test_batch_parity import ALL_CASES, Case, compare_run
from tests.test_noise import assert_bit_identical, scalar_noise
from tests.test_perturb import assert_batches_identical, assert_scalar_identical

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The parity tests here need numpy's kernels to match libm (``tests/conftest.py``)."""

E2A = {"AnnuityShare": 0.3, "AnnuityAnchorW": 0.4}
NEUTRAL = ({"AnnuityShare": 0.0, "AnnuityAnchorW": 0.0}, {"AnnuityShare": 0.0, "AnnuityAnchorW": 0.4})
BASE = Params.baseline("phase7")
DT = 1 / 16
Y = 2026.5


def with_e2a(case: Case, e2a: Mapping[str, float]) -> Case:
    return replace(case, overrides={**case.overrides, **e2a})


@pytest.mark.parametrize("e2a", NEUTRAL, ids=["share 0, weight 0", "share 0, weight 0.4"])
def test_annuity_share_zero_is_bit_identical_on_the_27_cases(e2a: dict[str, float]) -> None:
    """``AnnuityShare`` 0 reproduces the default bit for bit (rows, final state, mins, ``finite``) on the 27-case
    batch, with the anchor weight at 0 and at 0.4: the term is exactly 1.0 without a branch. Three scalar runs too."""
    groups = [[c for c in ALL_CASES.values() if c.dt == DT], [ALL_CASES["base, dt 1/32"]]]
    assert sum(len(g) for g in groups) == 27
    for cases in groups:
        init = pack([c.state() for c in cases])
        ai = [c.ai_on for c in cases]
        dt = cases[0].dt
        default = run_batch(BatchParams.stack([c.params() for c in cases]), init, ai_on=ai, dt=dt)
        neutral = run_batch(BatchParams.stack([with_e2a(c, e2a).params() for c in cases]), init, ai_on=ai, dt=dt)
        assert_batches_identical(default, neutral)
    for name in ("scenario Base", "EXTREME", "base, dt 1/32"):
        case = ALL_CASES[name]
        assert_scalar_identical(case.scalar(record_every=1.0), with_e2a(case, e2a).scalar(record_every=1.0))


def test_e2a_changes_only_tm_prices_after_2024() -> None:
    """The mechanism acts: at 0.3 / 0.4 the TM new-signing price differs from Phase 7's after 2024, the other types'
    do not differ in 2024, and the 2024 row equals Phase 7's bit for bit (the design is neutral in 2024)."""
    keys = [f"PNew_{v}_{k}" for v in VENDORS for k in TYPES]
    a = run_batch(BatchParams.stack([BASE, BASE.with_overrides(**E2A)]), outputs=[*keys, "HeadTotal", "RevenueTot"])
    for key, s in a.series.items():
        assert s[0, 0] == s[1, 0], key
    for v in VENDORS:
        assert not np.array_equal(a.series[f"PNew_{v}_TM"][0], a.series[f"PNew_{v}_TM"][1]), v
    p7, p8 = run(BASE, record_every=1.0), run(BASE.with_overrides(**E2A), record_every=1.0)
    assert p7.rows[0] == p8.rows[0]


MIXED_2024 = [
    BASE.with_overrides(**E2A),
    BASE.with_overrides(**SCENARIOS["Fast AI"], **E2A),
    BASE.with_overrides(**SCENARIOS["Slow AI"], **E2A),
    BASE.with_overrides(**EXTREME, **E2A),
    BASE.with_overrides(g=0.12, PriceHorizon=5.0, TMBrake=0.25, PassThrough=0.75, **E2A),
]
MIXED_TWO_PHASE = [
    BASE.with_overrides(**E2A),
    BASE.with_overrides(**SCENARIOS["Fast AI"], **E2A),
    BASE.with_overrides(AICostDecline=0.2, JevonsEps=0.4, SrcCostSens=2.5, **E2A),
    BASE.with_overrides(PassThrough=0.75, PriceHorizon=6.0, **E2A),
    BASE.with_overrides(AnnuityShare=0.5, AnnuityAnchorW=0.3),
]


def test_parity_from_2024() -> None:
    """Five runs from 2024 at the E2a values: batch against the scalar oracle within 1e-12 (rows, final state, mins)."""
    batch = run_batch(BatchParams.stack(MIXED_2024), record_every=1.0)
    assert batch.finite.all()
    for i, p in enumerate(MIXED_2024):
        cmp = compare_run(batch, i, run(p, record_every=1.0))
        assert cmp.miss is None, (i, cmp.miss)


def test_parity_two_phase_with_anchor_noise() -> None:
    """Five two-phase runs at Y = 2026.5 with noise on the anchor (and on demand): bit-identical."""
    noise = {"anchor": Noise(0.1, 1.0), "demand": Noise(0.05, 2.0)}
    factors = ou_factors(noise, 41, range(len(MIXED_TWO_PHASE)), start_step=start_step_of(Y, DT), steps=256, dt=DT)
    batch = run_batch_from(BatchParams.stack(MIXED_TWO_PHASE), Y=Y, record_every=0.25, noise=factors, base=BASE)
    assert batch.finite.all()
    for i, p in enumerate(MIXED_TWO_PHASE):
        assert_bit_identical(batch, i, run_from(BASE, p, Y=Y, record_every=0.25, noise=scalar_noise(factors, i)))


def test_integrity_at_the_domain_extremes() -> None:
    """``AnnuityShare`` and ``AnnuityAnchorW`` at 0 and 1, alone and under ``EXTREME``: finite, people conserved,
    ``WorkCheckMax`` at round-off, no negative stocks, book and signing shares summing to 1."""
    grid = [(a, w) for a in (0.0, 1.0) for w in (0.0, 1.0)]
    samples = pd.DataFrame(grid, columns=["AnnuityShare", "AnnuityAnchorW"])
    mix = [f"Mix_{v}_{k}" for v in VENDORS for k in TYPES]
    sign = [f"Sign_{v}_{k}" for v in VENDORS for k in TYPES]
    keys = ["Grad_total", "Ext_total", "WorkCheckMax", *mix, *sign]
    for over in ({}, dict(EXTREME)):
        res = run_experiment(
            Experiment(overrides=over, samples=samples), outputs=keys, record_every=DT, keep_state=True, workers=1
        )
        assert res.valid.all() and res.final_state is not None and res.mins is not None
        s = res.series
        start = people(load_initial_state())
        for i in range(res.n):
            inflow = float(np.sum((s["Grad_total"][i, :-1] + s["Ext_total"][i, :-1]) / 16))
            total = people(unpack(res.final_state, i))
            assert abs(total - start - inflow) <= 1e-9 * total, (over, grid[i])
        assert np.max(s["WorkCheckMax"]) <= 1e-9
        assert min(float(np.min(a)) for a in res.mins.values()) >= -1e-12
        for v in VENDORS:
            for fam in ("Mix_", "Sign_"):
                assert np.max(np.abs(sum(s[f"{fam}{v}_{k}"] for k in TYPES) - 1)) <= 1e-12, (fam, v)
        assert all(np.isfinite(a).all() for a in s.values())


def test_pnew_tm_is_one_minus_disc_at_the_defaults() -> None:
    """At the defaults the TM (and SA) new-signing price is exactly ``1 - Disc_<v>``, in both engines, every step."""
    keys = [f"PNew_{v}_{k}" for v in VENDORS for k in ("TM", "SA")] + [f"Disc_{v}" for v in VENDORS]
    batch = run_batch(BatchParams.stack([BASE, BASE.with_overrides(**SCENARIOS["Fast AI"])]), outputs=keys)
    for v in VENDORS:
        for k in ("TM", "SA"):
            assert np.array_equal(batch.series[f"PNew_{v}_{k}"], 1 - batch.series[f"Disc_{v}"]), (v, k)
    res = run(BASE, record_every=DT, extras=True)
    assert res.extras is not None
    for row, extra in zip(res.rows, res.extras, strict=True):
        for v in VENDORS:
            assert extra[f"PNew_{v}_TM"] == 1 - row[f"Disc_{v}"], (v, row["year"])
