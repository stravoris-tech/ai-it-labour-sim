"""The source citations in ``domains.csv`` match the text stored for them (``tools/cites.py``, slice 7).

The gate runs ``--check``'s logic on the repo; a temporary copy shows that the check catches a moved line, that
``--fix`` restores it, and that an ambiguous match makes ``--fix`` exit 1 without writing.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tools.cites import DOMAINS, FIX_COMMAND, PACKAGE, ROOT, SIDECAR, check, cites_of, main, read_rows


def test_cites_match_their_stored_text() -> None:
    problems, rules = check(ROOT)
    assert not problems, f"{len(problems)} stale cite(s), first: {problems[0]}. Re-anchor with: {FIX_COMMAND}"
    assert "unresolved" not in rules and sum(rules.values()) > 1000


@pytest.fixture
def copy(tmp_path: Path) -> Path:
    """The package sources, ``domains.csv`` and the sidecar, at their repo paths under ``tmp_path``."""
    shutil.copytree(ROOT / PACKAGE, tmp_path / PACKAGE, ignore=shutil.ignore_patterns("__pycache__"))
    (tmp_path / SIDECAR).parent.mkdir(parents=True)
    shutil.copy2(ROOT / SIDECAR, tmp_path / SIDECAR)
    return tmp_path


def first_evidence_cite(root: Path) -> tuple[str, Path, int]:
    _, rows = read_rows(root)
    c = next(c for c in cites_of(root, rows) if c.field == "evidence" and not c.is_range)
    assert c.path is not None
    return c.row, c.path, c.first


def insert_line(path: Path, before: int, text: str) -> None:
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    lines.insert(before - 1, text + "\n")
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))


def test_inserted_line_fails_check_and_fix_restores(copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    row, path, line = first_evidence_cite(copy)
    insert_line(copy / path, line, "# a line inserted above a cited line")
    problems, _ = check(copy)
    assert any(p.cite.row == row and p.cite.first == line for p in problems)
    assert main(["--check", "--root", str(copy)]) == 1
    assert FIX_COMMAND in capsys.readouterr().out
    assert main(["--fix", "--root", str(copy)]) == 0
    assert check(copy)[0] == []
    _, rows = read_rows(copy)
    moved = next(c for c in cites_of(copy, rows) if c.row == row and c.field == "evidence")
    assert moved.first == line + 1
    before = (copy / DOMAINS).read_bytes(), (copy / SIDECAR).read_bytes()
    assert main(["--fix", "--root", str(copy)]) == 0
    assert ((copy / DOMAINS).read_bytes(), (copy / SIDECAR).read_bytes()) == before


def test_ambiguous_match_makes_fix_exit_1_without_writing(copy: Path, capsys: pytest.CaptureFixture[str]) -> None:
    row, path, line = first_evidence_cite(copy)
    text = (copy / path).read_text(encoding="utf-8").splitlines()[line - 1]
    insert_line(copy / path, 1, text)
    before = (copy / DOMAINS).read_bytes(), (copy / SIDECAR).read_bytes()
    assert main(["--fix", "--root", str(copy)]) == 1
    out = capsys.readouterr().out
    assert "ambiguous" in out and row in out and "nothing written" in out
    assert ((copy / DOMAINS).read_bytes(), (copy / SIDECAR).read_bytes()) == before
