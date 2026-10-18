"""The feedback loops of phase 9 (slice 12): neutral when off, each loop alone, all together, and their calibrations.

- **Off.** With every strength 0 the loops change nothing: the prototype parity and goldens (their 37 families) and
  the batch parity cover today's results; here the six loop families and ten loop extras are pinned, and the shape
  parameters are shown inert at strength 0 on the 27 parity cases in both engines.
- **Each loop alone, at its base value** (on ``phase8``): scalar-batch parity, a positive control, the 2024 row equal
  to off, and a restart at 2026.5 bit-exact against an uninterrupted run, in both engines. A loop is run under a stress
  in which its base value acts: in Base, C2 and C4 (relative viability stays above 0.8 for every vendor) and C5 and
  C6 (the floor and the ceiling do not bind) never act on ``phase8`` (recon 12b E1).
- **All loops on, as ``phase9``**: parity, the restart, integrity (T1 in Base; T2 and no negative stocks in Base and
  ``EXTREME``), and T1 with every strength at its high value.
- **Calibrations** (recon 12b C3, D): Atos's signings, no single-vendor collapse, and R10's margin cost.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest

import aisim.scalar.loops
from aisim import Params, RunResult, load_initial_state, run
from aisim.batch.engine import run_batch
from aisim.batch.params import BatchParams
from aisim.batch.record import EXTRA_KEYS
from aisim.batch.state import STATE_AXES, BatchState, pack
from aisim.dims import TYPES, VENDORS
from aisim.experiment.metadata import domains
from aisim.experiment.validate import ValidationError, validate
from aisim.params import EXTENSION_DEFAULTS, LEGACY_EXTENSIONS
from aisim.scenarios import EXTREME, STRUCTURAL_LEVERS, TORNADO, tornado_levers
from aisim.state import LOOP_FAMILIES, State, baseline_data
from tests.helpers import annual, people
from tests.test_batch_parity import ALL_CASES, compare_run, run_cases

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""Scalar-batch parity needs numpy's kernels to match libm (``tests/conftest.py``)."""

ROOT = Path(__file__).resolve().parent.parent
DT = 1 / 16
Y = 2026.5
K = round((Y - 2024) / DT)
MIN_STOCK = -1e-12

DOCUMENTED_FAMILIES = ("WS0", "VMarg", "ECost", "Attr0", "Dur0", "C4Hab")
"""The six loop state families, as ``aisim.state.LOOP_FAMILIES`` and ``docs/model-changes-phase9.md`` list them."""

DOCUMENTED_EXTRAS = (
    *(f"Vrel_{v}" for v in VENDORS),
    *(f"ClientFlight_{v}" for v in VENDORS),
    "GCCScaleTerm",
    *(f"VoluntaryAttrition_{v}" for v in VENDORS),
)
"""The ten loop extras of slice 12, after the 96 earlier extras."""

STRENGTHS = ("kR7", "R6e", "kViab", "PriceFloor", "AIDiscCeil", "R10rc", "R4a", "R4aIN")
SHAPES = {"R7Lcap": 0.5, "R6Theta": 0.9, "R6Cap": 0.15, "R6MargTime": 1.5, "C4FadeTime": 3.0, "C4Cap": 2.0}
"""Every shape parameter moved off its default (``MinSeekTime`` too, below): inert while the strengths are 0."""

BASE_VALUES = {
    "kR7": 0.4, "R7Lcap": 1.0, "R6Theta": 0.8, "R6e": 0.005, "R6Cap": 0.08, "R6MargTime": 0.75, "kViab": 5.8562,
    "C4FadeTime": 2.0, "C4Cap": 0.0, "PriceFloor": 1.0, "AIDiscCeil": 0.3, "R10rc": 0.1816, "R4a": 0.1, "R4aIN": 0.1,
    "MinSeekTime": 0.25,
}  # fmt: skip
"""Decision 2's base values, which ``phase9`` sets."""

OIT_SHOCK_2026 = {"PriceShock_OIT": 0.2, "PriceShockYear": 2026.0}
LOOPS: dict[str, tuple[dict[str, float], dict[str, float]]] = {
    "R7": ({"kR7": 0.4}, {}),
    "C2": ({"R6e": 0.005}, OIT_SHOCK_2026),
    "C4": ({"kViab": 5.8562}, OIT_SHOCK_2026),
    "C5": ({"PriceFloor": 1.0}, dict(EXTREME)),
    "C6": ({"AIDiscCeil": 0.3}, dict(EXTREME)),
    "R10": ({"R10rc": 0.1816}, {}),
    "R4": ({"R4a": 0.1, "R4aIN": 0.1}, {}),
}
"""Each loop at its base value, and the stress in which that value acts: C2 and C4 from 2026.19 (before Y) under an
OIT price shock from 2026; C5 from 2025.5 and C6 from 2026.81 under ``EXTREME``; R7, R10 and R4 in Base."""


