"""The dash check finds planted U+2014 characters and passes clean files."""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_dashes.py"


def run_check(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8", check=False
    )


def test_self_test_passes() -> None:
    assert run_check("--self-test").returncode == 0


def test_planted_dash_is_reported(tmp_path: Path) -> None:
    planted = tmp_path / "planted.md"
    planted.write_text("fine\nnot \u2014 fine\n", encoding="utf-8")
    proc = run_check("--paths", str(planted))
    assert proc.returncode == 1
    assert f"{planted}:2:5 U+2014" in proc.stdout


def test_clean_file_passes(tmp_path: Path) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("hyphens - only\n", encoding="utf-8")
    assert run_check("--paths", str(clean)).returncode == 0
