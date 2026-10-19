"""The model's static dependency graph: an AST pass over the scalar engine, with no run and no tracing.

A port of recon 10's static method (D1, D2). For each section function (S2-S13), ``integrate.py`` and the feedback-loop
helpers of ``loops.py``, every assignment's target is linked to the names it reads:

- **Aliases.** A local whose one assignment is a pure chain to a root (``H = st["H"]``, ``f = VF[v]``) resolves to
  that root: a stock (``st``), a parameter (``pr``), a table (``tb``), an upstream intermediate (``s`` or a section
  argument) or the year (``y``).
- **Call-site binding.** A section function's arguments are bound to the expressions ``run()`` passes it
  (``engine.py``), so ``vac.promo`` in ``run()`` makes ``promo`` in ``switching`` the intermediate ``promo``. A call
  to a ``loops.py`` helper is replaced by the helper's own reads, its arguments bound to the call site's expressions
  (``fl[u][l]["quits"]`` inside ``loops.vol_cell`` is ``fl.quits`` where the section passes ``fl``).
- **Dynamic keys.** ``pr["QuitRate_" + l]`` and ``pr[f"NormalTTF_{r}_{l}"]`` map to their parameter family (scalar
  names grouped by trailing dimension tokens, ``param_families``).
- **Named and root levels.** At the ``named`` level a local that its function returns as a named field stops the
  expansion (``quits`` is ``fl.quits``); at the ``root`` level expansion runs through it.
- **Control dependences.** With ``control=True`` the tests of enclosing ``if`` statements and conditional expressions
  are inputs too.
- **Dict values.** ``x.values()`` reads ``x``, so ``Completion = sum(CompE.values())`` links ``CompE`` to
  ``Completion`` (slice 10b).
- **S0.** ``run()`` tilts ``SrcPerc`` by ``GCCMomentum`` once before the time loop (``tilt_sourcing_perception``); it
  is added as one edge, as recon D2 did.

Dimensions collapse: index variables and constant dimension values (``H["OV"]``) are dropped, so an edge links named
items, not instances. ``record.py`` (outputs) and the rest of ``engine.py`` are not part of the graph.

Node names carry their kind as a prefix: ``param:QuitRate``, ``table:SectorShare``, ``stock:H``, ``item:fl.openings``,
``time:y``. ``root`` is a repository root, so the same pass can read another tree (slice 10a validated the port on
``ccfe6eb``, recon 10's commit).

Usage: ``uv run python tools/model_graph.py [--root PATH] [--counts]``
"""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from aisim import dims as D

ROOT: Final = Path(__file__).resolve().parent.parent
SCALAR: Final = Path("src/aisim/scalar")
MODULES: Final = ("capability", "work", "workforce", "labour_market", "finance", "sourcing", "adoption", "consumer")
"""The 8 engine modules that hold the sections, in the order of ``model_modules.csv``."""

DIMSETS: Final[Mapping[str, tuple[str, ...]]] = {
    "level": D.LEVELS,
    "region": D.REGIONS,
    "sector": D.SECTORS,
    "worktype": D.WTYPES,
    "type": D.TYPES,
    "vendor": D.VENDORS,
    "employer": D.EMPLOYERS,
    "unit": D.UNITS,
}
ALL_DIM_VALUES: Final = frozenset(v for vals in DIMSETS.values() for v in vals)
STEP_ATTRS: Final = frozenset(
    [
        "cap",
        "work",
        "mix",
        "staffing",
        "unemp",
        "vac",
        "switching",
        "visa",
        "exits",
        "hiring",
        "ttf",
        "pools",
        "costs",
        "contracts",
        "flows",
        "books",
        "wages",
        "spend",
        "adoption",
        "drivers",
        "options",
        "consumer",
        "targets",
    ]
)
"""The ``Step`` attributes: a path through ``s.<attr>`` names the intermediate without them."""
SPECIAL_BINDINGS: Final[Mapping[str, list[str]]] = {
    "pr": ["pr"],
    "st": ["st"],
    "tb": ["tb"],
    "y": ["time"],
    "W": ["pr", "W_*"],
    "RegDrag": ["item", "cons", "*", "RegDrag"],
    "demand_growth_late": ["pr", "DemandGrowthLate"],
}
"""``run()`` locals that are not section results: how each binds when passed to a section."""

