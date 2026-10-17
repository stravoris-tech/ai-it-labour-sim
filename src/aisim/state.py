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
from importlib.resources.abc import Traversable
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


DEFAULT_MODEL: Final = "phase8"
"""The model every library default and unknown-model fallback names: ``phase8``."""

BASELINE_FILES: Final[dict[str, Traversable]] = {
    "phase7": files("aisim").joinpath("data", "baseline.json"),
    "phase8": files("aisim").joinpath("data", "baseline_phase8.json"),
    "phase8_highadoption": files("aisim").joinpath("data", "baseline_phase8_highadoption.json"),
}
"""The model registry: each named model's baseline file.

- ``phase7`` (``data/baseline.json``) is the prototype's calibrated model, kept as the prototype-parity reference.
- ``phase8`` adds continuous openings and the slice 8 pricing design, with a full multi-start refit. It is the
  default (``DEFAULT_MODEL``).
- ``phase8_highadoption`` is the same refitted with ``p`` at Phase 7's 0.044, the adoption-speed alternative.

The phase 8 files are written by ``tools/build_model.py`` from ``tools/models/<name>/spec.json`` and ``fit.json``.

Every check reads this mapping at call time (``models()``), so it is the one list of models. A model registered at
runtime (the test fixture ``register_model``) is visible in this process only, so use it with ``workers=1``; a shipped
model is a package file and works with any worker count.
"""


def models() -> tuple[str, ...]:
    """The names of the registered models (``BASELINE_FILES``), read at call time."""
    return tuple(BASELINE_FILES)


def baseline_data(model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Return the parsed baseline file of ``model`` (a fresh object on every call).

    ``phase7`` reads ``data/baseline.json``. Raises ``ValueError`` for a model not in ``BASELINE_FILES``. ``Any``:
    parsed JSON; ``Params`` and ``State`` give it its types.
    """
    if model not in BASELINE_FILES:
        raise ValueError(f"unknown model {model!r}: one of {list(models())}")
    text = BASELINE_FILES[model].read_text(encoding="utf-8")
    data: dict[str, Any] = json.loads(text)
    return data


def copy_state(state: State) -> State:
    """Return a deep copy of ``state``."""
    return copy.deepcopy(state)


def load_initial_state() -> State:
    """Return the calibrated 2024 state, a fresh copy on every call.

    Every model starts from this state: the model extensions (``aisim.params.EXTENSION_DEFAULTS``) add no stock, so a
    model's baseline file carries the same ``init``.
    """
    init: State = baseline_data()["init"]
    return init
