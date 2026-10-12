"""Validation of an experiment's inputs, before any run starts.

``validate`` checks the fixed parameters, the table overrides and the realised values of the sampled levers, and
raises one ``ValidationError`` listing every violation. Rules (recon 04 B1-B3; all paths under ``src/aisim/scalar/``):

1. **Domains.** Every scalar and table entry against its bounds in ``domains.csv``. Values must be finite, except a
   ``DemandGrowthLate`` of None (NaN in a batch).
2. **No-effect overrides.** Overriding or sampling a parameter with ``read = false`` (never read by ``run()``), or
   overriding a ``Mix0`` or ``Src0`` table entry.
3. **Derived parameters.** ``AdoptC0`` is recomputed from ``pC``, ``qC`` and ``AC0``; setting it directly raises.
4. **Joint constraints** (B3 A, B, D, E):

   - ordered pairs, start <= end (equality allowed), ``WageMin <= 1 <= WageMax`` and ``LateYear >= 2024``;
   - parameter-only denominators and power bases that involve more than one value;
   - ``Share0_J + Share0_M + Share0_S = 1`` and the ``SectorShare``, ``WTMix`` and ``BuildMix`` sums, within 1e-9;
   - ``a2024 <= amax`` per work type and ``aL_2024 <= aL_max``;
   - ``BudgetShock = 1`` together with ``ReinvestFrac = 0`` (a zero budget).

   The single-value items of B3 are rule 1's domain classes: the power bases ``1 - g``, ``1 - VerifDecline``,
   ``1 - AICostDecline`` and ``1 + DemandGrowth`` (classes ``below_one`` and ``growth``); ``AICost2024``,
   ``CreditCost2024``, ``AIShockMult``, ``NormalUnempRate_r``, ``Wage_u``, ``PowerMin`` and ``Port0_x / AppLife``
   (``positive``); ``1 + PriceHorizon x PU`` and ``1 + DurPUSens x PU`` (``non_negative``, with PU >= 0); ``VTBase``,
   ``VTEnd`` and the other products of B3 E (``unit_interval``); ``JevonsCap >= 1`` (C10, its lower bound).
5. **Calibration identities** (B3 C), against the initial state in use, within 1e-9 (relative, absolute floor 1e-9):
   ``AC0``, ``A0``, ``VTBase``, ``NormalUnempRate_r``, ``NormalMargin_v``, ``LOB0_x``, ``Port0_x`` and ``Seats0_x``
   equal their stocks. C8 holds at its calibrated residual: the shipped ``CostPerBFY0`` and ``LabourCostPB0_e`` are
   rounded (2e-5 to 8e-5 off the 2024 values), so the 2024 ratios ``(ServicesSpend / Completion) / CostPerBFY0`` and
   ``LabPB_e / LabourCostPB0_e``, from a one-step ``run_batch``, must equal the baseline's within 1e-9. C1
   (``AdoptC0``) is rule 3.
6. **Time constants against dt** (B3 F): smoothing times and "no faster than" floors >= dt; each outflow rate (a
   rate a year, or 1 / an outflow time) times dt < 1. This rule rejects ``TargetClearanceTime = 1e-6`` (B2).
7. **Sampled levers.** ``support_violations`` checks each distribution's support against the lever's domain before
   drawing (``check_support``); rules 1-6 then run on every run's realised values.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from typing import Any, Final

import numpy as np
import pandas as pd

from aisim.batch.engine import run_batch
from aisim.batch.state import BatchState, pack
from aisim.batch.util import B, F
from aisim.dims import EMPLOYERS, LEVELS, REGIONS, SECTORS, VENDORS, WTYPES
from aisim.experiment.inputs import DGL, batch_arrays, make_batch_params
from aisim.experiment.metadata import domains
from aisim.experiment.sampling import Distribution, support_violations
from aisim.params import Params
from aisim.state import State, load_initial_state

TOL: Final = 1e-9
MAX_RUNS_SHOWN: Final = 10

SMOOTHING_TIMES: Final = (
    "PerceptionTime",
    "OnboardTime",
    "RecoveryTime",
    "UnempPerceptionTime",
    "StudentPerceptionTime",
    "TightPerceptionTime",
    "OverheadAdjTime",
    "ClientPerceptionTime",
    "ViabilityTime",
    "CostProgramTime",
    "WageAdjTime",
    "TrendTime",
    "SrcPerceptionTime",
    "ShareRefTime",
    "DiscAdjTime",
    "LOBAdjTime",
    "SeatAdjTime",
    "CostPerceptionTime",
    "BudgetCycle",
    "TargetClearanceTime",
    "HireAdjTime",
    "LayoffAdjTime",
)
"""First-order delays and adjustment times (B1 "first-order delay"; the gap-closing times of S3 and S8): >= dt."""

FLOORS: Final = ("MinCompletionTime", "MinLayoffTime", "MinAdoptionTime", "PromoFillTime", "MinFillTime", "MinDur")
"""The "no faster than" floors (B1 "rate cap") and the new-contract duration floor: >= dt."""

OUTFLOW_RATES: Final = (
    "QuitRate_J",
    "QuitRate_M",
    "QuitRate_S",
    "LeaveITRate_J",
    "LeaveITRate_M",
    "LeaveITRate_S",
    "RetireRate_S",
    "SeekerExitRate",
    "ConvRate",
    "SwitchRate",
)
"""Outflows given as a rate a year on a stock: rate x dt < 1."""

OUTFLOW_TIMES: Final = (
    "AbandonTime",
    "CancelTime",
    "TimeInJunior",
    "TimeInMid",
    "VisaTenure",
    "StudyTime",
    "AppLife",
    "IHReviewTime",
    "GCCReviewTime",
    "BaseDur_FP",
    "BaseDur_TM",
    "BaseDur_MS",
    "BaseDur_SA",
    "BaseDur_OB",
)
"""Outflows given as a stock over a time: (1 / time) x dt < 1."""

ORDERED: Final = (
    ("VTRampStart", "VTRampEnd", "workforce.py:79"),
    ("RegStart", "RegEnd", "consumer.py:98"),
    ("CyberStart", "CyberRampEnd", "consumer.py:99"),
    ("GCCRampStart", "GCCRampEnd", "consumer.py:112"),
    ("GCCRampEnd", "GCCFadeEnd", "consumer.py:113-114"),
    ("AIShockStart", "AIShockEnd", "finance.py:132"),
    ("BudgetShockStart", "BudgetShockEnd", "consumer.py:108"),
    ("WageMin", "WageMax", "finance.py:336"),
    ("PowerMin", "PowerMax", "finance.py:178"),
    ("CEMin", "CEMax", "adoption.py:57-58"),
)
"""Ordered pairs (B3 A): first <= second, equality allowed."""

FAMILIES: Final = (
    "domain",
    "no-effect",
    "derived",
    "ordered",
    "denominator",
    "sum",
    "table order",
    "budget",
    "calibration",
    "dt",
    "support",
)
"""The rule families, in report order."""


@dataclass(frozen=True, slots=True)
class Violation:
    """One broken rule: what (parameter, table entry or expression), the offending values or runs, rule, evidence."""

    family: str
    target: str
    value: str
    rule: str
    evidence: str

    def __str__(self) -> str:
        return f"[{self.family}] {self.target}: {self.value}; rule: {self.rule}; evidence: {self.evidence}"


class ValidationError(ValueError):
    """The experiment's inputs break one or more rules. ``violations`` lists every one."""

    def __init__(self, violations: Iterable[Violation]) -> None:
        self.violations = list(violations)
        lines = "\n".join(f"  {v}" for v in self.violations)
        super().__init__(f"{len(self.violations)} validation violation(s):\n{lines}")


