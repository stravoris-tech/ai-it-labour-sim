"""The model's diagrams: the overview, the causal-loop panels, the article set (slice 10b) and the module pages (slice
10c), as draw.io files.

Module pages are stock-and-flow views of each module (``MODULE_PAGES``; each item's page in ``tools/module_pages.csv``,
its module from ``model_docs.csv``): stocks as boxes, flows as valves, auxiliaries in the module colour, levers grey
italic, inputs from other modules as grey ghosts and inputs from the module's other pages as grey page references.
Their arrows carry no polarity. A stock's unnamed flow ``flow:<stock>`` is drawn as its valve: every input of the
update points at the valve, and the valve's pipe at the stock.

Every view is generated from the curated metadata (``src/aisim/data/model_docs.csv``, ``model_modules.csv`` and
``model_articles.csv``), the dependency edges (``docs/model/edges.csv``) and the loop inventory
(``docs/model/loops.csv``, ``docs/model/loop_summary.csv``), with its positions from a geometry sidecar
(``docs/model/diagrams/<view>.geometry.json``: cell id to ``[x, y, w, h]``, sorted keys; a link whose sign label is
moved has ``e:<source>><target>`` to ``[position along the link from -1 to 1, offset in px, 0, 0]``). The ``.drawio``
file is a pure function of these, so regeneration is byte-identical. draw.io desktop is needed only to export SVG and
PNG, locally; CI checks the exports against ``docs/model/diagrams/MANIFEST.json``.

- ``--write`` writes every ``.drawio``. It reports sidecar ids that no view uses (orphans) and cells with no position,
  which it places in a free column right of the drawn cells (not saved).
- ``--layout VIEW`` stores a first layout in VIEW's sidecar, only for cells that have no position. With an empty
  sidecar: a layered layout (stdlib) for the overview, networkx's spring layout for panels and articles (run with
  ``uv run --frozen --with networkx==3.4.2``; networkx is not a dependency). Otherwise new cells go to a free column
  right of the current bounding box, never on a placed cell. Regeneration never recomputes a layout.
- ``--absorb VIEW`` reads a ``.drawio`` saved by draw.io (plain or compressed) back into VIEW's sidecar.
- ``--check`` regenerates every ``.drawio`` and compares bytes, then checks the manifest; exit 1 on any difference.
- ``--export`` runs draw.io desktop to write each view's SVG and PNG (scale 2), then writes the manifest.

Cell ids are item names (``H``), item names with a role for option-indexed items (``SrcTarget@GCC``), a group
(``staff@vendor``: ``V``, ``O`` and ``H``), loop ids for loop labels (``R7``; ``P-C2:B`` where a loop has two labels),
``limit:<parameter>`` for limit markers, article node ids (``A1.ai_use``) and ``title``, ``legend``, ``caption:<n>``.

Usage: ``uv run --frozen python tools/model_diagrams.py --write`` (or ``--check``, ``--layout VIEW``, ``--absorb
VIEW``, ``--export``)
"""

from __future__ import annotations

import argparse
import ast
import base64
import collections
import csv
import hashlib
import importlib
import itertools
import json
import keyword
import math
import re
import subprocess
import sys
import textwrap
import tokenize
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parent.parent
DATA: Final = Path("src/aisim/data")
MODEL: Final = Path("docs/model")
DIAGRAMS: Final = MODEL / "diagrams"
MANIFEST: Final = DIAGRAMS / "MANIFEST.json"
DRAWIO_EXE: Final = Path(r"C:\Program Files\draw.io\draw.io.exe")
DRAWIO_VERSION: Final = "29.0.3"
PNG_SCALE: Final = 2
BORDER: Final = 20
STRESS_SET: Final = "Fast AI + OIT price shock"
"""The stress set of ``aisim.scenarios.STRESS_SCENARIOS`` that the panels' hollow labels refer to."""
WRAP: Final = 18
"""Node labels wrap at 18 characters, at most 3 lines on a panel."""

Geometry = dict[str, list[float]]

# ---- the views ------------------------------------------------------------------------------------------------------

STAFF_NOTE: Final = "Vendor staff groups vacancies, onboarding and headcount, which panel 1 shows apart."


@dataclass(frozen=True)
class PanelSpec:
    """One causal-loop panel: the loops of ``loop_summary.csv`` whose ``panel`` is ``key``."""

    key: str
    title: str
    collapse_staff: bool
    keep: tuple[str, ...]
    """Cells never collapsed into a link (the ends of capped links)."""
    captions: tuple[str, ...]


PANELS: Final = (
    PanelSpec(
        "labour",
        "Panel 1. Labour market and hiring",
        False,
        ("Comp",),
        (
            "? R5: balancing through hiring and unemployment, reinforcing only through the ageing chain (E10).",
            "? U3: reinforcing on paper, with a gain near zero: switching keeps each pool's headcount.",
            "R4 (skill erosion) is replaced by its phase 9 term P-R4 and not drawn (E3).",
            "P-R4 is balancing as built: more seekers mean longer spells and faster exits from IT, so fewer seekers.",
        ),
    ),
    PanelSpec(
        "distress",
        "Panel 2. Vendor distress",
        True,
        ("VF.Anchor", "VF.PNew", "VF.Revenue"),
        (
            "P-C2 has two labels on one path: balancing through labour cost (B), reinforcing through capacity (R).",
            "P-C4: client flight reinforces (R); clients getting used to the distress fade it (B).",
            "C5 and C6 are rules, not loops (limit markers). They bind only in the Fast AI scenario and the stress set:"
            "\nC5 (price floor) from 2028, C6 (AI-discount ceiling) from mid-2030.",
            STAFF_NOTE,
        ),
    ),
    PanelSpec(
        "pricing",
        "Panel 3. Pricing and contracts",
        True,
        (),
        (
            "? U1: closes through productivity (work over effort), where two parallel paths have opposite signs.",
            "B2 (T&M paradox) is reinforcing in the code, against the spec's balancing (E35).",
            "C6 caps the AI discount clients expect (limit marker)."
            "\nIt binds only in the Fast AI scenario and the stress set, from mid-2030.",
        ),
    ),
    PanelSpec(
        "sourcing",
        "Panel 4. Sourcing and GCC growth",
        False,
        ("GCCW", "GCCScaleTerm"),
        (
            "R7 feeds back until about 2032, then sits at its cap: a fixed shift with no further gain.",
            "R10 closes only through R6's margin terms (E17).",
            "B8 (political pressure) is replaced by the visa scenario input and not drawn (E7).",
        ),
    ),
    PanelSpec(
        "demand",
        "Panel 5. Adoption, demand and capability",
        False,
        (),
        (
            "? U5: a ratio (services spend over completed work) whose two paths have opposite signs.",
            "R3 and U5 are dormant while JevonsEps is 0 (they act in the Jevons rebound scenario).",
        ),
    ),
)
PANEL_VIEWS: Final = {f"panel-{p.key}": p for p in PANELS}
ARTICLES: Final = ("A1", "A2", "A3", "A4", "A5")
ARTICLE_VIEWS: Final = {f"article-{a.lower()}": a for a in ARTICLES}


@dataclass(frozen=True)
class PageSpec:
    """One module page (slice 10c): its key, the modules whose items it draws, its title and the short name that page
    references to it carry."""

    key: str
    modules: tuple[str, ...]
    title: str
    short: str


MODULE_PAGES: Final = (
    PageSpec("capability-adoption", ("capability", "adoption"), "AI capability and delivery AI adoption", "capability"),
    PageSpec(
        "consumer-a", ("consumer",), "Client demand and consumer AI (a): client AI and line of business", "consumer a"
    ),
    PageSpec("consumer-b", ("consumer",), "Client demand and consumer AI (b): budgets, demand and spend", "consumer b"),
    PageSpec("consumer-c", ("consumer",), "Client demand and consumer AI (c): applications and seats", "consumer c"),
    PageSpec("work", ("work",), "Work and productivity", "work"),
    PageSpec("workforce", ("workforce",), "Workforce planning", "workforce"),
    PageSpec("labour-market-a", ("labour_market",), "Labour market (a): people pools and exits", "labour market a"),
    PageSpec("labour-market-b", ("labour_market",), "Labour market (b): hiring and switching", "labour market b"),
    PageSpec("sourcing", ("sourcing",), "Sourcing choice", "sourcing"),
    PageSpec("finance-a", ("finance",), "Vendor finance and contracts (a): costs and wages", "finance a"),
    PageSpec("finance-b", ("finance",), "Vendor finance and contracts (b): contracts and prices", "finance b"),
    PageSpec("finance-c", ("finance",), "Vendor finance and contracts (c): revenue, margin and viability", "finance c"),
)
MODULE_VIEWS: Final = {f"module-{p.key}": p for p in MODULE_PAGES}
MAP_VIEWS: Final = ("model-map",)
"""The whole-model map (slice 10e): one A2 page."""
VIEWS: Final = ("overview", *PANEL_VIEWS, *ARTICLE_VIEWS, *MODULE_VIEWS, *MAP_VIEWS)

QUESTION_LOOPS: Final = frozenset({"R5", "U1", "U3", "U5"})
"""Loops whose sign depends on which path dominates (decision 3): a "?" label and a caption."""
SPLIT_LABELS: Final[Mapping[str, tuple[tuple[str, str, str], ...]]] = {
    "P-C2": (("P-C2:B", "B", "leg a: labour cost"), ("P-C2:R", "R", "leg b: capacity")),
    "P-C4": (("P-C4", "R", ""), ("P-C4:B", "B", "the fade")),
}
"""Loops drawn with two labels: label id, letter, and what the label marks."""
SHARED_LABELS: Final = {"P-R7": "R7"}
"""A phase 9 term drawn with its spec loop's label."""
LIMITS: Final[Mapping[str, tuple[str, str, tuple[tuple[str, str], ...]]]] = {
    "P-C5": ("limit:PriceFloor", "limit: price floor (C5)", (("VF.Anchor", "VF.PNew"), ("Disc", "VF.PNew"))),
    "P-C6": ("limit:AIDiscCeil", "limit: AI-discount ceiling (C6)", (("ClientP", "VF.Anchor"), ("VF.PU", "VF.Anchor"))),
    "R7": ("limit:R7Lcap", "limit: cap (R7Lcap)", (("GCCW", "GCCScaleTerm"),)),
}
"""Limit markers: the rule or loop, the marker's id and label, and the links it caps."""

ROLE_ITEMS: Final = frozenset({"SrcTarget", "SrcPerc", "CostOpt", "RiskOpt", "ShareL", "UnitIn"})
"""Option- or level-indexed items whose sign differs by role: a panel node per role."""
ROLES: Final[Mapping[tuple[str, str], str]] = {
    ("R7", "SrcTarget"): "GCC",
    ("R7", "SrcPerc"): "GCC",
    ("P-R7", "SrcTarget"): "GCC",
    ("P-R7", "SrcPerc"): "GCC",
    ("R10", "RiskOpt"): "vendor",
    ("R10", "SrcTarget"): "GCC",
    ("R10", "SrcPerc"): "GCC",
    ("B3", "CostOpt"): "IH",
    ("B3", "SrcTarget"): "IH",
    ("B3", "SrcPerc"): "IH",
    ("U2", "SrcTarget"): "IH",
    ("U2", "SrcPerc"): "IH",
    ("R6", "RiskOpt"): "vendor",
    ("R6", "SrcTarget"): "vendor",
    ("R6", "SrcPerc"): "vendor",
    ("P-C4", "RiskOpt"): "vendor",
    ("P-C4", "SrcTarget"): "vendor",
    ("P-C4", "SrcPerc"): "vendor",
    ("P-C6", "CostOpt"): "vendor",
    ("B12", "CostOpt"): "vendor",
    ("B12", "SrcTarget"): "vendor",
    ("B12", "SrcPerc"): "vendor",
    ("U1", "CostOpt"): "vendor",
    ("U1", "SrcTarget"): "vendor",
    ("U1", "SrcPerc"): "vendor",
    ("U4", "CostOpt"): "vendor",
    ("U4", "SrcTarget"): "vendor",
    ("U4", "SrcPerc"): "vendor",
    ("R5", "ShareL"): "junior",
    ("B4", "ShareL"): "junior",
    ("B7", "UnitIn"): "onshore",
}
"""The role of an option-indexed item in each loop's links (the signs in ``loops.csv`` are for that role)."""
ROLE_STEPS: Final[Mapping[tuple[str, str], str]] = {("R7", "4 drains vendor revenue"): "vendor"}
"""Steps whose role differs from their loop's: R7's cross effect on the vendors' targets."""
ROLE_LABELS: Final[Mapping[str, str]] = {
    "SrcTarget@GCC": "GCC's sourcing target",
    "SrcTarget@vendor": "A vendor's sourcing target",
    "SrcTarget@IH": "In-house sourcing target",
    "SrcPerc@GCC": "GCC's perceived share",
    "SrcPerc@vendor": "A vendor's perceived share",
    "SrcPerc@IH": "In-house perceived share",
    "CostOpt@IH": "In-house option cost",
    "CostOpt@vendor": "A vendor's option cost",
    "RiskOpt@vendor": "A vendor's option risk",
    "ShareL@junior": "Junior share of staff",
    "UnitIn@onshore": "Onshore unit work share",
}
STAFF: Final = ("V", "O", "H", "hires", "fl.onboard")
"""The vendor staff group of panels 2 and 3: the three hiring stocks and the flows between them."""
STAFF_ID: Final = "staff@vendor"
STAFF_LABEL: Final = "Vendor staff"


@dataclass(frozen=True)
class Cell:
    """A vertex: its id, wrapped label, style, kind (``node``, ``loop``, ``limit``, ``legend``, ``caption``,
    ``title``) and the model items it stands for."""

    id: str
    label: str
    style: str
    kind: str = "node"
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class Link:
    """An arrow between two cells, with its label (the sign) and the items' links it stands for."""

    source: str
    target: str
    label: str
    style: str
    via: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class View:
    """One diagram: its cells and links, and for each loop label the cells of its loop (for the first layout)."""

    name: str
    kind: str
    cells: tuple[Cell, ...]
    links: tuple[Link, ...]
    loop_cells: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    limit_links: Mapping[str, tuple[tuple[str, str], ...]] = field(default_factory=dict)
    homes: Mapping[str, str] = field(default_factory=dict)
    """On the model map: each node's module, whose region holds it (slice 10e)."""

    def cell(self, cid: str) -> Cell:
        return next(c for c in self.cells if c.id == cid)


# ---- reading --------------------------------------------------------------------------------------------------------


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@dataclass(frozen=True)
class Sources:
    """The metadata a view reads."""

    docs: Mapping[tuple[str, str], Mapping[str, str]]
    modules: Sequence[Mapping[str, str]]
    edges: Sequence[Mapping[str, str]]
    loops: Sequence[Mapping[str, str]]
    summary: Mapping[str, Mapping[str, str]]
    articles: Sequence[Mapping[str, str]]
    kinds: Mapping[str, str]
    pages: Sequence[Mapping[str, str]] = ()
    """``tools/module_pages.csv``: each module item's page."""
    levers: frozenset[str] = frozenset()
    """The lever parameters (``docs/model/inventory.csv``, ``lever`` "yes" or "yes (structural)")."""
    pipes: Sequence[Mapping[str, str]] = ()
    """``tools/flow_pipes.csv``: each flow's pipes (slice 10e)."""


PAGES_CSV: Final = Path("tools/module_pages.csv")
PIPES_CSV: Final = Path("tools/flow_pipes.csv")
"""Each flow's pipes (slice 10e), derived from the integration code: ``flow,from,to,also_drains,cite``. ``from`` and
``to`` are stocks (``;`` lists where a flow touches several) or ``cloud``; ``also_drains`` lists the stocks a flow only
reduces (vacancies filled); ``cite`` gives ``path:line[,line] (stock)`` for each stock touched, joined by ``"; "``. A
second line is a local alias's definition where the update line names only the alias (operator ruling)."""
"""Each item a module page draws, with its page (``page,name,kind``); a page's valves follow their stocks."""

KIND_ORDER: Final = ("stock", "flow", "auxiliary", "parameter", "table", "time")


def read_sources(root: Path = ROOT) -> Sources:
    docs = {(r["name"], r["kind"]): r for r in read_csv(root / DATA / "model_docs.csv")}
    edges = read_csv(root / MODEL / "edges.csv")
    seen: dict[str, set[str]] = collections.defaultdict(set)
    for e in edges:
        seen[e["source"]].add(e["source_kind"])
        seen[e["target"]].add(e["target_kind"])
    kinds = {n: min(ks, key=KIND_ORDER.index) for n, ks in seen.items()}
    return Sources(
        docs,
        read_csv(root / DATA / "model_modules.csv"),
        edges,
        read_csv(root / MODEL / "loops.csv"),
        {r["loop_id"]: r for r in read_csv(root / MODEL / "loop_summary.csv")},
        read_csv(root / DATA / "model_articles.csv"),
        kinds,
        read_csv(root / PAGES_CSV),
        frozenset(
            r["name"]
            for r in read_csv(root / MODEL / "inventory.csv")
            if r["kind"] == "parameter" and r["lever"].startswith("yes")
        ),
        read_csv(root / PIPES_CSV),
    )


