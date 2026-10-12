"""The experiment API: ask a question of the model with many runs and get pandas results.

``Experiment`` describes the question (scenario, fixed overrides, sampled levers), ``run_experiment`` validates it and
runs it across cores with the batched engine, and ``ExperimentResult`` holds the series with percentile bands, ratios
to 2024, derived outputs and the Q3 outcome test. ``domains()``, ``catalogue()`` and ``keys()`` describe the
parameters and the outputs.

The submodules are ``runner``, ``validate`` (``validate()``, the rules), ``sampling``, ``results``, ``derived``,
``inputs`` and ``metadata`` (the data-table loaders).
"""

from aisim.experiment.metadata import catalogue, domains, keys
from aisim.experiment.results import ExperimentResult, pct
from aisim.experiment.runner import Experiment, run_experiment
from aisim.experiment.sampling import Choice, Distribution, Fixed, Triangular, TruncNormal, Uniform
from aisim.experiment.validate import ValidationError, Violation

__all__ = [
    "Choice",
    "Distribution",
    "Experiment",
    "ExperimentResult",
    "Fixed",
    "Triangular",
    "TruncNormal",
    "Uniform",
    "ValidationError",
    "Violation",
    "catalogue",
    "domains",
    "keys",
    "pct",
    "run_experiment",
]
