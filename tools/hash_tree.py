"""Hash every file under a directory and combine the hashes into one tree hash.

Each file contributes one line, ``<sha256 hex>  <relative POSIX path>\\n``, in sorted path order. The tree hash is the
SHA-256 of all lines concatenated and encoded as UTF-8. Used to pin the frozen prototype in ``reference/prototype/``.
Bytecode (``__pycache__`` directories and ``*.pyc`` files) is skipped, so running the prototype cannot change the hash.

Usage: ``python tools/hash_tree.py <directory>``
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TreeHash:
    """The per-file SHA-256 hashes of a directory, keyed by POSIX relative path, and the combined tree hash."""

    files: dict[str, str]
    tree: str


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_ignored(rel: Path) -> bool:
    """True for bytecode: any path with a ``__pycache__`` component, and any ``*.pyc`` file."""
    return "__pycache__" in rel.parts or rel.suffix == ".pyc"


def hash_tree(root: Path) -> TreeHash:
    """Hash every file under ``root``, sorted by POSIX path relative to it, skipping bytecode (``is_ignored``)."""
    paths = sorted(
        (p for p in root.rglob("*") if p.is_file() and not is_ignored(p.relative_to(root))),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    files = {p.relative_to(root).as_posix(): sha256_file(p) for p in paths}
    lines = "".join(f"{digest}  {rel}\n" for rel, digest in files.items())
    return TreeHash(files=files, tree=hashlib.sha256(lines.encode("utf-8")).hexdigest())


def main(argv: list[str]) -> int:
    """Print the file count, tree hash and per-file hashes of the directory given in ``argv``."""
    if len(argv) != 1:
        print("usage: python tools/hash_tree.py <directory>", file=sys.stderr)
        return 2
    root = Path(argv[0])
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 2
    result = hash_tree(root)
    print(f"files: {len(result.files)}")
    print(f"tree:  {result.tree}")
    for rel, digest in result.files.items():
        print(f"{digest}  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