def item_row(src: Sources, name: str) -> Mapping[str, str]:
    """An item's ``model_docs.csv`` row, by the kind the graph gives it."""
    kind = src.kinds.get(name)
    if kind is not None and (name, kind) in src.docs:
        return src.docs[(name, kind)]
    rows = [r for (n, k), r in src.docs.items() if n == name and k != "output"]
    if not rows:
        raise KeyError(f"no model_docs.csv row for {name!r}")
    return rows[0]


def signed_links(src: Sources) -> list[Mapping[str, str]]:
    """The ``loops.csv`` rows that are code links: sign +, - or unclear (``none`` marks a spec step with no code)."""
    return [r for r in src.loops if r["sign"] in ("+", "-", "unclear")]


# ---- labels and styles ----------------------------------------------------------------------------------------------


def wrap(label: str, width: int = WRAP, hyphens: bool = True) -> str:
    """A label wrapped at ``width``; module pages pass ``hyphens=False`` so that "phase-in" stays whole."""
    return "\n".join(textwrap.wrap(label, width, break_long_words=False, break_on_hyphens=hyphens)) or label


def text_size(label: str, font: float = 12.0, bold: bool = False) -> tuple[float, float]:
    """A box that holds ``label`` in Helvetica at ``font`` px, with padding (a generous estimate)."""
    lines = label.split("\n")
    per = font * (0.62 if bold else 0.58)
    return float(math.ceil(max(len(x) for x in lines) * per + 18)), float(math.ceil(len(lines) * font * 1.25 + 12))


def tint(hexc: str, a: float = 0.25) -> str:
    r, g, b = (int(hexc[i : i + 2], 16) for i in (1, 3, 5))
    return "#{:02X}{:02X}{:02X}".format(*(round(255 - (255 - c) * a) for c in (r, g, b)))


BASE: Final = "html=0;fontFamily=Helvetica;fontSize=12;"


def node_style(kind: str, colour: str) -> str:
    if kind == "stock":
        return BASE + f"rounded=0;fillColor={tint(colour)};strokeColor={colour};strokeWidth=2;fontColor=#1A1A1A;"
    if kind == "parameter":
        return BASE + "text;strokeColor=none;fillColor=none;fontStyle=2;fontColor=#555555;"
    if kind == "module":
        return BASE + f"rounded=1;fillColor={colour};strokeColor={colour};fontColor=#FFFFFF;fontStyle=1;fontSize=13;"
    return BASE + f"text;strokeColor=none;fillColor=none;fontStyle=1;fontColor={colour};"


LOOP_STYLE: Final = (
    BASE + "ellipse;fillColor=#FFFFFF;strokeColor=#333333;strokeWidth=1.5;fontStyle=1;fontColor=#1A1A1A;"
)
LIMIT_STYLE: Final = (
    BASE + "shape=hexagon;perimeter=hexagonPerimeter2;size=0.12;fillColor=#FFFFFF;strokeColor=#333333;"
    "fontSize=11;fontStyle=2;fontColor=#1A1A1A;"
)
LEGEND_STYLE: Final = (
    BASE + "text;align=left;verticalAlign=top;spacingLeft=8;spacingTop=4;fontSize=11;"
    "strokeColor=#999999;fillColor=#FAFAFA;fontColor=#333333;"
)
CAPTION_STYLE: Final = (
    BASE + "text;align=left;verticalAlign=top;fontSize=11;strokeColor=none;fillColor=none;fontColor=#333333;"
)
TITLE_STYLE: Final = BASE + "text;align=left;verticalAlign=top;fontSize=16;fontStyle=1;strokeColor=none;fillColor=none;"
EDGE_STYLE: Final = (
    "html=0;endArrow=classic;endSize=7;rounded=0;strokeColor=#444444;strokeWidth=1.2;fontFamily=Helvetica;"
    "fontSize=16;fontStyle=1;fontColor=#1A1A1A;labelBackgroundColor=#FFFFFF;"
)
LEGEND_LINES: Final = (
    ("", "Box: a stock. Bold text: an auxiliary. Colour: its module."),
    ("", "+ or - on an arrow: the link's polarity."),
    ("solid", "R / B circle: a reinforcing / balancing loop acting in Base."),
    ("hollow", "Dashed circle: weak in Base, or acting only in the stress set"),
    ("hollow", f"  '{STRESS_SET}'."),
    ("grey", "Grey circle: dormant in Base and in the stress set."),
    ("question", "? in a circle: the loop's sign depends on which path dominates."),
    ("open", "Dashed arrow: an open chain (no loop closes it)."),
    ("faded", "Faded arrow: every loop on it is dormant in Base."),
    ("limit", "Hexagon: a limit on the link beside it."),
)
"""The panels' legend: each line with the mark it explains ("" for every view); a view lists only the marks it
uses (Addendum C)."""


def view_marks(cells: Sequence[Cell], links: Sequence[Link]) -> set[str]:
    """The legend marks a view uses."""
    marks = {""}
    for c in cells:
        if c.kind == "limit":
            marks.add("limit")
        if c.kind == "loop":
            hollow, grey = "dashed=1" in c.style, "opacity=40" in c.style
            marks.add("hollow" if hollow else "grey" if grey else "solid")
            if c.label.startswith("?"):
                marks.add("question")
    for lk in links:
        if "dashPattern=8 4" in lk.style:
            marks.add("open")
        if "opacity=45" in lk.style:
            marks.add("faded")
    return marks


def legend_for(lines: Sequence[tuple[str, str]], cells: Sequence[Cell], links: Sequence[Link]) -> list[str]:
    marks = view_marks(cells, links)
    return [text for mark, text in lines if mark in marks]


def caption_cells(captions: Sequence[str]) -> list[Cell]:
    return [Cell(f"caption:{i}", c, CAPTION_STYLE, "caption") for i, c in enumerate(captions, start=1)]


def chrome(title: str, legend: Sequence[str], captions: Sequence[str]) -> list[Cell]:
    """The title, legend and captions of a view."""
    out = [Cell("title", title, TITLE_STYLE, "title")]
    if legend:
        out.append(Cell("legend", "\n".join(legend), LEGEND_STYLE, "legend"))
    return out + caption_cells(captions)


# ---- the overview ---------------------------------------------------------------------------------------------------

STATE_KINDS: Final = ("stock", "flow", "auxiliary")


def module_pairs(src: Sources) -> dict[tuple[str, str], int]:
    """Cross-module links with a stock, flow or auxiliary source (a parameter belongs to its reader), by pair."""
    c: collections.Counter[tuple[str, str]] = collections.Counter()
    for e in src.edges:
        a, b = e["module_from"], e["module_to"]
        if a and b and a != b and e["source_kind"] in STATE_KINDS:
            c[(a, b)] += 1
    return dict(sorted(c.items()))


def overview(src: Sources) -> View:
    mods = {m["module"]: m for m in src.modules}
    cells = [
        Cell(m, wrap(r["display_name"], 16), node_style("module", r["colour"]), "node", ()) for m, r in mods.items()
    ]
    links = []
    for (a, b), n in module_pairs(src).items():
        st = EDGE_STYLE.replace("strokeWidth=1.2;", f"strokeWidth={1 + 0.35 * (n - 1):.2f};")
        st = st.replace("strokeColor=#444444;", f"strokeColor={mods[a]['colour']};").replace(
            "fontSize=16;", "fontSize=12;"
        )
        if n == 1:
            st += "dashed=1;opacity=60;"
        links.append(Link(a, b, str(n), st))
    legend = (
        "Each arrow: the links from one module's stocks, flows and auxiliaries",
        "to items of another; its label and width give their number.",
        "Dashed: a single link. Parameters count with the module that reads them.",
    )
    pairs = module_pairs(src)
    captions = (
        f"{len(mods)} modules, {len(pairs)} module pairs, {sum(pairs.values())} links between modules "
        "(docs/model/edges.csv).",
    )
    return View(
        "overview", "overview", (*cells, *chrome("Overview: the model's eight modules", legend, captions)), tuple(links)
    )


# ---- the causal-loop panels -----------------------------------------------------------------------------------------


def role_of(row: Mapping[str, str], item: str) -> str | None:
    """The role of an option-indexed item in a ``loops.csv`` row, or None for any other item."""
    if item not in ROLE_ITEMS:
        return None
    step = ROLE_STEPS.get((row["loop_id"], row["step"]))
    if step is not None:
        return step
    try:
        return ROLES[(row["loop_id"], item)]
    except KeyError:
        raise KeyError(f"no role for {item} in loop {row['loop_id']} (step {row['step']!r})") from None


@dataclass
class _Link:
    signs: set[str]
    loops: set[str]
    via: list[tuple[str, str]]


def panel_rows(src: Sources, spec: PanelSpec) -> list[Mapping[str, str]]:
    """A panel's link rows: the on-cycle links of its loops, and the links of its open chains and rules (replaced
    loops are noted, not drawn)."""
    ids = {k for k, r in src.summary.items() if r["panel"] == spec.key and r["status"] != "replaced"}
    return [
        r
        for r in signed_links(src)
        if r["loop_id"] in ids and (r["on_cycle"] == "yes" or r["status"] in ("open", "rule (not a loop)"))
    ]


def panel_graph(src: Sources, spec: PanelSpec) -> dict[tuple[str, str], _Link]:
    """The panel's links between cells: roles split, the vendor staff grouped, pass-through cells collapsed."""

    def cell_of(row: Mapping[str, str], item: str) -> str:
        role = role_of(row, item)
        if role is not None:
            return f"{item}@{role}"
        if spec.collapse_staff and item in STAFF:
            return STAFF_ID
        return item

    g: dict[tuple[str, str], _Link] = {}
    for r in panel_rows(src, spec):
        a, b = cell_of(r, r["source"]), cell_of(r, r["target"])
        if a == b:
            continue
        sign = "?" if r["sign"] == "unclear" else r["sign"]
        e = g.setdefault((a, b), _Link(set(), set(), []))
        e.signs.add(sign)
        e.loops.add(r["loop_id"])
        if (r["source"], r["target"]) not in e.via:
            e.via.append((r["source"], r["target"]))
    mixed = sorted(k for k, e in g.items() if len(e.signs) > 1)
    if mixed:
        raise ValueError(f"panel {spec.key}: links with two signs {mixed}")

    def is_stock(n: str) -> bool:
        return n == STAFF_ID or src.kinds.get(n.split("@")[0]) == "stock"

    changed = True
    while changed:
        changed = False
        nodes = sorted({n for k in g for n in k})
        for n in nodes:
            ins = [k for k in g if k[1] == n]
            outs = [k for k in g if k[0] == n]
            if is_stock(n) or n in spec.keep or len(ins) != 1 or len(outs) != 1:
                continue
            (a, _), (_, b) = ins[0], outs[0]
            e1, e2 = g[ins[0]], g[outs[0]]
            s1, s2 = next(iter(e1.signs)), next(iter(e2.signs))
            if a == b or "?" in (s1, s2):
                continue
            s = "+" if s1 == s2 else "-"
            if (a, b) in g and g[(a, b)].signs != {s}:
                continue
            del g[ins[0]], g[outs[0]]
            e = g.setdefault((a, b), _Link({s}, set(), []))
            e.loops |= e1.loops | e2.loops
            e.via += [v for v in e1.via + e2.via if v not in e.via]
            changed = True
            break
    return dict(sorted(g.items()))


def loop_letter(row: Mapping[str, str]) -> str:
    if row["loop_id"] in QUESTION_LOOPS:
        return "?"
    pol = row["code_polarity"].split()[0].strip(":,(").lower()
    return {"reinforcing": "R", "balancing": "B"}.get(pol, "?")


def is_dormant(row: Mapping[str, str]) -> bool:
    return row["acts_phase9_base"].startswith("no")


def panel(src: Sources, view: str) -> View:
    spec = PANEL_VIEWS[view]
    g = panel_graph(src, spec)
    names = sorted({n for k in g for n in k})
    cells: list[Cell] = []
    items: tuple[str, ...]
    for n in names:
        item = n.split("@")[0]
        if n == STAFF_ID:
            row, label, items = item_row(src, "H"), STAFF_LABEL, STAFF
        else:
            row = item_row(src, item)
            label, items = ROLE_LABELS.get(n, row["label"]), (item,)
        colour = next(m["colour"] for m in src.modules if m["module"] == row["module"])
        kind = "stock" if n == STAFF_ID else src.kinds.get(item, row["kind"])
        cells.append(Cell(n, wrap(label), node_style(kind, colour), "node", items))
    links = []
    for (a, b), e in g.items():
        rows = [src.summary[x] for x in sorted(e.loops)]
        st = EDGE_STYLE
        if all(r["status"] == "open" for r in rows):
            st += "dashed=1;dashPattern=8 4;"
        if all(is_dormant(r) for r in rows):
            st += "opacity=45;textOpacity=60;"
        capped = [lid for lid, (_, _, ls) in LIMITS.items() if any(v in ls for v in e.via)]
        if capped:
            st += "strokeWidth=2.4;"
        links.append(Link(a, b, next(iter(e.signs)), st, tuple(e.via)))
    loop_cells: dict[str, tuple[str, ...]] = {}
    limit_links: dict[str, tuple[tuple[str, str], ...]] = {}
    ids = sorted(k for k, r in src.summary.items() if r["panel"] == spec.key)
    for lid in ids:
        r = src.summary[lid]
        members = tuple(sorted({n for k, e in g.items() if lid in e.loops for n in k}))
        if lid in LIMITS:
            mid, mlabel, ls = LIMITS[lid]
            capped_links = tuple(k for k, e in g.items() if any(v in ls for v in e.via))
            if capped_links:
                cells.append(Cell(mid, wrap(mlabel, 22), LIMIT_STYLE, "limit", (mid.split(":", 1)[1],)))
                limit_links[mid] = capped_links
        mark = r["diagram_mark"]
        if lid in SHARED_LABELS or r["status"] in ("open", "replaced", "rule (not a loop)") or not members:
            continue
        style = LOOP_STYLE
        if mark.startswith("hollow"):
            style += "dashed=1;"
        elif mark.startswith("grey"):
            style += "opacity=40;textOpacity=50;"
        for cid, letter in [(c, lt) for c, lt, _ in SPLIT_LABELS.get(lid, ((lid, loop_letter(r), ""),))]:
            cells.append(Cell(cid, f"{letter}\n{lid}", style, "loop", (lid,)))
            loop_cells[cid] = members
    for lid, (mid, mlabel, ls) in LIMITS.items():
        if lid not in ids and mid not in limit_links:
            capped_links = tuple(k for k, e in g.items() if any(v in ls for v in e.via))
            if capped_links:
                cells.append(Cell(mid, wrap(mlabel, 22), LIMIT_STYLE, "limit", (mid.split(":", 1)[1],)))
                limit_links[mid] = capped_links
    cells += chrome(spec.title, legend_for(LEGEND_LINES, cells, links), spec.captions)
    return View(view, "panel", tuple(cells), tuple(links), loop_cells, limit_links)


# ---- the articles ---------------------------------------------------------------------------------------------------

ARTICLE_LEGEND: Final = (
    ("", "+ or - on an arrow: the link's polarity."),
    ("solid", "R / B circle: a reinforcing / balancing loop."),
    ("", "Box: a stock (it accumulates). Bold text: everything else."),
    ("limit", "Hexagon: a limit on the link beside it."),
)


def article_rows(src: Sources, art: str, part: str) -> list[Mapping[str, str]]:
    return [r for r in src.articles if r["article"] == art and r["part"] == part]


def split_items(s: str) -> tuple[str, ...]:
    return tuple(x for x in s.split(";") if x)


