"""The diagrams stay in step with the model (``tools/model_diagrams.py``, slice 10b). None of these needs draw.io:
the exports are checked against ``docs/model/diagrams/MANIFEST.json``."""

from __future__ import annotations

import collections
import itertools
import math
import shutil
from pathlib import Path

import pytest

from tools import model_diagrams as D

ROOT = Path(__file__).resolve().parent.parent
DASHES = (chr(0x2014), chr(0x2013))


@pytest.fixture(scope="module")
def src() -> D.Sources:
    return D.read_sources(ROOT)


@pytest.fixture(scope="module")
def views(src: D.Sources) -> dict[str, D.View]:
    return D.build_views(ROOT, src)


def _names() -> set[str]:
    return {r["name"] for r in D.read_csv(ROOT / D.DATA / "model_docs.csv")}


# ---- 1, 2: regeneration and the manifest ----------------------------------------------------------------------------


def test_every_drawio_regenerates_byte_for_byte(views: dict[str, D.View]) -> None:
    assert set(views) == set(D.VIEWS)
    assert D.stale(ROOT, views) == []


def test_two_generations_are_identical(views: dict[str, D.View]) -> None:
    assert D.generate(ROOT, views) == D.generate(ROOT, D.build_views(ROOT))


def test_manifest_matches_the_sources_and_exports() -> None:
    assert D.manifest_problems(ROOT) == []


def test_check_fails_on_a_copy_with_one_changed_label(tmp_path: Path) -> None:
    for folder, files in (
        (D.DATA, ("model_docs.csv", "model_modules.csv", "model_articles.csv")),
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv", "inventory.csv")),
        (D.PAGES_CSV.parent, (D.PAGES_CSV.name, D.PIPES_CSV.name)),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / folder / name, tmp_path / folder / name)
    shutil.copytree(ROOT / D.DIAGRAMS, tmp_path / D.DIAGRAMS)
    assert D.stale(tmp_path) == []  # the copy is clean before the change
    assert D.manifest_problems(tmp_path) == []
    p = tmp_path / D.DATA / "model_docs.csv"
    text = p.read_bytes().decode("utf-8")
    assert text.count(",GCC work share,") == 1
    p.write_bytes(text.replace(",GCC work share,", ",GCC work share changed,").encode("utf-8"))
    assert "panel-sourcing" in D.stale(tmp_path)
    D.write(tmp_path)
    assert "panel-sourcing.drawio: changed since export" in D.manifest_problems(tmp_path)


# ---- 3: nodes map to items ------------------------------------------------------------------------------------------


def test_every_node_maps_to_model_items(views: dict[str, D.View], src: D.Sources) -> None:
    names = _names()
    modules = {m["module"] for m in src.modules}
    for name, v in views.items():
        for c in v.cells:
            if c.kind == "node" and v.kind == "overview":
                assert c.id in modules, (name, c.id)
            elif (c.kind == "node" and v.kind == "article") or (
                c.kind in ("node", "valve", "cloud") and v.kind == "map"
            ):
                assert c.items and set(c.items) <= names, (name, c.id)
            elif c.kind == "region":
                assert c.id.removeprefix("region:") in modules, (name, c.id)
            elif c.kind in ("node", "valve", "ghost", "ref") and v.kind == "module":
                assert c.items and set(c.items) <= names, (name, c.id)
                assert D.page_item(src, c.id)[0] == c.items[0], (name, c.id)
            elif c.kind == "node":
                ok = (
                    c.id in names
                    or c.id == D.STAFF_ID
                    or (c.id.split("@")[0] in D.ROLE_ITEMS and c.id in D.ROLE_LABELS)
                )
                assert ok and c.items and set(c.items) <= names, (name, c.id)
            elif c.kind == "loop" and v.kind == "panel":
                assert c.id.split(":")[0] in src.summary, (name, c.id)
            elif c.kind == "loop":
                assert c.items and set(c.items) <= set(src.summary), (name, c.id)
            elif c.kind == "limit":
                assert c.items and set(c.items) <= names, (name, c.id)


def test_every_panel_loop_has_its_label(views: dict[str, D.View], src: D.Sources) -> None:
    """Every closed or partial loop is labelled on its panel (a phase 9 term may share its spec loop's label)."""
    for name, spec in D.PANEL_VIEWS.items():
        labels = {c.id.split(":")[0] for c in views[name].cells if c.kind == "loop"}
        for lid, r in src.summary.items():
            if r["panel"] == spec.key and r["status"] in ("closed", "partial"):
                assert D.SHARED_LABELS.get(lid, lid) in labels, (name, lid)


def test_panel_links_carry_one_sign(views: dict[str, D.View]) -> None:
    for name in D.PANEL_VIEWS:
        assert {lk.label for lk in views[name].links} <= {"+", "-"}, name


# ---- 4: loop links are edges ----------------------------------------------------------------------------------------


