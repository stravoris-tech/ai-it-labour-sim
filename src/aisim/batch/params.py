"""Parameters of a batch: every scalar as an ``(N,)`` array and every table as an ``(N, ...)`` array.

``BatchParams.stack`` builds a batch from scalar ``Params`` objects, one per run; ``BatchParams.baseline`` builds one
from the calibrated baseline with per-run overrides. Two conventions carry over from ``Params``:

- ``DemandGrowthLate`` may be ``None`` ("same as ``DemandGrowth``"), per run: it is stored as a float array with NaN
  where it is ``None``, plus the mask ``dgl_is_none``.
- ``AdoptC0`` is recomputed per run, as ``Params.with_overrides`` does, when ``pC``, ``qC`` or ``AC0`` is overridden and
  ``AdoptC0`` is not.

``PARAM_DENOMINATORS`` and ``param_denominator_faults`` implement the pre-loop check of the parameter-only
denominators (a run with one of them zero or negative is not finite).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

import numpy as np
from numpy.typing import ArrayLike

from aisim.batch.util import B, F
from aisim.dims import EMPLOYERS, LEVELS, REGIONS, SECTORS, TYPES, VENDORS, WTYPES
from aisim.params import ADOPTC0_INPUTS, NULLABLE, Params

TABLE_AXES: Final[Mapping[str, tuple[tuple[str, ...], ...]]] = MappingProxyType(
    {
        "SectorShare": (SECTORS,),
        "LOBWage": (SECTORS,),
        "RegDragLevel": (SECTORS,),
        "WTMix": (WTYPES,),
        "a2024": (WTYPES,),
        "amax": (WTYPES,),
        "SpeedUp": (WTYPES,),
        "BuildMix": (WTYPES,),
        "OffExp": (EMPLOYERS,),
        "Mix0": (VENDORS, TYPES),
        "Src0": (SECTORS, EMPLOYERS),
    }
)
"""The axes of every table, in ``dims`` order."""

Override = float | None | Sequence[float | None] | ArrayLike
"""A ``BatchParams.baseline`` override: one value for every run, or one value per run."""


@dataclass(frozen=True, slots=True)
class BatchParams:
    """The parameters of N runs.

    ``scalars[name]`` is ``(N,)``; ``tables[name]`` is ``(N, ...)`` with the axes of ``TABLE_AXES``.
    ``DemandGrowthLate`` holds NaN where ``dgl_is_none``. Construct with ``stack`` or ``baseline``.
    """

    scalars: Mapping[str, F]
    tables: Mapping[str, F]
    dgl_is_none: B
    _families: dict[tuple[str, tuple[tuple[str, ...], ...]], F] = field(default_factory=dict, repr=False, compare=False)

    @property
    def n(self) -> int:
        """The number of runs."""
        return int(self.dgl_is_none.shape[0])

    def __getitem__(self, name: str) -> F:
        """The ``(N,)`` array of scalar ``name``."""
        return self.scalars[name]

    def table(self, name: str) -> F:
        """The ``(N, ...)`` array of table ``name``."""
        return self.tables[name]

    def fam(self, prefix: str, *axes: Sequence[str]) -> F:
        """The scalars ``prefix + "_".join(keys)`` over the given axes, as one ``(N, *axes)`` array (cached).

        A family member that does not exist (the partial families ``Price_``, ``ExtEntryRate_``, ``NormalTTF_`` and
        ``RetireRate_``) is NaN, so any use of it shows up as a non-finite value.
        """
        key = (prefix, tuple(tuple(a) for a in axes))
        cached = self._families.get(key)
        if cached is not None:
            return cached
        nan = np.full(self.n, np.nan)
        grid = np.meshgrid(*[np.arange(len(a)) for a in axes], indexing="ij")
        shape = tuple(len(a) for a in axes)
        out = np.empty((self.n, *shape))
        for pos in zip(*(g.ravel() for g in grid), strict=True):
            name = prefix + "_".join(axes[i][j] for i, j in enumerate(pos))
            out[(slice(None), *pos)] = self.scalars.get(name, nan)
        out.setflags(write=False)
        self._families[key] = out
        return out

    @classmethod
    def stack(cls, params: Sequence[Params]) -> BatchParams:
        """Stack scalar ``Params``, one per run. Raises ``ValueError`` if they are empty or their names differ."""
        if not params:
            raise ValueError("no parameter sets to stack")
        names = list(params[0].scalars)
        for p in params[1:]:
            if set(p.scalars) != set(names) or set(p.tables) != set(params[0].tables):
                raise ValueError("every Params must have the same scalar and table names")
        scalars: dict[str, F] = {}
        is_none = np.zeros(len(params), dtype=np.bool_)
        for name in names:
            values = [p.scalars[name] for p in params]
            if name in NULLABLE:
                is_none = np.array([v is None for v in values], dtype=np.bool_)
            scalars[name] = np.array([np.nan if v is None else v for v in values], dtype=np.float64)
        tables = {name: np.stack([_table_array(p, name) for p in params]) for name in TABLE_AXES}
        return cls._build(scalars, tables, is_none)

    @classmethod
    def baseline(cls, n: int, **overrides: Override) -> BatchParams:
        """The calibrated baseline for ``n`` runs, with ``overrides`` (a value for all runs or one per run).

        Raises ``KeyError`` for an unknown name, ``ValueError`` for a per-run sequence that is not of length ``n`` and
        for ``None`` on any name but ``DemandGrowthLate``. Recomputes ``AdoptC0`` per run as ``Params.with_overrides``
        does.
        """
        if n < 1:
            raise ValueError("n must be at least 1")
        base = Params.baseline()
        unknown = sorted(k for k in overrides if k not in base.scalars)
        if unknown:
            raise KeyError(f"unknown parameter(s): {unknown}")
        scalars: dict[str, F] = {}
        is_none = np.zeros(n, dtype=np.bool_)
        for name, value in base.scalars.items():
            values = _per_run(name, overrides.get(name, value), n)
            if name in NULLABLE:
                is_none = np.array([v is None for v in values], dtype=np.bool_)
            elif any(v is None for v in values):
                raise ValueError(f"only {sorted(NULLABLE)} may be None, not {name!r}")
            scalars[name] = np.array([np.nan if v is None else v for v in values], dtype=np.float64)
        if ADOPTC0_INPUTS & overrides.keys() and "AdoptC0" not in overrides:
            pC, qC, AC0 = scalars["pC"], scalars["qC"], scalars["AC0"]
            scalars["AdoptC0"] = (pC + qC * AC0) * (1 - AC0)
        tables = {name: np.stack([_table_array(base, name)] * n) for name in TABLE_AXES}
        return cls._build(scalars, tables, is_none)

    @classmethod
    def _build(cls, scalars: dict[str, F], tables: dict[str, F], is_none: B) -> BatchParams:
        for a in (*scalars.values(), *tables.values(), is_none):
            a.setflags(write=False)
        return cls(scalars=MappingProxyType(scalars), tables=MappingProxyType(tables), dgl_is_none=is_none)


def _per_run(name: str, value: Override, n: int) -> list[float | None]:
    """Expand one override to a list of ``n`` per-run values."""
    if value is None or isinstance(value, int | float):
        return [None if value is None else float(value)] * n
    if isinstance(value, Sequence) and not isinstance(value, str):
        seq: list[float | None] = [None if v is None else float(v) for v in value]
    else:
        seq = [float(v) for v in np.asarray(value, dtype=np.float64).ravel()]
        if np.ndim(value) != 1:
            raise ValueError(f"{name}: a per-run override must be one-dimensional")
    if len(seq) != n:
        raise ValueError(f"{name}: {len(seq)} values for {n} runs")
    return seq


def _table_array(p: Params, name: str) -> F:
    """Table ``name`` of ``p`` as an array with the axes of ``TABLE_AXES``."""
    axes = TABLE_AXES[name]
    t = p.tables[name]
    if len(axes) == 1:
        return np.array([t[k] for k in axes[0]], dtype=np.float64)
    rows = []
    for k in axes[0]:
        inner = t[k]
        assert isinstance(inner, Mapping)
        rows.append([inner[kk] for kk in axes[1]])
    return np.array(rows, dtype=np.float64)


PARAM_DENOMINATORS: Final[tuple[str, ...]] = (
    # Direct divisors, as the scalar engine reads them (recon 03 B2; the division scan is in the slice 3 ship report).
    "MinCompletionTime",
    "AbandonTime",
    "CancelTime",
    "MinFillTime",
    "TimeInJunior",
    "TimeInMid",
    "PromoFillTime",
    "HireAdjTime",
    "LayoffAdjTime",
    "MinLayoffTime",
    "OnboardTime",
    "VisaTenure",
    "RecoveryTime",
    "StudyTime",
    "TrendTime",
    "MinAdoptionTime",
    "CostPerBFY0",
    "AppLife",
    "IHReviewTime",
    "GCCReviewTime",
    "CostRef",
    "LOBAdjTime",
    "SeatAdjTime",
    "BudgetCycle",
    "SrcPerceptionTime",
    "CostPerceptionTime",
    "UnempPerceptionTime",
    "StudentPerceptionTime",
    "PerceptionTime",
    "ClientPerceptionTime",
    "TightPerceptionTime",
    "OverheadAdjTime",
    "ViabilityTime",
    "CostProgramTime",
    "DiscAdjTime",
    "ShareRefTime",
    "WageAdjTime",
    *(f"LabourCostPB0_{e}" for e in EMPLOYERS),
    *(f"BaseDur_{k}" for k in TYPES),
    *(f"NormalUnempRate_{r}" for r in REGIONS),
    *(f"NormalMargin_{v}" for v in VENDORS),
    *(f"Budget0_{x}" for x in SECTORS),
    *(f"Port0_{x}" for x in SECTORS),
    *(f"Seats0_{x}" for x in SECTORS),
    # NormalTTF_ is read only at M and S: ext is 0 at J, and TTFratio reads M. There is no NormalTTF_{r}_J parameter,
    # so the J slot of the family array is a NaN placeholder; it is excluded here by naming only the members read.
    # (The other partial families, Price_, ExtEntryRate_ and RetireRate_, are never divisors.)
    *(f"NormalTTF_{r}_{l}" for r in REGIONS for l in LEVELS if l != "J"),
)
"""Scalar parameters that the scalar engine divides by directly: each must be positive."""


def param_denominator_faults(pr: BatchParams) -> dict[str, B]:
    """Per-run masks of the parameter-only denominators that are zero or negative, by name.

    Covers ``PARAM_DENOMINATORS``, the ``SpeedUp`` table, and the parameter-only compound denominators: ``rest0 =
    Share0_M + Share0_S`` (S4), the ``PAI0`` denominator and ``A0 * PAI0 + (1 - A0)`` (S2), and ``NewApps0 = Port0 /
    AppLife`` (S13c). Every one is checked whatever branches a run takes.
    """
    out: dict[str, B] = {name: pr[name] <= 0 for name in PARAM_DENOMINATORS}
    speed_up, a2024 = pr.table("SpeedUp"), pr.table("a2024")
    out["SpeedUp"] = (speed_up <= 0).any(axis=1)
    out["Share0_M + Share0_S"] = pr["Share0_M"] + pr["Share0_S"] <= 0
    with np.errstate(divide="ignore", invalid="ignore"):
        pai0_den = (1 - a2024) + a2024 / speed_up + a2024 * pr["Verif"][:, None]
        pai0 = 1 / pai0_den
        A0 = pr["A0"][:, None]
        out["PAI0 denominator"] = (pai0_den <= 0).any(axis=1)
        out["A0 * PAI0 + (1 - A0)"] = (A0 * pai0 + (1 - A0) <= 0).any(axis=1)
        port0 = pr.fam("Port0_", SECTORS)
        out["NewApps0"] = (port0 / pr["AppLife"][:, None] <= 0).any(axis=1)
    return out