def article(src: Sources, view: str) -> View:
    art = ARTICLE_VIEWS[view]
    story = article_rows(src, art, "story")[0]
    cells: list[Cell] = []
    for r in article_rows(src, art, "node"):
        items = split_items(r["items"])
        rows = [item_row(src, i) for i in items]
        stock = any(src.kinds.get(i) == "stock" for i in items)
        colour = next(m["colour"] for m in src.modules if m["module"] == rows[0]["module"])
        cells.append(
            Cell(r["id"], wrap(r["label"]), node_style("stock" if stock else "auxiliary", colour), "node", items)
        )
    links = [
        Link(
            r["source"],
            r["target"],
            r["sign"],
            EDGE_STYLE
            + (
                "strokeWidth=2.4;"
                if any(
                    lr["source"] == r["source"] and lr["target"] == r["target"]
                    for lr in article_rows(src, art, "limit")
                )
                else ""
            ),
            tuple(zip(r["path"].split(" > "), r["path"].split(" > ")[1:], strict=False)),
        )
        for r in article_rows(src, art, "link")
    ]
    loop_cells: dict[str, tuple[str, ...]] = {}
    for r in article_rows(src, art, "loop"):
        cells.append(Cell(r["id"], f"{r['sign']}\n{wrap(r['label'], 14)}", LOOP_STYLE, "loop", split_items(r["items"])))
        loop_cells[r["id"]] = tuple(sorted(set(r["path"].split(" > "))))
    limit_links: dict[str, tuple[tuple[str, str], ...]] = {}
    for r in article_rows(src, art, "limit"):
        cells.append(Cell(r["id"], wrap(r["label"], 22), LIMIT_STYLE, "limit", split_items(r["items"])))
        limit_links[r["id"]] = ((r["source"], r["target"]),)
    legend = legend_for(ARTICLE_LEGEND, cells, links)
    cells += chrome(f"{art}. {story['label']}", legend, ["\n".join(textwrap.wrap(story["story"], 90))])
    return View(view, "article", tuple(cells), tuple(links), loop_cells, limit_links)


# ---- the module pages -----------------------------------------------------------------------------------------------

PAGE_KINDS: Final = ("stock", "flow", "auxiliary")
REFERENCE_STOCKS: Final = ("WS0", "Attr0", "Dur0")
"""Loop state families set once, on the first step, to a 2024 reference (``loops.pre``): no flow enters them, so a
flow they read is an input, not a pipe."""
COFLOWS: Final = frozenset({"NewD", "NewP"})
"""Stocks whose one unnamed flow is a coflow of the contract book, not a goal-seeking adjustment: their whole update
reads the signings and expiries (``integrate.py:122-123``; operator ruling, slice 10c)."""
NO_POLARITY: Final = (
    "Arrows show dependence only and carry no polarity: signs are on the causal-loop panels (panels 1-5) and in "
    "docs/model/loops.csv."
)
MODULE_WRAP: Final = 80
"""A module page's legend and captions wrap at 80 characters, side by side under the drawing."""
GHOST_STYLE: Final = BASE + "text;strokeColor=none;fillColor=none;fontSize=11;fontColor=#808080;"
REF_STYLE: Final = BASE + "text;rounded=1;dashed=1;strokeColor=#A0A0A0;fillColor=none;fontSize=11;fontColor=#808080;"
PIPE_STYLE: Final = "html=0;endArrow=block;endSize=6;rounded=0;strokeColor=#7A7A7A;strokeWidth=3;"
INFO_STYLE: Final = "html=0;endArrow=classic;endSize=6;rounded=0;strokeColor=#555555;strokeWidth=1;"
VALVE_W: Final = 24.0
VALVE_H: Final = 22.0
"""A valve's drawn shape; its sidecar box is the shape and the label below it."""
MODULE_LEGEND: Final = (
    ("stock", "Box: a stock."),
    ("valve", "Hourglass: a flow (its valve), named below."),
    ("auxiliary", "Bold coloured text: an auxiliary."),
    ("lever", "Grey italic: a lever parameter."),
    ("pipe", "Thick arrow: a flow changing the stock it points to."),
    ("", "Thin arrow: an input of the item it points to."),
    ("ghost", "Grey text, (module): an input from another module."),
    ("ref", "Dashed grey box, (page): an input from another page of this module."),
)
"""The module pages' legend: each part with the mark it explains ("" for every page), run together and wrapped."""

Item = tuple[str, str]
"""A model item: (name, kind)."""


def valve_style(colour: str) -> str:
    return (
        BASE + f"shape=mxgraph.flowchart.collate;fillColor={tint(colour)};strokeColor={colour};strokeWidth=1.5;"
        "verticalLabelPosition=bottom;verticalAlign=top;labelPosition=center;align=center;fontColor=#1A1A1A;"
        "labelBackgroundColor=#FFFFFF;"
    )


def module_items(src: Sources) -> dict[Item, str]:
    """Every item a module page draws, with its module from ``model_docs.csv``: stocks, named flows, auxiliaries and
    lever parameters. A stock's unnamed flow ``flow:<stock>`` is its valve and follows the stock."""
    return {
        (n, k): r["module"]
        for (n, k), r in sorted(src.docs.items())
        if not n.startswith("flow:") and (k in PAGE_KINDS or (k == "parameter" and n in src.levers))
    }


def page_assignment(src: Sources) -> dict[str, list[Item]]:
    """Each page's items (``tools/module_pages.csv``). Raises ``ValueError`` listing every unassigned item, every item
    assigned twice, and every row that names an unknown page, an item no module page draws or an item of another
    module."""
    items = module_items(src)
    mods = {p.key: p.modules for p in MODULE_PAGES}
    seen: dict[Item, str] = {}
    bad = []
    for r in src.pages:
        key, page = (r["name"], r["kind"]), r["page"]
        if page not in mods:
            bad.append(f"{key[0]} ({key[1]}): unknown page {page!r}")
        elif key not in items:
            bad.append(f"{key[0]} ({key[1]}) on {page}: not an item a module page draws")
        elif items[key] not in mods[page]:
            bad.append(f"{key[0]} ({key[1]}) on {page}: a {items[key]} item")
        elif key in seen:
            bad.append(f"{key[0]} ({key[1]}) assigned twice: {seen[key]} and {page}")
        else:
            seen[key] = page
    bad += [f"{n} ({k}) unassigned" for n, k in sorted(set(items) - set(seen))]
    if bad:
        raise ValueError("module pages: " + "; ".join(bad))
    out: dict[str, list[Item]] = {p.key: [] for p in MODULE_PAGES}
    for key, page in seen.items():
        out[page].append(key)
    return {k: sorted(v) for k, v in out.items()}


def valve_stocks(src: Sources) -> dict[str, str]:
    """Each stock with an unnamed flow ``flow:<stock>``, and whether that flow is ``goal-seeking`` or a ``coflow``.
    Raises if a goal-seeking stock's update also reads a named flow, so that it would have two flow items (the
    operator's stop rule)."""
    stocks = {n[5:] for n, _ in src.docs if n.startswith("flow:")}
    two = sorted(
        {
            e["target"]
            for e in src.edges
            if e["target"] in stocks - COFLOWS and e["target_kind"] == "stock" and e["source_kind"] == "flow"
        }
    )
    if two:
        raise ValueError(f"stocks whose update has more than one flow item: {two}")
    return {s: "coflow" if s in COFLOWS else "goal-seeking" for s in sorted(stocks)}


def name_clashes(src: Sources) -> set[str]:
    """Names shared by two items that module pages draw (``Att``: a stock and an auxiliary)."""
    names = collections.Counter(n for n, _ in module_items(src))
    return {n for n, c in names.items() if c > 1}


JS_NAMES: Final = frozenset(
    {
        "__proto__", "apply", "arguments", "at", "bind", "call", "caller", "concat", "constructor", "copyWithin",
        "entries", "every", "fill", "filter", "find", "findIndex", "findLast", "findLastIndex", "flat", "flatMap",
        "forEach", "hasOwnProperty", "includes", "indexOf", "isPrototypeOf", "join", "keys", "lastIndexOf", "length",
        "map", "name", "pop", "propertyIsEnumerable", "prototype", "push", "reduce", "reduceRight", "reverse", "shift",
        "slice", "some", "sort", "splice", "toLocaleString", "toReversed", "toSorted", "toSpliced", "toString",
        "unshift", "valueOf", "values", "with",
    }
)  # fmt: skip
"""JavaScript prototype members. draw.io keeps cells in an object keyed by id, and a cell whose id is one of these
(the auxiliary ``push``) makes its export fail, printing "Export failed" but exiting 0 (slice 10c)."""


def cell_id(item: Item, clashes: set[str]) -> str:
    """A module page's cell id for an item: its name, or ``name#kind`` where two drawn items share the name or the
    name is a JavaScript prototype member (``JS_NAMES``)."""
    return f"{item[0]}#{item[1]}" if item[0] in clashes or item[0] in JS_NAMES else item[0]


def page_item(src: Sources, cid: str) -> Item:
    """The item a module page's cell id stands for (a ghost or page-reference id without its prefix)."""
    cid = cid.split(":", 1)[1] if cid.startswith(("ghost:", "ref:")) else cid
    if cid.startswith("flow:"):
        return (cid, "flow")
    if "#" in cid:
        n, k = cid.split("#", 1)
        return (n, k)
    kinds = [k for n, k in module_items(src) if n == cid]
    if len(kinds) != 1:
        raise KeyError(f"no single module item named {cid!r}")
    return (cid, kinds[0])


def module_page(src: Sources, view: str) -> View:
    """A stock-and-flow page (slice 10c): the page's items, its stocks' valves, ghost inputs from other modules and
    page references to the module's other pages; arrows without signs. Every input of a stock's unnamed flow points
    at its valve, and the valve's pipe at the stock (operator rulings)."""
    spec = MODULE_VIEWS[view]
    assign = page_assignment(src)
    items = module_items(src)
    clashes = name_clashes(src)
    valves = valve_stocks(src)
    page_of = {it: p for p, its in assign.items() for it in its}
    short = {p.key: p.short for p in MODULE_PAGES}
    colours = {m["module"]: m["colour"] for m in src.modules}
    members = assign[spec.key]
    ids = {it: cell_id(it, clashes) for it in members}
    stocks = sorted(n for n, k in members if k == "stock" and n in valves)

    def target_cell(n: str, k: str) -> str | None:
        if (n, k) not in ids:
            return None
        return f"flow:{n}" if k == "stock" and n in stocks else ids[(n, k)]

    pairs: dict[tuple[str, str], str] = {}
    outside: dict[str, tuple[Item, str]] = {}
    for e in src.edges:
        tgt = target_cell(e["target"], e["target_kind"])
        sitem = (e["source"], e["source_kind"])
        if tgt is None:
            continue
        if sitem in ids:
            sid = ids[sitem]
        elif sitem in items and sitem[1] in PAGE_KINDS:
            if items[sitem] in spec.modules:
                sid = f"ref:{cell_id(sitem, clashes)}"
                outside[sid] = (sitem, short[page_of[sitem]])
            else:
                sid = f"ghost:{cell_id(sitem, clashes)}"
                outside[sid] = (sitem, items[sitem].replace("_", " "))
        else:
            continue
        if sid != tgt:
            pairs[(sid, tgt)] = sitem[1]
    for s in stocks:
        pairs[(f"flow:{s}", s)] = "flow"

    drawn = [*members, *((f"flow:{s}", "flow") for s in stocks), *(it for it, _ in outside.values())]
    labels = collections.Counter(src.docs[it]["label"] for it in drawn)

    def label_of(it: Item) -> str:
        lab = src.docs[it]["label"]
        return lab + (f" ({it[1]})" if labels[lab] > 1 else "")

    cells: list[Cell] = []
    marks = {""}
    for it in [*members, *((f"flow:{s}", "flow") for s in stocks)]:
        stock_of = it[0][5:] if it[0].startswith("flow:") else None
        colour = colours[items[(stock_of, "stock")] if stock_of else items[it]]
        cid = it[0] if stock_of else ids[it]
        if it[1] == "flow":
            cells.append(Cell(cid, wrap(label_of(it), hyphens=False), valve_style(colour), "valve", (it[0],)))
            marks.add("valve")
        else:
            cells.append(Cell(cid, wrap(label_of(it), hyphens=False), node_style(it[1], colour), "node", (it[0],)))
            marks.add("lever" if it[1] == "parameter" else it[1])
    for sid in sorted(outside):
        it, where = outside[sid]
        kind = "ref" if sid.startswith("ref:") else "ghost"
        style = REF_STYLE if kind == "ref" else GHOST_STYLE
        cells.append(Cell(sid, f"{wrap(label_of(it), hyphens=False)}\n({where})", style, kind, (it[0],)))
        marks.add(kind)
    stock_ids = {ids[it] for it in members if it[1] == "stock" and it[0] not in REFERENCE_STOCKS}
    links = []
    for (a, b), skind in sorted(pairs.items()):
        pipe = skind == "flow" and b in stock_ids
        marks |= {"pipe"} if pipe else set()
        links.append(Link(a, b, "", PIPE_STYLE if pipe else INFO_STYLE))
    captions = ["\n".join(textwrap.wrap(NO_POLARITY, MODULE_WRAP))]
    for kind, text in (
        ("goal-seeking", "Goal-seeking valves (a stock adjusting toward a target; every input points at the valve)"),
        ("coflow", "Coflow valves (the contract book's whole update in one flow, reading the signings and expiries)"),
    ):
        names = sorted(src.docs[(f"flow:{s}", "flow")]["label"] for s in stocks if valves[s] == kind)
        if names:
            captions.append("\n".join(textwrap.wrap(f"{text}: {', '.join(names)}.", MODULE_WRAP)))
    legend = textwrap.wrap(" ".join(t for m, t in MODULE_LEGEND if m in marks), MODULE_WRAP)
    cells += chrome(spec.title, legend, captions)
    return View(view, "module", tuple(cells), tuple(links))


# ---- the model map (slice 10e) --------------------------------------------------------------------------------------

CLOUD: Final = "cloud"
INTEGRATION: Final[Mapping[Path, str]] = {
    Path("src/aisim/scalar/integrate.py"): "integrate",
    Path("src/aisim/scalar/loops.py"): "post",
}
"""The functions that update the stocks (``integrate`` calls ``loops.post`` last); the cites point into them."""
WITHIN: Final[Mapping[str, tuple[tuple[str, ...], str]]] = {
    "conv": (("conv",), "within Headcount: visa to local"),
    "promo": (("promo", "fl.promo_out"), "within Headcount: junior to senior"),
    "sw.in": (("sw.in", "sw.out"), "within Headcount: between employers"),
}
"""Flows that move staff between members of Headcount (``from`` = ``to`` = ``H``), each group drawn as one valve
attached to Headcount, labelled with its flow's label and its note in brackets (operator rulings, slice 10e and
10e Addendum B: "Promotions (within Headcount: junior to senior)"). A group's flows are equal in total at every step:
``fl.promo_out`` is the next level's ``promo`` (``labour_market.py:204``) and each switch is one employer's ``in`` and
another's ``out`` (``labour_market.py:157-163``); ``test_within_headcount_valves_conserve`` checks it on a run."""
WIDE: Final = 4
"""A lever reaching more than this many stocks and flows is drawn with one arrow per other module (operator ruling)."""
MAP_TITLE: Final = "The model map: every stock, flow and lever, by module"
MAP_WRAP: Final = 110
MAP_FONT: Final = 12
REGION_PAD: Final = 16.0
REGION_HEAD: Final = 30.0
"""A region's padding around its nodes, and the extra room above them for its label."""
CLOUD_W: Final = 34.0
CLOUD_H: Final = 22.0
PIPE_IN_STYLE: Final = "html=0;endArrow=none;rounded=0;strokeColor=#7A7A7A;strokeWidth=3;"
"""A pipe from a stock or cloud into a valve; ``PIPE_STYLE`` (with its arrowhead) leads from the valve on."""
ATTACH_STYLE: Final = (
    "html=0;endArrow=none;startArrow=none;rounded=0;strokeColor=#7A7A7A;strokeWidth=3;dashed=1;dashPattern=2 2;"
)
DRAIN_STYLE: Final = "html=0;endArrow=open;endSize=8;rounded=0;strokeColor=#7A7A7A;strokeWidth=1.2;"
LEVER_STYLE: Final = (
    "html=0;endArrow=classic;endSize=6;rounded=0;strokeColor=#666666;strokeWidth=1;dashed=1;dashPattern=6 4;"
)
REGION_ARROW_STYLE: Final = (
    LEVER_STYLE.replace("strokeWidth=1;", "strokeWidth=1.4;")
    + f"fontFamily=Helvetica;fontSize={MAP_FONT};fontStyle=2;fontColor=#444444;labelBackgroundColor=#FFFFFF;"
)
CLOUD_STYLE: Final = BASE + "shape=cloud;fillColor=#FFFFFF;strokeColor=#7A7A7A;strokeWidth=1.2;"
MAP_LEGEND_STYLE: Final = LEGEND_STYLE.replace("fontSize=11;", f"fontSize={MAP_FONT};")
MAP_CAPTION_STYLE: Final = CAPTION_STYLE.replace("fontSize=11;", f"fontSize={MAP_FONT};")
MAP_TITLE_STYLE: Final = TITLE_STYLE.replace("fontSize=16;", "fontSize=20;")
MAP_LEGEND: Final = (
    "Tinted panel: a module. Box: a stock. Hourglass: a flow (its valve), named below. Cloud: a source or sink"
    " outside the model's stocks.",
    "Thick arrow (a pipe): what a flow moves, from a stock or cloud through its valve into a stock. A flow that only"
    " reduces a stock as it moves people (vacancies filled) has a thin arrow from its valve to that stock.",
    "Dotted thick line: a valve whose flow moves staff between members of Headcount (promotion, switching between"
    " employers, visa to local), so nothing enters or leaves Headcount.",
    "Grey italic: a lever. Dashed arrow: the first stocks and flows the lever reaches through auxiliaries"
    " (docs/model/edges.csv).",
    f"A lever reaching more than {WIDE} has one dashed arrow per other module, labelled with the lever and its count"
    ' there, and "(acts on N in this module)" for its own module;',
    'the model guide\'s table "Where the wide levers act" (docs/model-guide.md) lists the targets.',
)
MAP_CAPTIONS: Final = (
    "Left out: the auxiliaries, the parameters that are not levers, and the information links between stocks. The"
    " module pages and the causal-loop panels show them (docs/model-reference.pdf, docs/model/diagrams/).",
    "Pipes: tools/flow_pipes.csv, each cited to the line of the integration code that fills or drains the stock.",
    "Sourcing choice: In-house, GCC and vendor work are shares of one total: work released by turnover and contract"
    " expiry is re-sourced among the three. The clouds on these flows stand for that common pool.",
)
"""The map's captions. The third is the sourcing note of 10e Addendum A (operator ruling): the three shares conserve
together (``IHW + GCCW + VW``, slice 10e R4). It belongs in the sourcing region, but no spot there is clear of every
box, drawn path and label, so it sits in the caption block, as the ruling allows."""


