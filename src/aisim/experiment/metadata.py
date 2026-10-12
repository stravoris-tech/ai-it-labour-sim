"""The package's data tables: parameter domains and the output catalogue.

- ``domains()``: one row per scalar parameter (``Params.baseline()`` order) and per table entry (``SpeedUp[APP]``,
  ``Mix0[OIT][TM]``), with its domain class, explicit bounds, the evidence (file:line in the scalar engine), notes,
  ``read``: False where ``run()`` never reads the value, so that overriding it has no effect, and ``level_2024``: True
  where the value describes 2024 itself (a 2024 level or a stored 2024 calibration constant), so it cannot act from a
  later perturb year (slice 6).
- ``catalogue()``: one row per output name: the 317 row keys (``kind = row``), the extras (``kind = extra``) and the
  derived outputs (``kind = derived``), with family, dimensions, unit, description and spec reference.
- ``keys(family, **dims)`` filters the names by family and dimension values; ``dims(key)`` parses one key's dimensions.

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
    """The parameter domains: ``name, domain, lower, lower_inclusive, upper, upper_inclusive, evidence, notes, read,
    level_2024``.

    ``lower`` and ``upper`` are floats (NaN where there is no bound); the ``*_inclusive`` columns are nullable booleans
    (missing where there is no bound); ``read`` and ``level_2024`` are boolean. Returns a fresh copy.
    """
    df = _read("domains.csv").copy()
    for col in ("lower", "upper"):
        df[col] = df[col].astype(float)
    for col in ("lower_inclusive", "upper_inclusive"):
        df[col] = df[col].map({"true": True, "false": False, "": pd.NA}).astype("boolean")
    for col in ("read", "level_2024"):
        df[col] = df[col].map({"true": True, "false": False}).astype(bool)
    return df


def catalogue() -> pd.DataFrame:
    """The output catalogue: ``key, family, dims, unit, description, spec_ref, kind, unit_inferred``. A fresh copy."""
    df = _read("catalogue.csv").copy()
    df["unit_inferred"] = df["unit_inferred"].map({"true": True, "false": False}).astype(bool)
    return df


def _dims_of(text: str) -> dict[str, str]:
    """Parse a catalogue ``dims`` cell (``vendor=OIT;type=FP``); ``{}`` for an empty one."""
    if not text:
        return {}
    return dict(part.split("=", 1) for part in text.split(";"))


@cache
def _dims_table() -> dict[str, dict[str, str]]:
    cat = _read("catalogue.csv")
    return {k: _dims_of(d) for k, d in zip(cat["key"], cat["dims"], strict=True)}


@cache
def dimension_names() -> tuple[str, ...]:
    """The dimension names used in the catalogue, sorted (``employer``, ``level``, ... ``worktype``)."""
    return tuple(sorted({name for d in _dims_table().values() for name in d}))


def dims(key: str) -> dict[str, str]:
    """The dimensions of an output name, e.g. ``{"vendor": "OIT", "type": "FP"}``; ``{}`` for a key without any.

    Raises ``KeyError`` for an unknown name.
    """
    try:
        return dict(_dims_table()[key])
    except KeyError:
        raise KeyError(f"unknown output name {key!r}; see aisim.catalogue()") from None


def keys(family: str | None = None, **dims: str) -> list[str]:
    """The output names in ``family`` (all if None) whose dimensions match every ``name=value`` given, in catalogue
    order: ``keys(family="contract mix (book)", vendor="OIT")``.

    Raises ``KeyError`` for an unknown family or dimension name.
    """
    cat = _read("catalogue.csv")
    if family is not None and family not in set(cat["family"]):
        raise KeyError(f"unknown family {family!r}; families: {sorted(set(cat['family']))}")
    unknown = sorted(set(dims) - set(dimension_names()))
    if unknown:
        raise KeyError(f"unknown dimension(s) {unknown}; dimensions: {list(dimension_names())}")
    table = _dims_table()
    out = []
    for key, fam in zip(cat["key"], cat["family"], strict=True):
        if family is not None and fam != family:
            continue
        d = table[key]
        if all(d.get(name) == value for name, value in dims.items()):
            out.append(key)
    return out
