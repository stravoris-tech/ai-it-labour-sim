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
    """The 43 stock families (366 values) of the model: the prototype's 37 (347 values), then the six of the feedback
    loops (``LOOP_FAMILIES``)."""

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
    WS0: float
    """R7: the 2024 economy-wide GCC work share (sentinel -1 until the first step fills it)."""
    VMarg: Vec
    """R6: vendor margin smoothed over ``R6MargTime`` (0.75 years), starting from ``Viab``."""
    ECost: Vec
    """R6 C5: the vendor's expected delivery cost, ``CostIdx`` smoothed at the book's expiry rate (sentinel -1)."""
    Attr0: Vec
    """R10: the vendor's 2024 voluntary exits per head (sentinel -1)."""
    Dur0: Mat
    """R4: the 2024 seeker spell length by region and level (sentinel -1)."""
    C4Hab: Vec
    """R6 C4: the habituated viability shortfall, smoothed over ``C4FadeTime``, starting at 0."""


LOOP_FAMILIES: Final = ("WS0", "VMarg", "ECost", "Attr0", "Dur0", "C4Hab")
"""The state families of the feedback loops (slice 12), after the prototype's 37.

The four 2024 references (``WS0``, ``ECost``, ``Attr0``, ``Dur0``) start at the sentinel -1 and are filled at the
start of ``integrate`` on the first step, so every term sees "no reference" on step 0 and is neutral there. The two
smoothed signals start from their 2024 values (``VMarg`` = ``Viab``, so relative viability is exactly 1; ``C4Hab`` =
0), since they are read before ``integrate`` on step 0. All six are carried through ``BatchState``, so a restart at Y
is exact. They are advanced even when every loop is off, and then never read back.
"""


DEFAULT_MODEL: Final = "phase8"
"""The model every library default and unknown-model fallback names: ``phase8``."""

BASELINE_FILES: Final[dict[str, Traversable]] = {
    "phase7": files("aisim").joinpath("data", "baseline.json"),
    "phase8": files("aisim").joinpath("data", "baseline_phase8.json"),
    "phase8_highadoption": files("aisim").joinpath("data", "baseline_phase8_highadoption.json"),
    "phase9": files("aisim").joinpath("data", "baseline_phase9.json"),
    "phase9_highadoption": files("aisim").joinpath("data", "baseline_phase9_highadoption.json"),
}
"""The model registry: each named model's baseline file.

- ``phase7`` (``data/baseline.json``) is the prototype's calibrated model, kept as the prototype-parity reference.
- ``phase8`` adds continuous openings and the slice 8 pricing design, with a full multi-start refit. It is the
  default (``DEFAULT_MODEL``).
- ``phase8_highadoption`` is the same refitted with ``p`` at Phase 7's 0.044, the adoption-speed alternative.
- ``phase9`` is ``phase8`` plus the four feedback loops of slice 12 (R7, R6, R10, R4) at their evidence base values,
  with a full multi-start refit (``docs/model-changes-phase9.md``). It is registered, not the default.
- ``phase9_highadoption`` is ``phase9`` refitted with ``p`` at Phase 7's 0.044 (slice 13): the like-for-like
  adoption-speed alternative to ``phase9``, as ``phase8_highadoption`` is to ``phase8``.

The phase 8 and phase 9 files are written by ``tools/build_model.py`` from ``tools/models/<name>/spec.json`` and
``fit.json``.

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

    Every model starts from this state, and every model's baseline file carries the same ``init`` (the prototype's 37
    families). The six loop families (``LOOP_FAMILIES``) are not in the files: they are added here, at their sentinels
    and 2024 signals.
    """
    from aisim.dims import LEVELS, REGIONS, VENDORS

    init: State = baseline_data()["init"]
    init["WS0"] = -1.0
    init["VMarg"] = dict(init["Viab"])
    init["ECost"] = {v: -1.0 for v in VENDORS}
    init["Attr0"] = {v: -1.0 for v in VENDORS}
    init["Dur0"] = {r: {l: -1.0 for l in LEVELS} for r in REGIONS}
    init["C4Hab"] = {v: 0.0 for v in VENDORS}
    return init
