"""Generate the model's baseline data, ``src/aisim/data/baseline.json`` and ``src/aisim/data/parameters.csv``.

The baseline is the calibrated Phase 7 parameter set, the module-level tables of the prototype and the calibrated 2024
state, taken from the frozen prototype without modifying it:

- ``reference/prototype/data/calib7.json`` supplies ``params`` and ``init``.
- A fresh copy of ``phase7_sim.py`` (through ``tools.reference_runner``) supplies the two parameters that
  ``calib7.json`` predates, ``DemandGrowthLate`` and ``LateYear``, and the tables ``SEC6``, ``WT6``, ``EMPS6``, ``MIX0``
  and ``SRC0``.

The scalar parameters are assembled exactly as ``phase7_runs.py`` lines 6-10 assemble them: module ``P``, then
every calibrated key that is in ``P`` or has a calibration-only prefix. The ``-1.0`` sentinel of ``DemandGrowthLate``
is stored as ``null``, meaning "same as ``DemandGrowth``".

``parameters.csv`` classifies every scalar:

- ``kind``: ``calibrated`` (written by ``calibrate7_ss.py``, recon class c), ``unused`` (never read by ``run()``, recon
  class e) or ``structural`` (everything else). After the prototype's scalars come the model extensions
  (``aisim.params.EXTENSION_DEFAULTS``, not in ``baseline.json``), one row each with ``kind`` ``extension``.
- ``lever``: ``yes`` if a scenario or the tornado in ``reference/goldens/phase7_results.json`` sets it.
- ``fitted``: ``yes`` for the names in ``calibrate7.py`` ``FIT``, read from its source without running it.

Usage: ``uv run python tools/build_baseline.py``
"""

from __future__ import annotations

import ast
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim.params import EXTENSION_DEFAULTS
from tools.hash_tree import hash_tree, sha256_file
from tools.reference_runner import CALIB_PATH, CODE, PROTOTYPE, ROOT, apply_calibration, load_prototype_sim

DATA = ROOT / "src" / "aisim" / "data"
BASELINE = DATA / "baseline.json"
PARAMETERS_CSV = DATA / "parameters.csv"
RESULTS = ROOT / "reference" / "goldens" / "phase7_results.json"
COMMAND = "uv run python tools/build_baseline.py"

N_SCALARS = 330
N_INIT_KEYS = 37
N_INIT_LEAVES = 347

# Recon class c: the parameters calibrate7_ss.py writes. The first seven prefixes are the calibration-only families.
CALIBRATED_PREFIXES = (
    "SrcASC_",
    "TypeASC_",
    "LOB0_",
    "Port0_",
    "Seats0_",
    "Budget0_",
    "LabourCostPB0_",
    "BaseEnrolment_",
    "NormalUnempRate_",
    "NormalTTF_",
    "PriceMult_",
    "NormalMargin_",
)
CALIBRATED_NAMES = frozenset({"CostPerBFY0", "CostRef"})
N_CALIBRATED = 99

# Recon class e: never read by run().
UNUSED = frozenset({"TargetMargin_OIT", "TargetMargin_GSI", "TargetMargin_BQ", "Att0", "NormalUtil", "Leakage"})

# The 11 names of calibrate7.py FIT, as the slice prompt lists them. DemandGrowth is set from data, not fitted.
EXPECTED_FIT = frozenset(
    {"p", "q", "Verif", "GCCAppealEnd", "JuniorCut", "GCCMomentum", "qC", "pAtt", "PriceHorizon", "SeekerExitRate"}
    | {"AICost2024"}
)

NOTE = 'DemandGrowthLate null means "same as DemandGrowth" (the prototype encodes this as the sentinel -1.0).'


