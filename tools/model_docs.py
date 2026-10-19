"""The model inventory and its data dictionary: every named item of the engine, joined with the curated metadata.

The engine is the source of truth for names, kinds, dimensions, modules and values (recon 10 B5); the curated text
(label, description, units, sources) lives in ``src/aisim/data/model_docs.csv``, keyed by (name, kind), and the
modules in ``src/aisim/data/model_modules.csv``. This tool joins them and writes three generated files:

- ``docs/model/inventory.csv``: one row per item, with its values in every model;
- ``docs/model/edges.csv``: the collapsed dependency edges (``tools/model_graph.py``);
- ``docs/model-reference.md``: the data dictionary.

Kinds (recon 10 B1, D7):

- **stock**: a ``State`` family, the prototype's 37 and the six of the feedback loops;
- **flow**: an intermediate that enters a stock update as an additive term (``NAMED_FLOWS``), and the unnamed
  goal-seeking term of a stock, ``flow:<Stock>`` (``UNNAMED_FLOWS``);
- **auxiliary**: every other named intermediate (a field of a section result, found by tracing one step through
  ``run()``'s ``trace`` hook; the edges themselves are static);
- **parameter**: a scalar family, the scalars of ``parameters.csv`` grouped by trailing dimension tokens;
- **table**: a table of the baseline file;
- **output**: a catalogue key template (``catalogue.csv``).

Module: exactly one of the 8 engine modules, the one where the quantity itself lives (operator ruling R1, slice 10a).
A section's items take its module; a stock takes the module computing most of its update terms; a parameter or table
takes the module that reads it most (a time constant read only by a stock update, the stock's module); an output the
module of what it reads. ``MODULE_OVERRIDES`` settles the rest, each with its reason, and the other readers are
listed in the inventory's ``readers`` column.

Usage: ``uv run python tools/model_docs.py --write | --check [--counts] [--root PATH]``

- ``--write`` regenerates the three files; ``--check`` exits 1 if any of them differs from what ``--write`` would
  write (``tests/test_model_docs.py`` runs the same check in the gate). Two runs give byte-identical files.
- ``--counts`` prints the item counts by kind; with ``--root`` it reads another tree (import ``aisim`` from that tree,
  ``PYTHONPATH=<root>/src``).
"""

from __future__ import annotations

import argparse
import ast
import csv
import dataclasses
import inspect
import io
import json
import re
import sys
import typing
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from aisim.params import Params
from aisim.state import State, baseline_data, load_initial_state, models

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import model_diagrams as DG
from tools import model_graph as G

ROOT: Final = Path(__file__).resolve().parent.parent
DATA: Final = Path("src/aisim/data")
OUT_INVENTORY: Final = Path("docs/model/inventory.csv")
OUT_EDGES: Final = Path("docs/model/edges.csv")
OUT_REFERENCE: Final = Path("docs/model-reference.md")
KINDS: Final = ("stock", "flow", "auxiliary", "parameter", "table", "output")

SECTION_MODULE: Final[Mapping[str, str]] = {
    "S2": "capability",
    "S3": "work",
    "S4": "workforce",
    "S5": "workforce",
    "S6": "labour_market",
    "S7": "workforce",
    "S8a": "labour_market",
    "S8b": "labour_market",
    "S8c": "labour_market",
    "S8d": "labour_market",
    "S8e": "labour_market",
    "S8f": "labour_market",
    "S9": "finance",
    "S10": "finance",
    "S11a": "sourcing",
    "S11b": "finance",
    "S11c": "finance",
    "S11d": "finance",
    "S12": "adoption",
    "S13a": "consumer",
    "S13b": "sourcing",
    "S13c": "consumer",
    "S13d": "sourcing",
}
"""The engine module of each section ID (``aisim.scalar.engine.SECTION_IDS``)."""

NAMED_FLOWS: Final = frozenset(
    [
        "Demand",
        "Comp",
        "Aband",
        "cons.AdoptC",
        "cons.NewApps",
        "cons.Retire",
        "Src.IHTurn",
        "Src.GCCTurn",
        "Src.Contested",
        "SignS",
        "Src.VExp",
        "AttAdopt",
        "fl.openings",
        "cancel",
        "promo",
        "sw.in",
        "sw.out",
        "hires",
        "fl.onboard",
        "conv",
        "expiry",
        "fl.promo_out",
        "fl.quits",
        "fl.leave",
        "fl.retire",
        "fl.layoffs",
        "pool.rec_to_seek",
        "pool.rec_to_left",
        "pool.rec_retire",
        "pool.seek_exit",
        "pool.seek_retire",
        "Grad",
        "ext",
        "Enrol",
        "AdoptE",
        "VF.ExpLeg",
        "VB.Sign",
        "VF.ExpNew",
    ]
)
"""The intermediates that enter a stock update as an additive term, with at most a factor (recon 10 D7)."""

UNNAMED_FLOWS: Final = (
    "LOB",
    "SeatsB",
    "SpendRatio",
    "SrcPerc",
    "CostPerc",
    "PUS",
    "PUL",
    "PerceivedP",
    "ClientP",
    "ClientPRef",
    "TightPerc",
    "Overhead",
    "Viab",
    "CostProg",
    "Disc",
    "ShareRef",
    "NewD",
    "NewP",
    "WI",
    "VMarg",
    "ECost",
    "C4Hab",
)
"""The stocks whose update is a goal-seeking term written inline, ``(target - stock) / time`` (recon 10 D7), the
last three in ``loops.post``."""

REFERENCE_STOCKS: Final = ("WS0", "Attr0", "Dur0")
"""Loop state families set once, on the first step, to a 2024 reference (``loops.pre``): no flow enters them."""

UNIT_ALLOWLIST: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        # confirmed by operator, Addendum A: signings (book volume per year) enter the duration-weighted coflow NewD
        # (book volume-years) times the new-contract duration Dnew (years), integrate.py's NewD update
        ("NewD", "VB.Sign"),
    }
)
"""(stock, flow) pairs whose flow is not in the stock's units per year, each settled by its sources and confirmed
by the operator."""