@dataclass(frozen=True)
class Pipe:
    """A row of ``tools/flow_pipes.csv``: the flow, its source and sink stocks (``CLOUD`` for outside the model),
    the stocks it only drains, and its cites as (path, lines, stock)."""

    flow: str
    sources: tuple[str, ...]
    sinks: tuple[str, ...]
    drains: tuple[str, ...]
    cites: tuple[tuple[str, tuple[int, ...], str], ...]

    @property
    def within(self) -> bool:
        """Whether the flow moves stock between members of one stock (``from`` = ``to``)."""
        return self.sources == self.sinks and CLOUD not in self.sources


CITE: Final = re.compile(r"^(?P<path>[^:]+):(?P<lines>\d+(?:,\d+)*) \((?P<stock>[^()]+)\)$")


def _split(s: str) -> tuple[str, ...]:
    return tuple(x for x in s.split(";") if x)


def pipe_rows(src: Sources) -> dict[str, Pipe]:
    """``tools/flow_pipes.csv`` by flow. Raises ``ValueError`` listing every unknown or missing flow, flow listed
    twice, unknown stock, ``cloud`` mixed with stocks or in ``also_drains``, malformed cite, and stock touched without
    a cite or cited without a touch."""
    stocks = {n for n, k in src.docs if k == "stock"}
    flows = [n for n, k in src.docs if k == "flow"]
    out: dict[str, Pipe] = {}
    bad = []
    for r in src.pipes:
        f = r["flow"]
        if f not in flows:
            bad.append(f"{f}: not a flow")
            continue
        if f in out:
            bad.append(f"{f}: listed twice")
            continue
        ends = (_split(r["from"]), _split(r["to"]))
        drains = _split(r["also_drains"])
        for name, side in (("from", ends[0]), ("to", ends[1])):
            if not side or (CLOUD in side and len(side) > 1):
                bad.append(f"{f}: {name} {';'.join(side)!r}")
        unknown = sorted({s for s in (*ends[0], *ends[1], *drains) if s != CLOUD and s not in stocks})
        if unknown or CLOUD in drains:
            bad.append(f"{f}: unknown stocks {unknown or [CLOUD]}")
        cites = []
        for c in (x.strip() for x in r["cite"].split(";") if x.strip()):
            m = CITE.match(c)
            if m is None:
                bad.append(f"{f}: cite {c!r}")
                continue
            cites.append((m["path"], tuple(int(x) for x in m["lines"].split(",")), m["stock"]))
        touched = {s for s in (*ends[0], *ends[1], *drains) if s != CLOUD}
        if {c[2] for c in cites} != touched:
            bad.append(f"{f}: cites {sorted({c[2] for c in cites})} for stocks {sorted(touched)}")
        out[f] = Pipe(f, ends[0], ends[1], drains, tuple(cites))
    bad += [f"{f}: no row" for f in sorted(set(flows) - set(out))]
    if bad:
        raise ValueError(f"{PIPES_CSV.as_posix()}: " + "; ".join(bad))
    return {f: out[f] for f in sorted(out)}


def code_name(flow: str) -> str:
    """A flow's identifier in the integration code: the stock of ``flow:<stock>``, else the name's last segment
    (``fl.quits`` -> ``quits``, ``sw.in`` -> ``in``)."""
    return flow[5:] if flow.startswith("flow:") else flow.rsplit(".", 1)[-1]


def _named(node: ast.AST) -> set[str]:
    """The names, attributes and string keys an expression uses."""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _terms(node: ast.expr, sign: int = 1) -> list[tuple[int, ast.expr]]:
    """An expression's additive terms with their signs; a product or quotient with a one-term factor carries the
    other factor's terms (``d * (a - b) / T`` gives ``+a``, ``-b``)."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        flip = -sign if isinstance(node.op, ast.Sub) else sign
        return _terms(node.left, sign) + _terms(node.right, flip)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return _terms(node.operand, -sign)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Mult, ast.Div)):
        lt, rt = _terms(node.left), _terms(node.right)
        if len(rt) == 1 and (isinstance(node.op, ast.Div) or len(lt) > 1):
            return [(s * rt[0][0] * sign, n) for s, n in lt]
        if len(lt) == 1 and isinstance(node.op, ast.Mult) and len(rt) > 1:
            return [(s * lt[0][0] * sign, n) for s, n in rt]
        return [(sign * lt[0][0] * rt[0][0] if len(lt) == len(rt) == 1 else sign, node)]
    return [(sign, node)]


@dataclass(frozen=True)
class Update:
    """One augmented assignment to a stock in the integration code: the stock, its file and lines, and its terms with
    their signs and the names each uses (local aliases expanded)."""

    stock: str
    path: Path
    first: int
    last: int
    terms: tuple[tuple[int, frozenset[str]], ...]


def _function(root: Path, path: Path) -> ast.FunctionDef:
    tree = ast.parse((root / path).read_text(encoding="utf-8"))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == INTEGRATION[path])


def local_aliases(root: Path, path: Path) -> dict[str, set[str]]:
    """The single-name assignments of an integration function, each with the names its value uses
    (``promo_in = promo[u][l]`` gives ``promo_in``: ``promo``, ``u``, ``l``)."""
    alias: dict[str, set[str]] = {}
    for n in ast.walk(_function(root, path)):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            alias[n.targets[0].id] = _named(n.value)
    return alias


def stock_updates(root: Path = ROOT) -> list[Update]:
    """Every ``st["<stock>"]... += ...`` in ``INTEGRATION``'s functions, with each name a term uses expanded through
    the function's single-name assignments (``promo_in = promo[u][l]``)."""
    out = []
    for path in INTEGRATION:
        func = _function(root, path)
        alias = local_aliases(root, path)
        for n in ast.walk(func):
            if not (isinstance(n, ast.AugAssign) and isinstance(n.op, ast.Add)):
                continue
            base: ast.expr = n.target
            while isinstance(base, ast.Subscript) and not (isinstance(base.value, ast.Name) and base.value.id == "st"):
                base = base.value
            if not (isinstance(base, ast.Subscript) and isinstance(base.slice, ast.Constant)):
                continue
            terms = []
            for s, t in _terms(n.value):
                names = _named(t)
                names |= {x for a in names & alias.keys() for x in alias[a]}
                terms.append((s, frozenset(names)))
            out.append(Update(str(base.slice.value), path, n.lineno, n.end_lineno or n.lineno, tuple(terms)))
    return out


def _line_names(text: str) -> set[str]:
    """The non-keyword names and the string constants of one line of code."""
    out: set[str] = set()
    for tok in tokenize.generate_tokens(iter([text + "\n"]).__next__):
        if tok.type == tokenize.NAME and not keyword.iskeyword(tok.string):
            out.add(tok.string)
        elif tok.type == tokenize.STRING:
            out.add(ast.literal_eval(tok.string))
    return out


def cite_problems(root: Path, src: Sources) -> list[str]:
    """Cites that do not show their flow at work (strict, 10e Addendum B): every cited line must name the flow's
    identifier (``code_name``) or a local alias of it (``local_aliases``); one cited line inside an update of the
    cited stock must name it; and the flow's term there must carry the table's direction (added for ``to``,
    subtracted for ``from`` and ``also_drains``; either for a flow within one stock). A goal-seeking or coflow flow
    ``flow:<stock>`` is its stock's whole update."""
    updates = stock_updates(root)
    lines: dict[str, list[str]] = {}
    aliases: dict[str, dict[str, set[str]]] = {}
    out = []
    for f, p in pipe_rows(src).items():
        name = code_name(f)
        for path, nums, stock in p.cites:
            if Path(path) not in INTEGRATION:
                out.append(f"{f}: {path} is not integration code")
                continue
            text = lines.setdefault(path, (root / path).read_text(encoding="utf-8").split("\n"))
            alias = aliases.setdefault(path, local_aliases(root, Path(path)))
            ok = {name} | {a for a, used in alias.items() if name in used}
            named = [n for n in nums if 0 < n <= len(text) and _line_names(text[n - 1]) & ok]
            out += [f"{f}: {path}:{n} names neither {sorted(ok)}" for n in nums if n not in named]
            if not any(
                u.path == Path(path) and u.stock == stock and u.first <= n <= u.last for u in updates for n in named
            ):
                out.append(f"{f}: no line of {path}:{','.join(map(str, nums))} inside {stock}'s update names {name!r}")
            ups = [
                u
                for u in updates
                if u.path == Path(path) and u.stock == stock and any(u.first <= n <= u.last for n in nums)
            ]
            if len(ups) != 1:
                out.append(f"{f}: {path}:{nums} is not in one update of {stock}")
                continue
            if f.startswith("flow:"):
                continue
            signs = {s for s, names in ups[0].terms if name in names}
            want = set()
            if stock in p.sinks:
                want.add(1)
            if stock in p.sources or stock in p.drains:
                want.add(-1)
            if not signs or not signs <= want:
                out.append(f"{f}: its term in {stock}'s update at {path}:{ups[0].first} has sign {sorted(signs)}")
    return out


def code_flow_problems(root: Path, src: Sources) -> list[str]:
    """The table against the integration code, update by update: a stock updated with a ``flow:<stock>`` row is that
    flow's alone; in every other update each term must name a flow whose row has the stock on the term's side (``to``
    for an added term, ``from`` or ``also_drains`` for a subtracted one), and every stock a row names must be
    updated."""
    rows = pipe_rows(src)
    by_name: dict[str, list[str]] = collections.defaultdict(list)
    for f in rows:
        if not f.startswith("flow:"):
            by_name[code_name(f)].append(f)
    out = []
    updated = set()
    for u in stock_updates(root):
        updated.add(u.stock)
        if f"flow:{u.stock}" in rows:
            continue
        for s, names in u.terms:
            named = [f for n in names for f in by_name.get(n, [])]
            if not named:
                out.append(f"{u.stock} at {u.path.as_posix()}:{u.first}: a term that names no flow")
            for f in named:
                p = rows[f]
                ok = u.stock in p.sinks if s > 0 else (u.stock in p.sources or u.stock in p.drains)
                if not ok:
                    how = "adds to" if s > 0 else "takes from"
                    out.append(f"{f}: {how} {u.stock} at {u.path.as_posix()}:{u.first}, not in its row")
    for f, p in rows.items():
        for stock in sorted({*p.sources, *p.sinks, *p.drains} - {CLOUD}):
            if stock not in updated:
                out.append(f"{f}: {stock} has no update in the integration code")
    return out


def valve_ids(src: Sources) -> dict[str, str]:
    """Each flow's valve on the map: its own name, or the first flow of its ``WITHIN`` group."""
    out = {f: f for f in pipe_rows(src)}
    for vid, (flows, _) in WITHIN.items():
        out.update(dict.fromkeys(flows, vid))
    return out


def stock_modules(src: Sources) -> dict[str, str]:
    return {n: r["module"] for (n, k), r in src.docs.items() if k == "stock"}


def valve_modules(src: Sources) -> dict[str, str]:
    """Each valve's module (decision 4): its stocks' module, or for a flow between modules its ``model_docs.csv``
    module."""
    mods = stock_modules(src)
    rows = pipe_rows(src)
    out = {}
    for f, vid in valve_ids(src).items():
        p = rows[f]
        ms = {mods[s] for s in (*p.sources, *p.sinks) if s != CLOUD}
        out[vid] = ms.pop() if len(ms) == 1 else src.docs[(f, "flow")]["module"]
    return out


def lever_targets(src: Sources) -> dict[str, dict[str, int]]:
    """Each lever's targets with their distance in links: the first stocks and flows reached from it through
    auxiliaries only (``edges.csv``; decision 3). A stock with a goal-seeking or coflow valve is that valve, a flow its
    valve on the map."""
    out_edges: dict[tuple[str, str], list[tuple[str, str]]] = collections.defaultdict(list)
    for e in src.edges:
        out_edges[(e["source"], e["source_kind"])].append((e["target"], e["target_kind"]))
    valves = valve_stocks(src)
    vid = valve_ids(src)
    out: dict[str, dict[str, int]] = {}
    for lever in sorted(src.levers):
        found: dict[str, int] = {}
        seen: set[tuple[str, str]] = set()
        frontier = [(lever, "parameter")]
        hop = 0
        while frontier:
            hop += 1
            nxt = []
            for node in frontier:
                for t in out_edges[node]:
                    if t[1] in ("stock", "flow"):
                        cid = f"flow:{t[0]}" if t[1] == "stock" and t[0] in valves else t[0]
                        found.setdefault(vid.get(cid, cid), hop)
                    elif t[1] == "auxiliary" and t not in seen:
                        seen.add(t)
                        nxt.append(t)
            frontier = sorted(nxt)
        if not found:
            raise ValueError(f"lever {lever}: reaches no stock or flow")
        out[lever] = found
    return out


def target_modules(src: Sources) -> dict[str, str]:
    """The module of every lever target: a stock's, or its valve's (``valve_modules``)."""
    return {**stock_modules(src), **valve_modules(src)}


def lever_arrows(src: Sources) -> tuple[list[tuple[str, str, str]], dict[str, int]]:
    """The map's lever arrows as (lever, target cell, label) and each wide lever's count in its own module (operator
    rulings, slice 10e): a lever with at most ``WIDE`` targets points at each; a wider one has one arrow to each other
    module's region, labelled "<lever>, <count>", and its own module's count on its label."""
    mods = target_modules(src)
    own_mod = {n: r["module"] for (n, k), r in src.docs.items() if k == "parameter"}
    arrows: list[tuple[str, str, str]] = []
    own: dict[str, int] = {}
    for lever, targets in lever_targets(src).items():
        if len(targets) <= WIDE:
            arrows += [(lever, t, "") for t in sorted(targets)]
            continue
        counts = collections.Counter(mods[t] for t in targets)
        for m, n in sorted(counts.items()):
            if m == own_mod[lever]:
                own[lever] = n
            else:
                arrows.append((lever, f"region:{m}", f"{lever}, {n}"))
    return arrows, own


def own_note(n: int) -> str:
    return f"(acts on {n} in this module)"


