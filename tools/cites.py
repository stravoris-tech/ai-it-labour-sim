"""Keep the source citations in ``src/aisim/data/domains.csv`` pointing at the lines they were written for.

The ``evidence`` and ``notes`` fields cite source lines as ``src/aisim/scalar/consumer.py:187`` (evidence, separated by
``;``) or by bare file name, ``consumer.py:187`` (notes); a range is ``file.py:12-14``. Edits to the source move lines,
so a cite can silently point at different text. The sidecar ``tests/data/domains_cites.json`` stores, per row id, field
and cite (as written), the stripped text of the cited line; for a range, the text of its first and last lines.

Usage: ``uv run python tools/cites.py --check | --fix | --apt``

- ``--check`` exits 1 if any cite's file or line is missing, has no stored text, or its text differs from the stored
  text. It prints how many cites each resolution rule settled. ``tests/test_cites.py`` runs the same check in the gate.
- ``--fix`` re-anchors each failing cite only by a unique exact match of its stored text in the same file; a range
  shifts by its start line's offset, and its last line must then match too. It never guesses: if any cite is
  ambiguous (the text appears on more than one line) or missing, it lists them, writes nothing and exits 1.
  Otherwise it rewrites ``domains.csv`` (``newline=""``; only the cite numbers change) and refreshes the sidecar from
  the current lines, which also records the text of a newly written cite. A second run changes nothing.
- ``--apt`` reports, for each cite, whether the cited lines (plus or minus 2) mention the row's parameter name or the
  engine name it reads: the name itself, the table name of ``Name[KEY]`` rows, or the quoted prefix (``"W_"``) of a
  level or dimension row such as ``W_J``, which the engine reads as ``pr["W_" + l]``. A report only: exit 0.

**Resolving a file name** (the rule the slice 7 recon used to classify the cites): a cite whose folder is written
(``scalar/``, ``batch/``, ``experiment/`` or ``charts/``, with or without ``src/aisim/``) is that file. A bare name is
looked up in ``src/aisim/scalar/``, then ``src/aisim/``, then ``src/aisim/experiment/``, then ``src/aisim/batch/``, and
the first folder that has it wins: the scalar engine is the reference, so a name in both ``scalar/`` and ``batch/``
(such as ``labour_market.py``) is the scalar file. A bare name in none of the four folders is unresolved, and
``--check`` and ``--fix`` report it as an error rather than pick a file.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
DOMAINS: Final = Path("src/aisim/data/domains.csv")
SIDECAR: Final = Path("tests/data/domains_cites.json")
PACKAGE: Final = Path("src/aisim")
FIELDS: Final = ("evidence", "notes")
FIX_COMMAND: Final = "uv run python tools/cites.py --fix"
CITE: Final = re.compile(r"(?:src/aisim/)?((?:scalar|batch|experiment|charts)/)?([a-z_0-9]+\.py):(\d+)(?:-(\d+))?")
BARE_ORDER: Final = ("scalar/", "", "experiment/", "batch/")
"""The folders a bare file name is looked up in, first match wins."""
APT_WINDOW: Final = 2

Sidecar = dict[str, dict[str, dict[str, list[str]]]]
"""Row id to field to cite (as written) to its stored text: one line, or a range's first and last lines."""


@dataclass(frozen=True)
class Cite:
    """One cite in one field of one row."""

    row: str
    field: str
    text: str
    span: tuple[int, int]
    path: Path | None
    rule: str
    first: int
    last: int

    @property
    def is_range(self) -> bool:
        return self.last != self.first


@dataclass(frozen=True)
class Problem:
    """A cite that fails the check, or that ``--fix`` cannot re-anchor."""

    cite: Cite
    reason: str

    def __str__(self) -> str:
        return f"{self.cite.row} {self.cite.field}: {self.cite.text}: {self.reason}"


def resolve(root: Path, folder: str | None, name: str) -> tuple[Path | None, str]:
    """The cited file (relative to ``root``) and the rule that settled it; ``(None, "unresolved")`` if none."""
    if folder:
        path = PACKAGE / folder / name
        return (path, f"folder written: {folder}") if (root / path).is_file() else (None, "unresolved")
    for candidate in BARE_ORDER:
        path = PACKAGE / candidate / name
        if (root / path).is_file():
            return path, f"bare: src/aisim/{candidate}"
    return None, "unresolved"


