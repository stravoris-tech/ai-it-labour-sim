"""The model guide stays in step with its sources (``tools/model_guide.py``, slice 10d): it regenerates byte for byte,
lists every lever once and every named set with its values, and names only outputs of ``model_docs.csv``. Each
absence check has a positive control on a clean ``tmp_path`` copy."""

from __future__ import annotations

import contextlib
import csv
import io
import re
import shutil
from pathlib import Path

import pytest

from tools import model_diagrams as DG
from tools import model_docs as MD
from tools import model_guide as G
from tools import model_pdf as P

ROOT = Path(__file__).resolve().parent.parent
DASHES = (chr(0x2014), chr(0x2013))


@pytest.fixture(scope="module")
def md() -> str:
    return G.build(ROOT)


@pytest.fixture
def copy(tmp_path: Path, md: str) -> Path:
    """A clean copy of the regenerated guide."""
    p = tmp_path / "model-guide.md"
    with p.open("w", encoding="utf-8", newline="") as f:
        f.write(md)
    return p


def _levers() -> list[str]:
    return [r["name"] for r in G.lever_rows(ROOT)]


def test_the_guide_regenerates_byte_for_byte(tmp_path: Path, md: str) -> None:
    first = G.write(ROOT, tmp_path / "a").read_bytes()
    second = G.write(ROOT, tmp_path / "b").read_bytes()
    assert first == second == md.encode("utf-8") == (ROOT / G.OUT).read_bytes()
    assert b"\r" not in first


def test_the_staleness_check_fails_on_a_planted_edit(tmp_path: Path, md: str) -> None:
    out = tmp_path / G.OUT
    out.parent.mkdir(parents=True)
    out.write_bytes(md.encode("utf-8"))
    assert not G.stale(ROOT, tmp_path)
    out.write_bytes(md.replace("82,700", "82,600", 1).encode("utf-8"))
    assert G.stale(ROOT, tmp_path)


def test_every_lever_appears_exactly_once(md: str) -> None:
    levers = _levers()
    with (ROOT / G.INVENTORY).open(encoding="utf-8", newline="") as f:
        assert len(levers) == sum(r["lever"].startswith("yes") for r in csv.DictReader(f)) == 31
    assert G.lever_problems(md, levers) == []
    assert len(G.section_table(md, G.SECTIONS[2])) == len(levers)


def test_the_lever_check_fails_on_a_planted_missing_or_doubled_lever(copy: Path) -> None:
    clean = copy.read_text(encoding="utf-8")
    levers = _levers()
    assert G.lever_problems(clean, levers) == []
    lines = clean.split("\n")
    row = next(ln for ln in lines if ln.startswith("| `kR7` "))
    missing = "\n".join(ln for ln in lines if ln != row)
    assert G.lever_problems(missing, levers) == ["lever kR7: 0 rows"]
    doubled = clean.replace(row, row + "\n" + row, 1)
    assert G.lever_problems(doubled, levers) == ["lever kR7: 2 rows"]


def test_every_named_set_appears_with_its_values(md: str) -> None:
    sets = G.named_sets()
    assert len(sets) == 15
    assert G.scenario_problems(md, sets, set(_levers())) == []
    assert [r[0].strip("`") for r in G.section_table(md, G.SECTIONS[1])] == list(sets)


def test_the_scenario_check_fails_on_a_planted_wrong_value_or_non_lever(copy: Path) -> None:
    clean = copy.read_text(encoding="utf-8")
    sets = G.named_sets()
    levers = set(_levers())
    assert G.scenario_problems(clean, sets, levers) == []
    wrong = clean.replace(
        "| `Strict regulation` | `RegScenario` 1.5 |", "| `Strict regulation` | `RegScenario` 1.25 |", 1
    )
    assert wrong != clean
    assert G.scenario_problems(wrong, sets, levers) == ["scenario Strict regulation: RegScenario 1.25 against 1.5"]
    # A second parameter that is not a lever: the one named exception does not cover it.
    planted = {**sets, "Strict regulation": {"RegScenario": 1.5, "PriceShock_GSI": 0.1}}
    text = clean.replace("`RegScenario` 1.5 |", "`RegScenario` 1.5; `PriceShock_GSI` 0.1 |", 1)
    assert G.scenario_problems(text, planted, levers) == ["scenario Strict regulation: PriceShock_GSI is not a lever"]
    unflagged = clean.replace(f", {G.STRESS_FLAG}", "", 1)
    assert unflagged != clean
    assert G.scenario_problems(unflagged, sets, levers) == [
        "scenario Fast AI + OIT price shock: PriceShock_OIT is not flagged as a stress-test input"
    ]