def model_map(src: Sources, view: str) -> View:
    """The whole model on one page (slice 10e): each module a tinted region holding its stocks, valves, clouds and
    levers; pipes from ``tools/flow_pipes.csv``; lever arrows by ``lever_arrows``. No auxiliaries, no other parameters
    and no information links."""
    mods = {m["module"]: m for m in src.modules}
    smod = stock_modules(src)
    vmod = valve_modules(src)
    rows = pipe_rows(src)
    vid = valve_ids(src)
    arrows, own = lever_arrows(src)
    cells: list[Cell] = [
        Cell(f"region:{m}", r["display_name"], region_style(r["colour"]), "region", ()) for m, r in mods.items()
    ]
    for s in sorted(smod):
        lab = wrap(src.docs[(s, "stock")]["label"], hyphens=False)
        cells.append(Cell(s, lab, node_style("stock", mods[smod[s]]["colour"]), "node", (s,)))
    for v in sorted(set(vid.values())):
        flows = WITHIN[v][0] if v in WITHIN else (v,)
        lab = src.docs[(v, "flow")]["label"] + (f" ({WITHIN[v][1]})" if v in WITHIN else "")
        lab = wrap(lab, hyphens=False)
        cells.append(Cell(v, lab, valve_style(mods[vmod[v]]["colour"]), "valve", flows))
    for f, p in rows.items():
        if CLOUD in (*p.sources, *p.sinks):
            cells.append(Cell(f"cloud:{f}", "", CLOUD_STYLE, "cloud", (f,)))
    for lever in sorted(src.levers):
        r = src.docs[(lever, "parameter")]
        label = r["label"] + (f" {own_note(own[lever])}" if lever in own else "")
        cells.append(Cell(lever, wrap(label, hyphens=False), node_style("parameter", ""), "node", (lever,)))
    links: list[Link] = []
    for f, p in rows.items():
        v = vid[f]
        if p.within:
            if f == v:
                links.append(Link(v, p.sources[0], "", ATTACH_STYLE))
        else:
            links += [Link(f"cloud:{f}" if s == CLOUD else s, v, "", PIPE_IN_STYLE) for s in p.sources]
            links += [Link(v, f"cloud:{f}" if s == CLOUD else s, "", PIPE_STYLE) for s in p.sinks]
        links += [Link(v, s, "", DRAIN_STYLE) for s in p.drains]
    links += [Link(a, b, lab, REGION_ARROW_STYLE if lab else LEVER_STYLE) for a, b, lab in arrows]
    legend = [line for text in MAP_LEGEND for line in textwrap.wrap(text, MAP_WRAP)]
    captions = ["\n".join(textwrap.wrap(c, MAP_WRAP)) for c in MAP_CAPTIONS]
    cells += [
        Cell("title", MAP_TITLE, MAP_TITLE_STYLE, "title"),
        Cell("legend", "\n".join(legend), MAP_LEGEND_STYLE, "legend"),
        *(Cell(f"caption:{i}", c, MAP_CAPTION_STYLE, "caption") for i, c in enumerate(captions, start=1)),
    ]
    return View(view, "map", tuple(cells), tuple(links), homes=map_homes(src))


def region_style(colour: str) -> str:
    return (
        BASE + f"rounded=1;arcSize=3;fillColor={tint(colour, 0.12)};strokeColor={colour};strokeWidth=2;"
        "verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontSize=16;fontStyle=1;fontColor=#1A1A1A;"
    )


def build_views(root: Path = ROOT, src: Sources | None = None) -> dict[str, View]:
    src = read_sources(root) if src is None else src
    out = {"overview": overview(src)}
    out.update({v: panel(src, v) for v in PANEL_VIEWS})
    out.update({v: article(src, v) for v in ARTICLE_VIEWS})
    out.update({v: module_page(src, v) for v in MODULE_VIEWS})
    out.update({v: model_map(src, v) for v in MAP_VIEWS})
    return out


# ---- signed paths ---------------------------------------------------------------------------------------------------


def link_signs(src: Sources) -> dict[tuple[str, str], set[str]]:
    """Every signed ``loops.csv`` link (+ or -) with the signs it carries (two where the roles differ)."""
    out: dict[tuple[str, str], set[str]] = collections.defaultdict(set)
    for r in src.loops:
        if r["sign"] in ("+", "-"):
            out[(r["source"], r["target"])].add(r["sign"])
    return dict(out)


def shortest_signed_path(
    signs: Mapping[tuple[str, str], set[str]], sources: Iterable[str], targets: Iterable[str], sign: str
) -> tuple[list[str], list[str]] | None:
    """The shortest path of ``loops.csv`` links from any source item to any target item whose sign product is
    ``sign`` (a breadth-first search over (item, sign) states, neighbours in sorted order): its items and the sign
    of each link (a link that carries two signs, one per role, is taken with the sign the path needs); or None."""
    adj: dict[str, list[tuple[str, str]]] = collections.defaultdict(list)
    for (a, b), ss in sorted(signs.items()):
        for s in sorted(ss):
            adj[a].append((b, s))
    tgt = set(targets)
    start = [(s, "+") for s in sorted(set(sources))]
    parent: dict[tuple[str, str], tuple[str, str] | None] = {s: None for s in start}
    queue = collections.deque(start)
    while queue:
        node, sg = queue.popleft()
        for nxt, s in adj[node]:
            state = (nxt, "+" if s == sg else "-")
            if state in parent:
                continue
            parent[state] = (node, sg)
            if nxt in tgt and state[1] == sign:
                states = [state]
                cur: tuple[str, str] | None = (node, sg)
                while cur is not None:
                    states.append(cur)
                    cur = parent[cur]
                states.reverse()
                nodes = [n for n, _ in states]
                link_signs_ = ["+" if a == b else "-" for (_, a), (_, b) in itertools.pairwise(states)]
                return nodes, link_signs_
            queue.append(state)
    return None


def path_sign(signs: Mapping[tuple[str, str], set[str]], path: Sequence[str], path_signs: Sequence[str]) -> str | None:
    """The sign product of a stored path, link by link: each link must be a ``loops.csv`` link carrying its stored
    sign; None if one is not."""
    if len(path_signs) != len(path) - 1:
        return None
    neg = 0
    for a, b, s in zip(path, path[1:], path_signs, strict=False):
        if s not in signs.get((a, b), set()):
            return None
        neg += s == "-"
    return "+" if neg % 2 == 0 else "-"


def bundle_problems(src: Sources) -> list[str]:
    """Article nodes that bundle items and that a loop enters at item X and leaves from item Y: the loop closes in the
    code only if ``loops.csv`` has a path X to Y with sign +, no longer than any path with sign - (Addendum A)."""
    signs = link_signs(src)
    paths = {(r["source"], r["target"]): r["path"].split(" > ") for r in src.articles if r["part"] == "link"}
    out = []
    for r in (x for x in src.articles if x["part"] == "loop"):
        cyc = r["path"].split(" > ")[:-1]
        for i, b in enumerate(cyc):
            a, c = cyc[i - 1], cyc[(i + 1) % len(cyc)]
            x, y = paths[(a, b)][-1], paths[(b, c)][0]
            if x == y:
                continue
            plus = shortest_signed_path(signs, [x], [y], "+")
            minus = shortest_signed_path(signs, [x], [y], "-")
            if plus is None or (minus is not None and len(minus[0]) < len(plus[0])):
                out.append(f"{r['id']}: {b} entered at {x}, left from {y}: no + path at least as short as any - path")
    return out


# ---- geometry -------------------------------------------------------------------------------------------------------


def sidecar_path(root: Path, view: str) -> Path:
    return root / DIAGRAMS / f"{view}.geometry.json"


def read_sidecar(root: Path, view: str) -> Geometry:
    p = sidecar_path(root, view)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {str(k): [float(x) for x in v] for k, v in data.items()}


def dump_sidecar(geom: Mapping[str, Sequence[float]]) -> str:
    clean = {k: [_round(x) for x in v] for k, v in sorted(geom.items())}
    return json.dumps(clean, indent=1, sort_keys=True) + "\n"


def write_sidecar(root: Path, view: str, geom: Mapping[str, Sequence[float]]) -> None:
    p = sidecar_path(root, view)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        f.write(dump_sidecar(geom))


def _round(v: float) -> float | int:
    r = round(v, 1)
    return int(r) if r == int(r) else r


def _num(v: float) -> str:
    return str(_round(v))


def _font(style: str) -> float:
    """A style's font size in px (draw.io takes its last ``fontSize``)."""
    found = re.findall(r"fontSize=([0-9.]+);", style)
    return float(found[-1]) if found else 12.0


def cell_size(c: Cell) -> tuple[float, float]:
    """The box a cell's label needs."""
    if c.kind == "cloud":
        return CLOUD_W, CLOUD_H
    if c.kind == "region":
        return text_size(c.label, _font(c.style), True)
    if c.kind in ("title", "legend", "caption") and c.style in (MAP_TITLE_STYLE, MAP_LEGEND_STYLE, MAP_CAPTION_STYLE):
        return text_size(c.label, _font(c.style), c.kind == "title")
    if c.kind == "loop":
        w, h = text_size(c.label, 12, True)
        return max(math.ceil(w * 1.2), h, 52.0), max(math.ceil(h * 1.15), 52.0)
    if c.kind == "limit":
        w, h = text_size(c.label, 11, False)
        return w + 20, h
    if c.kind == "title":
        return text_size(c.label, 16, True)
    if c.kind in ("legend", "caption", "ghost", "ref"):
        return text_size(c.label, 11, False)
    if c.kind == "valve":
        w, h = text_size(c.label, 12, False)
        return max(w, VALVE_W + 16), h + VALVE_H
    bold = "fontStyle=1" in c.style
    return text_size(c.label, 13 if "fontSize=13" in c.style else 12, bold)


def unplaced(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    return [c.id for c in view.cells if c.id not in geom]


def edge_id(lk: Link) -> str:
    return f"e:{lk.source}>{lk.target}"


def label_offset_id(cid: str) -> str:
    return f"l:{cid}"


def sidecar_ids(view: View) -> set[str]:
    """The ids a view's sidecar may hold: its cells; each link's ``e:`` entry (its sign label) and ``w:`` entry (its
    bends); each valve's ``l:`` entry (its label's offset, 10e Addendum B)."""
    ids = {c.id for c in view.cells} | {edge_id(lk) for lk in view.links} | {waypoint_id(lk) for lk in view.links}
    return ids | {label_offset_id(c.id) for c in view.cells if c.kind == "valve"}


def orphans(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Sidecar ids that are not among the view's ``sidecar_ids``."""
    ids = sidecar_ids(view)
    return sorted(k for k in geom if k not in ids)


def bbox(boxes: Iterable[Sequence[float]]) -> tuple[float, float, float, float]:
    bs = list(boxes)
    if not bs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[0] + b[2] for b in bs), max(b[1] + b[3] for b in bs))


def place_free(view: View, geom: Geometry, ids: Sequence[str]) -> Geometry:
    """Cells without a position, stacked in a free column right of the placed cells (recon D2)."""
    out = dict(geom)
    placed = [geom[c.id] for c in view.cells if c.id in geom]
    _x0, y0, x1, _ = bbox(placed) if placed else (40.0, 40.0, 40.0, 40.0)
    y = y0
    for cid in ids:
        w, h = cell_size(view.cell(cid))
        out[cid] = [x1 + 60, y, w, h]
        y += h + 20
    return out


def view_geometry(root: Path, view: View) -> Geometry:
    """The sidecar's positions for the view's cells, with any unplaced cell in the free column."""
    ids = sidecar_ids(view)
    geom = {k: v for k, v in read_sidecar(root, view.name).items() if k in ids}
    return place_free(view, geom, unplaced(view, geom))


# ---- the first layout -----------------------------------------------------------------------------------------------


def layered(nodes: Sequence[str], edges: Iterable[tuple[str, str]], sweeps: int = 12) -> dict[str, tuple[int, int]]:
    """A deterministic layered layout, stdlib only: node to (layer, order). Cycles are broken by a DFS in sorted
    order, layers are longest paths, and barycentre sweeps order each layer; ties break by name (recon D1)."""
    ns = sorted(set(nodes))
    adj: dict[str, list[str]] = {n: [] for n in ns}
    for a, b in sorted(set(edges)):
        if a != b and a in adj and b in adj:
            adj[a].append(b)
    state: dict[str, int] = {}
    dag: set[tuple[str, str]] = set()

    def dfs(u: str) -> None:
        state[u] = 1
        for v in adj[u]:
            if state.get(v) == 1:
                dag.add((v, u))
            else:
                dag.add((u, v))
                if v not in state:
                    dfs(v)
        state[u] = 2

    indeg = dict.fromkeys(ns, 0)
    for a in ns:
        for b in adj[a]:
            indeg[b] += 1
    for n in sorted(ns, key=lambda x: (indeg[x], x)):
        if n not in state:
            dfs(n)
    preds: dict[str, list[str]] = {n: [] for n in ns}
    succs: dict[str, list[str]] = {n: [] for n in ns}
    for a, b in sorted(dag):
        if a != b:
            preds[b].append(a)
            succs[a].append(b)
    layer: dict[str, int] = {}

    def lay(n: str, seen: frozenset[str]) -> int:
        if n not in layer:
            ps = [p for p in preds[n] if p not in seen]
            layer[n] = 0 if not ps else 1 + max(lay(p, seen | {n}) for p in ps)
        return layer[n]

    for n in ns:
        lay(n, frozenset())
    nl = max(layer.values(), default=0) + 1
    rows = [sorted(n for n in ns if layer[n] == i) for i in range(nl)]
    pos = {n: float(i) for r in rows for i, n in enumerate(r)}
    for s in range(sweeps):
        nb = preds if s % 2 == 0 else succs
        for i in range(1, nl) if s % 2 == 0 else range(nl - 2, -1, -1):

            def bary(n: str, nb: Mapping[str, list[str]] = nb) -> tuple[float, str]:
                xs = [pos[m] for m in nb[n]]
                return (sum(xs) / len(xs) if xs else pos[n], n)

            rows[i].sort(key=bary)
            for j, n in enumerate(rows[i]):
                pos[n] = float(j)
    return {n: (layer[n], int(pos[n])) for n in ns}


def spring(nodes: Sequence[str], edges: Iterable[tuple[str, str]], seed: int = 7) -> dict[str, tuple[float, float]]:
    """networkx's spring layout in [0, 1] x [0, 1] (needs ``--with networkx==3.4.2``)."""
    nx = importlib.import_module("networkx")
    g = nx.Graph()
    g.add_nodes_from(sorted(nodes))
    g.add_edges_from(sorted({tuple(sorted(e)) for e in edges if e[0] != e[1]}))
    raw = nx.spring_layout(g, seed=seed, k=1.4 / math.sqrt(max(len(nodes), 1)), iterations=300)
    pos = {str(k): (float(v[0]), float(v[1])) for k, v in raw.items()}
    xs, ys = [p[0] for p in pos.values()], [p[1] for p in pos.values()]
    dx, dy = (max(xs) - min(xs)) or 1.0, (max(ys) - min(ys)) or 1.0
    return {n: ((p[0] - min(xs)) / dx, (p[1] - min(ys)) / dy) for n, p in pos.items()}


def first_layout(view: View) -> Geometry:
    """A first layout of every cell of a view (decision 6)."""
    if view.kind == "map":
        return map_first_layout(view)
    nodes = [c for c in view.cells if c.kind in ("node", "valve", "ghost", "ref")]
    ids = [c.id for c in nodes]
    edges = [(lk.source, lk.target) for lk in view.links]
    geom: Geometry = {}
    if view.kind == "module":  # layers left to right, as stocks and valves read along their main flow
        lo = layered(ids, edges)
        for n, (la, o) in lo.items():
            w, h = cell_size(view.cell(n))
            geom[n] = [60 + la * 200, 90 + o * 80, w, h]
    elif view.kind == "overview":
        lo = layered(ids, edges)
        for n, (la, o) in lo.items():
            w, h = cell_size(view.cell(n))
            geom[n] = [60 + la * 260, 90 + o * 130, max(w, 170.0), max(h, 60.0)]
    else:
        width, height = (1300.0, 820.0) if view.kind == "panel" else (1000.0, 600.0)
        for n, (px, py) in spring(ids, edges).items():
            w, h = cell_size(view.cell(n))
            geom[n] = [40 + px * width, 80 + py * height, w, h]

    def centre(cid: str) -> tuple[float, float]:
        b = geom[cid]
        return b[0] + b[2] / 2, b[1] + b[3] / 2

    for lid, members in view.loop_cells.items():
        pts = [centre(m) for m in members if m in geom]
        w, h = cell_size(view.cell(lid))
        cx, cy = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else (0.0, 0.0)
        geom[lid] = [cx - w / 2, cy - h / 2, w, h]
    for mid, links in view.limit_links.items():
        a, b = links[0]
        (ax, ay), (bx, by) = centre(a), centre(b)
        w, h = cell_size(view.cell(mid))
        geom[mid] = [(ax + bx) / 2 + 10, (ay + by) / 2 + 10, w, h]
    x0, y0, _x1, y1 = bbox(geom.values())
    w, h = cell_size(view.cell("title"))
    geom["title"] = [x0, y0 - h - 20, w, h]
    y = y1 + 30
    for c in view.cells:
        if c.kind in ("legend", "caption"):
            w, h = cell_size(c)
            geom[c.id] = [x0, y, w, h]
            y += h + 10
    return {k: [float(_round(x)) for x in v] for k, v in geom.items()}


MAP_ROWS: Final = (
    ("capability", "adoption", "consumer", "work"),
    ("workforce", "labour_market", "sourcing", "finance"),
)
"""The first layout's module grid (slice 10e). No pipe crosses modules, so the modules sit where the lever arrows
between them stay short: capability beside adoption, consumer and work; workforce beside the labour market; finance
beside sourcing."""


