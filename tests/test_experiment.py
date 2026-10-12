"""The experiment runner and results: determinism across workers and chunks, layer precedence, derived outputs,
the exact percentile, the memory warning and the result views."""

from __future__ import annotations

import math
import random

import numpy as np
import pandas as pd
import pytest

from aisim import (
    SCENARIOS,
    BatchParams,
    Experiment,
    ExperimentResult,
    Fixed,
    Uniform,
    run_batch,
    run_experiment,
)
from aisim.batch.record import EXTRA_KEYS, ROW_KEYS
from aisim.experiment import runner
from aisim.experiment.derived import DERIVED
from aisim.experiment.inputs import batch_arrays
from aisim.experiment.results import pct
from aisim.experiment.runner import design, estimated_bytes, fixed_params

KEYS = ["HeadTotal", "Q1_ConsIndia", "Book_OIT_TM", "OnshoreTotal", "EffortShare_revenue_weighted"]
DET = Experiment(sample={"g": Uniform(0.06, 0.15), "JuniorCut": Uniform(0.3, 0.8)}, n=60, seed=1)


def assert_identical(a: ExperimentResult, b: ExperimentResult) -> None:
    assert list(a.series) == list(b.series)
    for k in a.series:
        assert np.array_equal(a.series[k], b.series[k]), k
    assert np.array_equal(a.years, b.years) and np.array_equal(a.valid, b.valid)
    pd.testing.assert_frame_equal(a.samples, b.samples, check_exact=True)


# ---- determinism -----------------------------------------------------------------------------------------------------


def test_determinism_across_workers_and_chunks() -> None:
    one = run_experiment(DET, outputs=KEYS, workers=1, chunk_size=500)
    many = run_experiment(DET, outputs=KEYS, workers=4, chunk_size=7)
    assert many.meta["workers"] == 4
    assert_identical(one, many)


@pytest.mark.slow
@pytest.mark.parametrize(("workers", "chunk_size"), [(1, 7), (4, 7), (4, 500)])
def test_determinism_matrix(workers: int, chunk_size: int) -> None:
    exp = Experiment(sample={"g": Uniform(0.06, 0.15), "SrcCostSens": Uniform(2.0, 4.0)}, n=1100, seed=9)
    ref = run_experiment(exp, outputs=KEYS, workers=1, chunk_size=500)
    res = run_experiment(exp, outputs=KEYS, workers=workers, chunk_size=chunk_size)
    assert res.meta["workers"] == min(workers, math.ceil(1100 / chunk_size))
    assert_identical(ref, res)


# ---- precedence and conflicts ----------------------------------------------------------------------------------------


def test_layers_apply_in_order() -> None:
    fast = dict(SCENARIOS["Fast AI"])
    # 2 over 1: the scenario sets g and VerifDecline.
    p, _ = fixed_params(Experiment(scenario="Fast AI"))
    assert (p.scalars["g"], p.scalars["VerifDecline"]) == (fast["g"], fast["VerifDecline"])
    # 3 over 2: an override replaces the scenario's value, the rest of the scenario stays.
    p, on_top = fixed_params(Experiment(scenario="Fast AI", overrides={"g": 0.1}))
    assert (p.scalars["g"], p.scalars["VerifDecline"]) == (0.1, fast["VerifDecline"])
    assert on_top == {"g": 0.1, "VerifDecline": fast["VerifDecline"]}
    # 4 over 2: a sampled value replaces the scenario's, per run.
    exp = Experiment(scenario="Fast AI", sample={"g": Fixed(0.12)}, n=3, seed=1)
    p, _ = fixed_params(exp)
    s = design(exp)
    scalars, _, _ = batch_arrays(p, {"g": s["g"].to_numpy()}, 3)
    assert (scalars["g"] == 0.12).all() and (scalars["VerifDecline"] == fast["VerifDecline"]).all()
    # End to end, the layers give the same run as the equivalent batch.
    res = run_experiment(Experiment(scenario="Fast AI", overrides={"JevonsEps": 0.3}), outputs=["HeadTotal"])
    ref = run_batch(BatchParams.baseline(1, **fast, JevonsEps=0.3), outputs=["HeadTotal"])
    assert np.array_equal(res.series["HeadTotal"], ref.series["HeadTotal"])


