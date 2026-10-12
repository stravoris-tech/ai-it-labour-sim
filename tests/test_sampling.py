"""Sampling: distribution bounds and moments, Latin hypercube strata, Iman-Conover rank correlation and seeding."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import truncnorm

from aisim import Choice, Experiment, Fixed, Triangular, TruncNormal, Uniform, run_experiment
from aisim.experiment.sampling import Distribution, draw

N = 100_000

F2_TARGET = np.array(
    [
        [1.0, 0.5, -0.3, 0.0, 0.2],
        [0.5, 1.0, 0.0, 0.1, 0.0],
        [-0.3, 0.0, 1.0, 0.0, 0.0],
        [0.0, 0.1, 0.0, 1.0, -0.4],
        [0.2, 0.0, 0.0, -0.4, 1.0],
    ]
)
"""The recon 04 F2 Spearman target (positive definite)."""


def spearman(x: np.ndarray) -> np.ndarray:
    ranks = np.argsort(np.argsort(x, axis=0), axis=0).astype(np.float64)
    out: np.ndarray = np.asarray(np.corrcoef(ranks, rowvar=False), dtype=np.float64)
    return out


def triangular_moments(a: float, c: float, b: float) -> tuple[float, float]:
    return (a + b + c) / 3, (a * a + b * b + c * c - a * b - a * c - b * c) / 18


CASES: list[tuple[Distribution, float, float, float, float]] = [
    # distribution, lower, upper, mean, variance
    (Uniform(2.0, 5.0), 2.0, 5.0, 3.5, 9 / 12),
    (Triangular(0.0, 0.3, 1.0), 0.0, 1.0, *triangular_moments(0.0, 0.3, 1.0)),
    (Triangular(1.0, 1.0, 2.0), 1.0, 2.0, *triangular_moments(1.0, 1.0, 2.0)),
    (
        TruncNormal(0.0, 1.0, -1.0, 2.0),
        -1.0,
        2.0,
        float(truncnorm.mean(-1.0, 2.0)),
        float(truncnorm.var(-1.0, 2.0)),
    ),
    (Choice([1.0, 2.0, 3.0], [0.2, 0.3, 0.5]), 1.0, 3.0, 2.3, 0.2 * 1 + 0.3 * 4 + 0.5 * 9 - 2.3**2),
    (Fixed(0.7), 0.7, 0.7, 0.7, 0.0),
]


@pytest.mark.parametrize("method", ["random", "lhs"])
@pytest.mark.parametrize(("dist", "lo", "hi", "mean", "var"), CASES, ids=lambda c: type(c).__name__)
def test_bounds_and_moments(dist: Distribution, lo: float, hi: float, mean: float, var: float, method: str) -> None:
    """At N = 100,000: inside the support, mean within 0.5% of the range and variance within 2% (plus 1e-6)."""
    x = draw({"x": dist}, N, seed=11, method="lhs" if method == "lhs" else "random")["x"].to_numpy()
    assert x.min() >= lo and x.max() <= hi
    assert abs(x.mean() - mean) <= 0.005 * max(hi - lo, 1e-12)
    assert abs(x.var() - var) <= 0.02 * var + 1e-6


def test_choice_frequencies() -> None:
    x = draw({"x": Choice([1.0, 2.0, 3.0], [0.2, 0.3, 0.5])}, N, seed=5)["x"].to_numpy()
    freq = [float((x == v).mean()) for v in (1.0, 2.0, 3.0)]
    assert freq == pytest.approx([0.2, 0.3, 0.5], abs=0.01)


def test_lhs_one_point_per_stratum() -> None:
    n = 1000
    df = draw({"a": Uniform(0.0, 1.0), "b": Uniform(0.0, 1.0), "c": Uniform(0.0, 1.0)}, n, seed=3, method="lhs")
    for col in df.columns:
        strata = np.floor(df[col].to_numpy() * n).astype(int)
        assert sorted(strata) == list(range(n))


def test_iman_conover_reaches_the_target() -> None:
    sample: dict[str, Distribution] = {
        "a": Uniform(0.0, 1.0),
        "b": Triangular(0.0, 0.3, 1.0),
        "c": TruncNormal(0.0, 1.0, -1.0, 2.0),
        "d": Uniform(2.0, 4.0),
        "e": Uniform(-1.0, 1.0),
    }
    names = list(sample)
    corr = {
        (names[i], names[j]): float(F2_TARGET[i, j]) for i in range(5) for j in range(i + 1, 5) if F2_TARGET[i, j] != 0
    }
    plain = draw(sample, 10_000, seed=21)
    df = draw(sample, 10_000, seed=21, correlation=corr)
    achieved = spearman(df.to_numpy())
    assert np.abs(achieved - F2_TARGET).max() <= 0.01
    for col in names:  # marginals unchanged: the same values, reordered
        assert np.array_equal(np.sort(df[col].to_numpy()), np.sort(plain[col].to_numpy()))


def test_correlation_must_be_positive_definite() -> None:
    sample: dict[str, Distribution] = {"a": Uniform(0, 1), "b": Uniform(0, 1), "c": Uniform(0, 1)}
    bad = {("a", "b"): 0.9, ("a", "c"): 0.9, ("b", "c"): -0.9}
    with pytest.raises(ValueError, match="positive definite"):
        draw(sample, 100, seed=1, correlation=bad)
    with pytest.raises(ValueError, match="not sampled"):
        draw(sample, 100, seed=1, correlation={("a", "z"): 0.5})


@pytest.mark.parametrize("method", ["random", "lhs"])
def test_seeding(method: str) -> None:
    sample: dict[str, Distribution] = {"g": Uniform(0.06, 0.15), "Verif": TruncNormal(0.43, 0.05, 0.3, 0.56)}
    a = draw(sample, 500, seed=7, method="lhs" if method == "lhs" else "random")
    b = draw(sample, 500, seed=7, method="lhs" if method == "lhs" else "random")
    c = draw(sample, 500, seed=8, method="lhs" if method == "lhs" else "random")
    pd.testing.assert_frame_equal(a, b, check_exact=True)
    assert not np.array_equal(a.to_numpy(), c.to_numpy())


def test_levers_draw_in_declared_order() -> None:
    """A lever's draws do not depend on the levers declared after it."""
    one = draw({"g": Uniform(0.0, 1.0)}, 50, seed=4)
    two = draw({"g": Uniform(0.0, 1.0), "Verif": Uniform(0.0, 1.0)}, 50, seed=4)
    assert np.array_equal(one["g"].to_numpy(), two["g"].to_numpy())


def test_seed_required_when_sampling() -> None:
    with pytest.raises(ValueError, match="seed is required"):
        run_experiment(Experiment(sample={"g": Uniform(0.06, 0.15)}, n=3), outputs=["HeadTotal"])


def test_distribution_arguments_checked() -> None:
    with pytest.raises(ValueError):
        Uniform(2.0, 1.0)
    with pytest.raises(ValueError):
        Triangular(0.0, 2.0, 1.0)
    with pytest.raises(ValueError):
        TruncNormal(0.0, 0.0, -1.0, 1.0)
    with pytest.raises(ValueError):
        Choice([1.0, 2.0], [1.0])