def scalar_run(params: Params, record_every: float = DT) -> RunResult:
    return run(params, record_every=record_every, extras=True)


# ---- off: the families, the extras, inert shapes ---------------------------------------------------------------------


def test_loop_families_are_the_documented_six() -> None:
    assert LOOP_FAMILIES == DOCUMENTED_FAMILIES
    st = load_initial_state()
    assert list(st)[-6:] == list(DOCUMENTED_FAMILIES) and len(st) == 43
    assert list(st)[:37] == list(baseline_data("phase7")["init"])
    assert list(STATE_AXES) == list(st)
    assert st["WS0"] == -1.0 and st["VMarg"] == st["Viab"] and st["C4Hab"] == dict.fromkeys(VENDORS, 0.0)
    assert all(v == -1.0 for v in st["ECost"].values()) and all(v == -1.0 for v in st["Attr0"].values())
    assert all(v == -1.0 for row in st["Dur0"].values() for v in row.values())
    result = run(Params.baseline("phase7"), record_every=1.0)
    assert list(result.final_state) == list(st)
    assert all(result.final_state["Attr0"][v] > 0 for v in VENDORS) and result.final_state["WS0"] > 0


def test_extras_are_the_earlier_96_and_the_documented_ten() -> None:
    assert EXTRA_KEYS[96:] == DOCUMENTED_EXTRAS and len(EXTRA_KEYS) == 106
    assert not set(EXTRA_KEYS[:96]) & set(DOCUMENTED_EXTRAS)
    assert EXTRA_KEYS[95] == "CapE_BQ"


@pytest.mark.parametrize("model", ["phase7", "phase8", "phase9"])
def test_loop_extras_are_neutral_in_2024(model: str) -> None:
    """Every model records the loop extras; on the 2024 row they are at their neutral values."""
    first = run(Params.baseline(model), record_every=1.0, extras=True).extras[0]
    for v in VENDORS:
        assert first[f"Vrel_{v}"] == 1.0 and first[f"ClientFlight_{v}"] == 0.0
        assert first[f"VoluntaryAttrition_{v}"] == 1.0
    assert first["GCCScaleTerm"] == 0.0


def test_no_new_parameter_is_a_2024_level() -> None:
    """Every loop term is neutral at 2024, so no new parameter is flagged ``level_2024``: each can vary from any Y."""
    new = [k for k in EXTENSION_DEFAULTS if k not in LEGACY_EXTENSIONS]
    assert len(new) == 15
    rows = domains().set_index("name")
    assert not rows.loc[new, "level_2024"].any()
    assert rows.loc[new, "read"].all()


def test_shapes_are_inert_at_strength_zero_on_the_27_cases() -> None:
    """With every strength 0, moving every shape parameter changes no row, no existing family and no mins, in either
    engine, on the 27 parity cases."""
    shapes = {**SHAPES, "MinSeekTime": 0.5}
    assert set(shapes) == set(EXTENSION_DEFAULTS) - set(LEGACY_EXTENSIONS) - set(STRENGTHS)
    cases = list(ALL_CASES.values())
    assert len(cases) == 27
    moved = [dataclasses.replace(c, overrides={**c.overrides, **shapes}) for c in cases]
    existing = [k for k in STATE_AXES if k not in LOOP_FAMILIES]
    for a, b in zip(cases, moved, strict=True):
        ra, rb = a.scalar(), b.scalar()
        assert ra.rows == rb.rows and ra.mins == rb.mins, a.name
        fa, fb = cast(dict[str, Any], ra.final_state), cast(dict[str, Any], rb.final_state)
        assert all(fa[k] == fb[k] for k in existing), a.name
    for dt in (1 / 16, 1 / 32):
        group = [i for i, c in enumerate(cases) if c.dt == dt]
        ba = run_cases([cases[i] for i in group], record_every=1.0)
        bb = run_cases([moved[i] for i in group], record_every=1.0)
        assert all(np.array_equal(ba.series[k], bb.series[k]) for k in ba.series)
        assert all(np.array_equal(ba.mins[k], bb.mins[k]) for k in ba.mins)
        sa, sb = ba.final_state.arrays(), bb.final_state.arrays()
        assert all(np.array_equal(sa[k], sb[k]) for k in existing)


