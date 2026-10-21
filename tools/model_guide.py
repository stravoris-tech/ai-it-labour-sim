"""The model guide: the scenarios, the levers and the main outputs with their phase9 Base values (slice 10d).

The guide (``docs/model-guide.md``) is the menu of questions the model can answer. It is generated from committed
data, never edited by hand:

- the scenarios from ``aisim.scenarios`` (``SCENARIOS``, then ``STRESS_SCENARIOS``), read at generation time;
- the levers from ``docs/model/inventory.csv`` (every row whose ``lever`` begins with "yes"), with their descriptions
  from ``src/aisim/data/model_docs.csv`` unchanged and their sensitivity ranges from ``tornado_levers``;
- the main outputs from ``tools/guide_outputs.csv`` (one ``model_docs.csv`` output name per row), with their
  ``phase9`` Base values measured at every step (dt 1/16) through the public API and rounded to 3 significant
  figures, so that platform floating-point differences cannot change the page;
- the labels of the dimension values from the specification's dimension table
  (``reference/prototype/spec/00_model_spec.md``).

It carries no build date and no commit hash, so two generations are byte-identical. ``tools/model_pdf.py`` prints it
as ``docs/model-guide.pdf`` and as a section of ``docs/model-reference.pdf``.

Usage: ``uv run --frozen python tools/model_guide.py --write | --check``. ``--check`` exits 1 if the committed guide
differs from what ``--write`` would write (``tests/test_model_guide.py`` runs the same check in the gate).
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

import numpy as np

from aisim import Experiment, Params, ValidationError, run_experiment
from aisim.dims import EMPLOYERS, REGIONS, VENDORS
from aisim.experiment.validate import validate
from aisim.scenarios import SCENARIOS, STRESS_SCENARIOS, tornado_levers

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools import model_docs as MD

ROOT: Final = Path(__file__).resolve().parent.parent
OUT: Final = Path("docs/model-guide.md")
OUTPUTS_CSV: Final = Path("tools/guide_outputs.csv")
INVENTORY: Final = Path("docs/model/inventory.csv")
MODEL_DOCS: Final = Path("src/aisim/data/model_docs.csv")
CATALOGUE: Final = Path("src/aisim/data/catalogue.csv")
SPEC: Final = Path("reference/prototype/spec/00_model_spec.md")
MODEL: Final = "phase9"
ALT: Final = "phase9_highadoption"
Y: Final = 2026.5
YEARS: Final = (2024.0, 2040.0)
OUTPUT_STATUSES: Final = ("drafted", "reviewed")
RANGE_HEAD: Final = "Sensitivity range (tornado_levers)"
"""``run_experiment`` samples only the levers an ``Experiment`` names (``sample`` defaults to none), so these ranges are
``tornado_levers``' sensitivity ranges, which a Monte Carlo may choose to sample."""

SECTIONS: Final = (
    "1. How to ask the model a question",
    "2. Scenarios",
    "3. Levers",
    "4. Main outputs",
    "5. Where to look next",
)

STRESS_INPUTS: Final[Mapping[str, str]] = {"PriceShock_OIT": "PriceShock"}
"""The one parameter a named set may set that is not a lever (operator ruling, slice 10d D1): the stress set's OIT
price shock, of the inventory family ``PriceShock`` (lever = no). Any other non-lever in a named set is an error."""
STRESS_FLAG: Final = "not a lever: a stress-test input (inventory lever = no)"

AT_Y: Final[Mapping[str, str]] = {
    "SrcCostSens": "steps",
    "JuniorCut": "steps",
    "PriceHorizon": "steps",
    "JevonsEps": "steps",
    "kR7": "steps",
    "g": "builds gradually",
    "VerifDecline": "builds gradually",
    "aL_max": "builds gradually",
    "AICostDecline": "builds gradually",
    "Verif": "cannot act from Y (a 2024 level)",
}
"""What a lever does at the perturb year Y, where the README records it ("Perturb from year Y"): the levers "whose own
effect is immediate still step at Y"; the rates of the closed-form paths continue from their base value at Y, so they
build gradually; ``Verif`` is a 2024 level. ``tests/test_model_guide.py`` checks this map against the README."""