Token = tuple[str, ...]
"""A read: ``("param", family)``, ``("stock", name)``, ``("table", name)``, ``("time", "y")``, ``("item", dotted)``,
``("local", name, field)`` inside a function, or ``("arg", name, *path)`` inside a ``loops.py`` helper."""
Key = tuple[str, str | None]
"""A local written by a function: its name and, for a field write (``x_["openings"] = ...``), the field."""


# ---- parameter families ---------------------------------------------------------------------------------------------


def dim_of_keys(keys: set[str]) -> tuple[str, int]:
    """Name the dimension a key set indexes: an exact match first, else the smallest dimension containing it."""
    for name, vals in DIMSETS.items():
        if set(vals) == keys:
            return name, len(keys)
    best: str | None = None
    for name, vals in DIMSETS.items():
        if keys <= set(vals) and (best is None or len(vals) < len(DIMSETS[best])):
            best = name
    if best is None:
        return "?" + ",".join(sorted(keys)), len(keys)
    return f"{best}({','.join(k for k in DIMSETS[best] if k in keys)})", len(keys)


@dataclass(frozen=True)
class Family:
    """A parameter family: scalars sharing a stem, indexed by trailing dimension tokens."""

    members: tuple[str, ...]
    dims: tuple[str, ...]
    suffixes: Mapping[str, str]


def _tokens(name: str) -> list[str]:
    return name.replace("SI_IN", "SI\x00IN").replace("SI_ON", "SI\x00ON").split("_")


def _detok(t: str) -> str:
    return t.replace("\x00", "_")


def param_families(names: Sequence[str]) -> dict[str, Family]:
    """Group scalar names into families by trailing dimension-value tokens, as the code builds them (``pr["X_" + e]``).

    A family needs at least two members sharing the stem and the number of suffix tokens; any other name is its own
    family.
    """
    split: dict[str, tuple[str, tuple[str, ...]]] = {}
    for n in names:
        toks = _tokens(n)
        k = 0
        while k < len(toks) - 1 and _detok(toks[len(toks) - 1 - k]) in ALL_DIM_VALUES:
            k += 1
        stem = "_".join(_detok(t) for t in toks[: len(toks) - k])
        split[n] = (stem, tuple(_detok(t) for t in toks[len(toks) - k :]))
    groups: dict[tuple[str, int], list[str]] = {}
    for n, (stem, suf) in split.items():
        if suf:
            groups.setdefault((stem, len(suf)), []).append(n)
    fams: dict[str, Family] = {}
    grouped: set[str] = set()
    for (stem, k), members in groups.items():
        if len(members) < 2:
            continue
        dims_ = tuple(dim_of_keys({split[m][1][pos] for m in members})[0] for pos in range(k))
        fams[stem] = Family(tuple(members), dims_, {m: "/".join(split[m][1]) for m in members})
        grouped.update(members)
    for n in names:
        if n not in grouped:
            fams[n] = Family((n,), (), {n: ""})
    return fams


def parameter_names(root: Path) -> list[str]:
    """The scalar parameter names of ``parameters.csv``, in file order."""
    with (root / "src/aisim/data/parameters.csv").open(encoding="utf-8", newline="") as f:
        return [r["name"] for r in csv.DictReader(f)]


# ---- one function ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Summary:
    """What a ``loops.py`` helper reads: its return value's reads (data and control) and its stock writes.

    ``("arg", name, *path)`` tokens stand for the helper's arguments, bound at each call site.
    """

    params: tuple[str, ...]
    data: frozenset[Token]
    ctrl: frozenset[Token]
    writes: Mapping[str, tuple[frozenset[Token], frozenset[Token], frozenset[int]]]


Resolver = Callable[[ast.Call], "Summary | None"]


@dataclass
class FuncInfo:
    """The assignments of one function: what each local reads, where, and which locals it returns as named fields."""

    name: str
    module: str
    aliases: dict[str, list[str]] = field(default_factory=dict)
    deps: dict[Key, set[Token]] = field(default_factory=dict)
    lines: dict[Key, set[int]] = field(default_factory=dict)
    ctrl: dict[Key, set[Token]] = field(default_factory=dict)
    outputs: dict[str, list[Key]] = field(default_factory=dict)
    named_local: dict[str, str] = field(default_factory=dict)
    local_fields: dict[str, set[str]] = field(default_factory=dict)
    ext_lines: dict[Key, set[str]] = field(default_factory=dict)
    """Lines in another file that write a key (a ``loops.py`` helper's stock writes, called from ``integrate``)."""


