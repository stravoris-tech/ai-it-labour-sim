"""The model's diagrams: the overview, the causal-loop panels and the article set, as draw.io files (slice 10b).

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
import base64
import collections
import csv
import hashlib
import importlib
import itertools
import json
import math
import subprocess
import sys
import textwrap
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
            "\nC5 (price floor) from 2028, C6 (AI-discount ceiling) from 2031.",
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
            "\nIt binds only in the Fast AI scenario and the stress set, from 2031.",
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
VIEWS: Final = ("overview", *PANEL_VIEWS, *ARTICLE_VIEWS)

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


def wrap(label: str, width: int = WRAP) -> str:
    return "\n".join(textwrap.wrap(label, width, break_long_words=False)) or label


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
    "Box: a stock. Bold text: an auxiliary. Colour: its module.",
    "+ or - on an arrow: the link's polarity.",
    "R / B circle: a reinforcing / balancing loop acting in Base.",
    "Dashed circle: weak in Base, or acting only in the stress set",
    f"  '{STRESS_SET}'.",
    "Grey circle: dormant in Base and in the stress set.",
    "? in a circle: the loop's sign depends on which path dominates.",
    "Dashed arrow: an open chain (no loop closes it).",
    "Faded arrow: every loop on it is dormant in Base.",
    "Hexagon: a limit on the link beside it.",
)


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
    cells += chrome(spec.title, LEGEND_LINES, spec.captions)
    return View(view, "panel", tuple(cells), tuple(links), loop_cells, limit_links)


# ---- the articles ---------------------------------------------------------------------------------------------------

ARTICLE_LEGEND: Final = (
    "+ or - on an arrow: the link's polarity.",
    "R / B circle: a reinforcing / balancing loop.",
    "Box: a stock (it accumulates). Bold text: everything else.",
    "Hexagon: a limit on the link beside it.",
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
    cells += chrome(f"{art}. {story['label']}", ARTICLE_LEGEND, ["\n".join(textwrap.wrap(story["story"], 90))])
    return View(view, "article", tuple(cells), tuple(links), loop_cells, limit_links)


def build_views(root: Path = ROOT, src: Sources | None = None) -> dict[str, View]:
    src = read_sources(root) if src is None else src
    out = {"overview": overview(src)}
    out.update({v: panel(src, v) for v in PANEL_VIEWS})
    out.update({v: article(src, v) for v in ARTICLE_VIEWS})
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


def cell_size(c: Cell) -> tuple[float, float]:
    """The box a cell's label needs."""
    if c.kind == "loop":
        w, h = text_size(c.label, 12, True)
        return max(math.ceil(w * 1.2), h, 52.0), max(math.ceil(h * 1.15), 52.0)
    if c.kind == "limit":
        w, h = text_size(c.label, 11, False)
        return w + 20, h
    if c.kind == "title":
        return text_size(c.label, 16, True)
    if c.kind in ("legend", "caption"):
        return text_size(c.label, 11, False)
    bold = "fontStyle=1" in c.style
    return text_size(c.label, 13 if "fontSize=13" in c.style else 12, bold)


def unplaced(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    return [c.id for c in view.cells if c.id not in geom]


def edge_id(lk: Link) -> str:
    return f"e:{lk.source}>{lk.target}"


def orphans(view: View, geom: Mapping[str, Sequence[float]]) -> list[str]:
    """Sidecar ids that are neither a cell nor a link of the view (a link's entry places its sign label)."""
    ids = {c.id for c in view.cells} | {edge_id(lk) for lk in view.links}
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
    ids = {c.id for c in view.cells} | {edge_id(lk) for lk in view.links}
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
    nodes = [c for c in view.cells if c.kind == "node"]
    ids = [c.id for c in nodes]
    edges = [(lk.source, lk.target) for lk in view.links]
    geom: Geometry = {}
    if view.kind == "overview":
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


KIND_RANK: Final = {"node": 0, "limit": 1, "loop": 2, "title": 3, "legend": 4, "caption": 5}


def render(view: View, geom: Mapping[str, Sequence[float]]) -> bytes:
    """The ``.drawio`` XML of a view: fixed element and attribute order, sorted cells, numbers to 0.1, LF."""
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
    pairs = {(lk.source, lk.target) for lk in view.links}
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
        if (lk.target, lk.source) in pairs:
            arr = ET.SubElement(g, "Array", {"as": "points"})
            px, py = _offset(geom, lk.source, lk.target)
            ET.SubElement(arr, "mxPoint", {"x": _num(px), "y": _num(py)})
    for cell in sorted(view.cells, key=lambda c: (KIND_RANK[c.kind], c.id)):
        c = ET.SubElement(
            root, "mxCell", {"id": cell.id, "value": cell.label, "style": cell.style, "vertex": "1", "parent": "1"}
        )
        x, y, w, h = geom[cell.id]
        ET.SubElement(
            c, "mxGeometry", {"x": _num(x), "y": _num(y), "width": _num(w), "height": _num(h), "as": "geometry"}
        )
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
    """Pairs of cells whose boxes overlap: nodes, loop labels, limit markers, the title, legend and captions."""
    ids = sorted(c.id for c in view.cells)
    return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1 :] if boxes_overlap(geom[a], geom[b])]


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
            if c.id in (lk.source, lk.target):
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


# ---- export ---------------------------------------------------------------------------------------------------------


def export(root: Path = ROOT) -> dict[str, dict[str, str]]:
    """Export every view to SVG and PNG with draw.io desktop, then write the manifest (local only)."""
    entries: dict[str, dict[str, str]] = {}
    for name in VIEWS:
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
    man = {"drawio": DRAWIO_VERSION, "png_scale": PNG_SCALE, "border": BORDER, "views": entries}
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
        for name, ent in export(a.root).items():
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
