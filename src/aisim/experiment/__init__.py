"""The experiment API: ask a question of the model with many runs and get pandas results.

``Experiment`` describes the question (scenario, fixed overrides, sampled levers), ``run_experiment`` validates it and
runs it across cores with the batched engine, and ``ExperimentResult`` holds the series with percentile bands, ratios
to 2024, derived outputs, the Q3 outcome test and save/load. ``run_scenarios`` runs several scenarios on the same
samples (``ScenarioResult``); ``drivers`` ranks sampled levers by rank correlation and ``shift_share`` splits a
weighted average's change. ``domains()``, ``catalogue()``, ``keys()`` and ``dims()`` describe the parameters and the
outputs.

The submodules are ``runner``, ``scenarios`` (``run_scenarios``), ``validate`` (``validate()``, the rules),
``sampling``, ``results``, ``analysis`` (``drivers``, ``shift_share``), ``derived``, ``inputs``, ``meta`` (JSON-safe
meta and provenance) and ``metadata`` (the data-table loaders).
"""

from aisim.experiment.analysis import drivers, shift_share
from aisim.experiment.metadata import catalogue, dims, domains, keys
from aisim.experiment.results import ExperimentResult, pct
from aisim.experiment.runner import Experiment, auto_chunk_size, run_experiment
from aisim.experiment.sampling import Choice, Distribution, Fixed, Triangular, TruncNormal, Uniform
from aisim.experiment.scenarios import ScenarioResult, run_scenarios
from aisim.experiment.validate import ValidationError, Violation

__all__ = [
    "Choice",
    "Distribution",
    "Experiment",
    "ExperimentResult",
    "Fixed",
    "ScenarioResult",
    "Triangular",
    "TruncNormal",
    "Uniform",
    "ValidationError",
    "Violation",
    "auto_chunk_size",
    "catalogue",
    "dims",
    "domains",
    "drivers",
    "keys",
    "pct",
    "run_experiment",
    "run_scenarios",
    "shift_share",
]
