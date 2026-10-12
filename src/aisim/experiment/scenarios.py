"""Scenario comparisons on common random numbers: ``run_scenarios`` and ``ScenarioResult``.

``run_scenarios(exp, ["Slow AI", "Fast AI", None])`` draws ``exp``'s samples once and runs every scenario on the same
draws, all in one ``run_experiment`` call (one batch, one pool). ``None`` is the baseline. The differences between the
scenarios' results are then due to the scenarios alone, not to different samples.

- **Pinning.** Within a scenario's block, the scenario's own parameters replace the sampled values of any lever it
  sets: ``ScenarioResult.pinned[s]`` lists those levers. Every block keeps the other sampled levers' values unchanged.
- **Same as a solo run.** Each block is bit-identical to ``run_experiment(Experiment(scenario=s, samples=<the same
  draws without the pinned levers>, overrides=...))``: the scenario's values go into the batch as per-run columns
  instead of fixed values, and runs in a batch never interact.
- **Overrides.** ``exp.overrides`` may not set a parameter that a requested scenario sets. In a single
  ``run_experiment`` an override replaces the scenario's value (the layers), but here it would silently erase the
  difference between the scenarios, so ``run_scenarios`` raises instead.
- **Perturb year and noise.** ``exp.perturb_from`` is one Y for every block. Noise is keyed by the run's index within
  its block, so run i has the same noise in every scenario (common random numbers for the noise too).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal

import numpy as np
import pandas as pd

from aisim.experiment.meta import experiment_dict
from aisim.experiment.results import ExperimentResult
from aisim.experiment.runner import Experiment, check_supports, design, execute, fixed_params
from aisim.scenarios import SCENARIOS

BASELINE_LABEL = "Baseline"
"""The label of the baseline (scenario None) in charts and tables."""


def scenario_label(scenario: str | None) -> str:
    """``"Baseline"`` for None, else the scenario's name."""
    return BASELINE_LABEL if scenario is None else scenario


@dataclass(frozen=True)
class ScenarioResult:
    """The output of ``run_scenarios``: one ``ExperimentResult`` view per scenario, on the same samples.

    - ``scenarios``: the scenario names as requested (None is the baseline).
    - ``result[s]``: scenario ``s``'s runs, an ``ExperimentResult`` whose arrays are views into the one batch; its
      ``samples`` are ``exp``'s sampled levers, with the pinned ones at the scenario's value, and its ``meta`` adds
      ``scenario`` and ``pinned``.
    - ``pinned[s]``: the sampled levers whose values scenario ``s`` replaced (sorted).
    - ``meta``: the batch's meta, with ``experiment`` the sample design, ``scenarios`` and ``pinned``. JSON-safe.
    """

    scenarios: tuple[str | None, ...]
    results: Mapping[str | None, ExperimentResult]
    pinned: Mapping[str | None, list[str]]
    meta: Mapping[str, Any]

    def __getitem__(self, scenario: str | None) -> ExperimentResult:
        try:
            return self.results[scenario]
        except KeyError:
            raise KeyError(f"scenario {scenario!r} was not run; run: {list(self.scenarios)}") from None

    def __iter__(self) -> Iterator[str | None]:
        return iter(self.scenarios)

    def __len__(self) -> int:
        return len(self.scenarios)

    @staticmethod
    def label(scenario: str | None) -> str:
        """``"Baseline"`` for None, else the scenario's name."""
        return scenario_label(scenario)


