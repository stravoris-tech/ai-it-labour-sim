"""Output rows: 317 keys, named and ordered exactly as the prototype's.

Prototype: ``phase7_sim.py`` REC, lines 497-545. The row is built from the state before the step's integration and the
step's intermediates. Key families (recon D1): 21 scalars; ``HireJ_`` by region; ``H_``, ``LabCost_``, ``Del_`` by
unit; ``Head_``, ``A_``, ``P_``, ``Cost_``, ``CompE_``, ``LabPB_``, ``WorkShare_`` by employer; 20 vendor families plus
``AvgNewDur_`` and ``Overhead_``; ``Mix_`` and ``Sign_`` by vendor and type; ``Dem_`` by sector and by work type;
``AC_``, ``LOB_``, ``Committed_``, ``Budget_``, ``CompS_``, ``WorkCheck_`` by sector; ``Src_`` and ``SrcT_`` by sector
and employer; ``Unemp_``, ``HeadLoc_`` and ``TTF_`` by region; and the four ``Q1_`` lines.

``record_extras`` records the extras (``EXTRA_KEYS``): outputs the prototype does not record but the step already holds,
kept apart from the rows so that the rows stay the prototype's. Each is a value read from the state or an intermediate,
never a new calculation:

- ``Book_{v}_{k}``: the contract book by vendor and type, ``Leg + NewV`` (finance.py:180-181, the numerator of
  ``Mix_``). Spec 00:89 names these stocks contract value in USD; the calibrated state normalises each vendor's 2024
  book to 1, so the unit is book volume (vendor 2024 book = 1), not USD.
- ``SignVol_{v}_{k}``: new signings by vendor and type, S11b ``Sign[k]`` (finance.py:293), book volume per year.
- ``Dnew_{v}_{k}``: the new-contract duration by vendor and type, S10 ``Dnew[k]`` (finance.py:183-186), years.
- ``PNew_{v}_{k}``: the new-signing price by vendor and type, S10 ``PNew[k]`` (finance.py:225-228), price per unit
  of book volume (2024 = 1).
- ``LeftField_{r}``: people who left the IT field, by region (state ``LeftField``), model-unit persons.
- ``SeatSpend_{x}``, ``CreditSpend_{x}``, ``CloudSpend_{x}``: the seat, credit and cloud parts of consumer spend by
  sector, S13c (consumer.py:172, 182, 183), USD per year.
- ``WI_{u}``: the wage index by unit (state ``WI``), 2024 = 1.
- ``CapE_{e}``: delivery capacity by employer, S3 ``CapE`` (work.py:70), BFY per year.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from aisim.dims import EMP_OF, EMPLOYERS, LEVELS, LOC, POOL, REGIONS, SECTORS, TYPES, UNITS, VENDORS, WTYPES
from aisim.scalar.step import Step
from aisim.state import State


def record(st: State, s: Step, SectorShare: Mapping[str, float]) -> dict[str, float]:
    """Return the output row for the step whose intermediates are ``s``.

    ``LabPB_e`` is S12's ``labpb[e]``: the prototype recomputes it here with the identical expression.
    """
    Aemp, H = st["A"], st["H"]
    work = s.work
    CompE, Completion, EmpShare, CS, CompS = work.CompE, work.Completion, work.EmpShare, work.CS, work.CompS
    LabourCost, Delivered = s.costs.LabourCost, s.costs.Delivered
    hires = s.hiring.hires
    ext, TTFr = s.ttf.ext, s.ttf.TTFr
    cons, Demand = s.consumer.cons, s.consumer.Demand
    CostOpt = s.options.CostOpt
    SrcTarget = s.targets.SrcTarget
    row: dict[str, float] = {
        "year": round(s.y, 4),
        "P_all": work.P_all,
        "Demand": s.consumer.DemandTot,
        "Completion": Completion,
        "Backlog": work.TotBL,
        "VisaTight": s.staffing.VisaTight,
        "ServicesSpend": s.spend.ServicesSpend,
        "RevenueTot": s.spend.RevenueTot,
        "ConsIT": s.drivers.ConsIT,
        "Grad_total": sum(s.pools.Grad.values()),
        "Ext_total": sum(ext[r][l] for r in REGIONS for l in LEVELS),
        "G": s.cap.G,
        "Att": s.drivers.Att,
        "A_mean": sum(Aemp[e] * CompE[e] for e in EMPLOYERS) / max(Completion, 1e-9),
        "HireJ_IN": sum(hires[u]["J"] for u in UNITS if POOL[u] == "IN"),
        "HireJ_ON": sum(hires[u]["J"] for u in UNITS if POOL[u] == "ON"),
        "AC_mean": sum(st["AC"][x] * SectorShare[x] for x in SECTORS),
    }
    for u in UNITS:
        row["H_" + u] = sum(H[u][l] for l in LEVELS)
        row["LabCost_" + u] = LabourCost[u]
        row["Del_" + u] = Delivered[u]
    labpb = s.adoption.labpb
    for e in EMPLOYERS:
        row["Head_" + e] = sum(row["H_" + u] for u in UNITS if EMP_OF[u] == e)
        row["A_" + e] = Aemp[e]
        row["P_" + e] = work.Pe[e]
        row["Cost_" + e] = CostOpt[e]
        row["CompE_" + e] = CompE[e]
        row["LabPB_" + e] = labpb[e]
        row["WorkShare_" + e] = sum(EmpShare[x][e] * CS[x] for x in SECTORS)
    VF, VB = s.contracts.VF, s.books.VB
    for v in VENDORS:
        f, b = VF[v], VB[v]
        row["Revenue_" + v] = f.Revenue
        row["Margin_" + v] = b.Margin
        row["Vi_" + v] = f.Vi
        row["Disc_" + v] = f.Disc
        row["Power_" + v] = f.Power
        row["PU_" + v] = f.PU
        row["AvgIdx_" + v] = f.AvgIdx
        row["SignRate_" + v] = b.SignRate
        row["ExpRate_" + v] = f.ExpRate
        row["SalesCost_" + v] = b.SalesCost
        row["AICost_" + v] = f.AICost
        row["VisaCost_" + v] = f.VisaCost
        row["VLab_" + v] = f.VLab
        row["LabRaw_" + v] = f.LabRaw
        row["BaseRev_" + v] = f.BaseRev
        row["VendDel_" + v] = f.VendDel
        row["EffortShare_" + v] = b.EffortShare
        row["VShare_" + v] = b.VShare
        row["ShareLoss_" + v] = b.ShareLoss
        row["VendorCost_" + v] = b.VendorCost
        for k in TYPES:
            row[f"Mix_{v}_{k}"] = (st["Leg"][v][k] + st["NewV"][v][k]) / max(f.Book, 1e-12)
            row[f"Sign_{v}_{k}"] = b.TypeShare[k]
        row["AvgNewDur_" + v] = sum(b.TypeShare[k] * f.Dnew[k] for k in TYPES)
        row["Overhead_" + v] = st["Overhead"][v]
    for x in SECTORS:
        c = cons[x]
        row["Dem_" + x] = sum(Demand[x][w] for w in WTYPES)
        row["AC_" + x] = st["AC"][x]
        row["LOB_" + x] = st["LOB"][x]
        row["Committed_" + x] = c.Committed
        row["Budget_" + x] = c.Budget
        row["CompS_" + x] = CompS[x]
        row["WorkCheck_" + x] = st["IHW"][x] + st["GCCW"][x] + sum(st["VW"][x][v] for v in VENDORS)
        for e in EMPLOYERS:
            row[f"Src_{x}_{e}"] = EmpShare[x][e]
            row[f"SrcT_{x}_{e}"] = SrcTarget[x][e]
    for w in WTYPES:
        row["Dem_" + w] = sum(Demand[x][w] for x in SECTORS)
    UnempRate = s.unemp.UnempRate
    for r in REGIONS:
        row["Unemp_" + r] = UnempRate[r]
        row["HeadLoc_" + r] = sum(H[u][l] for u in UNITS if LOC[u] == r for l in LEVELS)
        for l in LEVELS:
            row[f"TTF_{r}_{l}"] = TTFr[r][l]
    row["HeadTotal"] = sum(H[u][l] for u in UNITS for l in LEVELS)
    row["VendorHead"] = sum(row["Head_" + v] for v in VENDORS)
    row["Q1_ConsOnshore"] = row["H_IH"]
    row["Q1_ConsIndia"] = row["H_GCC"]
    row["Q1_VendOnshore"] = row["H_OV"] + row["H_OL"] + row["H_SI_ON"] + row["H_BQ"]
    row["Q1_VendIndia"] = row["H_VI"] + row["H_SI_IN"]
    row["LOB"] = sum(st["LOB"][x] for x in SECTORS)
    row["Committed"] = sum(cons[x].Committed for x in SECTORS)
    row["Budget"] = sum(cons[x].Budget for x in SECTORS)
    row["WorkCheckMax"] = max(abs(row["WorkCheck_" + x] - 1) for x in SECTORS)
    return row


def record_extras(st: State, s: Step) -> dict[str, float]:
    """Return the extras (``EXTRA_KEYS``) for the step whose intermediates are ``s``, from the same state as the row."""
    VF, VB = s.contracts.VF, s.books.VB
    out: dict[str, float] = {}
    for v in VENDORS:
        for k in TYPES:
            out[f"Book_{v}_{k}"] = st["Leg"][v][k] + st["NewV"][v][k]
    for v in VENDORS:
        for k in TYPES:
            out[f"SignVol_{v}_{k}"] = VB[v].Sign[k]
    for v in VENDORS:
        for k in TYPES:
            out[f"Dnew_{v}_{k}"] = VF[v].Dnew[k]
    for v in VENDORS:
        for k in TYPES:
            out[f"PNew_{v}_{k}"] = VF[v].PNew[k]
    for r in REGIONS:
        out["LeftField_" + r] = st["LeftField"][r]
    cons = s.consumer.cons
    for x in SECTORS:
        out["SeatSpend_" + x] = cons[x].SeatSpend
    for x in SECTORS:
        out["CreditSpend_" + x] = cons[x].CreditSpend
    for x in SECTORS:
        out["CloudSpend_" + x] = cons[x].CloudSpend
    for u in UNITS:
        out["WI_" + u] = st["WI"][u]
    for e in EMPLOYERS:
        out["CapE_" + e] = s.work.CapE[e]
    return out


def _extra_keys() -> tuple[str, ...]:
    """The extras keys in the order ``record_extras`` builds them."""
    keys: list[str] = []
    for prefix in ("Book_", "SignVol_", "Dnew_", "PNew_"):
        keys += [f"{prefix}{v}_{k}" for v in VENDORS for k in TYPES]
    keys += ["LeftField_" + r for r in REGIONS]
    for prefix in ("SeatSpend_", "CreditSpend_", "CloudSpend_"):
        keys += [prefix + x for x in SECTORS]
    keys += ["WI_" + u for u in UNITS]
    keys += ["CapE_" + e for e in EMPLOYERS]
    return tuple(keys)


EXTRA_KEYS: Final = _extra_keys()
"""The 96 extras keys, in ``record_extras`` order."""
