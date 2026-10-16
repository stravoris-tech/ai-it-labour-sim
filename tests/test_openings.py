"""The continuous-openings extension ``OpeningsContinuous`` (slice 9, recon 09b's C form), in both engines.

At 0 (the default) both engines run Phase 7's code: an ``if`` in the scalar engine, ``np.where`` on complete results in
the batch engine. At 1 (on when ``>= 0.5``), openings are ``max(0, netloss + (-sp - V) / HireAdjTime)`` for every
surplus ``sp``, and layoffs keep their formula and branch. There is no prototype for it, so the scalar engine is the
oracle and batch-scalar parity the cross-check.

- At 0 the 27 cases are bit-identical to the default, and the selection is per run: no blending in a mixed batch.
- At 1 the engines agree on recon 09b's five runs and on a two-phase run with noise.
- Integrity (T1, T2, no negative stocks) holds at 1, in Base and ``EXTREME``.
- At 1 the openings flow is continuous across every surplus sign flip; at 0 the same measure sees the jump.
- Validation rejects values outside the switch's [0, 1].
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import replace

import numpy as np
import pytest

from aisim import BatchParams, Noise, Params, load_initial_state, run, run_batch
from aisim.batch.state import pack
from aisim.dims import LEVELS, UNITS
from aisim.noise import ou_factors
from aisim.perturb import run_batch_from, run_from, start_step_of
from aisim.scalar import engine
from aisim.scalar import labour_market as lm
from aisim.scenarios import EXTREME, SCENARIOS
from aisim.state import Mat, State
from tests.helpers import annual, people
from tests.test_batch_parity import ALL_CASES, Case, assert_run_identical, compare_run
from tests.test_integrity import MIN_STOCK
from tests.test_noise import assert_bit_identical, scalar_noise
from tests.test_perturb import assert_batches_identical, assert_scalar_identical
from tests.test_validate import violations

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The parity tests here need numpy's kernels to match libm (``tests/conftest.py``)."""

ON = {"OpeningsContinuous": 1.0}
BASE = Params.baseline()
DT = 1 / 16
Y = 2026.5

C2 = {
    "p": 0.043668571258719056,
    "q": 0.49476051045843134,
    "Verif": 0.43234231150836094,
    "GCCAppealEnd": 3.087108018591279,
    "JuniorCut": 0.5833411565706552,
    "GCCMomentum": 1.8393158869075872,
    "qC": 0.23641913341941465,
    "pAtt": 0.01225697261355878,
    "PriceHorizon": 7.877014895746029,
    "SeekerExitRate": 0.5000389728015764,
    "AICost2024": 34796.93079115779,
}
"""Recon 09's "C2": the Phase 7 fit as ``tools/calibrate.py`` reproduces it (loss 0.000800786)."""

A2_B7 = {
    "p": 0.24037488329769297,
    "q": 0.08295247372275598,
    "Verif": 0.5508791747868235,
    "GCCAppealEnd": 2.7107540799627623,
    "JuniorCut": 0.7645619037688749,
    "GCCMomentum": 1.897056680496845,
    "qC": 0.2368122517958691,
    "pAtt": 0.012256021826289487,
    "PriceHorizon": 6.999991989093559,
    "SeekerExitRate": 0.48264501851085423,
    "AICost2024": 42526.43354099063,
}
"""Recon 09's "A2-b7": recon 08b's multi-start best with ``PriceHorizon`` at most 7 (loss 0.000416)."""

PARITY_RUNS = {
    "C2 Base": {**C2, **SCENARIOS["Base"]},
    "C2 Fast AI": {**C2, **SCENARIOS["Fast AI"]},
    "A2-b7": dict(A2_B7),
    "C2 EXTREME": {**C2, **EXTREME},
    "A2-b7 Slow AI": {**A2_B7, **SCENARIOS["Slow AI"]},
}
"""Recon 09b B6's five runs (recon 09 ``b3_eval.parity``)."""

FLIP_LIMIT = 0.01
"""Recon 09b A3: the largest openings step across a flip is 0.4% of staff a year in Base (59% at 0)."""