LOOP_TERMS: Final[Mapping[str, str]] = {
    "R7": "sourcing",
    "C2": "workforce",
    "C4": "sourcing",
    "C5": "finance",
    "C6": "finance",
    "R10": "finance",
    "R4": "labour_market",
}
"""The seven phase 9 loop terms and the module of the section that calls each (decision 1)."""

MODULE_OVERRIDES: Final[Mapping[tuple[str, str], tuple[str, str]]] = {
    ("TargetMargin", "parameter"): ("finance", "unread; the vendors' calibration target margin (06b:230)"),
    ("Att0", "parameter"): ("consumer", "unread; the 2024 AI seat attach rate, stock Att (06a:232)"),
    ("Leakage", "parameter"): ("consumer", "unread; the share of credit spend going to AI providers (06a:235)"),
    ("NormalUtil", "parameter"): ("consumer", "unread; the normal ratio of committed spend to budget (06a:241)"),
    ("Mix0", "table"): ("finance", "unread by run(); the 2024 contract mix by vendor and type (engine.py TABLES_1D)"),
    ("Src0", "table"): ("sourcing", "unread by run(); the 2024 sourcing shares by sector and employer"),
    ("WS0", "stock"): (
        "sourcing",
        "R7's 2024 economy-wide GCC work share, a sourcing quantity (its update reads work's CS)",
    ),
    ("C4Hab", "stock"): ("sourcing", "C4's habituated shortfall, read only by client flight in S13b"),
    ("A_mean", "output"): ("adoption", "the completion-weighted mean of the adoption stock A"),
    ("Src_{sector}_{employer}", "output"): ("sourcing", "the sourcing work shares IHW, GCCW and VW"),
    ("NormalMargin", "parameter"): (
        "finance",
        "the vendors' normal margin; workforce (C2) and sourcing (C4) read it for Vrel",
    ),
    ("R6Theta", "parameter"): ("finance", "a threshold on relative viability, a fraction of the normal margin"),
}
"""(name, kind) to (module, reason), where the rules above do not give the module the quantity lives in."""


# ---- reading the tree ------------------------------------------------------------------------------------------------


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def cat_template(r: Mapping[str, str]) -> str:
    """A catalogue key's template: each dimension value replaced by ``{dimension}`` (``H_IH`` is ``H_{unit}``)."""
    t = r["key"]
    for kv in filter(None, r["dims"].split(";")):
        k, v = kv.split("=")
        t = re.sub(r"(?<=_)" + re.escape(v) + r"(?=_|$)", "{" + k + "}", t, count=1)
    return t


def dims_of_value(v: object) -> tuple[list[str], int]:
    """The dimensions of a nested dict of values, outer first, and its instance count."""
    dims_: list[str] = []
    n = 1
    while isinstance(v, dict):
        name, k = G.dim_of_keys(set(v))
        dims_.append(name)
        n *= k
        v = next(iter(v.values()))
    return dims_, n


def fmt_val(v: object) -> str:
    """A value as text: a float by ``repr``, a nested dict as ``a/b=value;...`` in key order."""
    if isinstance(v, dict):
        parts: list[str] = []

        def rec(o: object, pre: str) -> None:
            if isinstance(o, dict):
                for k, x in o.items():
                    rec(x, f"{pre}/{k}" if pre else str(k))
            else:
                parts.append(f"{pre}={o!r}")

        rec(v, "")
        return ";".join(parts)
    return repr(v)


def class_field_lines(cls: type) -> dict[str, int]:
    """The line of each annotated field in a class body (a functional ``TypedDict``: its one line for every key)."""
    try:
        lines, start = inspect.getsourcelines(cls)
    except OSError:  # X = TypedDict("X", {...})
        mod = sys.modules[cls.__module__]
        src_lines = Path(inspect.getsourcefile(mod) or "").read_text(encoding="utf-8").splitlines()
        for i, t in enumerate(src_lines, start=1):
            if t.startswith(f"{cls.__name__} = TypedDict("):
                return {k: i for k in typing.get_type_hints(cls)}
        raise
    out: dict[str, int] = {}
    for i, text in enumerate(lines):
        m = re.match(r"\s+([A-Za-z_][A-Za-z0-9_]*)\s*:", text)
        if m and i > 0:
            out.setdefault(m.group(1), start + i)
    return out


def _rel(path: str | None, root: Path) -> str:
    return Path(path or "").resolve().relative_to(root.resolve()).as_posix()


@dataclass(frozen=True)
class Intermediate:
    """A named leaf of a section result: dotted name without dimension levels, dimensions, count, definition."""

    name: str
    dims: tuple[str, ...]
    n: int
    defined_at: str
    section: str
    leaf: str


def walk_items(sid: str, obj: object, root: Path) -> list[Intermediate]:
    """Every named leaf of one section's result (recon 10 B1): dataclass fields, typed-dict keys, dict dimensions."""
    out: list[Intermediate] = []

    def rec(o: object, tp: object, path: list[str], dims_: list[str], n: int, deflines: list[str]) -> None:
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            hints = typing.get_type_hints(type(o))
            fl = class_field_lines(type(o))
            src = _rel(inspect.getsourcefile(type(o)), root)
            for f in dataclasses.fields(o):
                rec(getattr(o, f.name), hints[f.name], [*path, f.name], dims_, n, [*deflines, f"{src}:{fl[f.name]}"])
            return
        if isinstance(tp, type) and typing.is_typeddict(tp):
            hints = typing.get_type_hints(tp)
            fl = class_field_lines(tp)
            src = _rel(inspect.getsourcefile(tp), root)
            assert isinstance(o, Mapping)
            for k in hints:
                rec(o[k], hints[k], [*path, k], dims_, n, [*deflines, f"{src}:{fl.get(k, 0)}"])
            return
        if isinstance(o, dict):
            dname, size = G.dim_of_keys(set(o))
            args = typing.get_args(tp)
            sub_tp = args[1] if len(args) == 2 else float
            rec(next(iter(o.values())), sub_tp, path, [*dims_, dname], n * size, deflines)
            return
        leaf = "tuple" if isinstance(o, tuple) else "float"
        out.append(Intermediate(".".join(path), tuple(dims_), n, deflines[-1], sid, leaf))

    rec(obj, type(obj), [], [], 1, [])
    return out