def run_scenarios(
    exp: Experiment,
    scenarios: Sequence[str | None],
    *,
    outputs: Sequence[str] | Literal["all"],
    record_every: float = 1.0,
    dt: float = 1 / 16,
    stop: float = 16.0,
    workers: int | None = None,
    chunk_size: int | None = None,
    validate: bool = True,
) -> ScenarioResult:
    """Run every scenario in ``scenarios`` on the same draws of ``exp``, in one ``run_experiment`` call.

    ``exp`` gives the sample design (``sample`` with ``n``, ``method``, ``seed`` and ``correlation``, or explicit
    ``samples``), plus ``overrides``, ``tables`` and ``ai_on`` for every scenario; its ``scenario`` must be None. The
    keyword arguments are those of ``run_experiment`` (no ``keep_state``).

    Unlike a single ``run_experiment``, where an override replaces the scenario's value, an override of a parameter
    that any requested scenario sets raises ``ValueError``: it would make those scenarios identical in that parameter.
    Raises ``KeyError`` for an unknown scenario and ``ValueError`` for an empty or repeated list.
    """
    names = list(scenarios)
    if not names:
        raise ValueError("scenarios is empty; name at least one (None is the baseline)")
    if exp.scenario is not None:
        raise ValueError("run_scenarios takes the scenarios as a list; leave exp.scenario as None")
    repeated = sorted({str(s) for s in names if names.count(s) > 1})
    if repeated:
        raise ValueError(f"scenario(s) repeated: {repeated}")
    unknown = [s for s in names if s is not None and s not in SCENARIOS]
    if unknown:
        raise KeyError(f"unknown scenario(s) {unknown}; scenarios: {list(SCENARIOS)}")
    clashes = {s: sorted(set(SCENARIOS[s]) & set(exp.overrides)) for s in names if s is not None}
    clashes = {s: c for s, c in clashes.items() if c}
    if clashes:
        params = sorted({p for c in clashes.values() for p in c})
        raise ValueError(
            f"overrides set parameter(s) {params} that scenario(s) {list(clashes)} also set; in run_scenarios the "
            "override would erase the difference between the scenarios. Drop the override, or run each scenario "
            "with run_experiment"
        )
    if validate:
        check_supports(exp, dt, stop)

    base = design(exp)
    n = len(base)
    sampled = [str(c) for c in base.columns]
    fixed, _ = fixed_params(exp)
    # Scenario parameters that are not sampled become columns too: the scenario's value in its block, the fixed value
    # (baseline, or an override's) elsewhere. NaN in DemandGrowthLate means None.
    extra: list[str] = []
    for s in names:
        for p in SCENARIOS[s] if s is not None else ():
            if p not in sampled and p not in extra:
                extra.append(p)
    blocks = []
    pinned: dict[str | None, list[str]] = {}
    for s in names:
        own = dict(SCENARIOS[s]) if s is not None else {}
        block = base.copy()
        for p in extra:
            v = own.get(p, fixed.scalars[p])
            block[p] = np.nan if v is None else float(v)
        pinned[s] = sorted(p for p in own if p in sampled)
        for p in pinned[s]:
            block[p] = float(own[p])
        blocks.append(block)
    combined = pd.concat(blocks, ignore_index=True)
    combined.index.name = "run"

    res = execute(
        Experiment(
            overrides=exp.overrides,
            tables=exp.tables,
            samples=combined,
            ai_on=exp.ai_on,
            perturb_from=exp.perturb_from,
            noise=exp.noise,
            noise_seed=exp.noise_seed,
        ),
        outputs=outputs,
        record_every=record_every,
        dt=dt,
        stop=stop,
        workers=workers,
        chunk_size=chunk_size,
        validate=validate,
        noise_index=np.tile(np.arange(n), len(names)),
    )

    views: dict[str | None, ExperimentResult] = {}
    for i, s in enumerate(names):
        lo, hi = i * n, (i + 1) * n
        valid = res.valid[lo:hi]
        samples = combined.iloc[lo:hi][sampled].reset_index(drop=True)
        samples.index.name = "run"
        meta = {
            **res.meta,
            "experiment": experiment_dict(replace(exp, scenario=s)),
            "seed": exp.seed,
            "n": n,
            "n_invalid": int((~valid).sum()),
            "scenario": s,
            "pinned": pinned[s],
        }
        views[s] = ExperimentResult(
            samples=samples,
            years=res.years,
            series={k: a[lo:hi] for k, a in res.series.items()},
            valid=valid,
            meta=meta,
        )
    meta = {
        **res.meta,
        "experiment": experiment_dict(exp),
        "seed": exp.seed,
        "n_per_scenario": n,
        "scenarios": names,
        "pinned": [{"scenario": s, "levers": pinned[s]} for s in names],
    }
    return ScenarioResult(scenarios=tuple(names), results=views, pinned=pinned, meta=meta)
