"""Model parameters: the calibrated scalars and tables, loading and overrides.

``Params.baseline()`` is the calibrated Phase 7 parameter set from ``data/baseline.json``: the scalars exactly as
``phase7_runs.py`` assembles them from ``calib7.json`` and the module ``P``, and the module-level tables of
``phase7_sim.py`` (``SEC6``, ``WT6``, ``EMPS6``, ``MIX0``, ``SRC0``), plus the model extensions at their neutral
``EXTENSION_DEFAULTS``. ``Params.baseline(model)`` reads another registered model's file
(``aisim.state.BASELINE_FILES``; today only ``phase7``). ``data/parameters.csv`` classifies every scalar.

Two conventions differ from the prototype:

- ``DemandGrowthLate is None`` means "same as ``DemandGrowth``". It replaces the prototype's ``-1.0`` sentinel; an
  explicit float is used as given.
- ``AdoptC0`` is derived, ``(pC + qC * AC0) * (1 - AC0)`` (07). ``with_overrides`` recomputes it when ``pC``, ``qC``
  or ``AC0`` changes and ``AdoptC0`` is not overridden too, so 2024 stays on its growth path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal, overload

from aisim.state import baseline_data

Table1D = Mapping[str, float]
Table2D = Mapping[str, Mapping[str, float]]
Table = Table1D | Table2D

EXTENSION_DEFAULTS: Final[Mapping[str, float]] = MappingProxyType({"AnnuityShare": 0.0, "AnnuityAnchorW": 0.0})
"""Model extensions: parameters the prototype does not have, at values that reproduce Phase 7 bit for bit.

