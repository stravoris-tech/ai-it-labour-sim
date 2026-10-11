"""Model parameters: the calibrated scalars and tables, loading and overrides.

``Params.baseline()`` is the calibrated Phase 7 parameter set from ``data/baseline.json``: the scalars exactly as
``phase7_runs.py`` assembles them from ``calib7.json`` and the module ``P``, and the module-level tables of
``phase7_sim.py`` (``SEC6``, ``WT6``, ``EMPS6``, ``MIX0``, ``SRC0``). ``data/parameters.csv`` classifies every scalar.

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
from typing import Any

from aisim.state import baseline_data

Table1D = Mapping[str, float]
Table2D = Mapping[str, Mapping[str, float]]
Table = Table1D | Table2D

NULLABLE = frozenset({"DemandGrowthLate"})
"""The only scalar that may be ``None``."""

ADOPTC0_INPUTS = frozenset({"pC", "qC", "AC0"})


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
    def baseline(cls) -> Params:
        """Return the calibrated baseline parameters shipped in ``data/baseline.json``."""
        data = baseline_data()
        return cls(scalars=data["params"], tables=data["tables"])

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

    def table(self, name: str) -> dict[str, float]:
        """Return a copy of a one-dimensional table. Raises ``TypeError`` for a two-dimensional one."""
        out: dict[str, float] = {}
        for k, v in self.tables[name].items():
            if isinstance(v, Mapping):
                raise TypeError(f"table {name!r} is two-dimensional")
            out[k] = v
        return out

    @staticmethod
    def float_of(scalars: Mapping[str, float | None], name: str) -> float:
        """Return ``scalars[name]``, which must not be ``None``."""
        v = scalars[name]
        if v is None:
            raise ValueError(f"{name} is None")
        return v
