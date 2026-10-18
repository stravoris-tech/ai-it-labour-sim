"""The one colour map: a fixed, colour-blind-safe colour and line style for every dimension value and scenario.

Colours come from the Okabe-Ito palette, in its order except that yellow moves to the end of the hues (it has low
contrast on white as a line), plus wine and indigo (from Paul Tol's muted scheme) before it: 10 colours, black last.
Each value keeps its colour in every chart: vendor OIT is the same colour whether a chart shows vendors or employers,
contract type FP the same in every vendor's chart, and so on. Values shared between dimensions (``vendor`` is a subset
of ``employer``; ``unit`` reuses BQ, GCC and IH) share their colour.

**Beyond ten series** the colours repeat with a different line style: series 1-10 are solid, 11-20 dashed and 21-30
dotted, so the (colour, style) pairs stay unique up to 30 series (``key_colours`` with ``key_styles``).

Scenarios: each of the 16 labels (14 scenarios, the baseline and the stress set of ``STRESS_SCENARIOS``) has its
own (colour, style) pair. The baseline is
black (and the ``Base`` scenario, the same run, black dashed); Baseline, Fast AI and Slow AI are solid; the
scenarios of each contrast pair (Fast / Slow AI, Strict / Light regulation, Compute shock / Downturn, Visa crackdown /
relaxation, GCC wave persists / fades, Demand boom / stalls) differ in colour.

Measured with the method of recon 07 D4: WCAG 2 contrast on white, and the CIE76 distance in Lab after the Machado et
al. 2009 simulation at severity 1, applied in linear RGB.

| Colour | Hex | Contrast on white |
| --- | --- | --- |
| orange | ``#E69F00`` | 2.25 |
| sky blue | ``#56B4E9`` | 2.31 |
| green | ``#009E73`` | 3.42 |
| blue | ``#0072B2`` | 5.19 |
| vermillion | ``#D55E00`` | 3.87 |
| purple | ``#CC79A7`` | 3.06 |
| wine | ``#882255`` | 8.73 |
| indigo | ``#332288`` | 12.17 |
| yellow | ``#F0E442`` | 1.32 |
| black | ``#000000`` | 21.00 |

Smallest pairwise distance within the 10 colours: normal vision 26.4 (sky blue / blue), protan 20.7 (sky blue /
purple), deutan 17.0 (orange / yellow), tritan 16.1 (sky blue / green). These are the 8-colour palette's own minima:
wine and indigo are further than that from every colour under all four simulations.

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
WINE: Final = "#882255"
INDIGO: Final = "#332288"

OKABE_ITO: Final = (ORANGE, SKY_BLUE, GREEN, YELLOW, BLUE, VERMILLION, PURPLE, BLACK)
"""The Okabe-Ito palette in its published order."""

PALETTE: Final = (ORANGE, SKY_BLUE, GREEN, BLUE, VERMILLION, PURPLE, WINE, INDIGO, YELLOW, BLACK)
"""The order colours are given out in: Okabe-Ito, then wine and indigo, with yellow after every other hue and black
last."""

SOLID: Final = "-"
DASHED: Final = "--"
DOTTED: Final = ":"
LINE_STYLES: Final = (SOLID, DASHED, DOTTED)
"""The line styles in the order they are given out: each round through ``PALETTE`` takes the next one."""

GREY: Final = "#8A8A85"
"""Neutral: the calibration-period shading."""

INK: Final = "#3D3D3A"
"""Neutral: style-legend entries, zero lines and labels."""

RAISES: Final = BLUE
LOWERS: Final = VERMILLION
"""Sign colours of the drivers chart."""


def _colour_at(position: int) -> str:
    return PALETTE[position % len(PALETTE)]


def _style_at(position: int) -> str:
    return LINE_STYLES[(position // len(PALETTE)) % len(LINE_STYLES)]


def _by_order(values: Sequence[str]) -> dict[str, str]:
    return {v: _colour_at(i) for i, v in enumerate(values)}


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

_SCENARIO_LINES: Final = {
    "Baseline": (BLACK, SOLID),
    "Base": (BLACK, DASHED),
    "Slow AI": (SKY_BLUE, SOLID),
    "Fast AI": (VERMILLION, SOLID),
    "Jevons rebound": (GREEN, SOLID),
    "Strict regulation": (BLUE, SOLID),
    "Light regulation": (ORANGE, SOLID),
    "Compute shock": (PURPLE, SOLID),
    "Downturn": (WINE, SOLID),
    "Visa crackdown": (YELLOW, SOLID),
    "Visa relaxation": (INDIGO, SOLID),
    "Demand stalls": (BLUE, DASHED),
    "Demand boom": (ORANGE, DASHED),
    "GCC wave persists": (SKY_BLUE, DASHED),
    "GCC wave fades": (VERMILLION, DASHED),
    "Fast AI + OIT price shock": (VERMILLION, DOTTED),
}

SCENARIO_COLOURS: Final[Mapping[str, str]] = MappingProxyType({k: c for k, (c, _) in _SCENARIO_LINES.items()})
"""Scenario label (``"Baseline"`` for None) to colour. The ``"Base"`` scenario (no overrides) is the same run as
the baseline: black too, but dashed."""

SCENARIO_STYLES: Final[Mapping[str, str]] = MappingProxyType({k: s for k, (_, s) in _SCENARIO_LINES.items()})
"""Scenario label to line style. With ``SCENARIO_COLOURS``, each of the 16 labels has its own pair."""


def scenario_colour(label: str, position: int = 0) -> str:
    """The colour of a scenario label; an unknown label takes the palette colour at ``position``."""
    return SCENARIO_COLOURS.get(label, _colour_at(position))


def scenario_style(label: str, position: int = 0) -> str:
    """The line style of a scenario label; an unknown label takes the style at ``position``, as ``key_styles``."""
    return SCENARIO_STYLES.get(label, _style_at(position))


def _by_dimension(names: Sequence[str]) -> dict[str, str] | None:
    """Each name's dimension-value colour, if the names are catalogue keys that differ in exactly one dimension."""
    known = set(all_keys())
    if names and all(n in known for n in names):
        ds = [key_dims(n) for n in names]
        if all(set(x) == set(ds[0]) for x in ds):
            varying = [k for k in ds[0] if len({x[k] for x in ds}) > 1]
            if len(varying) == 1 and varying[0] in DIMENSION_COLOURS:
                cmap = DIMENSION_COLOURS[varying[0]]
                if all(x[varying[0]] in cmap for x in ds):
                    return {n: cmap[x[varying[0]]] for n, x in zip(names, ds, strict=True)}
    return None


def key_colours(names: Sequence[str]) -> dict[str, str]:
    """A colour per name: by the one dimension the catalogue keys differ in, else by position in ``PALETTE``.

    If every name is a catalogue key, all have the same dimension names, and exactly one dimension's value differs
    between them, each takes that value's colour (so ``Mix_OIT_FP`` and ``Mix_GSI_FP`` are both FP's colour in their
    vendors' charts). Otherwise (computed series, mixed families) the colours go by position and repeat after 10
    series; ``key_styles`` tells the rounds apart.
    """
    by_dimension = _by_dimension(names)
    if by_dimension is not None:
        return by_dimension
    return {n: _colour_at(i) for i, n in enumerate(names)}


def key_styles(names: Sequence[str]) -> dict[str, str]:
    """A line style per name, to go with ``key_colours``.

    Dimension colours are solid (each value has its own colour). By position, series 1-10 are solid, 11-20 dashed and
    21-30 dotted, so the (colour, style) pairs stay unique up to 30 series.
    """
    if _by_dimension(names) is not None:
        return dict.fromkeys(names, SOLID)
    return {n: _style_at(i) for i, n in enumerate(names)}