def read_rows(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    with (root / DOMAINS).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def cites_of(root: Path, rows: Sequence[dict[str, str]]) -> list[Cite]:
    out = []
    for r in rows:
        for field in FIELDS:
            for m in CITE.finditer(r[field]):
                path, rule = resolve(root, m.group(1), m.group(2))
                first = int(m.group(3))
                last = int(m.group(4)) if m.group(4) else first
                out.append(Cite(r["name"], field, m.group(0), m.span(), path, rule, first, last))
    return out


class Files:
    """Stripped source lines, read once per file."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lines: dict[Path, list[str]] = {}

    def lines(self, path: Path) -> list[str]:
        if path not in self._lines:
            text = (self.root / path).read_text(encoding="utf-8")
            self._lines[path] = [line.strip() for line in text.splitlines()]
        return self._lines[path]

    def text(self, cite: Cite) -> list[str] | None:
        """The cite's current text (one line, or first and last), or None if its file or a line is missing."""
        if cite.path is None:
            return None
        lines = self.lines(cite.path)
        if not 1 <= cite.first <= cite.last <= len(lines):
            return None
        return [lines[cite.first - 1], lines[cite.last - 1]] if cite.is_range else [lines[cite.first - 1]]


def load_sidecar(root: Path) -> Sidecar:
    path = root / SIDECAR
    if not path.is_file():
        return {}
    data: Sidecar = json.loads(path.read_text(encoding="utf-8"))
    return data


def stored(sidecar: Sidecar, cite: Cite) -> list[str] | None:
    return sidecar.get(cite.row, {}).get(cite.field, {}).get(cite.text)


def problem_of(files: Files, sidecar: Sidecar, cite: Cite) -> Problem | None:
    if cite.path is None:
        return Problem(cite, "file not found (no folder in the resolution rule has it)")
    now = files.text(cite)
    if now is None:
        return Problem(cite, f"line missing ({len(files.lines(cite.path))} lines in {cite.path.as_posix()})")
    want = stored(sidecar, cite)
    if want is None:
        return Problem(cite, "no stored text")
    if now != want:
        return Problem(cite, f"text differs: now {now!r}, stored {want!r}")
    return None


def check(root: Path) -> tuple[list[Problem], Counter[str]]:
    """Every failing cite, and how many cites each resolution rule settled."""
    _, rows = read_rows(root)
    cites = cites_of(root, rows)
    files, sidecar = Files(root), load_sidecar(root)
    problems = [p for c in cites if (p := problem_of(files, sidecar, c)) is not None]
    return problems, Counter(c.rule for c in cites)


def sidecar_of(root: Path, rows: Sequence[dict[str, str]]) -> Sidecar:
    """The sidecar for ``rows`` from the current source lines (every cite must resolve)."""
    files = Files(root)
    out: Sidecar = {}
    for c in cites_of(root, rows):
        now = files.text(c)
        if now is None:
            raise ValueError(f"{c.row} {c.field}: {c.text} does not resolve")
        out.setdefault(c.row, {}).setdefault(c.field, {})[c.text] = now
    return out


def dump_sidecar(sidecar: Sidecar) -> str:
    return json.dumps(sidecar, indent=1, ensure_ascii=True) + "\n"


def dump_rows(fieldnames: Sequence[str], rows: Sequence[dict[str, str]]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


@dataclass(frozen=True)
class FixResult:
    moved: list[tuple[Cite, str]]
    """Each re-anchored cite and its new text."""
    unresolved: list[Problem]
    written: bool


def reanchor(files: Files, cite: Cite, want: list[str]) -> str | Problem:
    """The cite's new text, found by a unique exact match of its stored first line in the same file."""
    assert cite.path is not None
    lines = files.lines(cite.path)
    hits = [i + 1 for i, line in enumerate(lines) if line == want[0]]
    if not hits:
        return Problem(cite, "stored text not found in the file")
    if len(hits) > 1:
        return Problem(cite, f"ambiguous: stored text on {len(hits)} lines {hits}")
    first = hits[0]
    last = first + (cite.last - cite.first)
    if cite.is_range and (last > len(lines) or lines[last - 1] != want[1]):
        return Problem(cite, f"range end differs after the shift to {first}-{last}")
    head = cite.text[: cite.text.rindex(":") + 1]
    return head + (f"{first}-{last}" if cite.is_range else f"{first}")


def fix(root: Path) -> FixResult:
    """Re-anchor every failing cite, or write nothing if any cannot be re-anchored uniquely."""
    fieldnames, rows = read_rows(root)
    files, sidecar = Files(root), load_sidecar(root)
    moved: list[tuple[Cite, str]] = []
    unresolved: list[Problem] = []
    for c in cites_of(root, rows):
        p = problem_of(files, sidecar, c)
        if p is None:
            continue
        want = stored(sidecar, c)
        if c.path is None or want is None:
            if c.path is not None and files.text(c) is not None:
                continue  # a new cite: the sidecar refresh records its text
            unresolved.append(p if want is not None else Problem(c, f"{p.reason}, and no stored text to match"))
            continue
        new = reanchor(files, c, want)
        if isinstance(new, Problem):
            unresolved.append(new)
        else:
            moved.append((c, new))
    if unresolved:
        return FixResult(moved, unresolved, False)
    by_field: dict[tuple[str, str], list[tuple[Cite, str]]] = {}
    for c, new in moved:
        by_field.setdefault((c.row, c.field), []).append((c, new))
    for r in rows:
        for field in FIELDS:
            for c, new in sorted(by_field.get((r["name"], field), []), key=lambda x: x[0].span, reverse=True):
                a, b = c.span
                r[field] = r[field][:a] + new + r[field][b:]
    written = False
    csv_text = dump_rows(fieldnames, rows)
    if csv_text != (root / DOMAINS).read_text(encoding="utf-8"):
        with (root / DOMAINS).open("w", encoding="utf-8", newline="") as f:
            f.write(csv_text)
        written = True
    side_text = dump_sidecar(sidecar_of(root, rows))
    side_path = root / SIDECAR
    if not side_path.is_file() or side_text != side_path.read_text(encoding="utf-8"):
        with side_path.open("w", encoding="utf-8", newline="") as f:
            f.write(side_text)
        written = True
    return FixResult(moved, [], written)


def engine_names(row: str) -> list[re.Pattern[str]]:
    """The patterns ``--apt`` looks for: the row name, a table's name, a level or dimension row's quoted prefix."""
    pats = [re.compile(rf"(?<![A-Za-z0-9_]){re.escape(row)}(?![A-Za-z0-9_])")]
    if "[" in row:
        table = row.split("[", 1)[0]
        pats.append(re.compile(rf"(?<![A-Za-z0-9_]){re.escape(table)}(?![A-Za-z0-9_])"))
    elif "_" in row:
        prefix = row.rsplit("_", 1)[0] + "_"
        pats.append(re.compile(rf"[\"']{re.escape(prefix)}[\"'{{]"))
    return pats


@dataclass(frozen=True)
class Apt:
    cite: Cite
    apt: bool
    lines_in_file: list[int]
    """For a miss: the lines of the cited file that mention one of the names."""


def apt(root: Path) -> list[Apt]:
    _, rows = read_rows(root)
    files = Files(root)
    out = []
    for c in cites_of(root, rows):
        if c.path is None:
            continue
        lines = files.lines(c.path)
        pats = engine_names(c.row)
        lo, hi = max(1, c.first - APT_WINDOW), min(len(lines), c.last + APT_WINDOW)
        ok = any(p.search(lines[i - 1]) for i in range(lo, hi + 1) for p in pats)
        hits = [] if ok else [i + 1 for i, line in enumerate(lines) if any(p.search(line) for p in pats)]
        out.append(Apt(c, ok, hits))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="exit 1 on any stale or unresolved cite")
    mode.add_argument("--fix", action="store_true", help="re-anchor stale cites by unique exact text")
    mode.add_argument("--apt", action="store_true", help="report whether each cited line mentions its parameter")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    root: Path = args.root
    if args.check:
        problems, rules = check(root)
        print(
            f"{sum(rules.values())} cites; resolved by rule: " + ", ".join(f"{k} {v}" for k, v in sorted(rules.items()))
        )
        for p in problems:
            print(p)
        if problems:
            print(f"{len(problems)} cite(s) fail; re-anchor with: {FIX_COMMAND}")
            return 1
        print("all cites match their stored text")
        return 0
    if args.fix:
        result = fix(root)
        for c, new in result.moved:
            print(f"{c.row} {c.field}: {c.text} -> {new}")
        if result.unresolved:
            for p in result.unresolved:
                print(f"UNRESOLVED {p}")
            print(f"{len(result.unresolved)} unresolved, {len(result.moved)} re-anchorable; nothing written")
            return 1
        print(f"{len(result.moved)} re-anchored; {'written' if result.written else 'no change'}")
        return 0
    report = apt(root)
    for a in report:
        if not a.apt:
            where = a.cite.path.as_posix() if a.cite.path else "?"
            print(f"MISS\t{a.cite.row}\t{a.cite.field}\t{a.cite.text}\t{where}\tname lines {a.lines_in_file}")
    misses = sum(not a.apt for a in report)
    print(f"{len(report)} cites; {len(report) - misses} apt, {misses} not")
    return 0


if __name__ == "__main__":
    sys.exit(main())
