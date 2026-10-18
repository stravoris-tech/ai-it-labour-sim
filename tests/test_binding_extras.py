"""The binding extras of slice 13: when C5's price floor and C6's AI-discount ceiling bind, and R4's multiplier.

- **Off values.** Every flag is 0 and every multiplier 1 whenever its strength is 0: on ``phase7``, ``phase8`` and
  ``phase8_highadoption`` in Base and ``EXTREME``, and on ``phase9`` in ``EXTREME`` with the three terms off.
- **Scalar-batch parity** of the new extras on ``phase9`` in the stress set and in ``EXTREME``, bit for bit.
- **Onset.** On ``phase9`` in Fast AI, the first step each flag or multiplier leaves its off value is the onset by
  difference against the same run with that term off (Q05 B1's definition): for C5 and C6, the first row (rows and
  the earlier extras) that differs; for R4, the first step whose seeker exits (the S8f trace) differ.

The rows themselves are covered by the existing parity tests (rows, the 43 families, mins), which these extras leave
unchanged.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from aisim import Params, RunResult, run
from aisim.batch.engine import run_batch
from aisim.batch.params import BatchParams
from aisim.batch.record import EXTRA_KEYS
from aisim.batch.state import BatchState
from aisim.dims import LEVELS, REGIONS, TYPES, VENDORS
from aisim.scenarios import EXTREME, SCENARIOS
from tests.test_loops import DOCUMENTED_EXTRAS_13

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""Scalar-batch parity needs numpy's kernels to match libm (``tests/conftest.py``)."""

DT = 1 / 16
STRESS = {"g": 0.20, "VerifDecline": 0.10, "PriceShock_OIT": 0.2}
"""Q05 B3's stress set (``aisim.scenarios.STRESS_SCENARIOS``), spelled out so this file does not depend on it."""
C5 = [f"PriceFloorBinds_{v}_{k}" for v in VENDORS for k in TYPES]
C6 = [f"AIDiscCeilBinds_{v}" for v in VENDORS]
R4 = [f"SkillErosionMult_{r}_{lv}" for r in REGIONS for lv in LEVELS]
OFF = {"PriceFloor": 0.0, "AIDiscCeil": 0.0, "R4a": 0.0, "R4aIN": 0.0}
EARLIER = EXTRA_KEYS[:106]


def scalar_run(params: Params, trace: Any = None) -> RunResult:
    return run(params, record_every=DT, extras=True, trace=trace)


def test_the_three_families_are_the_documented_block() -> None:
    assert (*C5, *C6, *R4) == DOCUMENTED_EXTRAS_13


@pytest.mark.parametrize(
    ("model", "case"),
    [(m, c) for m in ("phase7", "phase8", "phase8_highadoption") for c in ("Base", "EXTREME")] + [("phase9", "off")],
)
def test_off_values_at_strength_zero(model: str, case: str) -> None:
    over = {**dict(EXTREME), **OFF} if case == "off" else dict(EXTREME) if case == "EXTREME" else {}
    params = Params.baseline(model).with_overrides(**over)
    assert all(params.scalars[k] == 0.0 for k in OFF)
    extras = scalar_run(params).extras
    assert len(extras) == 257
    for e in extras:
        assert all(e[k] == 0.0 for k in (*C5, *C6))
        assert all(e[k] == 1.0 for k in R4)


@pytest.mark.parametrize("case", ["stress", "EXTREME"])
def test_batch_matches_scalar_on_the_new_extras(case: str) -> None:
    """Bit for bit, on ``phase9`` where every one of the three terms acts."""
    params = Params.baseline("phase9").with_overrides(**(STRESS if case == "stress" else dict(EXTREME)))
    extras = scalar_run(params).extras
    batch = run_batch(
        BatchParams.stack([params]), BatchState.baseline(1), record_every=DT, outputs=list(DOCUMENTED_EXTRAS_13)
    )
    for k in DOCUMENTED_EXTRAS_13:
        assert np.array_equal(batch.series[k][0], [e[k] for e in extras]), k
    for family in (C5, C6):
        assert any(e[k] == 1.0 for e in extras for k in family)
    assert any(e[k] != 1.0 for e in extras for k in R4)


def first_step(flags: list[bool]) -> int:
    return flags.index(True)


def test_onset_equals_the_onset_by_difference() -> None:
    """``phase9`` in Fast AI: C5 at 2028.0, C6 at 2030.375 and R4 at 2024.75 (Q05 B3, recon 13 E4)."""
    params = Params.baseline("phase9").with_overrides(**dict(SCENARIOS["Fast AI"]))
    seek: dict[str, list[list[float]]] = {"on": [], "off": []}

    def keep(label: str) -> Any:
        def cb(step: int, y: float, sid: str, o: Any) -> None:
            if sid == "S8f":
                seek[label].append([o.pool[r][lv]["seek_exit"] for r in REGIONS for lv in LEVELS])

        return cb

    on = scalar_run(params, trace=keep("on"))
    years = [row["year"] for row in on.rows]

    def by_difference(off: RunResult) -> int:
        return first_step(
            [
                a != b or any(x[k] != z[k] for k in EARLIER)
                for a, b, x, z in zip(on.rows, off.rows, on.extras, off.extras, strict=True)
            ]
        )

    c5 = first_step([any(e[k] == 1.0 for k in C5) for e in on.extras])
    c6 = first_step([any(e[k] == 1.0 for k in C6) for e in on.extras])
    r4 = first_step([any(e[k] != 1.0 for k in R4) for e in on.extras])
    assert c5 == by_difference(scalar_run(params.with_overrides(PriceFloor=0.0)))
    assert c6 == by_difference(scalar_run(params.with_overrides(AIDiscCeil=0.0)))
    scalar_run(params.with_overrides(R4a=0.0, R4aIN=0.0), trace=keep("off"))
    assert r4 == first_step([a != b for a, b in zip(seek["on"], seek["off"], strict=True)])
    assert (years[c5], years[c6], years[r4]) == (2028.0, 2030.375, 2024.75)
