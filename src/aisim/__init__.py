"""System Dynamics model of AI's impact on IT employment, contract mix and vendor viability.

The ``aisim`` package is a port of the frozen Python prototype in ``reference/prototype/``, covering India and onshore
(North America and Europe) from 2024 to 2040. The scalar engine (``aisim.scalar``) reproduces the prototype bit for
bit. ``run()`` runs it once; ``Params`` holds the calibrated parameters and ``SCENARIOS`` the named scenarios.
"""

from aisim.params import Params
from aisim.scalar.engine import RunResult, run
from aisim.scenarios import SCENARIOS
from aisim.state import State, load_initial_state

__version__ = "0.1.0"

__all__ = ["SCENARIOS", "Params", "RunResult", "State", "__version__", "load_initial_state", "run"]
