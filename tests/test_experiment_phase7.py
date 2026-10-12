"""Slice 4 acceptance: the Phase 7 Monte Carlo, Q3 counts and tornado through the experiment API.

The 300 MC samples are drawn exactly as ``phase7_runs.py`` draws them (``random.Random(7)``, ``rng.uniform(lo, hi)``
over ``TORNADO`` in list order, line 143); the tornado is the base run and the 28 one-at-a-time runs. Two parts:

- **API checks, bit-equal on every platform.** The same samples run directly through
  ``run_batch(BatchParams.baseline(n, **per_run))``, built without the experiment code (as recon 04 E did), with the
  verbatim prototype ``pct``, ``q3`` and tornado formula applied. The bands, Q3 results and tornado from
  ``run_experiment`` must be ``np.array_equal`` to these: live runs on the same machine.
- **Golden checks, platform-aware.** The goldens were generated on the platform in ``reference/goldens/MANIFEST.json``.
  There they must match bit for bit; elsewhere they are compared at the golden tolerance (``tests/helpers.py``
  ``TOL``, as ``test_golden_port.py`` does), because the C library may round differently in the last ulp. The Q3
  counts must equal the goldens on every platform.

The mode that ran is recorded as the JUnit test-suite property ``phase7_golden_mode`` (``record_property`` is not
written in pytest's default ``xunit2`` format) and printed in the terminal summary
(``tests/conftest.py``). The batched engine is involved, so this needs numpy's kernels to match libm.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from aisim import BatchParams, Experiment, ExperimentResult, Params, run_batch, run_experiment
from aisim.batch.engine import BatchResult
from aisim.dims import VENDORS
from aisim.scenarios import TORNADO
from tests.helpers import PHASE7, TOL, assert_close, golden_platform_matches, platform_signature

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")

GOLDENS = Path(__file__).resolve().parent.parent / "reference" / "goldens"
OUTS = ("HeadTotal", "Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia")
Q3_KEYS = tuple(f"{p}_{v}" for v in VENDORS for p in ("Vi", "Head", "Revenue"))
KEYS = (*OUTS, *Q3_KEYS)
QS = (0.1, 0.5, 0.9)
YEARS = tuple(range(2024, 2041))
NAMES = tuple(p for p, *_ in TORNADO)

# Per-year rows of floats, as the prototype keeps them, and bands by output and quantile.
Ann = dict[int, dict[str, float]]
Bands = dict[str, dict[float, list[float]]]


# ---- verbatim copies from phase7_runs.py -----------------------------------------------------------------------------


def q3(ann: Ann, v: str) -> str:  # phase7_runs.py:65-76, verbatim
    """Spec outcome test over 2038-2040: collapse, new equilibrium or still adjusting."""
    neg_run, best = 0, 0
    for yv in range(2024, 2041):
        neg_run = neg_run + 1 if ann[yv]["Vi_" + v] < 0 else 0
        best = max(best, neg_run)
    fall = max(1 - ann[yv]["Head_" + v] / max(ann[yv - 1]["Head_" + v], 1e-9) for yv in (2039, 2040))
    if best >= 3 and fall > 0.15:
        return "collapse"
    ch = max(
        abs(ann[yv][k] / max(ann[yv - 1][k], 1e-9) - 1) for yv in (2039, 2040) for k in ("Head_" + v, "Revenue_" + v)
    )
    return "equilibrium" if ch < 0.02 else f"adjusting ({ch * 100:.1f}%/yr)"


def pct(xs: list[float], q: float) -> float:  # phase7_runs.py:151-153, verbatim
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    f = math.floor(i)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (i - f)


# ---- samples ---------------------------------------------------------------------------------------------------------


def mc_draws() -> list[dict[str, float]]:
    rng = random.Random(7)
    draws = []
    for _ in range(300):
        over = {p: rng.uniform(lo, hi) for p, lo, hi, _ in TORNADO}  # phase7_runs.py:143
        draws.append(over)
    return draws


def tornado_rows() -> list[dict[str, float | None]]:
    """The base run and the 28 one-at-a-time runs, every tornado parameter given (None: DemandGrowthLate's baseline)."""
    base = Params.baseline().scalars
    cases: list[dict[str, float]] = [{}]
    cases += [{p: value} for p, lo, hi, _ in TORNADO for value in (lo, hi)]
    return [{p: case.get(p, base[p]) for p in NAMES} for case in cases]


def anns(res: BatchResult) -> list[Ann]:
    """Per run: ``{year: {key: float}}``, as ``annual(rows)`` (phase7_runs.py:61-62) on ``record_every = 1.0`` rows."""
    years = [round(float(y)) for y in res.years]
    return [{yv: {k: float(res.series[k][i, j]) for k in KEYS} for j, yv in enumerate(years)} for i in range(300)]


# ---- runs (each once per module) -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    with (GOLDENS / "phase7_results.json").open(encoding="utf-8") as f:
        out: dict[str, Any] = json.load(f)
    return out


@pytest.fixture(scope="module")
def manifest_env() -> dict[str, str]:
    with (GOLDENS / "MANIFEST.json").open(encoding="utf-8") as f:
        env: dict[str, str] = json.load(f)["environment"]
    return env


@pytest.fixture(scope="module")
def api_mc() -> ExperimentResult:
    return run_experiment(Experiment(samples=pd.DataFrame(mc_draws())), outputs=list(KEYS), workers=1)


@pytest.fixture(scope="module")
def api_tornado() -> ExperimentResult:
    # A None DemandGrowthLate is NaN in an explicit design.
    samples = pd.DataFrame(tornado_rows(), dtype=np.float64)
    return run_experiment(Experiment(samples=samples), outputs=list(OUTS), workers=1)


@pytest.fixture(scope="module")
def direct_mc() -> list[Ann]:
    draws = mc_draws()
    bp = BatchParams.baseline(300, **{p: [d[p] for d in draws] for p in NAMES})
    res = run_batch(bp, record_every=1.0, outputs=KEYS)
    assert res.finite.all()
    return anns(res)


@pytest.fixture(scope="module")
def direct_tornado() -> list[Ann]:
    rows = tornado_rows()
    bp = BatchParams.baseline(len(rows), **{p: [r[p] for r in rows] for p in NAMES})
    res = run_batch(bp, record_every=1.0, outputs=OUTS)
    years = [round(float(y)) for y in res.years]
    return [{yv: {k: float(res.series[k][i, j]) for k in OUTS} for j, yv in enumerate(years)} for i in range(len(rows))]


def proto_bands(runs: list[Ann]) -> Bands:
    traj = {k: [[a[yv][k] / a[2024][k] for yv in YEARS] for a in runs] for k in OUTS}  # phase7_runs.py:145-146
    return {k: {q: [pct([t[j] for t in traj[k]], q) for j in range(len(YEARS))] for q in QS} for k in OUTS}


def proto_tornado(runs: list[Ann]) -> list[float]:
    """Tornado values in golden order: per parameter, lo then hi, per output (phase7_runs.py:125-134)."""
    base_ann = runs[0]
    out = []
    for idx in range(len(TORNADO)):
        for s in range(2):
            ann = runs[1 + 2 * idx + s]
            out += [ann[2040][k] / base_ann[2040][k] - 1 for k in OUTS]
    return out


def api_bands(res: ExperimentResult) -> Bands:
    out: Bands = {}
    for k in OUTS:
        b = res.bands(k, ratio_to=2024)
        assert [float(y) for y in b.index] == [float(y) for y in YEARS]
        out[k] = {q: b[q].tolist() for q in QS}
    return out


def api_tornado_values(res: ExperimentResult) -> list[float]:
    end = {k: res.frame(k)[2040.0].to_numpy() for k in OUTS}
    return [
        float(end[k][1 + 2 * idx + s] / end[k][0] - 1) for idx in range(len(TORNADO)) for s in range(2) for k in OUTS
    ]


def counts_of(labels: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for label in labels:
        word = label.split(" ")[0]
        out[word] = out.get(word, 0) + 1
    return out


def note(config: pytest.Config, key: str, value: str | None = None) -> None:
    """Record a passed check for the summary line: set ``key`` to ``value``, or count it."""
    parts = config.stash.setdefault(PHASE7, {})
    parts[key] = value if value is not None else str(int(parts.get(key, "0")) + 1)


# ---- (i) API checks: bit-equal on every platform ---------------------------------------------------------------------


def test_api_bands_equal_direct(api_mc: ExperimentResult, direct_mc: list[Ann], pytestconfig: pytest.Config) -> None:
    fresh, ref = api_bands(api_mc), proto_bands(direct_mc)
    for k in OUTS:
        for q in QS:
            assert np.array_equal(np.array(fresh[k][q]), np.array(ref[k][q])), (k, q)
    assert sum(len(v) for b in fresh.values() for v in b.values()) == 255
    note(pytestconfig, "api")


def test_api_q3_equal_direct(api_mc: ExperimentResult, direct_mc: list[Ann], pytestconfig: pytest.Config) -> None:
    labels = api_mc.q3()
    counts = api_mc.q3_counts()
    for v in VENDORS:
        ref = [q3(a, v) for a in direct_mc]
        assert np.array_equal(labels[v].astype(str).to_numpy(), np.array([r.split(" ")[0] for r in ref])), v
        ref_counts = counts_of(ref)
        fresh = np.array([int(counts.loc[label, v]) for label in counts.index])
        assert np.array_equal(fresh, np.array([ref_counts.get(str(label), 0) for label in counts.index])), v
    note(pytestconfig, "api")


def test_api_tornado_equal_direct(
    api_tornado: ExperimentResult, direct_tornado: list[Ann], pytestconfig: pytest.Config
) -> None:
    fresh, ref = api_tornado_values(api_tornado), proto_tornado(direct_tornado)
    assert len(fresh) == len(ref) == 140
    assert np.array_equal(np.array(fresh), np.array(ref))
    note(pytestconfig, "api")


# ---- (ii) golden checks: bit for bit on the manifest platform, else at the golden tolerance --------------------------


def golden_mode(env: dict[str, str]) -> tuple[bool, str]:
    here, there = platform_signature(), platform_signature(env)
    exact = golden_platform_matches(env)

    def show(sig: dict[str, str]) -> str:
        return f"{sig['os']} {sig['machine']} {sig['python_implementation']} {sig['python_version']}"

    if exact:
        return True, f"bit-exact (platform {show(here)} matches the manifest)"
    return False, f"tolerance {TOL:g} (platform {show(here)} vs manifest {show(there)})"


def compare_golden(fresh: Any, gold: Any, exact: bool) -> None:
    """Bit for bit when ``exact``, else ``assert_close`` at ``TOL`` (``test_golden_port.py``'s comparison)."""
    if exact:
        assert fresh == gold
    else:
        assert_close(fresh, gold, TOL, TOL)


def test_golden_mc(
    api_mc: ExperimentResult,
    golden: dict[str, Any],
    manifest_env: dict[str, str],
    record_testsuite_property: Any,
    pytestconfig: pytest.Config,
) -> None:
    exact, mode = golden_mode(manifest_env)
    record_testsuite_property("phase7_golden_mode", mode)
    note(pytestconfig, "mode", mode)
    assert golden["mc"]["N"] == 300 and golden["mc"]["years"] == list(YEARS)
    fresh = {k: {str(q): v for q, v in b.items()} for k, b in api_bands(api_mc).items()}
    compare_golden(fresh, golden["mc"]["bands"], exact)
    counts = api_mc.q3_counts()
    fresh_q3 = {v: {str(label): int(c) for label, c in counts[v].items() if c} for v in VENDORS}
    assert fresh_q3 == golden["mc"]["q3"]  # exact on every platform
    note(pytestconfig, "q3", "equal")
    note(pytestconfig, "golden")


def test_golden_tornado(
    api_tornado: ExperimentResult,
    golden: dict[str, Any],
    manifest_env: dict[str, str],
    record_testsuite_property: Any,
    pytestconfig: pytest.Config,
) -> None:
    exact, mode = golden_mode(manifest_env)
    record_testsuite_property("phase7_golden_mode", mode)
    gold = golden["tornado"]
    assert [(r["param"], r["lo"], r["hi"], r["label"]) for r in gold] == [tuple(t) for t in TORNADO]
    expect = [row[f"{side}_{k}"] for row in gold for side in ("lo", "hi") for k in OUTS]
    compare_golden(api_tornado_values(api_tornado), expect, exact)
    note(pytestconfig, "golden")


def test_golden_platform_matcher(manifest_env: dict[str, str]) -> None:
    """The matcher's positive and negative controls (pure: it is given the platform to test)."""
    same = platform_signature(manifest_env)
    assert golden_platform_matches(manifest_env, same)
    for field, other in (("os", "Linux"), ("machine", "x86_64"), ("python_version", "3.12.3")):
        assert not golden_platform_matches(manifest_env, {**same, field: other}), field
    assert platform_signature(manifest_env) == {
        "os": "Windows",
        "machine": "ARM64",
        "python_implementation": "CPython",
        "python_version": "3.12.10",
    }


def test_golden_comparison_modes() -> None:
    """Controls for both modes: bit-exact rejects a 1-ulp change; the tolerance mode accepts it but rejects 1e-9."""
    gold = {"a": [0.9, 1.1], "b": [1.0]}
    ulp = {"a": [math.nextafter(0.9, 1.0), 1.1], "b": [1.0]}
    off = {"a": [0.9 * (1 + 1e-9), 1.1], "b": [1.0]}
    compare_golden(gold, gold, exact=True)
    with pytest.raises(AssertionError):
        compare_golden(ulp, gold, exact=True)
    compare_golden(ulp, gold, exact=False)
    with pytest.raises(pytest.fail.Exception):
        compare_golden(off, gold, exact=False)
