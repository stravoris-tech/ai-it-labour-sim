"""Reports: one self-contained HTML page (no outside resources, unique ids across charts) and markdown plus PNGs."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aisim import Experiment, ExperimentResult, Uniform, charts, run_experiment
from aisim.experiment import ScenarioResult, drivers, run_scenarios
from aisim.report import Report, inline_svg, settings_rows, to_markdown_table

DASHES = (chr(0x2014), chr(0x2013))


@pytest.fixture(scope="module")
def mc() -> ExperimentResult:
    exp = Experiment(sample={"g": Uniform(0.06, 0.15), "JuniorCut": Uniform(0.3, 0.8)}, n=10, seed=8)
    return run_experiment(exp, outputs=["Mix_OIT_FP", "Mix_OIT_TM", "HeadTotal"])


@pytest.fixture(scope="module")
def scen() -> ScenarioResult:
    exp = Experiment(sample={"JevonsEps": Uniform(0.0, 0.5)}, n=5, seed=9)
    return run_scenarios(exp, [None, "Fast AI"], outputs=["Mix_OIT_FP"])


def build(mc: ExperimentResult, scen: ScenarioResult) -> Report:
    report = Report("Contract mix & drivers")
    report.add_text("The model shows a <shift>.\n\n- first point\n- second point")
    # Two charts of the same keys: their gids and matplotlib's counter ids would collide without the prefixes.
    report.add_chart(charts.bands(mc, ["Mix_OIT_FP", "Mix_OIT_TM"]), "Book mix, OIT")
    report.add_chart(charts.bands(mc, ["Mix_OIT_FP", "Mix_OIT_TM"], window=(2024, 2032)), "Book mix to 2032")
    report.add_chart(charts.scenarios(scen, "Mix_OIT_FP"), "Scenarios")  # small multiples: gids repeat per panel
    table = pd.DataFrame({"scenario": ["Fast AI & co", "Slow|AI"], "value": [0.123456, np.nan], "n": [3, 4]})
    report.add_table(table, "Values", "{:.3f}")
    report.add_table(drivers(mc, ["HeadTotal"], 2032), "Drivers")
    report.add_settings(mc)
    report.add_settings(scen)
    return report


def test_html_is_self_contained(mc: ExperimentResult, scen: ScenarioResult, tmp_path: Path) -> None:
    page = build(mc, scen).to_html(tmp_path / "report.html").read_text(encoding="utf-8")
    assert page.startswith("<!doctype html>") and page.count("<svg") == 3
    assert not re.findall(r'\b(?:src|href)\s*=\s*"(?!#)', page)
    assert not re.findall(r"url\((?!#)", page) and "<!DOCTYPE svg" not in page and "<?xml" not in page
    ids = re.findall(r'\bid="([^"]*)"', page)
    dupes = [i for i, c in Counter(ids).items() if c > 1]
    assert ids and not dupes
    assert all(re.fullmatch(r"[A-Za-z0-9_.:-]+", i) for i in ids)
    refs = set(re.findall(r'href="#([^"]*)"', page)) | set(re.findall(r"url\(#([^)]*)\)", page))
    assert refs <= set(ids)


def test_html_content(mc: ExperimentResult, scen: ScenarioResult, tmp_path: Path) -> None:
    page = build(mc, scen).to_html(tmp_path / "report.html").read_text(encoding="utf-8")
    assert "<title>Contract mix &amp; drivers</title>" in page and "&lt;shift&gt;" in page
    assert "<li>first point</li>" in page
    for cell in ("0.123", "n/a", "Fast AI &amp; co", "Slow|AI", "Table 1. Values", "Figure 3. Scenarios"):
        assert cell in page, cell
    assert "git_commit" in page and str(mc.meta["git_commit"]) in page
    assert "NPY_DISABLE_CPU_FEATURES" in page and "matplotlib" in page and "Baseline, Fast AI" in page
    assert not any(d in page for d in DASHES)


def test_markdown_output(mc: ExperimentResult, scen: ScenarioResult, tmp_path: Path) -> None:
    md_path = build(mc, scen).to_markdown(tmp_path / "md")
    md = md_path.read_text(encoding="utf-8")
    pngs = sorted(p.name for p in (tmp_path / "md").glob("*.png"))
    assert pngs == ["chart-01.png", "chart-02.png", "chart-03.png"]
    assert all((tmp_path / "md" / p).stat().st_size > 1000 and f"]({p})" in md for p in pngs)
    assert "| Fast AI & co | 0.123 | 3 |" in md and r"| Slow\|AI | n/a | 4 |" in md
    assert "| git_commit |" in md
    assert not any(d in md for d in DASHES)


def test_markdown_table() -> None:
    df = pd.DataFrame({"a": [1.0, float("nan")], "b|c": ["x", None]})
    assert to_markdown_table(df, "{:.1f}") == "| a | b\\|c |\n| --- | --- |\n| 1.0 | x |\n| n/a | n/a |"


def test_settings_rows(mc: ExperimentResult, scen: ScenarioResult) -> None:
    rows = dict(settings_rows(mc))
    assert rows["seed"] == "8" and rows["runs"] == "10" and rows["invalid runs (n_invalid)"] == "0"
    assert rows["scenario"] == "Baseline" and rows["git_commit"] == str(mc.meta["git_commit"])
    rows = dict(settings_rows(scen.meta))
    assert rows["scenarios"] == "Baseline, Fast AI" and rows["runs"] == "5 per scenario x 2 = 10"


def test_inline_svg_prefixes_ids() -> None:
    svg = '<?xml version="1.0"?>\n<!DOCTYPE svg>\n<svg><metadata>m</metadata><g id="a b"><use xlink:href="#a b"/>'
    svg += '<path clip-path="url(#p1)"/></g></svg>'
    out = inline_svg(svg, "c1-")
    assert out == '<svg><g id="c1-a_b"><use xlink:href="#c1-a_b"/><path clip-path="url(#c1-p1)"/></g></svg>'
