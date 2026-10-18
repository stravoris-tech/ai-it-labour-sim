"""The batched engine: ``run_batch()``, the time loop of N runs advancing together as arrays.

It calls the sections in the scalar engine's order (``aisim.scalar.engine``), each mirroring its scalar counterpart on
arrays with a leading run axis. Runs never interact: every operation is element-wise over the run axis, so a run's
results do not depend on the other runs in its batch, and a run that fails numerically (NaN, inf) cannot affect them.

The scalar engine is the oracle. The batched engine matches it within a relative 1e-12 (absolute floor 1e-12) on every
row key, the final state and the stock minimums, and on every section's intermediates (``tests/test_batch_parity.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from aisim.batch.adoption import adoption
from aisim.batch.axes import EMP_IX
from aisim.batch.capability import capability
from aisim.batch.consumer import consumer, drivers
from aisim.batch.finance import contracts, costs, spend, vendor_books, wage_targets
from aisim.batch.integrate import Mins, integrate
from aisim.batch.labour_market import exits, hiring, pools, switching, time_to_fill, unemployment, visa_flows
from aisim.batch.params import BatchParams, param_denominator_faults
from aisim.batch.record import EXTRA_KEYS, ROW_KEYS, record, record_extras
from aisim.batch.sourcing import option_costs, sourcing_flows, sourcing_targets
from aisim.batch.state import BatchState
from aisim.batch.step import Step
from aisim.batch.util import B, F, Faults, softmax
from aisim.batch.work import work
from aisim.batch.workforce import level_mix, staffing, vacancies
from aisim.dims import LEVELS
from aisim.params import Reanchor

Trace = Callable[[int, float, str, object], None]
"""``trace(step, year, section_id, intermediates)``, called after every section of every step."""

PARAM_SITE_PREFIX = "PARAM "
"""Fault sites of the pre-loop parameter check are named ``PARAM <denominator>``."""


@dataclass(frozen=True, slots=True)
class BatchResult:
    """The output of a batch of N runs.

    - ``years``: ``(T,)``, the recorded years.
    - ``series``: key to ``(N, T)`` array, for the recorded keys: row keys in row order, then any extras
      (``EXTRA_KEYS``) in their order.
    - ``final_state``: the state of every run after the last step.
    - ``mins``: tracked-stock key to ``(N,)`` array of running minimums (as the scalar engine's ``mins``).
    - ``finite``: ``(N,)``, True for a valid run: its state stayed finite and it reached no site where the scalar
      engine raises (a crash-site fault); see ``run_batch``.
    """

    years: F
    series: Mapping[str, F]
    final_state: BatchState
    mins: Mapping[str, F]
    finite: B

    def rows(self, i: int) -> list[dict[str, float]]:
        """Run ``i`` in the scalar ``RunResult.rows`` format. Raises ``ValueError`` unless every key was recorded."""
        if tuple(self.series) != ROW_KEYS:
            raise ValueError("rows() needs every row key recorded (outputs=None)")
        cols = [(k, a[i]) for k, a in self.series.items()]
        return [{k: float(col[t]) for k, col in cols} for t in range(len(self.years))]


def tilt_sourcing_perception(st: BatchState, GCCMomentum: F) -> None:
    """S0: tilt perceived sourcing shares toward GCC by ``GCCMomentum`` on the logit scale, in place, per run.

    Runs with ``GCCMomentum == 0`` are left unchanged: a tilt of 0 is not the identity (recon 03 F1).
    """
    tilt = np.zeros((st.n, 1, st.SrcPerc.shape[2]))
    tilt[:, 0, EMP_IX["GCC"]] = GCCMomentum
    lg = np.log(np.maximum(st.SrcPerc, 1e-12)) + tilt
    np.copyto(st.SrcPerc, softmax(lg), where=(GCCMomentum != 0.0)[:, None, None])


def run_batch(
    params: BatchParams | None = None,
    init: BatchState | None = None,
    *,
    ai_on: bool | Sequence[bool] = True,
    dt: float = 1 / 16,
    stop: float = 16.0,
    record_every: float = 1.0,
    outputs: Sequence[str] | None = None,
    trace: Trace | None = None,
    start_step: int = 0,
    tilt: bool = True,
    reanchor: Reanchor | None = None,
    noise: Mapping[str, F] | None = None,
) -> BatchResult:
    """Run N runs of the model from 2024 for ``stop`` years, together, and return their series, final states and mins.

    - ``params`` defaults to ``BatchParams.baseline(1)`` and ``init`` to ``BatchState.baseline(params.n)``; ``init``
      is copied, never changed. Their run counts must agree.
    - ``ai_on`` is one switch for every run or one per run.
    - A row is recorded every ``record_every`` years (rounded to whole steps). The default is 1.0, not the scalar
      engine's 0.25, because recorded rows dominate memory: at N = 10,000 all 317 keys take about 0.4 GiB at 1.0,
      1.5 GiB at 0.25 and 6.1 GiB at 1/16 (recon 03 F3). ``outputs`` limits the recorded keys (default: all 317 row
      keys). It may also name extras (``EXTRA_KEYS``), which are recorded only when asked for.
    - ``trace``, when given, is called after every section of every step with the step number, the year, the section
      ID (``aisim.scalar.engine.SECTION_IDS``) and the section's intermediates (arrays with a leading run axis).
    - Restarts (phase 2 of a two-phase run, ``aisim.perturb``), as in the scalar ``run``: ``start_step`` (the global
      step to start at; rows are recorded on the global step), ``tilt=False`` (skip S0), ``reanchor`` (the five
      2024-anchored paths, per run where the rates differ from the base) and ``noise`` (channel to ``(N, steps + 1)``
      factors, indexed by the global step). Every default reproduces a plain run bit for bit.

    A numerical failure in one run never raises and never changes another run. ``finite[i]`` marks a valid run: a
    finite state and no crash-site fault. It is False when any of these holds for run ``i``:

    1. its state became non-finite at some step (or was non-finite at the start);
    2. it reached a site where the scalar engine raises (recon 03 B2): ``AICostPerUnit`` or ``CreditCostPB`` equal to
       0 (``AIShockMult = 0`` inside the shock window), ``Budget`` equal to 0 (``BudgetShock = 1``), or a negative
       ``1 - g`` raised to a non-integer power (``g > 1``);
    3. one of its parameter-only denominators (``params.PARAM_DENOMINATORS``, the ``SpeedUp`` table and the
       parameter-only compound denominators) is zero or negative, checked once before the loop.

    Other zero denominators that depend on the state are not checked. Where the scalar engine would raise on one of
    them, this engine may instead carry on with a limiting value (an infinity clamped by a ``min``, ``max`` or
    ``clamp``, say) and report ``finite = True``.
    """
    result, _ = simulate(
        params,
        init,
        ai_on=ai_on,
        dt=dt,
        stop=stop,
        record_every=record_every,
        outputs=outputs,
        trace=trace,
        start_step=start_step,
        tilt=tilt,
        reanchor=reanchor,
        noise=noise,
    )
    return result


def simulate(
    params: BatchParams | None = None,
    init: BatchState | None = None,
    *,
    ai_on: bool | Sequence[bool] = True,
    dt: float = 1 / 16,
    stop: float = 16.0,
    record_every: float = 1.0,
    outputs: Sequence[str] | None = None,
    trace: Trace | None = None,
    start_step: int = 0,
    tilt: bool = True,
    reanchor: Reanchor | None = None,
    noise: Mapping[str, F] | None = None,
) -> tuple[BatchResult, Faults]:
    """``run_batch``, also returning the per-site fault masks (internal; for tests of the fault sites)."""
    pr = BatchParams.baseline(1) if params is None else params
    n = pr.n
    st = (BatchState.baseline(n) if init is None else init).copy()
    if st.n != n:
        raise ValueError(f"params has {n} runs but init has {st.n}")
    ai: B = np.full(n, ai_on, dtype=np.bool_) if isinstance(ai_on, bool) else np.array(list(ai_on), dtype=np.bool_)
    if ai.shape != (n,):
        raise ValueError(f"ai_on has {ai.size} values for {n} runs")
    faults = Faults(n)
    for name, mask in param_denominator_faults(pr).items():
        faults.flag(PARAM_SITE_PREFIX + name, mask)
    keys = _output_keys(outputs)
    want_extras = any(k in EXTRA_KEYS for k in keys)
    ok = _finite_state(st)

    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        # ---- S0 ----
        if tilt:
            tilt_sourcing_perception(st, pr["GCCMomentum"])
        steps = round(stop / dt)
        rk = max(1, round(record_every / dt))
        j0 = -(-start_step // rk)  # the first recorded row, counted on the global step
        n_rec = steps // rk - j0 + 1
        years = np.empty(n_rec)
        series: dict[str, F] = {}
        mins = Mins()
        W = pr.fam("W_", LEVELS)
        t = start_step * dt
        for step in range(start_step, steps + 1):
            # ---- S1 ----
            y = 2024 + t
            nz = {ch: a[:, step] for ch, a in noise.items()} if noise else None
            s = _sections(pr, st, y, ai, W, faults, step, trace, reanchor, nz)
            # ---- REC ----
            if step % rk == 0:
                row = record(st, s, pr.table("SectorShare"))
                if want_extras:
                    row |= record_extras(st, s)
                j = step // rk - j0
                if j == 0:
                    series = {k: np.empty((n, n_rec)) for k in keys}
                years[j] = round(y, 4)
                for k, a in series.items():
                    a[:, j] = row[k]
            if step == steps:
                break
            # ---- INT ----
            integrate(pr, st, s, dt, faults)
            mins.track(st)
            ok &= _finite_state(st)
            t += dt
    finite = ok & ~faults.any()
    result = BatchResult(years=years, series=series, final_state=st, mins=mins.keyed(), finite=finite)
    return result, faults


def _sections(
    pr: BatchParams,
    st: BatchState,
    y: float,
    ai: B,
    W: F,
    faults: Faults,
    step: int,
    trace: Trace | None,
    reanchor: Reanchor | None = None,
    nz: Mapping[str, F] | None = None,
) -> Step:
    """Run sections S2-S13 for one step and return their intermediates, calling ``trace`` after each."""

    def emit(section_id: str, value: object) -> None:
        if trace is not None:
            trace(step, y, section_id, value)

    cap = capability(pr, st, y, ai, faults, reanchor=reanchor, nz=nz)
    emit("S2", cap)
    wk = work(pr, st, W, cap.Pew)
    emit("S3", wk)
    mix = level_mix(pr, st, W, ai)
    emit("S4", mix)
    stf = staffing(pr, st, y, wk.BLe, mix)
    emit("S5", stf)
    unemp = unemployment(pr, st)
    emit("S6", unemp)
    vac = vacancies(pr, st, stf.Desired)
    emit("S7", vac)
    swi = switching(pr, st, vac.avail, vac.promo)
    emit("S8a", swi)
    visa = visa_flows(pr, st, stf.VisaTight, cap.G)
    emit("S8b", visa)
    ex = exits(pr, st, vac.surplus, vac.promo, swi.sw, visa)
    emit("S8c", ex)
    hi = hiring(pr, st, vac.avail, vac.promo, swi.sw, visa.VisaCap)
    emit("S8d", hi)
    ttf = time_to_fill(pr, st, hi.hires, vac.promo, swi.sw)
    emit("S8e", ttf)
    pl = pools(pr, st, cap.G, unemp, ttf.TTFr, hi.hires)
    emit("S8f", pl)
    cst = costs(pr, st, y, W, wk.CompE, wk.EffStaffE, reanchor=reanchor, nz=nz)
    emit("S9", cst)
    con = contracts(pr, st, y, wk.Pe, stf.UnitIn, hi.hires, cst, nz=nz)
    emit("S10", con)
    flo = sourcing_flows(pr, st, con.VF)
    emit("S11a", flo)
    bks = vendor_books(pr, st, wk.Pe, wk.CompS, wk.CS, pl.TTFratio, flo.SignS, con, ex.fl, swi.sw, cst.Wage)
    emit("S11b", bks)
    wag = wage_targets(pr, st, con.VF)
    emit("S11c", wag)
    spd = spend(pr, wk.Pe, cst, con.VF)
    emit("S11d", spd)
    ado = adoption(pr, st, ai, wk.EffStaffE, cst.LabourCost, cst.AICostPerUnit, bks.VB, faults)
    emit("S12", ado)
    drv = drivers(
        pr,
        st,
        y,
        ai,
        cap.G,
        wk.Completion,
        wk.P_all,
        cst.AIShockNow,
        spd.ServicesSpend,
        faults,
        reanchor=reanchor,
        nz=nz,
    )
    emit("S13a", drv)
    opt = option_costs(pr, st, W, mix.ShareL, cst.AICostPerUnit, con.VF)
    emit("S13b", opt)
    csm = consumer(pr, st, y, ai, cap.G, wk.CS, wk.CompS, spd.ServicesSpend, drv, nz=nz)
    emit("S13c", csm)
    tgt = sourcing_targets(pr, st, ai, csm.cons.RegDrag, drv.GCCAppeal, pl.TTFratio, opt, wk.CS)
    emit("S13d", tgt)
    return Step(
        y=y,
        W=W,
        cap=cap,
        work=wk,
        mix=mix,
        staffing=stf,
        unemp=unemp,
        vac=vac,
        switching=swi,
        visa=visa,
        exits=ex,
        hiring=hi,
        ttf=ttf,
        pools=pl,
        costs=cst,
        contracts=con,
        flows=flo,
        books=bks,
        wages=wag,
        spend=spd,
        adoption=ado,
        drivers=drv,
        options=opt,
        consumer=csm,
        targets=tgt,
    )


def _output_keys(outputs: Sequence[str] | None) -> list[str]:
    """The keys to record, row keys in row order then extras: ``outputs`` (every row key if None).

    Raises ``ValueError`` for unknown keys.
    """
    if outputs is None:
        return list(ROW_KEYS)
    unknown = sorted(set(outputs) - set(ROW_KEYS) - set(EXTRA_KEYS))
    if unknown:
        raise ValueError(f"unknown output key(s): {unknown}")
    wanted = set(outputs)
    return [k for k in (*ROW_KEYS, *EXTRA_KEYS) if k in wanted]


def _finite_state(st: BatchState) -> B:
    """Per run: every state value is finite."""
    ok: B = np.ones(st.n, dtype=np.bool_)
    for a in st.arrays().values():
        ok &= np.isfinite(a.reshape(st.n, -1)).all(axis=1)
    return ok
