"""Generate the golden outputs in ``reference/goldens/`` from the frozen prototype.

Writes ``base.json`` (AI on) and ``ai_off.json`` (AI off) from in-process base runs, ``phase7_results.json`` as a byte
copy of a full ``phase7_runs.py`` run, and ``MANIFEST.json`` with the prototype tree hash, the hash of each golden file,
the environment and the wall time of each part. Run only when a slice prompt says so:

``uv run python tools/generate_goldens.py``
"""

from __future__ import annotations

import datetime as dt
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.hash_tree import hash_tree, sha256_file
from tools.reference_runner import PROTOTYPE, ROOT, RunResult, run_base, run_full_suite

GOLDENS = ROOT / "reference" / "goldens"
COMMAND = "uv run python tools/generate_goldens.py"


def write_json(path: Path, obj: Any) -> None:
    """Write ``obj`` as JSON with ``indent=1``, UTF-8 and LF line endings on every platform."""
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=1)


def as_golden(result: RunResult) -> dict[str, Any]:
    """Name the parts of a prototype run result."""
    rows, final_state, mins = result
    return {"rows": rows, "final_state": final_state, "mins": mins}


def uv_version() -> str:
    """Return ``uv --version``, using the uv that launched this process when known."""
    uv = os.environ.get("UV", "uv")
    try:
        return subprocess.run([uv, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    """Generate every golden file and the manifest."""
    GOLDENS.mkdir(parents=True, exist_ok=True)
    started = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    wall: dict[str, float] = {}

    t0 = time.perf_counter()
    write_json(GOLDENS / "base.json", as_golden(run_base(ai_on=True, record_every=0.25)))
    wall["base"] = round(time.perf_counter() - t0, 3)
    print(f"base.json: {wall['base']} s", flush=True)

    t0 = time.perf_counter()
    write_json(GOLDENS / "ai_off.json", as_golden(run_base(ai_on=False, record_every=0.25)))
    wall["ai_off"] = round(time.perf_counter() - t0, 3)
    print(f"ai_off.json: {wall['ai_off']} s", flush=True)

    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copyfile(run_full_suite(Path(tmp) / "suite"), GOLDENS / "phase7_results.json")
    wall["full_suite"] = round(time.perf_counter() - t0, 3)
    print(f"phase7_results.json: {wall['full_suite']} s", flush=True)

    tree = hash_tree(PROTOTYPE)
    manifest = {
        "prototype": {"path": "reference/prototype", "tree_sha256": tree.tree, "files": tree.files},
        "goldens": {name: sha256_file(GOLDENS / name) for name in ("base.json", "ai_off.json", "phase7_results.json")},
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "uv_version": uv_version(),
        },
        "generated_utc": started,
        "command": COMMAND,
        "wall_time_s": wall,
    }
    write_json(GOLDENS / "MANIFEST.json", manifest)
    print(f"MANIFEST.json written; prototype tree {tree.tree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
