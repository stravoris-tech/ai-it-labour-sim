"""The model state: one entry per stock family, and the calibrated 2024 state.

``State`` mirrors the state dict of ``phase7_sim.py`` (its ``init`` argument, the ``st`` of ``run()``). Stocks indexed
by one dimension are ``Vec`` (for example ``A[employer]``), by two dimensions ``Mat`` (for example ``H[unit][level]``),
and three stocks are plain floats. The calibrated 2024 state is the ``init`` of ``data/baseline.json``, copied exactly
from ``calib7.json``. Spec: 00 "Stocks, flows and key auxiliaries".
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any, Final, TypedDict

Vec = dict[str, float]
"""A quantity indexed by one dimension."""

Mat = dict[str, dict[str, float]]
"""A quantity indexed by two dimensions, outer then inner."""


class State(TypedDict):
    """The 37 stock families (347 values) of the model."""

    BL: Mat
    """Backlog of work by sector and work type."""
    A: Vec
    """Delivery AI adoption by employer."""
    PerceivedP: Vec
    """Productivity perceived by employers, for hiring."""
    ClientP: Vec
    """Productivity perceived by clients, for pricing."""
    ClientPRef: Vec
    """Client reference productivity (the trend clients price against)."""
    TightPerc: float
    """Perceived visa tightness."""
    H: Mat
    """Headcount by unit and level."""
    O: Mat
    """Onboarding staff by unit and level."""
    V: Mat
    """Vacancies by unit and level."""
    R: Mat
    """Recently laid off, by region and level."""
    U: Mat
    """Job seekers by region and level."""
    Pipeline: Vec
    """Students by region."""
    LeftField: Vec
    """People who left the IT field, by region (accumulator)."""
    Retired: Vec
    """People who retired, by region (accumulator)."""
    PUS: Vec
    """Perceived unemployment (short, for leaving and wages), by region."""
    PUL: Vec
    """Perceived unemployment (long, for students), by region."""
    WI: Vec
    """Wage index by unit."""
    Overhead: Vec
    """Vendor overhead."""
    Viab: Vec
    """Vendor viability (smoothed margin)."""
    CostProg: Vec
    """Vendor cost programme savings."""
    Disc: Vec
    """Vendor competitive discount."""
    ShareRef: Vec
    """Vendor reference work share."""
    Leg: Mat
    """Legacy contract book by vendor and contract type."""
    NewV: Mat
    """New contract volume by vendor and type."""
    NewD: Mat
    """Duration-weighted new contract volume."""
    NewP: Mat
    """Price-weighted new contract volume."""
    IHW: Vec
    """In-house share of each sector's work."""
    GCCW: Vec
    """GCC share of each sector's work."""
    VW: Mat
    """Vendor shares of each sector's work."""
    SrcPerc: Mat
    """Perceived sourcing shares by sector and employer."""
    AC: Vec
    """Consumer AI adoption by sector."""
    LOB: Vec
    """Line-of-business staff by sector."""
    Port: Vec
    """Application portfolio by sector."""
    SeatsB: Vec
    """Billed software seats by sector."""
    SpendRatio: Vec
    """Committed spend over budget, by sector (smoothed)."""
    Att: float
    """AI seat attach rate."""
    CostPerc: float
    """Perceived cost index of IT services."""


MODELS: Final = ("phase7", "phase8")
"""The named models: ``phase7`` (the prototype's calibrated model, the default) and ``phase8`` (contract pricing)."""

BASELINE_FILES: Final = {"phase7": "baseline.json", "phase8": "baseline_phase8.json"}
"""The baseline file of each model under ``aisim/data``."""


def baseline_data(model: str = "phase7") -> dict[str, Any]:
    """Return the parsed baseline file of ``model`` shipped with the package (a fresh object on every call).

    ``phase7`` reads ``data/baseline.json``, ``phase8`` reads ``data/baseline_phase8.json``. Raises ``ValueError``
    for a model not in ``MODELS``. ``Any``: parsed JSON; ``Params`` and ``State`` give it its types.
    """
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}: one of {list(MODELS)}")
    text = files("aisim").joinpath("data", BASELINE_FILES[model]).read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def copy_state(state: State) -> State:
    """Return a deep copy of ``state``."""
    return copy.deepcopy(state)


def load_initial_state() -> State:
    """Return the calibrated 2024 state, a fresh copy on every call.

    Every model starts from this state: phase 8 adds no stock and is neutral in 2024, so its baseline file carries
    the same ``init``.
    """
    init: State = baseline_data()["init"]
    return init
