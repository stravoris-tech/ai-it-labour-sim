"""The port reproduces the stored goldens at rel and abs 1e-12, and ``SCENARIOS`` matches the stored scenarios."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aisim import SCENARIOS, Params, run
from tests.helpers import TOL, annual, assert_close, existing_families, port_dict
from tools.reference_runner import ROOT

GOLDENS = ROOT / "reference" / "goldens"


# Any: parsed JSON of any shape.
def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


RESULTS = load_json(GOLDENS / "phase7_results.json")


@pytest.mark.parametrize(("ai_on", "golden_file"), [(True, "base.json"), (False, "ai_off.json")])
def test_matches_run_golden(ai_on: bool, golden_file: str) -> None:
    golden = load_json(GOLDENS / golden_file)
    fresh = existing_families(port_dict(run(Params.baseline("phase7"), ai_on=ai_on, record_every=0.25)))
    assert len(fresh["rows"]) == len(golden["rows"])
    assert_close(fresh, golden, TOL, TOL)


@pytest.mark.parametrize("name", list(SCENARIOS))
def test_scenario_matches_results_golden(name: str) -> None:
    stored = RESULTS["scenarios"][name]["ann"]
    ann = annual(run(Params.baseline("phase7").with_overrides(**SCENARIOS[name]), record_every=1.0).rows)
    fresh = {year: {k: ann[int(year)][k] for k in keys} for year, keys in stored.items()}
    assert len(stored) == 17
    assert_close(fresh, stored, TOL, TOL)


def test_scenarios_equal_stored_overrides() -> None:
    assert list(SCENARIOS) == list(RESULTS["scenarios"])
    for name, scenario in RESULTS["scenarios"].items():
        expected = dict(scenario["over"])
        actual = dict(SCENARIOS[name])
        if "DemandGrowthLate" not in expected:
            actual.pop("DemandGrowthLate", None)
        assert actual == expected, name
        assert all(isinstance(v, float) for v in SCENARIOS[name].values()), name