class _Values:
    """Per-run values of every scalar: fixed values broadcast, sampled values as given (NaN for a None)."""

    def __init__(self, params: Params, sampled: Mapping[str, F]) -> None:
        self.params = params
        self.sampled = {k: np.asarray(v, dtype=np.float64) for k, v in sampled.items()}
        self.n = len(next(iter(self.sampled.values()))) if self.sampled else 1

    def __getitem__(self, name: str) -> F:
        if name in self.sampled:
            return self.sampled[name]
        v = self.params.scalars[name]
        return np.full(self.n, np.nan if v is None else v)

    def table(self, name: str) -> dict[str, float]:
        return self.params.table(name)

    def describe(self, names: Iterable[str], bad: B) -> str:
        """The offending values (fixed) or run indices (when any of ``names`` is sampled)."""
        names = list(names)
        idx = np.flatnonzero(bad)
        if any(n in self.sampled for n in names):
            shown = ", ".join(str(int(i)) for i in idx[:MAX_RUNS_SHOWN])
            more = ", ..." if idx.size > MAX_RUNS_SHOWN else ""
            first = int(idx[0])
            vals = ", ".join(f"{n}={float(self[n][first])!r}" for n in names)
            return f"runs [{shown}{more}] ({idx.size} of {self.n}; run {first}: {vals})"
        return ", ".join(f"{n}={float(self[n][0])!r}" for n in names) or "fixed"


