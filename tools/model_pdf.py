"""The PDF model reference: one HTML page generated from the committed rows, printed with headless Edge (slice 10c).

The HTML is a pure function of the committed files it reads (``inputs()``): the inventory, the loop inventory, the
module and page tables, the spec errata, the exported SVGs and ``pyproject.toml``. It carries no build date and no
commit hash, so two generations are byte-identical. Edge prints it locally; the PDF's dates and ``/ID`` are then
replaced by fixed values of the same byte length (``pin()``), so two prints are byte-identical too. The manifest
(``docs/model/diagrams/MANIFEST.json``, key ``reference``) records the SHA-256 of the HTML and of the pinned PDF; CI
regenerates the HTML and checks both hashes without Edge.

Order (recon 10b E2): title page, contents, introduction, the model guide (slice 10d), overview, the module pages
each with its item list, the causal-loop panels and the loop table, the data dictionary (parameters and tables in a
compact layout), the spec errata, and an appendix with the per-link loop table and the name clashes.

The model guide (slice 10d) is rendered from the committed ``docs/model-guide.md`` (``tools/model_guide.py`` writes
it), so this tool still runs no model code. It prints twice: as a section of the reference and on its own as
``docs/model-guide.pdf``. Its "Where to look next" lines carry the reference PDF's page numbers. They are read from the
printed PDF's named destinations (``dest_pages()``), reprinted until they settle, and stored in the manifest (key
``guide``, with the guide's HTML and PDF hashes), so CI regenerates both HTMLs without Edge.

Usage: ``uv run --frozen python tools/model_pdf.py --html`` (writes ``docs/_build/model-reference.html`` and
``docs/_build/model-guide.html``), ``--pdf`` (writes the HTML, prints it with Edge, pins it, writes
``docs/model-reference.pdf``, ``docs/model-guide.pdf`` and the manifest's hashes and pages; local only) or ``--check``
(exit 1 if an HTML or a committed PDF differs from the manifest, or the stored pages from the reference PDF's).
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import html
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import model_diagrams as DG

ROOT: Final = Path(__file__).resolve().parent.parent
HTML_OUT: Final = Path("docs/_build/model-reference.html")
PDF_OUT: Final = Path("docs/model-reference.pdf")
INVENTORY: Final = DG.MODEL / "inventory.csv"
ERRATA: Final = Path("docs/spec-errata.md")
STATE_PY: Final = Path("src/aisim/state.py")
GUIDE_MD: Final = Path("docs/model-guide.md")
GUIDE_OUTPUTS: Final = Path("tools/guide_outputs.csv")
GUIDE_HTML_OUT: Final = Path("docs/_build/model-guide.html")
GUIDE_PDF_OUT: Final = Path("docs/model-guide.pdf")
MAP_HTML_OUT: Final = Path("docs/_build/model-map.html")
MAP_PDF_OUT: Final = Path("docs/model-map.pdf")
EDGE_EXE: Final = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")

PAGE_W_MM: Final = 297.0
PAGE_H_MM: Final = 210.0
MARGIN_MM: Final = 10.0
FIG_W_MM: Final = PAGE_W_MM - 2 * MARGIN_MM
FIG_H_MM: Final = 176.0
"""A diagram page: the SVG is scaled to fit FIG_W_MM x FIG_H_MM, leaving room for a one-line caption."""
HEADING_MM: Final = 12.0
"""The first diagram of a part carries the part's heading on its page, and is that much shorter."""
FIRST_FIGURES: Final = frozenset({"overview", next(iter(DG.MODULE_VIEWS)), next(iter(DG.PANEL_VIEWS))})
PT_PER_MM: Final = 72 / 25.4
MIN_LABEL_PT: Final = 6.5
MAP_PAGE_W_MM: Final = 594.0
MAP_PAGE_H_MM: Final = 420.0
MAP_FIG_W_MM: Final = MAP_PAGE_W_MM - 2 * MARGIN_MM
MAP_FIG_H_MM: Final = 374.0
"""The model map's page (slice 10e): A2 landscape, the named page ``map``. Its size is given in mm because Edge 155
ignores the ``A2 landscape`` keyword on a named page. The figure leaves room for the heading and a caption."""
MAP_MIN_LABEL_PT: Final = 7.0
EDGE_TIMEOUT_S: Final = 300
"""Edge is stopped after this many seconds (slice 10e: the 10d re-verify saw it hang after writing its PDF)."""
PIN_DATE: Final = b"20000101000000"
KINDS: Final = ("stock", "flow", "auxiliary", "parameter", "table", "output")
SECTION_TITLES: Final = {
    "stock": "Stocks",
    "flow": "Flows",
    "auxiliary": "Auxiliaries",
    "parameter": "Parameters",
    "table": "Tables",
    "output": "Outputs",
}
LOOP_RULING: Final = re.compile(r"\bE\d+\b")
GUIDE_MIN_PT: Final = 8.0
"""The guide's smallest text in print: its tables, code and code blocks (slice 10d: 8 pt or larger at A4)."""
GUIDE_WIDTHS: Final[Mapping[tuple[str, ...], tuple[float, ...]]] = {
    ("Scenario", "What it changes", "What it represents"): (17, 41, 42),
    (
        "Lever",
        "What it is",
        "Units",
        "Base value",
        "Scenarios that move it",
        "Sensitivity range (tornado_levers)",
        "At year Y",
    ): (13, 30, 8, 11, 15, 13, 10),
    ("Output", "Units", "What it tells you", "phase9 Base 2024", "phase9 Base 2040"): (19, 8, 23, 25, 25),
    ("Lever", "Targets", "Where it acts"): (13, 7, 80),
}
"""The guide's tables by header row: their column widths (percent). A guide table without an entry raises."""
GUIDE_PAGES: Final[Mapping[str, tuple[str, str]]] = {
    "Model map": ("model-map", "module-pages"),
    "Module pages": ("module-pages", "panels"),
    "Feedback loops": ("panels", "dictionary"),
    "Data dictionary": ("dictionary", "errata-title"),
}
"""The guide's "Where to look next" lines that point into the reference PDF: the anchor of the part's first page and
of the next part's, whose page less one is the part's last."""
PAGE_ANCHORS: Final = tuple(dict.fromkeys(a for pair in GUIDE_PAGES.values() for a in pair))

