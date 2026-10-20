"""The diagrams stay in step with the model (``tools/model_diagrams.py``, slice 10b). None of these needs draw.io:
the exports are checked against ``docs/model/diagrams/MANIFEST.json``."""

from __future__ import annotations

import itertools
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
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv")),
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
            elif c.kind == "node" and v.kind == "article":
                assert c.items and set(c.items) <= names, (name, c.id)
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
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv")),
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
    for name in D.PANEL_VIEWS:
        for c in views[name].cells:
            if c.kind == "node":
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
        labels = [c.label for c in v.cells if c.kind == "node"]
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
    """No two links' sign labels sit within 6 px of each other, with the sidecar's label offsets (Addendum C)."""
    for name, v in views.items():
        assert D.sign_label_clashes(v, D.read_sidecar(ROOT, name)) == [], name


def test_sign_label_check_fails_on_planted_coincident_labels(tmp_path: Path) -> None:
    for folder, files in (
        (D.DATA, ("model_docs.csv", "model_modules.csv", "model_articles.csv")),
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv")),
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
        (D.MODEL, ("edges.csv", "loops.csv", "loop_summary.csv")),
    ):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
        for name in files:
            shutil.copyfile(ROOT / folder / name, tmp_path / folder / name)
    shutil.copytree(ROOT / D.DIAGRAMS, tmp_path / D.DIAGRAMS)


def test_no_sign_sits_on_a_link_of_opposite_sign(views: dict[str, D.View]) -> None:
    """No sign label lies within 6 px of another link's drawn path when that link carries the opposite sign (slice
    10b.1). The overview's labels are counts, not signs."""
    found = {
        name: D.signs_on_opposite_links(v, D.read_sidecar(ROOT, name))
        for name, v in views.items()
        if name != "overview"
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
    sign label sits within 6 px of it (slice 10b.1)."""
    found = {name: D.limit_marker_problems(v, D.read_sidecar(ROOT, name)) for name, v in views.items()}
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
    geom["e:GCCW>GCCScaleTerm"] = [0.1, 10.0, 0.0, 0.0]  # the capped link's "+" moved onto the marker
    D.write_sidecar(tmp_path, "panel-sourcing", geom)
    found = D.limit_marker_problems(v, D.read_sidecar(tmp_path, "panel-sourcing"))
    assert any(x.startswith("limit:R7Lcap: the sign of e:GCCW>GCCScaleTerm") for x in found), found
