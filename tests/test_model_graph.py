"""The static dependency extractor (``tools/model_graph.py``): ground truth, determinism and the loop bindings."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools import model_graph as G

ROOT = Path(__file__).resolve().parent.parent
TRUTH = ROOT / "tests" / "data" / "edges_truth.csv"


@pytest.fixture(scope="module")
def edges() -> list[G.GraphEdge]:
    return G.edges(ROOT)


def _truth() -> list[dict[str, str]]:
    with TRUTH.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_truth_fixture_is_the_recon_ground_truth() -> None:
    rows = _truth()
    assert len(rows) == 44
    assert len({(r["source"], r["target"]) for r in rows}) == 44
    assert {r["target"] for r in rows} == {
        "item:fl.openings",
        "item:fl.layoffs",
        "item:hires",
        "item:sw.out",
        "item:UnempRate",
    }
    for r in rows:  # every cited line exists
        path, lines = r["file_line"].split(":")
        n = len((ROOT / path).read_text(encoding="utf-8").splitlines())
        assert all(1 <= int(x) <= n for x in lines.split(";")), r


def test_extractor_finds_all_44_truth_edges(edges: list[G.GraphEdge]) -> None:
    found = {(e.source, e.target) for e in edges}
    missing = [(r["source"], r["target"]) for r in _truth() if (r["source"], r["target"]) not in found]
    assert missing == []


def test_openings_switch_is_a_control_dependence(edges: list[G.GraphEdge]) -> None:
    dep = {(e.source, e.target): e.dependence for e in edges}
    assert dep[("param:OpeningsContinuous", "item:fl.openings")] == "control"
    assert dep[("param:QuitRate", "item:fl.quits")] == "data"
    assert dep[("param:GCCMomentum", "stock:SrcPerc")] == "data"  # S0


def test_two_passes_are_identical(edges: list[G.GraphEdge]) -> None:
    assert G.edges(ROOT) == edges
    assert G.nodes(ROOT) == G.nodes(ROOT)


def test_loop_helpers_bind_at_their_call_sites(edges: list[G.GraphEdge]) -> None:
    found = {(e.source, e.target) for e in edges}
    expected = {
        ("param:kR7", "item:GCCScaleTerm"),  # R7, sourcing_targets -> loops.r7
        ("stock:WS0", "item:GCCScaleTerm"),
        ("param:R6e", "item:DesiredE"),  # C2, staffing -> loops.cut
        ("stock:VMarg", "item:ClientFlight"),  # C4, option_costs -> loops.client_flight
        ("stock:ECost", "item:VF.PNew"),  # C5, contracts -> loops.floor
        ("param:AIDiscCeil", "item:VF.Anchor"),  # C6, contracts -> loops.ceil
        ("item:fl.quits", "item:VB.VendorCost"),  # R10: fl[u][l]["quits"] inside loops.vol_cell
        ("item:sw.out", "item:VB.VendorCost"),
        ("item:R4Mult", "item:pool.seek_exit"),  # R4, pools -> loops.seek_exit
        ("item:VB.Margin", "stock:VMarg"),  # loops.post
        ("item:hires", "stock:Dur0"),  # loops.pre
    }
    assert expected - found == set()
    assert not any(e.source == "item:fl" for e in edges)  # field paths through helper arguments are kept


def test_nodes_have_kinds_and_section_items_a_module(edges: list[G.GraphEdge]) -> None:
    ns = G.nodes(ROOT, es=edges)
    assert {n.kind for n in ns} == {"param", "table", "stock", "item", "time"}
    assert {n.name for n in ns} == {e.source for e in edges} | {e.target for e in edges}
    targets = {e.target for e in edges if e.target.startswith("item:")}
    assert all(n.module in G.MODULES for n in ns if n.name in targets)


def test_param_families_group_by_trailing_dimension_tokens() -> None:
    fams = G.param_families(["QuitRate_J", "QuitRate_M", "QuitRate_S", "RetireRate_S", "Wage_SI_IN", "Wage_IH", "kR7"])
    assert fams["QuitRate"].members == ("QuitRate_J", "QuitRate_M", "QuitRate_S")
    assert fams["QuitRate"].dims == ("level",)
    assert fams["RetireRate_S"].members == ("RetireRate_S",)  # a family needs two members
    assert fams["Wage"].suffixes["Wage_SI_IN"] == "SI_IN"
    assert fams["kR7"].dims == ()