class Analyzer:
    """Resolves the names an expression reads, within one function."""

    def __init__(
        self,
        fi: FuncInfo,
        bindings: Mapping[str, list[str]],
        fams: Mapping[str, Family],
        resolve: Resolver | None = None,
    ) -> None:
        self.fi = fi
        self.b = bindings
        self.fams = fams
        self.fam_of = {m: f for f, d in fams.items() for m in d.members}
        self.computed: set[str] = set()
        self.resolve = resolve

    def param_token(self, key: str) -> str:
        """The parameter family a (possibly dynamic, ``*``) key names."""
        if "*" in key:
            stem = key.split("*")[0].rstrip("_")
            while stem and stem not in self.fams:
                if "_" not in stem:
                    break
                stem = stem.rsplit("_", 1)[0]
            return stem
        return self.fam_of.get(key, key)

    def chain(self, node: ast.expr) -> list[str] | None:
        """The access path of a name, attribute or subscript chain, from its root; None if it has no root."""
        if isinstance(node, ast.Name):
            n = node.id
            if n in ("pr", "st", "tb", "s"):
                return [n] if n != "s" else ["item"]
            if n in self.fi.aliases and n not in self.computed:
                return list(self.fi.aliases[n])
            if n in self.b:
                return list(self.b[n])
            if n in self.computed or n in self.fi.local_fields:
                return ["local", n]
            return None
        if isinstance(node, ast.Attribute):
            base = self.chain(node.value)
            return None if base is None else [*base, node.attr]
        if isinstance(node, ast.Subscript):
            base = self.chain(node.value)
            if base is None:
                return None
            s = node.slice
            if isinstance(s, ast.Constant) and isinstance(s.value, str):
                return [*base, s.value]
            if isinstance(s, ast.BinOp) and isinstance(s.left, ast.Constant):
                return [*base, str(s.left.value) + "*"]
            if isinstance(s, ast.JoinedStr):
                return [*base, "".join(str(v.value) if isinstance(v, ast.Constant) else "*" for v in s.values)]
            return [*base, "*"]
        return None

    def token(self, path: list[str]) -> Token | None:
        """The node an access path names, or None."""
        root = path[0]
        if root == "pr":
            return ("param", self.param_token(path[1])) if len(path) > 1 else None
        if root == "st":
            return ("stock", path[1]) if len(path) > 1 else None
        if root == "tb":
            return ("table", path[1]) if len(path) > 1 else None
        if root == "time":
            return ("time", "y")
        if root == "item":
            parts = [p for p in path[1:] if p != "*" and p not in ALL_DIM_VALUES and "*" not in p]
            parts = [p for p in parts if p not in STEP_ATTRS]
            return ("item", ".".join(parts)) if parts else None
        if root == "local":
            name = path[1]
            flds = self.fi.local_fields.get(name, set())
            fld = next((p for p in path[2:] if p in flds), None)
            return ("local", name, fld) if fld else ("local", name, "")
        if root == "arg":
            return ("arg", *path[1:])
        return None

    def reads(self, e: ast.expr | None, control: bool = False) -> set[Token]:
        """The nodes and locals an expression reads; with ``control``, also the tests inside it."""
        out: set[Token] = set()
        if e is None:
            return out
        if isinstance(e, ast.Name | ast.Attribute | ast.Subscript):
            c = self.chain(e)
            if c is not None:
                t = self.token(c)
                if t is not None:
                    out.add(t)
                    return out
                if c and c[0] in ("pr", "st", "tb", "item"):
                    return out
            if isinstance(e, ast.Name):
                return out
            if isinstance(e, ast.Attribute):
                return self.reads(e.value, control)
            out |= self.reads(e.value, control)
            out |= self.reads(e.slice, control)
            return out
        if isinstance(e, ast.IfExp):
            out |= self.reads(e.body, control) | self.reads(e.orelse, control)
            if control:
                out |= self.reads(e.test, control)
            return out
        if isinstance(e, ast.Call):
            summ = self.resolve(e) if self.resolve is not None else None
            if summ is not None:
                return self.substitute(summ, summ.data | (summ.ctrl if control else frozenset()), e, control)
            if isinstance(e.func, ast.Attribute) and e.func.attr == "values" and not e.args and not e.keywords:
                return self.reads(e.func.value, control)  # sum(x.values()) reads x
            for a in e.args:
                out |= self.reads(a, control)
            for kw in e.keywords:
                out |= self.reads(kw.value, control)
            return out
        if isinstance(e, ast.ListComp | ast.SetComp | ast.GeneratorExp):
            out |= self.reads(e.elt, control)
            if control:
                for g in e.generators:
                    for cond in g.ifs:
                        out |= self.reads(cond, control)
            return out
        if isinstance(e, ast.DictComp):
            out |= self.reads(e.value, control)
            if control:
                for g in e.generators:
                    for cond in g.ifs:
                        out |= self.reads(cond, control)
            return out
        if isinstance(e, ast.Dict):
            for v in e.values:
                out |= self.reads(v, control)
            return out
        for child in ast.iter_child_nodes(e):
            if isinstance(child, ast.expr):
                out |= self.reads(child, control)
        return out

    def substitute(self, summ: Summary, tokens: frozenset[Token], call: ast.Call, control: bool) -> set[Token]:
        """A helper's reads at one call site: each argument token replaced by what the passed expression names."""
        out: set[Token] = set()
        for t in tokens:
            if t[0] != "arg":
                out.add(t)
                continue
            arg = _call_arg(summ.params, call, t[1])
            if arg is None:
                continue
            suffix = list(t[2:])
            c = self.chain(arg) if suffix else None
            tok = self.token([*c, *suffix]) if c is not None else None
            if tok is not None:
                out.add(tok)
            else:
                out |= self.reads(arg, control)
        return out


