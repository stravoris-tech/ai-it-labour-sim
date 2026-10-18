"""``STRESS_SCENARIOS`` (slice 13): named stress sets outside ``SCENARIOS``, accepted by name like a scenario.

- The one entry, "Fast AI + OIT price shock" (Q05 B3), validates on ``phase8``, ``phase9`` and
  ``phase9_highadoption``, with no perturb year and with ``perturb_from`` 2026.5.
- ``run_experiment`` and ``run_scenarios`` accept its name; a lever both sampled and set by it is an error, as for a
  scenario; ``SCENARIOS`` is unchanged.

The regression test that every ``phase9`` loop acts in it is ``tests/test_loops.py``
``test_every_phase9_loop_acts_in_the_stress_set``.
"""

from __future__ import annotations

import numpy as np
import pytest

from aisim import SCENARIOS, STRESS_SCENARIOS, Experiment, Params, Uniform, run_experiment, run_scenarios
from aisim.experiment.validate import validate
from aisim.scenarios import ALL_SCENARIOS

NAME = "Fast AI + OIT price shock"
KEYS = ["HeadTotal", "Revenue_OIT"]


def test_the_entry_and_the_views() -> None:
    assert dict(STRESS_SCENARIOS) == {NAME: {"g": 0.20, "VerifDecline": 0.10, "PriceShock_OIT": 0.2}}
    assert len(SCENARIOS) == 14 and NAME not in SCENARIOS
    assert list(ALL_SCENARIOS) == [*SCENARIOS, *STRESS_SCENARIOS]


@pytest.mark.parametrize("model", ["phase8", "phase9", "phase9_highadoption"])
@pytest.mark.parametrize("perturb_from", [None, 2026.5], ids=["2024", "2026.5"])
def test_the_entry_validates(model: str, perturb_from: float | None) -> None:
    over = dict(STRESS_SCENARIOS[NAME])
    validate(Params.baseline(model).with_overrides(**over), overrides=over, perturb_from=perturb_from, model=model)


def test_run_experiment_and_run_scenarios_accept_the_name() -> None:
    """By name it is the same run as its overrides; in ``run_scenarios`` its block equals the solo run; a lever it
    sets cannot also be sampled in ``run_experiment``."""
    by_name = run_experiment(Experiment(model="phase9", scenario=NAME), outputs=KEYS, workers=1)
    by_over = run_experiment(
        Experiment(model="phase9", overrides=dict(STRESS_SCENARIOS[NAME])), outputs=KEYS, workers=1
    )
    for k in KEYS:
        assert np.array_equal(by_name.series[k], by_over.series[k])
    exp = Experiment(model="phase9", sample={"JevonsEps": Uniform(0.0, 0.5)}, n=4, method="lhs", seed=5)
    both = run_scenarios(exp, [None, NAME], outputs=KEYS, workers=1)
    solo = run_experiment(
        Experiment(model="phase9", scenario=NAME, samples=both[None].samples), outputs=KEYS, workers=1
    )
    for k in KEYS:
        assert np.array_equal(both[NAME].series[k], solo.series[k])
    with pytest.raises(ValueError, match="both fixed and sampled"):
        run_experiment(Experiment(model="phase9", scenario=NAME, sample={"g": Uniform(0.06, 0.15)}, n=2, seed=1),
                       outputs=KEYS, workers=1)  # fmt: skip