def capture_step(model: str) -> dict[str, object]:
    """The section results of step 0 of a run of ``model``, by section ID (the engine's ``trace`` hook)."""
    from aisim.scalar.engine import run

    got: dict[str, object] = {}

    def trace(step: int, y: float, sid: str, value: object) -> None:
        if step == 0:
            got[sid] = value

    run(Params.baseline(model), trace=trace, stop=2 / 16)
    return got


@dataclass(frozen=True)
class RecordMap:
    """What ``record.py`` reads: node to the templates reading it (``direct`` when the key is the node itself, else
    ``aggregate``), and template to the other templates whose recorded values it reads (``row["H_IH"]``)."""

    reads: dict[str, dict[str, set[str]]]
    refs: dict[str, set[str]]


def record_map(root: Path, fams: Mapping[str, G.Family], cat_key_tpl: Mapping[str, str]) -> RecordMap:
    """The nodes and recorded keys each catalogue template reads in ``record`` and ``record_extras``."""
    loopvar_dim = {
        "u": "unit",
        "e": "employer",
        "v": "vendor",
        "x": "sector",
        "w": "worktype",
        "r": "region",
        "l": "level",
        "k": "type",
    }
    tree = ast.parse((root / G.SCALAR / "record.py").read_text(encoding="utf-8"))
    res: dict[str, dict[str, set[str]]] = {}
    refs: dict[str, set[str]] = {}

    def concrete_key(key: ast.expr) -> str | None:
        if isinstance(key, ast.Constant):
            return str(key.value)
        if isinstance(key, ast.BinOp) and isinstance(key.left, ast.Constant) and isinstance(key.right, ast.Name):
            return str(key.left.value) + G.DIMSETS[loopvar_dim[key.right.id]][0]
        if isinstance(key, ast.JoinedStr):
            parts = []
            for v in key.values:
                if isinstance(v, ast.Constant):
                    parts.append(str(v.value))
                else:
                    assert isinstance(v, ast.FormattedValue) and isinstance(v.value, ast.Name)
                    parts.append(G.DIMSETS[loopvar_dim[v.value.id]][0])
            return "".join(parts)
        return None

    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and fn.name in ("record", "record_extras")):
            continue
        fi, _ = G.analyse_function(fn, "record", {"s": ["item"]}, fams)
        an = G.Analyzer(fi, {"s": ["item"]}, fams)
        # a name assigned the same chain more than once (VB = s.books.VB in two blocks) is still an alias
        same: dict[str, set[str]] = {}
        chains: dict[str, ast.expr] = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                        tv = list(zip(t.elts, node.value.elts, strict=True))
                    else:
                        tv = [(t, node.value)]
                    for tt, vv in tv:
                        if isinstance(tt, ast.Name):
                            same.setdefault(tt.id, set()).add(ast.dump(vv))
                            chains[tt.id] = vv
        for name, dumps in same.items():
            if name not in fi.aliases and len(dumps) == 1 and G._is_chain(chains[name]):
                c = an.chain(chains[name])
                if c is not None and c[0] in ("st", "item", "pr", "tb"):
                    fi.aliases[name] = c
        an.computed = {k[0] for k in fi.deps} - set(fi.aliases)
        pairs: list[tuple[ast.expr, ast.expr]] = []
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Subscript):
                tgt = node.targets[0]
                if isinstance(tgt.value, ast.Name) and tgt.value.id in ("row", "out"):
                    pairs.append((tgt.slice, node.value))
            if isinstance(node, ast.AnnAssign) and isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values, strict=True):
                    if k is not None:
                        pairs.append((k, v))
        for key, val in pairs:
            concrete = concrete_key(key)
            if concrete is None:
                continue
            tpl = cat_key_tpl.get(concrete, "?" + concrete)
            for node in ast.walk(val):
                if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "row":
                    ref = concrete_key(node.slice)
                    if ref is not None and ref in cat_key_tpl:
                        refs.setdefault(tpl, set()).add(cat_key_tpl[ref])
            direct = isinstance(val, ast.Name | ast.Attribute | ast.Subscript)
            toks = an.reads(val)
            for node in ast.walk(val):  # sum(s.pools.Grad.values()): the object of a dict method call
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "values":
                    toks |= an.reads(node.func.value)
            for tk in toks:
                if tk[0] == "local":
                    continue
                tok = "time:y" if tk == ("item", "y") else ":".join(tk[:2])
                res.setdefault(tok, {"direct": set(), "aggregate": set()})["direct" if direct else "aggregate"].add(tpl)
    return RecordMap(res, refs)


# ---- the inventory ---------------------------------------------------------------------------------------------------


@dataclass
class Item:
    """One inventory row: a named item of the engine, without its curated text."""

    name: str
    kind: str
    module: str
    dimensions: str
    n_instances: int
    defined_at: str
    readers: str = ""
    values: dict[str, str] = field(default_factory=dict)
    classification: str = ""
    lever: str = ""
    term: str = ""
    catalogue: str = ""
    auto_notes: list[str] = field(default_factory=list)

    @property
    def key(self) -> tuple[str, str]:
        return (self.name, self.kind)


def _majority(mods: Sequence[str]) -> str:
    """The most frequent module, ties broken by ``MODULES`` order; empty if none."""
    c = Counter(m for m in mods if m in G.MODULES)
    if not c:
        return ""
    top = max(c.values())
    return next(m for m in G.MODULES if c[m] == top)