def _components(nodes: Sequence[str], edges: Iterable[tuple[str, str]]) -> list[list[str]]:
    """The connected groups of ``nodes`` (sorted, largest first)."""
    parent = {n: n for n in nodes}

    def find(n: str) -> str:
        while parent[n] != n:
            n = parent[n]
        return n

    for a, b in edges:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    groups: dict[str, list[str]] = collections.defaultdict(list)
    for n in sorted(nodes):
        groups[find(n)].append(n)
    return sorted(groups.values(), key=lambda g: (-len(g), g[0]))


def map_first_layout(view: View) -> Geometry:
    """The map's first layout: in each module its levers in a column on the left, then each connected group of stocks,
    valves and clouds laid left to right along its pipes (``layered``), the groups stacked; each region around its
    nodes, the regions on ``MAP_ROWS``."""
    cells = {c.id: c for c in view.cells}
    flows = [(lk.source, lk.target) for lk in view.links if lk.style in (*PIPE_STYLES, DRAIN_STYLE)]
    members: dict[str, list[str]] = collections.defaultdict(list)
    for cid, m in sorted(view.homes.items()):
        members[m].append(cid)
    local: dict[str, Geometry] = {}
    size: dict[str, tuple[float, float]] = {}
    for m, ids in members.items():
        geom: Geometry = {}
        levers = [i for i in ids if cells[i].kind == "node" and "fontStyle=2" in cells[i].style]
        y = REGION_HEAD + REGION_PAD
        for i in levers:
            w, h = cell_size(cells[i])
            geom[i] = [REGION_PAD, y, w, h]
            y += h + 14
        x0 = REGION_PAD + (max((geom[i][2] for i in levers), default=0.0) + 40 if levers else 0.0)
        cy = REGION_HEAD + REGION_PAD
        rest = [i for i in ids if i not in levers]
        for comp in _components(rest, flows):
            lo = layered(comp, [e for e in flows if e[0] in comp and e[1] in comp])
            sz = {i: cell_size(cells[i]) for i in comp}
            nl = max(la for la, _ in lo.values()) + 1
            no = max(o for _, o in lo.values()) + 1
            col_w = [max((sz[i][0] for i in comp if lo[i][0] == k), default=0.0) for k in range(nl)]
            row_h = [max((sz[i][1] for i in comp if lo[i][1] == k), default=0.0) for k in range(no)]
            xs = [x0 + sum(col_w[:k]) + 36 * k for k in range(nl)]
            ys = [cy + sum(row_h[:k]) + 18 * k for k in range(no)]
            for i in comp:
                la, o = lo[i]
                w, h = sz[i]
                geom[i] = [xs[la] + (col_w[la] - w) / 2, ys[o] + (row_h[o] - h) / 2, w, h]
            cy = ys[-1] + row_h[-1] + 30
        _, _, x1, y1 = bbox(geom.values())
        local[m] = geom
        size[m] = (x1 + REGION_PAD, max(y1, cy - 30) + REGION_PAD)
    out: Geometry = {}
    top = 80.0
    for row in MAP_ROWS:
        x = 40.0
        for m in row:
            w, h = size[m]
            out[f"region:{m}"] = [x, top, w, h]
            for i, (bx, by, bw, bh) in local[m].items():
                out[i] = [x + bx, top + by, bw, bh]
            x += w + 30
        top += max(size[m][1] for m in row) + 30
    x0, y0, _, y1 = bbox(out.values())
    w, h = cell_size(cells["title"])
    out["title"] = [x0, y0 - h - 20, w, h]
    y = y1 + 30
    for c in view.cells:
        if c.kind in ("legend", "caption"):
            w, h = cell_size(c)
            out[c.id] = [x0, y, w, h]
            y += h + 10
    return {k: [float(_round(x)) for x in v] for k, v in out.items()}


def layout(root: Path, name: str, view: View) -> tuple[list[str], list[str]]:
    """Store a first layout for the cells of a view with no position; returns (placed, orphans)."""
    geom = read_sidecar(root, name)
    missing = unplaced(view, geom)
    if not missing:
        return [], orphans(view, geom)
    new = first_layout(view) if not any(c.id in geom for c in view.cells) else place_free(view, geom, missing)
    geom.update({k: new[k] for k in missing})
    write_sidecar(root, name, geom)
    return missing, orphans(view, geom)


# ---- the .drawio writer and reader ----------------------------------------------------------------------------------


def _offset(geom: Mapping[str, Sequence[float]], a: str, b: str, d: float = 16.0) -> tuple[float, float]:
    """A waypoint left of the line a -> b, so that a two-way pair shows both arrows."""
    (x1, y1), (x2, y2) = ((geom[n][0] + geom[n][2] / 2, geom[n][1] + geom[n][3] / 2) for n in (a, b))
    ln = math.hypot(x2 - x1, y2 - y1) or 1.0
    return (x1 + x2) / 2 - (y2 - y1) / ln * d, (y1 + y2) / 2 + (x2 - x1) / ln * d


KIND_RANK: Final = {
    "region": -1,
    "cloud": 0,
    "node": 0,
    "valve": 0,
    "ghost": 0,
    "ref": 0,
    "limit": 1,
    "loop": 2,
    "title": 3,
    "legend": 4,
    "caption": 5,
}


def _vertex(root: ET.Element, cell: Cell, geom: Mapping[str, Sequence[float]]) -> None:
    c = ET.SubElement(
        root, "mxCell", {"id": cell.id, "value": cell.label, "style": cell.style, "vertex": "1", "parent": "1"}
    )
    x, y, w, h = geom[cell.id]
    if cell.kind == "valve":  # the shape at the top of its box, the label drawn below it
        x, y, w, h = x + w / 2 - VALVE_W / 2, y, VALVE_W, VALVE_H
    g = ET.SubElement(
        c, "mxGeometry", {"x": _num(x), "y": _num(y), "width": _num(w), "height": _num(h), "as": "geometry"}
    )
    off = geom.get(label_offset_id(cell.id))
    if off:  # the label moved by the sidecar's offset (10e Addendum B)
        ET.SubElement(g, "mxPoint", {"x": _num(off[0]), "y": _num(off[1]), "as": "offset"})


def render(view: View, geom: Mapping[str, Sequence[float]]) -> bytes:
    """The ``.drawio`` XML of a view: fixed element and attribute order, sorted cells, numbers to 0.1, LF. Module
    regions (the model map) come before the edges, so that every arrow draws above them; the other vertices after."""
    _x0, _y0, x1, y1 = bbox(geom[c.id] for c in view.cells)
    mxfile = ET.Element("mxfile", {"host": "aisim", "type": "device"})
    diagram = ET.SubElement(mxfile, "diagram", {"id": view.name, "name": view.name})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "grid": "0",
            "gridSize": "10",
            "page": "0",
            "pageWidth": _num(x1 + 40),
            "pageHeight": _num(y1 + 40),
            "math": "0",
            "shadow": "0",
        },
    )
    root = ET.SubElement(model, "root")
    ET.SubElement(root, "mxCell", {"id": "0"})
    ET.SubElement(root, "mxCell", {"id": "1", "parent": "0"})
    for cell in sorted((c for c in view.cells if c.kind == "region"), key=lambda c: c.id):
        _vertex(root, cell, geom)
    for lk in sorted(view.links, key=lambda x: (x.source, x.target)):
        c = ET.SubElement(
            root,
            "mxCell",
            {
                "id": f"e:{lk.source}>{lk.target}",
                "value": lk.label,
                "style": lk.style,
                "edge": "1",
                "parent": "1",
                "source": lk.source,
                "target": lk.target,
            },
        )
        label_at = geom.get(edge_id(lk))
        attrs = {"x": _num(label_at[0]), "y": _num(label_at[1])} if label_at else {}
        g = ET.SubElement(c, "mxGeometry", {**attrs, "relative": "1", "as": "geometry"})
        bends = waypoints(view, geom, lk)
        if bends:
            arr = ET.SubElement(g, "Array", {"as": "points"})
            for px, py in bends:
                ET.SubElement(arr, "mxPoint", {"x": _num(px), "y": _num(py)})
    for cell in sorted((c for c in view.cells if c.kind != "region"), key=lambda c: (KIND_RANK[c.kind], c.id)):
        _vertex(root, cell, geom)
    ET.indent(mxfile, "  ")
    return bytes(ET.tostring(mxfile, encoding="utf-8", xml_declaration=False)) + b"\n"


def drawio_path(root: Path, view: str) -> Path:
    return root / DIAGRAMS / f"{view}.drawio"


def generate(root: Path = ROOT, views: Mapping[str, View] | None = None) -> dict[str, bytes]:
    views = build_views(root) if views is None else views
    return {name: render(v, view_geometry(root, v)) for name, v in views.items()}


def read_drawio_geometry(path: Path) -> Geometry:
    """Vertex id to [x, y, w, h] from a ``.drawio`` file, plain or compressed (draw.io's deflate + base64)."""
    tree = ET.parse(path)
    out: Geometry = {}
    models = list(tree.iter("mxGraphModel"))
    if not models:
        for d in tree.iter("diagram"):
            raw = zlib.decompress(base64.b64decode((d.text or "").strip()), -15)
            models.append(ET.fromstring(urllib.parse.unquote(raw.decode("utf-8"))))
    for m in models:
        for c in m.iter("mxCell"):
            g = c.find("mxGeometry")
            if c.get("vertex") == "1" and g is not None:
                out[c.get("id", "")] = [float(g.get(k, "0")) for k in ("x", "y", "width", "height")]
    return out


def absorb(root: Path, name: str, view: View, path: Path | None = None) -> tuple[list[str], list[str]]:
    """Read a hand-edited ``.drawio`` back into the sidecar; returns (moved ids, ignored ids)."""
    got = read_drawio_geometry(drawio_path(root, name) if path is None else path)
    geom = read_sidecar(root, name)
    ids = {c.id for c in view.cells}
    moved = sorted(
        k for k, v in got.items() if k in ids and [_round(x) for x in v] != [_round(x) for x in geom.get(k, [])]
    )
    geom.update({k: [float(_round(x)) for x in v] for k, v in got.items() if k in ids})
    write_sidecar(root, name, geom)
    return moved, sorted(k for k in got if k not in ids)


# ---- checks ---------------------------------------------------------------------------------------------------------


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stale(root: Path = ROOT, views: Mapping[str, View] | None = None) -> list[str]:
    """Views whose committed ``.drawio`` differs from a regeneration."""
    out = []
    for name, data in generate(root, views).items():
        p = drawio_path(root, name)
        if not p.exists() or p.read_bytes() != data:
            out.append(name)
    return out


def export_paths(root: Path, view: str) -> dict[str, Path]:
    return {"svg": root / DIAGRAMS / "svg" / f"{view}.svg", "png": root / DIAGRAMS / "png" / f"{view}.png"}


def manifest_problems(root: Path = ROOT) -> list[str]:
    """Differences between the committed sources and exports and ``MANIFEST.json``."""
    p = root / MANIFEST
    if not p.exists():
        return [f"{MANIFEST.as_posix()}: missing"]
    man = json.loads(p.read_text(encoding="utf-8"))
    bad = []
    if set(man["views"]) != set(VIEWS):
        bad.append(f"manifest views {sorted(man['views'])} differ from {sorted(VIEWS)}")
    for name in VIEWS:
        ent = man["views"].get(name, {})
        src = drawio_path(root, name)
        if not src.exists() or sha256(src) != ent.get("source"):
            bad.append(f"{name}.drawio: changed since export")
        for fmt, path in export_paths(root, name).items():
            if not path.exists() or sha256(path) != ent.get(fmt):
                bad.append(f"{name}.{fmt}: missing or changed since export")
    for fmt in ("svg", "png"):
        d = root / DIAGRAMS / fmt
        for f in sorted(d.glob(f"*.{fmt}")) if d.exists() else []:
            if f.stem not in VIEWS:
                bad.append(f"{fmt}/{f.name}: not a view")
    return bad


def boxes_overlap(a: Sequence[float], b: Sequence[float], gap: float = 0.0) -> bool:
    return (
        a[0] < b[0] + b[2] + gap and b[0] < a[0] + a[2] + gap and a[1] < b[1] + b[3] + gap and b[1] < a[1] + a[3] + gap
    )


def overlaps(view: View, geom: Mapping[str, Sequence[float]]) -> list[tuple[str, str]]:
    """Pairs of cells whose boxes overlap: nodes, loop labels, limit markers, the title, legend and captions. A module
    region (the model map) holds its nodes, so only region against region counts for it."""
    ids = sorted(c.id for c in view.cells)
    region = {c.id for c in view.cells if c.kind == "region"}
    return [
        (a, b)
        for i, a in enumerate(ids)
        for b in ids[i + 1 :]
        if (a in region) == (b in region) and boxes_overlap(geom[a], geom[b])
    ]


