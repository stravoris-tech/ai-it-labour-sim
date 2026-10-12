"""Perturb from year Y (slice 6): the engines' restart options and the two-phase run (``aisim.perturb``).

- The new engine arguments at their defaults reproduce a plain run bit for bit.
- A restart at Y on the dt grid is exact (recon 06 B2), and Y = 2024 equals a plain run.
- Before Y every run is the calibrated baseline: zero band width (B7).
- The five 2024-anchored paths are re-anchored at Y, so the rate levers do not jump there (B5); the levers whose own
  effect is immediate are recorded as expected jumps.
- The two-phase run is the same in both engines, and does not depend on the workers or the chunking.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import replace

import numpy as np
import pytest

from aisim import BatchParams, Experiment, Params, run, run_batch, run_experiment
from aisim.batch.engine import BatchResult
from aisim.batch.state import BatchState, pack
from aisim.batch.util import F
from aisim.experiment.results import pct
from aisim.perturb import phase1, run_batch_from, run_from
from aisim.scalar.engine import RunResult
from aisim.scenarios import SCENARIOS, TORNADO, tornado_levers
from tests.test_batch_parity import ALL_CASES, Case, assert_run_identical

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The parity tests here need numpy's kernels to match libm (``tests/conftest.py``)."""

DT = 1 / 16
Y_GRID = (2026.0, 2026.5, 2027.0)
BASE = Params.baseline()
RANGE = {name: (lo, hi) for name, lo, hi, _ in TORNADO}


def batch_inputs(cases: Sequence[Case]) -> tuple[BatchParams, BatchState, list[bool], float]:
    dts = {c.dt for c in cases}
    assert len(dts) == 1
    return (
        BatchParams.stack([c.params() for c in cases]),
        pack([c.state() for c in cases]),
        [c.ai_on for c in cases],
        dts.pop(),
    )


def assert_batches_identical(a: BatchResult, b: BatchResult) -> None:
    assert a.finite.shape == b.finite.shape
    for i in range(a.finite.shape[0]):
        assert_run_identical(a, i, b, i)


def assert_scalar_identical(a: RunResult, b: RunResult) -> None:
    assert a.rows == b.rows
    assert a.final_state == b.final_state
    assert a.mins == b.mins


# ---- step 1: the engine options at their defaults --------------------------------------------------------------------


def test_new_engine_arguments_at_defaults_are_bit_identical_on_the_27_cases() -> None:
    """The 27-case batch (26 at dt 1/16 in one batch, the dt-1/32 case alone) with every new argument at its default,
    and with an empty noise mapping, equals the plain call: rows, final state, mins and ``finite``."""
    groups = [[c for c in ALL_CASES.values() if c.dt == DT], [ALL_CASES["base, dt 1/32"]]]
    assert sum(len(g) for g in groups) == 27
    for cases in groups:
        params, init, ai, dt = batch_inputs(cases)
        plain = run_batch(params, init, ai_on=ai, dt=dt, record_every=1.0)
        explicit = run_batch(
            params, init, ai_on=ai, dt=dt, record_every=1.0, start_step=0, tilt=True, reanchor=None, noise=None
        )
        empty = run_batch(params, init, ai_on=ai, dt=dt, record_every=1.0, noise={})
        assert_batches_identical(plain, explicit)
        assert_batches_identical(plain, empty)
    for name in ("scenario Base", "EXTREME", "base, dt 1/32"):
        case = ALL_CASES[name]
        plain_run = case.scalar(record_every=1.0)
        p, st = case.params(), case.state()
        explicit_run = run(
            p, st, ai_on=case.ai_on, dt=case.dt, record_every=1.0, start_step=0, tilt=True, reanchor=None, noise=None
        )
        empty_run = run(p, st, ai_on=case.ai_on, dt=case.dt, record_every=1.0, noise={})
        assert_scalar_identical(plain_run, explicit_run)
        assert_scalar_identical(plain_run, empty_run)


# ---- step 2: restarts ------------------------------------------------------------------------------------------------


def test_restart_is_exact_in_the_scalar_engine() -> None:
    """Unchanged parameters: a two-phase run at Y on the grid equals an uninterrupted run, rows, mins and state."""
    full = run(BASE, record_every=DT)
    for Y in Y_GRID:
        assert_scalar_identical(run_from(BASE, BASE, Y=Y, record_every=DT), full)


def test_restart_is_exact_in_the_batch_engine() -> None:
    full = run_batch(BatchParams.stack([BASE] * 2), record_every=DT)
    for Y in Y_GRID:
        assert_batches_identical(run_batch_from(BatchParams.stack([BASE] * 2), Y=Y, record_every=DT), full)