# ---- each loop alone, at its base value ------------------------------------------------------------------------------


@pytest.mark.parametrize("loop", list(LOOPS))
def test_loop_alone_parity_control_2024_row_and_restart(loop: str) -> None:
    over, stress = LOOPS[loop]
    off_p = Params.baseline("phase8").with_overrides(**stress)
    on_p = off_p.with_overrides(**over)
    on, off = scalar_run(on_p), scalar_run(off_p)
    # the 2024 row (and its extras) equals off; the run differs after 2024 (the positive control)
    assert on.rows[0] == off.rows[0] and on.extras[0] == off.extras[0]
    assert on.rows != off.rows
    # scalar-batch parity: rows, final state (all 43 families), mins, and the extras
    b = run_batch(BatchParams.stack([on_p]), BatchState.baseline(1), record_every=DT, outputs=EXTRA_KEYS)
    cmp = compare_run(
        run_batch(BatchParams.stack([on_p]), BatchState.baseline(1), record_every=DT), 0, run(on_p, record_every=DT)
    )
    assert cmp.miss is None, cmp.miss
    for k in EXTRA_KEYS:
        assert np.allclose(b.series[k][0], [e[k] for e in on.extras], rtol=1e-12, atol=1e-12), k
    # a restart at 2026.5 is bit-exact, scalar and batch
    assert_restart_is_exact(on_p)


def assert_restart_is_exact(params: Params) -> None:
    whole = run(params, record_every=DT)
    head = run(params, stop=Y - 2024, record_every=DT)
    tail = run(params, head.final_state, start_step=K, tilt=False, record_every=DT)
    assert tail.rows == whole.rows[K:]
    assert tail.final_state == whole.final_state
    bp = BatchParams.stack([params])
    bwhole = run_batch(bp, BatchState.baseline(1), record_every=DT)
    bhead = run_batch(bp, BatchState.baseline(1), stop=Y - 2024, record_every=DT)
    btail = run_batch(bp, bhead.final_state, start_step=K, tilt=False, record_every=DT)
    assert all(np.array_equal(btail.series[k], bwhole.series[k][:, K:]) for k in bwhole.series)
    sa, sb = btail.final_state.arrays(), bwhole.final_state.arrays()
    assert all(np.array_equal(sa[k], sb[k]) for k in sa)
    for k in LOOP_FAMILIES:  # the loop families carried through BatchState at Y
        assert np.array_equal(bhead.final_state.arrays()[k], pack([head.final_state]).arrays()[k]), k


def test_restart_control_detects_a_lost_reference() -> None:
    """Positive control for the restart check: restarting from a state whose 2024 references were reset to their
    sentinels (as a per-run reference outside the state would be) is not exact."""
    params = Params.baseline("phase9")
    whole = run(params, record_every=DT)
    head = run(params, stop=Y - 2024, record_every=DT)
    lost = head.final_state
    lost["WS0"] = -1.0
    lost["Attr0"] = dict.fromkeys(VENDORS, -1.0)
    tail = run(params, lost, start_step=K, tilt=False, record_every=DT)
    assert tail.rows != whole.rows[K:]


# ---- all loops on: phase9 --------------------------------------------------------------------------------------------


def test_phase9_sets_every_loop_at_its_base_value() -> None:
    p = Params.baseline("phase9").scalars
    assert {k: p[k] for k in BASE_VALUES} == BASE_VALUES


@pytest.mark.parametrize("scenario", ["Base", "EXTREME"])
def test_phase9_parity_and_restart(scenario: str) -> None:
    params = Params.baseline("phase9").with_overrides(**(dict(EXTREME) if scenario == "EXTREME" else {}))
    cmp = compare_run(
        run_batch(BatchParams.stack([params]), BatchState.baseline(1), record_every=DT), 0, run(params, record_every=DT)
    )
    assert cmp.miss is None, cmp.miss
    assert_restart_is_exact(params)


def t1(params: Params) -> float:
    ann = annual(run(params, ai_on=False, record_every=1.0).rows)
    h0 = ann[2024]["HeadTotal"]
    return max(abs(r["HeadTotal"] / h0 / r["G"] - 1) for r in ann.values())


