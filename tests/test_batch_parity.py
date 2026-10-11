"""The batched engine reproduces the scalar engine (the oracle) within a relative 1e-12, absolute floor 1e-12.

End to end, every run of a batch is compared with its own scalar run: every row key at every recorded time, the final
state and the stock minimums. Section by section, every intermediate field of every section at every step is compared
through the two engines' trace hooks. The batch-specific behaviour is tested too: run independence, failing runs, the
fault sites behind ``finite``, state packing, output subsets and ``BatchParams``.
"""

from __future__ import annotations

import dataclasses
import math
import random
import warnings
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from aisim import Params, run
from aisim.batch.adoption import AI_COST_SITE
from aisim.batch.capability import POWER_SITE
from aisim.batch.consumer import CREDIT_COST_SITE
from aisim.batch.engine import PARAM_SITE_PREFIX, BatchResult, Trace, run_batch, simulate
from aisim.batch.integrate import BUDGET_SITE
from aisim.batch.params import BatchParams
from aisim.batch.record import ROW_KEYS
from aisim.batch.state import BatchState, pack, unpack
from aisim.batch.util import B, F, csum, nsum
from aisim.dims import UNITS
from aisim.scalar.engine import SECTION_IDS, RunResult
from aisim.scalar.engine import Trace as ScalarTrace
from aisim.state import State, load_initial_state
from tests.helpers import init_state, load_coverage_cases
from tests.test_parity import CASES
from tools.reference_runner import InitEdit

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""Every test here needs numpy's kernels to match libm (``tests/conftest.py``)."""

REL_TOL = 1e-12
ABS_TOL = 1e-12

RUN_OPTIONS = ("ai_on", "dt", "record_every")

CRASHES: dict[str, dict[str, float]] = {
    "AIShockMult 0 in the window": {"AIShockMult": 0.0},
    "BudgetShock 1 from 2024": {"BudgetShock": 1.0, "BudgetShockStart": 2024.0, "BudgetShockEnd": 2040.0},
    "g above 1": {"g": 1.5},
}
"""Overrides on which the scalar engine raises (recon 03 B2). The default AI shock window, 2030-2032, is in the run."""


@dataclass(frozen=True)
class Case:
    """One run: parameter overrides, state edits and run options."""

    name: str
    overrides: dict[str, float] = field(default_factory=dict)
    init_edits: list[InitEdit] = field(default_factory=list)
    ai_on: bool = True
    dt: float = 1 / 16
    record_every: float = 1.0

    def params(self) -> Params:
        return Params.baseline().with_overrides(**self.overrides)

    def state(self) -> State:
        return init_state(self.init_edits)

    def scalar(self, record_every: float | None = None, trace: ScalarTrace | None = None) -> RunResult:
        every = self.record_every if record_every is None else record_every
        return run(self.params(), self.state(), ai_on=self.ai_on, dt=self.dt, record_every=every, trace=trace)


def parity_cases() -> list[Case]:
    """The 23 scalar parity cases (``tests/test_parity.py``) and the 4 coverage cases, as ``Case`` objects."""
    out = []
    for name, kwargs in CASES:
        overrides = {k: v for k, v in kwargs.items() if k not in RUN_OPTIONS}
        out.append(
            Case(
                name,
                overrides,
                ai_on=kwargs.get("ai_on", True),
                dt=kwargs.get("dt", 1 / 16),
                record_every=kwargs.get("record_every", 1.0),
            )
        )
    out += [Case(c.name, c.overrides, c.init_edits) for c in load_coverage_cases()]
    return out


ALL_CASES = {c.name: c for c in parity_cases()}


def run_cases(cases: Sequence[Case], record_every: float, trace: Trace | None = None) -> BatchResult:
    """Run ``cases`` as one batch, each with its own parameters, initial state and ``ai_on``."""
    dts = {c.dt for c in cases}
    assert len(dts) == 1, "a batch has one dt"
    params = BatchParams.stack([c.params() for c in cases])
    init = pack([c.state() for c in cases])
    ai = [c.ai_on for c in cases]
    return run_batch(params, init, ai_on=ai, dt=dts.pop(), record_every=record_every, trace=trace)


# ---- comparison ------------------------------------------------------------------------------------------------------


def close(fresh: F, oracle: F) -> B:
    """Element-wise: equal, or both finite and within the tolerance (math.isclose semantics, rel and abs 1e-12)."""
    with np.errstate(invalid="ignore", over="ignore"):
        bound = np.maximum(REL_TOL * np.maximum(np.abs(fresh), np.abs(oracle)), ABS_TOL)
        within = np.isfinite(fresh) & np.isfinite(oracle) & (np.abs(fresh - oracle) <= bound)
    out: B = (fresh == oracle) | within
    return out


