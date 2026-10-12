"""Perturb from year Y: the calibrated baseline runs unchanged until Y, and everything that differs acts from Y.

A two-phase run (recon 06 B6 approach (i)):

1. **Phase 1** runs the calibrated baseline from 2024 to Y. In a batch it runs once, for one run, and is tiled.
2. **Phase 2** restarts from phase 1's state at Y with each run's own parameters (scenario, overrides, sampled levers)
   and its noise, at the global step of Y, without the S0 tilt (the state already carries it), and with the five
   2024-anchored paths re-anchored at Y where the run's rates differ from the base (``aisim.params.Reanchor``).

The result has phase 1's rows before Y and phase 2's rows from Y on (the row at Y is phase 2's: the run's parameters
act at Y), the stock minimums of both phases (element-wise minimum) and ``finite`` of both (``finite1 & finite2``).
A restart at a Y on the dt grid is exact: with unchanged parameters a two-phase run equals an uninterrupted run bit for
bit (recon 06 B2), and Y = 2024 equals a plain run.

Any parameter, current or future, acts from Y without touching its read sites. Parameters that describe 2024 itself
(``domains()`` column ``level_2024``) cannot act from Y; ``aisim.experiment.validate`` rejects them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from aisim.batch.engine import BatchResult, run_batch
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import F
from aisim.params import Params, Reanchor
from aisim.scalar.engine import RunResult, run
from aisim.state import State


def start_step_of(Y: float, dt: float) -> int:
    """The global step of year ``Y``, counted from 2024: ``round((Y - 2024) / dt)``."""
    return round((Y - 2024) / dt)


def _phase1_rows(start_step: int, record_every: float, dt: float) -> int:
    """How many recorded rows fall strictly before the start step: ``ceil(start_step / rk)``."""
    rk = max(1, round(record_every / dt))
    return -(-start_step // rk)


def _reanchor(base: Params, Y: float, start_step: int) -> Reanchor | None:
    """The re-anchoring at Y, or None at Y = 2024: the paths are anchored there already, and re-anchoring could move
    ``LOBAuto``'s anchor by an ulp (``aL_max - (aL_max - aL_2024)``), so Y = 2024 equals a plain run bit for bit."""
    return Reanchor.at(base, Y) if start_step > 0 else None


def run_from(
    params_base: Params,
    params_run: Params,
    init: State | None = None,
    *,
    Y: float,
    dt: float = 1 / 16,
    stop: float = 16.0,
    record_every: float = 0.25,
    noise: Mapping[str, Sequence[float]] | None = None,
) -> RunResult:
    """One two-phase run with the scalar engine: ``params_base`` from 2024 to Y, then ``params_run`` from Y to
    ``2024 + stop``. ``noise`` holds the run's noise factors by channel, indexed by the global step
    (``aisim.noise.ou_factors``). The reference for the batched two-phase run."""
    k = start_step_of(Y, dt)
    r1 = run(params_base, init, dt=dt, stop=k * dt, record_every=record_every)
    r2 = run(
        params_run,
        r1.final_state,
        dt=dt,
        stop=stop,
        record_every=record_every,
        start_step=k,
        tilt=False,
        reanchor=_reanchor(params_base, Y, k),
        noise=noise,
    )
    rows = r1.rows[: _phase1_rows(k, record_every, dt)] + r2.rows
    mins = {key: min(r1.mins[key], v) if key in r1.mins else v for key, v in r2.mins.items()}
    return RunResult(rows=rows, final_state=r2.final_state, mins=mins)


@dataclass(frozen=True, slots=True)
class Phase1:
    """Phase 1 of a batched two-phase run: the base run from 2024 to Y, for one run, as plain arrays (picklable).

    ``years`` and ``series`` (``(1, T1)``) hold the rows before Y; ``state`` the state at Y; ``mins`` the stock
    minimums (``(1,)``, empty when Y = 2024); ``finite`` whether it stayed valid; ``reanchor`` the base paths at Y (None
    at Y = 2024).
    """

    Y: float
    start_step: int
    years: F
    series: dict[str, F]
    state: dict[str, F]
    mins: dict[str, F]
    finite: bool
    reanchor: Reanchor | None


def phase1(
    Y: float,
    *,
    base: Params | None = None,
    dt: float = 1 / 16,
    record_every: float = 1.0,
    outputs: Sequence[str] | None = None,
) -> Phase1:
    """Run ``base`` (default: the calibrated baseline) from 2024 to Y once, with the batched engine and AI on."""
    p = Params.baseline() if base is None else base
    k = start_step_of(Y, dt)
    res = run_batch(BatchParams.stack([p]), dt=dt, stop=k * dt, record_every=record_every, outputs=outputs)
    n1 = _phase1_rows(k, record_every, dt)
    return Phase1(
        Y=Y,
        start_step=k,
        years=res.years[:n1],
        series={key: a[:, :n1] for key, a in res.series.items()},
        state=res.final_state.arrays(),
        mins=dict(res.mins),
        finite=bool(res.finite[0]),
        reanchor=_reanchor(p, Y, k),
    )


def run_batch_from(
    params: BatchParams,
    *,
    Y: float,
    dt: float = 1 / 16,
    stop: float = 16.0,
    record_every: float = 1.0,
    outputs: Sequence[str] | None = None,
    ai_on: bool | Sequence[bool] = True,
    noise: Mapping[str, F] | None = None,
    base: Params | None = None,
    first: Phase1 | None = None,
) -> BatchResult:
    """N two-phase runs with the batched engine: phase 1 (``first``, or ``phase1(Y, base=base, ...)``) tiled to N
    runs, then ``params`` from Y. ``noise`` maps channels to ``(N, steps + 1)`` factors indexed by the global step.

    Raises ``ValueError`` if ``first`` was run for another Y or dt."""
    p1 = phase1(Y, base=base, dt=dt, record_every=record_every, outputs=outputs) if first is None else first
    if p1.Y != Y or p1.start_step != start_step_of(Y, dt):
        raise ValueError(f"phase 1 was run to {p1.Y} (step {p1.start_step}), not to {Y} at dt = {dt}")
    n = params.n
    init = BatchState(**{key: np.repeat(a, n, axis=0) for key, a in p1.state.items()})
    r2 = run_batch(
        params,
        init,
        ai_on=ai_on,
        dt=dt,
        stop=stop,
        record_every=record_every,
        outputs=outputs,
        start_step=p1.start_step,
        tilt=False,
        reanchor=p1.reanchor,
        noise=noise,
    )
    years = np.concatenate([p1.years, r2.years])
    series = {key: np.concatenate([np.repeat(p1.series[key], n, axis=0), a], axis=1) for key, a in r2.series.items()}
    mins = {key: np.minimum(p1.mins[key], a) if key in p1.mins else a for key, a in r2.mins.items()}
    finite = r2.finite & p1.finite
    return BatchResult(years=years, series=series, final_state=r2.final_state, mins=mins, finite=finite)
