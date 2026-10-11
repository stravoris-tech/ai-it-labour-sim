"""The numerics guard (``tools/numerics_probe.py``, ``tests/conftest.py``): its comparison and its inputs.

The guard passing on this machine is shown by the parity tests that depend on it. These tests are its positive
controls: a one-ulp change is detected, and the regression points still name the engine's forms.
"""

from __future__ import annotations

import math

import numpy as np

from aisim.batch.util import F, pw
from tools.numerics_probe import (
    DISABLE,
    GUARD_N,
    MAX_SAVED,
    Form,
    check,
    compare,
    forms,
    guard_message,
    load_regression,
    py_power,
    run_forms,
)


def test_compare_detects_one_ulp() -> None:
    want = np.random.default_rng(1).uniform(0.1, 10.0, 1000)
    got = want.copy()
    got[[3, 500]] = np.nextafter(got[[3, 500]], math.inf)
    got[7] = np.nextafter(got[7], -math.inf)
    bad, ulp = compare(got, want)
    assert np.flatnonzero(bad).tolist() == [3, 7, 500]
    assert ulp == 1
    same, zero = compare(want.copy(), want)
    assert not same.any()
    assert zero == 0


def test_compare_counts_ulps_across_zero() -> None:
    """``-0.0`` and ``0.0`` are 0 ulp apart but not bit-identical; the smallest subnormals of each sign are 2 apart."""
    tiny = math.ulp(0.0)
    bad, ulp = compare(np.array([-0.0, -tiny]), np.array([0.0, tiny]))
    assert bad.tolist() == [True, True]
    assert ulp == 2


def test_check_detects_a_perturbed_kernel() -> None:
    """Positive control: a power kernel one ulp off on 1 input in 64 is caught, and the inputs are saved."""

    def off(a: F, b: F) -> F:
        out = pw(a, b)
        out[::64] = np.nextafter(out[::64], math.inf)
        return out

    rng = np.random.default_rng(2)
    a, b = rng.uniform(0.1, 10.0, GUARD_N), rng.uniform(-2.0, 2.0, GUARD_N)
    form = Form("perturbed", True, off, py_power, lambda r, n: (a, b))
    result = check(form, a, b)
    assert result.mismatches == GUARD_N // 64
    assert result.max_ulp == 1
    assert result.inputs == [[float(a[i]), float(b[i])] for i in range(0, 64 * MAX_SAVED, 64)]
    honest = check(Form("pw", True, pw, py_power, lambda r, n: (a, b)), a, b)
    assert honest.mismatches == 0


def test_regression_points_name_engine_forms() -> None:
    """Every regression form is an engine form, so the guard really checks its points; and a form's points are added."""
    points = load_regression()
    engine = {f.name for f in forms() if f.engine}
    assert set(points) <= engine
    assert len(points) == 10
    assert all(0 < len(p) <= MAX_SAVED and all(len(ab) == 2 for ab in p) for p in points.values())
    name = next(iter(points))
    plain = {r.name: r.n for r in run_forms(16, engine_only=True)}
    extended = {r.name: r.n for r in run_forms(16, extra=points, engine_only=True)}
    assert extended[name] == plain[name] + len(points[name])


def test_guard_message_names_cause_and_fix() -> None:
    results = run_forms(16, engine_only=True)
    message = guard_message(results)
    for part in ("AVX-512", f'NPY_DISABLE_CPU_FEATURES="{DISABLE}"', "ARM64", "macOS", "__cpu_dispatch__", "In use"):
        assert part in message, part