def test_fixed_and_sampled_conflict() -> None:
    with pytest.raises(ValueError, match="both fixed and sampled"):
        run_experiment(
            Experiment(overrides={"g": 0.1}, sample={"g": Uniform(0.0, 0.2)}, n=2, seed=1), outputs=["HeadTotal"]
        )
    with pytest.raises(ValueError, match="both fixed and sampled"):
        run_experiment(Experiment(overrides={"g": 0.1}, samples=pd.DataFrame({"g": [0.1]})), outputs=["HeadTotal"])


def test_experiment_errors() -> None:
    with pytest.raises(KeyError, match="unknown scenario"):
        run_experiment(Experiment(scenario="No such"), outputs=["HeadTotal"])
    with pytest.raises(ValueError, match="unknown output"):
        run_experiment(Experiment(), outputs=["NoSuchKey"])
    with pytest.raises(ValueError, match="excludes"):
        run_experiment(Experiment(samples=pd.DataFrame({"g": [0.1]}), method="lhs"), outputs=["HeadTotal"])
    with pytest.raises(KeyError, match="unknown parameter"):
        run_experiment(Experiment(sample={"nope": Uniform(0, 1)}, n=2, seed=1), outputs=["HeadTotal"])
    with pytest.raises(ValueError, match="record_every"):
        run_experiment(Experiment(), outputs=["JuniorHiringRatio"], record_every=1.0)


# ---- derived outputs -------------------------------------------------------------------------------------------------


def test_derived_identities_on_the_base_run() -> None:
    res = run_experiment(
        Experiment(), outputs=["OnshoreTotal", "HeadLoc_ON", "IndiaPeople_ConsIndia", "IndiaPeople_VendIndia"]
    )
    assert np.allclose(res.series["OnshoreTotal"], res.series["HeadLoc_ON"], rtol=1e-12, atol=0)
    j = int(np.flatnonzero(res.years == 2040.0)[0])
    assert res.series["IndiaPeople_ConsIndia"][0, j] == pytest.approx(5.88e6, rel=0.005)
    assert res.series["IndiaPeople_VendIndia"][0, j] == pytest.approx(1.73e6, rel=0.005)
    assert set(res.series) == {
        "OnshoreTotal",
        "HeadLoc_ON",
        "IndiaPeople_ConsIndia",
        "IndiaPeople_VendIndia",
        "Q1_ConsOnshore",
        "Q1_VendOnshore",
        "Q1_ConsIndia",
        "Q1_VendIndia",
    }


def test_every_derived_output() -> None:
    res = run_experiment(Experiment(), outputs=list(DERIVED), record_every=0.25)
    s = res.series
    vend = s["WorkShare_OIT"] + s["WorkShare_GSI"] + s["WorkShare_BQ"]
    assert np.array_equal(s["VendorWorkShare"], vend)
    assert np.array_equal(s["IndiaPeople"], s["IndiaPeople_VendIndia"] + s["IndiaPeople_ConsIndia"])
    assert np.array_equal(s["IndiaTotal"], s["Q1_ConsIndia"] + s["Q1_VendIndia"])
    assert s["JuniorHiringRatio"][0, 0] == 1.0
    assert ((s["EffortShare_revenue_weighted"] > 0) & (s["EffortShare_revenue_weighted"] < 1)).all()


# ---- pct -------------------------------------------------------------------------------------------------------------


def proto_pct(xs: list[float], q: float) -> float:  # phase7_runs.py:151-153, verbatim
    xs = sorted(xs)
    i = (len(xs) - 1) * q
    f = math.floor(i)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (i - f)