def test_every_loop_link_is_an_edge(src: D.Sources) -> None:
    edges = {(e["source"], e["target"]) for e in src.edges}
    links = D.signed_links(src)
    assert len(links) == 508
    assert [(r["loop_id"], r["source"], r["target"]) for r in links if (r["source"], r["target"]) not in edges] == []
    assert {r["in_edges_csv"] for r in links} == {"yes"}
    assert {r["loop_id"] for r in src.loops} == set(src.summary)


def _has_cycle(links: set[tuple[str, str]]) -> bool:
    adj: dict[str, list[str]] = {}
    for a, b in links:
        adj.setdefault(a, []).append(b)
    state: dict[str, int] = {}

    def dfs(u: str) -> bool:
        state[u] = 1
        for w in adj.get(u, []):
            if state.get(w) == 1 or (w not in state and dfs(w)):
                return True
        state[u] = 2
        return False

    return any(n not in state and dfs(n) for n in sorted(adj))


def test_every_closed_loop_has_a_cycle_in_its_links(src: D.Sources) -> None:
    closed = [k for k, r in src.summary.items() if r["status"] == "closed"]
    assert len(closed) == 22
    for lid in closed:
        links = {(r["source"], r["target"]) for r in D.signed_links(src) if r["loop_id"] == lid}
        assert _has_cycle(links), lid


# ---- 5: article links are derived ------------------------------------------------------------------------------------


def test_article_links_have_a_signed_path_with_their_sign(src: D.Sources) -> None:
    signs = D.link_signs(src)
    links = [r for r in src.articles if r["part"] == "link"]
    assert len(links) == 46
    for r in links:
        nodes = {n["id"]: D.split_items(n["items"]) for n in src.articles if n["part"] == "node"}
        path, path_signs = r["path"].split(" > "), r["path_signs"].split()
        assert path[0] in nodes[r["source"]] and path[-1] in nodes[r["target"]], r["id"]
        assert D.path_sign(signs, path, path_signs) == r["sign"], r["id"]
        shortest = D.shortest_signed_path(signs, nodes[r["source"]], nodes[r["target"]], r["sign"])
        assert shortest is not None and len(shortest[0]) == len(path), r["id"]


def test_bundled_article_nodes_connect_inside(src: D.Sources) -> None:
    """Where an article loop enters a node at one item and leaves from another, ``loops.csv`` joins them with a +
    path (Addendum A part 6)."""
    assert D.bundle_problems(src) == []


def test_bundle_check_fails_on_a_planted_bundle(tmp_path: Path) -> None:
    for folder, files in (
        (D.DATA, ("model_docs.csv", "model_modules.csv", "model_articles.csv")),
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv", "inventory.csv")),
        (D.PAGES_CSV.parent, (D.PAGES_CSV.name, D.PIPES_CSV.name)),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / folder / name, tmp_path / folder / name)
    assert D.bundle_problems(D.read_sources(tmp_path)) == []
    p = tmp_path / D.DATA / "model_articles.csv"
    text = p.read_bytes().decode("utf-8")
    old = "A5.graduates>A5.unemployment,,,A5.graduates,A5.unemployment,+,Grad > U,+,"
    assert text.count(old) == 1
    text = text.replace(old, "A5.graduates>A5.unemployment,,,A5.graduates,A5.unemployment,+,AC > U,+,")
    p.write_bytes(text.replace("A5.graduates,Graduates,Grad,", "A5.graduates,Graduates,Grad;AC,").encode("utf-8"))
    problems = D.bundle_problems(D.read_sources(tmp_path))
    assert problems and all("A5.graduates entered at Grad, left from AC" in x for x in problems)


def test_article_loops_close_with_their_polarity(src: D.Sources) -> None:
    for art in D.ARTICLES:
        sign = {
            (r["source"], r["target"]): r["sign"] for r in src.articles if r["article"] == art and r["part"] == "link"
        }
        loops = [r for r in src.articles if r["article"] == art and r["part"] == "loop"]
        assert loops, art
        for r in loops:
            ring = r["path"].split(" > ")
            assert ring[0] == ring[-1], r["id"]
            neg = sum(sign[(a, b)] == "-" for a, b in itertools.pairwise(ring))
            assert r["sign"] == ("R" if neg % 2 == 0 else "B"), r["id"]
        for r in (x for x in src.articles if x["article"] == art and x["part"] == "limit"):
            assert (r["source"], r["target"]) in sign, r["id"]


# ---- 6: label limits ------------------------------------------------------------------------------------------------


def test_labels_stay_within_their_limits(views: dict[str, D.View], src: D.Sources) -> None:
    """Panel and module page labels: at most 3 lines of 18 characters (a ghost's or page reference's last line is
    its module or page)."""
    for name in (*D.PANEL_VIEWS, *D.MODULE_VIEWS):
        for c in views[name].cells:
            if c.kind in ("node", "valve", "ghost", "ref"):
                lines = c.label.split("\n")
                assert len(lines) <= 3 and max(len(x) for x in lines) <= 18, (name, c.id, c.label)
    for r in src.articles:
        if r["part"] == "node":
            assert len(r["label"].split()) <= 6, r["id"]
    texts = [c.label for v in views.values() for c in v.cells] + [lk.label for v in views.values() for lk in v.links]
    texts += [x for r in src.articles for x in r.values()]
    assert [t for t in texts if any(d in t for d in DASHES)] == []