def test_every_output_row_is_a_model_docs_output() -> None:
    rows = G.output_rows(ROOT)
    assert 15 <= len(rows) <= 20
    assert G.output_problems(rows, MD.read_csv(ROOT / G.MODEL_DOCS), MD.read_csv(ROOT / G.CATALOGUE)) == []
    assert {r["status"] for r in rows} <= {"drafted", "reviewed"}


def test_the_output_check_fails_on_a_planted_unknown_output(tmp_path: Path) -> None:
    p = tmp_path / "guide_outputs.csv"
    shutil.copyfile(ROOT / G.OUTPUTS_CSV, p)
    docs, catalogue = MD.read_csv(ROOT / G.MODEL_DOCS), MD.read_csv(ROOT / G.CATALOGUE)
    assert G.output_problems(MD.read_csv(p), docs, catalogue) == []
    with p.open("a", encoding="utf-8", newline="") as f:
        csv.writer(f, lineterminator="\n").writerows([["NoSuchOutput", "planted", "drafted"], ["A_mean", "x", "ok"]])
    assert G.output_problems(MD.read_csv(p), docs, catalogue) == [
        "NoSuchOutput: not an output in model_docs.csv",
        "A_mean: status 'ok'",
    ]


def test_the_scenario_sentences_cover_every_named_set() -> None:
    assert list(G.SCENARIO_TEXT) == list(G.named_sets())


def _readme_bullet(text: str, start: str) -> str:
    i = text.index(start)
    return text[i : text.index("\n- ", i)]