def test_pct_matches_the_prototype_bit_for_bit() -> None:
    rng = np.random.default_rng(42)
    for n in (1, 2, 10, 99, 300, 1000):
        a = rng.lognormal(size=(n, 40))
        for q in (0.0, 0.1, 0.25, 0.5, 0.9, 0.95, 1.0):
            fresh = pct(a, q)
            for j in range(a.shape[1]):
                assert fresh[j] == proto_pct(a[:, j].tolist(), q), (n, q, j)


# ---- memory warning --------------------------------------------------------------------------------------------------


def test_memory_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = len(ROW_KEYS) + len(EXTRA_KEYS)
    assert estimated_bytes(10_000, 17, keys) < runner.MEMORY_WARN_BYTES < estimated_bytes(50_000, 17, keys)
    monkeypatch.setattr(runner, "MEMORY_WARN_BYTES", estimated_bytes(1, 17, keys) - 1)
    with pytest.warns(ResourceWarning, match="GiB"):
        res = run_experiment(Experiment(), outputs="all", workers=1)
    assert list(res.series) == [*ROW_KEYS, *EXTRA_KEYS]


# ---- results ---------------------------------------------------------------------------------------------------------


def test_invalid_runs_and_views() -> None:
    samples = pd.DataFrame({"g": [0.1, 1.5, 0.12]})
    res = run_experiment(
        Experiment(samples=samples),
        outputs=["HeadTotal", "Vi_OIT", "Head_OIT", "Revenue_OIT", *_q3_keys()],
        validate=False,
        keep_state=True,
    )
    assert res.valid.tolist() == [True, False, True] and res.meta["n_invalid"] == 1
    with pytest.warns(UserWarning, match="1 invalid run"):
        bands = res.bands("HeadTotal", ratio_to=2024, years=(2024, 2032))
    assert bands.attrs["n_invalid"] == 1
    assert list(bands.index) == [float(y) for y in range(2024, 2033)] and [float(c) for c in bands.columns] == [
        0.1,
        0.5,
        0.9,
    ]
    q3 = res.q3()
    assert q3.loc[1].isna().all() and q3.loc[[0, 2]].notna().all().all()
    assert int(res.q3_counts()["OIT"].sum()) == 2
    frame = res.frame("HeadTotal")
    assert frame.shape == (3, 17) and frame.index.name == "run" and frame.columns.name == "year"
    long = res.long(["HeadTotal", "Vi_OIT"])
    assert list(long.columns) == ["run", "year", "key", "value"] and len(long) == 2 * 3 * 17
    assert isinstance(long["key"].dtype, pd.CategoricalDtype)
    vi = long.loc[long["key"] == "Vi_OIT", "value"].to_numpy()
    assert np.array_equal(vi, res.series["Vi_OIT"].ravel(), equal_nan=True)  # the invalid run holds NaN
    ratio = res.ratio("HeadTotal")
    assert (ratio[:, 0] == 1.0).all()
    assert res.final_state is not None and res.final_state.n == 3 and res.mins is not None
    assert set(res.meta["versions"]) == {"ai-it-labour-sim", "numpy", "pandas", "scipy"}
    assert "NPY_DISABLE_CPU_FEATURES" in res.meta


def _q3_keys() -> list[str]:
    return [f"{p}_{v}" for v in ("GSI", "BQ") for p in ("Vi", "Head", "Revenue")]


def test_explicit_samples_match_random_draws() -> None:
    """An explicit design is used as given: the MC draw of phase7_runs.py through samples equals BatchParams."""
    rng = random.Random(3)
    draws = pd.DataFrame([{"g": rng.uniform(0.06, 0.15), "TMBrake": rng.uniform(0.2, 0.6)} for _ in range(5)])
    res = run_experiment(Experiment(samples=draws), outputs=["HeadTotal"])
    ref = run_batch(BatchParams.baseline(5, g=draws["g"].tolist(), TMBrake=draws["TMBrake"].tolist()))
    assert np.array_equal(res.series["HeadTotal"], ref.series["HeadTotal"])