def rel_diff(fresh: F, oracle: F) -> F:
    """Element-wise ``|a - b| / max(|a|, |b|)``, 0 where equal."""
    with np.errstate(invalid="ignore", divide="ignore"):
        d = np.abs(fresh - oracle) / np.maximum(np.abs(fresh), np.abs(oracle))
    out: F = np.where(fresh == oracle, 0.0, d)
    return out


@dataclass
class Comparison:
    """The worst relative difference seen, and the first value outside the tolerance (if any)."""

    worst: float = 0.0
    worst_at: str = ""
    miss: str | None = None

    def check(self, fresh: F, oracle: F, where: str) -> None:
        assert fresh.shape == oracle.shape, f"{where}: shape {fresh.shape} vs {oracle.shape}"
        d = rel_diff(fresh, oracle)
        if d.size and (np.isnan(d).any() or float(d.max()) > self.worst):
            self.worst = math.inf if np.isnan(d).any() else float(d.max())
            self.worst_at = where
        ok = close(fresh, oracle)
        if self.miss is None and not ok.all():
            idx = tuple(int(j) for j in np.argwhere(~ok)[0])
            self.miss = f"{where}{list(idx)}: batch {fresh[idx]!r} vs scalar {oracle[idx]!r}"


def compare_run(result: BatchResult, i: int, scalar: RunResult) -> Comparison:
    """Compare run ``i`` of ``result`` with its scalar run: rows (every key, every time), final state and mins."""
    cmp = Comparison()
    rows = scalar.rows
    assert len(rows) == len(result.years)
    assert tuple(result.series) == tuple(rows[0]) == ROW_KEYS
    for key in ROW_KEYS:
        cmp.check(result.series[key][i], np.array([r[key] for r in rows]), f"rows/{key}")
    oracle_state = pack([scalar.final_state]).arrays()
    for name, a in result.final_state.arrays().items():
        cmp.check(a[i], oracle_state[name][0], f"final_state/{name}")
    assert list(result.mins) == list(scalar.mins)
    for key, v in scalar.mins.items():
        cmp.check(result.mins[key][i : i + 1], np.array([v]), f"mins/{key}")
    return cmp


def assert_runs_match(result: BatchResult, cases: Sequence[Case], record_every: float) -> dict[str, Comparison]:
    out = {}
    for i, case in enumerate(cases):
        cmp = compare_run(result, i, case.scalar(record_every=record_every))
        assert cmp.miss is None, f"{case.name}: {cmp.miss}"
        out[case.name] = cmp
    return out


# ---- end to end ------------------------------------------------------------------------------------------------------


def test_case_list() -> None:
    assert len(ALL_CASES) == 27
    assert sum(c.dt == 1 / 16 for c in ALL_CASES.values()) == 26


def test_end_to_end_main_batch() -> None:
    """The 22 dt-1/16 parity cases and the 4 coverage cases in one batch of 26, at ``record_every=1.0``.

    It mixes ``ai_on``, ``Burn``, ``FreezeSourcing``, ``WagesEndogenous = 0``, ``GCCMomentum = 0``, the shock windows,
    ``DemandGrowthLate`` as None and as a float, a step ramp and an edited initial state.
    """
    cases = [c for c in ALL_CASES.values() if c.dt == 1 / 16]
    result = run_cases(cases, record_every=1.0)
    assert result.finite.all()
    assert_runs_match(result, cases, 1.0)


def test_end_to_end_dt_1_32() -> None:
    """``dt=1/32`` cannot share a batch with ``dt=1/16``: its own batch, at its parity ``record_every`` (0.25)."""
    case = ALL_CASES["base, dt 1/32"]
    result = run_cases([case], record_every=case.record_every)
    assert result.finite.all()
    assert_runs_match(result, [case], case.record_every)


def test_end_to_end_every_step() -> None:
    """Base and AI off, recorded at every step (``record_every=1/16``), as in their parity cases."""
    cases = [ALL_CASES["base, every step"], ALL_CASES["AI off, every step"]]
    result = run_cases(cases, record_every=1 / 16)
    assert len(result.years) == 257
    assert_runs_match(result, cases, 1 / 16)


