"""Shared helpers for comparing the port with the prototype and the goldens."""

from __future__ import annotations

import json
import math
import platform
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, NamedTuple, cast

import pytest

from aisim import Params, RunResult
from aisim.dims import LEVELS, REGIONS, UNITS
from aisim.state import State, copy_state, load_initial_state
from tools.reference_runner import InitEdit, apply_init_edits, iter_numeric_pairs, max_rel_diff, rel_diff
from tools.reference_runner import RunResult as ProtoResult

TOL = 1e-12

PHASE7 = pytest.StashKey[dict[str, str]]()
"""Parts of the Phase 7 acceptance summary line (``tests/conftest.py``), set by ``tests/test_experiment_phase7.py`` as
its checks pass: ``mode``, ``golden`` (checks passed), ``api`` (checks passed) and ``q3``."""

COVERAGE_CASES = Path(__file__).parent / "data" / "coverage_cases.json"


class CoverageCase(NamedTuple):
    """A guard-coverage case: parameter overrides and edits to the calibrated 2024 state."""

    name: str
    overrides: dict[str, float]
    init_edits: list[InitEdit]


def load_coverage_cases() -> list[CoverageCase]:
    """The four guard-coverage cases of ``data/coverage_cases.json`` (recon 03 B3), in file order.

    The reserved key ``__init__`` holds the state edits; ``__run__`` (run options) is not used by any case.
    """
    with COVERAGE_CASES.open(encoding="utf-8") as f:
        # Any: parsed JSON; each case maps parameter names to floats, plus the reserved keys.
        raw: dict[str, dict[str, Any]] = json.load(f)
    out = []
    for name, case in raw.items():
        if "__run__" in case:
            raise ValueError(f"{name}: __run__ is not supported")
        edits = case.get("__init__", [])
        overrides = {k: float(v) for k, v in case.items() if k != "__init__"}
        out.append(CoverageCase(name, overrides, edits))
    return out


def init_state(edits: list[InitEdit]) -> State:
    """A copy of the calibrated 2024 state with ``edits`` applied (``tools.reference_runner.apply_init_edits``)."""
    st = copy_state(load_initial_state())
    # Any: State is a TypedDict, which the edit walker treats as a plain nested dict of floats.
    apply_init_edits(cast(dict[str, Any], st), edits)
    return st


# Any: the parts are rows (a list), the final state (a nested dict) and mins (a dict), as in the goldens.
def port_dict(result: RunResult) -> dict[str, Any]:
    """Name the parts of a port run result as the goldens do."""
    return {"rows": result.rows, "final_state": dict(result.final_state), "mins": result.mins}


# Any: the parts are rows (a list), the final state (a nested dict) and mins (a dict), as in the goldens.
def proto_dict(result: ProtoResult) -> dict[str, Any]:
    """Name the parts of a prototype run result as the goldens do."""
    rows, final_state, mins = result
    return {"rows": rows, "final_state": final_state, "mins": mins}


def parity(port: RunResult, proto: ProtoResult) -> tuple[float, str]:
    """Return the largest relative difference over all row keys, the final state and ``mins``, and where it occurs.

    Raises ``ValueError`` if keys or lengths differ, and fails the test if any row's keys are in a different order.
    """
    a, b = port_dict(port), proto_dict(proto)
    for i, (ra, rb) in enumerate(zip(a["rows"], b["rows"], strict=True)):
        if list(ra) != list(rb):
            pytest.fail(f"row {i}: keys differ in name or order")
    diff, path = max_rel_diff(a, b)
    return diff, "/".join(map(str, path))


# Any: both are nested structures of dicts, lists and numbers, walked by iter_numeric_pairs.
def assert_close(fresh: Any, golden: Any, rel_tol: float = TOL, abs_tol: float = TOL) -> None:
    """Every numeric leaf is close; keys, lengths and non-numeric leaves are equal. Reports the worst miss."""
    misses = [
        (rel_diff(x, y), path, x, y)
        for path, x, y in iter_numeric_pairs(fresh, golden)
        if not math.isclose(x, y, rel_tol=rel_tol, abs_tol=abs_tol)
    ]
    if misses:
        diff, path, x, y = max(misses, key=lambda m: m[0])
        pytest.fail(
            f"{len(misses)} leaves differ; worst {'/'.join(map(str, path))}: "
            f"fresh {x!r} vs golden {y!r}, rel diff {diff:.3e}"
        )


