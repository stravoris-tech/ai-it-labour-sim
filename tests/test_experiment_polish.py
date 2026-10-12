"""Slice 05 API polish: scenario and sampling conflicts, run_scenarios on common random numbers, auto chunking,
keys() by dimension, array bands, JSON meta, 2-D tables, drivers, shift-share and save/load."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from aisim import SCENARIOS, Choice, Experiment, ExperimentResult, Params, Uniform, run_experiment
from aisim.experiment import ScenarioResult, auto_chunk_size, dims, drivers, keys, run_scenarios, shift_share
from aisim.experiment.runner import design
from aisim.scenarios import TORNADO
from aisim.state import baseline_data
from tests.test_experiment import assert_identical

RANGES = {name: (lo, hi) for name, lo, hi, _ in TORNADO}
MC_KEYS = ["HeadTotal", "Mix_OIT_FP", "EffortShare_revenue_weighted"]


@pytest.fixture(scope="module")
def mc() -> ExperimentResult:
    """60 LHS runs with a tied lever (Choice), recording a derived output that pulls in its dependencies."""
    exp = Experiment(
        sample={"g": Uniform(0.06, 0.15), "JuniorCut": Uniform(0.3, 0.8), "PriceHorizon": Choice([4.0, 6.0, 8.0])},
        n=60,
        method="lhs",
        seed=11,
    )
    return run_experiment(exp, outputs=MC_KEYS)


# ---- 1. a scenario plus a sampled lever it sets ----------------------------------------------------------------------


def overlapping() -> list[tuple[str, str]]:
    return [(s, sorted(set(p) & set(RANGES))[0]) for s, p in SCENARIOS.items() if set(p) & set(RANGES)]


def test_nine_scenarios_overlap_the_tornado_levers() -> None:
    assert len(overlapping()) == 9


@pytest.mark.parametrize(("scenario", "lever"), overlapping())
def test_scenario_and_sampled_lever_conflict(scenario: str, lever: str) -> None:
    lo, hi = RANGES[lever]
    sampled = Experiment(scenario=scenario, sample={lever: Uniform(lo, hi)}, n=4, seed=1)
    with pytest.raises(ValueError, match=f"both fixed and sampled: \\['{lever}'.*{scenario}"):
        run_experiment(sampled, outputs=["HeadTotal"])
    explicit = Experiment(scenario=scenario, samples=pd.DataFrame({lever: [lo, hi]}))
    with pytest.raises(ValueError, match=f"both fixed and sampled: \\['{lever}'.*{scenario}"):
        run_experiment(explicit, outputs=["HeadTotal"])


def test_scenario_with_other_lever_runs() -> None:
    res = run_experiment(
        Experiment(scenario="Fast AI", sample={"JevonsEps": Uniform(0.0, 0.5)}, n=2, seed=1), outputs=["HeadTotal"]
    )
    assert res.n == 2 and res.n_invalid == 0


# ---- 2. run_scenarios ------------------------------------------------------------------------------------------------

SCEN = [None, "Fast AI", "Demand stalls", "Compute shock"]
SCEN_EXP = Experiment(
    sample={"g": Uniform(0.06, 0.15), "JevonsEps": Uniform(0.0, 0.5), "TMBrake": Uniform(0.2, 0.6)},
    n=50,
    method="lhs",
    seed=7,
)


@pytest.fixture(scope="module")
def scen() -> ScenarioResult:
    return run_scenarios(SCEN_EXP, SCEN, outputs=MC_KEYS, workers=1)


def test_blocks_equal_solo_runs(scen: ScenarioResult) -> None:
    for s in SCEN:
        block = scen[s]
        solo = run_experiment(
            Experiment(scenario=s, samples=block.samples.drop(columns=scen.pinned[s])), outputs=MC_KEYS, workers=1
        )
        assert list(block.series) == list(solo.series)
        for k in solo.series:
            assert np.array_equal(block.series[k], solo.series[k]), (s, k)
        assert np.array_equal(block.valid, solo.valid) and np.array_equal(block.years, solo.years)


def test_common_random_numbers_and_pinning(scen: ScenarioResult) -> None:
    drawn = design(SCEN_EXP)
    assert scen.pinned == {None: [], "Fast AI": ["g"], "Demand stalls": [], "Compute shock": []}
    for s in SCEN:
        block = scen[s].samples
        assert list(block.columns) == list(drawn.columns) and block.index.name == "run"
        for col in drawn.columns:
            if col in scen.pinned[s]:
                assert (block[col] == SCENARIOS[str(s)][col]).all()
            else:
                pd.testing.assert_series_equal(block[col], drawn[col], check_exact=True)
        assert scen[s].meta["scenario"] == s and scen[s].meta["pinned"] == scen.pinned[s]
    assert scen.scenarios == tuple(SCEN) and len(scen) == 4 and ScenarioResult.label(None) == "Baseline"
    json.dumps(scen.meta)
    for s in SCEN:
        json.dumps(scen[s].meta)


def test_run_scenarios_determinism_across_workers(scen: ScenarioResult) -> None:
    many = run_scenarios(SCEN_EXP, SCEN, outputs=MC_KEYS, workers=4, chunk_size=13)
    assert many.meta["workers"] == 4
    for s in SCEN:
        assert_identical(scen[s], many[s])


def test_run_scenarios_override_clash() -> None:
    exp = Experiment(overrides={"g": 0.1}, sample={"JevonsEps": Uniform(0.0, 0.5)}, n=2, seed=1)
    with pytest.raises(ValueError, match=r"\['g'\].*\['Slow AI', 'Fast AI'\]"):
        run_scenarios(exp, ["Slow AI", "Fast AI"], outputs=["HeadTotal"])
    # A single run_experiment keeps the layers: the override replaces the scenario's value.
    run_experiment(Experiment(scenario="Fast AI", overrides={"g": 0.1}), outputs=["HeadTotal"])


def test_run_scenarios_with_a_separate_override() -> None:
    exp = Experiment(overrides={"PriceHorizon": 6.0}, sample={"JevonsEps": Uniform(0.0, 0.5)}, n=3, seed=2)
    res = run_scenarios(exp, [None, "Fast AI"], outputs=["HeadTotal"])
    solo = run_experiment(
        Experiment(scenario="Fast AI", overrides={"PriceHorizon": 6.0}, samples=res["Fast AI"].samples),
        outputs=["HeadTotal"],
    )
    assert np.array_equal(res["Fast AI"].series["HeadTotal"], solo.series["HeadTotal"])


def test_run_scenarios_errors() -> None:
    with pytest.raises(ValueError, match=r"leave exp\.scenario"):
        run_scenarios(Experiment(scenario="Fast AI"), [None], outputs=["HeadTotal"])
    with pytest.raises(ValueError, match="repeated"):
        run_scenarios(Experiment(), ["Fast AI", "Fast AI"], outputs=["HeadTotal"])
    with pytest.raises(KeyError, match="unknown scenario"):
        run_scenarios(Experiment(), ["No such"], outputs=["HeadTotal"])
    with pytest.raises(ValueError, match="empty"):
        run_scenarios(Experiment(), [], outputs=["HeadTotal"])


# ---- 3. auto chunking ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("n", "workers", "chunk"),
    [
        (100, 8, 100),
        (200, 8, 200),
        (201, 8, 50),
        (500, 8, 63),
        (1000, 8, 125),
        (5000, 8, 625),
        (20000, 8, 625),
        (100, 12, 100),
        (500, 12, 50),
        (1000, 12, 84),
        (5000, 12, 417),
        (20000, 12, 625),
        (1000, 1, 625),
    ],
)
def test_auto_chunk_rule(n: int, workers: int, chunk: int) -> None:
    assert auto_chunk_size(n, workers) == chunk


def test_auto_chunk_rejects_no_workers() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        auto_chunk_size(10, 0)
    with pytest.raises(ValueError, match="at least 1"):
        run_experiment(Experiment(), outputs=["HeadTotal"], workers=0)


@pytest.mark.parametrize("n", [7, 250, 1000])
def test_auto_chunking_is_bit_identical(n: int) -> None:
    exp = Experiment(sample={"g": Uniform(0.06, 0.15), "SrcCostSens": Uniform(2.0, 4.0)}, n=n, seed=5)
    ref = run_experiment(exp, outputs=["HeadTotal", "Mix_OIT_FP"], workers=1, chunk_size=500)
    for workers in (1, 4):
        auto = run_experiment(exp, outputs=["HeadTotal", "Mix_OIT_FP"], workers=workers)
        assert auto.meta["chunk_size_auto"] and auto.meta["chunk_size"] == auto_chunk_size(n, workers)
        assert auto.meta["workers"] == (1 if n <= 200 else min(workers, -(-n // auto_chunk_size(n, workers))))
        assert_identical(ref, auto)


# ---- 4. keys() by dimension and dims() -------------------------------------------------------------------------------

F1 = {
    "type;vendor": 75,
    "sector": 70,
    "employer;sector": 70,
    "vendor": 66,
    "employer": 40,
    "unit": 32,
    "level;region": 8,
    "worktype": 6,
    "region": 6,
}


def test_dimension_combinations() -> None:
    combos = Counter(";".join(sorted(dims(k))) for k in keys())
    assert combos.pop("") == 33
    assert dict(combos) == F1
    for name in ("employer", "level", "region", "sector", "type", "unit", "vendor", "worktype"):
        with_name = [k for k in keys() if name in dims(k)]
        values = sorted({dims(k)[name] for k in with_name})
        assert sum(len(keys(**{name: v})) for v in values) == len(with_name), name


def test_keys_filter() -> None:
    assert keys(family="contract mix (book)", vendor="OIT") == [f"Mix_OIT_{t}" for t in ("FP", "TM", "MS", "SA", "OB")]
    assert len(keys(vendor="OIT", type="FP")) == 75 // 15
    assert len(keys(sector="FIN")) == (70 + 70) // 7
    assert keys() == list(pd.read_csv(Path("src/aisim/data/catalogue.csv"), dtype=str)["key"])
    assert dims("Mix_OIT_FP") == {"vendor": "OIT", "type": "FP"} and dims("HeadTotal") == {}
    with pytest.raises(KeyError, match="unknown dimension"):
        keys(colour="red")
    with pytest.raises(KeyError, match="unknown output"):
        dims("NoSuchKey")


# ---- 5. bands of arrays and single() ---------------------------------------------------------------------------------


def test_array_bands_equal_key_bands(mc: ExperimentResult) -> None:
    a = mc.series["Mix_OIT_FP"]
    pairs = [
        (mc.bands("Mix_OIT_FP"), mc.bands(a)),
        (mc.bands("Mix_OIT_FP", ratio_to=2024, years=(2024, 2032)), mc.bands(a, ratio_to=2024, years=(2024, 2032))),
        (mc.bands("Mix_OIT_FP", q=(0.25, 0.75), years=(2030, 2040)), mc.bands(a, q=(0.25, 0.75), years=(2030, 2040))),
    ]
    for by_key, by_array in pairs:
        pd.testing.assert_frame_equal(by_key, by_array, check_exact=True)
    with pytest.raises(ValueError, match="runs, years"):
        mc.bands(mc.series["Mix_OIT_FP"][:, :5])


def test_array_bands_drop_invalid_runs() -> None:
    res = run_experiment(
        Experiment(samples=pd.DataFrame({"g": [0.1, 1.5, 0.12]})), outputs=["HeadTotal"], validate=False
    )
    with pytest.warns(UserWarning, match="1 invalid"):
        by_key = res.bands("HeadTotal", ratio_to=2024)
    with pytest.warns(UserWarning, match="1 invalid"):
        by_array = res.bands(res.series["HeadTotal"] * 1.0, ratio_to=2024)
    pd.testing.assert_frame_equal(by_key, by_array, check_exact=True)


def test_single() -> None:
    one = run_experiment(Experiment(), outputs=["HeadTotal"])
    assert one.single("HeadTotal").shape == (17,)
    assert np.array_equal(one.single("HeadTotal"), one.series["HeadTotal"][0])
    two = run_experiment(Experiment(samples=pd.DataFrame({"g": [0.1, 0.12]})), outputs=["HeadTotal"])
    with pytest.raises(ValueError, match="one-run"):
        two.single("HeadTotal")


# ---- 6. JSON-safe meta -----------------------------------------------------------------------------------------------


def test_meta_is_json_serialisable() -> None:
    samples = pd.DataFrame({"g": [0.1, 0.12], "TMBrake": [0.3, 0.5]})
    cases = [
        Experiment(scenario="Fast AI"),
        Experiment(overrides={"g": 0.1, "DemandGrowthLate": None}),
        Experiment(
            sample={"g": Uniform(0.06, 0.15), "JuniorCut": Uniform(0.3, 0.8)},
            correlation={("g", "JuniorCut"): 0.5},
            n=10,
            seed=4,
        ),
        Experiment(samples=samples),
    ]
    metas = [run_experiment(exp, outputs=["HeadTotal"]).meta for exp in cases]
    for meta in metas:
        back = json.loads(json.dumps(meta))
        assert set(back["platform"]) == {"os", "machine", "python"}
        assert "git_commit" in back and "git_dirty" in back and back["n"] >= 1
    assert metas[0]["experiment"]["scenario"] == "Fast AI"
    assert metas[1]["experiment"]["overrides"] == {"g": 0.1, "DemandGrowthLate": None}
    assert metas[2]["experiment"]["sample"]["g"] == {"type": "Uniform", "lo": 0.06, "hi": 0.15}
    assert metas[2]["experiment"]["correlation"] == {"g|JuniorCut": 0.5}
    ref = metas[3]["experiment"]["samples"]
    digest = hashlib.sha256(np.ascontiguousarray(samples.to_numpy(dtype=np.float64)).tobytes()).hexdigest()
    assert ref == {"shape": [2, 2], "columns": ["g", "TMBrake"], "sha256": digest}


# ---- 7. two-dimensional tables ---------------------------------------------------------------------------------------


def test_two_dimensional_tables() -> None:
    p = Params.baseline()
    for name in ("Mix0", "Src0"):
        table = p.table(name)
        assert type(table) is dict and all(type(row) is dict for row in table.values())
        assert table == baseline_data()["tables"][name]
    assert p.table("Mix0")["OIT"]["FP"] == 0.35
    assert p.table("SpeedUp") == dict(p.tables["SpeedUp"])


# ---- 8. drivers ------------------------------------------------------------------------------------------------------


def test_drivers_match_scipy(mc: ExperimentResult) -> None:
    targets = ["HeadTotal", "Mix_OIT_FP", "EffortShare_revenue_weighted"]
    df = drivers(mc, targets, 2032)
    assert list(df.columns) == ["lever", "label", *targets]
    j = int(np.flatnonzero(mc.years == 2032.0)[0])
    x = mc.samples.to_numpy()
    y = np.column_stack([mc.series[t][:, j] for t in targets])
    ref = np.asarray(spearmanr(np.column_stack([x, y])).statistic)[: x.shape[1], x.shape[1] :]
    got = df.set_index("lever").loc[list(mc.samples.columns), targets].to_numpy()
    assert np.max(np.abs(got - ref)) <= 1e-12
    assert list(df[targets[0]].abs()) == sorted(df[targets[0]].abs(), reverse=True)
    labels = {name: label for name, _, _, label in TORNADO}
    assert list(df["label"]) == [labels[name] for name in df["lever"]]


def test_drivers_constant_lever_sorts_last() -> None:
    res = run_experiment(
        Experiment(samples=pd.DataFrame({"TMBrake": [0.3] * 6, "g": np.linspace(0.06, 0.15, 6)})), outputs=["HeadTotal"]
    )
    df = drivers(res, ["HeadTotal"], 2030)
    assert list(df["lever"]) == ["g", "TMBrake"] and np.isnan(df["HeadTotal"].iloc[1])


# ---- 9. shift-share --------------------------------------------------------------------------------------------------


def test_shift_share_parts_sum_to_total(mc: ExperimentResult) -> None:
    s = mc.series
    w = {v: s[f"Revenue_{v}"] / s["RevenueTot"] for v in ("OIT", "GSI", "BQ")}
    e = {v: s[f"EffortShare_{v}"] for v in ("OIT", "GSI", "BQ")}
    parts = shift_share(w, e, 2024, years=mc.years)
    assert set(parts) == {"within", "between", "interaction", "total"}
    assert np.max(np.abs(parts["within"] + parts["between"] + parts["interaction"] - parts["total"])) <= 1e-12
    rw = s["EffortShare_revenue_weighted"]
    assert np.max(np.abs(parts["total"] - (rw - rw[:, :1]))) <= 1e-12
    assert mc.bands(parts["within"], years=(2024, 2040)).shape == (17, 3)


# ---- 10. save and load -----------------------------------------------------------------------------------------------


def test_save_load_round_trip(mc: ExperimentResult, tmp_path: Path) -> None:
    path = mc.save(tmp_path / "mc.npz")
    back = ExperimentResult.load(path)
    assert_identical(mc, back)
    pd.testing.assert_frame_equal(mc.bands("Mix_OIT_FP", ratio_to=2024), back.bands("Mix_OIT_FP", ratio_to=2024))
    sidecar = json.loads((tmp_path / "mc.json").read_text(encoding="utf-8"))
    assert set(sidecar["requested"]) == set(MC_KEYS)
    assert set(sidecar["dependencies"]) == set(mc.series) - set(MC_KEYS)
    assert "RevenueTot" in sidecar["dependencies"] and sidecar["state_dropped"] is False
    assert back.meta["experiment"] == mc.meta["experiment"]


def test_save_refuses_state_unless_dropped(tmp_path: Path) -> None:
    res = run_experiment(Experiment(), outputs=["HeadTotal"], keep_state=True)
    with pytest.raises(ValueError, match="include_state=False"):
        res.save(tmp_path / "s.npz")
    back = ExperimentResult.load(res.save(tmp_path / "s.npz", include_state=False))
    assert back.final_state is None and back.meta["state_dropped"] is True
    assert np.array_equal(back.single("HeadTotal"), res.single("HeadTotal"))
    with pytest.raises(ValueError, match=r"\.npz"):
        res.save(tmp_path / "s.bin", include_state=False)
