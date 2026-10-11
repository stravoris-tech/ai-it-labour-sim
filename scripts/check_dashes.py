"""Fail if any text file contains an em dash (U+2014) or an en dash (U+2013).

Scope: the files from ``git ls-files --cached --others --exclude-standard`` (tracked plus untracked, not ignored), or
the files given with ``--paths``. Files that are not valid UTF-8 are skipped as binary, and ``LICENSE-DOCS`` is skipped
as third-party legal text.

Each hit prints as ``path:line:col U+2014``. Exit 1 if there are hits, 0 if there are none, 2 on a usage error.
``--self-test`` is the positive control: it plants both characters in a temporary file and exits 0 only if the
detector finds exactly those two hits.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

DASHES = {"\u2014": "U+2014", "\u2013": "U+2013"}
SKIPPED_NAMES = frozenset({"LICENSE-DOCS"})


@dataclass(frozen=True)
class Hit:
    """One forbidden character: its file, 1-based line and column, and code point label."""

    path: str
    line: int
    col: int
    code: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}:{self.col} {self.code}"


def find_dashes(path: Path, display: str | None = None) -> list[Hit]:
    """Return every dash hit in ``path``; an empty list for clean, skipped or non-UTF-8 files."""
    if path.name in SKIPPED_NAMES:
        return []
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        return []
    label = display if display is not None else path.as_posix()
    hits: list[Hit] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for col_no, char in enumerate(line, start=1):
            code = DASHES.get(char)
            if code is not None:
                hits.append(Hit(label, line_no, col_no, code))
    return hits


def repo_files() -> list[str]:
    """List tracked files plus untracked files that are not ignored, relative to the current directory."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
    ).stdout
    return [p for p in out.decode("utf-8").split("\0") if p]


def check(paths: list[str]) -> list[Hit]:
    """Check each existing file in ``paths`` and return all hits."""
    hits: list[Hit] = []
    for p in paths:
        path = Path(p)
        if path.is_file():
            hits.extend(find_dashes(path, p))
    return hits


def self_test() -> int:
    """Plant one U+2014 and one U+2013 beside a clean line; exit 0 only if exactly those two hits are found."""
    with tempfile.TemporaryDirectory() as tmp:
        planted = Path(tmp) / "planted.txt"
        planted.write_text("clean line - hyphen only\nem \u2014 dash\nen \u2013 dash\n", encoding="utf-8")
        hits = find_dashes(planted, "planted.txt")
    expected = [Hit("planted.txt", 2, 4, "U+2014"), Hit("planted.txt", 3, 4, "U+2013")]
    for hit in hits:
        print(hit)
    if hits == expected:
        print("self-test: PASS (2 planted hits found)")
        return 0
    print(f"self-test: FAIL (expected {len(expected)} hits at known positions, found {len(hits)})")
    return 1


def main(argv: list[str]) -> int:
    """Parse arguments and run the self-test or the check."""
    parser = argparse.ArgumentParser(description="Fail on U+2014 or U+2013 in text files.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--paths", nargs="+", metavar="PATH", help="check only these files")
    group.add_argument("--self-test", action="store_true", help="run the positive control")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    paths: list[str] = args.paths if args.paths is not None else repo_files()
    hits = check(paths)
    for hit in hits:
        print(hit)
    print(f"dash check: {len(hits)} hit(s) in {len(paths)} file(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
