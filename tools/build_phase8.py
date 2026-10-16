"""Generate the phase 8 baseline, ``src/aisim/data/baseline_phase8.json``, from the Phase 7 baseline, a spec and a fit.

The phase 8 parameter set is the Phase 7 set (``baseline.json``) plus the model extensions at ``EXTENSION_DEFAULTS``,
with two changes: the values the spec sets (``tools/phase8_spec.json``: ``PassThrough``, ``AnnuityShare``,
``AnnuityAnchorW``) and the values the spec's fit found (``tools/fits/phase8_pricing.json``: ``PriceHorizon``). Every
key is written explicitly. The tables and the 2024 state are Phase 7's: phase 8 adds no stock and is neutral in 2024.

The fit must have been made at the spec's values (its ``fixed`` equals the spec's ``set``), and the spec and the fit
may not set the same parameter. The output has no timestamp, so running the tool again gives a byte-identical file.

Usage: ``uv run python tools/build_phase8.py``
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim.params import EXTENSION_DEFAULTS

ROOT: Final = Path(__file__).resolve().parent.parent
DATA: Final = ROOT / "src" / "aisim" / "data"
BASELINE: Final = DATA / "baseline.json"
SPEC: Final = ROOT / "tools" / "phase8_spec.json"
OUTPUT: Final = DATA / "baseline_phase8.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(spec_path: Path = SPEC) -> str:
    """Return the text of ``baseline_phase8.json``. Raises ``ValueError`` if the spec and the fit disagree."""
    base_bytes = BASELINE.read_bytes()
    # Any: parsed JSON.
    base: dict[str, Any] = json.loads(base_bytes)
    spec_bytes = spec_path.read_bytes()
    spec: dict[str, Any] = json.loads(spec_bytes)
    fit_path = ROOT / spec["fit"]
    fit_bytes = fit_path.read_bytes()
    fit: dict[str, Any] = json.loads(fit_bytes)
    params: dict[str, float | None] = dict(base["params"])
    for name, value in EXTENSION_DEFAULTS.items():
        params.setdefault(name, value)
    set_values: dict[str, float] = {k: float(v) for k, v in spec["set"].items()}
    fitted: dict[str, float] = {k: float(v) for k, v in fit["fitted"].items()}
    if {k: float(v) for k, v in fit["fixed"].items()} != set_values:
        raise ValueError(f"the fit was made at {fit['fixed']}, not at the spec's values {set_values}")
    if set(set_values) & set(fitted):
        raise ValueError(f"the spec and the fit both set {sorted(set(set_values) & set(fitted))}")
    unknown = sorted(k for k in [*set_values, *fitted] if k not in params)
    if unknown:
        raise ValueError(f"unknown parameter(s): {unknown}")
    params.update(set_values)
    params.update(fitted)
    out = {
        "meta": {
            "model": spec["model"],
            "baseline_sha256": sha256_bytes(base_bytes),
            "spec": spec_path.relative_to(ROOT).as_posix(),
            "spec_sha256": sha256_bytes(spec_bytes),
            "fit": spec["fit"],
            "fit_sha256": sha256_bytes(fit_bytes),
            "set": set_values,
            "fitted": fitted,
            "command": "uv run python tools/build_phase8.py",
            "note": base["meta"]["note"],
        },
        "params": params,
        "tables": base["tables"],
        "init": base["init"],
    }
    return json.dumps(out, indent=1) + "\n"


def main() -> int:
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as f:
        f.write(build())
    print(f"wrote {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
