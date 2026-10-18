"""The ``phase9_highadoption`` goldens (``tests/data/goldens/phase9_highadoption/``, ``tools/generate_goldens_phase9.py
phase9_highadoption``), platform-aware: the phase 9 goldens' tests (``tests/test_golden_phase9.py``) for the slice 13
model.

As the phase 8 goldens (``tests/test_golden_phase8.py``, whose comparison helpers this reuses): bit for bit on the
platform in ``MANIFEST.json``, elsewhere at ``TOL`` with the near-zero rule. The final state is the full 43 families,
the six loop families included.

- The scalar base and AI-off runs (rows every quarter, final state, mins).
- The 14 scenarios on the scalar engine.
- The 300-run Monte Carlo over ``tornado_levers(model="phase9_highadoption")`` (the 14 tornado levers and the eight
  structural levers) through the experiment API (the batched engine) against the scalar goldens.
- The manifest names the current baseline file and every golden file by hash.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from aisim import Experiment, ExperimentResult, Params, run, run_experiment
from aisim.dims import VENDORS
from aisim.scenarios import STRUCTURAL_LEVERS
from aisim.state import BASELINE_FILES, LOOP_FAMILIES
from tests.helpers import port_dict
from tests.test_experiment_phase7 import compare_golden, golden_mode
from tests.test_golden_phase8 import KEYS_Q3, compare_rows, compare_run, json_round_trip, load
from tools.generate_goldens_phase8 import GOLDENS, KEEP, OUTS, QS, YEARS, annual, mc_draws, mc_levers, q3
from tools.hash_tree import sha256_file

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The Monte Carlo runs on the batched engine, so this needs numpy's kernels to match libm."""

MODEL = "phase9_highadoption"


def test_manifest_names_the_current_baseline_and_goldens() -> None:
    manifest = load(MODEL, "MANIFEST.json")
    assert manifest["model"] == MODEL
    assert manifest["baseline"]["sha256"] == sha256_file(Path(str(BASELINE_FILES[MODEL])))
    for name, digest in manifest["goldens"].items():
        assert sha256_file(GOLDENS / MODEL / name) == digest, name
    assert set(manifest["goldens"]) == {"base.json", "ai_off.json", "results.json"}


@pytest.mark.parametrize("ai_on", [True, False], ids=["base", "ai_off"])
def test_golden_base_and_ai_off(ai_on: bool) -> None:
    exact, _ = golden_mode(load(MODEL, "MANIFEST.json")["environment"])
    gold = load(MODEL, "base.json" if ai_on else "ai_off.json")
    assert set(LOOP_FAMILIES) <= set(gold["final_state"])
    fresh = json_round_trip(port_dict(run(Params.baseline(MODEL), ai_on=ai_on, record_every=0.25)))
    compare_run(fresh, gold, exact)


@pytest.mark.parametrize("ai_on", [True, False], ids=["base", "ai_off"])
def test_off_platform_path_on_the_goldens(ai_on: bool) -> None:
    """The off-platform comparison on the real goldens: a live run passes it on any platform."""
    gold = load(MODEL, "base.json" if ai_on else "ai_off.json")
    fresh = json_round_trip(port_dict(run(Params.baseline(MODEL), ai_on=ai_on, record_every=0.25)))
    zero = compare_run(fresh, gold, exact=False)
    assert "WorkCheckMax" in zero


def test_golden_scenarios() -> None:
    exact, _ = golden_mode(load(MODEL, "MANIFEST.json")["environment"])
    golden = load(MODEL, "results.json")["scenarios"]
    base = Params.baseline(MODEL)
    assert len(golden) == 14
    for name, gold in golden.items():
        res = run(base.with_overrides(**gold["over"]), record_every=1.0)
        ann = annual(res.rows)
        fresh = json_round_trip({yv: {k: ann[yv][k] for k in KEEP} for yv in ann})
        assert list(fresh) == list(gold["ann"])
        compare_rows(list(fresh.values()), list(gold["ann"].values()), exact)
        assert {v: q3(ann, v) for v in VENDORS} == gold["q3"], name
        assert [k for k, v in res.mins.items() if v < -1e-6] == gold["neg"], name


def test_golden_mc_levers_are_the_model_levers() -> None:
    """The 22 levers: the 14 tornado levers, then the eight structural levers of phase 9 (the same rows), in order."""
    mc = load(MODEL, "results.json")["mc"]
    assert mc["N"] == 300 and mc["years"] == list(YEARS)
    levers = [tuple(lever) for lever in mc["levers"]]
    assert levers == mc_levers(MODEL) and len(levers) == 22
    assert levers[14:] == [(name, lo, hi) for name, lo, hi, _ in STRUCTURAL_LEVERS[MODEL]]


@pytest.fixture(scope="module")
def api_mc() -> ExperimentResult:
    samples = pd.DataFrame(mc_draws(MODEL))
    return run_experiment(Experiment(model=MODEL, samples=samples), outputs=[*OUTS, *KEYS_Q3], workers=1)


def test_golden_mc(api_mc: ExperimentResult) -> None:
    """The batched Monte Carlo against the scalar goldens: bands per output and quantile, and the Q3 counts."""
    exact, _ = golden_mode(load(MODEL, "MANIFEST.json")["environment"])
    mc = load(MODEL, "results.json")["mc"]
    fresh: dict[str, dict[str, list[float]]] = {}
    for k in OUTS:
        b = api_mc.bands(k, ratio_to=2024)
        assert [float(y) for y in b.index] == [float(y) for y in YEARS]
        fresh[k] = {str(q): b[q].tolist() for q in QS}
    compare_golden(fresh, mc["bands"], exact)
    counts = api_mc.q3_counts()
    assert {v: {str(label): int(c) for label, c in counts[v].items() if c} for v in VENDORS} == mc["q3"]