CSS: Final = f"""@page {{ size: A4 landscape; margin: {MARGIN_MM:g}mm; }}
html {{ font-family: Helvetica, Arial, sans-serif; font-size: 8pt; color: #1A1A1A; }}
body {{ margin: 0; }}
h1 {{ font-size: 16pt; margin: 0 0 4mm; break-before: page; break-after: avoid; }}
h2 {{ font-size: 12pt; margin: 4mm 0 2mm; break-after: avoid; }}
h3 {{ font-size: 10pt; margin: 3mm 0 1.5mm; break-after: avoid; }}
p, li {{ line-height: 1.35; }}
a {{ color: #0B4F8A; text-decoration: none; }}
code {{ font-family: Consolas, Menlo, monospace; font-size: 7.2pt; }}
table {{ border-collapse: collapse; width: 100%; table-layout: fixed; margin: 1mm 0 3mm; }}
th, td {{ border: 0.4pt solid #9A9A9A; padding: 1.2pt 2.5pt; vertical-align: top; text-align: left;
  overflow-wrap: anywhere; }}
th {{ background: #ECECEC; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
table.small {{ font-size: 6.8pt; }}
section.title {{ height: {PAGE_H_MM - 2 * MARGIN_MM - 1:g}mm; display: flex; flex-direction: column;
  justify-content: center; }}
section.title h1 {{ font-size: 28pt; break-before: auto; }}
section.title p.sub {{ font-size: 16pt; margin: 0 0 8mm; }}
section.title table {{ width: 120mm; font-size: 10pt; }}
section.figure {{ break-before: page; break-after: page; break-inside: avoid; }}
svg.diagram {{ display: block; width: {FIG_W_MM:g}mm; height: {FIG_H_MM:g}mm; }}
svg.diagram.headed {{ height: {FIG_H_MM - HEADING_MM:g}mm; }}
@page map {{ size: {MAP_PAGE_W_MM:g}mm {MAP_PAGE_H_MM:g}mm; margin: {MARGIN_MM:g}mm; }}
section.map {{ page: map; }}
svg.map {{ display: block; width: {MAP_FIG_W_MM:g}mm; height: {MAP_FIG_H_MM:g}mm; }}
section.figure h1 {{ break-before: auto; }}
p.caption {{ font-size: 8pt; font-style: italic; margin: 1.5mm 0 0; }}
nav ol {{ margin: 0; }}
nav li {{ margin: 0.4mm 0; }}
dl.marks dt {{ font-weight: bold; margin-top: 1.5mm; }}
dl.marks dd {{ margin-left: 6mm; }}
section.guide table, section.guide code, section.guide pre {{ font-size: {GUIDE_MIN_PT:g}pt; }}
section.guide pre {{ background: #F4F4F4; padding: 1.5mm 2.5mm; margin: 1mm 0 3mm; white-space: pre-wrap;
  break-inside: avoid; }}
section.guide p.sub {{ font-size: 10pt; margin: 0 0 3mm; }}
section.guide ul {{ break-inside: avoid; }}
"""


# ---- reading --------------------------------------------------------------------------------------------------------


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as f:
        return str(tomllib.load(f)["project"]["version"])


