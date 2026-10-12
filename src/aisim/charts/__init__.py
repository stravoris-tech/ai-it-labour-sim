"""Charts of experiment results, with years on the x-axis: ``bands``, ``scenarios``, ``lines``, ``drivers`` and
``save``.

Needs the optional ``charts`` extra (matplotlib): ``pip install 'ai-it-labour-sim[charts]'``. Importing this package
does not import matplotlib; the first chart does, and raises an ``ImportError`` naming the extra if it is missing.
Figures are drawn on the Agg canvas without ``pyplot``.

- Default window 2024-2040 (``window=`` on every year chart); the 2024-2026 calibration period is shaded unless
  ``shade=False``. Bands there reflect lever uncertainty applied from 2024 (see ``aisim.charts.core``).
- Y-labels come from ``catalogue().unit``, with " (unit inferred)" where the catalogue inferred it; ``ylabel=``
  overrides.
- Colours are fixed per dimension value and scenario (``aisim.charts.colours``), colour-blind safe.
- Every artist has a ``gid`` (``median:<key>``, ``band:<key>``, ``baseline:<key>``, ``shade:calibration``, ...).
"""

from aisim.charts.colours import DIMENSION_COLOURS, SCENARIO_COLOURS, key_colours, scenario_colour
from aisim.charts.core import bands, drivers, lines, scenarios
from aisim.charts.output import save

__all__ = [
    "DIMENSION_COLOURS",
    "SCENARIO_COLOURS",
    "bands",
    "drivers",
    "key_colours",
    "lines",
    "save",
    "scenario_colour",
    "scenarios",
]