def test_no_view_repeats_a_node_label(views: dict[str, D.View]) -> None:
    for name, v in views.items():
        labels = [c.label for c in v.cells if c.kind in ("node", "valve", "ghost", "ref")]
        assert len(labels) == len(set(labels)), name


def test_the_article_rows_are_drafted_or_reviewed(src: D.Sources) -> None:
    assert {r["status"] for r in src.articles} <= {"drafted", "reviewed"}
    assert {r["article"] for r in src.articles} == set(D.ARTICLES)


# ---- 7, 8: sidecars and geometry ------------------------------------------------------------------------------------


def test_sidecars_have_no_orphans_and_no_unplaced_cells(views: dict[str, D.View]) -> None:
    for name, v in views.items():
        geom = D.read_sidecar(ROOT, name)
        assert D.orphans(v, geom) == [], name
        assert D.unplaced(v, geom) == [], name


def test_no_box_overlaps_another_and_every_label_fits(views: dict[str, D.View]) -> None:
    """No two cells overlap: nodes, loop labels, limit markers, the title, legend and captions (Step 5)."""
    for name, v in views.items():
        geom = D.read_sidecar(ROOT, name)
        assert D.overlaps(v, geom) == [], name
        assert D.too_small(v, geom) == [], name


def test_overlap_check_detects_a_planted_overlap(views: dict[str, D.View]) -> None:
    v = views["article-a5"]
    geom = D.read_sidecar(ROOT, "article-a5")
    a, b = sorted(c.id for c in v.cells if c.kind == "node")[:2]
    geom[b] = [geom[a][0] + 5, geom[a][1] + 5, *geom[b][2:]]
    assert (a, b) in D.overlaps(v, geom) or (b, a) in D.overlaps(v, geom)


def test_no_two_sign_labels_coincide(views: dict[str, D.View]) -> None:
    """No two links' sign labels sit within 6 px of each other, with the sidecar's label offsets (Addendum C). Signed
    views only: the module pages are skipped on purpose, as their arrows carry no label (slice 10c), and so is the
    model map, whose labels are counts, checked as boxes by ``map_label_problems`` (slice 10e)."""
    for name, v in views.items():
        if v.kind in ("module", "map"):
            continue
        assert D.sign_label_clashes(v, D.read_sidecar(ROOT, name)) == [], name


def test_sign_label_check_fails_on_planted_coincident_labels(tmp_path: Path) -> None:
    for folder, files in (
        (D.DATA, ("model_docs.csv", "model_modules.csv", "model_articles.csv")),
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv", "inventory.csv")),
        (D.PAGES_CSV.parent, (D.PAGES_CSV.name, D.PIPES_CSV.name)),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / folder / name, tmp_path / folder / name)
    shutil.copytree(ROOT / D.DIAGRAMS, tmp_path / D.DIAGRAMS)
    v = D.build_views(tmp_path)["article-a5"]
    assert D.sign_label_clashes(v, D.read_sidecar(tmp_path, "article-a5")) == []
    geom = D.read_sidecar(tmp_path, "article-a5")
    geom["A5.pipeline"] = list(geom["A5.unemployment"])  # the pipeline -> graduates link now lies on
    geom["A5.graduates"] = list(geom["A5.seen"])  # unemployment -> seen, so their signs coincide
    D.write_sidecar(tmp_path, "article-a5", geom)
    clashes = D.sign_label_clashes(v, D.read_sidecar(tmp_path, "article-a5"))
    assert ("e:A5.pipeline>A5.graduates", "e:A5.unemployment>A5.seen") in clashes


def _copy_inputs(tmp_path: Path) -> None:
    for folder, files in (
        (D.DATA, ("model_docs.csv", "model_modules.csv", "model_articles.csv")),
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv", "inventory.csv")),
        (D.PAGES_CSV.parent, (D.PAGES_CSV.name, D.PIPES_CSV.name)),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / folder / name, tmp_path / folder / name)
    shutil.copytree(ROOT / D.DIAGRAMS, tmp_path / D.DIAGRAMS)


def test_no_sign_sits_on_a_link_of_opposite_sign(views: dict[str, D.View]) -> None:
    """No sign label lies within 6 px of another link's drawn path when that link carries the opposite sign (slice
    10b.1). Signed views only: the overview's labels are counts, not signs, and the module pages are skipped on
    purpose, as their arrows carry no sign (slice 10c), and so is the model map, whose labels are counts (slice 10e)."""
    found = {
        name: D.signs_on_opposite_links(v, D.read_sidecar(ROOT, name))
        for name, v in views.items()
        if name != "overview" and v.kind not in ("module", "map")
    }
    assert {k: v for k, v in found.items() if v} == {}