def _state_lines(root: Path) -> dict[str, int]:
    lines = (root / "src/aisim/state.py").read_text(encoding="utf-8").splitlines()
    out: dict[str, int] = {}
    in_state = False
    for i, t in enumerate(lines, start=1):
        if t.startswith("class State("):
            in_state = True
            continue
        if in_state and t and not t.startswith(" "):
            break
        m = re.match(r"    ([A-Za-z0-9]+): (Mat|Vec|float)$", t)
        if in_state and m:
            out[m.group(1)] = i
    return out


def _flow_line(root: Path, stock: str) -> str:
    """The line of a stock's goal-seeking update (``st["X"]... +=``), in ``integrate.py`` or ``loops.py``."""
    pat = re.compile(r'st\["' + re.escape(stock) + r'"\][^=]*\+=')
    for name in ("integrate.py", "loops.py"):
        path = root / G.SCALAR / name
        if not path.exists():
            continue
        for i, t in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pat.search(t):
                return f"{G.SCALAR.as_posix()}/{name}:{i}"
    raise ValueError(f"no goal-seeking update of {stock}")


def _json_lines(path: Path, section: str) -> dict[str, int]:
    """The line of each key directly under ``section`` in a JSON file written with one-space indent."""
    out: dict[str, int] = {}
    inside = False
    for i, t in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if t.startswith(f' "{section}": {{'):
            inside = True
            continue
        if inside:
            m = re.match(r'  "([^"]+)":', t)
            if m:
                out[m.group(1)] = i
            elif t.startswith(" }"):
                break
    return out


@dataclass(frozen=True)
class Inventory:
    """Every item, and the graph it was built from."""

    items: list[Item]
    graph: G.Graph
    edges: list[G.GraphEdge]
    models: tuple[str, ...]


