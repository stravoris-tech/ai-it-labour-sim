"""The state of N runs: one array per stock family, with a leading run axis.

``BatchState`` mirrors ``aisim.state.State``: the same 43 families (the prototype's 37, then the six loop families of
``aisim.state.LOOP_FAMILIES``), each an ``(N, ...)`` array whose other axes are the family's dimensions in ``dims``
order (recon 03 D1); the four plain-float stocks (the prototype's three and ``WS0``) are ``(N,)``. ``pack`` and
``unpack`` convert to and from scalar ``State`` dicts exactly (float64 holds every value of a Python float).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields
from types import MappingProxyType
from typing import Any, Final, cast

import numpy as np

from aisim.batch.util import F
from aisim.dims import EMPLOYERS, LEVELS, REGIONS, SECTORS, TYPES, UNITS, VENDORS, WTYPES
from aisim.state import State, load_initial_state

STATE_AXES: Final[Mapping[str, tuple[tuple[str, ...], ...]]] = MappingProxyType(
    {
        "BL": (SECTORS, WTYPES),
        "A": (EMPLOYERS,),
        "PerceivedP": (EMPLOYERS,),
        "ClientP": (EMPLOYERS,),
        "ClientPRef": (EMPLOYERS,),
        "TightPerc": (),
        "H": (UNITS, LEVELS),
        "O": (UNITS, LEVELS),
        "V": (UNITS, LEVELS),
        "R": (REGIONS, LEVELS),
        "U": (REGIONS, LEVELS),
        "Pipeline": (REGIONS,),
        "LeftField": (REGIONS,),
        "Retired": (REGIONS,),
        "PUS": (REGIONS,),
        "PUL": (REGIONS,),
        "WI": (UNITS,),
        "Overhead": (VENDORS,),
        "Viab": (VENDORS,),
        "CostProg": (VENDORS,),
        "Disc": (VENDORS,),
        "ShareRef": (VENDORS,),
        "Leg": (VENDORS, TYPES),
        "NewV": (VENDORS, TYPES),
        "NewD": (VENDORS, TYPES),
        "NewP": (VENDORS, TYPES),
        "IHW": (SECTORS,),
        "GCCW": (SECTORS,),
        "VW": (SECTORS, VENDORS),
        "SrcPerc": (SECTORS, EMPLOYERS),
        "AC": (SECTORS,),
        "LOB": (SECTORS,),
        "Port": (SECTORS,),
        "SeatsB": (SECTORS,),
        "SpendRatio": (SECTORS,),
        "Att": (),
        "CostPerc": (),
        "WS0": (),
        "VMarg": (VENDORS,),
        "ECost": (VENDORS,),
        "Attr0": (VENDORS,),
        "Dur0": (REGIONS, LEVELS),
        "C4Hab": (VENDORS,),
    }
)
"""The axes of every stock family, in ``State`` order."""


@dataclass(frozen=True, slots=True)
class BatchState:
    """The 43 stock families of N runs. The arrays are updated in place by the engine's integration step."""

    BL: F
    A: F
    PerceivedP: F
    ClientP: F
    ClientPRef: F
    TightPerc: F
    H: F
    O: F
    V: F
    R: F
    U: F
    Pipeline: F
    LeftField: F
    Retired: F
    PUS: F
    PUL: F
    WI: F
    Overhead: F
    Viab: F
    CostProg: F
    Disc: F
    ShareRef: F
    Leg: F
    NewV: F
    NewD: F
    NewP: F
    IHW: F
    GCCW: F
    VW: F
    SrcPerc: F
    AC: F
    LOB: F
    Port: F
    SeatsB: F
    SpendRatio: F
    Att: F
    CostPerc: F
    WS0: F
    VMarg: F
    ECost: F
    Attr0: F
    Dur0: F
    C4Hab: F

    @property
    def n(self) -> int:
        """The number of runs."""
        return int(self.Att.shape[0])

    def arrays(self) -> dict[str, F]:
        """Every family's array, by name, in ``State`` order (the arrays themselves, not copies)."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def copy(self) -> BatchState:
        """A deep copy (new arrays)."""
        return BatchState(**{k: v.copy() for k, v in self.arrays().items()})

    @classmethod
    def baseline(cls, n: int) -> BatchState:
        """The calibrated 2024 state for ``n`` runs."""
        if n < 1:
            raise ValueError("n must be at least 1")
        one = pack([load_initial_state()])
        return BatchState(**{k: np.repeat(v, n, axis=0) for k, v in one.arrays().items()})


def _leaf(state: State, name: str, keys: tuple[str, ...]) -> float:
    # Any: a State family is a float, a dict of floats or a dict of dicts of floats, walked by key.
    node: Any = cast(Mapping[str, Any], state)[name]
    for k in keys:
        node = node[k]
    return float(node)


def pack(states: Sequence[State]) -> BatchState:
    """Stack scalar states, one per run, into a ``BatchState``. Raises ``ValueError`` if ``states`` is empty."""
    if not states:
        raise ValueError("no states to pack")
    arrays: dict[str, F] = {}
    for name, axes in STATE_AXES.items():
        shape = tuple(len(a) for a in axes)
        out = np.empty((len(states), *shape))
        for idx in np.ndindex(*shape):
            keys = tuple(axes[i][j] for i, j in enumerate(idx))
            out[(slice(None), *idx)] = [_leaf(s, name, keys) for s in states]
        arrays[name] = out
    return BatchState(**arrays)


def unpack(batch: BatchState, i: int) -> State:
    """Return run ``i`` of ``batch`` as a scalar ``State`` (Python floats, keys in ``dims`` order)."""
    # Any: the families are built generically by shape; the result has exactly the keys and nesting of State.
    out: dict[str, Any] = {}
    for name, axes in STATE_AXES.items():
        a = getattr(batch, name)[i]
        if len(axes) == 0:
            out[name] = float(a)
        elif len(axes) == 1:
            out[name] = {k: float(a[j]) for j, k in enumerate(axes[0])}
        else:
            out[name] = {k: {kk: float(a[j, jj]) for jj, kk in enumerate(axes[1])} for j, k in enumerate(axes[0])}
    return cast(State, out)
