"""The phase 8 goldens (``tests/data/goldens/<model>/``, ``tools/generate_goldens_phase8.py``), platform-aware.

There is no prototype for phase 8: the goldens are the scalar engine's own output, generated on the platform in each
model's ``MANIFEST.json``. There fresh runs must match them bit for bit; elsewhere they are compared at the golden
tolerance (``tests/helpers.py`` ``TOL``), as ``test_experiment_phase7.py`` does, with one rule for keys that are zero
up to round-off: a key whose golden values are all within ``NEAR_ZERO`` of 0 at every step (for example ``AICost_<v>``
with AI off, ``AICostPerUnit x VendDel x (1 - 1 / Pe)`` with ``Pe`` 1 up to round-off) is compared with that absolute
tolerance, and its live values must also stay within ``NEAR_ZERO`` of 0. A relative tolerance cannot work against
zero. The Phase 7 golden comparison is unchanged. The Q3 counts must be equal on every platform.

- Both models: the scalar base and AI-off runs (rows every quarter, final state, mins).
- ``phase8``: the 14 scenarios on the scalar engine, and the 300-run Monte Carlo through the experiment API (the
  batched engine) against the scalar goldens.
- The manifests: they name the model's current baseline file, by hash, and every golden file's hash.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from aisim import Experiment, ExperimentResult, Params, run, run_experiment
from aisim.dims import VENDORS
from aisim.state import BASELINE_FILES
from tests.helpers import TOL, assert_close, port_dict
from tests.test_experiment_phase7 import compare_golden, golden_mode
from tools.generate_goldens_phase8 import (
    GOLDENS,
    KEEP,
    MC_MODEL,
    MODELS,
    OUTS,
    QS,
    YEARS,
    annual,
    mc_draws,
    mc_levers,
    q3,
)
from tools.hash_tree import sha256_file

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""The Monte Carlo runs on the batched engine, so this needs numpy's kernels to match libm."""


NEAR_ZERO = 1e-6
"""Off the manifest platform: the absolute tolerance, and the bound, for keys that are zero up to round-off."""

Rows = list[dict[str, float]]


def near_zero_keys(rows: Rows) -> list[str]:
    """The keys whose golden values are all within ``NEAR_ZERO`` of 0 at every step."""
    return [k for k in rows[0] if all(abs(r[k]) <= NEAR_ZERO for r in rows)]


def compare_rows(fresh: Rows, gold: Rows, exact: bool) -> list[str]:
    """Bit for bit when ``exact``. Otherwise every leaf at ``TOL``, except the near-zero keys: their live values must
    stay within ``NEAR_ZERO`` of 0 and of the golden values. Returns the near-zero keys."""
    if exact:
        assert fresh == gold
        return near_zero_keys(gold)
    assert len(fresh) == len(gold) and [list(r) for r in fresh] == [list(r) for r in gold]
    zero = near_zero_keys(gold)
    for k in zero:
        for i, (a, b) in enumerate(zip(fresh, gold, strict=True)):
            assert abs(a[k]) <= NEAR_ZERO and abs(a[k] - b[k]) <= NEAR_ZERO, (k, i, a[k], b[k])
    rest = [{k: v for k, v in r.items() if k not in zero} for r in fresh]
    assert_close(rest, [{k: v for k, v in r.items() if k not in zero} for r in gold], TOL, TOL)
    return zero


def compare_run(fresh: dict[str, Any], gold: dict[str, Any], exact: bool) -> list[str]:
    """A golden run (rows, final state, mins): the rows by ``compare_rows``, the rest by ``compare_golden``. ``Any``:
    parsed JSON."""
    zero = compare_rows(fresh["rows"], gold["rows"], exact)
    compare_golden(
        {k: v for k, v in fresh.items() if k != "rows"}, {k: v for k, v in gold.items() if k != "rows"}, exact
    )
    return zero


def load(model: str, name: str) -> Any:
    """A golden file. ``Any``: parsed JSON."""
    with (GOLDENS / model / name).open(encoding="utf-8") as f:
        return json.load(f)


def json_round_trip(obj: Any) -> Any:
    """``obj`` as the goldens store it (string keys). ``Any``: JSON-ready values."""
    return json.loads(json.dumps(obj))


@pytest.fixture(scope="module", params=MODELS)
def model(request: pytest.FixtureRequest) -> str:
    name: str = request.param
    return name


def test_manifest_names_the_current_baseline_and_goldens(model: str) -> None:
    """A changed baseline file or golden file makes the goldens stale: regenerate them (a slice prompt says when)."""
    manifest = load(model, "MANIFEST.json")
    assert manifest["model"] == model
    assert manifest["baseline"]["sha256"] == sha256_file(Path(str(BASELINE_FILES[model])))
    for name, digest in manifest["goldens"].items():
        assert sha256_file(GOLDENS / model / name) == digest, name
    expect = {"base.json", "ai_off.json", *(["results.json"] if model == MC_MODEL else [])}
    assert set(manifest["goldens"]) == expect


