"""Process noise (slice 6, ``aisim.noise``): the OU generator, its streams, and noise in the two-phase runs."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import replace

import numpy as np
import pytest

from aisim import BatchParams, Experiment, Noise, Params, Uniform, run_experiment, run_scenarios
from aisim.batch.engine import BatchResult
from aisim.batch.state import pack, unpack
from aisim.batch.util import F
from aisim.dims import EMPLOYERS, SECTORS, TYPES, VENDORS
from aisim.noise import CHANNELS, ou_factors, ou_paths
from aisim.perturb import run_batch_from, run_from, start_step_of
from aisim.scalar.engine import RunResult
from aisim.scenarios import SCENARIOS, tornado_levers
from aisim.state import load_initial_state
from tests.helpers import people

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The parity tests here need numpy's kernels to match libm (``tests/conftest.py``)."""

DT = 1 / 16
Y = 2026.5
K = start_step_of(Y, DT)
STEPS = 256
BASE = Params.baseline()
ALL_SIX = {c: Noise(0.05, 1.0) for c in CHANNELS}


# ---- the generator ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("dt", [1 / 16, 1 / 32])
@pytest.mark.parametrize("tau", [0.5, 1.0, 2.0])
def test_ou_statistics(dt: float, tau: float) -> None:
    """10,000 paths from 0: after the start has decayed (12 tau), the sd is ``sigma`` and the one-year autocorrelation
    ``exp(-1 / tau)``, each within 3 standard errors, at either dt (exact OU, recon 06 C2)."""
    sigma, n = 0.05, 10_000
    t0 = 12 * tau
    steps = round((t0 + 1) / dt)
    lag = round(1 / dt)
    parts = [
        ou_paths({"cap": Noise(sigma, tau)}, 99, range(lo, lo + 2500), start_step=0, steps=steps, dt=dt)["cap"]
        for lo in range(0, n, 2500)
    ]
    x = np.concatenate(parts)
    a, b = x[:, steps - lag], x[:, steps]
    sd = float(np.std(b))
    assert abs(sd - sigma) <= 3 * sigma / math.sqrt(2 * n), sd
    rho, theory = float(np.corrcoef(a, b)[0, 1]), math.exp(-1 / tau)
    assert abs(rho - theory) <= 3 * (1 - theory**2) / math.sqrt(n), (rho, theory)


def test_noise_is_zero_up_to_and_including_y() -> None:
    f = ou_factors(ALL_SIX, 5, [0, 1, 7], start_step=K, steps=STEPS, dt=DT)
    x = ou_paths(ALL_SIX, 5, [0, 1, 7], start_step=K, steps=STEPS, dt=DT)
    assert list(f) == list(CHANNELS)
    for c in CHANNELS:
        assert f[c].shape == (3, STEPS + 1)
        assert np.all(x[c][:, : K + 1] == 0.0) and np.all(f[c][:, : K + 1] == 1.0)
        assert np.all(x[c][:, K + 1] != 0.0)


def test_streams_are_per_run_and_per_channel() -> None:
    """A run's path depends on its index, not on the runs beside it or on which other channels are on."""
    one = ou_paths({"demand": Noise(0.05)}, 3, [4], start_step=K, steps=STEPS, dt=DT)["demand"]
    many = ou_paths(ALL_SIX, 3, [9, 4, 2], start_step=K, steps=STEPS, dt=DT)["demand"]
    assert np.array_equal(one[0], many[1])
    assert not np.array_equal(many[0], many[1])
    assert ou_factors({"cap": Noise(0.0)}, 3, [0], start_step=K, steps=STEPS, dt=DT) == {}


# ---- noise in the runs -----------------------------------------------------------------------------------------------


def experiment(noise: Mapping[str, Noise], n: int = 40, seed: int = 11) -> Experiment:
    return Experiment(
        sample=tornado_levers(Y), n=n, method="lhs", seed=seed, perturb_from=Y, noise=noise, noise_seed=2026
    )