def test_phase9_integrity() -> None:
    """T1 (the AI-off growth path) in Base only: it is defined on the AI-off growth path, which ``EXTREME``'s
    overrides leave. T2 (people conservation) and no negative stocks in Base and ``EXTREME``."""
    params = Params.baseline("phase9")
    assert t1(params) < 0.012
    for over in ({}, dict(EXTREME)):
        result = run(params.with_overrides(**over), record_every=1 / 16)
        inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in result.rows[:-1])
        total = people(result.final_state)
        assert abs(total - people(load_initial_state()) - inflow) <= 1e-9 * total
    for over in ({}, dict(EXTREME)):
        mins = run(params.with_overrides(**over), record_every=1.0).mins
        worst = min(mins, key=lambda k: mins[k])
        assert mins[worst] >= MIN_STOCK, f"{worst} = {mins[worst]!r}"


def test_t1_with_every_strength_at_its_high_value() -> None:
    """The structural levers' highs and ``R4aIN`` at 0.25, on ``phase9`` without a refit: T1 still passes."""
    high = {name: hi for name, _, hi, _ in STRUCTURAL_LEVERS["phase9"]}
    high["R4aIN"] = 0.25
    assert set(STRENGTHS) <= set(high)
    assert t1(Params.baseline("phase9").with_overrides(**high)) < 0.012


# ---- R7: the in-step work share is the recorded one ------------------------------------------------------------------


def test_r7_work_share_is_the_recorded_work_share(monkeypatch: pytest.MonkeyPatch) -> None:
    """The economy-wide share R7 reads in the step equals the recorded ``WorkShare_GCC`` bit for bit at every step."""
    seen: list[float] = []
    real = aisim.scalar.loops.r7

    def spy(pr: Mapping[str, float], st: State, w: float) -> float:
        seen.append(w)
        return real(pr, st, w)

    monkeypatch.setattr(aisim.scalar.loops, "r7", spy)
    rows = run(Params.baseline("phase8").with_overrides(kR7=0.4), record_every=DT).rows
    assert len(seen) == len(rows) == 257
    assert seen == [r["WorkShare_GCC"] for r in rows]


# ---- calibrations as regression tests --------------------------------------------------------------------------------


def oit_signings_and_vrel(params: Params) -> tuple[np.ndarray, np.ndarray]:
    extras = run(params, record_every=DT, extras=True).extras
    sign = np.array([sum(e[f"SignVol_OIT_{k}"] for k in TYPES) for e in extras])
    return sign, np.array([e["Vrel_OIT"] for e in extras])


def test_atos_calibration() -> None:
    """C4 alone on phase8 under ``PriceShock_OIT`` 0.2 from 2028: OIT's signings at its relative-viability trough (of
    the run without the term) are -21.5% +/- 1 point against the term off, at kViab's base (Atos's book-to-bill 93% to
    73%; recon 12b C3)."""
    off_p = Params.baseline("phase8").with_overrides(PriceShock_OIT=0.2)
    s_on, _ = oit_signings_and_vrel(off_p.with_overrides(kViab=5.8562))
    s_off, v_off = oit_signings_and_vrel(off_p)
    j = int(v_off[:-1].argmin())
    assert 0.24 < v_off[j] < 0.26
    assert abs(100 * (s_on[j] / s_off[j] - 1) - (-21.5)) <= 1.0


@pytest.mark.parametrize("vendor", ["BQ", "OIT"])
def test_no_single_vendor_collapse(vendor: str) -> None:
    """``phase9`` under a 0.2 price shock on one vendor from 2028: the vendor's revenue against the same run with C2
    and C4 off is in [0.48, 1.0] 2 and 5 years after distress onset (the first step the reference's relative viability
    is below R6Theta), and above 0.48 in 2040 (recon 12b C2, distress-attributable envelope)."""
    p = Params.baseline("phase9").with_overrides(**{f"PriceShock_{vendor}": 0.2})
    on = run(p, record_every=DT)
    ref = run(p.with_overrides(R6e=0.0, kViab=0.0), record_every=DT, extras=True)
    years = np.array([r["year"] for r in on.rows])
    ratio = np.array([a[f"Revenue_{vendor}"] / b[f"Revenue_{vendor}"] for a, b in zip(on.rows, ref.rows, strict=True)])
    vrel = np.array([e[f"Vrel_{vendor}"] for e in ref.extras])
    onset = float(years[np.argmax(vrel < p.scalars["R6Theta"])])
    assert 2028.0 <= onset < 2029.0
    for after in (2, 5):
        r = ratio[int(np.argmin(np.abs(years - (onset + after))))]
        assert 0.48 <= r <= 1.0, (after, r)
    assert ratio[-1] > 0.48


