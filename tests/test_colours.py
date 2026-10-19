"""The colour map beyond eight series (slice 7): 10 colours with yellow the last hue, line styles from series 11 on,
and one (colour, style) pair per scenario label. Chart checks are data-level, by artist gid."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from matplotlib.artist import Artist
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.lines import Line2D

from aisim import SCENARIOS, STRESS_SCENARIOS, Experiment, ExperimentResult, charts, run_experiment
from aisim.charts import SCENARIO_COLOURS, SCENARIO_STYLES, key_colours, key_styles, scenario_colour, scenario_style
from aisim.charts.colours import BLACK, DASHED, DOTTED, INDIGO, LINE_STYLES, PALETTE, SOLID, WINE, YELLOW
from aisim.experiment import ScenarioResult, run_scenarios

LABELS = ["Baseline", *SCENARIOS, *STRESS_SCENARIOS]
"""The 16 scenario labels: the baseline (None), the 14 scenarios, ``Base`` among them, and the stress set."""

CONTRAST_PAIRS = [
    ("Fast AI", "Slow AI"),
    ("Strict regulation", "Light regulation"),
    ("Compute shock", "Downturn"),
    ("Visa crackdown", "Visa relaxation"),
    ("GCC wave persists", "GCC wave fades"),
    ("Demand boom", "Demand stalls"),
]


def find(fig: Figure, gid: str) -> Any:
    hits = fig.findobj(lambda a: isinstance(a, Artist) and a.get_gid() == gid)
    assert len(hits) == 1, (gid, len(hits))
    return hits[0]


def test_palette_has_ten_colours_with_yellow_after_every_hue_but_black() -> None:
    assert len(PALETTE) == len(set(PALETTE)) == 10
    assert PALETTE[-1] == BLACK
    hues = [c for c in PALETTE if c != BLACK]
    assert hues[-1] == YELLOW
    assert all(PALETTE.index(YELLOW) > PALETTE.index(c) for c in hues if c != YELLOW)
    assert PALETTE.index(WINE) < PALETTE.index(YELLOW) and PALETTE.index(INDIGO) < PALETTE.index(YELLOW)
    assert LINE_STYLES == (SOLID, DASHED, DOTTED)


@pytest.mark.parametrize("n", range(1, 31))
def test_key_colours_and_styles_unique_up_to_30_series(n: int) -> None:
    names = [f"series {i}" for i in range(n)]
    colours, styles = key_colours(names), key_styles(names)
    pairs = [(colours[k], styles[k]) for k in names]
    assert len(set(pairs)) == n
    assert all(styles[k] == SOLID for k in names[:10])
    assert all(styles[k] == DASHED for k in names[10:20])
    assert all(styles[k] == DOTTED for k in names[20:30])


def test_dimension_colours_stay_solid() -> None:
    names = ["Mix_OIT_FP", "Mix_OIT_TM", "Mix_OIT_MS"]
    assert key_styles(names) == dict.fromkeys(names, SOLID)


def test_every_scenario_label_has_a_unique_pair() -> None:
    assert set(SCENARIO_COLOURS) == set(SCENARIO_STYLES) == set(LABELS)
    pairs = [(SCENARIO_COLOURS[k], SCENARIO_STYLES[k]) for k in LABELS]
    assert len(LABELS) == 16 and len(set(pairs)) == 16
    assert (SCENARIO_COLOURS["Base"], SCENARIO_STYLES["Base"]) == (BLACK, DASHED)
    assert all(SCENARIO_STYLES[k] == SOLID for k in ("Baseline", "Fast AI", "Slow AI"))
    assert SCENARIO_COLOURS["Baseline"] == BLACK


@pytest.mark.parametrize(("a", "b"), CONTRAST_PAIRS)
def test_contrast_pairs_differ_in_colour(a: str, b: str) -> None:
    assert SCENARIO_COLOURS[a] != SCENARIO_COLOURS[b]


def test_unknown_scenario_label_takes_the_position() -> None:
    assert (scenario_colour("x", 12), scenario_style("x", 12)) == (PALETTE[2], DASHED)


# ---- the style reaches every line ------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def one() -> ExperimentResult:
    return run_experiment(Experiment(), outputs=["HeadTotal"])


def test_lines_and_bands_carry_the_style(one: ExperimentResult) -> None:
    names = [f"s{i}" for i in range(22)]
    base = one.series["HeadTotal"][0]
    fig = charts.lines({k: base * (1 + i / 100) for i, k in enumerate(names)}, years=one.years)
    colours, styles = key_colours(names), key_styles(names)
    for k in names:
        line = find(fig, f"line:{k}")
        assert (to_hex(line.get_color()), line.get_linestyle()) == (colours[k].lower(), styles[k]), k
    arrays = {k: one.series["HeadTotal"] * (1 + i / 100) for i, k in enumerate(names[:12])}
    fig = charts.bands(one, arrays)
    for k in names[:12]:
        median = find(fig, f"median:{k}")
        assert (to_hex(median.get_color()), median.get_linestyle()) == (colours[k].lower(), styles[k]), k


def test_scenario_overlay_lines_and_legend_carry_the_style() -> None:
    labels = [None, "GCC wave persists", "GCC wave fades", "Slow AI"]
    scen: ScenarioResult = run_scenarios(Experiment(), labels, outputs=["HeadTotal"])
    fig = charts.scenarios(scen, "HeadTotal", layout="overlay")
    legend = next(a for a in fig.findobj(Legend))
    by_label = {t.get_text(): h for t, h in zip(legend.get_texts(), legend.legend_handles, strict=False)}
    for i, s in enumerate(scen):
        label = ScenarioResult.label(s)
        line = find(fig, f"median:HeadTotal@{label}")
        expect = (scenario_colour(label, i).lower(), scenario_style(label, i))
        assert (to_hex(line.get_color()), line.get_linestyle()) == expect, label
        handle = by_label[label]
        assert isinstance(handle, Line2D)
        assert (to_hex(handle.get_color()), handle.get_linestyle()) == expect, label
    assert np.array_equal(
        find(fig, "median:HeadTotal@Baseline").get_xydata()[:, 1], scen[None].bands("HeadTotal")[0.5].to_numpy()
    )