def test_opposite_sign_check_fails_on_a_planted_sign(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    v = D.build_views(tmp_path)["panel-demand"]
    assert D.signs_on_opposite_links(v, D.read_sidecar(tmp_path, "panel-demand")) == []
    geom = D.read_sidecar(tmp_path, "panel-demand")
    del geom["e:LOB>SeatsB"]  # its "+" goes back to the middle, on the crossing with AC -> LOB target ("-")
    D.write_sidecar(tmp_path, "panel-demand", geom)
    found = D.signs_on_opposite_links(v, D.read_sidecar(tmp_path, "panel-demand"))
    assert ("e:LOB>SeatsB", "e:AC>cons.LOBTarget") in found


def test_each_limit_marker_sits_nearest_a_link_it_caps(views: dict[str, D.View]) -> None:
    """Each limit marker is at least 5 px nearer a link it caps than any link it does not, on the drawn paths, and no
    sign label sits within 6 px of it (slice 10b.1). Signed views only: the module pages are skipped on purpose, as
    they have no limit markers and no signs (slice 10c), and so is the model map (slice 10e)."""
    found = {
        name: D.limit_marker_problems(v, D.read_sidecar(ROOT, name))
        for name, v in views.items()
        if v.kind not in ("module", "map")
    }
    assert {k: v for k, v in found.items() if v} == {}


def test_limit_marker_check_fails_on_a_planted_marker(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    v = D.build_views(tmp_path)["panel-sourcing"]
    clean = D.read_sidecar(tmp_path, "panel-sourcing")
    assert D.limit_marker_problems(v, clean) == []
    geom = dict(clean)
    geom["limit:R7Lcap"] = [880.0, 257.0, 160.0, 26.0]  # main's place, midway between two vertical links
    D.write_sidecar(tmp_path, "panel-sourcing", geom)
    found = D.limit_marker_problems(v, D.read_sidecar(tmp_path, "panel-sourcing"))
    assert any(x.startswith("limit:R7Lcap: capped link at") for x in found), found
    geom = dict(clean)
    # the capped link's "+" moved onto the marker (slice 10e: offsets run to draw.io's side, so -10, not +10)
    geom["e:GCCW>GCCScaleTerm"] = [0.1, -10.0, 0.0, 0.0]
    D.write_sidecar(tmp_path, "panel-sourcing", geom)
    found = D.limit_marker_problems(v, D.read_sidecar(tmp_path, "panel-sourcing"))
    assert any(x.startswith("limit:R7Lcap: the sign of e:GCCW>GCCScaleTerm") for x in found), found


# ---- 10c: the module pages ------------------------------------------------------------------------------------------


def _page_cells(root: Path, name: str) -> list[D.DrawnCell]:
    return D.read_drawio_cells(D.drawio_path(root, name))


def test_every_module_item_is_on_exactly_one_page_of_its_module(src: D.Sources) -> None:
    """Each item a module page draws (``model_docs.csv``'s module) is drawn on exactly one page of its module, as a
    node of that page, never twice (slice 10c)."""
    items = D.module_items(src)
    assign = D.page_assignment(src)
    assert sorted(it for its in assign.values() for it in its) == sorted(items)
    drawn: dict[D.Item, list[str]] = {}
    for name, spec in D.MODULE_VIEWS.items():
        for c in _page_cells(ROOT, name):
            if not c.is_item():
                continue
            it = D.page_item(src, c.id)
            assert items[it] in spec.modules, (name, c.id)
            drawn.setdefault(it, []).append(name)
    assert {it: ps for it, ps in drawn.items() if len(ps) != 1} == {}
    assert sorted(drawn) == sorted(items)


def test_the_page_table_fails_on_a_planted_duplicate_or_missing_item(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    p = tmp_path / D.PAGES_CSV
    D.page_assignment(D.read_sources(tmp_path))  # the copy is clean before the plant
    text = p.read_bytes().decode("utf-8")
    assert text.count("\nfinance-b,VF.PNew,auxiliary\n") == 1
    p.write_bytes((text + "finance-c,VF.PNew,auxiliary\n").encode("utf-8"))
    with pytest.raises(ValueError, match=r"VF\.PNew \(auxiliary\) assigned twice"):
        D.page_assignment(D.read_sources(tmp_path))
    p.write_bytes(text.replace("finance-b,VF.PNew,auxiliary\n", "").encode("utf-8"))
    with pytest.raises(ValueError, match=r"VF\.PNew \(auxiliary\) unassigned"):
        D.page_assignment(D.read_sources(tmp_path))


def test_ghosts_and_page_references_are_inputs_from_where_they_say(src: D.Sources) -> None:
    """A ghost is an item of another module with an edge into the page; a page reference an item of the same module,
    assigned to a different page, with an edge into the page (slice 10c)."""
    found = {name: D.reference_problems(src, name, _page_cells(ROOT, name)) for name in D.MODULE_VIEWS}
    assert {k: v for k, v in found.items() if v} == {}


def test_the_reference_checks_fail_on_planted_cells(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    src = D.read_sources(tmp_path)
    path = D.drawio_path(tmp_path, "module-finance-b")
    clean = path.read_bytes().decode("utf-8")
    assert D.reference_problems(src, "module-finance-b", D.read_drawio_cells(path)) == []
    plants = {
        "ref:VF.PNew": "on this page",  # a reference to an item drawn on the same page
        "ref:RevenueTot": "no edge into the page",  # an item of a sibling page that feeds nothing here
        "ghost:VF.Book": "not of another module",  # a ghost of the page's own module
    }
    for cid, why in plants.items():
        cell = (
            f'<mxCell id="{cid}" value="x" style="text;" vertex="1" parent="1">'
            '<mxGeometry x="0" y="0" width="9" height="9" as="geometry"/></mxCell>'
        )
        path.write_bytes(clean.replace("</root>", cell + "</root>", 1).encode("utf-8"))
        problems = D.reference_problems(src, "module-finance-b", D.read_drawio_cells(path))
        assert any(cid in x and why in x for x in problems), (cid, problems)


def test_no_edge_on_a_module_page_carries_a_sign() -> None:
    """Module pages show dependence only: no arrow has a label (decision 2)."""
    found = {name: D.sign_problems(_page_cells(ROOT, name)) for name in D.MODULE_VIEWS}
    assert {k: v for k, v in found.items() if v} == {}


def test_the_sign_check_fails_on_a_planted_sign(tmp_path: Path) -> None:
    p = tmp_path / "module-work.drawio"
    shutil.copyfile(D.drawio_path(ROOT, "module-work"), p)
    clean = p.read_bytes().decode("utf-8")
    assert D.sign_problems(D.read_drawio_cells(p)) == []
    i = clean.index('value="" style="html=0;endArrow')
    p.write_bytes((clean[:i] + 'value="+"' + clean[i + len('value=""') :]).encode("utf-8"))
    assert len(D.sign_problems(D.read_drawio_cells(p))) == 1


def test_every_valve_sits_with_its_stock(src: D.Sources) -> None:
    """Each goal-seeking or coflow stock on a page has exactly one valve and exactly one arrow into its box, the pipe
    from that valve, so no input of its update points at the stock; no valve lacks its stock (slice 10c)."""
    found = {name: D.valve_problems(src, _page_cells(ROOT, name)) for name in D.MODULE_VIEWS}
    assert {k: v for k, v in found.items() if v} == {}
    kinds = D.valve_stocks(src)
    assert sum(k == "goal-seeking" for k in kinds.values()) == 20
    assert sorted(s for s, k in kinds.items() if k == "coflow") == ["NewD", "NewP"]


def test_the_valve_check_fails_on_planted_cells(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    src = D.read_sources(tmp_path)
    path = D.drawio_path(tmp_path, "module-finance-c")
    clean = path.read_bytes().decode("utf-8")
    assert D.valve_problems(src, D.read_drawio_cells(path)) == []
    i = clean.index('<mxCell id="flow:Viab"')
    j = clean.index("</mxCell>", i) + len("</mxCell>")
    path.write_bytes((clean[:i] + clean[j:]).encode("utf-8"))  # the valve removed
    assert any("Viab" in x and "valve" in x for x in D.valve_problems(src, D.read_drawio_cells(path)))
    k = clean.index('target="flow:Viab"')
    path.write_bytes((clean[:k] + 'target="Viab"' + clean[k + len('target="flow:Viab"') :]).encode("utf-8"))
    assert any("Viab" in x and "arrows into" in x for x in D.valve_problems(src, D.read_drawio_cells(path)))


# ---- 10e: arrows through boxes on their drawn paths, every view -----------------------------------------------------


def test_no_drawn_arrow_passes_through_a_box(views: dict[str, D.View]) -> None:
    """No link's drawn path (``link_paths``, with its two-way waypoints) crosses a box it does not connect, in any
    view, with ``through_boxes``'s 2 px inset (slice 10e, step 5)."""
    found = {name: D.drawn_through_boxes(v, D.read_sidecar(ROOT, name)) for name, v in views.items()}
    assert {k: v for k, v in found.items() if v} == {}


def test_the_drawn_path_check_fails_on_a_planted_box(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    v = D.build_views(tmp_path)["module-work"]
    geom = D.read_sidecar(tmp_path, "module-work")
    assert D.drawn_through_boxes(v, geom) == []  # the copy is clean before the plant
    lk = v.links[0]
    (ax, ay), (bx, by) = D.link_paths(v, geom)[D.edge_id(lk)][:2]
    other = next(c.id for c in v.cells if c.id not in (lk.source, lk.target) and c.kind == "node")
    w, h = geom[other][2:4]
    geom[other] = [(ax + bx) / 2 - w / 2, (ay + by) / 2 - h / 2, w, h]  # a box on the drawn segment's midpoint
    D.write_sidecar(tmp_path, "module-work", geom)
    assert (D.edge_id(lk), other) in D.drawn_through_boxes(v, D.read_sidecar(tmp_path, "module-work"))


# ---- 10e: the model map ---------------------------------------------------------------------------------------------

MAP = D.MAP_VIEWS[0]
SCALAR = Path("src/aisim/scalar")


def _map_cells(root: Path) -> list[D.DrawnCell]:
    return D.read_drawio_cells(D.drawio_path(root, MAP))


def _length(path: list[tuple[float, float]]) -> float:
    return sum(math.dist(p, q) for p, q in itertools.pairwise(path))


def _without(text: str, cid: str) -> str:
    """A .drawio text without the cell ``cid`` (its id as the XML writes it, ``>`` escaped)."""
    i = text.index(f'<mxCell id="{cid.replace(">", "&gt;")}"')
    j = text.index("</mxCell>", i) + len("</mxCell>")
    return text[:i] + text[j:]


def test_the_map_holds_every_stock_valve_lever_and_cloud_once(src: D.Sources, views: dict[str, D.View]) -> None:
    """Every stock, every flow's valve and every lever exactly once, the clouds ``tools/flow_pipes.csv`` implies and
    the eight regions, and nothing else but the title, legend and captions (slice 10e, step 4.1). A within-Headcount
    valve stands for its group's flows, so every flow is on exactly one valve."""
    assert D.map_contents_problems(src, _map_cells(ROOT)) == []
    cells = views[MAP].cells
    kinds = collections.Counter(c.kind for c in cells)
    stocks = [n for n, k in src.docs if k == "stock"]
    flows = sorted(n for n, k in src.docs if k == "flow")
    assert len(stocks) == 43 and len(flows) == 60 and len(src.levers) == 31
    assert kinds["valve"] == 58 and kinds["cloud"] == 42 and kinds["region"] == 8
    assert kinds["node"] == len(stocks) + len(src.levers)
    assert sorted(f for c in cells if c.kind == "valve" for f in c.items) == flows


def test_the_map_contents_check_fails_on_planted_cells(tmp_path: Path, src: D.Sources) -> None:
    p = tmp_path / "model-map.drawio"
    shutil.copyfile(D.drawio_path(ROOT, MAP), p)
    clean = p.read_bytes().decode("utf-8")
    assert D.map_contents_problems(src, D.read_drawio_cells(p)) == []
    p.write_bytes(_without(clean, "cloud:Enrol").encode("utf-8"))  # a cloud the table implies, removed
    assert "cloud:Enrol: drawn 0 times" in D.map_contents_problems(src, D.read_drawio_cells(p))
    i = clean.index('<mxCell id="BL"')
    j = clean.index("</mxCell>", i) + len("</mxCell>")
    p.write_bytes((clean[:j] + clean[i:j] + clean[j:]).encode("utf-8"))  # a stock drawn twice
    assert "BL: drawn 2 times" in D.map_contents_problems(src, D.read_drawio_cells(p))
    extra = '<mxCell id="cons.LOBTarget" value="x" style="text;" vertex="1" parent="1"></mxCell>'
    p.write_bytes(clean.replace("</root>", extra + "</root>", 1).encode("utf-8"))  # an auxiliary
    assert any(x.startswith("cons.LOBTarget: not a") for x in D.map_contents_problems(src, D.read_drawio_cells(p)))


def test_the_pipe_table_is_derived_from_the_integration_code(src: D.Sources) -> None:
    """``tools/flow_pipes.csv`` has one row per flow with known stocks; every cite's lines name the flow's code
    identifier, lie in an update of the cited stock and carry the row's direction; and every term of every stock
    update names a flow whose row has that stock on the term's side (slice 10e, step 4.2)."""
    assert sorted(D.pipe_rows(src)) == sorted(n for n, k in src.docs if k == "flow")
    assert D.cite_problems(ROOT, src) == []
    assert D.code_flow_problems(ROOT, src) == []


def test_the_pipe_checks_fail_on_planted_rows(tmp_path: Path) -> None:
    _copy_inputs(tmp_path)
    (tmp_path / SCALAR).mkdir(parents=True)
    for name in ("integrate.py", "loops.py"):
        shutil.copyfile(ROOT / SCALAR / name, tmp_path / SCALAR / name)
    p = tmp_path / D.PIPES_CSV
    clean = p.read_bytes().decode("utf-8")
    src = D.read_sources(tmp_path)
    assert D.cite_problems(tmp_path, src) == [] and D.code_flow_problems(tmp_path, src) == []
    row = "\nComp,BL,cloud,,src/aisim/scalar/integrate.py:37 (BL)\n"
    assert clean.count(row) == 1
    p.write_bytes(clean.replace(row, "\nComp,cloud,BL,,src/aisim/scalar/integrate.py:37 (BL)\n").encode("utf-8"))
    src = D.read_sources(tmp_path)  # a wrong direction: completion fills the backlog
    assert any(x.startswith("Comp: takes from BL") for x in D.code_flow_problems(tmp_path, src))
    assert any(x.startswith("Comp: its term in BL") for x in D.cite_problems(tmp_path, src))
    p.write_bytes(clean.replace(row, "\nComp,BL,cloud,,src/aisim/scalar/integrate.py:38 (BL)\n").encode("utf-8"))
    src = D.read_sources(tmp_path)  # a wrong cite line
    assert "Comp: src/aisim/scalar/integrate.py:(38,) does not name 'Comp'" in D.cite_problems(tmp_path, src)
    p.write_bytes(clean.replace(row, "\n").encode("utf-8"))  # a missing row
    with pytest.raises(ValueError, match="Comp: no row"):
        D.pipe_rows(D.read_sources(tmp_path))


def test_the_map_pipes_and_drains_follow_the_table(src: D.Sources) -> None:
    """Each flow's pipes from its sources (or its cloud) into its valve and on to its sinks, each within-Headcount
    valve's attachment to Headcount with no pipe, and each also-drains arrow, exactly as ``tools/flow_pipes.csv``
    says; no other edge style (operator rulings, slice 10e)."""
    assert D.pipe_problems(src, _map_cells(ROOT)) == []
    kinds = D.map_link_kinds(_map_cells(ROOT))
    assert sorted(kinds["attach"]) == [("conv", "H"), ("promo", "H"), ("sw.in", "H")]
    assert sorted(kinds["drain"]) == [("hires", "V"), ("promo", "V"), ("sw.in", "V")]


def test_the_pipe_check_fails_on_a_planted_pipe(tmp_path: Path, src: D.Sources) -> None:
    p = tmp_path / "model-map.drawio"
    shutil.copyfile(D.drawio_path(ROOT, MAP), p)
    clean = p.read_bytes().decode("utf-8")
    assert D.pipe_problems(src, D.read_drawio_cells(p)) == []
    old = 'source="hires" target="O"'
    assert clean.count(old) == 1
    p.write_bytes(clean.replace(old, 'source="hires" target="H"').encode("utf-8"))  # hires into Headcount
    problems = D.pipe_problems(src, D.read_drawio_cells(p))
    assert "pipe-out hires -> O: missing" in problems and "pipe-out hires -> H: not in the pipe table" in problems


def test_lever_arrows_follow_the_rulings(src: D.Sources) -> None:
    """A lever with at most four targets points at each; a wider one has one labelled arrow to each other module it
    reaches and its own-module count on its label (operator rulings, slice 10e, step 4.3): 42 + 32 = 74 arrows."""
    assert D.lever_arrow_problems(src, _map_cells(ROOT)) == []
    arrows, own = D.lever_arrows(src)
    assert (len(arrows), sum(not lab for _, _, lab in arrows)) == (74, 42)
    assert own == {"AICostDecline": 4, "AIShockEnd": 4, "AIShockMult": 4, "AIShockStart": 4, "aL_max": 5}
    assert all(len(t) > 0 for t in D.lever_targets(src).values())


def test_the_lever_arrow_check_fails_on_planted_arrows(tmp_path: Path, src: D.Sources) -> None:
    p = tmp_path / "model-map.drawio"
    shutil.copyfile(D.drawio_path(ROOT, MAP), p)
    clean = p.read_bytes().decode("utf-8")
    assert D.lever_arrow_problems(src, D.read_drawio_cells(p)) == []
    p.write_bytes(_without(clean, "e:kR7>flow:SrcPerc").encode("utf-8"))  # a narrow lever's arrow removed
    assert "lever kR7 -> flow:SrcPerc: missing" in D.lever_arrow_problems(src, D.read_drawio_cells(p))
    assert clean.count('value="g, 7"') == 1
    p.write_bytes(clean.replace('value="g, 7"', 'value="g, 6"').encode("utf-8"))  # a wrong region count
    found = D.lever_arrow_problems(src, D.read_drawio_cells(p))
    assert any(x.startswith("region arrow g -> region:consumer") for x in found)
    p.write_bytes(clean.replace("(acts on 4 in", "(acts on 3 in", 1).encode("utf-8"))  # a wrong own-module count
    assert any("label counts [3]" in x for x in D.lever_arrow_problems(src, D.read_drawio_cells(p)))


def test_every_map_node_sits_in_its_module_region(src: D.Sources, views: dict[str, D.View]) -> None:
    """Every stock, valve, cloud and lever lies wholly inside its module's region, and no two regions overlap (slice
    10e, step 4.4)."""
    assert D.region_problems(src, views[MAP], D.read_sidecar(ROOT, MAP)) == []


def test_the_region_check_fails_on_planted_moves(src: D.Sources, views: dict[str, D.View]) -> None:
    geom = D.read_sidecar(ROOT, MAP)
    assert D.region_problems(src, views[MAP], geom) == []
    moved = dict(geom)
    r = geom["region:finance"]
    moved["BL"] = [r[0] + 40, r[1] + 60, *geom["BL"][2:]]  # the backlog inside the finance region
    assert "BL: outside region:work" in D.region_problems(src, views[MAP], moved)
    grown = dict(geom)
    w = geom["region:work"]
    grown["region:work"] = [w[0], w[1], w[2] + 60, w[3]]  # the work region over the workforce region
    assert "region:work overlaps region:workforce" in D.region_problems(src, views[MAP], grown)


def test_no_lever_arrow_runs_along_a_pipe_and_no_label_clashes(views: dict[str, D.View]) -> None:
    """Lever arrows may cross pipes but never run along one, and the region-arrow labels overlap no other label, box
    or pipe (slice 10e criteria)."""
    geom = D.read_sidecar(ROOT, MAP)
    assert D.runs_along(views[MAP], geom) == []
    assert D.map_label_problems(views[MAP], geom) == []


def test_the_run_along_and_label_checks_fail_on_planted_geometry(views: dict[str, D.View]) -> None:
    v = views[MAP]
    geom = D.read_sidecar(ROOT, MAP)
    assert D.runs_along(v, geom) == [] and D.map_label_problems(v, geom) == []
    paths = D.link_paths(v, geom)
    pipe = max((lk for lk in v.links if lk.style in D.PIPE_STYLES), key=lambda lk: _length(paths[D.edge_id(lk)]))
    (sx, sy), (tx, ty) = paths[D.edge_id(pipe)][0], paths[D.edge_id(pipe)][-1]
    w, h = geom["kR7"][2:4]
    planted = dict(geom)
    planted["kR7"] = [2 * sx - tx - w / 2, 2 * sy - ty - h / 2, w, h]  # kR7 on the line of the longest pipe
    arrow = D.Link("kR7", pipe.target, "", D.LEVER_STYLE)  # an arrow from kR7 along that pipe to its end
    along = D.View(v.name, v.kind, v.cells, (pipe, arrow))
    assert D.runs_along(along, planted) == [f"e:kR7>{pipe.target} runs along a pipe"]
    e, box = sorted(D.label_boxes(v, geom).items())[0]
    covered = dict(geom)
    covered["TMBrake"] = [box[0], box[1], *geom["TMBrake"][2:]]  # a lever under a label
    assert f"{e}: label on TMBrake" in D.map_label_problems(v, covered)


def test_within_headcount_valves_conserve() -> None:
    """Each two-flow ``WITHIN`` group moves staff between members of Headcount: its flows are equal in total, summed
    over units and levels, at every step of a phase9 Base run (operator ruling, slice 10e). Control: promotions
    against quits do not conserve."""
    from aisim.dims import LEVELS, UNITS
    from aisim.params import Params
    from aisim.scalar.engine import run
    from aisim.scalar.labour_market import Exits, Switching
    from aisim.scalar.workforce import Vacancies

    seen: dict[int, tuple[Vacancies, Switching, Exits]] = {}
    parts: dict[str, object] = {}

    def trace(step: int, y: float, sec: str, obj: object) -> None:
        parts[sec] = obj
        if sec == "S8c":
            vac, sw, ex = parts["S7"], parts["S8a"], parts["S8c"]
            assert isinstance(vac, Vacancies) and isinstance(sw, Switching) and isinstance(ex, Exits)
            seen[step] = (vac, sw, ex)

    run(Params.baseline("phase9"), trace=trace)

    def total(s: tuple[Vacancies, Switching, Exits], flow: str) -> float:
        vac, sw, ex = s
        if flow == "promo":
            return sum(vac.promo[u][lv] for u in UNITS for lv in LEVELS)
        if flow == "sw.in":
            return sum(sw.sw[u][lv]["in"] for u in UNITS for lv in LEVELS)
        if flow == "sw.out":
            return sum(sw.sw[u][lv]["out"] for u in UNITS for lv in LEVELS)
        if flow == "fl.promo_out":
            return sum(ex.fl[u][lv]["promo_out"] for u in UNITS for lv in LEVELS)
        assert flow == "fl.quits"  # the control
        return sum(ex.fl[u][lv]["quits"] for u in UNITS for lv in LEVELS)

    def worst(a: str, b: str) -> float:
        return max(abs(total(s, a) - total(s, b)) / max(1.0, abs(total(s, a))) for s in seen.values())

    pairs = [flows for flows, _ in D.WITHIN.values() if len(flows) == 2]
    assert sorted(pairs) == [("promo", "fl.promo_out"), ("sw.in", "sw.out")]
    assert len(seen) == 257
    for a, b in pairs:
        assert worst(a, b) < 1e-12, (a, b)
    assert worst("promo", "fl.quits") > 1e-3
