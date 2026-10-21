"""The PDF model reference stays in step with its sources (``tools/model_pdf.py``, slice 10c). None of these needs
Edge: the HTML is regenerated and both hashes are checked against ``docs/model/diagrams/MANIFEST.json``."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from tools import model_diagrams as D
from tools import model_pdf as P

ROOT = Path(__file__).resolve().parent.parent
DASHES = (chr(0x2014), chr(0x2013))


@pytest.fixture(scope="module")
def html() -> str:
    return P.build_html(ROOT)


def _sources() -> list[str]:
    return [p.read_bytes().decode("utf-8") for p in P.inputs(ROOT)]


def test_the_html_regenerates_byte_for_byte_and_matches_the_manifest(tmp_path: Path, html: str) -> None:
    first = P.write_html(ROOT, tmp_path / "a").read_bytes()
    second = P.write_html(ROOT, tmp_path / "b").read_bytes()
    assert first == second == html.encode("utf-8")
    assert hashlib.sha256(first).hexdigest() == P.reference_hashes(ROOT)["html"]


def test_the_committed_pdf_matches_the_manifest() -> None:
    pdf = (ROOT / P.PDF_OUT).read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert hashlib.sha256(pdf).hexdigest() == P.reference_hashes(ROOT)["pdf"]


def test_the_html_has_no_dashes_and_no_build_stamp(html: str) -> None:
    """No U+2014 or U+2013, and no date, time or commit-hash pattern that none of the HTML's source files holds (a
    build date or commit would be one)."""
    assert [d for d in DASHES if d in html] == []
    assert P.stamp_problems(html, _sources()) == []


def test_the_stamp_and_dash_checks_fail_on_planted_text(tmp_path: Path, html: str) -> None:
    p = tmp_path / "model-reference.html"
    p.write_bytes(html.encode("utf-8"))
    clean = p.read_bytes().decode("utf-8")
    sources = _sources()
    assert P.stamp_problems(clean, sources) == [] and not any(d in clean for d in DASHES)
    planted_date = "1987-06-05"
    assert not any(planted_date in s for s in sources)  # a date no input holds
    stamped = clean.replace("<p>Generated from", f"<p>{planted_date} Generated from", 1)
    assert P.stamp_problems(stamped, sources) == [planted_date]
    dashed = clean.replace("Generated from", "Generated" + DASHES[0] + "from", 1)
    assert any(d in dashed for d in DASHES)


def test_every_internal_link_has_its_target(html: str) -> None:
    assert re.findall(r'href="#', html)
    assert P.link_problems(html) == []


def test_the_link_check_fails_on_a_planted_dangling_link(tmp_path: Path, html: str) -> None:
    p = tmp_path / "model-reference.html"
    p.write_bytes(html.encode("utf-8"))
    clean = p.read_bytes().decode("utf-8")
    assert P.link_problems(clean) == []
    planted = clean.replace('<nav id="contents">', '<nav id="contents"><a href="#no-such-section">x</a>', 1)
    assert P.link_problems(planted) == ["no-such-section"]


def test_indexed_parameters_point_to_the_inventory(html: str) -> None:
    """The compact parameter table (decision 6): an indexed value reads "per <dimensions>, see inventory.csv"."""
    with (ROOT / P.INVENTORY).open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["kind"] == "parameter"]
    indexed = [r for r in rows if "=" in r["value_phase9"]]
    assert indexed
    for r in indexed:
        assert P.short_value(r, "phase9") == f"per {r['dimensions']}, see inventory.csv", r["name"]
    section = html[html.index('id="dict-parameter"') : html.index('id="dict-table"')]
    assert section.count(", see inventory.csv") == len(indexed)


def test_module_pages_print_at_the_minimum_label_size() -> None:
    """Every module page fits the PDF's diagram area on A4 landscape with its smallest label at 6.5 pt or more."""
    for name, v in D.build_views(ROOT).items():
        if v.kind != "module":
            continue
        w, h = P.svg_size(P.svg_path(ROOT, name))
        assert D.min_font_px(v) * P.print_pt_per_px(w, h, P.fig_h_mm(name)) >= P.MIN_LABEL_PT, name


def test_the_print_size_check_fails_on_a_planted_wide_page(tmp_path: Path) -> None:
    src = P.svg_path(ROOT, "module-work")
    p = tmp_path / "module-work.svg"
    shutil.copyfile(src, p)
    w, h = P.svg_size(p)
    assert 11 * P.print_pt_per_px(w, h) >= P.MIN_LABEL_PT
    text = p.read_bytes().decode("utf-8").replace(f'width="{w:g}px"', f'width="{w * 2:g}px"', 1)
    p.write_bytes(text.encode("utf-8"))
    w2, h2 = P.svg_size(p)
    assert w2 == w * 2
    assert 11 * P.print_pt_per_px(w2, h2) < P.MIN_LABEL_PT