def test_the_at_year_y_column_matches_the_readme() -> None:
    """``AT_Y`` is what the README's "Perturb from year Y" bullets record, no more and no less."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    paths = _readme_bullet(text, "- **Paths stay continuous.**")
    gradual, steps = paths.split("Levers whose own effect is immediate still step at Y:")
    code = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)`")
    params = {r["name"] for r in MD.read_csv(ROOT / G.INVENTORY) if r["kind"] == "parameter"}

    def names(s: str) -> set[str]:
        return set(code.findall(s)) & params  # the bullets also name models (`phase9`)

    assert {k for k, v in G.AT_Y.items() if v == "steps"} == names(steps)
    assert {k for k, v in G.AT_Y.items() if v == "builds gradually"} == names(gradual)
    levels = _readme_bullet(text, "- **2024 levels cannot act from Y.**")
    assert [k for k, v in G.AT_Y.items() if v.startswith("cannot act")] == ["Verif"]
    assert "`Verif`" in levels
    assert set(G.AT_Y) <= set(_levers())


def test_the_dimension_labels_come_from_the_specification() -> None:
    assert G.dim_labels(ROOT) == {
        "region": {"IN": "India", "ON": "Onshore"},
        "employer": {
            "IH": "Consumer in-house",
            "GCC": "GCC",
            "OIT": "Offshore Indian IT",
            "GSI": "Global SI",
            "BQ": "Boutique",
        },
        "vendor": {"OIT": "Offshore Indian IT", "GSI": "Global SI", "BQ": "Boutique"},
    }


def test_values_round_to_three_significant_figures() -> None:
    assert [G.three(v) for v in (82654.0, 5.73e9, 0.35, 1.0, 0.0984, 15.4e9, 7.62e6, 0.0)] == [
        "82,700",
        "5.73 bn",
        "0.350",
        "1.00",
        "0.0984",
        "15.4 bn",
        "7.62 million",
        "0",
    ]
    assert [G.percent(v) for v in (0.0553, 0.316, 0.35, 0.0984)] == ["5.53%", "31.6%", "35.0%", "9.84%"]
    with pytest.raises(ValueError):
        G.three(82650.0)  # halfway between 82,600 and 82,700: a last-digit change would flip it


def test_the_guide_has_no_dashes_and_no_build_stamp(copy: Path, md: str) -> None:
    sources = [(ROOT / p).read_text(encoding="utf-8") for p in (G.INVENTORY, G.MODEL_DOCS, G.OUTPUTS_CSV)]
    sources.append((ROOT / "src/aisim/scenarios.py").read_text(encoding="utf-8"))
    assert [d for d in DASHES if d in md] == []
    assert P.stamp_problems(md, sources) == []
    clean = copy.read_text(encoding="utf-8")
    planted_date, planted_hash = "1987-06-05", "0c011e3"
    assert not any(planted_date in s or planted_hash in s for s in sources)
    stamped = clean.replace("# Model guide", f"# Model guide {planted_date} {planted_hash}", 1)
    assert P.stamp_problems(stamped, sources) == [planted_hash, planted_date]
    assert any(d in clean.replace("Model guide", "Model" + DASHES[1] + "guide", 1) for d in DASHES)


def test_the_example_call_runs(md: str) -> None:
    block = md[md.index("```python\n") + len("```python\n") :]
    code = block[: block.index("\n```")]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "model-guide example", "exec"), {"__name__": "__main__"})
    assert "2040" in out.getvalue()


def test_the_where_next_counts_match_the_diagrams() -> None:
    """Section 5's counts, written in words, are the diagram set's: modules, module pages, panels and articles."""
    words = {5: "five", 8: "eight", 12: "twelve"}
    text = dict(G.WHERE_NEXT)
    modules = len(DG.read_sources(ROOT).modules)
    articles = len([v for v in DG.VIEWS if v.startswith("article-")])
    assert (
        f"each of the {words[modules]} engine modules, on {words[len(DG.MODULE_VIEWS)]} pages" in text["Module pages"]
    )
    assert text["Feedback loops"].startswith(f"{words[len(DG.PANEL_VIEWS)]} causal-loop panels")
    assert text["Article diagrams"].startswith(f"{words[articles]} small diagrams")


def test_shares_and_rates_print_in_percent(md: str) -> None:
    """The shares and rates of ``PERCENT`` show every member value in percent, with units "percent"; no other output
    does."""
    rows = G.section_table(md, G.SECTIONS[3])
    names = [G.CODE.match(r[0]) for r in rows]
    assert all(names)
    for m, r in zip(names, rows, strict=True):
        assert m is not None
        parts = [p for cell in r[3:5] for p in cell.split("; ")]
        if m.group(1) in G.PERCENT:
            assert r[1] == "percent" and all(p.endswith("%") for p in parts), m.group(1)
        else:
            assert r[1] != "percent" and not any(p.endswith("%") for p in parts), m.group(1)
    assert sum(m is not None and m.group(1) in G.PERCENT for m in names) == len(G.PERCENT) == 6


# ---- the wide levers (slice 10e) ------------------------------------------------------------------------------------


def test_the_wide_lever_table_matches_the_computation(md: str) -> None:
    """Section 3's "Where the wide levers act" lists every lever with more than ``DG.WIDE`` targets once, with its
    count and its targets by module, from the computation the model map draws (operator ruling, slice 10e)."""
    assert G.wide_lever_problems(md) == []
    assert [w[0] for w in G.wide_levers(ROOT)] == [
        "DemandGrowthLate",
        "g",
        "Verif",
        "VerifDecline",
        "AICostDecline",
        "AIShockEnd",
        "AIShockMult",
        "AIShockStart",
        "R6Theta",
        "aL_max",
    ]


def test_the_wide_lever_check_fails_on_planted_rows(copy: Path) -> None:
    clean = copy.read_text(encoding="utf-8")
    assert G.wide_lever_problems(clean) == []
    assert clean.count("| `g` | 22 |") == 1
    assert G.wide_lever_problems(clean.replace("| `g` | 22 |", "| `g` | 21 |")) == ["wide lever g: count 21 against 22"]
    row = next(ln for ln in clean.split("\n") if ln.startswith("| `R6Theta` |"))
    assert any(
        x.startswith("wide lever R6Theta: targets")
        for x in G.wide_lever_problems(clean.replace(row, row.replace(", `fl.openings`", "")))
    )
    assert G.wide_lever_problems(clean.replace(row + "\n", "")) == ["wide lever R6Theta: no row"]
