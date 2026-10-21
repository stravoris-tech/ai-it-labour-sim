"""The model inventory and data dictionary stay in step with the code (``tools/model_docs.py``, slice 10a)."""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

import pytest

from aisim.charts.colours import PALETTE
from tools import model_docs as M
from tools import model_graph as G

ROOT = Path(__file__).resolve().parent.parent
CITE = re.compile(r"^([A-Za-z0-9_./-]+\.(?:py|md|csv|json)):(\d+)(?:-(\d+))?$")
LINE_REF = re.compile(r"[A-Za-z_0-9]+\.py:\d+")
DERIVED_PROTOTYPE_CITES = frozenset({"IndiaPeople_ConsIndia", "IndiaPeople_VendIndia"})
"""Derived rows whose formula cites the prototype (``phase7_runs.py:14``), pinned by ``test_catalogue`` to
``aisim.experiment.derived.DERIVED`` (operator ruling, slice 10a); every other description is free of line cites."""
SPEC_CITE = re.compile(r"`(reference/prototype/spec/[0-9a-z_]+\.md):(\d+)(?:-(\d+))?`")


@pytest.fixture(scope="module")
def inv() -> M.Inventory:
    return M.build_inventory(ROOT)


@pytest.fixture(scope="module")
def meta() -> dict[tuple[str, str], dict[str, str]]:
    return M.read_metadata(ROOT)


def _lines(path: str) -> int:
    return len((ROOT / path).read_text(encoding="utf-8").splitlines())


def _cites_exist(sources: str) -> list[str]:
    bad = []
    for c in (x.strip() for x in sources.split(";")):
        m = CITE.match(c)
        if not m:
            bad.append(c)
            continue
        a, b = int(m.group(2)), int(m.group(3) or m.group(2))
        if not (ROOT / m.group(1)).is_file() or not 1 <= a <= b <= _lines(m.group(1)):
            bad.append(c)
    return bad


# ---- coverage --------------------------------------------------------------------------------------------------------


