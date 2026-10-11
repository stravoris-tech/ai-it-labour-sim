"""Small numeric helpers: ``clamp``, ``ramp`` and ``softmax`` (``phase7_sim.py`` lines 137-147).

They keep the prototype's arithmetic exactly, including ``math.e ** x`` (not ``math.exp``) in ``softmax``. The one
behaviour change is that ``ramp`` with ``start == end`` is a step instead of raising ``ZeroDivisionError``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

E = math.e


def clamp(x: float, lo: float, hi: float) -> float:
    """Return ``x`` limited to ``[lo, hi]``."""
    return max(lo, min(hi, x))


def ramp(year: float, start: float, end: float, v0: float, v1: float) -> float:
    """Return ``v0`` before ``start``, ``v1`` from ``end`` on, and a straight line between them.

    With ``start == end`` the ramp is a step: ``v0`` before ``start`` and ``v1`` from ``start`` on.
    """
    if start == end:
        return v0 if year < start else v1
    return v0 + (v1 - v0) * clamp((year - start) / (end - start), 0.0, 1.0)


def softmax(d: Mapping[str, float]) -> dict[str, float]:
    """Return the logit shares of the values in ``d``, keyed and ordered as ``d``."""
    mx = max(d.values())
    ez = {k: E ** (v - mx) for k, v in d.items()}
    z = sum(ez.values())
    return {k: ez[k] / z for k in d}