def fit_names() -> frozenset[str]:
    """Return the parameter names in ``calibrate7.py`` ``FIT``, parsed from its source without running it."""
    tree = ast.parse((CODE / "calibrate7.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "FIT" for t in node.targets):
            fit: list[tuple[str, float, float]] = ast.literal_eval(node.value)
            return frozenset(name for name, _, _ in fit)
    raise ValueError("FIT not found in calibrate7.py")


def float_table(table: dict[str, Any]) -> dict[str, float]:
    """Return a one-dimensional table with every value as a float."""
    return {k: float(v) for k, v in table.items()}


def count_leaves(obj: Any) -> int:
    """Count the non-dict leaves of a nested dict."""
    return sum(count_leaves(v) for v in obj.values()) if isinstance(obj, dict) else 1


def build() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Build the baseline object and the parameter CSV rows."""
    sim = load_prototype_sim()
    init = apply_calibration(sim)
    with CALIB_PATH.open(encoding="utf-8") as f:
        calib = json.load(f)

    effective: dict[str, Any] = dict(sim.P)
    missing = set(effective) - set(calib["params"])
    if missing != {"DemandGrowthLate", "LateYear"} or len(effective) != N_SCALARS:
        raise ValueError(f"unexpected parameter set: {len(effective)} keys, not in calib7.json: {sorted(missing)}")
    if effective["DemandGrowthLate"] != -1.0:
        raise ValueError(f"DemandGrowthLate is {effective['DemandGrowthLate']!r}, not the -1.0 sentinel")
    params: dict[str, float | None] = {k: (None if k == "DemandGrowthLate" else float(v)) for k, v in effective.items()}

    tables: dict[str, Any] = {
        "SectorShare": float_table(sim.SEC6["SectorShare"]),
        "LOBWage": float_table(sim.SEC6["LOBWage"]),
        "RegDragLevel": float_table(sim.SEC6["RegDragLevel"]),
        "WTMix": float_table(sim.WT6["Mix"]),
        "a2024": float_table(sim.WT6["a2024"]),
        "amax": float_table(sim.WT6["amax"]),
        "SpeedUp": float_table(sim.WT6["s"]),
        "BuildMix": float_table(sim.WT6["BuildMix"]),
        "OffExp": float_table(sim.EMPS6["OffExp"]),
        "Mix0": {v: float_table(row) for v, row in sim.MIX0.items()},
        "Src0": {x: float_table(row) for x, row in sim.SRC0.items()},
    }
    if len(init) != N_INIT_KEYS or count_leaves(init) != N_INIT_LEAVES:
        raise ValueError(f"unexpected init: {len(init)} keys, {count_leaves(init)} leaves")

    baseline = {
        "meta": {
            "source_tree_sha256": hash_tree(PROTOTYPE).tree,
            "calib7_sha256": sha256_file(CALIB_PATH),
            "command": COMMAND,
            "note": NOTE,
        },
        "params": params,
        "tables": tables,
        "init": init,
    }

    fitted = fit_names()
    if fitted != EXPECTED_FIT:
        raise ValueError(f"calibrate7.py FIT is {sorted(fitted)}, expected {sorted(EXPECTED_FIT)}")
    with RESULTS.open(encoding="utf-8") as f:
        results = json.load(f)
    levers = {k for s in results["scenarios"].values() for k in s["over"]} | {t["param"] for t in results["tornado"]}
    if not levers <= set(params):
        raise ValueError(f"levers not in the parameter set: {sorted(levers - set(params))}")

    rows: list[dict[str, str]] = []
    n_calibrated = 0
    for name, value in params.items():
        if name.startswith(CALIBRATED_PREFIXES) or name in CALIBRATED_NAMES:
            kind = "calibrated"
            n_calibrated += 1
        elif name in UNUSED:
            kind = "unused"
        else:
            kind = "structural"
        rows.append(
            {
                "name": name,
                "value": "" if value is None else repr(value),
                "kind": kind,
                "lever": "yes" if name in levers else "no",
                "fitted": "yes" if name in fitted else "no",
            }
        )
    for name, ext in EXTENSION_DEFAULTS.items():
        rows.append({"name": name, "value": repr(ext), "kind": "extension", "lever": "no", "fitted": "no"})
    if n_calibrated != N_CALIBRATED:
        raise ValueError(f"{n_calibrated} calibrated parameters, expected {N_CALIBRATED}")
    return baseline, rows


def render() -> tuple[dict[str, Any], str, str, int]:
    """The baseline object, the text of ``baseline.json`` and of ``parameters.csv``, and the CSV row count."""
    baseline, rows = build()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["name", "value", "kind", "lever", "fitted"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return baseline, json.dumps(baseline, indent=1) + "\n", buf.getvalue(), len(rows)


def main() -> int:
    """Write ``baseline.json`` and ``parameters.csv``."""
    baseline, baseline_text, csv_text, n_rows = render()
    DATA.mkdir(parents=True, exist_ok=True)
    with BASELINE.open("w", encoding="utf-8", newline="\n") as f:
        f.write(baseline_text)
    with PARAMETERS_CSV.open("w", encoding="utf-8", newline="") as f:
        f.write(csv_text)
    print(
        f"{BASELINE.relative_to(ROOT).as_posix()}: {len(baseline['params'])} params, {len(baseline['tables'])} tables"
    )
    print(f"{PARAMETERS_CSV.relative_to(ROOT).as_posix()}: {n_rows} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