def test_r10_margin_cost_at_a_voluntary_attrition_ratio_of_1_8() -> None:
    """At ``R10rc``'s base, OIT's margin falls 150 +/- 25 bps at a voluntary-attrition ratio of 1.8 (recon 12b D):
    phase 1 is phase8 to 2025; phase 2 multiplies the quit, leave-IT and switch rates by 1.7875; 2025-2026 averages
    against the same run with ``R10rc`` 0."""
    p = Params.baseline("phase8")
    head = run(p, stop=1.0, record_every=0.25)
    rates = [f"QuitRate_{lv}" for lv in "JMS"] + [f"LeaveITRate_{lv}" for lv in "JMS"] + ["SwitchRate"]
    stress = {k: Params.float_of(p.scalars, k) * 1.7875 for k in rates}

    def margin_and_ratio(rc: float) -> tuple[float, float]:
        r = run(p.with_overrides(**stress, R10rc=rc), head.final_state, start_step=16, tilt=False, record_every=DT,
                extras=True)  # fmt: skip
        sel = [i for i, row in enumerate(r.rows) if 2025.0 <= row["year"] < 2026.0]
        assert len(sel) == 16
        return (float(np.mean([r.rows[i]["Margin_OIT"] for i in sel])),
                float(np.mean([r.extras[i]["VoluntaryAttrition_OIT"] for i in sel])))  # fmt: skip

    m_off, ratio = margin_and_ratio(0.0)
    m_on, _ = margin_and_ratio(0.1816)
    assert abs(ratio - 1.8) < 0.01
    assert abs((m_off - m_on) * 1e4 - 150) <= 25


# ---- validation and levers -------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("name", "value"), [("kR7", 1.2), ("R6Theta", 0.0), ("R6e", -0.001), ("C4FadeTime", 0.0)])
def test_out_of_domain_values_are_rejected(name: str, value: float) -> None:
    base = Params.baseline("phase9")
    with pytest.raises(ValidationError) as info:
        validate(base.with_overrides(**{name: value}), overrides={name: value}, model="phase9")
    assert any(v.target == name for v in info.value.violations)


def test_time_constants_against_dt() -> None:
    base = Params.baseline("phase9")
    for name in ("R6MargTime", "C4FadeTime", "MinSeekTime"):
        with pytest.raises(ValidationError) as info:
            validate(base.with_overrides(**{name: 0.01}), overrides={name: 0.01}, model="phase9")
        assert [(v.family, v.target) for v in info.value.violations] == [("dt", name)]


def test_phase9_levers() -> None:
    """``tornado_levers(model="phase9")``: phase 9's 14 tornado levers (13 from 2026.5, ``Verif`` out), then the eight
    structural levers with decision 2's ranges, every one of them valid at 2026.5. The other models are unchanged."""
    table = STRUCTURAL_LEVERS["phase9"]
    assert [(n, lo, hi) for n, lo, hi, _ in table] == [
        ("kR7", 0.15, 0.75), ("R6Theta", 0.65, 0.92), ("R6e", 0.002, 0.012), ("kViab", 0.0, 10.6511),
        ("PriceFloor", 0.85, 1.08), ("AIDiscCeil", 0.20, 0.45), ("R10rc", 0.0748, 0.3223), ("R4a", 0.0, 0.25),
    ]  # fmt: skip
    assert list(STRUCTURAL_LEVERS) == ["phase9"]
    full = tornado_levers(model="phase9")
    assert list(full) == [*(t[0] for t in TORNADO), *(t[0] for t in table)]
    from_y = tornado_levers(Y, model="phase9")
    assert list(from_y) == [*(t[0] for t in TORNADO if t[0] != "Verif"), *(t[0] for t in table)]
    assert len(from_y) == 13 + 8
    for name, lo, hi, _ in table:
        assert (from_y[name].lo, from_y[name].hi) == (lo, hi)
    for model in ("phase7", "phase8", "phase8_highadoption"):
        assert list(tornado_levers(model=model)) == [t[0] for t in TORNADO]


def test_phase9_spec_names_every_loop_parameter() -> None:
    spec = json.loads((ROOT / "tools" / "models" / "phase9" / "spec.json").read_text(encoding="utf-8"))
    assert {k: spec["set"][k] for k in BASE_VALUES} == BASE_VALUES
    data = baseline_data("phase9")
    assert list(data["params"])[-18:] == list(EXTENSION_DEFAULTS)
