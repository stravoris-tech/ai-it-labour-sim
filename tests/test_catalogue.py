"""The package data tables: ``domains.csv`` and ``catalogue.csv``, and their loaders."""

from __future__ import annotations

import math

import pytest

from aisim import Params, catalogue, domains, keys
from aisim.batch.params import TABLE_AXES
from aisim.batch.record import EXTRA_KEYS, ROW_KEYS
from aisim.experiment.derived import DERIVED

NEVER_READ = {"TargetMargin_OIT", "TargetMargin_GSI", "TargetMargin_BQ", "Att0", "Leakage", "NormalUtil", "Wage_OV"}


def test_domains_cover_every_scalar_and_table_entry_in_order() -> None:
    expect = list(Params.baseline().scalars)
    for name, axes in TABLE_AXES.items():
        if len(axes) == 1:
            expect += [f"{name}[{k}]" for k in axes[0]]
        else:
            expect += [f"{name}[{a}][{b}]" for a in axes[0] for b in axes[1]]
    df = domains()
    assert list(df.columns) == [
        "name",
        "domain",
        "lower",
        "lower_inclusive",
        "upper",
        "upper_inclusive",
        "evidence",
        "notes",
        "read",
        "level_2024",
    ]
    assert list(df["name"]) == expect
    assert len(df) == 439


def test_domain_classes_and_bounds() -> None:
    df = domains().set_index("name")
    assert set(df["domain"]) == {
        "positive",
        "non_negative",
        "unit_interval",
        "below_one",
        "year",
        "ordered_pair",
        "switch",
        "free",
        "growth",
    }
    for name in ("DemandGrowth", "DemandGrowthLate", "ITBudgetGrowth"):
        assert df.loc[name, "domain"] == "growth"
        assert df.loc[name, "lower"] == -1 and not df.loc[name, "lower_inclusive"]
    for name in ("StepYear", "PriceShockYear", "LateYear"):
        assert (df.loc[name, "lower"], df.loc[name, "upper"]) == (2000, 2100)
    for name in ("PriceHorizon", "DurPUSens", "Verif", "GCCAppealKeep"):
        assert df.loc[name, "domain"] == "non_negative"
    assert df.loc["WageMin", "domain"] == "positive"
    for name in ("NormalUnempRate_IN", "NormalMargin_OIT"):
        assert df.loc[name, "domain"] == "positive" and df.loc[name, "upper"] == 1 and df.loc[name, "upper_inclusive"]
    assert not df.loc["AICostDecline", "upper_inclusive"] and df.loc["g", "upper_inclusive"]
    # A bound and its inclusive flag are given together; positive bounds are exclusive at 0.
    for side in ("lower", "upper"):
        has_bound = ~df[side].isna()
        assert (has_bound == ~df[f"{side}_inclusive"].isna()).all()
    pos = df[df["domain"] == "positive"]
    assert (pos["lower"] == 0).all() and (~pos["lower_inclusive"].astype(bool)).all()


def test_read_flags() -> None:
    df = domains()
    unread = set(df.loc[~df["read"], "name"])
    tables = {n for n in df["name"] if n.startswith(("Mix0[", "Src0["))}
    assert unread == NEVER_READ | tables
    assert len(tables) == 50


def test_catalogue_keys_kinds_and_units() -> None:
    df = catalogue()
    assert list(df.columns) == ["key", "family", "dims", "unit", "description", "spec_ref", "kind", "unit_inferred"]
    assert list(df["key"]) == [*ROW_KEYS, *EXTRA_KEYS, *DERIVED]
    assert list(df["kind"]) == ["row"] * 317 + ["extra"] * len(EXTRA_KEYS) + ["derived"] * len(DERIVED)
    assert len(EXTRA_KEYS) == 96
    assert int(df["unit_inferred"].sum()) == 46
    assert (df["unit"] != "").all()
    derived = df.set_index("key").loc[list(DERIVED)]
    assert [str(f) for f in derived["description"]] == [d.formula for d in DERIVED.values()]


def test_keys_by_family() -> None:
    assert keys("Q1 headcount lines") == ["Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia"]
    assert keys("derived") == list(DERIVED)
    assert len(keys("contract book (extra)")) == 15
    assert keys() == list(catalogue()["key"])
    with pytest.raises(KeyError):
        keys("no such family")


def test_loaders_return_copies() -> None:
    a = domains()
    a.loc[0, "lower"] = math.pi
    assert domains().loc[0, "lower"] != math.pi
