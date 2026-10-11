"""The frozen prototype is unchanged, and fresh runs of it reproduce the goldens and the recon's headline values."""

import json
import math
from pathlib import Path
from typing import Any

import pytest

from tools.hash_tree import hash_tree
from tools.reference_runner import PROTOTYPE, ROOT, RunResult, iter_numeric_pairs, rel_diff, run_base, run_full_suite

# Hard-coded so that a regenerated manifest cannot hide a change to the prototype.
PROTOTYPE_TREE_SHA256 = "c1f5173e211a599d7a9a040b6adfc61cdc6bb93074bb2cffcdf7651f4442bf90"

GOLDENS = ROOT / "reference" / "goldens"
REL_TOL = 1e-9
ABS_TOL = 1e-9


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def as_golden(result: RunResult) -> dict[str, Any]:
    rows, final_state, mins = result
    return {"rows": rows, "final_state": final_state, "mins": mins}


def assert_matches_golden(fresh: Any, golden: Any) -> None:
    """Every numeric leaf is close; keys, lengths and non-numeric leaves are equal. Reports the worst miss."""
    misses = [
        (rel_diff(x, y), path, x, y)
        for path, x, y in iter_numeric_pairs(fresh, golden)
        if not math.isclose(x, y, rel_tol=REL_TOL, abs_tol=ABS_TOL)
    ]
    if misses:
        diff, path, x, y = max(misses, key=lambda m: m[0])
        year = fresh["rows"][path[1]]["year"] if path[:1] == ("rows",) and len(path) > 1 else None
        pytest.fail(
            f"{len(misses)} leaves differ; worst {'/'.join(map(str, path))} (year {year}): "
            f"fresh {x!r} vs golden {y!r}, rel diff {diff:.3e}"
        )


def annual(rows: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {round(r["year"]): r for r in rows if abs(r["year"] - round(r["year"])) < 1e-6}


def test_reference_tree_unchanged() -> None:
    manifest = load_json(GOLDENS / "MANIFEST.json")
    tree = hash_tree(PROTOTYPE).tree
    assert tree == manifest["prototype"]["tree_sha256"]
    assert tree == PROTOTYPE_TREE_SHA256


def compare_run_with_golden(ai_on: bool, golden_file: str) -> None:
    golden = load_json(GOLDENS / golden_file)
    fresh = as_golden(run_base(ai_on=ai_on, record_every=0.25))
    assert fresh.keys() == golden.keys()
    assert len(fresh["rows"]) == len(golden["rows"])
    assert_matches_golden(fresh, golden)


def test_base_matches_golden() -> None:
    compare_run_with_golden(True, "base.json")


def test_ai_off_matches_golden() -> None:
    compare_run_with_golden(False, "ai_off.json")


def test_headline_values() -> None:
    rows, _, _ = run_base()
    ann = annual(rows)
    y24, y40 = ann[2024], ann[2040]
    assert y24["HeadTotal"] == pytest.approx(82653.569, abs=1e-3)
    assert y40["HeadTotal"] / y24["HeadTotal"] == pytest.approx(0.962530, abs=5e-6)
    expected = {
        "Q1_ConsOnshore": 0.911401,
        "Q1_ConsIndia": 3.097270,
        "Q1_VendOnshore": 0.785606,
        "Q1_VendIndia": 0.489738,
    }
    for key, ratio in expected.items():
        assert y40[key] / y24[key] == pytest.approx(ratio, abs=5e-6), key


def test_t1_growth_path() -> None:
    rows, _, _ = run_base(ai_on=False, record_every=1.0)
    ann = annual(rows)
    h2024 = ann[2024]["HeadTotal"]
    max_dev = max(abs(r["HeadTotal"] / h2024 / r["G"] - 1) for r in ann.values())
    assert max_dev == pytest.approx(0.0117959, abs=1e-6)
    assert max_dev < 0.012


@pytest.mark.slow
def test_full_suite_matches_golden(tmp_path: Path) -> None:
    fresh = load_json(run_full_suite(tmp_path))
    golden = load_json(GOLDENS / "phase7_results.json")
    assert_matches_golden(fresh, golden)