def _call_arg(params: tuple[str, ...], call: ast.Call, name: str) -> ast.expr | None:
    """The expression a call passes for parameter ``name``, positionally or by keyword."""
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    i = params.index(name)
    return call.args[i] if i < len(call.args) else None


def _target_key(t: ast.expr) -> Key | None:
    """The local (name, field) an assignment target writes."""
    if isinstance(t, ast.Name):
        return (t.id, None)
    if isinstance(t, ast.Subscript):
        node: ast.expr = t
        fld = None
        while isinstance(node, ast.Subscript):
            s = node.slice
            if isinstance(s, ast.Constant) and isinstance(s.value, str) and s.value not in ALL_DIM_VALUES:
                fld = s.value
            node = node.value
        if isinstance(node, ast.Name):
            return (node.id, fld)
    return None


def _is_chain(e: ast.expr) -> bool:
    while isinstance(e, ast.Attribute | ast.Subscript):
        e = e.value
    return isinstance(e, ast.Name)


def _is_constructor(v: ast.expr) -> bool:
    return isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id[0].isupper()


def _field_key(k: ast.expr | None) -> str | None:
    if isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value not in ALL_DIM_VALUES:
        return k.value
    return None


def analyse_function(
    fn: ast.FunctionDef,
    module: str,
    bindings: Mapping[str, list[str]],
    fams: Mapping[str, Family],
    resolve: Resolver | None = None,
    ret: str = "__return__",
) -> tuple[FuncInfo, Analyzer]:
    """Every assignment of ``fn`` with what it reads and its enclosing tests; ``ret`` names the return value."""
    fi = FuncInfo(fn.name, module)
    an = Analyzer(fi, bindings, fams, resolve)
    assigns: list[tuple[ast.expr, ast.expr, int, bool, list[ast.expr]]] = []

    def visit(stmts: list[ast.stmt], tests: list[ast.expr]) -> None:
        for s in stmts:
            if isinstance(s, ast.Assign):
                for t in s.targets:
                    if isinstance(t, ast.Tuple) and isinstance(s.value, ast.Tuple):
                        for tt, vv in zip(t.elts, s.value.elts, strict=True):
                            assigns.append((tt, vv, s.lineno, False, tests))
                    else:
                        assigns.append((t, s.value, s.lineno, False, tests))
            elif isinstance(s, ast.AnnAssign) and s.value is not None:
                assigns.append((s.target, s.value, s.lineno, False, tests))
            elif isinstance(s, ast.AugAssign):
                assigns.append((s.target, s.value, s.lineno, True, tests))
            elif isinstance(s, ast.For):
                visit(s.body, tests)
            elif isinstance(s, ast.If):
                visit(s.body, [*tests, s.test])
                visit(s.orelse, [*tests, s.test])
            elif isinstance(s, ast.Return) and s.value is not None:
                assigns.append((ast.Name(id=ret), s.value, s.lineno, False, tests))

    visit(fn.body, [])
    # aliases (a name whose one assignment is a pure chain to a root) and computed locals
    by_name: dict[str, list[ast.expr]] = {}
    for t, v, _, aug, _ in assigns:
        k = _target_key(t)
        if k:
            by_name.setdefault(k[0], []).append(v if not aug else ast.Constant(value=None))
            if k[1]:
                fi.local_fields.setdefault(k[0], set()).add(k[1])
    for name, vals in by_name.items():
        if len(vals) == 1 and _is_chain(vals[0]):
            c = an.chain(vals[0])
            if c is not None and c[0] in ("pr", "st", "tb", "item", "time", "arg"):
                fi.aliases[name] = c
                continue
        an.computed.add(name)
    # fields of locals built from dict literals or constructor keywords
    for t, v, _, _, _ in assigns:
        k = _target_key(t)
        if not k:
            continue
        for node in ast.walk(v):
            if isinstance(node, ast.Dict):
                for kk in node.keys:
                    f = _field_key(kk)
                    if f is not None:
                        fi.local_fields.setdefault(k[0], set()).add(f)
                        an.computed.add(k[0])
        if isinstance(v, ast.Call) and v.keywords and _is_constructor(v):
            for kw in v.keywords:
                if kw.arg:
                    fi.local_fields.setdefault(k[0], set()).add(kw.arg)
    # what each local reads
    for t, v, line, _aug, tests in assigns:
        k = _target_key(t)
        if not k:
            continue
        name, fld = k
        if name == "__return__" or (isinstance(v, ast.Call) and v.keywords and _is_constructor(v)):
            for kw in v.keywords if isinstance(v, ast.Call) else []:
                if not kw.arg:
                    continue
                key: Key = (name, kw.arg)
                fi.deps.setdefault(key, set()).update(an.reads(kw.value))
                fi.ctrl.setdefault(key, set()).update(an.reads(kw.value, True) - an.reads(kw.value))
                fi.lines.setdefault(key, set()).add(kw.value.lineno)
                if tests:
                    fi.ctrl.setdefault(key, set()).update(*(an.reads(x, True) for x in tests))
            continue
        if isinstance(v, ast.Dict) and any(_field_key(kk) is not None for kk in v.keys):
            for kk, vv in zip(v.keys, v.values, strict=True):
                f = _field_key(kk)
                if f is not None:
                    key = (name, f)
                    fi.deps.setdefault(key, set()).update(an.reads(vv))
                    fi.lines.setdefault(key, set()).add(line)
            continue
        if isinstance(v, ast.DictComp | ast.Dict):
            # nested dict comprehensions whose leaves are field dicts: {u: {l: {"in": 0.0, ...}}}
            inner: ast.expr = v
            while isinstance(inner, ast.DictComp) and isinstance(inner.value, ast.DictComp | ast.Dict):
                inner = inner.value
            if isinstance(inner, ast.Dict) and inner.keys and all(_field_key(kk) is not None for kk in inner.keys):
                for kk, vv in zip(inner.keys, inner.values, strict=True):
                    fkey: Key = (name, _field_key(kk))
                    fi.deps.setdefault(fkey, set()).update(an.reads(vv))
                    fi.lines.setdefault(fkey, set()).add(line)
                continue
        key = (name, fld)
        fi.deps.setdefault(key, set()).update(an.reads(v))
        fi.lines.setdefault(key, set()).add(line)
        fi.ctrl.setdefault(key, set()).update(an.reads(v, True) - an.reads(v))  # tests inside the value
        if tests:
            fi.ctrl.setdefault(key, set()).update(*(an.reads(x, True) for x in tests))
    # outputs: return Constructor(field=local)
    for r in (n for n in ast.walk(fn) if isinstance(n, ast.Return) and isinstance(n.value, ast.Call)):
        assert isinstance(r.value, ast.Call)
        for kw in r.value.keywords:
            if not kw.arg:
                continue
            base, v = kw.arg, kw.value
            if isinstance(v, ast.Name) and fi.local_fields.get(v.id):
                for f_ in sorted(fi.local_fields[v.id]):
                    fi.outputs[f"{base}.{f_}"] = [(v.id, f_)]
                    fi.named_local.setdefault(v.id + "." + f_, f"{base}.{f_}")
            elif isinstance(v, ast.Name):
                fi.outputs[base] = [(v.id, None)]
                fi.named_local[v.id] = base
            else:
                fi.outputs[base] = [("__return__", kw.arg)]
    # constructor locals inside dicts (VF[v] = VendorTerms(...)): field locals named by keyword values
    for t, v, _, _, _ in assigns:
        k = _target_key(t)
        if k and isinstance(v, ast.Call) and _is_constructor(v):
            for kw in v.keywords:
                if kw.arg and isinstance(kw.value, ast.Name) and kw.value.id != k[0]:
                    for item, keys in fi.outputs.items():
                        if keys == [(k[0], kw.arg)]:
                            fi.named_local.setdefault(kw.value.id, item)
    return fi, an