def default_model(root: Path) -> str:
    """``aisim.state.DEFAULT_MODEL``, read from the source so that this tool imports no model code."""
    tree = ast.parse((root / STATE_PY).read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "DEFAULT_MODEL"
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    raise ValueError(f"no DEFAULT_MODEL in {STATE_PY.as_posix()}")


def svg_path(root: Path, view: str) -> Path:
    return DG.export_paths(root, view)["svg"]


def inputs(root: Path = ROOT) -> list[Path]:
    """Every file the HTML is built from."""
    out = [
        root / "pyproject.toml",
        root / STATE_PY,
        root / INVENTORY,
        root / DG.DATA / "model_docs.csv",
        root / DG.DATA / "model_modules.csv",
        root / DG.DATA / "model_articles.csv",
        root / DG.MODEL / "edges.csv",
        root / DG.MODEL / "loops.csv",
        root / DG.MODEL / "loop_summary.csv",
        root / DG.PAGES_CSV,
        root / ERRATA,
        root / GUIDE_MD,
        root / GUIDE_OUTPUTS,
        root / DG.PIPES_CSV,
    ]
    return out + [svg_path(root, v) for v in DG.VIEWS if not v.startswith("article-")]


# ---- HTML pieces ----------------------------------------------------------------------------------------------------


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def code(s: str) -> str:
    return f"<code>{esc(s)}</code>"


def table(head: Sequence[str] | None, widths: Sequence[float], rows: Sequence[Sequence[str]], cls: str = "") -> str:
    """A table with fixed column widths (percent) and a repeating header row, or none if ``head`` is None; cells
    are HTML already escaped by the caller."""
    if any(len(r) != len(widths) for r in rows) or (head is not None and len(head) != len(widths)):
        raise ValueError("table: a row's length differs from the widths'")
    cols = "".join(f'<col style="width:{w:g}%">' for w in widths)
    if head is None:
        body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n" for r in rows)
        attr = f' class="{cls}"' if cls else ""
        return f"<table{attr}><colgroup>{cols}</colgroup>\n<tbody>\n{body}</tbody></table>\n"
    th = "".join(f"<th>{esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>\n" for r in rows)
    attr = f' class="{cls}"' if cls else ""
    return f"<table{attr}><colgroup>{cols}</colgroup>\n<thead><tr>{th}</tr></thead>\n<tbody>\n{body}</tbody></table>\n"


SVG_SIZE: Final = re.compile(r'\s(width|height)="[^"]*"')


def inline_svg(path: Path, cls: str = "diagram") -> str:
    """A committed SVG export as inline SVG: no XML declaration or doctype, scaled by CSS through its viewBox."""
    text = path.read_bytes().decode("utf-8")
    text = text[text.index("<svg") :].rstrip()
    end = text.index(">")
    head = SVG_SIZE.sub("", text[:end])
    return head.replace("<svg ", f'<svg class="{cls}" ', 1) + text[end:]


def svg_size(path: Path) -> tuple[float, float]:
    """The width and height of an SVG export in px (draw.io writes them on the root element)."""
    text = path.read_bytes().decode("utf-8")
    root = text[text.index("<svg") : text.index(">", text.index("<svg"))]
    w = re.search(r'\swidth="([0-9.]+)px"', root)
    h = re.search(r'\sheight="([0-9.]+)px"', root)
    if w is None or h is None:
        raise ValueError(f"{path.name}: no width and height in px")
    return float(w.group(1)), float(h.group(1))


def fig_h_mm(view: str) -> float:
    """The height a view's diagram is printed into: shorter where it carries its part's heading."""
    return FIG_H_MM - HEADING_MM if view in FIRST_FIGURES else FIG_H_MM


def print_pt_per_px(width: float, height: float, fig_h: float = FIG_H_MM, fig_w: float = FIG_W_MM) -> float:
    """The printed size of one SVG px in pt, for a diagram scaled to fit ``fig_w`` x ``fig_h`` (A4 by default)."""
    return min(fig_w / width, fig_h / height) * PT_PER_MM


def figure(root: Path, view: str, anchor: str, caption: str = "", heading: tuple[str, str] | None = None) -> str:
    """A diagram on its own page; ``heading`` (anchor, title) puts its part's heading on the page above it."""
    cap = f'<p class="caption">{esc(caption)}</p>' if caption else ""
    top = f'<h1 id="{heading[0]}">{esc(heading[1])}</h1>\n' if heading else ""
    svg = inline_svg(svg_path(root, view), "diagram headed" if heading else "diagram")
    return f'<section class="figure" id="{anchor}">\n{top}{svg}\n{cap}</section>\n'


# ---- sections -------------------------------------------------------------------------------------------------------


def title_page(root: Path) -> str:
    rows = [["Version", esc(version(root))], ["Default model", code(default_model(root))]]
    return (
        '<section class="title" id="title">\n<h1>ai-it-labour-sim</h1>\n<p class="sub">Model reference</p>\n'
        "<p>A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India "
        "and onshore (North America and Europe), 2024-2040.</p>\n"
        + table(None, [35, 65], rows)
        + "<p>Generated from the committed metadata; see docs/model/diagrams/MANIFEST.json</p>\n"
        "<p>Code: MIT. Text and diagrams: CC BY 4.0 (LICENSE-DOCS).</p>\n</section>\n"
    )


def contents(entries: Sequence[tuple[str, str, Sequence[tuple[str, str]]]]) -> str:
    out = ['<nav id="contents">\n<h1>Contents</h1>\n<ol>']
    for anchor, label, subs in entries:
        sub = ""
        if subs:
            sub = "<ol>" + "".join(f'<li><a href="#{a}">{esc(t)}</a></li>' for a, t in subs) + "</ol>"
        out.append(f'<li><a href="#{anchor}">{esc(label)}</a>{sub}</li>')
    out.append("</ol>\n</nav>\n")
    return "\n".join(out)


MARKS: Final = (
    (
        "Stock",
        "A box filled with its module's colour: a quantity that accumulates (a backlog, a headcount, a book of "
        "contracts). Stocks change only through flows.",
    ),
    (
        "Flow (valve)",
        "An hourglass with its name below: a rate that changes a stock. A thick arrow from a valve to a "
        "stock means the flow changes that stock, in or out; module pages do not say which, as they carry no "
        "polarity.",
    ),
    (
        "Goal-seeking valve",
        "A stock that adjusts toward a target over a time (a perception, a smoothed signal) has "
        "one unnamed flow, its adjustment, drawn as a valve named after the stock's change. Every input of the "
        "adjustment points at the valve, the stock's own level included.",
    ),
    (
        "Coflow valve",
        "Two stocks of the contract book (the duration-weighted and price-weighted new book) move with "
        "the book itself: their whole update is one flow that reads the signings and expiries. It is drawn as a valve "
        "whose inputs include those flows' valves.",
    ),
    (
        "Cloud and module region",
        "On the model map: a cloud is a source or sink outside the model's stocks; a tinted panel holds one "
        "module's stocks, valves and levers.",
    ),
    ("Auxiliary", "Bold text in the module's colour: a quantity computed afresh every step from other items."),
    ("Lever", "Grey italic text: a parameter that scenarios or the levers of an experiment set."),
    ("Ghost input", "Small grey text with a module in brackets: an item of another module that feeds this page."),
    (
        "Page reference",
        "Small grey text in a dashed box with a page in brackets: an item of the same module drawn on "
        "another of its pages, that feeds this page.",
    ),
    (
        "Polarity",
        "On the causal-loop panels and the article diagrams, + on an arrow means the target moves the same "
        "way as the source, - the opposite way. Module pages show dependence only: their arrows carry no sign.",
    ),
    ("R and B labels", "A circle with R marks a reinforcing loop, B a balancing loop, with the loop's id."),
    ("The ? label", "A loop whose sign depends on which of its paths dominates."),
    (
        "Hollow, grey and faded marks",
        "A dashed (hollow) circle marks a loop that is weak in Base or acts only in the "
        f"stress set '{DG.STRESS_SET}'; a grey circle one dormant in both; a faded arrow a link whose every loop is "
        "dormant in Base; a dashed arrow an open chain that no loop closes.",
    ),
    ("Limit markers", "A hexagon beside a link: a rule (a floor, a ceiling or a cap) that limits that link."),
)


def introduction(src: DG.Sources) -> str:
    marks = "".join(f"<dt>{esc(a)}</dt><dd>{esc(b)}</dd>" for a, b in MARKS)
    return (
        '<section id="intro">\n<h1>Introduction</h1>\n'
        "<p>This is the model reference of <code>ai-it-labour-sim</code>, a System Dynamics model of AI's impact on "
        "IT employment, contract mix and vendor viability. It gives scenario projections, not forecasts: read every "
        'value as "under these assumptions" (README). Its only model results are the Base values of the model guide; '
        "the README and the analyses state the rest.</p>\n"
        f"<p>The model has {len(src.modules)} engine modules. The overview shows how they feed each other; the model "
        "map shows every stock, flow and lever on one A2 page, with the pipes between the stocks; one or more "
        "module pages show each module's stocks, flows, auxiliaries and levers as a stock-and-flow diagram, each "
        "followed by its item list; five causal-loop panels show the feedback loops with their polarity; the data "
        "dictionary describes every named item; the errata list where the original specification is wrong and what "
        "the model does instead. The full per-link loop table is in the appendix. Every diagram and table is "
        "generated from the committed files; names are the engine's (<code>docs/model/inventory.csv</code>).</p>\n"
        "<p>On the module pages, arrows show which item is computed from which (<code>docs/model/edges.csv</code>); "
        "they carry no polarity, which is on the causal-loop panels and in <code>docs/model/loops.csv</code>. The "
        "larger modules take two or three pages, and each page is followed by its item list.</p>\n"
        f'<h2>How to read the diagrams</h2>\n<dl class="marks">{marks}</dl>\n</section>\n'
    )


def overview(root: Path, src: DG.Sources) -> str:
    pairs = DG.module_pairs(src)
    cap = (
        f"The eight modules and the {len(pairs)} module pairs that one module's stocks, flows and auxiliaries link to "
        f"another's items ({sum(pairs.values())} links). The label and width give the number of links; a dashed "
        "arrow is a single link."
    )
    rows = [[code(m["module"]), esc(m["display_name"]), esc(m["description"])] for m in src.modules]
    return (
        '<section id="overview-part">\n'
        + figure(root, "overview", "overview-figure", cap, ("overview", "Overview"))
        + '<h2 id="modules">The modules</h2>\n'
        + table(["Module", "Display name", "Description"], [14, 20, 66], rows)
        + "</section>\n"
    )


MAP_CAPTION: Final = (
    "Every stock, flow and lever of the model, by module: the pipes each flow fills and drains (tools/flow_pipes.csv, "
    "cited to the integration code) and each lever's first stocks and flows (docs/model/edges.csv). The legend on "
    "the map explains its marks; the module pages after it show the auxiliaries and information links it leaves out."
)


def map_section(root: Path) -> str:
    """The model map on its own A2 landscape page (slice 10e), with its heading and caption."""
    svg = inline_svg(svg_path(root, DG.MAP_VIEWS[0]), "map")
    return (
        f'<section class="figure map" id="model-map-part">\n<h1 id="model-map">Model map</h1>\n{svg}\n'
        f'<p class="caption">{esc(MAP_CAPTION)}</p></section>\n'
    )


def module_pages(root: Path, src: DG.Sources, inv: Mapping[tuple[str, str], Mapping[str, str]]) -> str:
    views = {name: DG.module_page(src, name) for name in DG.MODULE_VIEWS}
    valves = DG.valve_stocks(src)
    out = ['<section class="part">\n']
    for name, spec in DG.MODULE_VIEWS.items():
        v = views[name]
        heading = ("module-pages", "Module pages") if name in FIRST_FIGURES else None
        out.append(figure(root, name, name, heading=heading))
        rows = []
        for c in v.cells:
            if c.kind not in ("node", "valve"):
                continue
            item = DG.page_item(src, c.id)
            r = inv.get(item, {})
            kind = item[1]
            if item[0].startswith("flow:"):
                kind = f"flow ({valves[item[0].removeprefix('flow:')]})"
            rows.append([code(item[0]), esc(kind), esc(r.get("label", "")), esc(r.get("units", ""))])
        rows.sort(key=lambda x: x[0])
        ghosts = sorted(c.label.replace("\n", " ") for c in v.cells if c.kind == "ghost")
        refs = sorted(c.label.replace("\n", " ") for c in v.cells if c.kind == "ref")
        out.append(f'<section id="items-{name}">\n<h2>{esc(spec.title)}: items</h2>\n')
        out.append(table(["Name", "Kind", "Label", "Units"], [22, 14, 40, 24], rows, "small"))
        if ghosts:
            out.append(f"<p>Inputs from other modules: {esc('; '.join(ghosts))}.</p>\n")
        if refs:
            out.append(f"<p>Inputs from other pages of this module: {esc('; '.join(refs))}.</p>\n")
        out.append("</section>\n")
    out.append("</section>\n")
    return "".join(out)


def panels(root: Path, src: DG.Sources) -> str:
    out = ['<section class="part">\n']
    for view, spec in DG.PANEL_VIEWS.items():
        ids = sorted(k for k, r in src.summary.items() if r["panel"] == spec.key)
        heading = ("panels", "Feedback loops") if view in FIRST_FIGURES else None
        out.append(figure(root, view, view, f"Loops: {', '.join(ids)}.", heading))
    rows = []
    for lid, r in src.summary.items():
        ruling = ", ".join(dict.fromkeys(LOOP_RULING.findall(r["status_basis"]))) or "-"
        polarity = r["code_polarity"].split()[0].strip(":,(") if r["code_polarity"] else ""
        cells = [lid, r["name"], polarity, r["status"], r["acts_phase9_base"], r["acts_stress_set"], ruling]
        rows.append([esc(x) for x in cells])
    out.append(
        '<h2 id="loops">The loops</h2>\n<p>The five panels are drawn from the loop inventory: '
        "<code>docs/model/loops.csv</code> (one row per link, with its sign, the code line and the regime it needs) "
        f"and <code>docs/model/loop_summary.csv</code> (one row per loop: the {len(rows)} loops below). Each panel's "
        f"legend gives its marks; the stress set is '{esc(DG.STRESS_SET)}'. Open chains are dashed; replaced loops "
        "(R4, B8) are noted, not drawn.</p>\n"
    )
    head = ["Loop", "Name", "Polarity", "Status", "Acts in Base", "Acts in the stress set", "Ruling"]
    out.append(table(head, [6, 20, 10, 9, 22, 22, 11], rows, "small"))
    out.append("</section>\n")
    return "".join(out)


def short_value(row: Mapping[str, str], model: str) -> str:
    """A parameter's or table's value for the compact table: the scalar as stored, or a pointer to the inventory."""
    v = row.get(f"value_{model}", "")
    if "=" not in v and ";" not in v:
        return v
    dims = row["dimensions"]
    return f"per {dims}, see inventory.csv" if dims else "indexed, see inventory.csv"


def dictionary(inv_rows: Sequence[Mapping[str, str]], model: str) -> str:
    models = [k.removeprefix("value_") for k in inv_rows[0] if k.startswith("value_")]
    others = [m for m in models if m != model]
    out = [
        '<section id="dictionary">\n<h1>Data dictionary</h1>\n',
        "<p>Every named item of the model, as in <code>docs/model-reference.md</code>. Parameters and tables show "
        f"their <code>{esc(model)}</code> value: a scalar as stored, or a pointer for an indexed value; every model's "
        'full values are in <code>docs/model/inventory.csv</code>. "Differs in" names the models whose value '
        f"differs from <code>{esc(model)}</code>'s.</p>\n",
    ]
    for kind in KINDS:
        rows = []
        for r in (x for x in inv_rows if x["kind"] == kind):
            row = [code(r["name"]), esc(r["label"]), esc(r["description"]), esc(r["units"]), esc(r["dimensions"])]
            row.append(esc(r["module"]))
            if kind in ("parameter", "table"):
                ref = r.get(f"value_{model}", "")
                differs = [m for m in others if r.get(f"value_{m}", "") != ref]
                row += [esc(short_value(r, model)), esc(", ".join(differs)), esc(r["classification"]), esc(r["lever"])]
            row.append(esc(r["status"]))
            rows.append(row)
        head = ["Name", "Label", "Description", "Units", "Dimensions", "Module"]
        widths: list[float] = [11, 13, 41, 12, 9, 7]
        if kind in ("parameter", "table"):
            head += [model, "Differs in", "Class", "Lever"]
            widths = [9, 10, 25, 8, 7, 6, 9, 8, 8, 4]
        head.append("Status")
        widths.append(7 if kind not in ("parameter", "table") else 6)
        widths[2] += 100 - sum(widths)
        out.append(f'<h2 id="dict-{kind}">{SECTION_TITLES[kind]}</h2>\n<p>{len(rows)} items.</p>\n')
        out.append(table(head, widths, rows, "small"))
    out.append("</section>\n")
    return "".join(out)


INLINE: Final = re.compile(r"`([^`]+)`|\*\*(.+?)\*\*")


def inline(s: str) -> str:
    """Code spans and bold, the only inline marks of the errata file; everything else escaped."""
    out, pos = [], 0
    for m in INLINE.finditer(s):
        out.append(esc(s[pos : m.start()]))
        out.append(code(m.group(1)) if m.group(1) is not None else f"<strong>{inline(m.group(2))}</strong>")
        pos = m.end()
    out.append(esc(s[pos:]))
    return "".join(out)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def markdown(
    path: Path, text: str, prefix: str, widths: Mapping[tuple[str, ...], Sequence[float]] | None = None
) -> tuple[list[str], list[tuple[str, str]]]:
    """A committed markdown file of this repo's own constructs as HTML pieces: headings, paragraphs, bullet lists with
    indented continuation lines, tables, fenced code blocks, code spans and bold. Any other line raises, so a new
    construct is never dropped silently. A table takes its column widths from ``widths`` by header row, or equal
    widths if ``widths`` is None (with ``widths`` given, an unknown header raises). Returns the pieces and the
    (anchor, title) of each ``##`` heading, anchored ``<prefix><slug>``."""
    lines = text.split("\n")
    out: list[str] = []
    heads: list[tuple[str, str]] = []
    para: list[str] = []
    items: list[list[str]] = []
    rows: list[list[str]] = []
    block: list[str] | None = None

    def flush() -> None:
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>\n")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{inline(' '.join(x))}</li>" for x in items) + "</ul>\n")
            items.clear()
        if rows:
            head = tuple(rows[0])
            if widths is None:
                w: Sequence[float] = [100 / len(head)] * len(head)
            elif head in widths:
                w = widths[head]
            else:
                raise ValueError(f"{path.as_posix()}: no column widths for the table {head!r}")
            out.append(table(rows[0], w, [[inline(c) for c in r] for r in rows[1:]]))
            rows.clear()

    for ln in lines:
        if block is not None:
            if ln == "```":
                out.append(f"<pre><code>{esc(chr(10).join(block))}</code></pre>\n")
                block = None
            else:
                block.append(ln)
        elif ln.startswith("```"):
            flush()
            block = []
        elif not ln.strip():
            flush()
        elif ln.startswith("# "):
            flush()
            out.append(f"<h1>{inline(ln[2:])}</h1>\n")
        elif ln.startswith("## "):
            flush()
            anchor = f"{prefix}{slug(ln[3:])}"
            heads.append((anchor, ln[3:]))
            out.append(f'<h2 id="{anchor}">{inline(ln[3:])}</h2>\n')
        elif ln.startswith("### "):
            flush()
            out.append(f"<h3>{inline(ln[4:])}</h3>\n")
        elif ln.startswith("- "):
            if para or rows:
                flush()
            items.append([ln[2:]])
        elif ln.startswith("  ") and items:
            items[-1].append(ln.strip())
        elif ln.startswith("| "):
            if para or items:
                flush()
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if not all(set(c) <= {"-"} for c in cells):
                rows.append(cells)
        elif ln[0].isalnum() or ln[0] in '(`*"':
            if items:
                flush()
            para.append(ln.strip())
        else:
            raise ValueError(f"{path.as_posix()}: a line this renderer does not know: {ln!r}")
    if block is not None:
        raise ValueError(f"{path.as_posix()}: an unclosed code block")
    flush()
    if not out or not out[0].startswith("<h1>"):
        raise ValueError(f"{path.as_posix()}: no title")
    return out, heads