def test_comparison_detects_a_change() -> None:
    """Positive control: the same check fails when the batch runs on one parameter 1e-9 (relative) from the scalar's."""
    case = ALL_CASES["base, every step"]
    cost = Params.float_of(Params.baseline().scalars, "AICost2024")
    nudged = BatchParams.baseline(1, AICost2024=cost * (1 + 1e-9))
    result = run_batch(nudged, record_every=1.0)
    cmp = compare_run(result, 0, case.scalar(record_every=1.0))
    assert cmp.miss is not None
    assert cmp.worst > REL_TOL


# ---- section by section ----------------------------------------------------------------------------------------------


def to_array(value: Any) -> F:
    """A scalar intermediate (a float, or nested dicts or lists of floats, in key order) as an array.

    ``Any``: the scalar engine's intermediates are floats, dicts of floats or dicts of dicts of floats.
    """
    if isinstance(value, dict):
        return np.stack([to_array(v) for v in value.values()])
    if isinstance(value, list):
        return np.stack([to_array(v) for v in value])
    return np.array(float(value))


def vu_mask(tuples: Sequence[tuple[str, ...]]) -> F:
    """The per-vendor unit tuples ``VF[v].vu`` as a ``(vendor, unit)`` 0/1 array."""
    return np.array([[float(u in t) for u in UNITS] for t in tuples])


def scalar_fields(section: Any) -> dict[str, F]:
    """Every field of a scalar section dataclass, as arrays. A dict of dataclasses (``VF``, ``VB``, ``Src``, ``cons``)
    becomes one array per inner field, named ``outer.inner``, stacked over the dict's keys.

    ``Any``: any section dataclass.
    """
    out: dict[str, F] = {}
    for f in dataclasses.fields(section):
        value = getattr(section, f.name)
        first = next(iter(value.values()), None) if isinstance(value, dict) else None
        if first is not None and dataclasses.is_dataclass(first):
            for g in dataclasses.fields(first):
                inner = [getattr(x, g.name) for x in value.values()]
                out[f"{f.name}.{g.name}"] = vu_mask(inner) if g.name == "vu" else to_array(inner)
        else:
            out[f.name] = to_array(value)
    return out


def batch_fields(section: Any, i: int) -> dict[str, F]:
    """Run ``i`` of every field of a batched section dataclass, named as ``scalar_fields`` names them.

    ``Any``: any batched section dataclass.
    """
    out: dict[str, F] = {}
    for f in dataclasses.fields(section):
        value = getattr(section, f.name)
        if dataclasses.is_dataclass(value):
            for g in dataclasses.fields(value):
                inner = getattr(value, g.name)
                out[f"{f.name}.{g.name}"] = inner.astype(np.float64) if g.name == "vu" else inner[i]
        else:
            out[f.name] = value[i]
    return out


def scalar_trace(case: Case) -> dict[tuple[int, str], dict[str, F]]:
    """Every section's fields at every step of the scalar run of ``case``, keyed by ``(step, section_id)``."""
    store: dict[tuple[int, str], dict[str, F]] = {}

    def keep(step: int, year: float, section_id: str, section: object) -> None:
        store[(step, section_id)] = scalar_fields(section)

    case.scalar(trace=keep)
    return store


def assert_sections_match(cases: Sequence[Case]) -> None:
    """Every intermediate field of every section at every step matches between the engines, for every case.

    On failure, reports the first step, section, field, case and index that differ.
    """
    expected = [scalar_trace(case) for case in cases]
    seen: list[tuple[int, str]] = []
    cmp = Comparison()

    def check(step: int, year: float, section_id: str, section: object) -> None:
        seen.append((step, section_id))
        if cmp.miss is not None:
            return
        for i, case in enumerate(cases):
            want = expected[i][(step, section_id)]
            got = batch_fields(section, i)
            assert got.keys() == want.keys(), f"{section_id}: fields differ"
            for name in want:
                cmp.check(got[name], want[name], f"step {step} {section_id}.{name} ({case.name})")

    run_cases(cases, record_every=1.0, trace=check)
    assert cmp.miss is None, cmp.miss
    assert len(seen) == 257 * len(SECTION_IDS)
    assert {key for store in expected for key in store} == set(seen)


def test_sections_base() -> None:
    assert_sections_match([ALL_CASES["scenario Base"]])


def test_sections_mixed() -> None:
    """Base, EXTREME, ``zero_start`` and ``lever_extremes`` in one batch."""
    assert_sections_match([ALL_CASES[k] for k in ("scenario Base", "EXTREME", "zero_start", "lever_extremes")])