def too_small(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Cells whose stored box is smaller than their label needs."""
    out = []
    for c in view.cells:
        w, h = cell_size(c)
        if geom[c.id][2] + 0.05 < w or geom[c.id][3] + 0.05 < h:
            out.append(c.id)
    return out


def _segment(geom: Mapping[str, Sequence[float]], a: str, b: str) -> tuple[float, float, float, float]:
    (x1, y1), (x2, y2) = ((geom[n][0] + geom[n][2] / 2, geom[n][1] + geom[n][3] / 2) for n in (a, b))
    return x1, y1, x2, y2


def _cross(p: tuple[float, float, float, float], q: tuple[float, float, float, float]) -> bool:
    def orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
        return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)

    d1 = orient(q[0], q[1], q[2], q[3], p[0], p[1])
    d2 = orient(q[0], q[1], q[2], q[3], p[2], p[3])
    d3 = orient(p[0], p[1], p[2], p[3], q[0], q[1])
    d4 = orient(p[0], p[1], p[2], p[3], q[2], q[3])
    return d1 * d2 < 0 and d3 * d4 < 0


def _exit(box: Sequence[float], towards: tuple[float, float]) -> tuple[float, float]:
    """Where the line from a box's centre towards a point leaves the box."""
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    dx, dy = towards[0] - cx, towards[1] - cy
    ts = [box[2] / 2 / abs(dx)] if dx else []
    ts += [box[3] / 2 / abs(dy)] if dy else []
    t = min([*ts, 1.0])
    return cx + t * dx, cy + t * dy


def waypoint_id(lk: Link) -> str:
    return f"w:{lk.source}>{lk.target}"


def waypoints(view: View, geom: Mapping[str, Sequence[float]], lk: Link) -> list[tuple[float, float]]:
    """A link's bends: the sidecar's ``w:<source>><target>`` points, x and y in turn (slice 10e), else the offset
    point of a two-way pair, else none."""
    w = geom.get(waypoint_id(lk))
    if w:
        return [(w[i], w[i + 1]) for i in range(0, len(w) - 1, 2)]
    if any(o.source == lk.target and o.target == lk.source for o in view.links):
        return [_offset(geom, lk.source, lk.target)]
    return []


HELVETICA: Final[Mapping[str, int]] = dict(
    zip(
        " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~",
        (
            278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
            556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
            1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
            667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
            333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
            556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
        ),
        strict=True,
    )
)  # fmt: skip
"""Helvetica's character widths in thousandths of an em (Adobe's AFM; Arial matches them), for the label boxes."""
LABEL_GAP: Final = 8.0
"""A valve's label box starts this many px below its shape (draw.io's bottom label position, measured on the SVGs)."""


def text_px(line: str, font: float) -> float:
    """A line's width in Helvetica at ``font`` px."""
    return sum(HELVETICA.get(ch, 556) for ch in line) * font / 1000


def text_box(label: str, cx: float, top: float, font: float) -> list[float]:
    """The box draw.io draws behind a label (its white background): the widest line plus 2 px, 1.2 lines per font
    px plus 1 px, centred on ``cx`` from ``top``."""
    lines = label.split("\n")
    w = max(text_px(x, font) for x in lines) + 2
    return [cx - w / 2, top, w, float(round(len(lines) * font * 1.2 + 1))]


def drawn_cells(view: View, geom: Mapping[str, Sequence[float]]) -> dict[str, list[float]]:
    """Each cell's box as draw.io draws it (10e Addendum B): a valve is its 24 x 22 shape at the top centre of its
    sidecar box, as ``render`` writes it, and edges end on that shape; every other cell is its sidecar box."""
    out = {}
    for c in view.cells:
        x, y, w, h = geom[c.id][:4]
        out[c.id] = [x + w / 2 - VALVE_W / 2, y, VALVE_W, VALVE_H] if c.kind == "valve" else [x, y, w, h]
    return out


def drawn_labels(view: View, geom: Mapping[str, Sequence[float]]) -> dict[str, list[float]]:
    """The labels draw.io draws outside their cell, each as the box of its white background: every valve's, centred
    ``LABEL_GAP`` px below its shape, moved by its ``l:`` offset if the sidecar has one (10e Addendum B)."""
    out = {}
    for c in view.cells:
        if c.kind == "valve":
            x, y, w, _ = geom[c.id][:4]
            dx, dy = (geom.get(label_offset_id(c.id)) or [0.0, 0.0])[:2]
            out[c.id] = text_box(c.label, x + w / 2 + dx, y + VALVE_H + LABEL_GAP + dy, _font(c.style))
    return out


def valve_label_problems(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Valve labels whose box (``drawn_labels``) overlaps a drawn cell, its own valve's shape included, or another
    valve's label: an offset label must not hide a box (10e Addendum B). Regions are skipped."""
    cells = drawn_cells(view, geom)
    labels = drawn_labels(view, geom)
    out = [
        f"label:{v}: on {c.id}"
        for v, box in sorted(labels.items())
        for c in view.cells
        if c.kind != "region" and boxes_overlap(box, cells[c.id])
    ]
    out += [
        f"label:{a}: on label:{b}"
        for (a, p), (b, q) in itertools.combinations(sorted(labels.items()), 2)
        if boxes_overlap(p, q)
    ]
    return out


def link_paths(view: View, geom: Mapping[str, Sequence[float]]) -> dict[str, list[tuple[float, float]]]:
    """Each link's drawn path, as draw.io draws it: from the source's drawn cell (``drawn_cells``: a valve's shape) to
    the target's, through its waypoints (``waypoints``, from the sidecar as ``render`` writes them)."""
    cells = drawn_cells(view, geom)
    out = {}
    for lk in view.links:
        a, b = cells[lk.source], cells[lk.target]
        ca, cb = (a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)
        mid = waypoints(view, geom, lk)
        out[edge_id(lk)] = [_exit(a, (mid or [cb])[0]), *mid, _exit(b, (mid or [ca])[-1])]
    return out


def sign_label_points(view: View, geom: Mapping[str, Sequence[float]]) -> dict[str, tuple[float, float]]:
    """Each link's sign label position: draw.io's relative position along the link (the sidecar's ``e:`` entry, else
    the middle), on its drawn path (``link_paths``), moved by the entry's offset at right angles to the path, to the
    left of the direction of travel for a positive offset, as draw.io draws it (measured on its SVG, slice 10e; no
    view before the model map uses an offset)."""
    out = {}
    for eid, path in link_paths(view, geom).items():
        lens = [math.dist(p, q) for p, q in itertools.pairwise(path)]
        at = geom.get(eid, [0.0, 0.0])
        goal = (at[0] + 1) / 2 * sum(lens)
        for (p, q), ln in zip(itertools.pairwise(path), lens, strict=True):
            if goal <= ln or q == path[-1]:
                f = goal / ln if ln else 0.0
                nx, ny = ((q[1] - p[1]) / ln, -(q[0] - p[0]) / ln) if ln else (0.0, 0.0)
                out[eid] = (p[0] + f * (q[0] - p[0]) + at[1] * nx, p[1] + f * (q[1] - p[1]) + at[1] * ny)
                break
            goal -= ln
    return out


def _point_segment(p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln2 = dx * dx + dy * dy
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / ln2)) if ln2 else 0.0
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def _point_box(p: tuple[float, float], box: Sequence[float]) -> float:
    x, y, w, h = box[:4]
    return math.hypot(max(x - p[0], 0.0, p[0] - x - w), max(y - p[1], 0.0, p[1] - y - h))


def _box_path(box: Sequence[float], path: Sequence[tuple[float, float]]) -> float:
    """The distance from a box to a drawn path: 0 where the path enters the box."""
    x, y, w, h = box[:4]
    corners = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    sides = list(itertools.pairwise((*corners, corners[0])))
    best = math.inf
    for a, b in itertools.pairwise(path):
        if any(_cross((*a, *b), (*c, *d)) for c, d in sides):
            return 0.0
        best = min(best, _point_box(a, box), _point_box(b, box), *(_point_segment(c, a, b) for c in corners))
    return best


def signs_on_opposite_links(view: View, geom: Mapping[str, Sequence[float]], tol: float = 6.0) -> list[tuple[str, str]]:
    """(link, other link) pairs where the link's sign label sits within ``tol`` px of the other link's drawn path and
    the two signs are opposite, so a reader could take the sign for the other link's (slice 10b.1)."""
    paths = link_paths(view, geom)
    sign = {edge_id(lk): lk.label for lk in view.links}
    return [
        (e, o)
        for e, p in sorted(sign_label_points(view, geom).items())
        for o, path in sorted(paths.items())
        if o != e
        and {sign[e], sign[o]} == {"+", "-"}
        and min(_point_segment(p, a, b) for a, b in itertools.pairwise(path)) < tol
    ]


def limit_marker_problems(
    view: View, geom: Mapping[str, Sequence[float]], margin: float = 5.0, clearance: float = 6.0
) -> list[str]:
    """Limit markers not clearly beside a link they cap: the nearest capped link's drawn path must be at least
    ``margin`` px nearer the marker's box than any other link's, and no sign label may sit within ``clearance`` px of
    the box (slice 10b.1)."""
    paths = link_paths(view, geom)
    signs = sign_label_points(view, geom)
    out = []
    for mid, caps in sorted(view.limit_links.items()):
        box = geom[mid]
        capped = {f"e:{a}>{b}" for a, b in caps}
        near = min(_box_path(box, paths[e]) for e in capped)
        other, oid = min(((_box_path(box, p), e) for e, p in paths.items() if e not in capped), default=(math.inf, ""))
        if other - near < margin:
            out.append(f"{mid}: capped link at {near:.1f} px, {oid} at {other:.1f} px")
        for e, p in sorted(signs.items()):
            if _point_box(p, box) < clearance:
                out.append(f"{mid}: the sign of {e} at {_point_box(p, box):.1f} px")
    return out


def sign_label_clashes(view: View, geom: Mapping[str, Sequence[float]], tol: float = 6.0) -> list[tuple[str, str]]:
    """Pairs of links whose sign labels sit within ``tol`` px of each other (one would hide the other)."""
    pts = sorted(sign_label_points(view, geom).items())
    return [(a, b) for i, (a, p) in enumerate(pts) for b, q in pts[i + 1 :] if math.dist(p, q) < tol]


def crossings(view: View, geom: Mapping[str, Sequence[float]]) -> int:
    """Link crossings, counted on straight lines between cell centres, for links that share no cell."""
    segs = [(lk.source, lk.target, _segment(geom, lk.source, lk.target)) for lk in view.links]
    n = 0
    for i, (a, b, p) in enumerate(segs):
        for c, d, q in segs[i + 1 :]:
            if {a, b} & {c, d}:
                continue
            n += _cross(p, q)
    return n


def through_boxes(view: View, geom: Mapping[str, Sequence[float]]) -> list[tuple[str, str]]:
    """(link, cell) pairs where a link's straight line passes through a box it does not connect."""
    out = []
    for lk in view.links:
        p = _segment(geom, lk.source, lk.target)
        for c in view.cells:
            if c.id in (lk.source, lk.target) or c.kind == "region":
                continue
            x, y, w, h = geom[c.id]
            x, y, w, h = x + 2, y + 2, w - 4, h - 4
            sides = (
                (x, y, x + w, y),
                (x + w, y, x + w, y + h),
                (x, y + h, x + w, y + h),
                (x, y, x, y + h),
            )
            if any(_cross(p, s) for s in sides):
                out.append((f"{lk.source}>{lk.target}", c.id))
    return out


def min_font_px(view: View) -> float:
    """The smallest label font of a view's cells and labelled links in px (draw.io takes a style's last
    ``fontSize``)."""
    return min(_font(s) for s in (*(c.style for c in view.cells), *(lk.style for lk in view.links if lk.label)))


# ---- module page checks, on the committed .drawio files (slice 10c) -------------------------------------------------

CHROME_IDS: Final = re.compile(r"^(title|legend|caption:\d+)$")


@dataclass(frozen=True)
class DrawnCell:
    """A cell as a ``.drawio`` file has it: a vertex, or an edge with its source and target."""

    id: str
    value: str
    style: str
    edge: bool
    source: str = ""
    target: str = ""

    def is_item(self) -> bool:
        """A vertex standing for a module item drawn on its own page (not a ghost, a reference, a valve or chrome)."""
        return not self.edge and not CHROME_IDS.match(self.id) and not self.id.startswith(("ghost:", "ref:", "flow:"))


def read_drawio_cells(path: Path) -> list[DrawnCell]:
    out = []
    for c in ET.parse(path).iter("mxCell"):
        if c.get("vertex") == "1" or c.get("edge") == "1":
            out.append(
                DrawnCell(
                    c.get("id", ""),
                    c.get("value", ""),
                    c.get("style", ""),
                    c.get("edge") == "1",
                    c.get("source", ""),
                    c.get("target", ""),
                )
            )
    return out


def sign_problems(cells: Sequence[DrawnCell]) -> list[str]:
    """Edges of a module page that carry a label: module pages show no polarity (decision 2)."""
    return [f"{c.id}: label {c.value!r}" for c in cells if c.edge and c.value]


def reference_problems(src: Sources, view: str, cells: Sequence[DrawnCell]) -> list[str]:
    """Ghosts that are not an item of another module with an edge into the page, and page references that are not
    an item of the same module, assigned to a different page, with an edge into the page (``edges.csv``, and drawn)."""
    spec = MODULE_VIEWS[view]
    items = module_items(src)
    page_of = {it: p for p, its in page_assignment(src).items() for it in its}
    on_page = {page_item(src, c.id) for c in cells if c.is_item()}
    feeds = {(e["source"], e["source_kind"]) for e in src.edges if (e["target"], e["target_kind"]) in on_page}
    drawn = {c.source for c in cells if c.edge}
    out = []
    for c in cells:
        if c.edge or not c.id.startswith(("ghost:", "ref:")):
            continue
        try:
            it = page_item(src, c.id)
        except KeyError:
            out.append(f"{c.id}: not a module item")
            continue
        if c.id.startswith("ghost:") and items[it] in spec.modules:
            out.append(f"{c.id}: not of another module")
        if c.id.startswith("ref:") and items[it] not in spec.modules:
            out.append(f"{c.id}: not of this page's module")
        if c.id.startswith("ref:") and page_of.get(it) == spec.key:
            out.append(f"{c.id}: on this page")
        if it not in feeds or c.id not in drawn:
            out.append(f"{c.id}: no edge into the page")
    return out


def valve_problems(src: Sources, cells: Sequence[DrawnCell]) -> list[str]:
    """For each goal-seeking or coflow stock on a module page: exactly one valve and exactly one arrow into the stock
    box, the pipe from that valve (so no input of its update points at the stock); and no valve without its stock."""
    valves = valve_stocks(src)
    vertices = {c.id: c for c in cells if not c.edge}
    clashes = name_clashes(src)
    out = []
    for c in cells:
        if c.is_item() and page_item(src, c.id)[1] == "stock" and page_item(src, c.id)[0] in valves:
            s = page_item(src, c.id)[0]
            v = [x for x in vertices.values() if x.id == f"flow:{s}"]
            if len(v) != 1 or "mxgraph.flowchart.collate" not in v[0].style:
                out.append(f"{s}: {len(v)} valve cells for its {valves[s]} flow")
            into = sorted(x.source for x in cells if x.edge and x.target == c.id)
            if into != [f"flow:{s}"]:
                out.append(f"{s}: arrows into the stock box from {into}, not only its valve's pipe")
    for cid in vertices:
        if cid.startswith("flow:"):
            s = cid[5:]
            if s not in valves or cell_id((s, "stock"), clashes) not in vertices:
                out.append(f"{cid}: a valve without its stock on this page")
    return out


# ---- the drawn geometry against an exported SVG (10e Addendum B) ----------------------------------------------------

SVG_CELL: Final = re.compile(r'<g data-cell-id="([^"]+)">')
SVG_RECT: Final = re.compile(
    r'<rect fill="#FFFFFF" stroke="none" x="([0-9.-]+)" y="([0-9.-]+)" width="([0-9.]+)" height="([0-9.]+)"'
)
SVG_NUM: Final = re.compile(r"-?[0-9]+(?:\.[0-9]+)?")


def svg_cells(svg: str) -> dict[str, str]:
    """Each ``data-cell-id`` group of a draw.io SVG export, up to the next one (ids unescaped)."""
    starts = [(m.start(), m.group(1).replace("&gt;", ">").replace("&amp;", "&")) for m in SVG_CELL.finditer(svg)]
    return {cid: svg[i:j] for (i, cid), (j, _) in zip(starts, [*starts[1:], (len(svg), "")], strict=True)}


def svg_drawn_problems(view: View, geom: Mapping[str, Sequence[float]], svg: str, tol: float = 2.0) -> list[str]:
    """The drawn geometry (``drawn_cells``, ``drawn_labels``, ``label_boxes``) against a draw.io SVG export of the
    view: each valve's shape (its path's bounding box), each valve label's white rectangle and each link label's
    rectangle must lie within ``tol`` px, after the export's translation (the valve shapes' median offset)."""
    groups = svg_cells(svg)
    cells = drawn_cells(view, geom)
    valves = [c.id for c in view.cells if c.kind == "valve"]

    def shape(cid: str) -> list[float]:
        d = re.search(r'<path d="([^"]+)"', groups[cid])
        nums = [float(x) for x in SVG_NUM.findall(d.group(1))] if d else [0.0, 0.0]
        xs, ys = nums[0::2], nums[1::2]
        return [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]

    def rects(cid: str) -> list[list[float]]:
        return [[float(m.group(i)) for i in range(1, 5)] for m in SVG_RECT.finditer(groups.get(cid, ""))]

    if not valves:
        return []
    offs = sorted((shape(v)[0] - cells[v][0], shape(v)[1] - cells[v][1]) for v in valves)
    dx = sorted(o[0] for o in offs)[len(offs) // 2]
    dy = sorted(o[1] for o in offs)[len(offs) // 2]

    def far(a: Sequence[float], b: Sequence[float]) -> float:
        return max(abs(a[0] - b[0] - dx), abs(a[1] - b[1] - dy), abs(a[2] - b[2]), abs(a[3] - b[3]))

    out = [f"{v}: shape {far(shape(v), cells[v]):.1f} px off" for v in valves if far(shape(v), cells[v]) > tol]
    for v, box in drawn_labels(view, geom).items():
        got = rects(v)
        if not got or far(got[0], box) > tol:
            out.append(f"label:{v}: {far(got[0], box) if got else math.inf:.1f} px off")
    for e, box in label_boxes(view, geom).items():
        got = rects(e)
        if not got or min(far(r, box) for r in got) > tol:
            out.append(f"{e}: label {min((far(r, box) for r in got), default=math.inf):.1f} px off")
    return out


# ---- map checks, on the committed .drawio file and sidecar (slice 10e) ----------------------------------------------


def map_contents_problems(src: Sources, cells: Sequence[DrawnCell]) -> list[str]:
    """The map's vertices against the model: every stock, valve and lever exactly once, the clouds the pipe table
    implies and the eight regions, and nothing else besides the title, legend and captions."""
    want = {
        *stock_modules(src),
        *valve_ids(src).values(),
        *src.levers,
        *(f"cloud:{f}" for f, p in pipe_rows(src).items() if CLOUD in (*p.sources, *p.sinks)),
        *(f"region:{m['module']}" for m in src.modules),
    }
    got = collections.Counter(c.id for c in cells if not c.edge and not CHROME_IDS.match(c.id))
    out = [f"{k}: drawn {got[k]} times" for k in sorted(want) if got[k] != 1]
    out += [f"{k}: not a stock, valve, lever, cloud or region" for k in sorted(got) if k not in want]
    return out


MAP_LINK_KINDS: Final = {
    PIPE_IN_STYLE: "pipe-in",
    PIPE_STYLE: "pipe-out",
    ATTACH_STYLE: "attach",
    DRAIN_STYLE: "drain",
    LEVER_STYLE: "lever",
    REGION_ARROW_STYLE: "region",
}


def map_link_kinds(cells: Sequence[DrawnCell]) -> dict[str, set[tuple[str, str]]]:
    """The map's edges by kind, from their styles (``other`` for an unknown style)."""
    out: dict[str, set[tuple[str, str]]] = {k: set() for k in (*MAP_LINK_KINDS.values(), "other")}
    for c in cells:
        if c.edge:
            out[MAP_LINK_KINDS.get(c.style, "other")].add((c.source, c.target))
    return out


def pipe_problems(src: Sources, cells: Sequence[DrawnCell]) -> list[str]:
    """The map's pipes, attachments and drain arrows against ``tools/flow_pipes.csv`` (operator rulings): a pipe from
    each source (or the flow's cloud) into its valve and from the valve to each sink; one attachment from a
    within-Headcount valve to its stock, with no pipe; a thin arrow from the valve to each stock it also drains."""
    vid = valve_ids(src)
    want: dict[str, set[tuple[str, str]]] = {k: set() for k in ("pipe-in", "pipe-out", "attach", "drain")}
    for f, p in pipe_rows(src).items():
        v = vid[f]
        if p.within:
            want["attach"].add((v, p.sources[0]))
        else:
            want["pipe-in"] |= {(f"cloud:{f}" if s == CLOUD else s, v) for s in p.sources}
            want["pipe-out"] |= {(v, f"cloud:{f}" if s == CLOUD else s) for s in p.sinks}
        want["drain"] |= {(v, s) for s in p.drains}
    got = map_link_kinds(cells)
    out = []
    for k, pairs in want.items():
        out += [f"{k} {a} -> {b}: missing" for a, b in sorted(pairs - got[k])]
        out += [f"{k} {a} -> {b}: not in the pipe table" for a, b in sorted(got[k] - pairs)]
    out += [f"{a} -> {b}: an edge of no known kind" for a, b in sorted(got["other"])]
    return out


def lever_arrow_problems(src: Sources, cells: Sequence[DrawnCell]) -> list[str]:
    """The map's lever arrows against ``lever_arrows``: each narrow lever's arrow to each target, each wide lever's
    labelled arrow to each other module's region, and its own-module count on its label (operator rulings)."""
    arrows, own = lever_arrows(src)
    got = map_link_kinds(cells)
    labels = {(c.source, c.target): c.value for c in cells if c.edge}
    out = [f"lever {a} -> {b}: missing" for a, b, lab in arrows if not lab and (a, b) not in got["lever"]]
    out += [
        f"region arrow {a} -> {b} {lab!r}: missing or labelled {labels.get((a, b))!r}"
        for a, b, lab in arrows
        if lab and ((a, b) not in got["region"] or labels.get((a, b)) != lab)
    ]
    narrow = {(a, b) for a, b, lab in arrows if not lab}
    wide = {(a, b) for a, b, lab in arrows if lab}
    out += [f"lever {a} -> {b}: not a target" for a, b in sorted(got["lever"] - narrow)]
    out += [f"region arrow {a} -> {b}: not a module the lever reaches" for a, b in sorted(got["region"] - wide)]
    text = {c.id: c.value.replace("\n", " ") for c in cells if not c.edge}
    for lever in sorted(src.levers):
        found = [int(n) for n in re.findall(r"\(acts on (\d+) in this module\)", text.get(lever, ""))]
        if found != ([own[lever]] if lever in own else []):
            out.append(f"{lever}: label counts {found}, own-module targets {own.get(lever, 0)}")
    return out


def map_homes(src: Sources) -> dict[str, str]:
    """The module whose region holds each map node: a stock's, a valve's (``valve_modules``), a cloud's valve's and a
    lever's own (decision 4)."""
    vmod = valve_modules(src)
    vid = valve_ids(src)
    home = {**stock_modules(src), **vmod}
    home.update({f"cloud:{f}": vmod[vid[f]] for f, p in pipe_rows(src).items() if CLOUD in (*p.sources, *p.sinks)})
    home.update({lever: src.docs[(lever, "parameter")]["module"] for lever in src.levers})
    return home


def region_problems(src: Sources, view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Nodes not wholly inside their module's region, and regions that overlap."""
    home = map_homes(src)
    out = []
    for c in view.cells:
        if c.id not in home:
            continue
        x, y, w, h = geom[c.id][:4]
        rx, ry, rw, rh = geom[f"region:{home[c.id]}"][:4]
        if not (rx <= x and ry <= y and x + w <= rx + rw and y + h <= ry + rh):
            out.append(f"{c.id}: outside region:{home[c.id]}")
    regions = sorted(c.id for c in view.cells if c.kind == "region")
    out += [f"{a} overlaps {b}" for a, b in itertools.combinations(regions, 2) if boxes_overlap(geom[a], geom[b])]
    return out


def drawn_through_boxes(view: View, geom: Mapping[str, Sequence[float]], inset: float = 2.0) -> list[tuple[str, str]]:
    """(link, box) pairs where a link's drawn path (``link_paths``) passes through a box, each shrunk by ``inset`` px
    as in ``through_boxes`` (slice 10e). The boxes are what draw.io draws (10e Addendum B): every cell the link does
    not connect (``drawn_cells``: a valve is its shape) and every valve label (``drawn_labels``, ids
    ``label:<valve>``). A pipe may not pass through its own valve's label either, since it would look broken there;
    an input or lever arrow may cross the label of the valve it points at (operator ruling on the stop). Module
    regions are skipped: they hold the arrows."""
    paths = link_paths(view, geom)
    cells = drawn_cells(view, geom)
    boxes = [(c.id, cells[c.id]) for c in view.cells if c.kind != "region"]
    boxes += [(f"label:{v}", b) for v, b in drawn_labels(view, geom).items()]
    out = []
    for lk in view.links:
        path = paths[edge_id(lk)]
        ends = {lk.source, lk.target}
        if lk.style not in PIPE_STYLES:  # an input or lever arrow may cross the label of the valve it points at
            ends.add(f"label:{lk.target}")
        for cid, box in boxes:
            if cid in ends:
                continue
            if _path_meets_box(path, [box[0] + inset, box[1] + inset, box[2] - 2 * inset, box[3] - 2 * inset]):
                out.append((edge_id(lk), cid))
    return out


PIPE_STYLES: Final = (PIPE_STYLE, PIPE_IN_STYLE, ATTACH_STYLE)
LEVER_STYLES: Final = (LEVER_STYLE, REGION_ARROW_STYLE)


def arrowheads_on_pipes(view: View, geom: Mapping[str, Sequence[float]], tol: float = 6.0) -> list[str]:
    """Lever arrows whose arrowhead (the end of the drawn path) lies within ``tol`` px of a pipe's drawn path, so that
    the pipe would read as arrowed (10e Addendum B: the IT work demand pipe read as two-headed)."""
    paths = link_paths(view, geom)
    pipes = [(edge_id(lk), paths[edge_id(lk)]) for lk in view.links if lk.style in PIPE_STYLES]
    out = []
    for lk in view.links:
        if lk.style not in LEVER_STYLES:
            continue
        tip = paths[edge_id(lk)][-1]
        for pid, path in pipes:
            d = min(_point_segment(tip, a, b) for a, b in itertools.pairwise(path))
            if d < tol:
                out.append(f"{edge_id(lk)}: arrowhead {d:.1f} px from the pipe {pid}")
    return out


def _samples(path: Sequence[tuple[float, float]], step: float) -> list[tuple[float, float, float, float]]:
    """Points about ``step`` px apart along a drawn path, each with its segment's unit direction."""
    out = []
    for a, b in itertools.pairwise(path):
        ln = math.dist(a, b)
        if ln == 0:
            continue
        ux, uy = (b[0] - a[0]) / ln, (b[1] - a[1]) / ln
        n = max(1, math.ceil(ln / step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n, ux, uy) for i in range(n + 1)]
    return out


def runs_along(
    view: View, geom: Mapping[str, Sequence[float]], tol: float = 3.0, run: float = 20.0, step: float = 2.0
) -> list[str]:
    """Lever arrows that run along a pipe: ``run`` px or more of the arrow's drawn path within ``tol`` px of a pipe
    segment and nearly parallel to it. Crossing a pipe is allowed (slice 10e)."""
    paths = link_paths(view, geom)
    pipes = [list(itertools.pairwise(paths[edge_id(lk)])) for lk in view.links if lk.style in PIPE_STYLES]
    out = []
    for lk in view.links:
        if lk.style not in LEVER_STYLES:
            continue
        path = paths[edge_id(lk)]
        lx0, ly0, lx1, ly1 = (
            min(p[0] for p in path),
            min(p[1] for p in path),
            max(p[0] for p in path),
            max(p[1] for p in path),
        )
        dirs = [
            ((b[0] - a[0]) / math.dist(a, b), (b[1] - a[1]) / math.dist(a, b))
            for a, b in itertools.pairwise(path)
            if a != b
        ]
        for all_segs in pipes:
            # only a pipe segment near the arrow's extent and nearly parallel to one of its segments can count
            segs = [
                (a, b)
                for a, b in all_segs
                if a != b
                and min(a[0], b[0]) - tol <= lx1
                and lx0 <= max(a[0], b[0]) + tol
                and min(a[1], b[1]) - tol <= ly1
                and ly0 <= max(a[1], b[1]) + tol
                and any(abs(ux * (b[0] - a[0]) + uy * (b[1] - a[1])) / math.dist(a, b) > 0.97 for ux, uy in dirs)
            ]
            if not segs:
                continue
            length = 0.0
            for x, y, ux, uy in _samples(paths[edge_id(lk)], step):
                along = any(
                    math.dist(a, b) > 0
                    and _point_segment((x, y), a, b) < tol
                    and abs(ux * (b[0] - a[0]) + uy * (b[1] - a[1])) / math.dist(a, b) > 0.97
                    for a, b in segs
                )
                length = length + step if along else 0.0
                if length >= run:
                    break
            if length >= run:
                out.append(f"{edge_id(lk)} runs along a pipe")
                break
    return out


def pipe_crossings(view: View, geom: Mapping[str, Sequence[float]]) -> list[tuple[str, str]]:
    """Pairs of pipes whose drawn paths cross (pipes that share no cell)."""
    paths = link_paths(view, geom)
    pipes = [lk for lk in view.links if lk.style in PIPE_STYLES]
    return [
        (edge_id(a), edge_id(b))
        for a, b in itertools.combinations(pipes, 2)
        if not {a.source, a.target} & {b.source, b.target}
        and any(
            _cross((*p, *q), (*r, *s))
            for p, q in itertools.pairwise(paths[edge_id(a)])
            for r, s in itertools.pairwise(paths[edge_id(b)])
        )
    ]


def label_boxes(view: View, geom: Mapping[str, Sequence[float]]) -> dict[str, list[float]]:
    """Each labelled link's label box as draw.io draws it (``text_box``: its white background), centred on its label
    point (``sign_label_points``, on the drawn path; 10e Addendum B)."""
    fonts = {edge_id(lk): (lk.label, _font(lk.style)) for lk in view.links if lk.label}
    out = {}
    for e, (x, y) in sign_label_points(view, geom).items():
        if e in fonts:
            box = text_box(fonts[e][0], x, y, fonts[e][1])
            out[e] = [box[0], y - box[3] / 2, box[2], box[3]]
    return out


def map_label_problems(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Region-arrow labels whose text box overlaps another label's, a drawn cell (module regions excepted) or a valve's
    label, or hides part of a pipe under its white background (slice 10e; drawn geometry, 10e Addendum B).
    ``labels_crossed`` reports lever arrows through a label."""
    boxes = sorted(label_boxes(view, geom).items())
    out = [f"{a} and {b}: labels overlap" for (a, p), (b, q) in itertools.combinations(boxes, 2) if boxes_overlap(p, q)]
    paths = link_paths(view, geom)
    pipes = [edge_id(lk) for lk in view.links if lk.style in PIPE_STYLES]
    cells = drawn_cells(view, geom)
    others = [(c.id, cells[c.id]) for c in view.cells if c.kind != "region"]
    others += [(f"label:{v}", b) for v, b in drawn_labels(view, geom).items()]
    for e, p in boxes:
        out += [f"{e}: label on {cid}" for cid, box in others if boxes_overlap(p, box)]
        out += [f"{e}: label on the pipe {o}" for o in pipes if _path_meets_box(paths[o], p)]
    return out


def labels_crossed(view: View, geom: Mapping[str, Sequence[float]]) -> list[tuple[str, str]]:
    """(labelled link, other link) pairs where the other link's drawn path runs through the label's text box: a
    readability measure for the review, not a gate criterion (slice 10e)."""
    paths = link_paths(view, geom)
    return [
        (e, o)
        for e, p in sorted(label_boxes(view, geom).items())
        for o, path in sorted(paths.items())
        if o != e and _path_meets_box(path, p)
    ]


def _path_meets_box(path: Sequence[tuple[float, float]], box: Sequence[float]) -> bool:
    """Whether a drawn path enters or crosses a box."""
    x, y, w, h = box[:4]
    sides = ((x, y, x + w, y), (x + w, y, x + w, y + h), (x, y + h, x + w, y + h), (x, y, x, y + h))
    inside = any(x < p[0] < x + w and y < p[1] < y + h for p in path)
    return inside or any(_cross((*a, *b), s) for a, b in itertools.pairwise(path) for s in sides)


# ---- export ---------------------------------------------------------------------------------------------------------


def export(root: Path = ROOT, views: Sequence[str] | None = None) -> dict[str, dict[str, str]]:
    """Export the views (default: every view) to SVG and PNG with draw.io desktop, then write their manifest entries
    (local only). Other entries and keys of an existing manifest are kept, so exporting new views never rewrites
    another view's files (slice 10c)."""
    entries: dict[str, dict[str, str]] = {}
    for name in VIEWS if views is None else views:
        src = drawio_path(root, name)
        for fmt, out in export_paths(root, name).items():
            out.parent.mkdir(parents=True, exist_ok=True)
            cmd = [str(DRAWIO_EXE), "-x", "-f", fmt, "--border", str(BORDER)]
            if fmt == "png":
                cmd += ["--scale", str(PNG_SCALE)]
            subprocess.run([*cmd, "-o", str(out), str(src)], check=True, capture_output=True)
            if not out.exists():
                raise RuntimeError(f"draw.io wrote no {out}")
        paths = export_paths(root, name)
        entries[name] = {"source": sha256(src), "svg": sha256(paths["svg"]), "png": sha256(paths["png"])}
    old: dict[str, object] = (
        json.loads((root / MANIFEST).read_text(encoding="utf-8")) if (root / MANIFEST).exists() else {}
    )
    kept = old.get("views", {})
    views_all = {**(kept if isinstance(kept, dict) else {}), **entries}
    man = {**old, "drawio": DRAWIO_VERSION, "png_scale": PNG_SCALE, "border": BORDER, "views": views_all}
    with (root / MANIFEST).open("w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return entries


# ---- the command line -----------------------------------------------------------------------------------------------


def write(root: Path = ROOT) -> list[str]:
    """Write every ``.drawio``; prints orphans and unplaced cells per view."""
    views = build_views(root)
    for name, view in views.items():
        geom = read_sidecar(root, name)
        o, u = orphans(view, geom), unplaced(view, geom)
        if o or u:
            print(f"{name}: orphans {o}; unplaced {u}")
    out = generate(root, views)
    for name, data in out.items():
        p = drawio_path(root, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return list(out)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="regenerate every .drawio from the metadata and sidecars")
    g.add_argument("--check", action="store_true", help="exit 1 if a .drawio is stale or the manifest differs")
    g.add_argument("--layout", metavar="VIEW", choices=VIEWS, help="a first layout for VIEW's unplaced cells")
    g.add_argument("--absorb", metavar="VIEW", choices=VIEWS, help="read VIEW's hand-edited .drawio into its sidecar")
    g.add_argument("--export", action="store_true", help="export SVG and PNG with draw.io desktop, write the manifest")
    ap.add_argument("--views", nargs="+", choices=VIEWS, help="with --export: export only these views")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this repository)")
    a = ap.parse_args(argv)
    if a.write:
        for name in write(a.root):
            print("wrote", drawio_path(Path("."), name).as_posix())
    elif a.layout:
        placed, orph = layout(a.root, a.layout, build_views(a.root)[a.layout])
        print(f"{a.layout}: placed {placed}; orphans {orph}")
    elif a.absorb:
        moved, ignored = absorb(a.root, a.absorb, build_views(a.root)[a.absorb])
        print(f"{a.absorb}: moved {moved}; ignored {ignored}")
    elif a.export:
        for name, ent in export(a.root, a.views).items():
            print(name, ent)
    else:
        views = build_views(a.root)
        bad = [f"{n}.drawio: stale" for n in stale(a.root, views)] + manifest_problems(a.root)
        for name, view in views.items():
            geom = read_sidecar(a.root, name)
            if orphans(view, geom) or unplaced(view, geom):
                bad.append(f"{name}: orphans {orphans(view, geom)}; unplaced {unplaced(view, geom)}")
        for b in bad:
            print(b)
        if bad:
            print("regenerate with: uv run --frozen python tools/model_diagrams.py --write (and --export, locally)")
            return 1
        print("model diagrams: every .drawio is current and matches the manifest")
    return 0


if __name__ == "__main__":
    sys.exit(main())