SCENARIO_TEXT: Final[Mapping[str, str]] = {
    "Base": "The calibrated baseline, with no lever changed.",
    "Slow AI": "AI capability grows more slowly and checking AI output never gets cheaper.",
    "Fast AI": "AI capability grows faster and checking AI output gets cheaper faster.",
    "Strict regulation": "Regulation slows clients' adoption of AI more than in Base.",
    "Light regulation": "Regulation slows clients' adoption of AI less than in Base.",
    "Compute shock": "A temporary shortage of AI compute makes AI work dearer for a few years.",
    "Visa crackdown": (
        "Onshore work visas become much harder to get, with tightening starting earlier and reaching a higher level "
        "than in Base."
    ),
    "Visa relaxation": "Onshore work visas become easier to get: tightening ends lower and sooner than in Base.",
    "Downturn": "A temporary downturn cuts the growth of clients' IT budgets for a few years.",
    "Jevons rebound": "Cheaper IT work draws out more demand for applications and data work.",
    "Demand stalls": "Underlying IT demand stops growing after mid-2026.",
    "Demand boom": "Underlying IT demand grows faster after mid-2026.",
    "GCC wave persists": "Clients keep their full appetite for captive centres in India after the wave peaks.",
    "GCC wave fades": "Clients' appetite for captive centres in India fades away after the wave peaks.",
    "Fast AI + OIT price shock": (
        "Fast AI, plus the offshore Indian IT vendor losing a share of its revenue from the price-shock year onward: "
        "a stress test in which every phase9 term acts, the loops GCC scale learning (R7), capacity exit (C2), client "
        "flight (C4), attrition cost (R10) and skill erosion (R4), and the price floor (C5) and AI-discount ceiling "
        "(C6) rules."
    ),
}
"""One plain sentence per named set, in ``SCENARIOS`` then ``STRESS_SCENARIOS`` order; the values are in the table."""

PERCENT: Final = frozenset(
    {
        "WorkShare_{employer}",
        "Margin_{vendor}",
        "EffortShare_revenue_weighted",
        "Unemp_{region}",
        "A_mean",
        "AC_mean",
    }
)
"""The outputs in ``model_docs.csv`` units "fraction" that are shares or rates: the guide shows them in percent
(Addendum A, Part 3)."""

DIM_ROWS: Final[Mapping[str, tuple[str, tuple[str, ...]]]] = {
    "region": ("`Region`", REGIONS),
    "employer": ("`Employer`", EMPLOYERS),
    "vendor": ("Vendor (subset of Employer)", VENDORS),
}
"""A dimension of an output in the guide: its row in the specification's dimension table, whose values are listed in
the model's order (``aisim.dims``)."""


# ---- reading --------------------------------------------------------------------------------------------------------


def named_sets() -> dict[str, Mapping[str, float]]:
    """Every named set the API takes: ``SCENARIOS``, then ``STRESS_SCENARIOS``."""
    return {**SCENARIOS, **STRESS_SCENARIOS}


def lever_rows(root: Path) -> list[dict[str, str]]:
    """The inventory's levers, in inventory order: the rows whose ``lever`` begins with "yes"."""
    return [r for r in MD.read_csv(root / INVENTORY) if r["lever"].startswith("yes")]


