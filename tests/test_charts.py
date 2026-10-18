"""Charts: checked at the data level through artist gids (``get_xydata``, band path vertices, bar widths), never by
pixels or image files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest
from matplotlib.artist import Artist
from matplotlib.axes import Axes
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_hex
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.text import Text

from aisim import Experiment, ExperimentResult, Uniform, catalogue, charts, run_experiment
from aisim.charts import DIMENSION_COLOURS, scenario_colour
from aisim.experiment import ScenarioResult, drivers, keys, run_scenarios
from aisim.scenarios import STRUCTURAL_LEVERS, TORNADO

INFERRED = str(catalogue().query("unit_inferred and kind == 'row'")["key"].iloc[0])
BOOK_OIT = keys(family="contract mix (book)", vendor="OIT")
BOOK_GSI = keys(family="contract mix (book)", vendor="GSI")
EFFORT = ["EffortShare_OIT", "EffortShare_GSI", "EffortShare_BQ"]
OUTPUTS = [*BOOK_OIT, *BOOK_GSI, *EFFORT, "HeadTotal", INFERRED]
SAMPLE = {"g": Uniform(0.06, 0.15), "JuniorCut": Uniform(0.3, 0.8)}


@pytest.fixture(scope="module")
def mc() -> ExperimentResult:
    return run_experiment(Experiment(sample=SAMPLE, n=40, method="lhs", seed=3), outputs=OUTPUTS)


@pytest.fixture(scope="module")
def base() -> ExperimentResult:
    return run_experiment(Experiment(), outputs=OUTPUTS)


@pytest.fixture(scope="module")
def scen() -> ScenarioResult:
    exp = Experiment(sample=SAMPLE, n=12, method="lhs", seed=4)
    return run_scenarios(exp, [None, "Slow AI", "Fast AI"], outputs=["Mix_OIT_FP", "Mix_OIT_TM", "HeadTotal"])


def find(where: Figure | Axes, gid: str) -> Any:
    hits = where.findobj(lambda a: isinstance(a, Artist) and a.get_gid() == gid)
    assert len(hits) == 1, (gid, len(hits))
    return hits[0]


def has(where: Figure | Axes, gid: str) -> bool:
    return bool(where.findobj(lambda a: isinstance(a, Artist) and a.get_gid() == gid))


def line_y(where: Figure | Axes, gid: str) -> np.ndarray[Any, Any]:
    line = find(where, gid)
    assert isinstance(line, Line2D)
    return np.asarray(line.get_xydata())


def band_verts(where: Figure | Axes, gid: str) -> np.ndarray[Any, Any]:
    band = find(where, gid)
    assert isinstance(band, PolyCollection)
    return np.asarray(band.get_paths()[0].vertices)


def axes_of(fig: Figure) -> list[Axes]:
    return [ax for ax in fig.axes if ax.get_visible()]


# ---- bands -----------------------------------------------------------------------------------------------------------


def test_bands_plot_the_band_data(mc: ExperimentResult, base: ExperimentResult) -> None:
    fig = charts.bands(mc, BOOK_OIT, baseline=base)
    (ax,) = axes_of(fig)
    for k in BOOK_OIT:
        b = mc.bands(k, years=(2024, 2040))
        xy = line_y(fig, f"median:{k}")
        assert np.array_equal(xy[:, 0], b.index.to_numpy()) and np.array_equal(xy[:, 1], b[0.5].to_numpy())
        verts = band_verts(fig, f"band:{k}")
        assert np.isin(b[0.1].to_numpy(), verts[:, 1]).all() and np.isin(b[0.9].to_numpy(), verts[:, 1]).all()
        bl = find(fig, f"baseline:{k}")
        assert bl.get_linestyle() == "--" and np.array_equal(line_y(fig, f"baseline:{k}")[:, 1], base.single(k))
        assert find(fig, f"label:{k}").get_text() == k
    assert has(fig, "shade:calibration") and ax.get_xlim() == (2024.0, 2040.0)
    assert ax.get_ylabel() == "share"


def test_bands_of_arrays_ratios_and_windows(mc: ExperimentResult, base: ExperimentResult) -> None:
    total = sum(mc.series[k] for k in BOOK_OIT[:2])
    assert isinstance(total, np.ndarray)
    fig = charts.bands(mc, {"FP + TM": total}, baseline=base, window=(2026, 2034), shade=False)
    (ax,) = axes_of(fig)
    b = mc.bands(total, years=(2026, 2034))
    assert np.array_equal(line_y(fig, "median:FP + TM")[:, 1], b[0.5].to_numpy())
    assert not has(fig, "baseline:FP + TM") and not has(fig, "shade:calibration")
    assert ax.get_xlim() == (2026.0, 2034.0) and ax.get_ylabel() == ""
    fig = charts.bands(mc, "HeadTotal", baseline=base, ratio_to=2024, q=(0.25, 0.75), window=(2024, 2032))
    (ax,) = axes_of(fig)
    b = mc.bands("HeadTotal", q=(0.25, 0.5, 0.75), ratio_to=2024, years=(2024, 2032))
    assert np.array_equal(line_y(fig, "median:HeadTotal")[:, 1], b[0.5].to_numpy())
    assert np.isin(b[0.25].to_numpy(), band_verts(fig, "band:HeadTotal")[:, 1]).all()
    ratio = base.series["HeadTotal"][0, :9] / base.series["HeadTotal"][0, 0]
    assert np.array_equal(line_y(fig, "baseline:HeadTotal")[:, 1], ratio)
    assert ax.get_ylabel() == "ratio to 2024" and ax.get_xlim() == (2024.0, 2032.0)


def test_ylabels_come_from_the_catalogue(mc: ExperimentResult) -> None:
    cat = catalogue().set_index("key")
    (ax,) = axes_of(charts.bands(mc, INFERRED))
    assert ax.get_ylabel() == f"{cat.at[INFERRED, 'unit']} (unit inferred)"
    (ax,) = axes_of(charts.bands(mc, "HeadTotal"))
    assert ax.get_ylabel() == cat.at["HeadTotal", "unit"]
    (ax,) = axes_of(charts.bands(mc, "HeadTotal", ylabel="people"))
    assert ax.get_ylabel() == "people"


def test_colours_are_fixed_per_dimension_value(mc: ExperimentResult) -> None:
    oit, gsi = charts.bands(mc, BOOK_OIT), charts.bands(mc, list(reversed(BOOK_GSI)))
    for t in ("FP", "TM", "MS", "SA", "OB"):
        want = DIMENSION_COLOURS["type"][t].lower()
        assert to_hex(find(oit, f"median:Mix_OIT_{t}").get_color()) == want
        assert to_hex(find(gsi, f"median:Mix_GSI_{t}").get_color()) == want
    for order in (EFFORT, list(reversed(EFFORT))):
        fig = charts.bands(mc, order)
        for k in EFFORT:
            want = DIMENSION_COLOURS["vendor"][k.split("_")[1]].lower()
            assert to_hex(find(fig, f"median:{k}").get_color()) == want
    assert DIMENSION_COLOURS["vendor"]["OIT"] == DIMENSION_COLOURS["employer"]["OIT"]


# ---- scenarios -------------------------------------------------------------------------------------------------------


def test_scenarios_small_multiples(scen: ScenarioResult) -> None:
    keys2 = ["Mix_OIT_FP", "Mix_OIT_TM"]
    fig = charts.scenarios(scen, keys2)
    panels = axes_of(fig)
    assert [ax.get_gid() for ax in panels] == ["scenario:Baseline", "scenario:Slow AI", "scenario:Fast AI"]
    for ax, s in zip(panels, scen, strict=True):
        for k in keys2:
            b = scen[s].bands(k, years=(2024, 2040))
            assert np.array_equal(line_y(ax, f"median:{k}")[:, 1], b[0.5].to_numpy())
            assert np.isin(b[0.9].to_numpy(), band_verts(ax, f"band:{k}")[:, 1]).all()
        assert has(ax, "shade:calibration") and ax.get_xlim() == (2024.0, 2040.0)
    assert len({ax.get_ylim() for ax in panels}) == 1


def test_scenarios_overlay(scen: ScenarioResult) -> None:
    fig = charts.scenarios(scen, ["Mix_OIT_FP", "Mix_OIT_TM"], layout="overlay", shade=False, window=(2024, 2032))
    panels = axes_of(fig)
    assert [ax.get_gid() for ax in panels] == ["key:Mix_OIT_FP", "key:Mix_OIT_TM"]
    for ax in panels:
        k = str(ax.get_gid()).split(":", 1)[1]
        for i, s in enumerate(scen):
            label = ScenarioResult.label(s)
            line = find(ax, f"median:{k}@{label}")
            assert np.array_equal(line.get_xydata()[:, 1], scen[s].bands(k, years=(2024, 2032))[0.5].to_numpy())
            assert to_hex(line.get_color()) == scenario_colour(label, i).lower()
        assert not has(ax, "shade:calibration") and ax.get_xlim() == (2024.0, 2032.0)
    assert len({ax.get_ylim() for ax in panels}) == 1
    # Keys in different units keep their own limits.
    mixed = axes_of(charts.scenarios(scen, ["Mix_OIT_FP", "HeadTotal"], layout="overlay"))
    assert mixed[0].get_ylim() != mixed[1].get_ylim() and mixed[1].get_ylabel() == "model-unit persons"


# ---- lines -----------------------------------------------------------------------------------------------------------


def test_lines(base: ExperimentResult) -> None:
    fig = charts.lines(base, keys=EFFORT, window=(2024, 2030))
    (ax,) = axes_of(fig)
    for k in EFFORT:
        xy = line_y(fig, f"line:{k}")
        assert np.array_equal(xy[:, 1], base.single(k)[:7]) and np.array_equal(xy[:, 0], base.years[:7])
    assert ax.get_xlim() == (2024.0, 2030.0) and has(fig, "shade:calibration")
    cat = catalogue().set_index("key")
    units = "; ".join(dict.fromkeys(str(cat.at[k, "unit"]) for k in EFFORT))
    inferred = any(bool(cat.at[k, "unit_inferred"]) for k in EFFORT)
    assert ax.get_ylabel() == units + (" (unit inferred)" if inferred else "")
    (ax,) = axes_of(charts.lines(base, keys=INFERRED))
    assert ax.get_ylabel() == f"{cat.at[INFERRED, 'unit']} (unit inferred)"
    sweep = np.array([0.0, 2.0, 4.0, 8.0])
    fig = charts.lines({"FP share": np.array([0.4, 0.38, 0.35, 0.3])}, x=sweep, xlabel="PriceHorizon (years)")
    (ax,) = axes_of(fig)
    assert np.array_equal(line_y(fig, "line:FP share")[:, 0], sweep) and not has(fig, "shade:calibration")
    assert ax.get_xlabel() == "PriceHorizon (years)"
    with pytest.raises(ValueError, match="years="):
        charts.lines({"a": np.zeros(3)})


# ---- drivers ---------------------------------------------------------------------------------------------------------


def test_drivers_chart(mc: ExperimentResult) -> None:
    df = drivers(mc, ["HeadTotal", "Mix_OIT_FP"], 2032)
    fig = charts.drivers(df)
    assert len(axes_of(fig)) == 2
    for t in ("HeadTotal", "Mix_OIT_FP"):
        for lever, rho in zip(df["lever"], df[t], strict=True):
            bar = find(fig, f"bar:{t}:{lever}")
            assert isinstance(bar, Rectangle) and bar.get_width() == rho
            assert to_hex(bar.get_facecolor()) == (charts.colours.RAISES if rho >= 0 else charts.colours.LOWERS).lower()
    legend = fig.legends[0]
    assert [t.get_text() for t in legend.get_texts()] == ["raises", "lowers"]
    first = axes_of(fig)[0]
    labels = [t.get_text() for t in first.get_yticklabels()]
    assert labels == list(df["label"])


def test_drivers_chart_shows_the_longest_label_unclipped() -> None:
    """Every tornado and ``phase9`` structural label, the longest 62 characters, lies inside the figure."""
    rows = [*TORNADO, *STRUCTURAL_LEVERS["phase9"]]
    assert max(len(label) for *_, label in rows) == 62
    df = pd.DataFrame({"lever": [r[0] for r in rows], "label": [r[3] for r in rows]})
    df["HeadTotal"] = np.linspace(-0.9, 0.9, len(rows))
    fig = charts.drivers(df)
    fig.draw_without_rendering()  # the constrained layout runs, as on save
    ticks = axes_of(fig)[0].get_yticklabels()
    assert [t.get_text() for t in ticks] == list(df["label"])
    for t in ticks:
        box = t.get_window_extent()
        assert fig.bbox.x0 <= box.x0 and box.x1 <= fig.bbox.x1, t.get_text()


# ---- text, saving and the import -------------------------------------------------------------------------------------


def test_no_em_or_en_dashes_in_any_chart(mc: ExperimentResult, base: ExperimentResult, scen: ScenarioResult) -> None:
    figs = [
        charts.bands(mc, BOOK_OIT, baseline=base, title="OIT book mix 2024-2040"),
        charts.scenarios(scen, ["Mix_OIT_FP"], title="Scenarios"),
        charts.scenarios(scen, ["Mix_OIT_FP", "HeadTotal"], layout="overlay"),
        charts.lines(base, keys=EFFORT),
        charts.drivers(drivers(mc, ["HeadTotal"], 2030)),
    ]
    for fig in figs:
        fig.canvas.draw()
        texts = [t.get_text() for t in fig.findobj(Text)]
        assert texts and not [t for t in texts if "\u2014" in t or "\u2013" in t]
        assert "calibration period 2024-2026" in texts or fig is figs[-1]


def test_save_formats_and_stable_svg(mc: ExperimentResult, tmp_path: Path) -> None:
    fig = charts.bands(mc, "HeadTotal")
    for suffix in ("png", "svg", "pdf"):
        assert charts.save(fig, tmp_path / f"c.{suffix}").stat().st_size > 1000
    first = (tmp_path / "c.svg").read_bytes()
    charts.save(fig, tmp_path / "c.svg")
    assert (tmp_path / "c.svg").read_bytes() == first and b"dc:date" not in first
    for suffix in ("png", "pdf"):
        once = (tmp_path / f"c.{suffix}").read_bytes()
        charts.save(fig, tmp_path / f"c.{suffix}")
        assert (tmp_path / f"c.{suffix}").read_bytes() == once, suffix
    with pytest.raises(ValueError, match="png"):
        charts.save(fig, tmp_path / "c.jpg")


def test_importing_charts_does_not_import_matplotlib() -> None:
    code = "import sys, aisim, aisim.charts, aisim.report; sys.exit('matplotlib' in sys.modules)"
    assert subprocess.run([sys.executable, "-c", code], check=False).returncode == 0


def test_missing_matplotlib_names_the_extra(mc: ExperimentResult, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    with pytest.raises(ImportError, match=r"ai-it-labour-sim\[charts\]"):
        charts.bands(mc, "HeadTotal")


# ---- perturb from year Y (slice 6) -----------------------------------------------------------------------------------

PERTURB = 2026.5


@pytest.fixture(scope="module")
def mc_y() -> ExperimentResult:
    exp = Experiment(sample=SAMPLE, n=20, method="lhs", seed=3, perturb_from=PERTURB)
    return run_experiment(exp, outputs=OUTPUTS)


@pytest.fixture(scope="module")
def scen_y() -> ScenarioResult:
    exp = Experiment(sample=SAMPLE, n=6, method="lhs", seed=4, perturb_from=PERTURB)
    return run_scenarios(exp, [None, "Fast AI"], outputs=["Mix_OIT_FP", "HeadTotal"])


def shade_span(where: Figure | Axes) -> tuple[float, float, str]:
    patch = find(where, "shade:calibration")
    assert isinstance(patch, Rectangle)
    return float(patch.get_x()), float(patch.get_x() + patch.get_width()), str(patch.get_label())


def legend_texts(fig: Figure) -> list[str]:
    return [t.get_text() for t in fig.findobj(Text)]


def test_shading_follows_perturb_from(mc: ExperimentResult, mc_y: ExperimentResult) -> None:
    """With ``perturb_from`` the shade spans 2024 to Y, labelled "calibrated baseline until 2026.5"; without it,
    2024-2026 and "calibration period 2024-2026"."""
    label = "calibrated baseline until 2026.5"
    fig = charts.bands(mc_y, "HeadTotal")
    assert shade_span(fig) == (2024.0, PERTURB, label)
    assert label in legend_texts(fig) and "calibration period 2024-2026" not in legend_texts(fig)
    assert shade_span(charts.bands(mc, "HeadTotal")) == (2024.0, 2026.0, "calibration period 2024-2026")
    b = mc_y.bands("HeadTotal", q=(0.1, 0.9))
    assert (b.loc[b.index < PERTURB, 0.9] - b.loc[b.index < PERTURB, 0.1]).eq(0).all()


def test_scenarios_shading_follows_perturb_from(scen_y: ScenarioResult) -> None:
    for layout in ("small_multiples", "overlay"):
        fig = charts.scenarios(scen_y, ["Mix_OIT_FP"], layout=layout)
        for ax in axes_of(fig):
            assert shade_span(ax) == (2024.0, PERTURB, "calibrated baseline until 2026.5")
        assert "calibrated baseline until 2026.5" in legend_texts(fig)


def test_lines_shading_follows_perturb_from(mc_y: ExperimentResult, base: ExperimentResult) -> None:
    """``lines`` of a result reads its meta; a mapping has none and keeps the calibration period."""
    one = run_experiment(Experiment(perturb_from=PERTURB), outputs=OUTPUTS)
    assert shade_span(charts.lines(one, keys="HeadTotal")) == (2024.0, PERTURB, "calibrated baseline until 2026.5")
    assert shade_span(charts.lines(base, keys="HeadTotal"))[2] == "calibration period 2024-2026"
    fig = charts.lines({"x": base.single("HeadTotal")}, years=base.years)
    assert shade_span(fig) == (2024.0, 2026.0, "calibration period 2024-2026")


def test_report_settings_show_perturb_from_and_noise(mc: ExperimentResult) -> None:
    from aisim import Noise
    from aisim.report import settings_rows

    exp = Experiment(n=2, perturb_from=PERTURB, noise={"demand": Noise(0.009), "cap": Noise(0.0)}, noise_seed=7)
    rows = dict(settings_rows(run_experiment(exp, outputs=["HeadTotal"])))
    assert rows["perturb_from"] == "2026.5 (calibrated baseline until then)"
    assert rows["noise"] == "demand: sigma 0.009, tau 1 (noise_seed 7)"
    rows = dict(settings_rows(mc))
    assert rows["perturb_from"] == "none (levers act from 2024)" and rows["noise"] == "off"