def _out_of_bounds(x: F, lower: float, lower_inc: bool, upper: float, upper_inc: bool) -> B:
    bad = np.zeros(x.shape, dtype=np.bool_)
    if not math.isnan(lower):
        bad |= (x < lower) | ((x == lower) & (not lower_inc))
    if not math.isnan(upper):
        bad |= (x > upper) | ((x == upper) & (not upper_inc))
    return bad


def _bounds_text(domain: str, lower: float, lower_inc: bool, upper: float, upper_inc: bool) -> str:
    lo = "-inf" if math.isnan(lower) else f"{lower:g}"
    hi = "inf" if math.isnan(upper) else f"{upper:g}"
    left = "[" if lower_inc and not math.isnan(lower) else "("
    right = "]" if upper_inc and not math.isnan(upper) else ")"
    return f"domain {domain}: {left}{lo}, {hi}{right}"


@dataclass(frozen=True, slots=True)
class _DomainRow:
    name: str
    domain: str
    lower: float
    lower_inc: bool
    upper: float
    upper_inc: bool
    evidence: str
    read: bool


@cache
def _domain_rows() -> tuple[_DomainRow, ...]:
    out = []
    # Any: a record of the domains table; the nullable booleans are pd.NA where there is no bound.
    rec: dict[Any, Any]
    for rec in domains().to_dict("records"):
        li, ui = rec["lower_inclusive"], rec["upper_inclusive"]
        out.append(
            _DomainRow(
                name=str(rec["name"]),
                domain=str(rec["domain"]),
                lower=float(rec["lower"]),
                lower_inc=True if pd.isna(li) else bool(li),
                upper=float(rec["upper"]),
                upper_inc=True if pd.isna(ui) else bool(ui),
                evidence=str(rec["evidence"]),
                read=bool(rec["read"]),
            )
        )
    return tuple(out)


def domain_of(name: str) -> _DomainRow:
    """The ``domains.csv`` row of a scalar or table entry. Raises ``KeyError`` for an unknown name."""
    for row in _domain_rows():
        if row.name == name:
            return row
    raise KeyError(name)


def _table_entry(params: Params, name: str) -> float:
    """The value of a table entry named like ``SpeedUp[APP]`` or ``Mix0[OIT][TM]``."""
    table, _, rest = name.partition("[")
    keys = rest.rstrip("]").split("][")
    # Any: a one- or two-dimensional table, walked by key.
    node: Any = params.tables[table]
    for k in keys:
        node = node[k]
    return float(node)


def check_support(sample: Mapping[str, Distribution]) -> None:
    """Rule 7, before drawing: each distribution's support lies in its lever's domain. Raises ``ValidationError``."""
    out = []
    for name, dist in sample.items():
        row = domain_of(name)
        why = support_violations(dist, row.lower, row.lower_inc, row.upper, row.upper_inc)
        if why is not None:
            out.append(
                Violation(
                    "support",
                    name,
                    f"{dist!r}: {why}",
                    _bounds_text(row.domain, row.lower, row.lower_inc, row.upper, row.upper_inc),
                    row.evidence,
                )
            )
    if out:
        raise ValidationError(out)