def errata(root: Path) -> tuple[str, list[tuple[str, str]]]:
    """``docs/spec-errata.md`` as HTML (``markdown()``, equal column widths). Returns the HTML and the (anchor, title)
    of each module heading."""
    out, heads = markdown(ERRATA, (root / ERRATA).read_text(encoding="utf-8"), "errata-")
    out[0] = out[0].replace("<h1>", '<h1 id="errata-title">', 1)
    return '<section id="errata">\n' + "".join(out) + "</section>\n", heads


def page_range(pages: Mapping[str, int], first: str, after: str) -> str:
    """The pages of a part of the reference PDF: from its first anchor's page to the page before the next part's."""
    a, b = pages[first], pages[after] - 1
    return f"page {a}" if a >= b else f"pages {a}-{b}"


def guide_section(root: Path, pages: Mapping[str, int], standalone: bool) -> tuple[str, list[tuple[str, str]]]:
    """``docs/model-guide.md`` as HTML (``markdown()`` with ``GUIDE_WIDTHS``), in ``<section class="guide">``. The
    "Where to look next" lines of ``GUIDE_PAGES`` gain the reference PDF's pages: linked in the reference, as text in
    the standalone guide, which also carries a subtitle with the version. Returns the HTML and its (anchor, title)
    headings."""
    out, heads = markdown(GUIDE_MD, (root / GUIDE_MD).read_text(encoding="utf-8"), "guide-", GUIDE_WIDTHS)
    sub = ""
    if standalone:
        sub = f'<p class="sub">ai-it-labour-sim {esc(version(root))}</p>\n'
    out[0] = out[0].replace("<h1>", '<h1 id="guide">', 1) + sub
    text = "".join(out)
    for title, (first, after) in GUIDE_PAGES.items():
        start = text.find(f"<li><strong>{esc(title)}:</strong>")
        if start < 0:
            raise ValueError(f"{GUIDE_MD.as_posix()}: no 'Where to look next' line {title!r}")
        end = text.index("</li>", start)
        span = page_range(pages, first, after)
        add = (
            f' In this PDF: <a href="#{first}">{span}</a>.' if not standalone else f" In {PDF_OUT.as_posix()}: {span}."
        )
        text = text[:end] + add + text[end:]
    return f'<section class="guide" id="guide-part">\n{text}</section>\n', heads


