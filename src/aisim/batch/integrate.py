"""All stock updates of one Euler step of N runs, in place, and the tracking of stock minimums.

Mirrors ``aisim.scalar.integrate``. Every stock element that the scalar engine updates once a step is updated in one
vectorised statement. The order that matters is kept exactly (recon 03 C5):

- ``U``, ``R``, ``LeftField`` and ``Retired`` receive several additions a step. They are made one by one in the scalar
  engine's order: an explicit loop over units (levels inside it for the region-level accumulators), with
  ``U[IN] += d * expiry`` straight after OV, then the pool loop. A single summed addition would round differently.
- Read-after-update: ``ClientPRef`` reads the updated ``ClientP``, and ``NewD`` the updated ``NewV``.

``Committed / Budget`` is a fault site (recon 03 B2: ``BudgetShock = 1`` from 2024 makes ``Budget`` 0).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from aisim.batch.axes import EMP_IX, POOL_IX, REG_IX, UNIT_IX
from aisim.batch.labour_market import LEVEL_FLOWS, POOL_FLOWS
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.step import Step
from aisim.batch.util import F, Faults
from aisim.dims import LEVELS, REGIONS, SECTORS, TYPES, UNITS, VENDORS

BUDGET_SITE = "INT Committed / Budget"

_FL = {name: i for i, name in enumerate(LEVEL_FLOWS)}
_PZ = {name: i for i, name in enumerate(POOL_FLOWS)}
_OV, _OL, _IN = UNIT_IX["OV"], UNIT_IX["OL"], REG_IX["IN"]


def integrate(pr: BatchParams, st: BatchState, s: Step, d: float, faults: Faults) -> None:
    """Advance every stock of every run by one step of length ``d``, in place."""
    cons, Demand = s.consumer.cons, s.consumer.Demand
    Comp, Aband = s.work.Comp, s.work.Aband
    Src, SignS = s.flows.Src, s.flows.SignS
    SrcTarget = s.targets.SrcTarget

    def col(name: str) -> F:
        return pr[name][:, None]

    st.BL[...] += d * (Demand - Comp - Aband)
    st.AC[...] += d * cons.AdoptC
    st.LOB[...] += d * (cons.LOBTarget - st.LOB) / col("LOBAdjTime")
    st.Port[...] += d * (cons.NewApps - cons.Retire)
    st.SeatsB[...] += d * (cons.Seats - st.SeatsB) / col("SeatAdjTime")
    faults.flag(BUDGET_SITE, (cons.Budget == 0).any(axis=1))
    st.SpendRatio[...] += d * (cons.Committed / cons.Budget - st.SpendRatio) / col("BudgetCycle")
    moving = (pr["FreezeSourcing"] < 0.5)[:, None]
    SrcPerc = st.SrcPerc
    ih, gcc = EMP_IX["IH"], EMP_IX["GCC"]
    Contest = col("Contest")
    IHW = st.IHW + d * (Src.Contested * SrcPerc[:, :, ih] - Contest * Src.IHTurn)
    GCCW = st.GCCW + d * (Src.Contested * SrcPerc[:, :, gcc] - Contest * Src.GCCTurn)
    VW = st.VW + d * (SignS - Src.VExp)
    new_src = SrcPerc + d * (SrcTarget - SrcPerc) / pr["SrcPerceptionTime"][:, None, None]
    np.copyto(st.IHW, IHW, where=moving)
    np.copyto(st.GCCW, GCCW, where=moving)
    np.copyto(st.VW, VW, where=moving[:, :, None])
    np.copyto(st.SrcPerc, new_src, where=moving[:, :, None])
    st.Att[...] += d * s.drivers.AttAdopt
    st.CostPerc[...] += d * (s.drivers.CostIdx6 - st.CostPerc) / pr["CostPerceptionTime"]

    fl, promo, cancel = s.exits.fl, s.vac.promo, s.vac.cancel
    sw_in, sw_out = s.switching.sw[:, :, :, 0], s.switching.sw[:, :, :, 1]
    hires = s.hiring.hires
    expiry, conv = s.visa.expiry, s.visa.conv
    quits, leave, retire = fl[..., _FL["quits"]], fl[..., _FL["leave"]], fl[..., _FL["retire"]]
    promo_out, openings = fl[..., _FL["promo_out"]], fl[..., _FL["openings"]]
    layoffs, onboard = fl[..., _FL["layoffs"]], fl[..., _FL["onboard"]]
    conv_in = np.zeros_like(st.H)
    conv_in[:, _OL, :] = conv
    visa_out = np.zeros_like(st.H)
    visa_out[:, _OV, :] = expiry + conv
    st.V[...] += d * (openings - cancel - promo - sw_in - hires)
    st.O[...] += d * (hires - onboard)
    st.H[...] += d * (
        onboard + promo + sw_in + conv_in - promo_out - quits - leave - retire - layoffs - sw_out - visa_out
    )
    for u in range(len(UNITS)):
        r = POOL_IX[u]
        st.R[:, r, :] += d * layoffs[:, u, :]
        st.U[:, r, :] += d * (quits[:, u, :] - hires[:, u, :])
        for l in range(len(LEVELS)):
            st.LeftField[:, r] += d * leave[:, u, l]
            st.Retired[:, r] += d * retire[:, u, l]
        if u == _OV:
            st.U[:, _IN, :] += d * expiry

    pool, Grad, Enrol, ext = s.pools.pool, s.pools.Grad, s.pools.Enrol, s.ttf.ext
    rec_to_seek, rec_to_left = pool[..., _PZ["rec_to_seek"]], pool[..., _PZ["rec_to_left"]]
    seek_exit, rec_retire, seek_retire = (
        pool[..., _PZ["seek_exit"]],
        pool[..., _PZ["rec_retire"]],
        pool[..., _PZ["seek_retire"]],
    )
    grad_in = np.zeros_like(st.U)
    grad_in[:, :, 0] = Grad
    st.R[...] += d * (-rec_to_seek - rec_to_left - rec_retire)
    st.U[...] += d * (grad_in + rec_to_seek + ext - seek_exit - seek_retire)
    for l in range(len(LEVELS)):
        st.LeftField[...] += d * (rec_to_left[:, :, l] + seek_exit[:, :, l])
        st.Retired[...] += d * (rec_retire[:, :, l] + seek_retire[:, :, l])
    UnempRate = s.unemp.UnempRate
    st.Pipeline[...] += d * (Enrol - Grad)
    st.PUS[...] += d * (UnempRate - st.PUS) / col("UnempPerceptionTime")
    st.PUL[...] += d * (UnempRate - st.PUL) / col("StudentPerceptionTime")

    Pe, AdoptE = s.work.Pe, s.adoption.AdoptE
    st.A[...] += d * AdoptE
    st.PerceivedP[...] += d * (Pe - st.PerceivedP) / col("PerceptionTime")
    st.ClientP[...] += d * (Pe - st.ClientP) / col("ClientPerceptionTime")
    # Read-after-update (prototype line 602): ClientP was updated on the line above.
    st.ClientPRef[...] += d * (st.ClientP - st.ClientPRef) / col("TrendTime")
    st.TightPerc[...] += d * (s.staffing.VisaTight - st.TightPerc) / pr["TightPerceptionTime"]

    f, b = s.contracts.VF, s.books.VB
    st.Overhead[...] += d * (pr.fam("OverheadRate_", VENDORS) * f.Revenue - st.Overhead) / col("OverheadAdjTime")
    st.Viab[...] += d * (b.Margin - st.Viab) / col("ViabilityTime")
    st.CostProg[...] += d * (b.CostProgTarget - st.CostProg) / col("CostProgramTime")
    st.Disc[...] += d * (b.DiscTarget - st.Disc) / col("DiscAdjTime")
    st.ShareRef[...] += d * (b.VShare - st.ShareRef) / col("ShareRefTime")
    st.Leg[...] += d * (-f.ExpLeg)
    st.NewV[...] += d * (b.Sign - f.ExpNew)
    # Read-after-update (prototype line 614): NewV was updated on the line above.
    st.NewD[...] += d * (b.Sign * f.Dnew - st.NewV)
    st.NewP[...] += d * (b.Sign * f.PNew - f.ExpNew * f.AvgP - st.NewP * f.Glide)
    st.WI[...] += d * (s.wages.WITarget - st.WI) / col("WageAdjTime")


MIN_FAMILIES = ("H", "O", "V", "R", "U", "IHW", "GCCW", "VW", "Leg", "NewV", "NewP", "NewD")
"""The stocks whose running minimum is tracked, as ``aisim.scalar.integrate.track_mins`` tracks them."""


@dataclass
class Mins:
    """Running minimums of the tracked stocks, per run, after each step's updates (not of the initial state)."""

    lows: dict[str, F] = field(default_factory=dict)

    def track(self, st: BatchState) -> None:
        """Lower each running minimum to the current state."""
        for name in MIN_FAMILIES:
            a = getattr(st, name)
            prev = self.lows.get(name)
            self.lows[name] = np.minimum(np.full_like(a, 1e18) if prev is None else prev, a)

    def keyed(self) -> dict[str, F]:
        """The minimums as ``(N,)`` arrays, keyed and ordered as the scalar ``mins``; empty if never tracked."""
        if not self.lows:
            return {}
        lo = self.lows
        out: dict[str, F] = {}
        for grp in ("H", "O", "V"):
            for i, u in enumerate(UNITS):
                for j, l in enumerate(LEVELS):
                    out[f"{grp}_{u}_{l}"] = lo[grp][:, i, j]
        for grp in ("R", "U"):
            for i, r in enumerate(REGIONS):
                for j, l in enumerate(LEVELS):
                    out[f"{grp}_{r}_{l}"] = lo[grp][:, i, j]
        for i, x in enumerate(SECTORS):
            out[f"IHW_{x}"] = lo["IHW"][:, i]
            out[f"GCCW_{x}"] = lo["GCCW"][:, i]
            for j, v in enumerate(VENDORS):
                out[f"VW_{x}_{v}"] = lo["VW"][:, i, j]
        for i, v in enumerate(VENDORS):
            for j, k in enumerate(TYPES):
                for grp in ("Leg", "NewV", "NewP", "NewD"):
                    out[f"{grp}_{v}_{k}"] = lo[grp][:, i, j]
        return out
