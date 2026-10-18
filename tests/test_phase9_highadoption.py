"""``phase9_highadoption`` (slice 13): ``phase9`` refitted with ``p`` fixed at Phase 7's 0.044, the like-for-like
adoption-speed alternative to ``phase9`` (as ``phase8_highadoption`` is to ``phase8``).

- **The model.** Its spec is ``phase9``'s plus ``p``, and it sets every loop at its base value.
- **All loops on:** scalar-batch parity and the restart at 2026.5 in Base and ``EXTREME``; integrity (T1 in Base;
  T2 and no negative stocks in Base and ``EXTREME``; T1 with every strength at its high value); the loop extras
  neutral in 2024.
- **The levers** are ``phase9``'s.
- **Like-for-like.** In Base in 2040, its adoption effect against ``phase9`` is within 1 point of
  ``phase8_highadoption``'s against ``phase8`` on the four headlines (recon 13 C3).

The build checks (the shipped file is ``build_model.py``'s output and reproduces its fit's loss) are in
``tests/test_phase8.py`` (``BUILT_MODELS``); the goldens in ``tests/test_golden_phase9_highadoption.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aisim import Params, load_initial_state, run
from aisim.batch.engine import run_batch
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.scenarios import EXTREME, STRUCTURAL_LEVERS, TORNADO, tornado_levers
from aisim.state import baseline_data
from tests.helpers import people
from tests.test_batch_parity import compare_run
from tests.test_loops import (
    BASE_VALUES,
    DOCUMENTED_EXTRAS,
    DOCUMENTED_EXTRAS_13,
    DT,
    MIN_STOCK,
    STRENGTHS,
    Y,
    assert_restart_is_exact,
    t1,
)

pytestmark = pytest.mark.usefixtures("numpy_kernels_match_libm")
"""Scalar-batch parity needs numpy's kernels to match libm (``tests/conftest.py``)."""

ROOT = Path(__file__).resolve().parent.parent
MODEL = "phase9_highadoption"
HEADLINES = ("HeadTotal", "VendorHead", "Head_GCC", "RevenueTot")


def spec(model: str) -> dict[str, Any]:
    """``Any``: parsed JSON."""
    out: dict[str, Any] = json.loads((ROOT / "tools" / "models" / model / "spec.json").read_text(encoding="utf-8"))
    return out


def test_spec_is_phase9_plus_p() -> None:
    own, base = spec(MODEL), spec("phase9")
    assert own["model"] == MODEL and own["fit"] == f"tools/models/{MODEL}/fit.json"
    assert own["set"] == {**base["set"], "p": 0.044}


def test_sets_every_loop_at_its_base_value() -> None:
    p = Params.baseline(MODEL).scalars
    assert {k: p[k] for k in BASE_VALUES} == BASE_VALUES
    assert p["p"] == 0.044
    assert list(baseline_data(MODEL)["params"])[-18:] == list(baseline_data("phase9")["params"])[-18:]


@pytest.mark.parametrize("scenario", ["Base", "EXTREME"])
def test_parity_and_restart(scenario: str) -> None:
    params = Params.baseline(MODEL).with_overrides(**(dict(EXTREME) if scenario == "EXTREME" else {}))
    cmp = compare_run(
        run_batch(BatchParams.stack([params]), BatchState.baseline(1), record_every=DT), 0, run(params, record_every=DT)
    )
    assert cmp.miss is None, cmp.miss
    assert_restart_is_exact(params)


def test_integrity() -> None:
    """T1 (the AI-off growth path) in Base only; T2 (people conservation) and no negative stocks in Base and
    ``EXTREME``; T1 with every strength at its high value (the structural levers' highs and ``R4aIN`` 0.25)."""
    params = Params.baseline(MODEL)
    assert t1(params) < 0.012
    for over in ({}, dict(EXTREME)):
        result = run(params.with_overrides(**over), record_every=1 / 16)
        inflow = sum((x["Grad_total"] + x["Ext_total"]) / 16 for x in result.rows[:-1])
        total = people(result.final_state)
        assert abs(total - people(load_initial_state()) - inflow) <= 1e-9 * total
        mins = run(params.with_overrides(**over), record_every=1.0).mins
        worst = min(mins, key=lambda k: mins[k])
        assert mins[worst] >= MIN_STOCK, f"{worst} = {mins[worst]!r}"
    high = {name: hi for name, _, hi, _ in STRUCTURAL_LEVERS[MODEL]}
    high["R4aIN"] = 0.25
    assert set(STRENGTHS) <= set(high)
    assert t1(params.with_overrides(**high)) < 0.012


def test_loop_extras_are_neutral_in_2024() -> None:
    """The ten loop extras of slice 12 and the 24 binding extras of slice 13 are at their neutral values in 2024."""
    first = run(Params.baseline(MODEL), record_every=1.0, extras=True).extras[0]
    neutral = {k: (1.0 if k.startswith(("Vrel_", "VoluntaryAttrition_", "SkillErosionMult_")) else 0.0)
               for k in (*DOCUMENTED_EXTRAS, *DOCUMENTED_EXTRAS_13)}  # fmt: skip
    assert {k: first[k] for k in neutral} == neutral


def test_levers_are_phase9s() -> None:
    """The same structural rows as ``phase9``; the tornado ranges of ``Verif`` and ``JuniorCut`` are relative to this
    model's own values (x0.7/x1.3 and x0.5/x1.5), every other range is the same."""
    assert STRUCTURAL_LEVERS[MODEL] == STRUCTURAL_LEVERS["phase9"]
    base = Params.baseline(MODEL).scalars
    verif, junior_cut = Params.float_of(base, "Verif"), Params.float_of(base, "JuniorCut")
    for perturb_from in (None, Y):
        mine, theirs = tornado_levers(perturb_from, model=MODEL), tornado_levers(perturb_from, model="phase9")
        assert list(mine) == list(theirs)
        assert len(mine) == (14 if perturb_from is None else 13) + 8
        for name in mine:
            if name == "Verif":
                assert (mine[name].lo, mine[name].hi) == (verif * 0.7, verif * 1.3)
            elif name == "JuniorCut":
                assert (mine[name].lo, mine[name].hi) == (junior_cut * 0.5, junior_cut * 1.5)
            else:
                assert (mine[name].lo, mine[name].hi) == (theirs[name].lo, theirs[name].hi), name
    assert [t[0] for t in TORNADO] == list(tornado_levers(model=MODEL))[:14]


def headlines_2040(model: str) -> dict[str, float]:
    row = run(Params.baseline(model), record_every=1.0).rows[-1]
    assert row["year"] == 2040.0
    return {k: row[k] for k in HEADLINES}


def test_like_for_like_adoption_effect() -> None:
    """In Base in 2040, the adoption effect of this model against ``phase9`` is within 1 percentage point of
    ``phase8_highadoption``'s against ``phase8`` on HeadTotal, VendorHead, Head_GCC and RevenueTot (decision 4; recon
    13 C3: the gaps are 0.02, 0.29, 0.07 and 0.26 points)."""
    h = {m: headlines_2040(m) for m in ("phase8", "phase8_highadoption", "phase9", MODEL)}
    for k in HEADLINES:
        e8 = 100 * (h["phase8_highadoption"][k] / h["phase8"][k] - 1)
        e9 = 100 * (h[MODEL][k] / h["phase9"][k] - 1)
        assert abs(e9 - e8) <= 1.0, (k, e8, e9)
        assert (e8 > 0) == (e9 > 0), k