def appendix(src: DG.Sources, inv_rows: Sequence[Mapping[str, str]]) -> str:
    rows = [
        [
            esc(r["loop_id"]),
            esc(r["step"]),
            code(r["source"]),
            code(r["target"]),
            esc(r["sign"]),
            esc(r["regime"]),
            esc(r["file_line"]),
        ]
        for r in src.loops
    ]
    by: dict[str, list[Mapping[str, str]]] = {}
    for r in inv_rows:
        by.setdefault(r["name"], []).append(r)
    clashes = [
        [
            code(n),
            esc(
                "; ".join(f"{n} ({r['kind']}, {r['module']})" for r in sorted(rs, key=lambda x: KINDS.index(x["kind"])))
            ),
        ]
        for n, rs in sorted(by.items())
        if len(rs) > 1
    ]
    return (
        '<section id="appendix">\n<h1>Appendix</h1>\n'
        f'<h2 id="loop-links">The loop links</h2>\n<p>{len(rows)} rows of <code>docs/model/loops.csv</code>, one per '
        "link of each loop: its step, source and target, sign, the regime it needs and the code line. The code "
        "expression and notes are in the file.</p>\n"
        + table(
            ["Loop", "Step", "Source", "Target", "Sign", "Regime", "Code"], [5, 18, 11, 11, 4, 33, 18], rows, "small"
        )
        + '<h2 id="name-clashes">Name clashes</h2>\n<p>Names shared by items of different kinds; each entry is '
        "qualified by its kind.</p>\n" + table(["Name", "Items"], [15, 85], clashes) + "</section>\n"
    )