def expand(
    fi: FuncInfo,
    key: Key,
    level: str,
    control: bool = False,
    seen: frozenset[Key] = frozenset(),
    self_item: str | None = None,
) -> dict[Token, None]:
    """A local's reads expanded to nodes (a read that names ``self_item`` itself is expanded, not stopped at)."""
    out: dict[Token, None] = {}
    deps = set(fi.deps.get(key, set()))
    if control:
        deps |= fi.ctrl.get(key, set())
    if key[1] is None:  # the whole local: all its fields
        for (n, f), d in fi.deps.items():
            if n == key[0] and f is not None:
                deps |= d
    for t in sorted(deps):
        if t[0] != "local":
            out[t] = None
            continue
        name, fld = t[1], (t[2] or None)
        lk: Key = (name, fld)
        nm = fi.named_local.get(f"{name}.{fld}") if fld else fi.named_local.get(name)
        if nm is not None and level == "named" and lk != key and lk not in seen and nm != self_item:
            out[("item", nm)] = None
            continue
        if lk in seen or lk == key:
            continue
        if lk not in fi.deps and fld is not None and (name, None) in fi.deps:
            lk = (name, None)
        out.update(expand(fi, lk, level, control, seen | {key}, self_item))
    return out


# ---- the loops.py helpers --------------------------------------------------------------------------------------------