def test_section_check_detects_a_change() -> None:
    """Positive control: a 1e-9 relative change of one parameter shows up in the section comparison."""
    case = ALL_CASES["scenario Base"]
    cost = Params.float_of(Params.baseline().scalars, "AICost2024")
    nudged = Case("nudged", {"AICost2024": cost * (1 + 1e-9)})
    store = scalar_trace(case)
    cmp = Comparison()

    def check(step: int, year: float, section_id: str, section: object) -> None:
        got = batch_fields(section, 0)
        for name, want in store[(step, section_id)].items():
            cmp.check(got[name], want, f"{section_id}.{name}")

    run_cases([nudged], record_every=1.0, trace=check)
    assert cmp.miss is not None


# ---- batch behaviour -------------------------------------------------------------------------------------------------


def assert_run_identical(a: BatchResult, i: int, b: BatchResult, j: int) -> None:
    """Run ``i`` of ``a`` and run ``j`` of ``b`` are bit for bit the same: series, final state, mins and ``finite``."""
    assert np.array_equal(a.years, b.years)
    assert list(a.series) == list(b.series)
    for key in a.series:
        assert np.array_equal(a.series[key][i], b.series[key][j]), key
    sa, sb = a.final_state.arrays(), b.final_state.arrays()
    for name in sa:
        assert np.array_equal(sa[name][i], sb[name][j]), name
    for key in a.mins:
        assert a.mins[key][i] == b.mins[key][j], key
    assert a.finite[i] == b.finite[j]


def test_batch_independence() -> None:
    """A run's results do not depend on its batch: alone, first of 10 and last of 10 (with a failing run) agree."""
    x = ALL_CASES["scenario Fast AI"]
    others = [ALL_CASES[k] for k in ("scenario Base", "AI off, every step", "EXTREME", "Burn", "zero_start")]
    others += [ALL_CASES[k] for k in ("tornado draw 1", "scenario Downturn", "lever_extremes")]
    others.append(Case("g above 1", CRASHES["g above 1"]))
    assert len(others) == 9
    alone = run_cases([x], 1.0)
    first = run_cases([x, *others], 1.0)
    last = run_cases([*others, x], 1.0)
    assert not first.finite[9] and not last.finite[8]
    assert_run_identical(alone, 0, first, 0)
    assert_run_identical(alone, 0, last, 9)


def test_failing_runs_are_isolated() -> None:
    """The three crash overrides and a base run in one batch: no exception or warning, the crash runs are not finite,
    and the base run is bit for bit its solo run."""
    for over in CRASHES.values():
        with pytest.raises((ZeroDivisionError, TypeError)):
            run(Params.baseline().with_overrides(**over), record_every=1.0)
    cases = [Case(name, over) for name, over in CRASHES.items()] + [Case("base")]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result = run_cases(cases, 1.0)
    assert result.finite.tolist() == [False, False, False, True]
    assert_run_identical(result, 3, run_cases([Case("base")], 1.0), 0)


def faults_of(overrides: dict[str, float]) -> tuple[BatchResult, dict[str, bool]]:
    """Run one case through the internal engine entry and return its result and fault sites."""
    result, faults = simulate(BatchParams.baseline(1, **overrides), record_every=1.0)
    return result, {site: bool(mask[0]) for site, mask in faults.sites.items()}


def final_state_finite(result: BatchResult) -> bool:
    return all(bool(np.isfinite(a).all()) for a in result.final_state.arrays().values())


def test_fault_ai_cost_zero() -> None:
    """``AIShockMult = 0``: the S12 and S13a sites fire. The state stays finite (the infinities are clamped), so only
    the fault sites make ``finite`` False."""
    result, sites = faults_of(CRASHES["AIShockMult 0 in the window"])
    assert sites[AI_COST_SITE] and sites[CREDIT_COST_SITE]
    assert final_state_finite(result)
    assert not result.finite[0]


def test_fault_budget_zero() -> None:
    result, sites = faults_of(CRASHES["BudgetShock 1 from 2024"])
    assert sites[BUDGET_SITE]
    assert not result.finite[0]


def test_fault_complex_power() -> None:
    result, sites = faults_of(CRASHES["g above 1"])
    assert sites[POWER_SITE]
    assert not result.finite[0]


@pytest.mark.parametrize("overrides", [{"CancelTime": 0.0}, {"AbandonTime": -1.0}])
def test_fault_parameter_denominator(overrides: dict[str, float]) -> None:
    (name,) = overrides
    result, sites = faults_of(overrides)
    assert sites[PARAM_SITE_PREFIX + name]
    assert not result.finite[0]


def test_no_fault_in_base() -> None:
    """Negative control: no site fires in the baseline run."""
    result, sites = faults_of({})
    assert sites, "the sites are recorded even when they do not fire"
    assert not any(sites.values())
    assert result.finite[0]