def test_pin_keeps_every_offset_and_fixes_the_dates_and_id() -> None:
    raw = (
        b"%PDF-1.4\n1 0 obj << /CreationDate (D:20261020101112+01'00') /ModDate (D:20261020101113+01'00') >>\n"
        b"trailer << /ID [<0123456789ABCDEF0123456789ABCDEF> <0123456789ABCDEF0123456789ABCDEF>] >>\n%%EOF\n"
    )
    out = P.pin(raw, "f" * 64)
    assert len(out) == len(raw)
    assert b"D:20000101000000+01'00'" in out and b"2026" not in out
    assert b"/ID [<ffffffffffffffffffffffffffffffff> <ffffffffffffffffffffffffffffffff>]" in out
    with pytest.raises(ValueError):
        P.pin(raw.replace(b"(D:20261020101113+01'00')", b"(x)"), "f" * 64)
    no_id = raw.replace(b" /ID [<0123456789ABCDEF0123456789ABCDEF> <0123456789ABCDEF0123456789ABCDEF>]", b"")
    assert P.pin(no_id, "f" * 64) == no_id.replace(b"D:20261020101112", b"D:20000101000000").replace(
        b"D:20261020101113", b"D:20000101000000"
    )


# ---- the model guide (slice 10d) ------------------------------------------------------------------------------------


def test_the_guide_html_regenerates_byte_for_byte_and_matches_the_manifest(tmp_path: Path) -> None:
    first = P.write_guide_html(ROOT, tmp_path / "a").read_bytes()
    second = P.write_guide_html(ROOT, tmp_path / "b").read_bytes()
    assert first == second == P.build_guide_html(ROOT).encode("utf-8")
    assert hashlib.sha256(first).hexdigest() == P.guide_hashes(ROOT)["html"]


def test_the_committed_guide_pdf_matches_the_manifest() -> None:
    pdf = (ROOT / P.GUIDE_PDF_OUT).read_bytes()
    assert pdf.startswith(b"%PDF-")
    assert hashlib.sha256(pdf).hexdigest() == P.guide_hashes(ROOT)["pdf"]


def test_the_stored_pages_are_the_reference_pdfs() -> None:
    pages = P.stored_pages(ROOT)
    assert all(v > 0 for v in pages.values())
    pdf = (ROOT / P.PDF_OUT).read_bytes()
    assert P.page_problems(pages, pdf) == []
    found = P.dest_pages(pdf)
    assert found["intro"] < found["guide"] < found["overview"] < found["module-pages"]


def test_the_page_check_fails_on_a_planted_wrong_page(tmp_path: Path) -> None:
    p = tmp_path / "MANIFEST.json"
    shutil.copyfile(ROOT / D.MANIFEST, p)
    man = json.loads(p.read_text(encoding="utf-8"))
    pdf = (ROOT / P.PDF_OUT).read_bytes()
    assert P.page_problems(man["guide"]["pages"], pdf) == []
    man["guide"]["pages"]["panels"] += 1
    right = man["guide"]["pages"]["panels"] - 1
    assert P.page_problems(man["guide"]["pages"], pdf) == [f"panels: stored page {right + 1}, PDF page {right}"]


def _guide_part(text: str) -> str:
    return text[text.index('<section class="guide"') : text.index('<section id="overview-part">')]


def test_the_guide_prints_at_8_pt_or_larger(html: str) -> None:
    """The guide's tables, code and code blocks print at 8 pt or more: none of its tables takes the 6.8 pt
    ``small`` class, and the guide's own rule sets ``GUIDE_MIN_PT``."""
    assert P.GUIDE_MIN_PT >= 8
    assert f"section.guide table, section.guide code, section.guide pre {{ font-size: {P.GUIDE_MIN_PT:g}pt; }}" in P.CSS
    part = _guide_part(html)
    assert part.count("<table") == 3 and 'class="small"' not in part


def test_the_small_print_check_fails_on_a_planted_small_table(tmp_path: Path, html: str) -> None:
    p = tmp_path / "model-reference.html"
    p.write_bytes(html.encode("utf-8"))
    part = _guide_part(p.read_bytes().decode("utf-8"))
    assert 'class="small"' not in part
    assert 'class="small"' in part.replace("<table>", '<table class="small">', 1)


def test_the_guide_appears_after_the_introduction_with_its_contents_entries(html: str) -> None:
    assert html.index('<section id="intro">') < html.index('<section class="guide"') < html.index("overview-part")
    contents = html[html.index('<nav id="contents">') : html.index("</nav>")]
    assert contents.index('href="#intro"') < contents.index('href="#guide"') < contents.index('href="#overview"')
    assert '<a href="#guide-3-levers">Levers</a>' in contents