def annual(rows: list[dict[str, float]]) -> dict[int, dict[str, float]]:
    """Rows at whole years, keyed by year (as ``phase7_runs.py`` ``annual``)."""
    return {round(r["year"]): r for r in rows if abs(r["year"] - round(r["year"])) < 1e-6}


def people(s: State) -> float:
    """Everyone the model tracks, as ``phase7_runs.py`` ``people``."""
    return (
        sum(m[u][lv] for m in (s["H"], s["O"]) for u in UNITS for lv in LEVELS)
        + sum(m[r][lv] for m in (s["R"], s["U"]) for r in REGIONS for lv in LEVELS)
        + sum(s["LeftField"].values())
        + sum(s["Retired"].values())
    )


PLATFORM_FIELDS = ("os", "machine", "python_implementation", "python_version")
"""What makes two platforms give the same doubles for the goldens: the OS (its C library), the CPU architecture and
the Python build."""


def platform_signature(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """``PLATFORM_FIELDS`` of a golden manifest's ``environment`` (``tools/generate_goldens.py``), or of this machine.

    The OS is the first token of the manifest's ``platform`` string (``Windows-11-10.0.26200-SP0`` gives
    ``Windows``), compared with ``platform.system()``; the OS build number is not part of the match.
    """
    if env is None:
        return {
            "os": platform.system(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        }
    return {
        "os": env["platform"].split("-")[0],
        "machine": env["machine"],
        "python_implementation": env["python_implementation"],
        "python_version": env["python_version"],
    }


def golden_platform_matches(env: Mapping[str, str], here: Mapping[str, str] | None = None) -> bool:
    """True if this machine (or ``here``, a ``platform_signature``) is the platform the goldens were generated on.

    Goldens are bit-equal only there; elsewhere they are compared at ``TOL``.
    """
    mine = platform_signature() if here is None else dict(here)
    return platform_signature(env) == {k: mine[k] for k in PLATFORM_FIELDS}


# ---- a second model for tests (slice 8 close-out) --------------------------------------------------------------------

SECOND_MODEL = "fixture"
"""The name the ``register_model`` fixture (``tests/conftest.py``) registers a test model under."""

PRICING_CHANGES: Mapping[str, float] = {
    "PassThrough": 0.75,
    "PriceHorizon": 7.0,
    "AnnuityShare": 0.3,
    "AnnuityAnchorW": 0.4,
}
"""Pricing changes that are neutral in 2024 (the held phase 8 design values): a model with only these has Phase 7's
2024 row."""

LEVEL_2024_CHANGE = "PriceMult_OIT"
"""The ``level_2024`` parameter the fixture model changes. It moves the 2024 C8 services-spend ratio (rule 5), so the
fixture also tests that C8 is judged against the selected model's 2024 step."""

FIXTURE_CHANGES: Mapping[str, float] = {**PRICING_CHANGES, LEVEL_2024_CHANGE: 1.07}
"""The fixture model: Phase 7 plus ``PRICING_CHANGES`` plus one ``level_2024`` change (``PriceMult_OIT`` 1.0154 to
1.07)."""

RegisterModel = Callable[[str, Mapping[str, float]], Params]
"""The ``register_model`` fixture: ``register(name, changes)`` registers a model and returns its baseline."""


PHASE8_MANIFEST = Path(__file__).resolve().parent / "data" / "goldens" / "phase8" / "MANIFEST.json"
"""The phase 8 golden manifest. The phase 8 fits (``tools/models/``) were made on the same machine, so its platform is
the one on which fit-derived values are bit-exact."""


def phase8_platform_matches() -> bool:
    """True on the platform the phase 8 goldens and fits were generated on."""
    env: dict[str, str] = json.loads(PHASE8_MANIFEST.read_text(encoding="utf-8"))["environment"]
    return golden_platform_matches(env)