They are not in ``data/baseline.json`` (whose bytes stay the prototype's); ``Params.baseline`` merges them in.
``AnnuityShare`` is the annuity share of new TM signings and ``AnnuityAnchorW`` the weight of the client price anchor
on their price (the E2a annuity pricing term, slice 8).
"""

NULLABLE = frozenset({"DemandGrowthLate"})
"""The only scalar that may be ``None``."""

ADOPTC0_INPUTS = frozenset({"pC", "qC", "AC0"})

Table1DName = Literal[
    "SectorShare", "LOBWage", "RegDragLevel", "WTMix", "a2024", "amax", "SpeedUp", "BuildMix", "OffExp"
]
"""The one-dimensional tables of the baseline."""

Table2DName = Literal["Mix0", "Src0"]
"""The two-dimensional tables of the baseline (vendor x type, vendor x location)."""


def _freeze_table(values: Mapping[str, Any]) -> Table:
    """Return a read-only copy of a one- or two-dimensional table, with float values.

    ``Any``: the values come from parsed JSON or from a caller, and are either floats or mappings of floats.
    """
    if all(isinstance(v, Mapping) for v in values.values()):
        return MappingProxyType(
            {k: MappingProxyType({kk: float(vv) for kk, vv in v.items()}) for k, v in values.items()}
        )
    return MappingProxyType({k: float(v) for k, v in values.items()})


def _same_keys(old: Table, new: Mapping[str, Any]) -> bool:
    """True if ``new`` has the keys of ``old`` at both levels (order free)."""
    if set(old) != set(new):
        return False
    for k, v in old.items():
        if isinstance(v, Mapping) != isinstance(new[k], Mapping):
            return False
        if isinstance(v, Mapping) and set(v) != set(new[k]):
            return False
    return True


@dataclass(frozen=True, slots=True)
class Params:
    """An immutable parameter set: named scalars and named tables.

    Construct with ``Params.baseline()`` and derive variants with ``with_overrides`` and ``with_table``. The
    constructor copies its inputs into read-only mappings.
    """

    scalars: Mapping[str, float | None]
    tables: Mapping[str, Table]

    def __post_init__(self) -> None:
        bad = sorted(k for k, v in self.scalars.items() if v is None and k not in NULLABLE)
        if bad:
            raise ValueError(f"only {sorted(NULLABLE)} may be None, not {bad}")
        scalars = {k: (None if v is None else float(v)) for k, v in self.scalars.items()}
        tables = {name: _freeze_table(values) for name, values in self.tables.items()}
        object.__setattr__(self, "scalars", MappingProxyType(scalars))
        object.__setattr__(self, "tables", MappingProxyType(tables))

    @classmethod
    def baseline(cls, model: str = "phase7") -> Params:
        """Return the calibrated baseline parameters of ``model`` (``aisim.state.BASELINE_FILES``).

        ``phase7`` is ``data/baseline.json``. ``EXTENSION_DEFAULTS`` fill any extension the file does not carry,
        after its own scalars. Raises ``ValueError`` for an unknown model.
        """
        data = baseline_data(model)
        scalars = dict(data["params"])
        for name, value in EXTENSION_DEFAULTS.items():
            scalars.setdefault(name, value)
        return cls(scalars=scalars, tables=data["tables"])

    def with_overrides(self, **scalars: float | None) -> Params:
        """Return a new ``Params`` with the given scalars replaced.

        Raises ``KeyError`` for an unknown name and ``ValueError`` for ``None`` on any name but ``DemandGrowthLate``.
        Recomputes ``AdoptC0`` when ``pC``, ``qC`` or ``AC0`` is overridden and ``AdoptC0`` is not.
        """
        unknown = sorted(k for k in scalars if k not in self.scalars)
        if unknown:
            raise KeyError(f"unknown parameter(s): {unknown}")
        new = dict(self.scalars)
        new.update(scalars)
        if ADOPTC0_INPUTS & scalars.keys() and "AdoptC0" not in scalars:
            pC, qC, AC0 = (self.float_of(new, k) for k in ("pC", "qC", "AC0"))
            new["AdoptC0"] = (pC + qC * AC0) * (1 - AC0)
        return Params(scalars=new, tables=self.tables)

    def with_table(self, name: str, values: Table) -> Params:
        """Return a new ``Params`` with table ``name`` replaced by ``values``.

        Raises ``KeyError`` for an unknown table and ``ValueError`` if the keys (at both levels) differ.
        """
        if name not in self.tables:
            raise KeyError(f"unknown table: {name!r}")
        old = self.tables[name]
        if not _same_keys(old, values):
            raise ValueError(f"table {name!r}: keys must be {sorted(old)} (and the same inner keys)")
        # Any: the table is one- or two-dimensional; _same_keys has checked its shape against the old one.
        raw: Mapping[str, Any] = values
        ordered = {k: ({kk: raw[k][kk] for kk in v} if isinstance(v, Mapping) else raw[k]) for k, v in old.items()}
        tables = dict(self.tables)
        tables[name] = _freeze_table(ordered)
        return Params(scalars=self.scalars, tables=tables)

    @overload
    def table(self, name: Table1DName) -> dict[str, float]: ...

    @overload
    def table(self, name: Table2DName) -> dict[str, dict[str, float]]: ...

    @overload
    def table(self, name: str) -> dict[str, Any]: ...

    def table(self, name: str) -> dict[str, Any]:
        """Return a plain copy of a table: ``dict[str, float]`` for a one-dimensional table, ``dict[str, dict[str,
        float]]`` for a two-dimensional one (``Mix0``, ``Src0``).

        Any: a name that is not a literal may be either shape. mypy rejects a ``str`` overload returning
        ``dict[str, float]`` beside the two-dimensional literal one (overlapping overloads), so the literal names carry
        the precise types.
        """
        return {k: (dict(v) if isinstance(v, Mapping) else v) for k, v in self.tables[name].items()}

    @staticmethod
    def float_of(scalars: Mapping[str, float | None], name: str) -> float:
        """Return ``scalars[name]``, which must not be ``None``."""
        v = scalars[name]
        if v is None:
            raise ValueError(f"{name} is None")
        return v


@dataclass(frozen=True, slots=True)
class Reanchor:
    """The re-anchoring of the five 2024-anchored exogenous paths at year ``Y``, for phase 2 of a two-phase run.

    ``aW`` (rate ``g``), ``VerifNow`` (``VerifDecline``), ``LOBAuto`` (``aL_max``, ``g``), ``CreditCostPB`` and
    ``AICostPerUnit`` (``AICostDecline``) are written in closed form from 2024. A run whose rate differs from the base
    rate would jump at Y to where the new rate would have taken the path since 2024 (recon 06 B5). Re-anchored, the
    path continues from its base value at Y at the run's rate, so it is continuous at Y.

    The engines use the re-anchored formula only for a run whose path inputs differ from the base rates held here, and
    today's formula otherwise, so an unchanged run stays bit-identical (recon 06 E4). The base values at Y are computed
    once here, in Python floats, so both engines read the same numbers.
    """

    Y: float
    g: float
    VerifDecline: float
    aL_max: float
    AICostDecline: float
    g_decay: float
    """``(1 - g) ** (Y - 2024)`` at the base ``g``."""
    verif_Y: float
    """The base ``VerifNow`` at Y."""
    lob_Y: float
    """The base ``LOBAuto`` at Y, before its floor at 0."""
    cost_decay: float
    """``(1 - AICostDecline) ** (Y - 2024)`` at the base ``AICostDecline``."""

    @classmethod
    def at(cls, base: Params, Y: float) -> Reanchor:
        """The re-anchoring at year ``Y`` of the paths of ``base`` (the calibrated baseline of phase 1)."""
        s = base.scalars
        g, vd, aL_max, acd = (Params.float_of(s, k) for k in ("g", "VerifDecline", "aL_max", "AICostDecline"))
        g_decay = (1 - g) ** (Y - 2024)
        return cls(
            Y=Y,
            g=g,
            VerifDecline=vd,
            aL_max=aL_max,
            AICostDecline=acd,
            g_decay=g_decay,
            verif_Y=Params.float_of(s, "Verif") * (1 - vd) ** (Y - 2024),
            lob_Y=aL_max - (aL_max - Params.float_of(s, "aL_2024")) * g_decay,
            cost_decay=(1 - acd) ** (Y - 2024),
        )
