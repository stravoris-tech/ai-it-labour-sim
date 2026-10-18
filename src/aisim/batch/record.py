"""Output rows of N runs: the 317 keys of ``aisim.scalar.record``, in the same order, each an ``(N,)`` array.

Built from the state before the step's integration and the step's intermediates, as the scalar row is. Sums are naive,
in the scalar engine's term order.

``record_extras`` records the 106 extras of ``aisim.scalar.record.EXTRA_KEYS`` (see its module docstring for each
family, its source and its unit), each an ``(N,)`` array read from the state or an intermediate.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from aisim.batch.axes import EMP_IX, LOC_MASK, POOL_MASK, REG_IX, UNITS_OF_EMP, VEND_IX
from aisim.batch.state import BatchState
from aisim.batch.step import Step
from aisim.batch.util import F, csum, csum_axis
from aisim.dims import EMPLOYERS, LEVELS, REGIONS, SECTORS, TYPES, UNITS, VENDORS, WTYPES
from aisim.scalar.record import EXTRA_KEYS as scalar_extra_keys


def record(st: BatchState, s: Step, SectorShare: F) -> dict[str, F]:
    """Return the output row of every run for the step whose intermediates are ``s``."""
    n = st.n
    Aemp, H = st.A, st.H
    work = s.work
    CompE, Completion, EmpShare, CS, CompS = work.CompE, work.Completion, work.EmpShare, work.CS, work.CompS
    LabourCost, Delivered = s.costs.LabourCost, s.costs.Delivered
    hires = s.hiring.hires
    ext, TTFr = s.ttf.ext, s.ttf.TTFr
    cons, Demand = s.consumer.cons, s.consumer.Demand
    CostOpt = s.options.CostOpt
    SrcTarget = s.targets.SrcTarget
    in_pool = [[u for u in range(len(UNITS)) if POOL_MASK[r, u]] for r in range(len(REGIONS))]
    row: dict[str, F] = {
        "year": np.full(n, round(s.y, 4)),
        "P_all": work.P_all,
        "Demand": s.consumer.DemandTot,
        "Completion": Completion,
        "Backlog": work.TotBL,
        "VisaTight": s.staffing.VisaTight,
        "ServicesSpend": s.spend.ServicesSpend,
        "RevenueTot": s.spend.RevenueTot,
        "ConsIT": s.drivers.ConsIT,
        "Grad_total": csum_axis(s.pools.Grad, 1),
        "Ext_total": csum_axis(ext.reshape(n, -1), 1),
        "G": s.cap.G,
        "Att": s.drivers.Att,
        "A_mean": csum_axis(Aemp * CompE, 1) / np.maximum(Completion, 1e-9),
        "HireJ_IN": csum(hires[:, u, 0] for u in in_pool[REG_IX["IN"]]),
        "HireJ_ON": csum(hires[:, u, 0] for u in in_pool[REG_IX["ON"]]),
        "AC_mean": csum_axis(st.AC * SectorShare, 1),
    }
    for i, u in enumerate(UNITS):
        row["H_" + u] = csum_axis(H[:, i, :], 1)
        row["LabCost_" + u] = LabourCost[:, i]
        row["Del_" + u] = Delivered[:, i]
    labpb = s.adoption.labpb
    for e in EMPLOYERS:
        j = EMP_IX[e]
        row["Head_" + e] = csum(row["H_" + u] for i, u in enumerate(UNITS) if UNITS_OF_EMP[j, i])
        row["A_" + e] = Aemp[:, j]
        row["P_" + e] = work.Pe[:, j]
        row["Cost_" + e] = CostOpt[:, j]
        row["CompE_" + e] = CompE[:, j]
        row["LabPB_" + e] = labpb[:, j]
        row["WorkShare_" + e] = csum_axis(EmpShare[:, :, j] * CS, 1)
    f, b = s.contracts.VF, s.books.VB
    book_floor = np.maximum(f.Book, 1e-12)
    for v in VENDORS:
        j = VEND_IX[v]
        row["Revenue_" + v] = f.Revenue[:, j]
        row["Margin_" + v] = b.Margin[:, j]
        row["Vi_" + v] = f.Vi[:, j]
        row["Disc_" + v] = f.Disc[:, j]
        row["Power_" + v] = f.Power[:, j]
        row["PU_" + v] = f.PU[:, j]
        row["AvgIdx_" + v] = f.AvgIdx[:, j]
        row["SignRate_" + v] = b.SignRate[:, j]
        row["ExpRate_" + v] = f.ExpRate[:, j]
        row["SalesCost_" + v] = b.SalesCost[:, j]
        row["AICost_" + v] = f.AICost[:, j]
        row["VisaCost_" + v] = f.VisaCost[:, j]
        row["VLab_" + v] = f.VLab[:, j]
        row["LabRaw_" + v] = f.LabRaw[:, j]
        row["BaseRev_" + v] = f.BaseRev[:, j]
        row["VendDel_" + v] = f.VendDel[:, j]
        row["EffortShare_" + v] = b.EffortShare[:, j]
        row["VShare_" + v] = b.VShare[:, j]
        row["ShareLoss_" + v] = b.ShareLoss[:, j]
        row["VendorCost_" + v] = b.VendorCost[:, j]
        for k, kk in enumerate(TYPES):
            row[f"Mix_{v}_{kk}"] = (st.Leg[:, j, k] + st.NewV[:, j, k]) / book_floor[:, j]
            row[f"Sign_{v}_{kk}"] = b.TypeShare[:, j, k]
        row["AvgNewDur_" + v] = csum_axis(b.TypeShare[:, j, :] * f.Dnew[:, j, :], 1)
        row["Overhead_" + v] = st.Overhead[:, j]
    for i, x in enumerate(SECTORS):
        row["Dem_" + x] = csum_axis(Demand[:, i, :], 1)
        row["AC_" + x] = st.AC[:, i]
        row["LOB_" + x] = st.LOB[:, i]
        row["Committed_" + x] = cons.Committed[:, i]
        row["Budget_" + x] = cons.Budget[:, i]
        row["CompS_" + x] = CompS[:, i]
        row["WorkCheck_" + x] = st.IHW[:, i] + st.GCCW[:, i] + csum_axis(st.VW[:, i, :], 1)
        for j, e in enumerate(EMPLOYERS):
            row[f"Src_{x}_{e}"] = EmpShare[:, i, j]
            row[f"SrcT_{x}_{e}"] = SrcTarget[:, i, j]
    for k, w in enumerate(WTYPES):
        row["Dem_" + w] = csum_axis(Demand[:, :, k], 1)
    UnempRate = s.unemp.UnempRate
    for i, r in enumerate(REGIONS):
        row["Unemp_" + r] = UnempRate[:, i]
        row["HeadLoc_" + r] = csum(H[:, u, l] for u in range(len(UNITS)) if LOC_MASK[i, u] for l in range(len(LEVELS)))
        for j, l in enumerate(LEVELS):
            row[f"TTF_{r}_{l}"] = TTFr[:, i, j]
    row["HeadTotal"] = csum_axis(H.reshape(n, -1), 1)
    row["VendorHead"] = csum(row["Head_" + v] for v in VENDORS)
    row["Q1_ConsOnshore"] = row["H_IH"]
    row["Q1_ConsIndia"] = row["H_GCC"]
    row["Q1_VendOnshore"] = row["H_OV"] + row["H_OL"] + row["H_SI_ON"] + row["H_BQ"]
    row["Q1_VendIndia"] = row["H_VI"] + row["H_SI_IN"]
    row["LOB"] = csum_axis(st.LOB, 1)
    row["Committed"] = csum_axis(cons.Committed, 1)
    row["Budget"] = csum_axis(cons.Budget, 1)
    check = np.stack([np.abs(row["WorkCheck_" + x] - 1) for x in SECTORS], axis=1)
    row["WorkCheckMax"] = np.max(check, axis=1)
    return row


def _row_keys() -> tuple[str, ...]:
    """The 317 row keys in the order ``record`` (and ``aisim.scalar.record.record``) builds them."""
    keys = ["year", "P_all", "Demand", "Completion", "Backlog", "VisaTight", "ServicesSpend", "RevenueTot", "ConsIT"]
    keys += ["Grad_total", "Ext_total", "G", "Att", "A_mean", "HireJ_IN", "HireJ_ON", "AC_mean"]
    for u in UNITS:
        keys += ["H_" + u, "LabCost_" + u, "Del_" + u]
    for e in EMPLOYERS:
        keys += [p + e for p in ("Head_", "A_", "P_", "Cost_", "CompE_", "LabPB_", "WorkShare_")]
    vendor_families: tuple[str, ...] = (
        "Revenue_",
        "Margin_",
        "Vi_",
        "Disc_",
        "Power_",
        "PU_",
        "AvgIdx_",
        "SignRate_",
        "ExpRate_",
    )
    vendor_families += ("SalesCost_", "AICost_", "VisaCost_", "VLab_", "LabRaw_", "BaseRev_", "VendDel_")
    vendor_families += ("EffortShare_", "VShare_", "ShareLoss_", "VendorCost_")
    for v in VENDORS:
        keys += [p + v for p in vendor_families]
        for k in TYPES:
            keys += [f"Mix_{v}_{k}", f"Sign_{v}_{k}"]
        keys += ["AvgNewDur_" + v, "Overhead_" + v]
    for x in SECTORS:
        keys += [p + x for p in ("Dem_", "AC_", "LOB_", "Committed_", "Budget_", "CompS_", "WorkCheck_")]
        for e in EMPLOYERS:
            keys += [f"Src_{x}_{e}", f"SrcT_{x}_{e}"]
    keys += ["Dem_" + w for w in WTYPES]
    for r in REGIONS:
        keys += ["Unemp_" + r, "HeadLoc_" + r] + [f"TTF_{r}_{l}" for l in LEVELS]
    keys += ["HeadTotal", "VendorHead", "Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia"]
    keys += ["LOB", "Committed", "Budget", "WorkCheckMax"]
    return tuple(keys)


ROW_KEYS: Final = _row_keys()
"""The 317 row keys, in row order."""


def record_extras(st: BatchState, s: Step) -> dict[str, F]:
    """Return the extras of every run (``EXTRA_KEYS``) for the step whose intermediates are ``s``."""
    f, b = s.contracts.VF, s.books.VB
    out: dict[str, F] = {}
    for v in VENDORS:
        j = VEND_IX[v]
        for k, kk in enumerate(TYPES):
            out[f"Book_{v}_{kk}"] = st.Leg[:, j, k] + st.NewV[:, j, k]
    for v in VENDORS:
        j = VEND_IX[v]
        for k, kk in enumerate(TYPES):
            out[f"SignVol_{v}_{kk}"] = b.Sign[:, j, k]
    for v in VENDORS:
        j = VEND_IX[v]
        for k, kk in enumerate(TYPES):
            out[f"Dnew_{v}_{kk}"] = f.Dnew[:, j, k]
    for v in VENDORS:
        j = VEND_IX[v]
        for k, kk in enumerate(TYPES):
            out[f"PNew_{v}_{kk}"] = f.PNew[:, j, k]
    for i, r in enumerate(REGIONS):
        out["LeftField_" + r] = st.LeftField[:, i]
    cons = s.consumer.cons
    for i, x in enumerate(SECTORS):
        out["SeatSpend_" + x] = cons.SeatSpend[:, i]
    for i, x in enumerate(SECTORS):
        out["CreditSpend_" + x] = cons.CreditSpend[:, i]
    for i, x in enumerate(SECTORS):
        out["CloudSpend_" + x] = cons.CloudSpend[:, i]
    for i, u in enumerate(UNITS):
        out["WI_" + u] = st.WI[:, i]
    for e in EMPLOYERS:
        out["CapE_" + e] = s.work.CapE[:, EMP_IX[e]]
    opt = s.options
    for v in VENDORS:
        out["Vrel_" + v] = opt.Vrel[:, VEND_IX[v]]
    for v in VENDORS:
        out["ClientFlight_" + v] = opt.ClientFlight[:, VEND_IX[v]]
    out["GCCScaleTerm"] = s.targets.GCCScaleTerm
    for v in VENDORS:
        out["VoluntaryAttrition_" + v] = b.VolAttr[:, VEND_IX[v]]
    return out


EXTRA_KEYS: Final = scalar_extra_keys
"""The 106 extras keys, in ``record_extras`` order (the scalar engine's ``EXTRA_KEYS``)."""