def validate(
    params: Params,
    *,
    init: State | None = None,
    dt: float = 1 / 16,
    overrides: Mapping[str, float | None] | None = None,
    tables: Mapping[str, Mapping[str, Any]] | None = None,
    sampled: Mapping[str, F] | None = None,
) -> None:
    """Check ``params`` (the fixed parameters, overrides and tables applied) and the sampled values. Raises
    ``ValidationError`` listing every violation.

    - ``init``: the initial state in use (default: the calibrated 2024 state).
    - ``overrides``: the scalar names set on top of the baseline (scenario and overrides), for rules 2 and 3.
    - ``tables``: the table overrides (name to values), for rule 2.
    - ``sampled``: the realised value of each sampled lever per run, as ``(N,)`` arrays (NaN for a None
      ``DemandGrowthLate``).

    ``Any``: a table override is one- or two-dimensional.
    """
    st = load_initial_state() if init is None else init
    v = _Values(params, sampled or {})
    out: list[Violation] = []
    out += _domain_violations(v)
    out += _no_effect_violations(v, overrides or {}, tables or {})
    out += _joint_violations(v, st)
    out += _calibration_violations(v, st, dt)
    out += _dt_violations(v, dt)
    if out:
        out.sort(key=lambda x: FAMILIES.index(x.family))
        raise ValidationError(out)


# ---- 1. domains ------------------------------------------------------------------------------------------------------


def _domain_violations(v: _Values) -> list[Violation]:
    out = []
    for row in _domain_rows():
        bounds = _bounds_text(row.domain, row.lower, row.lower_inc, row.upper, row.upper_inc)
        if "[" in row.name:
            x = np.array([_table_entry(v.params, row.name)])
            names: list[str] = []
        else:
            x = v[row.name]
            names = [row.name]
        allowed_nan = np.isnan(x) if row.name == DGL else np.zeros(x.shape, dtype=np.bool_)
        nonfinite = ~np.isfinite(x) & ~allowed_nan
        bad = nonfinite | (_out_of_bounds(x, row.lower, row.lower_inc, row.upper, row.upper_inc) & ~allowed_nan)
        if bad.any():
            value = v.describe(names, bad) if names else f"{row.name}={x[0]!r}"
            rule = bounds + (" (and finite)" if nonfinite.any() else "")
            out.append(Violation("domain", row.name, value, rule, row.evidence))
    return out


# ---- 2, 3. no-effect and derived overrides ---------------------------------------------------------------------------


def _no_effect_violations(
    v: _Values, overrides: Mapping[str, float | None], tables: Mapping[str, Mapping[str, Any]]
) -> list[Violation]:
    out = []
    unread = {row.name: row for row in _domain_rows() if not row.read and "[" not in row.name}
    for name in [*overrides, *v.sampled]:
        if name in unread:
            how = "sampled" if name in v.sampled else f"overridden to {overrides[name]!r}"
            out.append(
                Violation(
                    "no-effect",
                    name,
                    how,
                    "run() never reads this parameter: the override has no effect",
                    unread[name].evidence or "recon 04 B1 (never read)",
                )
            )
        if name == "AdoptC0":
            how = "sampled" if name in v.sampled else f"overridden to {overrides[name]!r}"
            out.append(
                Violation(
                    "derived",
                    name,
                    how,
                    "AdoptC0 is derived, (pC + qC * AC0) * (1 - AC0), and recomputed when pC, qC or AC0 changes",
                    "src/aisim/params.py:95-97; recon 04 B3 C1",
                )
            )
    for table in tables:
        if table in ("Mix0", "Src0"):
            out.append(
                Violation(
                    "no-effect",
                    table,
                    "table overridden",
                    f"run() never reads {table} (it only describes the 2024 state): the override has no effect",
                    "src/aisim/scalar/engine.py:71-72 (TABLES_1D); recon 04 B1",
                )
            )
    return out


# ---- 4. joint constraints --------------------------------------------------------------------------------------------