class Loops:
    """Summaries of the ``loops.py`` helpers, computed on demand (a helper may call another)."""

    def __init__(self, root: Path, fams: Mapping[str, Family]) -> None:
        path = root / SCALAR / "loops.py"
        self.fams = fams
        self.defs: dict[str, ast.FunctionDef] = {}
        if path.exists():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            self.defs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.cache: dict[str, Summary] = {}

    def summary(self, name: str) -> Summary:
        """The summary of helper ``name``."""
        if name not in self.cache:
            fn = self.defs[name]
            params = tuple(a.arg for a in fn.args.args)
            binds = {p: ["arg", p] for p in params if p not in ("pr", "st", "tb", "s")}
            fi, _ = analyse_function(fn, "loops", binds, self.fams, self.inner, ret="__ret__")
            data = frozenset(expand(fi, ("__ret__", None), "root"))
            ctrl = frozenset(expand(fi, ("__ret__", None), "root", True)) - data
            writes = {}
            for key in sorted(k for k in fi.deps if k[0] == "st" and k[1] is not None):
                d = frozenset(expand(fi, key, "root"))
                c = frozenset(expand(fi, key, "root", True)) - d
                assert key[1] is not None
                writes[key[1]] = (d, c, frozenset(fi.lines[key]))
            self.cache[name] = Summary(params, data, ctrl, writes)
        return self.cache[name]

    def inner(self, call: ast.Call) -> Summary | None:
        """A call inside ``loops.py``: a helper by its bare name."""
        if isinstance(call.func, ast.Name) and call.func.id in self.defs:
            return self.summary(call.func.id)
        return None

    def outer(self, call: ast.Call) -> Summary | None:
        """A call from another module: ``loops.<helper>``."""
        f = call.func
        if (
            isinstance(f, ast.Attribute)
            and isinstance(f.value, ast.Name)
            and f.value.id == "loops"
            and f.attr in self.defs
        ):
            return self.summary(f.attr)
        return None


# ---- the engine ------------------------------------------------------------------------------------------------------


def engine_bindings(root: Path) -> dict[str, dict[str, list[str]]]:
    """For each section function, each parameter bound to the path ``run()`` passes it."""
    tree = ast.parse((root / SCALAR / "engine.py").read_text(encoding="utf-8"))
    run = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run")
    sigs: dict[str, list[str]] = {}
    for m in MODULES:
        for n in ast.parse((root / SCALAR / f"{m}.py").read_text(encoding="utf-8")).body:
            if isinstance(n, ast.FunctionDef):
                sigs[n.name] = [a.arg for a in n.args.args] + [a.arg for a in n.args.kwonlyargs]
    section_vars: set[str] = set()
    out: dict[str, dict[str, list[str]]] = {}

    def bind(e: ast.expr) -> list[str] | None:
        if isinstance(e, ast.Name):
            if e.id in SPECIAL_BINDINGS:
                return list(SPECIAL_BINDINGS[e.id])
            if e.id in section_vars:
                return ["item"]
            return None
        if isinstance(e, ast.Attribute):
            b = bind(e.value)
            return None if b is None else [*b, e.attr]
        return None

    for st_ in ast.walk(run):
        if isinstance(st_, ast.Assign) and isinstance(st_.value, ast.Call) and isinstance(st_.value.func, ast.Name):
            fn = st_.value.func.id
            if fn in sigs:
                params = sigs[fn]
                b: dict[str, list[str]] = {}
                for i, a in enumerate(st_.value.args):
                    p = bind(a)
                    if p is not None:
                        b[params[i]] = p
                for kw in st_.value.keywords:
                    if kw.arg:
                        p = bind(kw.value)
                        if p is not None:
                            b[kw.arg] = p
                out[fn] = b
                tgt = st_.targets[0]
                assert isinstance(tgt, ast.Name)
                section_vars.add(tgt.id)
    return out