def with_openings(case: Case, value: float) -> Case:
    return replace(case, overrides={**case.overrides, "OpeningsContinuous": value})


# ---- at 0: Phase 7 bit for bit ---------------------------------------------------------------------------------------


def test_default_is_bit_identical_on_the_27_cases() -> None:
    """An explicit ``OpeningsContinuous`` 0 reproduces the default bit for bit (rows, final state, mins, ``finite``)
    on the 27-case batch, and in three scalar runs. The default itself is pinned to the prototype by the parity and
    golden tests."""
    groups = [[c for c in ALL_CASES.values() if c.dt == DT], [ALL_CASES["base, dt 1/32"]]]
    assert sum(len(g) for g in groups) == 27
    for cases in groups:
        init = pack([c.state() for c in cases])
        ai = [c.ai_on for c in cases]
        dt = cases[0].dt
        default = run_batch(BatchParams.stack([c.params() for c in cases]), init, ai_on=ai, dt=dt)
        explicit = run_batch(BatchParams.stack([with_openings(c, 0.0).params() for c in cases]), init, ai_on=ai, dt=dt)
        assert_batches_identical(default, explicit)
    for name in ("scenario Base", "EXTREME", "base, dt 1/32"):
        case = ALL_CASES[name]
        assert_scalar_identical(case.scalar(record_every=1.0), with_openings(case, 0.0).scalar(record_every=1.0))


def test_selection_is_per_run() -> None:
    """In a batch that alternates 0 and 1, every run at 0 equals the same run in a batch at 0, bit for bit:
    ``np.where`` picks complete results per run, never a blend. The runs at 1 differ (the form acts)."""
    cases = [c for c in ALL_CASES.values() if c.dt == DT]
    init = pack([c.state() for c in cases])
    ai = [c.ai_on for c in cases]
    alone = run_batch(BatchParams.stack([c.params() for c in cases]), init, ai_on=ai)
    mixed = run_batch(
        BatchParams.stack([with_openings(c, float(i % 2)).params() for i, c in enumerate(cases)]), init, ai_on=ai
    )
    for i in range(0, len(cases), 2):
        assert_run_identical(alone, i, mixed, i)
    moved = [
        i
        for i in range(1, len(cases), 2)
        if not np.array_equal(alone.series["HireJ_ON"][i], mixed.series["HireJ_ON"][i])
    ]
    assert moved


# ---- at 1: batch against the scalar oracle ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", list(PARITY_RUNS))
def test_parity_at_one(name: str) -> None:
    """Recon 09b's five runs with the C form: batch against scalar within 1e-12 (rows, final state, mins)."""
    p = BASE.with_overrides(**PARITY_RUNS[name], **ON)
    batch = run_batch(BatchParams.stack([p]), record_every=0.25)
    assert batch.finite.all()
    cmp = compare_run(batch, 0, run(p, record_every=0.25))
    assert cmp.miss is None, cmp.miss


def test_parity_two_phase_with_noise_at_one() -> None:
    """Two-phase runs at Y = 2026.5 with demand and anchor noise, the C form on: bit-identical."""
    runs = [
        BASE.with_overrides(**ON),
        BASE.with_overrides(**C2, **SCENARIOS["Fast AI"], **ON),
        BASE.with_overrides(**A2_B7, **ON),
    ]
    noise = {"anchor": Noise(0.1, 1.0), "demand": Noise(0.05, 2.0)}
    factors = ou_factors(noise, 43, range(len(runs)), start_step=start_step_of(Y, DT), steps=256, dt=DT)
    batch = run_batch_from(BatchParams.stack(runs), Y=Y, record_every=0.25, noise=factors)
    assert batch.finite.all()
    for i, p in enumerate(runs):
        assert_bit_identical(batch, i, run_from(BASE, p, Y=Y, record_every=0.25, noise=scalar_noise(factors, i)))


# ---- at 1: integrity -------------------------------------------------------------------------------------------------