def _joint_violations(v: _Values, st: State) -> list[Violation]:
    out: list[Violation] = []

    def check(family: str, target: str, names: Iterable[str], bad: B, rule: str, evidence: str) -> None:
        if bad.any():
            out.append(Violation(family, target, v.describe(names, bad), rule, evidence))

    for a, b, cite in ORDERED:
        check("ordered", f"{a} <= {b}", (a, b), ~(v[a] <= v[b]), "start <= end (equality allowed)", cite)
    check("ordered", "WageMin <= 1", ("WageMin",), ~(v["WageMin"] <= 1), "WageMin <= 1 <= WageMax", "finance.py:336")
    check("ordered", "1 <= WageMax", ("WageMax",), ~(v["WageMax"] >= 1), "WageMin <= 1 <= WageMax", "finance.py:336")
    check(
        "ordered",
        "LateYear >= 2024",
        ("LateYear",),
        ~(v["LateYear"] >= 2024),
        "LateYear is in the run window (not before 2024)",
        "capability.py:57",
    )

    m, s = v["Share0_M"], v["Share0_S"]
    check("denominator", "Share0_M + Share0_S > 0", ("Share0_M", "Share0_S"), ~(m + s > 0), "> 0", "workforce.py:61-62")
    a2024, amax, speed_up = v.table("a2024"), v.table("amax"), v.table("SpeedUp")
    verif, A0 = v["Verif"], v["A0"]
    for w in WTYPES:
        aw, am, su = np.float64(a2024[w]), np.float64(amax[w]), np.float64(speed_up[w])
        with np.errstate(divide="ignore", invalid="ignore"):
            den0 = (1 - aw) + aw / su + aw * verif
        check(
            "denominator",
            f"PAI0 denominator [{w}]",
            ("Verif",),
            ~(den0 > 0),
            "(1 - a2024) + a2024 / SpeedUp + a2024 * Verif > 0",
            "capability.py:54",
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            lowest = np.minimum.reduce([(1 - a) + a / su + a * vv for a in (aw, am) for vv in (verif * 0.0, verif)])
        check(
            "denominator",
            f"PAI denominator [{w}]",
            ("Verif",),
            ~(lowest > 0),
            "(1 - aW) + aW / SpeedUp + aW * VerifNow > 0 for aW in [a2024, amax], VerifNow in [0, Verif]",
            "capability.py:53",
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            pai0 = 1 / den0
        check(
            "denominator",
            f"A0 * PAI0 + (1 - A0) [{w}]",
            ("A0", "Verif"),
            ~(A0 * pai0 + (1 - A0) > 0),
            "> 0",
            "capability.py:60",
        )
    weights = {lv: v["W_" + lv] for lv in LEVELS}
    sJ0 = v["Share0_J"]
    rest0 = m + s
    with np.errstate(divide="ignore", invalid="ignore"):
        lows = []
        for sJ in (sJ0, 0.05 * sJ0):
            lows.append(sJ * weights["J"] + m * (1 - sJ) / rest0 * weights["M"] + s * (1 - sJ) / rest0 * weights["S"])
    check(
        "denominator",
        "denomE, AvgW > 0",
        ("W_J", "W_M", "W_S", "Share0_J", "Share0_M", "Share0_S"),
        ~((lows[0] > 0) & (lows[1] > 0)),
        "level-weighted staff per head > 0 at the 2024 and the floor junior share",
        "workforce.py:63, 96",
    )
    pp = min(st["PerceivedP"].values())
    check(
        "denominator",
        "TargetClearanceTime * WorkPerPerson * PerceivedP > 0",
        ("TargetClearanceTime", "WorkPerPerson"),
        ~(v["TargetClearanceTime"] * v["WorkPerPerson"] * pp > 0),
        "> 0",
        "workforce.py:94",
    )
    if st["CostPerc"] <= 0:
        check(
            "denominator",
            "CostPerc > 0 when JevonsEps > 0",
            ("JevonsEps",),
            v["JevonsEps"] > 0,
            "the initial CostPerc is a power base",
            "consumer.py:103",
        )

    total = v["Share0_J"] + m + s
    check(
        "sum",
        "Share0_J + Share0_M + Share0_S = 1",
        ("Share0_J", "Share0_M", "Share0_S"),
        ~(np.abs(total - 1) <= TOL),
        f"sum = 1 within {TOL:g}",
        "workforce.py:60-62; recon 04 B3 C9",
    )
    for table in ("SectorShare", "WTMix", "BuildMix"):
        t = v.table(table)
        tot = sum(t.values())
        if not abs(tot - 1) <= TOL:
            out.append(Violation("sum", f"sum of {table}", f"sum={tot!r}", f"sum = 1 within {TOL:g}", "recon 04 B3 D"))
    for w in WTYPES:
        if not a2024[w] <= amax[w]:
            out.append(
                Violation(
                    "table order",
                    f"a2024[{w}] <= amax[{w}]",
                    f"a2024={a2024[w]!r}, amax={amax[w]!r}",
                    "<=",
                    "capability.py:50",
                )
            )
    check(
        "table order",
        "aL_2024 <= aL_max",
        ("aL_2024", "aL_max"),
        ~(v["aL_2024"] <= v["aL_max"]),
        "<=",
        "consumer.py:95",
    )
    check(
        "budget",
        "BudgetShock = 1 with ReinvestFrac = 0",
        ("BudgetShock", "ReinvestFrac"),
        (v["BudgetShock"] >= 1) & (v["ReinvestFrac"] == 0),
        "the shocked budget would be 0 (a divisor)",
        "consumer.py:105-108; integrate.py:40",
    )
    return out


# ---- 5. calibration identities ---------------------------------------------------------------------------------------


def _close(a: F, b: float | F) -> B:
    out: B = np.abs(a - b) <= np.maximum(TOL * np.abs(b), TOL)
    return out


def _calibration_violations(v: _Values, st: State, dt: float) -> list[Violation]:
    out: list[Violation] = []

    def ident(name: str, stocks: Mapping[str, float], cite: str) -> None:
        """``name`` equals every one of ``stocks`` (initial-state values by label); one violation per name."""
        x = v[name]
        failing = {label: value for label, value in stocks.items() if (~_close(x, value)).any()}
        if failing:
            bad = np.logical_or.reduce([~_close(x, value) for value in failing.values()])
            against = ", ".join(f"{label}={value!r}" for label, value in failing.items())
            out.append(
                Violation(
                    "calibration",
                    f"{name} = {', '.join(failing)}",
                    v.describe([name], bad) + f" vs {against}",
                    f"equals the initial stock within {TOL:g}",
                    cite,
                )
            )

    ident("AC0", {f"AC[{x}]": st["AC"][x] for x in SECTORS}, "consumer.py:168; recon 04 B3 C2")
    ident("A0", {f"A[{e}]": st["A"][e] for e in EMPLOYERS}, "capability.py:60; workforce.py:60; recon 04 B3 C3")
    ident("VTBase", {"TightPerc": st["TightPerc"]}, "workforce.py:80; recon 04 B3 C4")
    for r in REGIONS:
        pools = {f"PUS[{r}]": st["PUS"][r], f"PUL[{r}]": st["PUL"][r]}
        ident(f"NormalUnempRate_{r}", pools, "labour_market.py:121; finance.py:333; recon 04 B3 C5")
    for vv in VENDORS:
        ident(f"NormalMargin_{vv}", {f"Viab[{vv}]": st["Viab"][vv]}, "finance.py:171; recon 04 B3 C6")
    for x in SECTORS:
        ident(f"LOB0_{x}", {f"LOB[{x}]": st["LOB"][x]}, "consumer.py:169; recon 04 B3 C7")
        ident(f"Port0_{x}", {f"Port[{x}]": st["Port"][x]}, "consumer.py:177; recon 04 B3 C7")
        ident(f"Seats0_{x}", {f"SeatsB[{x}]": st["SeatsB"][x]}, "consumer.py:198; recon 04 B3 C7")
    out += _c8_violations(v, st, dt)
    return out


C8_KEYS: Final = ("ServicesSpend", "Completion", *(f"LabPB_{e}" for e in EMPLOYERS))


def _c8_ratios(series: Mapping[str, F], scalars: Mapping[str, F]) -> dict[str, F]:
    """The 2024 ratios of C8 (consumer.py:102, adoption.py:56): spend per BFY and labour cost per staff over their
    calibrated parameters."""
    out = {"CostPerBFY0": (series["ServicesSpend"][:, 0] / np.maximum(series["Completion"][:, 0], 1e-9))}
    out["CostPerBFY0"] = out["CostPerBFY0"] / scalars["CostPerBFY0"]
    for e in EMPLOYERS:
        out[f"LabourCostPB0_{e}"] = series[f"LabPB_{e}"][:, 0] / scalars[f"LabourCostPB0_{e}"]
    return out


C8_BLOCK: Final = 2000
"""Runs per one-step batch in the C8 check: a step's intermediates for every run at once would dominate memory."""


def _one_step(params: Params, sampled: Mapping[str, F], n: int, st: State, dt: float) -> dict[str, F]:
    one = pack([st])
    parts: list[dict[str, F]] = []
    for lo in range(0, n, C8_BLOCK):
        hi = min(lo + C8_BLOCK, n)
        scalars, tables, dgl = batch_arrays(params, {k: a[lo:hi] for k, a in sampled.items()}, hi - lo)
        bp = make_batch_params(scalars, tables, dgl)
        init = BatchState(**{k: np.repeat(a, hi - lo, axis=0) for k, a in one.arrays().items()})
        res = run_batch(bp, init, dt=dt, stop=0.0, outputs=C8_KEYS)
        parts.append(_c8_ratios(res.series, bp.scalars))
    return {k: np.concatenate([part[k] for part in parts]) for k in parts[0]}


@cache
def _c8_baseline() -> dict[str, float]:
    ratios = _one_step(Params.baseline(), {}, 1, load_initial_state(), 1 / 16)
    return {k: float(a[0]) for k, a in ratios.items()}


def _c8_violations(v: _Values, st: State, dt: float) -> list[Violation]:
    ratios = _one_step(v.params, v.sampled, v.n, st, dt)
    base = _c8_baseline()
    out = []
    for name, r in ratios.items():
        bad = ~(np.abs(r - base[name]) <= TOL * abs(base[name]))
        if bad.any():
            what = "2024 services spend per BFY" if name == "CostPerBFY0" else "2024 labour cost per effective staff"
            first = int(np.flatnonzero(bad)[0])
            value = v.describe([name], bad) + f"; ratio {float(r[first])!r} vs calibrated {base[name]!r}"
            out.append(
                Violation(
                    "calibration",
                    f"{name} = {what}",
                    value,
                    f"the 2024 ratio stays at its calibrated value within {TOL:g} (relative)",
                    "consumer.py:102; adoption.py:56; recon 04 B3 C8",
                )
            )
    return out


# ---- 6. time constants against dt ------------------------------------------------------------------------------------


def _dt_violations(v: _Values, dt: float) -> list[Violation]:
    out: list[Violation] = []

    def check(names: Iterable[str], bad_of: Callable[[F], B], rule: str, evidence: str) -> None:
        for name in names:
            bad = bad_of(v[name])
            if bad.any():
                out.append(Violation("dt", name, v.describe([name], bad), rule, evidence))

    check(SMOOTHING_TIMES, lambda x: ~(x >= dt), f"smoothing time >= dt = {dt:g}", "recon 04 B3 F")
    check(FLOORS, lambda x: ~(x >= dt), f"'no faster than' floor >= dt = {dt:g}", "recon 04 B3 F")
    check(OUTFLOW_RATES, lambda x: ~(x * dt < 1), f"outflow rate x dt < 1 (dt = {dt:g})", "recon 04 B3 F")
    check(OUTFLOW_TIMES, lambda x: ~(dt / x < 1), f"outflow rate 1 / time x dt < 1 (dt = {dt:g})", "recon 04 B3 F")
    return out
