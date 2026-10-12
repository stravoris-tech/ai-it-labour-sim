"""Batch inputs of an experiment: fixed parameters broadcast to N runs, with the sampled levers' per-run values.

Shared by the runner (which splits the arrays into chunks) and the validator (whose calibration check runs one step).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

import numpy as np

from aisim.batch.params import BatchParams
from aisim.batch.util import B, F
from aisim.params import ADOPTC0_INPUTS, Params

DGL = "DemandGrowthLate"


def batch_arrays(fixed: Params, sampled: Mapping[str, F], n: int) -> tuple[dict[str, F], dict[str, F], B]:
    """The ``(scalars, tables, dgl_is_none)`` arrays of N runs: ``fixed`` everywhere, ``sampled`` per run.

    - A sampled ``DemandGrowthLate`` of NaN means None ("same as ``DemandGrowth``"), as in ``BatchParams``.
    - ``AdoptC0`` is recomputed per run, as ``BatchParams.baseline`` does, only when ``pC``, ``qC`` or ``AC0`` is
      sampled; otherwise it keeps the value in ``fixed`` exactly (the shipped value unless one of them was overridden).
    """
    one = BatchParams.stack([fixed])
    scalars = {name: np.repeat(a, n) for name, a in one.scalars.items()}
    dgl_is_none = np.repeat(one.dgl_is_none, n)
    for name, values in sampled.items():
        v = np.array(values, dtype=np.float64)
        if v.shape != (n,):
            raise ValueError(f"{name}: {v.shape} values for {n} runs")
        if name == DGL:
            dgl_is_none = np.isnan(v)
        scalars[name] = v
    if ADOPTC0_INPUTS & sampled.keys() and "AdoptC0" not in sampled:
        pC, qC, AC0 = scalars["pC"], scalars["qC"], scalars["AC0"]
        scalars["AdoptC0"] = (pC + qC * AC0) * (1 - AC0)
    tables = {name: np.repeat(a, n, axis=0) for name, a in one.tables.items()}
    return scalars, tables, dgl_is_none


def make_batch_params(scalars: Mapping[str, F], tables: Mapping[str, F], dgl_is_none: B) -> BatchParams:
    """A ``BatchParams`` over the given arrays (made read-only, as ``BatchParams`` keeps them)."""
    for a in (*scalars.values(), *tables.values(), dgl_is_none):
        a.setflags(write=False)
    return BatchParams(
        scalars=MappingProxyType(dict(scalars)),
        tables=MappingProxyType(dict(tables)),
        dgl_is_none=dgl_is_none,
    )