def dim_labels(root: Path) -> dict[str, dict[str, str]]:
    """Per dimension of ``DIM_ROWS``, each value's label from the specification's dimension table, without its
    parenthesis (``GCC (consumer-owned captive centre in India)`` is ``GCC``)."""
    lines = (root / SPEC).read_text(encoding="utf-8").split("\n")
    out: dict[str, dict[str, str]] = {}
    for dim, (row, values) in DIM_ROWS.items():
        found = [ln for ln in lines if ln.startswith(f"| {row} | ")]
        if len(found) != 1:
            raise ValueError(f"{SPEC.as_posix()}: expected one dimension row {row!r}, found {len(found)}")
        cell = found[0].split("|")[2]
        labels = [re.sub(r"\s*\([^)]*\)", "", x).strip() for x in cell.split(",")]
        if len(labels) != len(values):
            raise ValueError(f"{SPEC.as_posix()}: row {row!r} has {len(labels)} values, the model {len(values)}")
        out[dim] = dict(zip(values, labels, strict=True))
    return out


def output_rows(root: Path) -> list[dict[str, str]]:
    return MD.read_csv(root / OUTPUTS_CSV)


def members(name: str, catalogue: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    """The catalogue keys of an output name (a template such as ``Margin_{vendor}``, or a plain key), in catalogue
    order."""
    return [r for r in catalogue if MD.cat_template(r) == name]


# ---- formatting -----------------------------------------------------------------------------------------------------


def exact(v: float) -> str:
    """A value as short as it reads back exactly (``2027.0`` is ``2027``), for the scenarios' values."""
    s = f"{v:.6g}"
    return s if float(s) == v else repr(v)


def six(v: float) -> str:
    """A lever value to 6 significant figures: exact for the hand-set values, short for the fitted ones."""
    return f"{v:.6g}"


def _three(v: float) -> str:
    if v == 0:
        return "0"
    r = float(f"{v:.3g}")
    a = abs(r)
    if a >= 1e9:
        return f"{r / 1e9:#.3g}".rstrip(".") + " bn"
    if a >= 1e6:
        return f"{r / 1e6:#.3g}".rstrip(".") + " million"
    if a >= 1000:
        return f"{r:,.0f}"
    return f"{r:#.3g}".rstrip(".")


def three(v: float) -> str:
    """A measured value to 3 significant figures. Raises if the value lies within 1e-9 (relative) of a rounding
    boundary, where a platform's last-digit difference could change the page."""
    s = _three(v)
    if _three(v * (1 + 1e-9)) != s or _three(v * (1 - 1e-9)) != s:
        raise ValueError(f"{v!r} lies on a 3-significant-figure rounding boundary")
    return s


def percent(v: float) -> str:
    """A share or rate in percent to 3 significant figures (0.0553 is 5.53%), with ``three``'s boundary guard."""
    return three(v * 100) + "%"


def _cell(s: str) -> str:
    if "|" in s or "\n" in s:
        raise ValueError(f"a table cell holds '|' or a newline: {s!r}")
    return s


def _table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    out = ["| " + " | ".join(_cell(h) for h in head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    out += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return [*out, ""]


# ---- measuring ------------------------------------------------------------------------------------------------------


def measure(keys: Sequence[str]) -> dict[str, tuple[float, float]]:
    """Each key's ``phase9`` Base value in 2024 and 2040, recorded at every step through the public API."""
    res = run_experiment(Experiment(model=MODEL), outputs=list(keys), record_every=1 / 16)
    years = np.asarray(res.years)
    idx = [int(np.flatnonzero(years == y)[0]) for y in YEARS]
    out: dict[str, tuple[float, float]] = {}
    for k in keys:
        s = np.asarray(res.single(k))
        out[k] = (float(s[idx[0]]), float(s[idx[1]]))
    return out


def rejected_at(year: float) -> list[str]:
    """The named sets that validation rejects with ``perturb_from=year`` on ``phase9``."""
    base = Params.baseline(MODEL)
    out = []
    for name, ov in named_sets().items():
        try:
            validate(base.with_overrides(**ov), overrides=ov, perturb_from=year, model=MODEL)
        except ValidationError:
            out.append(name)
    return out


# ---- sections -------------------------------------------------------------------------------------------------------

EXAMPLE: Final = """\
from aisim import Experiment, run_experiment


def main() -> None:
    exp = Experiment(model="phase9", scenario="Fast AI", perturb_from=2026.5)
    res = run_experiment(exp, outputs=["HeadTotal", "Head_GCC"])
    print(res.bands("Head_GCC", years=(2026, 2040)))


if __name__ == "__main__":
    main()
"""


def how_to_ask() -> list[str]:
    rejected = rejected_at(Y)
    names = ", ".join(rejected) if rejected else "none"
    return [
        f"## {SECTIONS[0]}",
        "",
        "A question is a model, a scenario or lever change, and the outputs to read.",
        "",
        f"- **Choose a model.** `{MODEL}` is the default and fits every question. For a question that depends on how "
        f"fast AI adoption spreads after 2026, run `{ALT}` alongside it on the same draws and report both: the "
        "2024-2026 data identify the early adoption path but not its later speed (README, Models).",
        "- **Choose a scenario or a lever change.** Name a scenario from section 2, set levers from section 3 as "
        "`overrides`, or sample them for a Monte Carlo. With `perturb_from=Y` the calibrated baseline runs unchanged "
        f"until Y and the changes act from Y; validation rejects a change that cannot act from Y (at Y = {Y:g}: "
        f"{names}).",
        "- **Choose outputs.** Name them from `aisim.catalogue()`; section 4 lists the main ones.",
        "- **Read the answer as a projection.** The model gives scenario projections, not forecasts. Read every result "
        'as "under these assumptions" (README).',
        "",
        f"This example runs Fast AI on `{MODEL}` from mid-2026 and prints GCC headcount:",
        "",
        "```python",
        *EXAMPLE.rstrip("\n").split("\n"),
        "```",
        "",
    ]


def changes(ov: Mapping[str, float], levers: set[str]) -> str:
    if not ov:
        return "nothing: the calibrated baseline"
    parts = []
    for k, v in ov.items():
        flag = f", {STRESS_FLAG}" if k not in levers and k in STRESS_INPUTS else ""
        parts.append(f"`{k}` {exact(v)}{flag}")
    return "; ".join(parts)


def scenarios_section(levers: set[str]) -> list[str]:
    sets = named_sets()
    if set(SCENARIO_TEXT) != set(sets):
        raise ValueError(f"SCENARIO_TEXT and the named sets differ: {sorted(set(SCENARIO_TEXT) ^ set(sets))}")
    bad = sorted(k for ov in sets.values() for k in ov if k not in levers and k not in STRESS_INPUTS)
    if bad:
        raise ValueError(f"a named set sets a parameter that is not a lever: {bad}")
    rows = [[f"`{n}`", changes(ov, levers), SCENARIO_TEXT[n]] for n, ov in sets.items()]
    return [
        f"## {SECTIONS[1]}",
        "",
        f"The {len(SCENARIOS)} scenarios of `aisim.SCENARIOS` and the {len(STRESS_SCENARIOS)} stress set of "
        "`aisim.STRESS_SCENARIOS`, by the name `Experiment(scenario=...)` and `run_scenarios` take. Each sets the "
        "levers shown, from `src/aisim/scenarios.py`; every other parameter keeps its Base value.",
        "",
        *_table(["Scenario", "What it changes", "What it represents"], rows),
    ]


def _value(row: Mapping[str, str], inv: Mapping[str, Mapping[str, str]]) -> str:
    v, alt = row[f"value_{MODEL}"], row[f"value_{ALT}"]
    if row["dimensions"]:
        return f"per {row['dimensions']}, see inventory.csv"
    if v == "None":
        if row["name"] != "DemandGrowthLate" or alt != "None":
            raise ValueError(f"{row['name']}: no value in the inventory")
        return f"same as `DemandGrowth` ({six(float(inv['DemandGrowth'][f'value_{MODEL}']))})"
    out = six(float(v))
    return out if alt == v else f"{out} ({ALT} {six(float(alt))})"


def _range(name: str) -> str:
    r, ra = tornado_levers(None, MODEL).get(name), tornado_levers(None, ALT).get(name)
    if r is None:
        return "-"
    out = f"{six(r.lo)} to {six(r.hi)}"
    if ra is not None and (ra.lo, ra.hi) != (r.lo, r.hi):
        out += f" ({ALT} {six(ra.lo)} to {six(ra.hi)})"
    return out


def levers_section(root: Path) -> list[str]:
    rows_inv = lever_rows(root)
    params = {r["name"]: r for r in MD.read_csv(root / INVENTORY) if r["kind"] == "parameter"}
    docs = {r["name"]: r for r in MD.read_csv(root / MODEL_DOCS) if r["kind"] == "parameter"}
    sets = named_sets()
    rows = []
    for r in rows_inv:
        name = r["name"]
        moves = "; ".join(f"{s}: {exact(ov[name])}" for s, ov in sets.items() if name in ov) or "-"
        rows.append(
            [
                f"`{name}` {r['label']}",
                docs[name]["description"],
                r["units"],
                _value(r, params),
                moves,
                _range(name),
                AT_Y.get(name, "-"),
            ]
        )
    structural = sum(r["lever"] == "yes (structural)" for r in rows_inv)
    dropped = [(y, sorted(set(tornado_levers(None, MODEL)) - set(tornado_levers(y, MODEL)))) for y in (Y, Y + 0.5)]
    drop_text = "; ".join(f"from {y:g} it drops {', '.join(f'`{n}`' for n in ns)}" for y, ns in dropped)
    stress = []
    for key, fam in STRESS_INPUTS.items():
        p = params[fam]
        vals = {x.split("=")[1] for x in p[f"value_{MODEL}"].split(";")}
        base = f"{six(float(next(iter(vals))))} for every {p['dimensions']}" if len(vals) == 1 else "see inventory.csv"
        users = "; ".join(f"'{s}' sets `{key}` {exact(ov[key])}" for s, ov in STRESS_SCENARIOS.items() if key in ov)
        stress.append(
            f"**Stress-test input (not a lever).** `{fam}` {p['label']} ({p['units']}), per {p['dimensions']}, see "
            f"inventory.csv: {MODEL} Base {base}. `STRESS_SCENARIOS` sets it: {users}."
        )
    return [
        f"## {SECTIONS[2]}",
        "",
        f'The {len(rows)} levers of `docs/model/inventory.csv` (its `lever` column begins with "yes"), '
        f"{len(rows) - structural} scenario and tornado levers and {structural} structural loop strengths of "
        f"`{MODEL}`, in inventory order. Each is a single value; set it in `overrides` or sample it.",
        "",
        *_table(
            ["Lever", "What it is", "Units", "Base value", "Scenarios that move it", RANGE_HEAD, "At year Y"],
            rows,
        ),
        f"- **Base value:** the `{MODEL}` value, with the `{ALT}` value where it differs; fitted values to 6 "
        "significant figures.",
        f"- **{RANGE_HEAD}:** from `aisim.scenarios.tornado_levers(model=...)`, the one source of record for lever "
        "ranges: the 14 tornado ranges and the structural loop strengths' evidence ranges. `run_experiment` samples "
        'only the levers an experiment names, so a Monte Carlo samples these ranges when it passes them. "-": no '
        f"range. The set depends on the perturb year: {drop_text}.",
        "- **At year Y:** what the lever does when it acts from a perturb year Y, as the README records it "
        '("Perturb from year Y"): it "steps" at Y, or it "builds gradually" from its base path. "-": not recorded '
        "in the README or the Q05 analysis.",
        "",
        *stress,
        "",
    ]


def outputs_section(root: Path) -> list[str]:
    docs = {r["name"]: r for r in MD.read_csv(root / MODEL_DOCS) if r["kind"] == "output"}
    catalogue = MD.read_csv(root / CATALOGUE)
    labels = dim_labels(root)
    outs = output_rows(root)
    bad = output_problems(outs, MD.read_csv(root / MODEL_DOCS), catalogue)
    if bad:
        raise ValueError("; ".join(bad))
    keyed = {o["name"]: members(o["name"], catalogue) for o in outs}
    vals = measure([m["key"] for ms in keyed.values() for m in ms])

    for name in PERCENT:
        if docs[name]["units"] != "fraction":
            raise ValueError(f"{name}: shown in percent, but its units are {docs[name]['units']!r}")

    def cell(name: str, i: int) -> str:
        fmt = percent if name in PERCENT else three
        ms = keyed[name]
        if len(ms) == 1 and ms[0]["key"] == name:
            return fmt(vals[name][i])
        parts = []
        for m in ms:
            dim, value = m["dims"].split("=")
            parts.append(f"{labels[dim][value]} {fmt(vals[m['key']][i])}")
        return "; ".join(parts)

    rows = [
        [
            f"`{o['name']}` {docs[o['name']]['label']}",
            "percent" if o["name"] in PERCENT else docs[o["name"]]["units"],
            o["why"],
            cell(o["name"], 0),
            cell(o["name"], 1),
        ]
        for o in outs
    ]
    return [
        f"## {SECTIONS[3]}",
        "",
        f"{len(rows)} outputs from `tools/guide_outputs.csv`, with names, labels and units from "
        "`src/aisim/data/model_docs.csv`. A name with a dimension in braces gives every member, labelled as in the "
        f"specification. Values are {MODEL} Base: one deterministic run, recorded every step, rounded to 3 significant "
        "figures. Shares and rates are in percent. Headcounts are in model units, which are proportions, not "
        "national counts: compare changes and shares, not absolute levels (specification 07, "
        '"Model units are proportions, not national counts"). Work is in BFY, the baseline FTE-year: one '
        "person-year of effort at pre-AI productivity (specification 00). Money is in real USD a year.",
        "",
        *_table(["Output", "Units", "What it tells you", f"{MODEL} Base 2024", f"{MODEL} Base 2040"], rows),
    ]


WHERE_NEXT: Final = (
    (
        "Module pages",
        "the stock-and-flow diagram of each of the eight engine modules, on twelve pages, each with its item list "
        "(`docs/model/diagrams/`).",
    ),
    (
        "Feedback loops",
        "five causal-loop panels with their polarity, and the loop table (`docs/model-reference.md`, "
        "`docs/model/loops.csv`).",
    ),
    (
        "Article diagrams",
        "five small diagrams for readers outside the project, each with its story (`docs/model-reference.md`); "
        "they are not in the PDF.",
    ),
    (
        "Data dictionary",
        "every named item of the model with its description, units and values (`docs/model-reference.md`, "
        "`docs/model/inventory.csv`).",
    ),
)
"""Section 5: one line per place, by title. ``tools/model_pdf.py`` adds the PDF pages by title."""


def where_next() -> list[str]:
    return [f"## {SECTIONS[4]}", "", *(f"- **{t}:** {text}" for t, text in WHERE_NEXT), ""]


def build(root: Path = ROOT) -> str:
    levers = {r["name"] for r in lever_rows(root)}
    lines = [
        "# Model guide",
        "",
        "The menu of questions `ai-it-labour-sim` can answer: the scenarios, the levers and the main outputs. It is "
        "generated by `tools/model_guide.py` from `src/aisim/scenarios.py`, `docs/model/inventory.csv`, "
        "`src/aisim/data/model_docs.csv` and `tools/guide_outputs.csv`; do not edit it by hand.",
        "",
        *how_to_ask(),
        *scenarios_section(levers),
        *levers_section(root),
        *outputs_section(root),
        *where_next(),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


# ---- checks ---------------------------------------------------------------------------------------------------------


def section_table(md: str, title: str) -> list[list[str]]:
    """The body rows of the first table under the heading ``## <title>``, as stripped cells."""
    lines = md.split("\n")
    start = lines.index(f"## {title}")
    rows: list[list[str]] = []
    for ln in lines[start + 1 :]:
        if ln.startswith("## "):
            break
        if ln.startswith("| "):
            rows.append([c.strip() for c in ln.strip().strip("|").split("|")])
        elif rows:
            break
    return [r for r in rows[1:] if not all(set(c) <= {"-"} for c in r)]


CODE: Final = re.compile(r"`([^`]+)`")


def lever_problems(md: str, levers: Sequence[str]) -> list[str]:
    """Every lever exactly once in the lever table, and nothing else."""
    names = [m.group(1) for r in section_table(md, SECTIONS[2]) if (m := CODE.match(r[0]))]
    bad = [f"lever {n}: {names.count(n)} rows" for n in levers if names.count(n) != 1]
    return bad + [f"not a lever: {n}" for n in sorted(set(names) - set(levers))]


def scenario_problems(md: str, sets: Mapping[str, Mapping[str, float]], levers: set[str]) -> list[str]:
    """Every named set once, with exactly its parameters and values; a parameter that is not a lever only as the
    named stress-test input, flagged."""
    rows = {CODE.sub(r"\1", r[0]): r[1] for r in section_table(md, SECTIONS[1])}
    bad = [f"scenario {n}: missing" for n in sets if n not in rows]
    bad += [f"not a scenario: {n}" for n in rows if n not in sets]
    for n, ov in sets.items():
        if n not in rows:
            continue
        cell = rows[n]
        got = dict(re.findall(r"`([^`]+)` (-?[0-9][0-9.e+-]*)", cell))
        if set(got) != set(ov):
            bad.append(f"scenario {n}: parameters {sorted(got)} against {sorted(ov)}")
        bad += [f"scenario {n}: {k} {got[k]} against {v!r}" for k, v in ov.items() if k in got and float(got[k]) != v]
        for k in ov:
            if k in levers:
                continue
            if k not in STRESS_INPUTS:
                bad.append(f"scenario {n}: {k} is not a lever")
            elif f"`{k}` {got.get(k)}, {STRESS_FLAG}" not in cell:
                bad.append(f"scenario {n}: {k} is not flagged as a stress-test input")
    return bad


def output_problems(
    rows: Sequence[Mapping[str, str]], docs: Sequence[Mapping[str, str]], catalogue: Sequence[Mapping[str, str]]
) -> list[str]:
    """Every row names an output of ``model_docs.csv`` that the catalogue records, with a known status."""
    outputs = {r["name"] for r in docs if r["kind"] == "output"}
    bad = []
    for r in rows:
        if r["name"] not in outputs:
            bad.append(f"{r['name']}: not an output in model_docs.csv")
        elif not members(r["name"], catalogue):
            bad.append(f"{r['name']}: no catalogue key")
        if r["status"] not in OUTPUT_STATUSES:
            bad.append(f"{r['name']}: status {r['status']!r}")
    return bad


def stale(root: Path = ROOT, out_root: Path | None = None) -> bool:
    """Whether the guide under ``out_root`` (default ``root``) differs from what ``build(root)`` writes."""
    path = (root if out_root is None else out_root) / OUT
    return not path.exists() or path.read_bytes() != build(root).encode("utf-8")


def write(root: Path = ROOT, out_root: Path | None = None) -> Path:
    out = (root if out_root is None else out_root) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        f.write(build(root))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="regenerate docs/model-guide.md")
    g.add_argument("--check", action="store_true", help="exit 1 if docs/model-guide.md is stale")
    a = ap.parse_args(argv)
    if a.write:
        print("wrote", write().relative_to(ROOT).as_posix())
        return 0
    if stale():
        print(f"{OUT.as_posix()}: stale; rebuild with: uv run --frozen python tools/model_guide.py --write")
        return 1
    print("model guide: up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
