"""The Q01 example runs end to end (reduced to 50 runs per scenario) and writes a report under 1 MB."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "examples" / "q01_contract_mix.py"


def test_q01_example_end_to_end(tmp_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(EXAMPLE), "--n", "50", "--out", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    report = tmp_path / "report.html"
    assert report.is_file() and 0 < report.stat().st_size < 2**20
    page = report.read_text(encoding="utf-8")
    assert page.count("<svg") == 4 and "git_commit" in page and "50 per scenario x 4 = 200" in page