def stored_pages(root: Path) -> dict[str, int]:
    """The reference PDF's pages of ``PAGE_ANCHORS`` as the manifest stores them (key ``guide``); 0 for each anchor
    before the first print."""
    guide = manifest(root).get("guide", {})
    pages = guide.get("pages", {}) if isinstance(guide, dict) else {}
    return {a: int(pages.get(a, 0)) for a in PAGE_ANCHORS}


def _document(title: str, body: str) -> str:
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{esc(title)}</title>\n<style>\n{CSS}</style>\n</head>\n<body>\n{body}</body>\n</html>\n"
    )


def build_guide_html(root: Path = ROOT, pages: Mapping[str, int] | None = None) -> str:
    """The standalone model guide: the guide section alone, with the reference PDF's pages (the manifest's by
    default)."""
    html_, _ = guide_section(root, stored_pages(root) if pages is None else pages, standalone=True)
    return _document(f"ai-it-labour-sim model guide {version(root)}", html_)


def build_map_html(root: Path = ROOT) -> str:
    """The standalone model map: its A2 page alone."""
    return _document(f"ai-it-labour-sim model map {version(root)}", map_section(root))


def build_html(root: Path = ROOT, pages: Mapping[str, int] | None = None) -> str:
    """The model reference, with its own pages in the guide's "Where to look next" lines (the manifest's by
    default)."""
    src = DG.read_sources(root)
    inv_rows = read_csv(root / INVENTORY)
    inv = {(r["name"], r["kind"]): r for r in inv_rows}
    model = default_model(root)
    errata_html, errata_heads = errata(root)
    guide_html, guide_heads = guide_section(root, stored_pages(root) if pages is None else pages, standalone=False)
    entries: list[tuple[str, str, Sequence[tuple[str, str]]]] = [
        ("intro", "Introduction", ()),
        ("guide", "Model guide", [(a, re.sub(r"^\d+\. ", "", t)) for a, t in guide_heads]),
        ("overview", "Overview", (("modules", "The modules"),)),
        ("model-map", "Model map", ()),
        ("module-pages", "Module pages", [(n, s.title) for n, s in DG.MODULE_VIEWS.items()]),
        ("panels", "Feedback loops", [*((v, s.title) for v, s in DG.PANEL_VIEWS.items()), ("loops", "The loops")]),
        ("dictionary", "Data dictionary", [(f"dict-{k}", SECTION_TITLES[k]) for k in KINDS]),
        ("errata-title", "Specification errata", errata_heads),
        ("appendix", "Appendix", (("loop-links", "The loop links"), ("name-clashes", "Name clashes"))),
    ]
    body = (
        title_page(root)
        + contents(entries)
        + introduction(src)
        + guide_html
        + overview(root, src)
        + map_section(root)
        + module_pages(root, src, inv)
        + panels(root, src)
        + dictionary(inv_rows, model)
        + errata_html
        + appendix(src, inv_rows)
    )
    return _document(f"ai-it-labour-sim model reference {version(root)}", body)


# ---- checks ---------------------------------------------------------------------------------------------------------

DATE_PATTERN: Final = re.compile(r"\b(?:19|20)\d\d-[01]\d-[0-3]\d\b|\b[0-2]\d:[0-5]\d:[0-5]\d\b")
HASH_PATTERN: Final = re.compile(r"\b(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}\b")


