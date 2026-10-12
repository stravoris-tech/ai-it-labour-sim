"""The package's data tables: parameter domains and the output catalogue.

- ``domains()``: one row per scalar parameter (``Params.baseline()`` order) and per table entry (``SpeedUp[APP]``,
  ``Mix0[OIT][TM]``), with its domain class, explicit bounds, the evidence (file:line in the scalar engine), notes, and
  ``read``: False where ``run()`` never reads the value, so that overriding it has no effect.
- ``catalogue()``: one row per output name: the 317 row keys (``kind = row``), the extras (``kind = extra``) and the
  derived outputs (``kind = derived``), with family, dimensions, unit, description and spec reference.

Both are built from recon 04 (``04-domains.csv``, ``04-catalogue.csv``) and ship in ``aisim/data/`` (CC BY 4.0).
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

import pandas as pd


@cache
def _read(name: str) -> pd.DataFrame:
    with files("aisim").joinpath("data", name).open(encoding="utf-8") as f:
        return pd.read_csv(f, keep_default_na=False, na_values={"lower": [""], "upper": [""]}, dtype=str)


def domains() -> pd.DataFrame:
    """The parameter domains: ``name, domain, lower, lower_inclusive, upper, upper_inclusive, evidence, notes, read``.

    ``lower`` and ``upper`` are floats (NaN where there is no bound); the ``*_inclusive`` columns are nullable booleans
    (missing where there is no bound); ``read`` is boolean. Returns a fresh copy.
    """
    df = _read("domains.csv").copy()
    for col in ("lower", "upper"):
        df[col] = df[col].astype(float)
    for col in ("lower_inclusive", "upper_inclusive"):
        df[col] = df[col].map({"true": True, "false": False, "": pd.NA}).astype("boolean")
    df["read"] = df["read"].map({"true": True, "false": False}).astype(bool)
    return df


def catalogue() -> pd.DataFrame:
    """The output catalogue: ``key, family, dims, unit, description, spec_ref, kind, unit_inferred``. A fresh copy."""
    df = _read("catalogue.csv").copy()
    df["unit_inferred"] = df["unit_inferred"].map({"true": True, "false": False}).astype(bool)
    return df


def keys(family: str | None = None) -> list[str]:
    """The output names in ``family`` (all if None), in catalogue order. Raises ``KeyError`` for an unknown family."""
    cat = _read("catalogue.csv")
    if family is None:
        return list(cat["key"])
    if family not in set(cat["family"]):
        raise KeyError(f"unknown family {family!r}; families: {sorted(set(cat['family']))}")
    return list(cat.loc[cat["family"] == family, "key"])