def build_inventory(root: Path = ROOT, model_names: Sequence[str] | None = None) -> Inventory:
    """Every named item of the engine at ``root`` (``aisim`` must import from that tree)."""
    mods = tuple(models() if model_names is None else model_names)
    g = G.analyse(root)
    es = G.edges(root, g)
    sec = G.section_edges(g, control=True)
    integ = G.integrate_edges(g, control=True)
    imod = G.item_modules(g)
    items: list[Item] = []

    # ---- intermediates (flows and auxiliaries)
    got = capture_step(mods[-1] if "phase9" not in mods else "phase9")
    inter: list[Intermediate] = []
    for sid, obj in got.items():
        inter += [it for it in walk_items(sid, obj, root) if it.leaf != "tuple"]
    for it in inter:
        mod = SECTION_MODULE[it.section]
        if imod.get("item:" + it.name, mod) != mod:
            raise ValueError(f"{it.name}: section module {mod} against graph module {imod['item:' + it.name]}")
        kind = "flow" if it.name in NAMED_FLOWS else "auxiliary"
        items.append(
            Item(it.name, kind, mod, " x ".join(it.dims), it.n, it.defined_at, auto_notes=[f"section {it.section}"])
        )
    missing = NAMED_FLOWS - {it.name for it in inter}
    if missing:
        raise ValueError(f"named flows not found: {sorted(missing)}")

    # ---- stocks
    init = {m: baseline_data(m)["init"] for m in mods}
    full_: Mapping[str, object] = typing.cast(Mapping[str, object], load_initial_state())
    st_lines = _state_lines(root)
    node_mod = {"item:" + it.name: it.module for it in items}
    stock_src: dict[str, list[str]] = {}
    for e in integ:
        stock_src.setdefault(e.target[len("stock:") :], []).append(e.source)
    stock_mod: dict[str, str] = {}
    for name in typing.get_type_hints(State):
        stock_mod[name] = _majority([node_mod[s] for s in stock_src.get(name, []) if s in node_mod])
    for _ in range(3):  # a stock fed only by stocks takes their module
        for name, m in list(stock_mod.items()):
            if not m:
                stock_mod[name] = _majority(
                    [stock_mod[s[6:]] for s in stock_src.get(name, []) if s.startswith("stock:")]
                )
    for name in stock_mod:
        if (name, "stock") in MODULE_OVERRIDES:
            stock_mod[name] = MODULE_OVERRIDES[(name, "stock")][0]
    for name in typing.get_type_hints(State):
        v = full_[name]
        dims_, n = dims_of_value(v)
        vals = {m: fmt_val(init[m].get(name, v)) for m in mods}
        items.append(
            Item(
                name,
                "stock",
                stock_mod[name],
                " x ".join(dims_),
                n,
                f"src/aisim/state.py:{st_lines[name]}",
                values=vals,
                auto_notes=["values: the 2024 initial state"],
            )
        )
    for name in UNNAMED_FLOWS:
        if name not in stock_mod:
            continue
        dims_, n = dims_of_value(full_[name])
        items.append(
            Item(
                f"flow:{name}",
                "flow",
                stock_mod[name],
                " x ".join(dims_),
                n,
                _flow_line(root, name),
                auto_notes=[f"the goal-seeking update term of stock {name}"],
            )
        )
    node_mod.update({"stock:" + k: v for k, v in stock_mod.items()})
    node_mod["time:y"] = _majority([node_mod.get(e.target, "") for e in sec if e.source == "time:y"])

    # ---- parameters and tables: the modules that read them
    readers: dict[str, list[str]] = {}
    for e in sec:
        readers.setdefault(e.source, []).append(e.module)
    for e in integ:
        readers.setdefault(e.source, []).append(stock_mod[e.target[len("stock:") :]])
    readers.setdefault(g.s0.source, []).append(stock_mod[g.s0.target[len("stock:") :]])
    par = read_csv(root / DATA / "parameters.csv")
    par_line = {r["name"]: i for i, r in enumerate(par, start=2)}
    par_by = {r["name"]: r for r in par}
    pms = {m: Params.baseline(m) for m in mods}
    fits: dict[str, set[str]] = {}
    sets: dict[str, set[str]] = {}
    for m in mods:
        spec = root / "tools/models" / m / "spec.json"
        if spec.exists():
            sets[m] = set(json.loads(spec.read_text(encoding="utf-8"))["set"])
            fit = json.loads((root / "tools/models" / m / "fit.json").read_text(encoding="utf-8"))
            fits[m] = set(fit["fitted"])
        else:
            fits[m] = {r["name"] for r in par if r["fitted"] == "yes"}
            sets[m] = set()
    for fam, d in g.fams.items():
        prs = [par_by[x] for x in d.members]
        vals = {}
        for m in mods:
            sc = pms[m].scalars
            vals[m] = (
                repr(sc[d.members[0]])
                if len(d.members) == 1
                else ";".join(f"{d.suffixes[x]}={sc[x]!r}" for x in d.members)
            )
        cls = []
        fitted_in = [m for m in mods if any(x in fits[m] for x in d.members)]
        set_in = [m for m in mods if any(x in sets[m] for x in d.members)]
        if fitted_in:
            cls.append("fitted in " + ", ".join(fitted_in))
        if set_in:
            cls.append("set in " + ", ".join(set_in))
        cls.append("parameters.csv " + "/".join(sorted({p["kind"] for p in prs})))
        lever = "yes" if any(p["lever"] == "yes" for p in prs) else "no"
        rd = readers.get("param:" + fam, [])
        items.append(
            Item(
                fam,
                "parameter",
                _majority(rd),
                " x ".join(d.dims),
                len(d.members),
                f"{DATA.as_posix()}/parameters.csv:{par_line[d.members[0]]}",
                readers="+".join(m for m in G.MODULES if m in rd),
                values=vals,
                classification="; ".join(cls),
                lever=lever,
                auto_notes=[f"members: {', '.join(d.members)}"] if len(d.members) > 1 else [],
            )
        )
    tables = {m: baseline_data(m)["tables"] for m in mods}
    tline = _json_lines(root / DATA / "baseline.json", "tables")
    for tname, tv in tables[mods[0]].items():
        dims_, n = dims_of_value(tv)
        rd = readers.get("table:" + tname, [])
        items.append(
            Item(
                tname,
                "table",
                _majority(rd),
                " x ".join(dims_),
                n,
                f"{DATA.as_posix()}/baseline.json:{tline[tname]}",
                readers="+".join(m for m in G.MODULES if m in rd),
                values={m: fmt_val(tables[m][tname]) for m in mods},
                classification="set (baseline data)",
                lever="no",
            )
        )

    # ---- outputs: catalogue templates, the module of what they read
    cat = read_csv(root / DATA / "catalogue.csv")
    tpl_rows: dict[str, list[tuple[int, dict[str, str]]]] = {}
    key_tpl: dict[str, str] = {}
    for i, r in enumerate(cat, start=2):
        t = cat_template(r)
        tpl_rows.setdefault(t, []).append((i, r))
        key_tpl[r["key"]] = t
    rmap = record_map(root, g.fams, key_tpl)
    tpl_reads: dict[str, set[str]] = {}
    for tok, d2 in rmap.reads.items():
        for t in d2["direct"] | d2["aggregate"]:
            tpl_reads.setdefault(t, set()).add(tok)
    for t, rs in rmap.refs.items():
        tpl_reads.setdefault(t, set()).update("output:" + x for x in rs)
    try:
        from aisim.experiment.derived import DERIVED

        for name, dv in DERIVED.items():
            tpl_reads.setdefault(key_tpl.get(name, name), set()).update("output:" + key_tpl[k] for k in dv.deps)
    except ImportError:
        pass

    def mod_of(x: str) -> str:
        return node_mod.get(x, "") or out_mod.get(x[len("output:") :], "")

    out_mod: dict[str, str] = {}
    for _ in range(4):  # an output that reads recorded keys takes their module
        for tpl in tpl_rows:
            out_mod[tpl] = _majority([mod_of(x) for x in sorted(tpl_reads.get(tpl, set()))])
    for tpl, members in tpl_rows.items():
        line, r = members[0]
        dims_ = [kv.split("=")[0] for kv in filter(None, r["dims"].split(";"))]
        rd = sorted(tpl_reads.get(tpl, set()))
        mods_rd = {mod_of(x) for x in rd}
        items.append(
            Item(
                tpl,
                "output",
                out_mod[tpl],
                " x ".join(dims_),
                len(members),
                f"{DATA.as_posix()}/catalogue.csv:{line}",
                readers="+".join(m for m in G.MODULES if m in mods_rd),
                catalogue=f"{r['kind']}, family '{r['family']}', unit '{r['unit']}'",
                auto_notes=[f"reads {', '.join(rd)}" if rd else "reads no engine item"],
            )
        )

    for item in items:
        if item.key in MODULE_OVERRIDES:
            item.module = MODULE_OVERRIDES[item.key][0]
    return Inventory(items, g, es, mods)


# ---- the curated metadata ------------------------------------------------------------------------------------------

DOCS_COLUMNS: Final = (
    "name",
    "kind",
    "module",
    "label",
    "description",
    "units",
    "spec_name",
    "status",
    "sources",
    "notes",
)
MODULE_COLUMNS: Final = ("module", "display_name", "colour", "description", "status", "sources")
UNIT_VOCABULARY: Final = (
    "model-unit persons",
    "persons",
    "BFY",
    "USD",
    "book volume",
    "fraction",
    "index (2024 = 1)",
    "years",
    "weight",
    "multiplier",
    "logit units",
    "flag (0 or 1)",
    "switch",
    "dimensionless",
    "year",
)
"""The controlled unit vocabulary (decision 3)."""
UNIT_ADDITIONS: Final = ("applications", "seats", "book volume-years")
"""Terms added where no vocabulary term fits (slice 10a; confirmed by the operator, Addendum A): counts of
applications and of software seats (06a:60-61), and book volume-years, the duration-weighted contract book ``NewD``
(05:59)."""
UNIT_DENOMINATORS: Final = ("year", "person", "model-unit person", "application", "seat", "margin point")
"""Forms allowed after " per ": singulars (``USD per seat per year``), and margin point, a percentage point of
margin below the R6 threshold (``R6e``; confirmed by the operator, Addendum A)."""
STATUSES: Final = ("drafted", "reviewed")