def stamp_problems(text: str, sources: Sequence[str]) -> list[str]:
    """Date, time or commit-hash patterns in the HTML that appear in none of its source files (a build stamp)."""
    found = sorted(set(DATE_PATTERN.findall(text)) | set(HASH_PATTERN.findall(text)))
    return [f for f in found if not any(f in s for s in sources)]


def link_problems(text: str) -> list[str]:
    """Internal links whose target id does not exist."""
    ids = set(re.findall(r'\sid="([^"]+)"', text))
    return sorted({h for h in re.findall(r'\shref="#([^"]+)"', text) if h not in ids})


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def manifest(root: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads((root / DG.MANIFEST).read_text(encoding="utf-8"))
    return data


def reference_hashes(root: Path) -> dict[str, str]:
    ref = manifest(root).get("reference", {})
    if not isinstance(ref, dict):
        return {}
    return {str(k): str(v) for k, v in ref.items()}


def map_hashes(root: Path) -> dict[str, str]:
    """The standalone map's HTML and PDF hashes as the manifest stores them (key ``map``)."""
    entry = manifest(root).get("map", {})
    if not isinstance(entry, dict):
        return {}
    return {k: str(entry[k]) for k in ("html", "pdf") if k in entry}


def guide_hashes(root: Path) -> dict[str, str]:
    """The guide's HTML and PDF hashes as the manifest stores them (key ``guide``)."""
    guide = manifest(root).get("guide", {})
    if not isinstance(guide, dict):
        return {}
    return {k: str(guide[k]) for k in ("html", "pdf") if k in guide}


DEST: Final = re.compile(rb"/([^\s/\[\]<>()]+) \[(\d+) 0 R /XYZ")


def _pdf_object(pdf: bytes, num: int) -> bytes:
    start = pdf.index(b"\n%d 0 obj" % num)
    return pdf[start : pdf.index(b"endobj", start)]


def dest_pages(pdf: bytes) -> dict[str, int]:
    """Each named destination of an Edge PDF (an HTML anchor that a link targets) and its 1-based page: the catalog's
    ``/Dests`` dictionary against the page order of its ``/Pages`` tree, read without a PDF library."""
    cat = re.search(rb"/Type /Catalog\s*/Pages (\d+) 0 R\s*/Dests (\d+) 0 R", pdf)
    if cat is None:
        raise ValueError("dest_pages: no catalog with /Pages and /Dests")

    def leaves(num: int) -> list[int]:
        obj = _pdf_object(pdf, num)
        if not re.search(rb"/Type /Pages\b", obj):
            return [num]
        kids = re.search(rb"/Kids \[([^\]]*)\]", obj)
        if kids is None:
            raise ValueError(f"dest_pages: page tree node {num} has no /Kids")
        return [p for k in re.findall(rb"(\d+) 0 R", kids.group(1)) for p in leaves(int(k))]

    order = {num: i + 1 for i, num in enumerate(leaves(int(cat.group(1))))}
    dests = _pdf_object(pdf, int(cat.group(2)))
    return {m.group(1).decode("ascii"): order[int(m.group(2))] for m in DEST.finditer(dests)}


def page_problems(pages: Mapping[str, int], pdf: bytes) -> list[str]:
    """Anchors of ``PAGE_ANCHORS`` whose stored page differs from the PDF's."""
    found = dest_pages(pdf)
    return [
        f"{a}: stored page {pages.get(a)}, PDF page {found.get(a)}"
        for a in PAGE_ANCHORS
        if pages.get(a) != found.get(a)
    ]


def check(root: Path = ROOT) -> list[str]:
    ref = reference_hashes(root)
    guide = guide_hashes(root)
    bad = []
    if sha256_bytes(build_html(root).encode("utf-8")) != ref.get("html"):
        bad.append(f"{HTML_OUT.as_posix()}: differs from the manifest's hash (the PDF needs a new print)")
    pdf = root / PDF_OUT
    if not pdf.exists() or sha256_bytes(pdf.read_bytes()) != ref.get("pdf"):
        bad.append(f"{PDF_OUT.as_posix()}: missing or differs from the manifest's hash")
    else:
        bad += [f"{PDF_OUT.as_posix()}: {p}" for p in page_problems(stored_pages(root), pdf.read_bytes())]
    if sha256_bytes(build_guide_html(root).encode("utf-8")) != guide.get("html"):
        bad.append(f"{GUIDE_HTML_OUT.as_posix()}: differs from the manifest's hash (the PDF needs a new print)")
    gpdf = root / GUIDE_PDF_OUT
    if not gpdf.exists() or sha256_bytes(gpdf.read_bytes()) != guide.get("pdf"):
        bad.append(f"{GUIDE_PDF_OUT.as_posix()}: missing or differs from the manifest's hash")
    mp = map_hashes(root)
    if sha256_bytes(build_map_html(root).encode("utf-8")) != mp.get("html"):
        bad.append(f"{MAP_HTML_OUT.as_posix()}: differs from the manifest's hash (the PDF needs a new print)")
    mpdf = root / MAP_PDF_OUT
    if not mpdf.exists() or sha256_bytes(mpdf.read_bytes()) != mp.get("pdf"):
        bad.append(f"{MAP_PDF_OUT.as_posix()}: missing or differs from the manifest's hash")
    return bad


# ---- printing -------------------------------------------------------------------------------------------------------

PDF_DATE: Final = re.compile(rb"D:(\d{14})")
PDF_ID: Final = re.compile(rb"/ID\s*\[\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\]")


def pin(pdf: bytes, html_sha: str) -> bytes:
    """Edge's PDF with its dates and ``/ID`` replaced by fixed values of the same byte length, so that every
    offset (and the xref table) stays put: each ``D:`` date's 14 digits become ``PIN_DATE``, each ``/ID`` string the
    first characters of the HTML's SHA-256. Raises unless the PDF has exactly two dates (``/CreationDate`` and
    ``/ModDate``) and at most one file ``/ID`` of two strings (Edge 155 writes none in a tagged PDF; the structure
    tree's ``/ID (nodeNNNN)`` keys are counters, not dates or ids of the print)."""
    dates = PDF_DATE.findall(pdf)
    ids = PDF_ID.findall(pdf)
    if len(dates) != 2 or len(ids) > 1:
        raise ValueError(f"pin: expected 2 dates and at most 1 /ID, found {len(dates)} and {len(ids)}")
    out = PDF_DATE.sub(b"D:" + PIN_DATE, pdf)

    def fixed(m: re.Match[bytes]) -> bytes:
        whole, start = bytearray(m.group(0)), m.start(0)
        for g in (1, 2):
            if m.end(g) - m.start(g) > len(html_sha):
                raise ValueError("pin: an /ID string longer than the HTML hash")
            whole[m.start(g) - start : m.end(g) - start] = html_sha[: m.end(g) - m.start(g)].encode("ascii")
        return bytes(whole)

    out = PDF_ID.sub(fixed, out)
    if len(out) != len(pdf):
        raise ValueError("pin: the byte length changed")
    return out


def complete_pdf(path: Path) -> bool:
    """Whether a file is a whole PDF: it starts with ``%PDF-`` and ends with ``%%EOF``."""
    if not path.exists():
        return False
    data = path.read_bytes()
    return data.startswith(b"%PDF-") and data.rstrip().endswith(b"%%EOF")


def edge_print(html_file: Path, pdf_file: Path, timeout: float = EDGE_TIMEOUT_S) -> None:
    """Print the HTML with headless Edge (recon 10b A2's flags, a plain ``C:/`` path, a fresh profile), stopped after
    ``timeout`` seconds (slice 10e). On a timeout Edge's process tree is ended; a complete PDF it already wrote is
    used (``pin()`` follows), otherwise the print is tried once more. Each timeout is printed for the report. Edge's
    output is not piped: a child left running would hold the pipe open."""
    pdf_file.parent.mkdir(parents=True, exist_ok=True)
    for attempt in (1, 2):
        pdf_file.unlink(missing_ok=True)
        with tempfile.TemporaryDirectory(prefix="edge_profile_", ignore_cleanup_errors=True) as prof:
            cmd = [
                str(EDGE_EXE),
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--user-data-dir={prof}",
                f"--print-to-pdf={pdf_file.resolve()}",
                html_file.resolve().as_posix(),
            ]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                kill = ["taskkill", "/T", "/F", "/PID", str(proc.pid)]
                subprocess.run(kill, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                proc.wait()
                done = complete_pdf(pdf_file)
                outcome = "its PDF is complete and is used" if done else "no complete PDF, printing again"
                print(f"Edge timed out after {timeout:g} s printing {html_file.name} (attempt {attempt}); {outcome}")
                if done:
                    return
                continue
            if code != 0:
                raise subprocess.CalledProcessError(code, cmd)
        if not complete_pdf(pdf_file):
            raise RuntimeError(f"Edge wrote no complete {pdf_file}")
        return
    raise RuntimeError(f"Edge timed out twice printing {html_file.name}")


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
    return path


def write_html(root: Path = ROOT, out_root: Path | None = None, pages: Mapping[str, int] | None = None) -> Path:
    return _write((root if out_root is None else out_root) / HTML_OUT, build_html(root, pages))


def write_guide_html(root: Path = ROOT, out_root: Path | None = None, pages: Mapping[str, int] | None = None) -> Path:
    return _write((root if out_root is None else out_root) / GUIDE_HTML_OUT, build_guide_html(root, pages))


def write_map_html(root: Path = ROOT, out_root: Path | None = None) -> Path:
    return _write((root if out_root is None else out_root) / MAP_HTML_OUT, build_map_html(root))


def _print(root: Path, html_file: Path, name: str) -> tuple[str, bytes]:
    """Print an HTML file with Edge and pin it: the HTML's hash and the pinned PDF."""
    html_sha = sha256_bytes(html_file.read_bytes())
    raw = root / HTML_OUT.parent / f"{name}.raw.pdf"
    edge_print(html_file, raw)
    return html_sha, pin(raw.read_bytes(), html_sha)


MAX_PRINTS: Final = 3


def write_pdf(root: Path = ROOT) -> dict[str, object]:
    """Print the reference until the guide's page numbers equal its own (at most ``MAX_PRINTS`` prints), then the
    standalone guide with the same pages; pin both PDFs and record their hashes and the pages in the manifest (local
    only)."""
    pages = stored_pages(root)
    for _ in range(MAX_PRINTS):
        html_sha, pdf = _print(root, write_html(root, pages=pages), "model-reference")
        found = {a: dest_pages(pdf)[a] for a in PAGE_ANCHORS}
        if found == pages:
            break
        pages = found
    else:
        raise RuntimeError(f"the reference's page numbers did not settle in {MAX_PRINTS} prints")
    guide_sha, guide_pdf = _print(root, write_guide_html(root, pages=pages), "model-guide")
    map_sha, map_pdf = _print(root, write_map_html(root), "model-map")
    (root / PDF_OUT).write_bytes(pdf)
    (root / GUIDE_PDF_OUT).write_bytes(guide_pdf)
    (root / MAP_PDF_OUT).write_bytes(map_pdf)
    man = manifest(root)
    man["reference"] = {"html": html_sha, "pdf": sha256_bytes(pdf)}
    man["guide"] = {"html": guide_sha, "pdf": sha256_bytes(guide_pdf), "pages": pages}
    man["map"] = {"html": map_sha, "pdf": sha256_bytes(map_pdf)}
    with (root / DG.MANIFEST).open("w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return {"reference": man["reference"], "guide": man["guide"], "map": man["map"]}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--html", action="store_true", help="write the reference's and the guide's HTML to docs/_build/")
    g.add_argument("--pdf", action="store_true", help="write the HTML, print both PDFs with Edge, update the manifest")
    g.add_argument("--check", action="store_true", help="exit 1 if an HTML or a PDF differs from the manifest")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this repository)")
    a = ap.parse_args(argv)
    if a.html:
        for p in (write_html(a.root), write_guide_html(a.root), write_map_html(a.root)):
            print("wrote", p.relative_to(a.root).as_posix())
    elif a.pdf:
        print(PDF_OUT.as_posix(), GUIDE_PDF_OUT.as_posix(), MAP_PDF_OUT.as_posix(), write_pdf(a.root))
    else:
        bad = check(a.root)
        for b in bad:
            print(b)
        if bad:
            print("rebuild with: uv run --frozen python tools/model_pdf.py --pdf (locally, with Edge)")
            return 1
        print("model reference, model guide and model map: the HTML and the PDFs match the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