# ---- state, outputs, parameters --------------------------------------------------------------------------------------


def leaves(state: State) -> list[tuple[tuple[str, ...], object]]:
    """Every leaf of a state with its key path, in key order."""
    out: list[tuple[tuple[str, ...], object]] = []

    # Any: a State is nested dicts of floats, walked generically.
    def walk(node: Any, path: tuple[str, ...]) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, (*path, k))
        else:
            out.append((path, node))

    walk(state, ())
    return out


def assert_same_state(fresh: State, oracle: State) -> None:
    """The same key paths in the same order and equal values; every leaf of ``fresh`` is a float.

    ``baseline.json`` stores some 2024 values as JSON integers; float64 holds them exactly, so they come back as equal
    floats.
    """
    a, b = leaves(fresh), leaves(oracle)
    assert [p for p, _ in a] == [p for p, _ in b]
    assert [v for _, v in a] == [v for _, v in b]
    assert all(type(v) is float for _, v in a)


@pytest.mark.parametrize("name", ["scenario Base", "zero_start"])
def test_pack_unpack_round_trip(name: str) -> None:
    state = ALL_CASES[name].state()
    other = load_initial_state()
    batch = pack([other, state])
    assert_same_state(unpack(batch, 1), state)
    assert_same_state(unpack(batch, 0), other)
    assert_same_state(unpack(BatchState.baseline(2), 1), load_initial_state())


def test_outputs_subset() -> None:
    full = run_batch(BatchParams.baseline(2, g=[0.1, 0.2]))
    part = run_batch(BatchParams.baseline(2, g=[0.1, 0.2]), outputs=["Q1_VendIndia", "HeadTotal"])
    assert list(part.series) == ["HeadTotal", "Q1_VendIndia"]
    for key in part.series:
        assert np.array_equal(part.series[key], full.series[key])
    assert len(full.rows(1)) == 17
    with pytest.raises(ValueError, match="every row key"):
        part.rows(0)
    with pytest.raises(ValueError, match="unknown output"):
        run_batch(outputs=["NoSuchKey"])


def test_rows_match_scalar_format() -> None:
    result = run_batch()
    rows = result.rows(0)
    scalar = run(record_every=1.0).rows
    assert [list(r) for r in rows] == [list(r) for r in scalar]
    assert rows == scalar


def test_row_keys_are_the_scalar_keys() -> None:
    assert tuple(run(stop=0.0).rows[0]) == ROW_KEYS


def test_batch_params_adoptc0_and_stack() -> None:
    """``baseline`` recomputes ``AdoptC0`` per run as ``Params.with_overrides`` does, and ``stack`` agrees with it."""
    pcs, dgl = [0.01, 0.02, 0.03], [None, 0.02, None]
    batch = BatchParams.baseline(3, pC=pcs, DemandGrowthLate=dgl)
    singles = [Params.baseline().with_overrides(pC=p, DemandGrowthLate=d) for p, d in zip(pcs, dgl, strict=True)]
    stacked = BatchParams.stack(singles)
    for i, p in enumerate(singles):
        assert batch["AdoptC0"][i] == p.scalars["AdoptC0"]
    assert batch["AdoptC0"][0] != Params.baseline().scalars["AdoptC0"]
    assert batch.dgl_is_none.tolist() == stacked.dgl_is_none.tolist() == [True, False, True]
    for name in batch.scalars:
        assert np.array_equal(batch[name], stacked[name], equal_nan=True), name
    for name in batch.tables:
        assert np.array_equal(batch.table(name), stacked.table(name)), name
    with pytest.raises(KeyError):
        BatchParams.baseline(2, NoSuchParameter=1.0)
    with pytest.raises(ValueError):
        BatchParams.baseline(2, g=[0.1, 0.2, 0.3])
    with pytest.raises(ValueError):
        BatchParams.baseline(2, g=None)


def test_csum_is_builtin_sum() -> None:
    """``csum`` reproduces CPython's compensated ``sum()`` bit for bit; positive control: a naive sum does not."""
    rng = random.Random(2026)
    for size in range(1, 10):
        rows = [[rng.uniform(-1, 1) * 10 ** rng.uniform(-8, 8) for _ in range(size)] for _ in range(5000)]
        terms = [np.array([r[k] for r in rows]) for k in range(size)]
        builtin = np.array([sum(r) for r in rows])
        assert np.array_equal(csum(terms), builtin), size
        if size >= 3:
            assert not np.array_equal(nsum(terms), builtin), size
