"""Slice 4 acceptance: the Phase 7 Monte Carlo, Q3 counts and tornado through the experiment API, bit-equal to the
goldens.

The 300 MC samples are drawn exactly as ``phase7_runs.py`` draws them (``random.Random(7)``, ``rng.uniform(lo, hi)``
over ``TORNADO`` in list order, line 143) and passed as an explicit design. The bands, the Q3 counts and the tornado
(29 explicit samples: the base and 28 one-at-a-time runs) must equal ``reference/goldens/phase7_results.json`` bit
for bit. The batched engine is involved, so this needs numpy's kernels to match libm (``tests/conftest.py``).
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from aisim import Experiment, Params, run_experiment
from aisim.dims import VENDORS
from aisim.scenarios import TORNADO

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")

GOLDEN = Path(__file__).resolve().parent.parent / "reference" / "goldens" / "phase7_results.json"
OUTS = ("HeadTotal", "Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia")
Q3_KEYS = tuple(f"{p}_{v}" for v in VENDORS for p in ("Vi", "Head", "Revenue"))


@pytest.fixture(scope="module")
def golden() -> dict[str, Any]:
    # Any: parsed JSON.
    with GOLDEN.open(encoding="utf-8") as f:
        out: dict[str, Any] = json.load(f)
    return out


def mc_samples() -> pd.DataFrame:
    rng = random.Random(7)
    draws = []
    for _ in range(300):
        over = {p: rng.uniform(lo, hi) for p, lo, hi, _ in TORNADO}  # phase7_runs.py:143
        draws.append(over)
    return pd.DataFrame(draws)


def test_mc_bands_and_q3_counts(golden: dict[str, Any]) -> None:
    res = run_experiment(Experiment(samples=mc_samples()), outputs=[*OUTS, *Q3_KEYS], workers=1)
    assert res.n == 300 and res.n_invalid == 0
    assert [int(y) for y in res.years] == golden["mc"]["years"]
    equal = total = 0
    for key in OUTS:
        bands = res.bands(key, ratio_to=2024)
        for q in (0.1, 0.5, 0.9):
            fresh = bands[q].tolist()
            gold = golden["mc"]["bands"][key][str(q)]
            assert len(fresh) == len(gold) == 17
            equal += sum(a == b for a, b in zip(fresh, gold, strict=True))
            total += len(gold)
    assert (equal, total) == (255, 255)
    counts = res.q3_counts()
    fresh_q3 = {v: {label: int(c) for label, c in counts[v].items() if c} for v in VENDORS}
    assert fresh_q3 == golden["mc"]["q3"]


def test_tornado(golden: dict[str, Any]) -> None:
    base = Params.baseline().scalars
    names = [p for p, *_ in TORNADO]
    cases: list[dict[str, float]] = [{}]
    cases += [{p: value} for p, lo, hi, _ in TORNADO for value in (lo, hi)]
    rows = [{p: case.get(p, base[p]) for p in names} for case in cases]
    # A None DemandGrowthLate (the baseline: "same as DemandGrowth") is NaN in an explicit design.
    samples = pd.DataFrame(rows, dtype=np.float64)
    assert len(samples) == 29
    res = run_experiment(Experiment(samples=samples), outputs=list(OUTS), workers=1)
    end = {k: res.frame(k)[2040.0].to_numpy() for k in OUTS}
    gold = golden["tornado"]
    assert [(r["param"], r["lo"], r["hi"], r["label"]) for r in gold] == [tuple(t) for t in TORNADO]
    fresh, expect = [], []
    for idx, row in enumerate(gold):
        for s, side in enumerate(("lo", "hi")):
            for k in OUTS:
                fresh.append(end[k][1 + 2 * idx + s] / end[k][0] - 1)  # phase7_runs.py:125-134
                expect.append(row[f"{side}_{k}"])
    assert len(fresh) == 140
    assert sum(a == b for a, b in zip(fresh, expect, strict=True)) == 140
