"""The one colour map: a fixed, colour-blind-safe colour for every dimension value and scenario.

Colours come from the Okabe-Ito palette, in its order except that yellow moves to the end of the colours (it has low
contrast on white as a line). Each value keeps its colour in every chart: vendor OIT is the same colour whether a chart
shows vendors or employers, contract type FP the same in every vendor's chart, and so on. Values shared between
dimensions (``vendor`` is a subset of ``employer``; ``unit`` reuses BQ, GCC and IH) share their colour.

Scenarios: 15 names (14 scenarios and the baseline) share 8 colours, so some repeat; the baseline is black, and the
scenarios usually compared together (Q01's Baseline, Slow AI, Fast AI and Jevons rebound, and each opposite pair such
as Strict and Light regulation) differ.

This module does not import matplotlib.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Final

from aisim import dims as d
from aisim.experiment.metadata import dims as key_dims
from aisim.experiment.metadata import keys as all_keys

ORANGE: Final = "#E69F00"
SKY_BLUE: Final = "#56B4E9"
GREEN: Final = "#009E73"
YELLOW: Final = "#F0E442"
BLUE: Final = "#0072B2"
VERMILLION: Final = "#D55E00"
PURPLE: Final = "#CC79A7"
BLACK: Final = "#000000"

OKABE_ITO: Final = (ORANGE, SKY_BLUE, GREEN, YELLOW, BLUE, VERMILLION, PURPLE, BLACK)
"""The Okabe-Ito palette in its published order."""

PALETTE: Final = (ORANGE, SKY_BLUE, GREEN, BLUE, VERMILLION, PURPLE, YELLOW, BLACK)
"""The order colours are given out in: Okabe-Ito with yellow after the other colours."""

GREY: Final = "#8A8A85"
"""Neutral: the calibration-period shading."""

INK: Final = "#3D3D3A"
"""Neutral: style-legend entries, zero lines and labels."""

RAISES: Final = BLUE
LOWERS: Final = VERMILLION
"""Sign colours of the drivers chart."""


def _by_order(values: Sequence[str]) -> dict[str, str]:
    return {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(values)}


_EMPLOYER = _by_order(d.EMPLOYERS)
_UNIT = {
    "IH": _EMPLOYER["IH"],
    "GCC": _EMPLOYER["GCC"],
    "VI": _EMPLOYER["OIT"],
    "OV": PURPLE,
    "OL": YELLOW,
    "SI_IN": _EMPLOYER["GSI"],
    "SI_ON": BLACK,
    "BQ": _EMPLOYER["BQ"],
}

DIMENSION_COLOURS: Final[Mapping[str, Mapping[str, str]]] = MappingProxyType(
    {
        "employer": MappingProxyType(_EMPLOYER),
        "vendor": MappingProxyType({v: _EMPLOYER[v] for v in d.VENDORS}),
        "unit": MappingProxyType(_UNIT),
        "type": MappingProxyType(_by_order(d.TYPES)),
        "sector": MappingProxyType(_by_order(d.SECTORS)),
        "worktype": MappingProxyType(_by_order(d.WTYPES)),
        "region": MappingProxyType(_by_order(d.REGIONS)),
        "level": MappingProxyType(_by_order(d.LEVELS)),
    }
)
"""Dimension name to value to colour, for the 8 dimensions of the catalogue."""

SCENARIO_COLOURS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "Baseline": BLACK,
        "Base": BLACK,
        "Slow AI": SKY_BLUE,
        "Fast AI": VERMILLION,
        "Jevons rebound": GREEN,
        "Strict regulation": BLUE,
        "Light regulation": ORANGE,
        "Compute shock": PURPLE,
        "Visa crackdown": YELLOW,
        "Visa relaxation": GREEN,
        "Downturn": PURPLE,
        "Demand stalls": BLUE,
        "Demand boom": ORANGE,
        "GCC wave persists": SKY_BLUE,
        "GCC wave fades": VERMILLION,
    }
)
"""Scenario label (``"Baseline"`` for None) to colour."""


def scenario_colour(label: str, position: int = 0) -> str:
    """The colour of a scenario label; an unknown label takes the palette colour at ``position``."""
    return SCENARIO_COLOURS.get(label, PALETTE[position % len(PALETTE)])


def key_colours(names: Sequence[str]) -> dict[str, str]:
    """A colour per name: by the one dimension the catalogue keys differ in, else by position in ``PALETTE``.

    If every name is a catalogue key, all have the same dimension names, and exactly one dimension's value differs
    between them, each takes that value's colour (so ``Mix_OIT_FP`` and ``Mix_GSI_FP`` are both FP's colour in their
    vendors' charts). Otherwise (computed series, mixed families) the colours go by position.
    """
    known = set(all_keys())
    if names and all(n in known for n in names):
        ds = [key_dims(n) for n in names]
        if all(set(x) == set(ds[0]) for x in ds):
            varying = [k for k in ds[0] if len({x[k] for x in ds}) > 1]
            if len(varying) == 1 and varying[0] in DIMENSION_COLOURS:
                cmap = DIMENSION_COLOURS[varying[0]]
                if all(x[varying[0]] in cmap for x in ds):
                    return {n: cmap[x[varying[0]]] for n, x in zip(names, ds, strict=True)}
    return {n: PALETTE[i % len(PALETTE)] for i, n in enumerate(names)}