def test_y_2024_equals_the_default() -> None:
    """At Y = 2024 every lever acts from 2024, as without ``perturb_from``: bit for bit, in both engines and through
    the experiment API."""
    runs = [
        BASE,
        BASE.with_overrides(g=0.15, VerifDecline=0.1, aL_max=0.45, AICostDecline=0.25),
        BASE.with_overrides(**SCENARIOS["Visa crackdown"]),
    ]
    for p in runs:
        assert_scalar_identical(run_from(BASE, p, Y=2024.0), run(p))
    bp = BatchParams.stack(runs)
    assert_batches_identical(run_batch_from(bp, Y=2024.0), run_batch(bp))
    exp = Experiment(sample=tornado_levers(), n=20, method="lhs", seed=3)
    plain = run_experiment(exp, outputs="all", keep_state=True)
    at_2024 = run_experiment(replace(exp, perturb_from=2024.0), outputs="all", keep_state=True)
    for k in plain.series:
        assert np.array_equal(plain.series[k], at_2024.series[k]), k
    assert plain.mins is not None and at_2024.mins is not None
    for k in plain.mins:
        assert np.array_equal(plain.mins[k], at_2024.mins[k]), k


def test_zero_width_before_y() -> None:
    """The Q01 design with the 13 levers that may act from 2026.5: before Y every recorded key has a p10-p90 width
    (and a max-min range) of exactly 0; after Y the levers act."""
    exp = Experiment(sample=tornado_levers(2026.5), n=1000, method="lhs", seed=20261012, perturb_from=2026.5)
    assert len(exp.sample) == 13 and "Verif" not in exp.sample
    res = run_experiment(exp, outputs="all", record_every=0.25, stop=4.0)
    assert res.valid.all()
    before = res.years < 2026.5
    assert before.sum() == 10
    for k, a in res.series.items():
        x = a[:, before]
        assert np.array_equal(pct(x, 0.9) - pct(x, 0.1), np.zeros(x.shape[1])), k
        assert np.ptp(x, axis=0).max() == 0.0, k
    assert np.ptp(res.series["HeadTotal"][:, -1]) > 0


# ---- continuity at Y (B5) --------------------------------------------------------------------------------------------

Y_B5 = 2026.5
K_B5 = round((Y_B5 - 2024) / DT)
EXPECTED_JUMPS = {
    "SrcCostSens lo": {"SrcT_FIN_BQ", "SrcT_GOV_GSI"},
    "SrcCostSens hi": {"SrcT_FIN_BQ", "SrcT_LOG_GSI"},
    "JuniorCut lo": {"TTF_IN_J", "HireJ_ON", "TTF_ON_J"},
    "JuniorCut hi": {"TTF_ON_J", "TTF_IN_J"},
    "PriceHorizon lo": {"SrcT_LOG_GSI", "SrcT_FIN_BQ"},
    "JevonsEps hi": {"Dem_APP", "Dem_RET"},
}
"""Levers whose own effect is immediate at Y (recon 06 B5): their jumps are expected, and pinned here so that a change
cannot hide them. Each maps to keys that must stay among the flagged ones."""


def b5_ratios(base: dict[str, F], post: dict[str, F], i: int) -> dict[str, float]:
    """B5: |switched row at Y + dt - base row at Y| over max(median |step| of the 8 base steps before Y, 1e-6 |x|)."""
    out = {}
    for k, b in base.items():
        xY = float(b[0, K_B5])
        typical = float(np.median(np.abs(np.diff(b[0, K_B5 - 8 : K_B5 + 1]))))
        jump = abs(float(post[k][i, K_B5 + 1]) - xY)
        den = max(typical, 1e-6 * abs(xY))
        out[k] = jump / den if den > 0 else (0.0 if jump == 0 else math.inf)
    return out


def test_continuity_at_y() -> None:
    """The rate levers of the anchored paths, at their tornado extremes, move no row key by more than 10 typical
    steps at Y; the immediate-effect levers jump as recorded."""
    smooth = [f"{name} {end}" for name in ("g", "VerifDecline", "aL_max", "AICostDecline") for end in ("lo", "hi")]
    labels = smooth + list(EXPECTED_JUMPS)
    params = [BASE.with_overrides(**{lab.split()[0]: RANGE[lab.split()[0]][lab.endswith("hi")]}) for lab in labels]
    res = run_batch_from(BatchParams.stack(params), Y=Y_B5, record_every=DT, stop=3.0)
    base = dict(run_batch(BatchParams.stack([BASE]), record_every=DT, stop=Y_B5 - 2024).series)
    for i, label in enumerate(labels):
        r = b5_ratios(base, dict(res.series), i)
        flagged = {k for k, v in r.items() if v > 10}
        if label in EXPECTED_JUMPS:
            assert EXPECTED_JUMPS[label] <= flagged, (label, sorted(flagged))
        else:
            assert not flagged, (label, {k: r[k] for k in flagged})