@dataclass(frozen=True)
class Edge:
    """One collapsed edge: ``source`` to ``target`` (prefixed node names), its kind and where the code makes it."""

    source: str
    target: str
    module: str
    file_line: str


@dataclass(frozen=True)
class Graph:
    """The analysed engine: section functions, ``integrate``, and the families used to name parameters."""

    root: Path
    fams: Mapping[str, Family]
    sections: Mapping[str, FuncInfo]
    integrate: FuncInfo
    s0: Edge


def analyse(root: Path = ROOT) -> Graph:
    """Parse the section functions, ``integrate`` and the ``loops.py`` helpers of the tree at ``root``."""
    fams = param_families(parameter_names(root))
    loops = Loops(root, fams)
    binds = engine_bindings(root)
    sections: dict[str, FuncInfo] = {}
    for m in MODULES:
        for n in ast.parse((root / SCALAR / f"{m}.py").read_text(encoding="utf-8")).body:
            if isinstance(n, ast.FunctionDef) and n.name in binds:
                sections[n.name] = analyse_function(n, m, binds[n.name], fams, loops.outer)[0]
    tree = ast.parse((root / SCALAR / "integrate.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "integrate")
    integ, an = analyse_function(fn, "integrate", {"s": ["item"]}, fams, loops.outer)
    # stocks written inside loops.py helpers called from integrate (pre: the 2024 references; post: the signals)
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and (summ := loops.outer(node)) is not None:
            for stock, (d, c, lns) in summ.writes.items():
                key = ("st", stock)
                integ.deps.setdefault(key, set()).update(an.substitute(summ, d, node, False))
                integ.ctrl.setdefault(key, set()).update(an.substitute(summ, d | c, node, True))
                integ.ext_lines.setdefault(key, set()).update(f"{SCALAR.as_posix()}/loops.py:{x}" for x in lns)
    return Graph(root, fams, sections, integ, _s0_edge(root))


def _s0_edge(root: Path) -> Edge:
    """S0: ``GCCMomentum`` tilts ``SrcPerc`` once before the time loop (``tilt_sourcing_perception`` and its call)."""
    path = root / SCALAR / "engine.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "tilt_sourcing_perception")
    call = next(
        n.lineno
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "tilt_sourcing_perception"
    )
    return Edge(
        "param:GCCMomentum",
        "stock:SrcPerc",
        "engine",
        f"{SCALAR.as_posix()}/engine.py:{fn.lineno}-{fn.end_lineno};{call}",
    )


def section_edges(
    g: Graph, level: str = "named", control: bool = False, modules: Sequence[str] = MODULES
) -> list[Edge]:
    """Edges into every named output of every section function: (source, ``item:<output>``, module, file:line)."""
    out: list[Edge] = []
    for fi in g.sections.values():
        if fi.module not in modules:
            continue
        for item, keys in fi.outputs.items():
            srcs: dict[Token, None] = {}
            lines: set[int] = set()
            for k in keys:
                srcs.update(expand(fi, k, level, control, self_item=item))
                lines |= fi.lines.get(k, set())
                if k[1] is None:
                    for (n, _f), ls in fi.lines.items():
                        if n == k[0]:
                            lines |= ls
            for (n, f), ls in fi.lines.items():  # the named local's own assignments (openings = ...)
                if f is None and fi.named_local.get(n) == item:
                    lines |= ls
            fl = f"{SCALAR.as_posix()}/{fi.module}.py:" + ";".join(str(x) for x in sorted(lines))
            for s in srcs:
                if s[0] == "item" and s[1] == item:
                    continue
                out.append(Edge(":".join(s[:2]), "item:" + item, fi.module, fl))
    return out


def integrate_edges(g: Graph, control: bool = False) -> list[Edge]:
    """Edges into every stock: (source, ``stock:<name>``, ``integrate``, file:line)."""
    fi = g.integrate
    out: list[Edge] = []
    for (name, fld), _ in fi.deps.items():
        if name != "st" or fld is None:
            continue
        by_file: dict[str, set[int]] = {}
        if fi.lines.get((name, fld)):
            by_file[f"{SCALAR.as_posix()}/integrate.py"] = set(fi.lines[(name, fld)])
        for x in fi.ext_lines.get((name, fld), set()):
            path, line = x.rsplit(":", 1)
            by_file.setdefault(path, set()).add(int(line))
        fl = ";".join(f"{path}:" + ";".join(str(x) for x in sorted(ls)) for path, ls in by_file.items())
        for s in expand(fi, (name, fld), "named", control):
            out.append(Edge(":".join(s[:2]), "stock:" + fld, "integrate", fl))
    return out


@dataclass(frozen=True)
class GraphEdge:
    """A collapsed edge of the whole engine, with its dependence: data, or control only."""

    source: str
    target: str
    dependence: str
    file_line: str


def edges(root: Path = ROOT, g: Graph | None = None) -> list[GraphEdge]:
    """Every collapsed edge of the engine, with control dependences and the S0 tilt (recon D2), sorted.

    An edge that is a data dependence anywhere is ``data``; one found only through tests is ``control``. ``file_line``
    lists the lines that write the target, as ``path:line;line`` (a second file starts a new ``path:``).
    """
    g = analyse(root) if g is None else g
    data = {(e.source, e.target) for e in [*section_edges(g), *integrate_edges(g)]}
    data.add((g.s0.source, g.s0.target))
    where: dict[tuple[str, str], str] = {}
    for e in [*section_edges(g, control=True), *integrate_edges(g, control=True), g.s0]:
        where.setdefault((e.source, e.target), e.file_line)
    return [GraphEdge(s, t, "data" if (s, t) in data else "control", where[(s, t)]) for s, t in sorted(where)]


@dataclass(frozen=True)
class Node:
    """A graph node: its prefixed name, kind (param, table, stock, item, time) and the module that computes it.

    ``module`` is the section's module for an item, and empty for the others (the inventory assigns them); ``readers``
    are the modules whose code reads it, ``integrate`` for a stock update and ``engine`` for S0.
    """

    name: str
    kind: str
    module: str
    readers: tuple[str, ...]


def item_modules(g: Graph) -> dict[str, str]:
    """The module of every named output of every section function."""
    return {"item:" + item: fi.module for fi in g.sections.values() for item in fi.outputs}


def nodes(root: Path = ROOT, g: Graph | None = None, es: Sequence[GraphEdge] | None = None) -> list[Node]:
    """Every node of the collapsed graph, sorted by name."""
    g = analyse(root) if g is None else g
    es = edges(root, g) if es is None else es
    imod = item_modules(g)
    readers: dict[str, set[str]] = {}
    for e in [*section_edges(g, control=True), *integrate_edges(g, control=True), g.s0]:
        readers.setdefault(e.source, set()).add(e.module)
    names = sorted({e.source for e in es} | {e.target for e in es})
    return [Node(n, n.split(":", 1)[0], imod.get(n, ""), tuple(sorted(readers.get(n, set())))) for n in names]


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    ap.add_argument("--root", type=Path, default=ROOT, help="repository root to read (default: this repository)")
    ap.add_argument("--counts", action="store_true", help="print edge and node counts")
    ap.add_argument("--csv", type=Path, help="write the edges as CSV (source, target, dependence, file_line)")
    a = ap.parse_args(argv)
    g = analyse(a.root)
    es = edges(a.root, g)
    ns = nodes(a.root, g, es)
    if a.counts:
        data = sum(1 for e in es if e.dependence == "data")
        print(f"root {a.root}")
        print(f"edges {len(es)} (data {data}, control only {len(es) - data}); nodes {len(ns)}")
        print("nodes by kind", dict(sorted(Counter(n.kind for n in ns).items())))
        kinds = Counter(f"{e.source.split(':')[0]}->{e.target.split(':')[0]}" for e in es)
        print("edges by kind", dict(sorted(kinds.items())))
    if a.csv:
        with a.csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["source", "target", "dependence", "file_line"])
            w.writerows((e.source, e.target, e.dependence, e.file_line) for e in es)
    return 0


if __name__ == "__main__":
    sys.exit(main())