def test_sigma_zero_equals_no_noise() -> None:
    off = run_experiment(experiment({}), outputs="all", keep_state=True)
    zero = run_experiment(experiment({c: Noise(0.0) for c in CHANNELS}), outputs="all", keep_state=True)
    for k in off.series:
        assert np.array_equal(off.series[k], zero.series[k]), k
    assert off.final_state is not None and zero.final_state is not None
    sa, sb = off.final_state.arrays(), zero.final_state.arrays()
    assert all(np.array_equal(sa[k], sb[k]) for k in sa)


def test_rows_up_to_y_are_unchanged_by_noise() -> None:
    """With all six channels on, every row up to and including Y equals the run without noise; after Y it differs."""
    off = run_experiment(experiment({}), outputs="all", record_every=0.25)
    on = run_experiment(experiment(ALL_SIX), outputs="all", record_every=0.25)
    upto = off.years <= Y
    for k in off.series:
        assert np.array_equal(off.series[k][:, upto], on.series[k][:, upto]), k
    assert not np.array_equal(off.series["HeadTotal"][:, -1], on.series["HeadTotal"][:, -1])


def scalar_noise(factors: Mapping[str, F], i: int) -> dict[str, list[float]]:
    return {c: a[i].tolist() for c, a in factors.items()}


def assert_bit_identical(batch: BatchResult, i: int, scalar: RunResult) -> None:
    assert batch.rows(i) == scalar.rows
    fb, fs = batch.final_state.arrays(), pack([scalar.final_state]).arrays()
    for name, a in fs.items():
        assert np.array_equal(fb[name][i], a[0]), name
    assert {k: float(a[i]) for k, a in batch.mins.items()} == scalar.mins


PARITY_RUNS = [
    BASE,
    BASE.with_overrides(g=0.15, PriceHorizon=8.0, AICostDecline=0.08),
    BASE.with_overrides(**SCENARIOS["Compute shock"]),
    BASE.with_overrides(JuniorCut=0.1, aL_max=0.45),
    BASE.with_overrides(**SCENARIOS["Downturn"]),
]


def check_parity(noise: Mapping[str, Noise], runs: Sequence[Params]) -> None:
    factors = ou_factors(noise, 77, range(len(runs)), start_step=K, steps=STEPS, dt=DT)
    batch = run_batch_from(BatchParams.stack(list(runs)), Y=Y, record_every=0.25, noise=factors)
    assert batch.finite.all()
    for i, p in enumerate(runs):
        assert_bit_identical(batch, i, run_from(BASE, p, Y=Y, record_every=0.25, noise=scalar_noise(factors, i)))


@pytest.mark.parametrize("channel", CHANNELS)
def test_parity_per_channel(channel: str) -> None:
    """Scalar against batch with one channel's noise: bit-identical (recon 06 C4). Small N in the default gate."""
    check_parity({channel: Noise(0.1)}, PARITY_RUNS[:2])


def test_parity_all_six() -> None:
    check_parity({c: Noise(0.1, 0.5 + i / 4) for i, c in enumerate(CHANNELS)}, PARITY_RUNS[:3])


@pytest.mark.slow
@pytest.mark.parametrize("channel", CHANNELS)
def test_parity_per_channel_full(channel: str) -> None:
    check_parity({channel: Noise(0.1)}, PARITY_RUNS)


@pytest.mark.slow
def test_parity_all_six_full() -> None:
    check_parity({c: Noise(0.1, 0.5 + i / 4) for i, c in enumerate(CHANNELS)}, PARITY_RUNS)


def test_independent_of_workers_and_chunks() -> None:
    """Noisy results are bit-identical for workers 1 and 4 and chunk sizes 7, 250 and auto (recon 06 C3)."""
    exp = experiment(ALL_SIX, n=300)
    keys = ["HeadTotal", "RevenueTot", "Mix_OIT_FP", "G"]
    ref = run_experiment(exp, outputs=keys, workers=1)
    for workers in (1, 4):
        for chunk in (7, 250, None):
            other = run_experiment(exp, outputs=keys, workers=workers, chunk_size=chunk)
            for k in keys:
                assert np.array_equal(ref.series[k], other.series[k]), (workers, chunk, k)


