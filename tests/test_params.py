"""The baseline parameters, overrides and the parameter CSV."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping
from importlib.resources import files
from typing import Any, cast

import pytest

from aisim import Params
from aisim.dims import EMPLOYERS, SECTORS, TYPES, VENDORS, WTYPES
from tools.reference_runner import CALIB_PATH, ROOT, load_prototype_sim

FITTED = {
    "p",
    "q",
    "Verif",
    "GCCAppealEnd",
    "JuniorCut",
    "GCCMomentum",
    "qC",
    "pAtt",
    "PriceHorizon",
    "SeekerExitRate",
    "AICost2024",
}
UNUSED = {"TargetMargin_OIT", "TargetMargin_GSI", "TargetMargin_BQ", "Att0", "NormalUtil", "Leakage"}
TABLE_KEYS: dict[str, tuple[str, ...]] = {
    "SectorShare": SECTORS,
    "LOBWage": SECTORS,
    "RegDragLevel": SECTORS,
    "WTMix": WTYPES,
    "a2024": WTYPES,
    "amax": WTYPES,
    "SpeedUp": WTYPES,
    "BuildMix": WTYPES,
    "OffExp": EMPLOYERS,
}


# Any: the path is a Path or an importlib resource, and the result is parsed JSON of any shape.
def load_json(path: Any) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def csv_rows() -> list[dict[str, str]]:
    text = files("aisim").joinpath("data", "parameters.csv").read_text(encoding="utf-8")
    return list(csv.DictReader(text.splitlines()))


def test_baseline_shape() -> None:
    p = Params.baseline()
    assert len(p.scalars) == 333
    assert set(p.tables) == set(TABLE_KEYS) | {"Mix0", "Src0"}
    for name, keys in TABLE_KEYS.items():
        assert tuple(p.table(name)) == keys, name
    mix0, src0 = p.tables["Mix0"], p.tables["Src0"]
    assert list(mix0) == list(VENDORS)
    assert all(isinstance(row, Mapping) and list(row) == list(TYPES) for row in mix0.values())
    assert list(src0) == list(SECTORS)
    assert all(isinstance(row, Mapping) and list(row) == list(EMPLOYERS) for row in src0.values())


def test_baseline_values_equal_calibration() -> None:
    p = Params.baseline("phase7")
    calib = load_json(CALIB_PATH)["params"]
    assert set(p.scalars) - set(calib) == {
        "DemandGrowthLate",
        "LateYear",
        "AnnuityShare",
        "AnnuityAnchorW",
        "OpeningsContinuous",
    }
    for k, v in calib.items():
        assert p.scalars[k] == v, k
    assert p.scalars["DemandGrowthLate"] is None
    sim = load_prototype_sim()
    assert p.scalars["LateYear"] == sim.P["LateYear"]
    assert sim.P["DemandGrowthLate"] == -1.0
    assert dict(p.table("WTMix")) == sim.WT6["Mix"]
    assert dict(p.table("SpeedUp")) == sim.WT6["s"]
    assert dict(p.table("OffExp")) == sim.EMPS6["OffExp"]
    for name in ("SectorShare", "LOBWage", "RegDragLevel"):
        assert dict(p.table(name)) == sim.SEC6[name], name
    for name in ("a2024", "amax", "BuildMix"):
        assert dict(p.table(name)) == sim.WT6[name], name


def test_overrides_return_new_objects() -> None:
    base = Params.baseline()
    g = base.scalars["g"]
    new = base.with_overrides(g=0.2, DemandGrowthLate=0.01)
    assert new is not base
    assert new.scalars["g"] == 0.2
    assert new.scalars["DemandGrowthLate"] == 0.01
    assert base.scalars["g"] == g
    assert base.scalars["DemandGrowthLate"] is None
    with pytest.raises(TypeError):
        # Any: the point is to try a write that the read-only Mapping type forbids.
        cast(Any, base.scalars)["g"] = 0.3


def test_unknown_override_raises_key_error() -> None:
    with pytest.raises(KeyError):
        Params.baseline().with_overrides(NoSuchParameter=1.0)


def test_adoptc0_recomputed_on_qc_override() -> None:
    base = Params.baseline()
    new = base.with_overrides(qC=0.5)
    pC, AC0 = base.scalars["pC"], base.scalars["AC0"]
    assert pC is not None
    assert AC0 is not None
    assert new.scalars["AdoptC0"] == (pC + 0.5 * AC0) * (1 - AC0)
    assert new.scalars["AdoptC0"] != base.scalars["AdoptC0"]
    kept = base.with_overrides(qC=0.5, AdoptC0=0.07)
    assert kept.scalars["AdoptC0"] == 0.07
    assert base.with_overrides(g=0.2).scalars["AdoptC0"] == base.scalars["AdoptC0"]


def test_with_table_checks_keys() -> None:
    base = Params.baseline()
    shares = dict(base.table("SectorShare"))
    shares["FIN"] = 0.3
    new = base.with_table("SectorShare", shares)
    assert new.table("SectorShare")["FIN"] == 0.3
    assert base.table("SectorShare")["FIN"] == 0.25
    with pytest.raises(ValueError):
        base.with_table("SectorShare", {"FIN": 1.0})
    with pytest.raises(KeyError):
        base.with_table("NoSuchTable", shares)


def test_parameters_csv() -> None:
    rows = csv_rows()
    assert len(rows) == 333
    assert list(rows[0]) == ["name", "value", "kind", "lever", "fitted"]
    assert {r["name"] for r in rows} == set(Params.baseline().scalars)
    assert {r["name"] for r in rows if r["fitted"] == "yes"} == FITTED
    assert {r["name"] for r in rows if r["kind"] == "unused"} == UNUSED
    assert {r["kind"] for r in rows} == {"calibrated", "structural", "unused", "extension"}
    assert sum(r["kind"] == "calibrated" for r in rows) == 99
    results = load_json(ROOT / "reference" / "goldens" / "phase7_results.json")
    levers = {k for s in results["scenarios"].values() for k in s["over"]} | {t["param"] for t in results["tornado"]}
    assert {r["name"] for r in rows if r["lever"] == "yes"} == levers
    assert len(levers) == 23