@pytest.mark.parametrize("ai_on", [True, False], ids=["base", "ai_off"])
def test_golden_base_and_ai_off(model: str, ai_on: bool) -> None:
    exact, _ = golden_mode(load(model, "MANIFEST.json")["environment"])
    fresh = json_round_trip(port_dict(run(Params.baseline(model), ai_on=ai_on, record_every=0.25)))
    compare_run(fresh, load(model, "base.json" if ai_on else "ai_off.json"), exact)


def test_golden_scenarios() -> None:
    exact, _ = golden_mode(load(MC_MODEL, "MANIFEST.json")["environment"])
    golden = load(MC_MODEL, "results.json")["scenarios"]
    base = Params.baseline(MC_MODEL)
    assert len(golden) == 14
    for name, gold in golden.items():
        res = run(base.with_overrides(**gold["over"]), record_every=1.0)
        ann = annual(res.rows)
        fresh = json_round_trip({yv: {k: ann[yv][k] for k in KEEP} for yv in ann})
        assert list(fresh) == list(gold["ann"])
        compare_rows(list(fresh.values()), list(gold["ann"].values()), exact)
        assert {v: q3(ann, v) for v in VENDORS} == gold["q3"], name
        assert [k for k, v in res.mins.items() if v < -1e-6] == gold["neg"], name


@pytest.fixture(scope="module")
def api_mc() -> ExperimentResult:
    samples = pd.DataFrame(mc_draws(MC_MODEL))
    return run_experiment(Experiment(model=MC_MODEL, samples=samples), outputs=[*OUTS, *KEYS_Q3], workers=1)


KEYS_Q3 = tuple(f"{p}_{v}" for v in VENDORS for p in ("Vi", "Head", "Revenue"))


def test_golden_mc_levers_are_the_model_tornado_levers() -> None:
    mc = load(MC_MODEL, "results.json")["mc"]
    assert mc["N"] == 300 and mc["years"] == list(YEARS)
    assert [tuple(lever) for lever in mc["levers"]] == mc_levers(MC_MODEL)


def test_golden_mc(api_mc: ExperimentResult) -> None:
    """The batched Monte Carlo against the scalar goldens: bands per output and quantile, and the Q3 counts."""
    exact, _ = golden_mode(load(MC_MODEL, "MANIFEST.json")["environment"])
    mc = load(MC_MODEL, "results.json")["mc"]
    fresh: dict[str, dict[str, list[float]]] = {}
    for k in OUTS:
        b = api_mc.bands(k, ratio_to=2024)
        assert [float(y) for y in b.index] == [float(y) for y in YEARS]
        fresh[k] = {str(q): b[q].tolist() for q in QS}
    compare_golden(fresh, mc["bands"], exact)
    counts = api_mc.q3_counts()
    assert {v: {str(label): int(c) for label, c in counts[v].items() if c} for v in VENDORS} == mc["q3"]


def test_near_zero_rule_controls() -> None:
    """Positive controls for the off-platform comparison: a near-zero key that drifts to a real value fails, a
    near-zero key that moves by round-off passes, and an ordinary key that moves beyond ``TOL`` fails."""
    gold = [{"z": 0.0, "x": 1.0}, {"z": 1.8e-7, "x": 2.0}]
    assert near_zero_keys(gold) == ["z"]
    assert compare_rows([{"z": 2.2e-8, "x": 1.0}, {"z": 0.0, "x": 2.0}], gold, exact=False) == ["z"]
    with pytest.raises(AssertionError):
        compare_rows([{"z": 2e-6, "x": 1.0}, {"z": 0.0, "x": 2.0}], gold, exact=False)
    with pytest.raises(pytest.fail.Exception):
        compare_rows([{"z": 0.0, "x": 1.0 + 1e-9}, {"z": 0.0, "x": 2.0}], gold, exact=False)
    with pytest.raises(AssertionError):
        compare_rows([{"z": 2.2e-8, "x": 1.0}, {"z": 1.8e-7, "x": 2.0}], gold, exact=True)


@pytest.mark.parametrize("ai_on", [True, False], ids=["base", "ai_off"])
def test_off_platform_path_on_the_goldens(model: str, ai_on: bool) -> None:
    """The off-platform comparison on the real goldens: a live run passes it, and so does the AI-off golden with the
    value CI run 38983175912 (Linux x86-64) produced in place of the stored 0.0 (``AICost_GSI``, row 60)."""
    gold = load(model, "base.json" if ai_on else "ai_off.json")
    fresh = json_round_trip(port_dict(run(Params.baseline(model), ai_on=ai_on, record_every=0.25)))
    zero = compare_run(fresh, gold, exact=False)
    assert "WorkCheckMax" in zero
    if not ai_on:
        assert {"AICost_OIT", "AICost_GSI", "AICost_BQ"} <= set(zero)
        planted = json_round_trip(fresh)
        planted["rows"][60]["AICost_GSI"] = 2.213873183723297e-08
        compare_run(planted, gold, exact=False)
