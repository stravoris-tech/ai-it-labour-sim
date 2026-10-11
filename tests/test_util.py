"""``clamp``, ``softmax`` and ``ramp``, including the step case ``start == end``."""

from __future__ import annotations

import math

import pytest

from aisim.util import clamp, ramp, softmax


def test_clamp() -> None:
    assert clamp(0.5, 0.0, 1.0) == 0.5
    assert clamp(-1.0, 0.0, 1.0) == 0.0
    assert clamp(2.0, 0.0, 1.0) == 1.0


def test_softmax() -> None:
    shares = softmax({"a": 0.0, "b": math.log(3.0)})
    assert list(shares) == ["a", "b"]
    assert shares["a"] == pytest.approx(0.25)
    assert shares["b"] == pytest.approx(0.75)
    assert sum(shares.values()) == pytest.approx(1.0)
    assert softmax({"a": 1000.0, "b": 1000.0}) == {"a": 0.5, "b": 0.5}


def test_ramp_window() -> None:
    assert ramp(2026.0, 2027.0, 2031.0, 0.3, 0.7) == 0.3
    assert ramp(2027.0, 2027.0, 2031.0, 0.3, 0.7) == 0.3
    assert ramp(2029.0, 2027.0, 2031.0, 0.3, 0.7) == pytest.approx(0.5)
    assert ramp(2031.0, 2027.0, 2031.0, 0.3, 0.7) == pytest.approx(0.7)
    assert ramp(2035.0, 2027.0, 2031.0, 0.3, 0.7) == pytest.approx(0.7)


def test_ramp_step_when_start_equals_end() -> None:
    assert ramp(2027.9, 2028.0, 2028.0, 0.1, 0.9) == 0.1
    assert ramp(2028.0, 2028.0, 2028.0, 0.1, 0.9) == 0.9
    assert ramp(2030.0, 2028.0, 2028.0, 0.1, 0.9) == 0.9