def test_noise_never_touches_the_lever_samples() -> None:
    off = run_experiment(experiment({}), outputs=["HeadTotal"])
    on = run_experiment(experiment(ALL_SIX), outputs=["HeadTotal"])
    same_seed = run_experiment(replace(experiment(ALL_SIX), noise_seed=11), outputs=["HeadTotal"])
    assert off.samples.equals(on.samples) and off.samples.equals(same_seed.samples)


def test_run_scenarios_share_the_noise() -> None:
    """Run i has the same noise in every scenario block: ``G`` (exogenous, untouched by Compute shock and
    ``PriceHorizon``) is equal across blocks and equals the base ``G`` times the run's demand factor."""
    exp = Experiment(
        sample={"PriceHorizon": Uniform(4.0, 8.0)},
        n=6,
        seed=4,
        perturb_from=Y,
        noise={"demand": Noise(0.05)},
        noise_seed=9,
    )
    res = run_scenarios(exp, [None, "Compute shock"], outputs=["G"], record_every=DT)
    a, b = res[None].series["G"], res["Compute shock"].series["G"]
    assert np.array_equal(a, b)
    assert not np.array_equal(a[0], a[1])
    factors = ou_factors(exp.noise, 9, range(6), start_step=K, steps=STEPS, dt=DT)["demand"]
    plain = run_experiment(Experiment(perturb_from=Y), outputs=["G"], record_every=DT).series["G"][0]
    assert np.array_equal(a, plain * factors)


def test_integrity_with_all_six_channels() -> None:
    """All six channels at sigma = 0.1, 100 runs: people conservation, WorkCheck, no negative stocks, shares summing
    to 1, adoption in [0, 1] (recon 06 C1 checks)."""
    srct = [f"SrcT_{x}_{e}" for x in SECTORS for e in EMPLOYERS]
    mix = [f"Mix_{v}_{k}" for v in VENDORS for k in TYPES]
    frac = [f"A_{e}" for e in EMPLOYERS] + [f"AC_{x}" for x in SECTORS]
    keys = ["Grad_total", "Ext_total", "WorkCheckMax", *srct, *mix, *frac]
    exp = Experiment(n=100, perturb_from=Y, noise={c: Noise(0.1) for c in CHANNELS}, noise_seed=5)
    res = run_experiment(exp, outputs=keys, record_every=DT, keep_state=True)
    assert res.valid.all() and res.final_state is not None and res.mins is not None
    s = res.series
    start = people(load_initial_state())
    for i in range(res.n):
        inflow = float(np.sum((s["Grad_total"][i, :-1] + s["Ext_total"][i, :-1]) / 16))
        total = people(unpack(res.final_state, i))
        assert abs(total - start - inflow) <= 1e-9 * total, i
        sp = unpack(res.final_state, i)["SrcPerc"]
        assert max(abs(sum(sp[x].values()) - 1) for x in SECTORS) <= 1e-9
    assert np.max(s["WorkCheckMax"]) <= 1e-9
    assert min(float(np.min(a)) for a in res.mins.values()) >= -1e-12
    for x in SECTORS:
        assert np.max(np.abs(sum(s[f"SrcT_{x}_{e}"] for e in EMPLOYERS) - 1)) <= 1e-9
    for v in VENDORS:
        assert np.max(np.abs(sum(s[f"Mix_{v}_{k}"] for k in TYPES) - 1)) <= 1e-9
    for k in frac:
        assert np.min(s[k]) >= 0 and np.max(s[k]) <= 1


def test_meta_records_perturb_from_and_noise() -> None:
    res = run_experiment(experiment({"demand": Noise(0.009), "cap": Noise(0.0, 2.0)}, n=3), outputs=["HeadTotal"])
    noise = {"demand": {"sigma": 0.009, "tau": 1.0}, "cap": {"sigma": 0.0, "tau": 2.0}}
    assert res.meta["perturb_from"] == Y and res.meta["noise"] == noise and res.meta["noise_seed"] == 2026
    exp = res.meta["experiment"]
    assert exp["perturb_from"] == Y and exp["noise"] == noise and exp["noise_seed"] == 2026
    assert json.loads(json.dumps(res.meta))["noise"] == noise
    plain = run_experiment(Experiment(), outputs=["HeadTotal"])
    assert plain.meta["perturb_from"] is None and plain.meta["noise"] == {} and plain.meta["noise_seed"] is None