def unit_ok(units: str) -> bool:
    """Whether ``units`` is in the vocabulary or a " per " combination of it (``unclear`` is checked apart)."""
    parts = units.split(" per ")
    terms = set(UNIT_VOCABULARY) | set(UNIT_ADDITIONS)
    return parts[0] in terms and all(p in terms | set(UNIT_DENOMINATORS) for p in parts[1:])


def read_metadata(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    """``model_docs.csv`` keyed by (name, kind)."""
    rows = read_csv(root / DATA / "model_docs.csv")
    return {(r["name"], r["kind"]): r for r in rows}


def read_modules(root: Path) -> list[dict[str, str]]:
    """``model_modules.csv``, in file order."""
    return read_csv(root / DATA / "model_modules.csv")


@dataclass(frozen=True)
class LoopTerm:
    """A phase 9 loop term: its strength parameters, the evidence range and where the design note defines it."""

    term: str
    title: str
    strengths: tuple[str, ...]
    evidence: str
    section: str


LOOP_TERM_TABLE: Final = (
    LoopTerm("R7", "GCC scale learning", ("kR7",), "0.15 / 0.4 / 0.75", "docs/model-changes-phase9.md:53"),
    LoopTerm("C2", "R6 capacity exit", ("R6e",), "0.002 / 0.005 / 0.012", "docs/model-changes-phase9.md:93"),
    LoopTerm("C4", "R6 client flight", ("kViab",), "0 / 5.8562 / 10.6511", "docs/model-changes-phase9.md:97"),
    LoopTerm("C5", "R6 price floor", ("PriceFloor",), "0.85 / 1.00 / 1.08", "docs/model-changes-phase9.md:108"),
    LoopTerm("C6", "R6 AI-discount ceiling", ("AIDiscCeil",), "0.20 / 0.30 / 0.45", "docs/model-changes-phase9.md:110"),
    LoopTerm("R10", "attrition cost", ("R10rc",), "0.0748 / 0.1816 / 0.3223", "docs/model-changes-phase9.md:113"),
    LoopTerm("R4", "skill erosion", ("R4a", "R4aIN"), "0 / 0.10 / 0.25", "docs/model-changes-phase9.md:124"),
)
"""The seven terms; the low / base / high ranges are the design note's parameter table (``:135-143``)."""


def structural_levers() -> set[str]:
    """The structural loop strengths sampled as levers (``aisim.scenarios.STRUCTURAL_LEVERS``), read at call time."""
    from aisim.scenarios import STRUCTURAL_LEVERS

    return {lv[0] for levers in STRUCTURAL_LEVERS.values() for lv in levers}


# ---- rendering -----------------------------------------------------------------------------------------------------


def _csv(header: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def _sorted(items: Sequence[Item]) -> list[Item]:
    return sorted(items, key=lambda it: (KINDS.index(it.kind), G.MODULES.index(it.module), it.name.lower(), it.name))


def _lever(it: Item, strengths: set[str]) -> str:
    if it.name in strengths:
        return "yes (structural)"
    return it.lever


def render_inventory(inv: Inventory, meta: Mapping[tuple[str, str], Mapping[str, str]]) -> str:
    """``docs/model/inventory.csv``: every item joined with its curated row, values for every model."""
    strengths = structural_levers()
    head = [
        "name",
        "kind",
        "module",
        "label",
        "description",
        "units",
        "dimensions",
        "n_instances",
        "defined_at",
        "readers",
        "classification",
        "lever",
        "spec_name",
        "status",
        "sources",
        "notes",
        *(f"value_{m}" for m in inv.models),
    ]
    rows = []
    for it in _sorted(inv.items):
        md = meta.get(it.key, {})
        rows.append(
            [
                it.name,
                it.kind,
                it.module,
                md.get("label", ""),
                md.get("description", ""),
                md.get("units", ""),
                it.dimensions,
                it.n_instances,
                it.defined_at,
                it.readers,
                it.classification,
                _lever(it, strengths) if it.kind == "parameter" else it.lever,
                md.get("spec_name", ""),
                md.get("status", ""),
                md.get("sources", ""),
                md.get("notes", ""),
                *(it.values.get(m, "") for m in inv.models),
            ]
        )
    return _csv(head, rows)


def node_key(node: str) -> tuple[str, str]:
    """A graph node's inventory (name, kind); the year is ``("y", "time")``, not an inventory item."""
    prefix, name = node.split(":", 1)
    if prefix == "item":
        return name, "flow" if name in NAMED_FLOWS else "auxiliary"
    return name, {"param": "parameter", "table": "table", "stock": "stock", "time": "time"}[prefix]


def render_edges(inv: Inventory) -> str:
    """``docs/model/edges.csv``: the collapsed edges with each end's kind and module (the year has no module)."""
    mod = {it.key: it.module for it in inv.items}
    rows = []
    for e in inv.edges:
        s, t = node_key(e.source), node_key(e.target)
        rows.append([s[0], s[1], t[0], t[1], e.dependence, mod.get(s, ""), mod.get(t, ""), e.file_line])
    head = ["source", "source_kind", "target", "target_kind", "dependence", "module_from", "module_to", "file_line"]
    return _csv(head, rows)


def _cell(x: object) -> str:
    return str(x).replace("|", "\\|").replace("\n", " ")


def _table(head: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    out += ["| " + " | ".join(_cell(x) for x in r) + " |" for r in rows]
    return out


def name_clashes(items: Sequence[Item]) -> dict[str, list[Item]]:
    """Names shared by more than one item (of different kinds)."""
    by: dict[str, list[Item]] = {}
    for it in items:
        by.setdefault(it.name, []).append(it)
    return {n: sorted(v, key=lambda it: KINDS.index(it.kind)) for n, v in sorted(by.items()) if len(v) > 1}


SECTION_TITLES: Final = {
    "stock": "Stocks",
    "flow": "Flows",
    "auxiliary": "Auxiliaries",
    "parameter": "Parameters",
    "table": "Tables",
    "output": "Outputs",
}
INTRO: Final = """\
# Model reference

The data dictionary of `ai-it-labour-sim`: every named item of the model, generated by `tools/model_docs.py` from the
engine and from the curated text in `src/aisim/data/model_docs.csv` and `model_modules.csv`. Do not edit this file;
edit the curated CSVs and run `uv run python tools/model_docs.py --write`.

- **What the model is.** A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability,
  for India and onshore, 2024-2040. It gives scenario projections, not forecasts: read every value as "under these
  assumptions" (README).
- **Which model.** The default model is `phase9`, frozen at release 0.2.0. The parameter tables give the values of
  `phase9` and `phase9_highadoption` and flag where `phase7`, `phase8` or `phase8_highadoption` differ; every model's
  values are in `docs/model/inventory.csv`, and the dependency edges in `docs/model/edges.csv`.
- **Names are the engine's.** Every item is named as the code names it (`fl.openings` is the `openings` field of the
  S8c flows, `VF.Revenue` a field of a vendor's S10 terms); the specification's name, where it has one, is in the
  `spec_name` column of `inventory.csv`. Some names are shared by items of different kinds; the last section lists
  them, and each entry is qualified by its kind. An unnamed goal-seeking update term is `flow:<Stock>`.
- **Modules.** Each item belongs to exactly one of the 8 engine modules, the one where the quantity lives; the
  modules that also read it are in `inventory.csv` (`readers`).
- **Units.** "model-unit persons" are headcount in the model's own units: the calibrated stocks, not people.
  "persons" are real people, only in the outputs scaled to India's 2024 headcount. BFY is a unit of IT work (one
  person-year of 2024 delivery). Rates are "per year"; "years" is a duration, "year" a calendar year; "index (2024 =
  1)" is 1 in 2024 by construction. `unclear` means the sources do not settle the unit.
- **Status.** Every description and unit was drafted from the cited sources (`drafted`); a row is `reviewed` once the
  operator has checked it.
- **The specification's errors.** Where the original specification is wrong or inconsistent, and what the model does
  instead, is in [the spec errata](spec-errata.md).
"""


def render_reference(
    inv: Inventory,
    meta: Mapping[tuple[str, str], Mapping[str, str]],
    modules: Sequence[Mapping[str, str]],
    diagrams: Sequence[str] = (),
    loops: Sequence[str] = (),
) -> str:
    """``docs/model-reference.md``: the data dictionary."""
    strengths = structural_levers()
    lines = [INTRO.rstrip("\n"), "", "## Modules", ""]
    lines += _table(
        ["Module", "Display name", "Colour", "Description", "Status"],
        [[f"`{m['module']}`", m["display_name"], m["colour"], m["description"], m["status"]] for m in modules],
    )
    lines += ["", "## Diagrams", "", *diagrams]
    shown = [m for m in ("phase9", "phase9_highadoption") if m in inv.models]
    others = [m for m in inv.models if m not in shown]
    items = _sorted(inv.items)
    for kind in KINDS:
        rows = []
        for it in (x for x in items if x.kind == kind):
            md = meta.get(it.key, {})
            row: list[object] = [
                f"`{it.name}`",
                md.get("label", ""),
                md.get("description", ""),
                md.get("units", ""),
                it.dimensions,
                it.module,
            ]
            if kind in ("parameter", "table"):
                ref = it.values.get(shown[0], "") if shown else ""
                differs = [m for m in others if it.values.get(m, "") != ref]
                row += [it.values.get(m, "") for m in shown]
                row += [
                    ", ".join(differs),
                    it.classification,
                    _lever(it, strengths) if kind == "parameter" else it.lever,
                ]
            row.append(md.get("status", ""))
            rows.append(row)
        head = ["Name", "Label", "Description", "Units", "Dimensions", "Module"]
        if kind in ("parameter", "table"):
            head += [*shown, "Differs in", "Class", "Lever"]
        head.append("Status")
        lines += [f"## {SECTION_TITLES[kind]}", "", f"{len(rows)} items.", ""]
        lines += _table(head, rows)
        lines.append("")
    lines += [
        "## Feedback-loop terms",
        "",
        "The seven terms of `phase9`'s four feedback loops (`docs/model-changes-phase9.md`). Each is off at "
        "strength 0; the range is the evidence's low / base / high.",
        "",
    ]
    pm = Params.baseline("phase9").scalars if "phase9" in inv.models else {}
    mods = {it.key: it.module for it in inv.items}
    trows = []
    for lt in LOOP_TERM_TABLE:
        vals = ", ".join(f"`{s}` {pm.get(s)!r}" for s in lt.strengths)
        path, line = lt.section.split(":")
        link = f"[{path.split('/')[-1]}:{line}]({path.removeprefix('docs/')}#L{line})"
        trows.append([lt.term, lt.title, vals, lt.evidence, mods.get((lt.strengths[0], "parameter"), ""), link])
    lines += _table(["Term", "What", "Strength in phase9", "Evidence range", "Module", "Design note"], trows)
    lines += ["", "## Feedback loops (diagrams)", "", *loops]
    lines += [
        "## Name clashes",
        "",
        "Names shared by items of different kinds. Nothing is renamed; each entry is qualified by its kind, and "
        "each description states the clash.",
        "",
    ]
    crow = []
    for name, its in name_clashes(inv.items).items():
        crow.append([f"`{name}`", "; ".join(f"`{name}` ({it.kind}, {it.module})" for it in its)])
    lines += _table(["Name", "Items"], crow)
    return "\n".join(lines) + "\n"


LOOP_RULING: Final = re.compile(r"\bE\d+\b")


def _figure(view: str, alt: str, caption: str) -> list[str]:
    return [f"![{alt}](model/diagrams/svg/{view}.svg)", "", f"_{caption}_", ""]


def diagram_sections(root: Path = ROOT) -> tuple[list[str], list[str]]:
    """The "Diagrams" and "Feedback loops (diagrams)" sections: the exported SVGs with their captions (slice 10b),
    and the loop table from ``docs/model/loop_summary.csv``."""
    src = DG.read_sources(root)
    pairs = DG.module_pairs(src)
    diagrams = [
        "Generated by `tools/model_diagrams.py` from the curated metadata, `docs/model/edges.csv` and the loop "
        "inventory. The editable sources are the `.drawio` files in [`model/diagrams/`](model/diagrams/), with their "
        "layouts in the `.geometry.json` sidecars; PNG copies at twice the size are in `model/diagrams/png/`.",
        "",
        "### Overview",
        "",
        *_figure(
            "overview",
            "Overview: the model's eight modules",
            f"The eight modules and the {len(pairs)} module pairs that one module's stocks, flows and auxiliaries "
            f"link to another's items ({sum(pairs.values())} links). The label and width give the number of links; "
            "a dashed arrow is a single link.",
        ),
        "### The article set",
        "",
        "Five small diagrams for a reader outside the project. Every node stands for named items of the "
        "model and every link is a signed path in `docs/model/loops.csv` (the wording is in "
        "`src/aisim/data/model_articles.csv`).",
        "",
    ]
    for view, art in DG.ARTICLE_VIEWS.items():
        story = next(r for r in src.articles if r["article"] == art and r["part"] == "story")
        diagrams += [f"#### {art}. {story['label']}", "", *_figure(view, f"{art}. {story['label']}", story["story"])]
    loops = [
        "Five causal-loop panels drawn from the loop inventory: `docs/model/loops.csv` (one row per link, with its "
        "sign, the code line and the regime it needs) and `docs/model/loop_summary.csv` (one row per loop). Each "
        "panel's legend gives its marks; the stress set is "
        f"'{DG.STRESS_SET}'. Open chains are dashed; replaced loops (R4, B8) are noted, not drawn.",
        "",
    ]
    for view, spec in DG.PANEL_VIEWS.items():
        ids = sorted(k for k, r in src.summary.items() if r["panel"] == spec.key)
        caption = f"Loops: {', '.join(ids)}. " + " ".join(c.replace("\n", " ") for c in spec.captions)
        loops += [f"### {spec.title}", "", *_figure(view, spec.title, caption)]
    rows = []
    for lid, r in src.summary.items():
        ruling = ", ".join(dict.fromkeys(LOOP_RULING.findall(r["status_basis"]))) or "-"
        polarity = r["code_polarity"].split()[0].strip(":,(") if r["code_polarity"] else ""
        rows.append([lid, r["name"], polarity, r["status"], r["acts_phase9_base"], r["acts_stress_set"], ruling])
    loops += ["### The loops", "", f"{len(rows)} loops (`docs/model/loop_summary.csv`).", ""]
    loops += _table(["Loop", "Name", "Polarity", "Status", "Acts in Base", "Acts in the stress set", "Ruling"], rows)
    loops.append("")
    return diagrams, loops


def build(root: Path = ROOT, inv: Inventory | None = None) -> dict[Path, str]:
    """The three generated files, by path relative to ``root``."""
    inv = build_inventory(root) if inv is None else inv
    meta = read_metadata(root)
    return {
        OUT_INVENTORY: render_inventory(inv, meta),
        OUT_EDGES: render_edges(inv),
        OUT_REFERENCE: render_reference(inv, meta, read_modules(root), *diagram_sections(root)),
    }


def stale(root: Path = ROOT, out_root: Path | None = None, inv: Inventory | None = None) -> list[Path]:
    """The generated files under ``out_root`` (default ``root``) that differ from what ``build`` gives."""
    out_root = root if out_root is None else out_root
    bad = []
    for path, text in build(root, inv).items():
        p = out_root / path
        if not p.exists() or p.read_bytes() != text.encode("utf-8"):
            bad.append(path)
    return bad


def write(root: Path = ROOT) -> list[Path]:
    """Write the three generated files under ``root``; returns the paths."""
    out = build(root)
    for path, text in out.items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        with (root / path).open("w", encoding="utf-8", newline="") as f:
            f.write(text)
    return list(out)


def counts(inv: Inventory) -> dict[str, int]:
    """Items by kind, with the named and unnamed flows apart."""
    c = Counter(it.kind for it in inv.items)
    out = {k: c[k] for k in KINDS}
    out["flow (named)"] = sum(1 for it in inv.items if it.kind == "flow" and not it.name.startswith("flow:"))
    out["flow (unnamed)"] = out["flow"] - out["flow (named)"]
    out["total"] = len(inv.items)
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="regenerate the three files")
    g.add_argument("--check", action="store_true", help="exit 1 if any generated file is stale")
    ap.add_argument("--counts", action="store_true", help="print the item counts by kind")
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this repository)")
    a = ap.parse_args(argv)
    if a.counts:
        import aisim

        inv = build_inventory(a.root)
        print("aisim.__file__ =", aisim.__file__)
        print("models", inv.models)
        print(counts(inv))
        print("instances", {k: sum(it.n_instances for it in inv.items if it.kind == k) for k in KINDS})
        print("edges", len(inv.edges), "nodes", len({e.source for e in inv.edges} | {e.target for e in inv.edges}))
    if a.write:
        for path in write(a.root):
            print("wrote", path.as_posix())
    if a.check:
        bad = stale(a.root)
        for path in bad:
            print("stale:", path.as_posix())
        if bad:
            print("regenerate with: uv run python tools/model_docs.py --write")
            return 1
        print("model docs: all generated files are current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