def test_every_item_has_exactly_one_metadata_row(inv: M.Inventory) -> None:
    rows = M.read_csv(ROOT / M.DATA / "model_docs.csv")
    keys = [(r["name"], r["kind"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert set(keys) == {it.key for it in inv.items}
    with (ROOT / M.DATA / "model_docs.csv").open(encoding="utf-8", newline="") as f:
        assert tuple(next(csv.reader(f))) == M.DOCS_COLUMNS


def test_every_module_has_a_row_with_its_palette_colour() -> None:
    mods = M.read_modules(ROOT)
    assert [m["module"] for m in mods] == [
        "capability",
        "adoption",
        "consumer",
        "work",
        "workforce",
        "labour_market",
        "sourcing",
        "finance",
    ]
    assert set(m["module"] for m in mods) == set(G.MODULES)
    assert [m["colour"] for m in mods] == list(PALETTE[:8])
    with (ROOT / M.DATA / "model_modules.csv").open(encoding="utf-8", newline="") as f:
        assert tuple(next(csv.reader(f))) == M.MODULE_COLUMNS
    for m in mods:
        assert m["display_name"] and m["description"] and m["status"] in M.STATUSES
        assert len(m["description"].split()) <= 30
        assert _cites_exist(m["sources"]) == []


def test_every_item_has_one_of_the_8_modules(inv: M.Inventory, meta: dict[tuple[str, str], dict[str, str]]) -> None:
    for it in inv.items:
        assert it.module in G.MODULES, it.key
        assert meta[it.key]["module"] == it.module, it.key


# ---- completeness and consistency ---------------------------------------------------------------------------------


def test_rows_are_complete(meta: dict[tuple[str, str], dict[str, str]]) -> None:
    for key, r in meta.items():
        for c in ("label", "description", "units", "sources"):
            assert r[c].strip(), (key, c)
        assert r["status"] in M.STATUSES, key
        if r["units"] == "unclear":
            assert r["status"] == "drafted" and r["notes"].strip(), key
        else:
            assert M.unit_ok(r["units"]), (key, r["units"])
        assert _cites_exist(r["sources"]) == [], key


def test_labels_and_descriptions_are_short(meta: dict[tuple[str, str], dict[str, str]]) -> None:
    for key, r in meta.items():
        assert len(r["label"].split()) <= 4, key
        assert len(r["description"].split()) <= 30, key
        assert not LINE_REF.search(r["description"]), key


def test_unit_check_rejects_terms_outside_the_vocabulary() -> None:
    assert M.unit_ok("model-unit persons per year")
    assert M.unit_ok("USD per model-unit person per year")
    assert not M.unit_ok("people per year")
    assert not M.unit_ok("USD per BFY per fortnight")


def stock_flow_pairs(inv: M.Inventory) -> list[tuple[str, str]]:
    """(stock, flow) for every flow that enters a stock's update: the named flows read by it, and ``flow:<Stock>``."""
    pairs = {
        (e.target[6:], e.source[5:])
        for e in inv.edges
        if e.target.startswith("stock:")
        and e.source.startswith("item:")
        and e.source[5:] in M.NAMED_FLOWS
        and e.target[6:] not in M.REFERENCE_STOCKS
    }
    pairs |= {(s, f"flow:{s}") for s in M.UNNAMED_FLOWS}
    return sorted(pairs)


def test_flows_carry_their_stocks_units_per_year(inv: M.Inventory, meta: dict[tuple[str, str], dict[str, str]]) -> None:
    kind = {it.name: it.kind for it in inv.items if it.kind == "flow"}
    bad = []
    for stock, flow in stock_flow_pairs(inv):
        su, fu = meta[(stock, "stock")]["units"], meta[(flow, kind[flow])]["units"]
        if "unclear" in (su, fu) or (stock, flow) in M.UNIT_ALLOWLIST:
            continue
        if fu != su + " per year":
            bad.append((stock, su, flow, fu))
    assert bad == []
    assert all(p in stock_flow_pairs(inv) for p in M.UNIT_ALLOWLIST)


def test_name_clashes_are_stated_in_both_rows(inv: M.Inventory, meta: dict[tuple[str, str], dict[str, str]]) -> None:
    clashes = M.name_clashes(inv.items)
    assert len(clashes) >= 11
    for its in clashes.values():
        for it in its:
            text = meta[it.key]["description"].lower()
            for other in its:
                if other is not it:
                    assert other.kind in text, (it.key, other.kind)


def test_loop_items_record_their_term(meta: dict[tuple[str, str], dict[str, str]]) -> None:
    for lt in M.LOOP_TERM_TABLE:
        for s in lt.strengths:
            assert f"term: {lt.term}" in meta[(s, "parameter")]["notes"], s


def test_no_catalogue_description_carries_a_line_reference() -> None:
    assert LINE_REF.search("planted (finance.py:293)")  # positive control
    rows = M.read_csv(ROOT / M.DATA / "catalogue.csv")
    hits = {r["key"] for r in rows if LINE_REF.search(r["description"])}
    assert hits == DERIVED_PROTOTYPE_CITES


def test_tables_are_baseline_data_and_not_levers(inv: M.Inventory) -> None:
    """The 11 tables are set baseline data, not levers; the two that ``run()`` never reads say so (slice 10b)."""
    tables = [it for it in inv.items if it.kind == "table"]
    assert len(tables) == 11
    assert {(it.classification, it.lever) for it in tables} == {("set (baseline data)", "no")}
    rows = {(r["name"], r["kind"]): r for r in M.read_csv(ROOT / M.DATA / "model_docs.csv")}
    for name in ("Mix0", "Src0"):
        assert "not read by run()" in rows[(name, "table")]["notes"]


# ---- the errata ---------------------------------------------------------------------------------------------------


def test_errata_spec_lines_exist() -> None:
    text = (ROOT / "docs" / "spec-errata.md").read_text(encoding="utf-8")
    entries = re.findall(r"^### (E\d+):", text, flags=re.M)
    assert sorted(entries, key=lambda e: int(e[1:])) == [f"E{i}" for i in range(1, 37)]
    cites = SPEC_CITE.findall(text)
    assert len(cites) >= 33
    for path, a, b in cites:
        assert 1 <= int(a) <= int(b or a) <= _lines(path), (path, a)


# ---- the generated files ------------------------------------------------------------------------------------------


def test_generated_files_are_current(inv: M.Inventory) -> None:
    assert M.stale(ROOT, inv=inv) == []


def test_check_fails_on_a_copy_with_one_changed_description(inv: M.Inventory, tmp_path: Path) -> None:
    for path in (M.OUT_INVENTORY, M.OUT_EDGES, M.OUT_REFERENCE):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, tmp_path / path)
    assert M.stale(ROOT, tmp_path, inv=inv) == []
    p = tmp_path / M.OUT_INVENTORY
    with p.open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    col = rows[0].index("description")
    rows[1][col] += " Changed."
    with p.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows(rows)
    assert M.stale(ROOT, tmp_path, inv=inv) == [M.OUT_INVENTORY]


def test_two_builds_are_byte_identical(inv: M.Inventory) -> None:
    assert M.build(ROOT, inv) == M.build(ROOT, M.build_inventory(ROOT))
