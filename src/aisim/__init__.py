"""System Dynamics model of AI's impact on IT employment, contract mix and vendor viability.

The ``aisim`` package is a port of the frozen Python prototype in ``reference/prototype/``, covering India and onshore
(North America and Europe) from 2024 to 2040. The scalar engine (``aisim.scalar``) reproduces the prototype bit for
bit. ``run()`` runs it once; ``Params`` holds the calibrated parameters and ``SCENARIOS`` the named scenarios. The
batched engine (``aisim.batch``) runs many at once: ``run_batch()`` advances N runs together as numpy arrays, with
``BatchParams`` and ``BatchState`` holding their parameters and states, and matches the scalar engine to 1e-12.

The experiment API (``aisim.experiment``) asks questions with many runs: an ``Experiment`` combines a scenario, fixed
overrides and sampled levers (``Uniform``, ``Triangular``, ``TruncNormal``, ``Choice``, ``Fixed``);
``run_experiment()`` validates it (``ValidationError``) and runs it across cores, returning an ``ExperimentResult``
with percentile bands, ratios to 2024, derived outputs and the Q3 test. ``run_scenarios()`` runs several scenarios on
the same samples (``ScenarioResult``). ``domains()``, ``catalogue()`` and ``keys()`` describe the parameters and
outputs.

Charts (``aisim.charts``, needs the ``charts`` extra: matplotlib) and one-page reports (``aisim.report``) turn results
into figures and self-contained HTML.
"""

from aisim.batch.engine import BatchResult, run_batch
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.experiment import (
    Choice,
    Experiment,
    ExperimentResult,
    Fixed,
    Noise,
    ScenarioResult,
    Triangular,
    TruncNormal,
    Uniform,
    ValidationError,
    catalogue,
    domains,
    keys,
    run_experiment,
    run_scenarios,
)
from aisim.params import Params
from aisim.scalar.engine import RunResult, run
from aisim.scenarios import SCENARIOS
from aisim.state import State, load_initial_state

__version__ = "0.1.0"

__all__ = [
    "SCENARIOS",
    "BatchParams",
    "BatchResult",
    "BatchState",
    "Choice",
    "Experiment",
    "ExperimentResult",
    "Fixed",
    "Noise",
    "Params",
    "RunResult",
    "ScenarioResult",
    "State",
    "Triangular",
    "TruncNormal",
    "Uniform",
    "ValidationError",
    "__version__",
    "catalogue",
    "domains",
    "keys",
    "load_initial_state",
    "run",
    "run_batch",
    "run_experiment",
    "run_scenarios",
]