def test_t1_ai_off_growth_path_at_one() -> None:
    """T1 (``tests/test_integrity.py``) with the C form: the AI-off headcount follows the growth path within 1.2%."""
    ann = annual(run(BASE.with_overrides(**ON), ai_on=False, record_every=1.0).rows)
    h2024 = ann[2024]["HeadTotal"]
    assert max(abs(r["HeadTotal"] / h2024 / r["G"] - 1) for r in ann.values()) < 0.012


def test_t2_people_conservation_at_one() -> None:
    result = run(BASE.with_overrides(**ON), record_every=1 / 16)
    inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in result.rows[:-1])
    total = people(result.final_state)
    assert abs(total - people(load_initial_state()) - inflow) <= 1e-9 * total


@pytest.mark.parametrize("case", ["base", "EXTREME"])
def test_no_negative_stocks_at_one(case: str) -> None:
    params = BASE.with_overrides(**(EXTREME if case == "EXTREME" else {}), **ON)
    mins = run(params, record_every=1.0).mins
    worst = min(mins, key=lambda k: mins[k])
    assert mins[worst] >= MIN_STOCK, f"{worst} = {mins[worst]!r}"


# ---- continuity across surplus sign flips ----------------------------------------------------------------------------

Log = dict[tuple[str, str], list[tuple[float, float, float]]]


def openings_log(monkeypatch: pytest.MonkeyPatch, params: Params) -> Log:
    """Per unit and level, ``(surplus, openings, H + O)`` at every step of a scalar run to 2040."""
    log: Log = defaultdict(list)

    def logged(
        pr: Mapping[str, float],
        st: State,
        surplus: Mat,
        promo: Mat,
        sw: dict[str, dict[str, lm.SwitchFlows]],
        visa: lm.VisaFlows,
    ) -> lm.Exits:
        ex = lm.exits(pr, st, surplus, promo, sw, visa)
        for u in UNITS:
            for lv in LEVELS:
                log[(u, lv)].append((surplus[u][lv], ex.fl[u][lv]["openings"], st["H"][u][lv] + st["O"][u][lv]))
        return ex

    with monkeypatch.context() as m:
        m.setattr(engine, "exits", logged)
        run(params, record_every=1.0)
    return log


def largest_flip_step(log: Log) -> tuple[float, int]:
    """The largest ``|openings[s] - openings[s - 1]| / max(H + O, 1)`` (per year) at a step ``s`` where the surplus
    changes side of 0 (``sp <= 0`` against ``sp > 0``, recon 09b D3), and the number of such flips."""
    worst, flips = 0.0, 0
    for seq in log.values():
        for s in range(1, len(seq)):
            if (seq[s][0] <= 0) != (seq[s - 1][0] <= 0):
                flips += 1
                worst = max(worst, abs(seq[s][1] - seq[s - 1][1]) / max(seq[s][2], 1.0))
    return worst, flips


@pytest.mark.parametrize("scenario", ["Base", "Fast AI", "Slow AI"])
def test_openings_continuous_across_flips(monkeypatch: pytest.MonkeyPatch, scenario: str) -> None:
    """At 1 the openings flow changes by at most 1% of staff a year across every surplus sign flip (recon 09b A3)."""
    worst, flips = largest_flip_step(openings_log(monkeypatch, BASE.with_overrides(**SCENARIOS[scenario], **ON)))
    assert flips > 0
    assert worst <= FLIP_LIMIT, worst


def test_flip_measure_sees_the_phase7_jump(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: at 0 (Phase 7) the same measure finds a jump far above the limit (recon 09 B1: 0.59)."""
    worst, flips = largest_flip_step(openings_log(monkeypatch, BASE))
    assert flips > 0
    assert worst > 10 * FLIP_LIMIT, worst


# ---- validation ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0.0, 1.0])
def test_switch_values_are_valid(value: float) -> None:
    assert violations({"OpeningsContinuous": value}) == []


@pytest.mark.parametrize("value", [2.0, -1.0])
def test_values_outside_the_switch_are_rejected(value: float) -> None:
    vs = violations({"OpeningsContinuous": value})
    assert [(v.family, v.target) for v in vs] == [("domain", "OpeningsContinuous")]
    assert "switch" in vs[0].rule
