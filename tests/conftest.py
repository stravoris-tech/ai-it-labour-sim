"""Shared fixtures: the numerics guard behind batch-scalar parity (slice 03b).

Batch-scalar parity at 1e-12 assumes numpy's float64 ``np.power`` and ``np.log`` return libm's doubles. On x86-64
CPUs with AVX-512 they do not unless ``NPY_DISABLE_CPU_FEATURES`` turns the AVX-512 targets off. Tests that need the
parity request ``numpy_kernels_match_libm``: once per session it compares the engine's forms with Python's, and if they
differ those tests fail at once with one message naming the cause and the fix, instead of a parity diff.

The terminal summary also prints the Phase 7 acceptance line (``tests/test_experiment_phase7.py``): which golden mode
ran (bit-exact on the manifest platform, else the golden tolerance) and whether the API and Q3 checks passed.

``register_model`` registers a second model for one test (slice 8 close-out): the shipped tree has one model,
``phase7``, and the model-selector tests need another.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from aisim import Params, state
from aisim.params import EXTENSION_DEFAULTS
from aisim.state import baseline_data
from tests.helpers import PHASE7, RegisterModel
from tools.numerics_probe import guard, guard_line, guard_message

GUARD_LINE = pytest.StashKey[str]()


@pytest.fixture(scope="session")
def numpy_kernels_match_libm(request: pytest.FixtureRequest) -> None:
    """Fail (never skip) if numpy's kernels differ from libm in any form the batched engine uses."""
    results = guard()
    request.config.stash[GUARD_LINE] = guard_line(results)
    if any(r.mismatches for r in results):
        pytest.fail(guard_message(results), pytrace=False)


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    """Report the guard's verdict, with n and the CPU, whenever it ran, and the Phase 7 acceptance mode."""
    line = terminalreporter.config.stash.get(GUARD_LINE, None)
    if line is not None:
        terminalreporter.write_line(line)
    parts = terminalreporter.config.stash.get(PHASE7, None)
    if parts:
        mode = parts.get("mode", "golden checks not run")
        if parts.get("golden") != "2":
            mode = f"golden checks not all passed ({mode})"
        api = "API checks bit-equal" if parts.get("api") == "3" else "API checks not all passed"
        q3 = "Q3 counts equal" if parts.get("q3") == "equal" else "Q3 counts not confirmed"
        terminalreporter.write_line(f"phase7 goldens: {mode}; {api}; {q3}")


@pytest.fixture
def register_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[RegisterModel]:
    """A factory that registers a second model for one test (``tests.helpers.RegisterModel``).

    ``register(name, changes)`` writes ``tmp_path/baseline_<name>.json``, which is Phase 7's baseline file with every
    extension at its ``EXTENSION_DEFAULTS`` value and ``changes`` applied (same key order, tables and ``init``). It
    adds the file to the model registry, ``aisim.state.BASELINE_FILES``, which every check reads at call time, and
    returns ``Params.baseline(name)``. ``monkeypatch`` removes the entry after the test. The C8 baseline cache
    (keyed by model name) is cleared before and after. The model exists in this process only: use ``workers=1``.
    """
    from aisim.experiment import validate

    def register(name: str, changes: Mapping[str, float]) -> Params:
        data = baseline_data("phase7")
        params = {**data["params"], **EXTENSION_DEFAULTS}
        unknown = sorted(set(changes) - set(params))
        if unknown:
            raise KeyError(f"unknown parameter(s): {unknown}")
        data["params"] = {**params, **changes}
        path = tmp_path / f"baseline_{name}.json"
        path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        monkeypatch.setitem(state.BASELINE_FILES, name, path)
        validate._c8_baseline.cache_clear()
        return Params.baseline(name)

    validate._c8_baseline.cache_clear()
    yield register
    validate._c8_baseline.cache_clear()