# ---- parity and determinism ------------------------------------------------------------------------------------------

MIXED = [
    BASE,
    BASE.with_overrides(g=RANGE["g"][1]),
    BASE.with_overrides(VerifDecline=RANGE["VerifDecline"][1]),
    BASE.with_overrides(aL_max=RANGE["aL_max"][1]),
    BASE.with_overrides(AICostDecline=RANGE["AICostDecline"][0]),
    BASE.with_overrides(PriceHorizon=RANGE["PriceHorizon"][1], SrcCostSens=RANGE["SrcCostSens"][1]),
    BASE.with_overrides(JuniorCut=RANGE["JuniorCut"][0]),
    BASE.with_overrides(**SCENARIOS["Compute shock"]),
    BASE.with_overrides(**SCENARIOS["Fast AI"]),
    BASE.with_overrides(**SCENARIOS["Jevons rebound"]),
]


def assert_scalar_matches_batch(batch: BatchResult, i: int, scalar: RunResult) -> None:
    """Run ``i`` of ``batch`` equals the scalar run within 1e-12 (relative, absolute floor 1e-12)."""
    rows = batch.rows(i)
    assert len(rows) == len(scalar.rows)
    for rb, rs in zip(rows, scalar.rows, strict=True):
        for k, v in rs.items():
            assert math.isclose(rb[k], v, rel_tol=1e-12, abs_tol=1e-12), (k, rb["year"], rb[k], v)
    fb, fs = batch.final_state.arrays(), pack([scalar.final_state]).arrays()
    for name, a in fs.items():
        assert np.all(np.isclose(fb[name][i], a[0], rtol=1e-12, atol=1e-12)), name
    for k, v in scalar.mins.items():
        assert math.isclose(float(batch.mins[k][i]), v, rel_tol=1e-12, abs_tol=1e-12), k


def test_two_phase_parity_scalar_batch() -> None:
    """Ten mixed two-phase runs at Y = 2026.5: scalar against batch at 1e-12 (expected bit-identical)."""
    batch = run_batch_from(BatchParams.stack(MIXED), Y=2026.5, record_every=0.25)
    assert batch.finite.all()
    for i, p in enumerate(MIXED):
        assert_scalar_matches_batch(batch, i, run_from(BASE, p, Y=2026.5, record_every=0.25))


def test_phase1_is_reused_and_checked() -> None:
    first = phase1(2026.5, record_every=0.25)
    assert first.series["HeadTotal"].shape == (1, 10) and first.reanchor is not None
    assert phase1(2024.0).reanchor is None
    with pytest.raises(ValueError, match="phase 1"):
        run_batch_from(BatchParams.stack([BASE]), Y=2027.0, record_every=0.25, first=first)


def test_determinism_across_workers_and_chunks() -> None:
    """Two-phase results are bit-identical for workers 1 and 4 and chunk sizes 7 and auto."""
    exp = Experiment(sample=tornado_levers(2026.5), n=300, method="lhs", seed=11, perturb_from=2026.5)
    keys = ["HeadTotal", "RevenueTot", "Mix_OIT_FP", "EffortShare_OIT"]
    ref = run_experiment(exp, outputs=keys, workers=1, keep_state=True)
    for workers, chunk in ((1, 7), (4, 7), (4, None)):
        other = run_experiment(exp, outputs=keys, workers=workers, chunk_size=chunk, keep_state=True)
        assert ref.meta["perturb_from"] == other.meta["perturb_from"] == 2026.5
        for k in keys:
            assert np.array_equal(ref.series[k], other.series[k]), (workers, chunk, k)
        assert np.array_equal(ref.valid, other.valid)
        assert ref.final_state is not None and other.final_state is not None
        sa, sb = ref.final_state.arrays(), other.final_state.arrays()
        assert all(np.array_equal(sa[n], sb[n]) for n in sa)
        assert ref.mins is not None and other.mins is not None
        assert all(np.array_equal(ref.mins[n], other.mins[n]) for n in ref.mins)
