"""The scalar engine: ``run()``, the time loop that calls the sections in the prototype's order.

Prototype: ``phase7_sim.py`` ``run()``, lines 150-636: S0 (lines 151-159, before the loop), S1 (lines 160-163, the step
preamble), the sections S2-S13 (lines 164-496), the recording block (497-545) and the integration block (546-635).
Euler integration with ``Year = 2024 + t``; the last step is recorded but not integrated past.

Spec modules, by section: S0 is 10 Sourcing choice; S2 is 7 AI capability, 6 Delivery AI and 1 IT work demand; S3 is 1c
Work queues, 3 Workforce and 1 IT work demand; S4, S5 and S7 are 3 Workforce, 9 Visa policy and 3b Hiring pipeline; S6
and S8 are 4 Labour market, 3b Hiring pipeline, 3 Workforce and 9 Visa policy; S9-S11 are 8 Finance, 7 AI capability,
2 Contracts, 4 Labour market and 10 Sourcing choice; S12 is 6 Delivery AI; S13 is 5 Consumer AI, 1b Applications and
seats, 7 AI capability, 8 Finance, 1 IT work demand, 9 GCCs and 10 Sourcing choice. The integration block updates the
stocks of every module.

This engine is the reference statement of the model and the oracle for faster engines. It reproduces the prototype bit
for bit: same expressions, same operand order, built-in ``sum()`` over the same sequences (CPython 3.12 compensated
summation), and the same stock update order.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from aisim.dims import EMPLOYERS, LEVELS, SECTORS
from aisim.params import Params
from aisim.scalar.adoption import adoption
from aisim.scalar.capability import capability
from aisim.scalar.consumer import consumer, drivers
from aisim.scalar.finance import contracts, costs, spend, vendor_books, wage_targets
from aisim.scalar.integrate import integrate, track_mins
from aisim.scalar.labour_market import exits, hiring, pools, switching, time_to_fill, unemployment, visa_flows
from aisim.scalar.record import record
from aisim.scalar.sourcing import option_costs, sourcing_flows, sourcing_targets
from aisim.scalar.step import Step
from aisim.scalar.work import work
from aisim.scalar.workforce import level_mix, staffing, vacancies
from aisim.state import State, copy_state, load_initial_state
from aisim.util import softmax

Trace = Callable[[int, float, str, object], None]
"""``trace(step, year, section_id, intermediates)``, called after every section of every step."""

SECTION_IDS = (
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8a",
    "S8b",
    "S8c",
    "S8d",
    "S8e",
    "S8f",
    "S9",
    "S10",
    "S11a",
    "S11b",
    "S11c",
    "S11d",
    "S12",
    "S13a",
    "S13b",
    "S13c",
    "S13d",
)
"""The section IDs passed to ``trace``, in the order they run in every step (recon B1, with S8, S11 and S13 split)."""

TABLES_1D = ("SectorShare", "LOBWage", "RegDragLevel", "WTMix", "a2024", "amax", "SpeedUp", "BuildMix", "OffExp")
"""The tables ``run()`` reads. ``Mix0`` and ``Src0`` only describe the 2024 state."""


@dataclass(frozen=True, slots=True)
class RunResult:
    """The output of one run: recorded rows, the state at the end and the minimum of each tracked stock."""

    rows: list[dict[str, float]]
    final_state: State
    mins: dict[str, float]


def tilt_sourcing_perception(st: State, GCCMomentum: float) -> None:
    """S0: tilt every sector's perceived sourcing shares toward GCC by ``GCCMomentum`` on the logit scale, in place.

    It stands for the GCC build-out decided before 2024 and still being executed (07). No tilt when it is 0.
    """
    if GCCMomentum != 0.0:
        for x in SECTORS:
            lg = {
                e: math.log(max(st["SrcPerc"][x][e], 1e-12)) + (GCCMomentum if e == "GCC" else 0.0) for e in EMPLOYERS
            }
            st["SrcPerc"][x] = softmax(lg)


def run(
    params: Params | None = None,
    init: State | None = None,
    *,
    ai_on: bool = True,
    dt: float = 1 / 16,
    stop: float = 16.0,
    record_every: float = 0.25,
    trace: Trace | None = None,
    **overrides: float,
) -> RunResult:
    """Run the model from 2024 for ``stop`` years and return its rows, final state and stock minimums.

    ``params`` defaults to ``Params.baseline()`` and ``init`` to the calibrated 2024 state; ``init`` is copied, never
    changed. ``overrides`` are applied with ``Params.with_overrides``. ``ai_on=False`` switches off delivery AI,
    consumer AI, AI seat attach and AI-driven demand. A row is recorded every ``record_every`` years (rounded to whole
    steps). ``trace``, when given, is called after every section of every step with the step number, the year, the
    section ID (``SECTION_IDS``) and the section's intermediates; it does not change the results.
    """
    p = Params.baseline() if params is None else params
    if overrides:
        p = p.with_overrides(**overrides)
    pr = {k: v for k, v in p.scalars.items() if v is not None}
    demand_growth_late = p.scalars["DemandGrowthLate"]
    tb = {name: p.table(name) for name in TABLES_1D}
    st = copy_state(load_initial_state() if init is None else init)

    # ---- S0 ----
    tilt_sourcing_perception(st, pr["GCCMomentum"])
    rows: list[dict[str, float]] = []
    n = round(stop / dt)
    rk = max(1, round(record_every / dt))
    mins: dict[str, float] = {}
    t = 0.0
    for step in range(n + 1):
        # ---- S1 ----
        y = 2024 + t
        W = {l: pr["W_" + l] for l in LEVELS}
        cap = capability(pr, tb, st, y, ai_on, demand_growth_late)
        if trace is not None:
            trace(step, y, "S2", cap)
        wk = work(pr, tb, st, W, cap.Pew)
        if trace is not None:
            trace(step, y, "S3", wk)
        mix = level_mix(pr, st, W, ai_on)
        if trace is not None:
            trace(step, y, "S4", mix)
        stf = staffing(pr, st, y, wk.BLe, mix)
        if trace is not None:
            trace(step, y, "S5", stf)
        unemp = unemployment(pr, st)
        if trace is not None:
            trace(step, y, "S6", unemp)
        vac = vacancies(pr, st, stf.Desired)
        if trace is not None:
            trace(step, y, "S7", vac)
        swi = switching(pr, st, vac.avail, vac.promo)
        if trace is not None:
            trace(step, y, "S8a", swi)
        visa = visa_flows(pr, st, stf.VisaTight, cap.G)
        if trace is not None:
            trace(step, y, "S8b", visa)
        ex = exits(pr, st, vac.surplus, vac.promo, swi.sw, visa)
        if trace is not None:
            trace(step, y, "S8c", ex)
        hi = hiring(pr, st, vac.avail, vac.promo, swi.sw, visa.VisaCap)
        if trace is not None:
            trace(step, y, "S8d", hi)
        ttf = time_to_fill(pr, st, hi.hires, vac.promo, swi.sw)
        if trace is not None:
            trace(step, y, "S8e", ttf)
        pl = pools(pr, st, cap.G, unemp, ttf.TTFr)
        if trace is not None:
            trace(step, y, "S8f", pl)
        cst = costs(pr, st, y, W, wk.CompE, wk.EffStaffE)
        if trace is not None:
            trace(step, y, "S9", cst)
        con = contracts(pr, st, y, wk.Pe, stf.UnitIn, hi.hires, cst)
        if trace is not None:
            trace(step, y, "S10", con)
        flo = sourcing_flows(pr, st, con.VF)
        if trace is not None:
            trace(step, y, "S11a", flo)
        bks = vendor_books(pr, st, wk.Pe, wk.CompS, wk.CS, pl.TTFratio, flo.SignS, con)
        if trace is not None:
            trace(step, y, "S11b", bks)
        wag = wage_targets(pr, st, con.VF)
        if trace is not None:
            trace(step, y, "S11c", wag)
        spd = spend(pr, wk.Pe, cst, con.VF)
        if trace is not None:
            trace(step, y, "S11d", spd)
        ado = adoption(pr, st, ai_on, wk.EffStaffE, cst.LabourCost, cst.AICostPerUnit, bks.VB)
        if trace is not None:
            trace(step, y, "S12", ado)
        drv = drivers(pr, st, y, ai_on, cap.G, wk.Completion, wk.P_all, cst.AIShockNow, spd.ServicesSpend)
        if trace is not None:
            trace(step, y, "S13a", drv)
        opt = option_costs(pr, st, W, mix.ShareL, cst.AICostPerUnit, con.VF)
        if trace is not None:
            trace(step, y, "S13b", opt)
        csm = consumer(pr, tb, st, y, ai_on, cap.G, wk.CS, wk.CompS, spd.ServicesSpend, drv)
        if trace is not None:
            trace(step, y, "S13c", csm)
        RegDrag = {x: c.RegDrag for x, c in csm.cons.items()}
        tgt = sourcing_targets(pr, tb, st, ai_on, RegDrag, drv.GCCAppeal, pl.TTFratio, opt)
        if trace is not None:
            trace(step, y, "S13d", tgt)
        s = Step(
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
        # ---- REC ----
        if step % rk == 0:
            rows.append(record(st, s, tb["SectorShare"]))
        if step == n:
            break
        # ---- INT ----
        integrate(pr, st, s, dt)
        track_mins(st, mins)
        t += dt
    return RunResult(rows=rows, final_state=st, mins=mins)
