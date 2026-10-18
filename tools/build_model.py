"""Generate a model's baseline file from the Phase 7 baseline, a spec and a fit.

The new parameter set is the Phase 7 set (``src/aisim/data/baseline.json``) plus the model extensions at
``EXTENSION_DEFAULTS`` (the ``LEGACY_EXTENSIONS`` always, a later extension only when the spec or the fit names it;
``Params.baseline`` fills in the others at their defaults, so the phase 8 files stay byte-identical), with three kinds
of change: the values the spec sets (its ``set``), the values its fit found (the fit JSON's ``fitted``, written by
``tools/calibrate.py``) and the derived constants those move (``AdoptC0`` when ``pC``, ``qC`` or ``AC0`` changes),
computed by ``Params.with_overrides`` as the fit computed them, so that the file reproduces its fit's loss bit for
bit. Every key is written explicitly, in Phase 7's order. The tables and the 2024
state are Phase 7's: the extensions add no stock.

The spec is a JSON object: ``model`` (a free label, copied into the output's meta), ``set`` (name to value), ``fit``
(the fit JSON's path, relative to the repository root unless absolute) and an optional ``note``. The tool assumes no
model name. The fit must have been made at the spec's values (its ``fixed`` equals the spec's ``set``), and the spec
and the fit may not set the same parameter. The output has no timestamp, so running the tool again with the same
arguments gives a byte-identical file.

A shipped model's spec and fit live in ``tools/models/<name>/`` (``spec.json``, ``fit.json``), and this tool writes
its ``src/aisim/data/baseline_<name>.json``, registered in ``aisim.state.BASELINE_FILES``. A model is built this way,
``tools/calibrate.py`` then this tool, never by hand.

Usage: ``uv run python tools/build_model.py --spec tools/models/phase8/spec.json --out
src/aisim/data/baseline_phase8.json``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim.params import EXTENSION_DEFAULTS, LEGACY_EXTENSIONS, Params

ROOT: Final = Path(__file__).resolve().parent.parent
BASELINE: Final = ROOT / "src" / "aisim" / "data" / "baseline.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def derived_values(
    params: Mapping[str, float | None], tables: Mapping[str, Any], changes: Mapping[str, float]
) -> dict[str, float | None]:
    """The derived constants that ``changes`` move, by ``Params.with_overrides`` itself (today ``AdoptC0``, recomputed
    when ``pC``, ``qC`` or ``AC0`` changes), so that the file holds the parameter set the fit evaluated.
    ``Any``: the parsed tables."""
    new = Params(scalars=params, tables=tables).with_overrides(**changes).scalars
    return {k: new[k] for k in params if k not in changes and new[k] != params[k]}


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def build(spec_path: Path, out_path: Path | None = None) -> str:
    """Return the text of the baseline file the spec describes. Raises ``ValueError`` if the spec and the fit
    disagree or name an unknown parameter. ``out_path`` is only recorded in the meta's ``command``."""
    base_bytes = BASELINE.read_bytes()
    # Any: parsed JSON.
    base: dict[str, Any] = json.loads(base_bytes)
    spec_bytes = spec_path.read_bytes()
    spec: dict[str, Any] = json.loads(spec_bytes)
    fit_bytes = _resolve(spec["fit"]).read_bytes()
    fit: dict[str, Any] = json.loads(fit_bytes)
    set_values: dict[str, float] = {k: float(v) for k, v in spec["set"].items()}
    fitted: dict[str, float] = {k: float(v) for k, v in fit["fitted"].items()}
    params: dict[str, float | None] = dict(base["params"])
    for name, value in EXTENSION_DEFAULTS.items():
        if name in LEGACY_EXTENSIONS or name in set_values or name in fitted:
            params.setdefault(name, value)
    if {k: float(v) for k, v in fit["fixed"].items()} != set_values:
        raise ValueError(f"the fit was made at {fit['fixed']}, not at the spec's values {set_values}")
    if set(set_values) & set(fitted):
        raise ValueError(f"the spec and the fit both set {sorted(set(set_values) & set(fitted))}")
    unknown = sorted(k for k in [*set_values, *fitted] if k not in params)
    if unknown:
        raise ValueError(f"unknown parameter(s): {unknown}")
    derived = derived_values(params, base["tables"], {**set_values, **fitted})
    params.update(set_values)
    params.update(fitted)
    params.update(derived)
    command = f"uv run python tools/build_model.py --spec {spec_path.as_posix()}"
    if out_path is not None:
        command += f" --out {out_path.as_posix()}"
    out = {
        "meta": {
            "model": spec["model"],
            "baseline_sha256": sha256_bytes(base_bytes),
            "spec": spec_path.as_posix(),
            "spec_sha256": sha256_bytes(spec_bytes),
            "fit": spec["fit"],
            "fit_sha256": sha256_bytes(fit_bytes),
            "set": set_values,
            "fitted": fitted,
            "derived": derived,
            "command": command,
            "note": base["meta"]["note"],
        },
        "params": params,
        "tables": base["tables"],
        "init": base["init"],
    }
    return json.dumps(out, indent=1) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--spec", required=True, type=Path, help="the spec JSON (model, set, fit, note)")
    ap.add_argument("--out", required=True, type=Path, help="the baseline file to write")
    a = ap.parse_args(argv)
    text = build(a.spec, a.out)
    with a.out.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {a.out.as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
