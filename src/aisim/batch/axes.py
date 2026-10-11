"""Axis order, index maps and structural masks of the batched engine, all taken from ``aisim.dims``.

Every array axis that stands for a dimension is in the order of its ``dims`` tuple (``UNITS``, ``EMPLOYERS``, ...),
which is also the key order of every scalar-engine dict (recon 03 D1). Ragged groups (the units of an employer or a
vendor, the units of a pool, the switchers, the effort-billed types) are bool masks; the engine sums over them with
exact zeros in place of non-members, never with 0/1 matrix products (recon 03 C3).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import numpy as np
from numpy.typing import NDArray

from aisim.batch.util import B
from aisim.dims import (
    EFFORT,
    EMP_OF,
    EMP_POOL,
    EMPLOYERS,
    LEVELS,
    LOC,
    POOL,
    REGIONS,
    SECTORS,
    SWITCHERS,
    TYPES,
    UNITS,
    VENDORS,
    WTYPES,
)


def index(keys: Sequence[str]) -> dict[str, int]:
    """Return the position of each key."""
    return {k: i for i, k in enumerate(keys)}


def _ro[A: NDArray[np.generic]](a: A) -> A:
    """Make ``a`` read-only and return it."""
    a.setflags(write=False)
    return a


UNIT_IX: Final = index(UNITS)
EMP_IX: Final = index(EMPLOYERS)
VEND_IX: Final = index(VENDORS)
REG_IX: Final = index(REGIONS)
LEV_IX: Final = index(LEVELS)
SEC_IX: Final = index(SECTORS)
WT_IX: Final = index(WTYPES)
TYPE_IX: Final = index(TYPES)

EMP_OF_IX: Final = _ro(np.array([EMP_IX[EMP_OF[u]] for u in UNITS]))
"""Employer index of each unit, ``(units,)``."""

POOL_IX: Final = _ro(np.array([REG_IX[POOL[u]] for u in UNITS]))
"""Pool (region) index of each unit, ``(units,)``."""

VENDOR_EMP_IX: Final = _ro(np.array([EMP_IX[v] for v in VENDORS]))
"""Employer index of each vendor, ``(vendors,)``."""

EMP_POOL_IX: Final = _ro(np.array([REG_IX[EMP_POOL[e]] for e in EMPLOYERS]))
"""Main pool index of each employer, ``(employers,)``."""

UNITS_OF_EMP: Final[B] = _ro(np.array([[EMP_OF[u] == e for u in UNITS] for e in EMPLOYERS]))
"""``(employers, units)``: the units of each employer."""

UNITS_OF_VENDOR: Final[B] = _ro(np.array([[EMP_OF[u] == v for u in UNITS] for v in VENDORS]))
"""``(vendors, units)``: the units of each vendor (the scalar engine's ``VF[v].vu``)."""

POOL_MASK: Final[B] = _ro(np.array([[POOL[u] == r for u in UNITS] for r in REGIONS]))
"""``(regions, units)``: the units hiring from each pool."""

LOC_MASK: Final[B] = _ro(np.array([[LOC[u] == r for u in UNITS] for r in REGIONS]))
"""``(regions, units)``: the units located in each region."""

SWITCHER: Final[B] = _ro(np.array([u in SWITCHERS for u in UNITS]))
"""``(units,)``: units whose staff switch jobs (all but OV)."""

SWITCH_PAIR: Final[B] = _ro(
    np.array([[s in SWITCHERS and d in SWITCHERS and s != d and POOL[s] == POOL[d] for d in UNITS] for s in UNITS])
)
"""``(src, dst)`` over units: staff can switch from ``src`` to ``dst`` (both switchers, same pool, not the same)."""

SWITCH_PAIRS: Final = tuple(
    (UNIT_IX[s], UNIT_IX[d])
    for r in REGIONS
    for s in SWITCHERS
    if POOL[s] == r
    for d in SWITCHERS
    if POOL[d] == r and d != s
)
"""The 18 ``(src, dst)`` switching pairs as unit indices, in the scalar loop order (pool, source, destination)."""

SWITCH_SRC: Final = _ro(np.array([s for s, _ in SWITCH_PAIRS]))
SWITCH_DST: Final = _ro(np.array([d for _, d in SWITCH_PAIRS]))

SWITCH_OTHERS: Final = tuple(tuple(d for d in range(len(UNITS)) if SWITCH_PAIR[s, d]) for s in range(len(UNITS)))
"""For each unit, the other switchers of its pool, in unit order (empty for OV)."""

SWITCH_INTO: Final = tuple(tuple(p for p, (_, d) in enumerate(SWITCH_PAIRS) if d == u) for u in range(len(UNITS)))
"""For each unit, the pairs that switch into it, in source order."""

SWITCH_FROM: Final = tuple(tuple(p for p, (s, _) in enumerate(SWITCH_PAIRS) if s == u) for u in range(len(UNITS)))
"""For each unit, the pairs that switch out of it, in destination order."""

VENDOR_UNIT: Final[B] = _ro(np.array([EMP_OF[u] in VENDORS for u in UNITS]))
"""``(units,)``: units that belong to a vendor."""

VENDOR_OF_UNIT_IX: Final = _ro(np.array([VEND_IX.get(EMP_OF[u], 0) for u in UNITS]))
"""Vendor index of each unit, ``(units,)``; 0 (a placeholder, always masked by ``VENDOR_UNIT``) for IH and GCC."""

EFFORT_TYPE: Final[B] = _ro(np.array([k in EFFORT for k in TYPES]))
"""``(types,)``: the effort-billed contract types (TM, SA)."""

GLIDE_TYPE: Final[B] = _ro(np.array([k in ("MS", "OB") for k in TYPES]))
"""``(types,)``: the types whose price glides with productivity (MS, OB)."""
