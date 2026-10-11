"""Shared fixtures: the numerics guard behind batch-scalar parity (slice 03b).

Batch-scalar parity at 1e-12 assumes numpy's float64 ``np.power`` and ``np.log`` return libm's doubles. On x86-64
CPUs with AVX-512 they do not unless ``NPY_DISABLE_CPU_FEATURES`` turns the AVX-512 targets off. Tests that need the
parity request ``numpy_kernels_match_libm``: once per session it compares the engine's forms with Python's, and if they
differ those tests fail at once with one message naming the cause and the fix, instead of a parity diff.
"""

from __future__ import annotations

import pytest

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
    """Report the guard's verdict, with n and the CPU, whenever it ran."""
    line = terminalreporter.config.stash.get(GUARD_LINE, None)
    if line is not None:
        terminalreporter.write_line(line)
