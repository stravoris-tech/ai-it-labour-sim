"""Run the repository gate: lint, format check, type check, tests and the dash check.

Every step runs as ``sys.executable -m ...`` or ``sys.executable <script>``, and the gate continues after a failure so
the report is complete. It prints a table of steps with their exit codes and a test count line, and exits 0 only if
every step exited 0.

Usage: ``uv run python scripts/gate.py``
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JUNIT = ROOT / "temp" / "gate" / "junit.xml"
DASHES = str(ROOT / "scripts" / "check_dashes.py")

STEPS: list[tuple[str, list[str]]] = [
    ("ruff check", [sys.executable, "-m", "ruff", "check", "."]),
    ("ruff format --check", [sys.executable, "-m", "ruff", "format", "--check", "."]),
    ("mypy", [sys.executable, "-m", "mypy"]),
    ("pytest", [sys.executable, "-m", "pytest", f"--junitxml={JUNIT}"]),
    ("dash check --self-test", [sys.executable, DASHES, "--self-test"]),
    ("dash check", [sys.executable, DASHES]),
]


@dataclass(frozen=True)
class TestCounts:
    """Totals parsed from a JUnit XML report."""

    tests: int
    failures: int
    errors: int
    skipped: int


def parse_junit(path: Path) -> TestCounts | None:
    """Sum the test counts over every ``testsuite`` in a JUnit XML file, or return None if it cannot be read."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")

    def total(attr: str) -> int:
        return sum(int(s.get(attr, "0")) for s in suites)

    return TestCounts(total("tests"), total("failures"), total("errors"), total("skipped"))


def main() -> int:
    """Run every step, print the report and return 0 only if all steps passed."""
    JUNIT.parent.mkdir(parents=True, exist_ok=True)
    JUNIT.unlink(missing_ok=True)
    results: list[tuple[str, int]] = []
    for name, cmd in STEPS:
        print(f"\n=== {name} ===", flush=True)
        code = subprocess.run(cmd, cwd=ROOT).returncode
        results.append((name, code))

    width = max(len(name) for name, _ in results)
    print("\n" + "=" * (width + 18))
    print(f"{'step':<{width}}  exit  verdict")
    for name, code in results:
        print(f"{name:<{width}}  {code:>4}  {'PASS' if code == 0 else 'FAIL'}")
    counts = parse_junit(JUNIT)
    if counts is None:
        print("tests: no JUnit report found")
    else:
        passed = counts.tests - counts.failures - counts.errors - counts.skipped
        print(
            f"tests: {counts.tests} run, {passed} passed, {counts.failures} failed, "
            f"{counts.errors} errors, {counts.skipped} skipped"
        )
    ok = all(code == 0 for _, code in results)
    print(f"gate: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
