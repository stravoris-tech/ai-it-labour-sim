"""The experiment API: ``Experiment`` (the question) and ``run_experiment`` (many runs across cores).

A question combines four layers, applied lowest to highest: the baseline, an optional named scenario
(``aisim.scenarios.SCENARIOS``), fixed ``overrides`` (and ``tables``), and sampled or explicit per-run values. A
parameter both fixed and sampled is an error, whether ``overrides`` or the scenario fixes it. An override may replace a
scenario's value. To compare scenarios on the same samples, use ``aisim.experiment.scenarios.run_scenarios``.

- **Seeding.** Every sample is drawn in the parent from one ``np.random.default_rng(seed)``, in the order the levers
  are declared (``aisim.experiment.sampling``).
- **Chunks.** All batch inputs are built in the parent, split into contiguous chunks of ``chunk_size`` runs, run with
  ``run_batch`` in a spawn-context process pool, and reassembled in chunk order whatever order they finish in. Runs in
  a batch never interact, so the result is bit-identical for any worker count and chunk size. ``chunk_size=None``
  (the default) chooses it with ``auto_chunk_size`` (recon 05 C).
- **Validation.** With ``validate=True`` (the default) every rule of ``aisim.experiment.validate`` is checked before
  any run starts; ``validate=False`` skips them, and ``valid`` (``BatchResult.finite``) still marks each run.

**Perturb from year Y.** By default levers act from 2024, as in the prototype (and the goldens): 11 of the 23 scenario
and tornado levers change the 2024-2026 calibration window (recon 04 H). With ``perturb_from = Y`` the calibrated
baseline runs unchanged until Y and everything that differs (scenario, overrides, tables, samples, noise) acts from Y
(``aisim.perturb``): phase 1 runs once in the parent and every chunk restarts from its state. ``noise`` adds seeded
process noise from Y (``aisim.noise``); each run's stream is keyed by its index in the design, generated in its chunk.

Windows spawns worker processes by importing the caller's script, so a
script that calls ``run_experiment`` with more than one worker must guard its entry point with
``if __name__ == "__main__":``.
"""

from __future__ import annotations

import math
import multiprocessing
import os
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from importlib.metadata import version
from typing import Any, Final, Literal

import numpy as np
import pandas as pd

from aisim.batch.engine import run_batch
from aisim.batch.record import EXTRA_KEYS, ROW_KEYS
from aisim.batch.state import BatchState
from aisim.batch.util import B, F
from aisim.experiment.derived import DERIVED
from aisim.experiment.inputs import batch_arrays, make_batch_params
from aisim.experiment.meta import experiment_dict, noise_dict, provenance
from aisim.experiment.results import ExperimentResult
from aisim.experiment.sampling import Distribution, Method, draw
from aisim.experiment.validate import support_errors, validate
from aisim.noise import Noise, Runs, active, ou_factors
from aisim.params import Params, Table
from aisim.perturb import Phase1, phase1, run_batch_from
from aisim.scenarios import SCENARIOS
from aisim.state import BASELINE_FILES, DEFAULT_MODEL, load_initial_state

MEMORY_WARN_BYTES: Final = 4 * 2**30
"""Warn when the parent's estimated peak memory for the recorded series (about twice the data) exceeds this."""

RECORDABLE: Final = (*ROW_KEYS, *EXTRA_KEYS)

AUTO_IN_PROCESS_MAX: Final = 200
"""Up to this many runs, ``chunk_size=None`` runs in one chunk, in this process: a pool costs about 0.3 s and only
pays from about 300 runs (recon 05 C3)."""

AUTO_CHUNK_MIN: Final = 50
AUTO_CHUNK_MAX: Final = 625


def auto_chunk_size(n: int, workers: int) -> int:
    """The runs per chunk for ``chunk_size=None``.

    ``n`` (one chunk, so in-process) up to ``AUTO_IN_PROCESS_MAX`` runs, otherwise ``min(625, max(50, ceil(n /
    workers)))``: in recon 05 C2, ``ceil(n / 8)`` was best at n = 500 and 1,000, chunk 625 at n = 5,000 and 20,000.
    """
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if n <= AUTO_IN_PROCESS_MAX:
        return max(1, n)
    return min(AUTO_CHUNK_MAX, max(AUTO_CHUNK_MIN, math.ceil(n / workers)))


@dataclass(frozen=True)
class Experiment:
    """A question: the scenario, fixed overrides, fixed table overrides and sampled levers, and the run count.

    - ``scenario``: a name in ``aisim.scenarios.SCENARIOS``, or None for the baseline.
    - ``overrides``: fixed scalar values; ``tables``: fixed table overrides (``Params.with_table``).
    - ``sample``: sampled levers, drawn in declared order; ``correlation``: Spearman targets between them.
    - ``n``, ``method`` (``"random"`` or ``"lhs"``) and ``seed`` (required whenever ``sample`` is not empty).
    - ``samples``: an explicit design, runs x parameters, used as given; it excludes ``sample``, ``method``,
      ``correlation`` and ``n`` (which may be left at 1 or set to its length). In a ``DemandGrowthLate`` column, NaN
      means None ("same as ``DemandGrowth``").
    - ``ai_on``: one switch for every run.
    - ``perturb_from``: the year Y from which everything that differs from the calibrated baseline acts (None: from
      2024). One Y per experiment, on the dt grid. Parameters that describe 2024 itself (``domains()`` column
      ``level_2024``, ``Verif`` among them) must stay at their baseline values.
    - ``noise``: process noise by channel (``aisim.noise.CHANNELS``), off by default; it needs ``perturb_from`` and a
      ``noise_seed``. No amplitude is built in.
    - ``model``: the named model (``aisim.state.BASELINE_FILES``) whose baseline every run starts from: ``"phase8"``
      (the default, ``aisim.state.DEFAULT_MODEL``), ``"phase7"`` or ``"phase8_highadoption"``.
    """

    scenario: str | None = None
    overrides: Mapping[str, float | None] = field(default_factory=dict)
    tables: Mapping[str, Table] = field(default_factory=dict)
    sample: Mapping[str, Distribution] = field(default_factory=dict)
    correlation: Mapping[tuple[str, str], float] | None = None
    n: int = 1
    method: Literal["random", "lhs"] = "random"
    seed: int | None = None
    samples: pd.DataFrame | None = None
    ai_on: bool = True
    perturb_from: float | None = None
    noise: Mapping[str, Noise] = field(default_factory=dict)
    noise_seed: int | None = None
    model: str = DEFAULT_MODEL


@dataclass(frozen=True, slots=True)
class _Chunk:
    """One chunk's inputs, sent to a worker."""

    index: int
    scalars: dict[str, F]
    tables: dict[str, F]
    dgl_is_none: B
    ai_on: bool
    dt: float
    stop: float
    record_every: float
    keys: tuple[str, ...]
    keep_state: bool
    first: Phase1 | None = None
    runs: Runs | None = None
    noise: dict[str, Noise] = field(default_factory=dict)
    noise_seed: int | None = None


@dataclass(frozen=True, slots=True)
class _ChunkResult:
    """One chunk's outputs: only the requested keys (and the state, if asked for)."""

    index: int
    years: F
    series: dict[str, F]
    finite: B
    state: dict[str, F] | None
    mins: dict[str, F] | None


def _run_chunk(chunk: _Chunk) -> _ChunkResult:
    """Run one chunk with ``run_batch`` (top level, so spawned workers can import it)."""
    params = make_batch_params(chunk.scalars, chunk.tables, chunk.dgl_is_none)
    if chunk.first is None:
        res = run_batch(
            params, ai_on=chunk.ai_on, dt=chunk.dt, stop=chunk.stop, record_every=chunk.record_every, outputs=chunk.keys
        )
    else:
        factors = None
        if active(chunk.noise):
            assert chunk.noise_seed is not None and chunk.runs is not None
            steps = round(chunk.stop / chunk.dt)
            factors = ou_factors(
                chunk.noise, chunk.noise_seed, chunk.runs, start_step=chunk.first.start_step, steps=steps, dt=chunk.dt
            )
        res = run_batch_from(
            params,
            Y=chunk.first.Y,
            dt=chunk.dt,
            stop=chunk.stop,
            record_every=chunk.record_every,
            outputs=chunk.keys,
            ai_on=chunk.ai_on,
            noise=factors,
            first=chunk.first,
        )
    return _ChunkResult(
        index=chunk.index,
        years=res.years,
        series=dict(res.series),
        finite=res.finite,
        state=res.final_state.arrays() if chunk.keep_state else None,
        mins=dict(res.mins) if chunk.keep_state else None,
    )


def resolve_outputs(outputs: Sequence[str] | Literal["all"], record_every: float) -> tuple[list[str], list[str]]:
    """``(record, derived)``: the row keys and extras to record (requested ones plus the derived outputs' needs, in
    recording order) and the derived outputs requested. Raises ``ValueError`` for an unknown name or a derived output
    that needs a finer ``record_every``."""
    if isinstance(outputs, str):
        if outputs != "all":
            raise TypeError("outputs must be a sequence of names or 'all'")
        return list(RECORDABLE), []
    names = list(outputs)
    if not names:
        raise ValueError("outputs is empty; name the keys to record (or pass 'all')")
    unknown = sorted(set(names) - set(RECORDABLE) - set(DERIVED))
    if unknown:
        raise ValueError(f"unknown output name(s): {unknown}; see aisim.catalogue()")
    derived = [name for name in names if name in DERIVED]
    wanted = {name for name in names if name not in DERIVED}
    for name in derived:
        d = DERIVED[name]
        if d.max_record_every is not None and record_every > d.max_record_every:
            raise ValueError(f"{name} needs record_every <= {d.max_record_every}, not {record_every}")
        wanted.update(d.deps)
    return [k for k in RECORDABLE if k in wanted], derived


def fixed_params(exp: Experiment) -> tuple[Params, dict[str, float | None]]:
    """The fixed parameters (baseline, then scenario, then overrides and tables) and the scalar names set on top of
    the baseline. ``AdoptC0`` keeps its shipped value unless ``pC``, ``qC`` or ``AC0`` is overridden. The baseline
    is ``exp.model``'s; an unknown model raises ``ValueError``."""
    p = Params.baseline(exp.model)
    set_on_top: dict[str, float | None] = {}
    if exp.scenario is not None:
        if exp.scenario not in SCENARIOS:
            raise KeyError(f"unknown scenario {exp.scenario!r}; scenarios: {list(SCENARIOS)}")
        scenario = dict(SCENARIOS[exp.scenario])
        if scenario:
            p = p.with_overrides(**scenario)
        set_on_top.update(scenario)
    if exp.overrides:
        p = p.with_overrides(**exp.overrides)
        set_on_top.update(exp.overrides)
    for name, values in exp.tables.items():
        p = p.with_table(name, values)
    return p, set_on_top


def design(exp: Experiment) -> pd.DataFrame:
    """The per-run values of the varying parameters: the explicit ``samples`` or a draw of ``sample``."""
    base = Params.baseline(exp.model).scalars
    if exp.samples is not None:
        df = exp.samples
        if exp.sample or exp.method != "random" or exp.correlation or exp.n not in (1, len(df)):
            raise ValueError("an explicit samples design excludes sample, method, correlation and n")
        unknown = sorted(str(c) for c in df.columns if c not in base)
        if unknown:
            raise KeyError(f"unknown parameter(s) in samples: {unknown}")
        if len(df) < 1:
            raise ValueError("samples has no runs")
        out = df.reset_index(drop=True).astype(np.float64)
        out.index.name = "run"
        return out
    if exp.n < 1:
        raise ValueError("n must be at least 1")
    if not exp.sample:
        if exp.correlation:
            raise ValueError("correlation needs sampled levers")
        return pd.DataFrame(index=pd.RangeIndex(exp.n, name="run"))
    unknown = sorted(k for k in exp.sample if k not in base)
    if unknown:
        raise KeyError(f"unknown parameter(s) in sample: {unknown}")
    if exp.seed is None:
        raise ValueError("a seed is required when levers are sampled (no hidden randomness)")
    method: Method = exp.method
    return draw(exp.sample, exp.n, seed=exp.seed, method=method, correlation=exp.correlation)


def estimated_bytes(n: int, n_years: int, n_keys: int) -> int:
    """The parent's estimated peak for ``n_keys`` recorded series: about twice the data (chunk parts and the
    concatenated copy; recon 04 C2)."""
    return 2 * 8 * n * n_years * n_keys


def run_experiment(
    exp: Experiment,
    *,
    outputs: Sequence[str] | Literal["all"],
    record_every: float = 1.0,
    dt: float = 1 / 16,
    stop: float = 16.0,
    workers: int | None = None,
    chunk_size: int | None = None,
    validate: bool = True,
    keep_state: bool = False,
) -> ExperimentResult:
    """Run the experiment and return its results.

    - ``outputs`` (required): row keys, extras and derived names (``aisim.catalogue()``), or ``"all"`` for every row
      key and extra. A derived name records the keys it needs.
    - ``workers`` defaults to ``min(8, os.cpu_count())``; with one worker (or one chunk) the runs execute in this
      process, with no pool. ``chunk_size`` is the runs per ``run_batch`` call; None (the default) chooses it with
      ``auto_chunk_size``, which runs up to 200 runs in this process.
    - ``validate=False`` skips the input checks (``valid`` still marks failed runs).
    - ``keep_state=True`` also returns every run's final state and stock minimums.

    Raises ``ValidationError`` (before any run) for invalid inputs, ``KeyError`` for unknown names and ``ValueError``
    for an inconsistent experiment, including a parameter that ``overrides`` or the scenario fixes and ``sample`` or
    ``samples`` also varies. Warns when the recorded series would need more than ``MEMORY_WARN_BYTES``.
    """
    return execute(
        exp,
        outputs=outputs,
        record_every=record_every,
        dt=dt,
        stop=stop,
        workers=workers,
        chunk_size=chunk_size,
        validate=validate,
        keep_state=keep_state,
    )


def execute(
    exp: Experiment,
    *,
    outputs: Sequence[str] | Literal["all"],
    record_every: float = 1.0,
    dt: float = 1 / 16,
    stop: float = 16.0,
    workers: int | None = None,
    chunk_size: int | None = None,
    validate: bool = True,
    keep_state: bool = False,
    noise_index: Runs | None = None,
) -> ExperimentResult:
    """``run_experiment``, with ``noise_index``: each run's index for its noise stream (default: its row in the
    design). ``run_scenarios`` passes the index within each block, so run i has the same noise in every scenario."""
    record, derived = resolve_outputs(outputs, record_every)
    varied = set(exp.sample) | _columns(exp.samples)
    conflict = sorted(set(exp.overrides) & varied)
    if conflict:
        raise ValueError(f"parameter(s) both fixed and sampled: {conflict}")
    if exp.scenario is not None and exp.scenario in SCENARIOS:
        conflict = sorted(set(SCENARIOS[exp.scenario]) & varied)
        if conflict:
            raise ValueError(
                f"parameter(s) both fixed and sampled: {conflict} (set by scenario {exp.scenario!r}); sample other "
                "levers, or use run_scenarios to pin them per scenario"
            )
    if workers is not None and workers < 1:
        raise ValueError("workers must be at least 1")
    known = known_model(exp) if validate else exp
    params, set_on_top = fixed_params(known)
    if validate and exp.samples is None and support_errors(exp.sample):
        # The values cannot be drawn: raise the support errors with every check on the fixed values.
        _validate(params, set_on_top, exp, {}, dt, stop)
    samples = design(known)
    n = len(samples)
    sampled = {str(c): samples[c].to_numpy(dtype=np.float64) for c in samples.columns}
    if validate:
        _validate(params, set_on_top, exp, sampled, dt, stop)
    noisy = active(exp.noise)
    if noisy and exp.perturb_from is None:
        raise ValueError(f"noise on {noisy} needs perturb_from (no noise in the calibration period)")
    if noisy and exp.noise_seed is None:
        raise ValueError("a noise_seed is required when any noise sigma > 0 (no hidden randomness)")
    runs = np.arange(n) if noise_index is None else np.asarray(noise_index, dtype=np.int64)
    if runs.shape != (n,):
        raise ValueError(f"noise_index has {runs.size} values for {n} runs")

    steps = round(stop / dt)
    rk = max(1, round(record_every / dt))
    n_years = steps // rk + 1
    need = estimated_bytes(n, n_years, len(record) + len(derived))
    if need > MEMORY_WARN_BYTES:
        warnings.warn(
            f"the recorded series need about {need / 2**30:.1f} GiB in this process "
            f"({n} runs x {n_years} years x {len(record) + len(derived)} keys); record fewer keys or runs",
            ResourceWarning,
            stacklevel=2,
        )

    scalars, tables, dgl = batch_arrays(params, sampled, n)
    first = None
    if exp.perturb_from is not None:
        first = phase1(
            exp.perturb_from, base=Params.baseline(exp.model), dt=dt, record_every=record_every, outputs=record
        )
    asked = _default_workers() if workers is None else workers
    size = auto_chunk_size(n, asked) if chunk_size is None else max(1, chunk_size)
    bounds = [(a, min(a + size, n)) for a in range(0, n, size)]
    chunks = [
        _Chunk(
            index=i,
            scalars={k: a[lo:hi] for k, a in scalars.items()},
            tables={k: a[lo:hi] for k, a in tables.items()},
            dgl_is_none=dgl[lo:hi],
            ai_on=exp.ai_on,
            dt=dt,
            stop=stop,
            record_every=record_every,
            keys=tuple(record),
            keep_state=keep_state,
            first=first,
            runs=runs[lo:hi],
            noise=dict(exp.noise),
            noise_seed=exp.noise_seed,
        )
        for i, (lo, hi) in enumerate(bounds)
    ]
    n_workers = min(asked, len(chunks))
    if n_workers < 1:
        raise ValueError("workers must be at least 1")
    parts: list[_ChunkResult | None] = [None] * len(chunks)
    if n_workers == 1:
        for c in chunks:
            parts[c.index] = _run_chunk(c)
    else:
        ctx = multiprocessing.get_context("spawn")
        with ctx.Pool(processes=n_workers) as pool:
            for res in pool.imap_unordered(_run_chunk, chunks):
                parts[res.index] = res
    done = [p for p in parts if p is not None]
    assert len(done) == len(chunks)

    series = {k: np.concatenate([p.series[k] for p in done]) for k in record}
    valid = np.concatenate([p.finite for p in done])
    years = done[0].years
    for name in derived:
        series[name] = DERIVED[name].compute(series, years)
    final_state = mins = None
    if keep_state:
        final_state = BatchState(
            **{k: np.concatenate([p.state[k] for p in done if p.state]) for k in done[0].state or {}}
        )
        mins = {k: np.concatenate([p.mins[k] for p in done if p.mins]) for k in done[0].mins or {}}
    meta = {
        "experiment": experiment_dict(exp),
        "seed": exp.seed,
        "n": n,
        "outputs": outputs if isinstance(outputs, str) else list(outputs),
        "record_every": record_every,
        "dt": dt,
        "stop": stop,
        "workers": n_workers,
        "chunk_size": size,
        "chunk_size_auto": chunk_size is None,
        "validate": validate,
        "versions": {pkg: version(pkg) for pkg in ("ai-it-labour-sim", "numpy", "pandas", "scipy")},
        "NPY_DISABLE_CPU_FEATURES": os.environ.get("NPY_DISABLE_CPU_FEATURES"),
        "n_invalid": int((~valid).sum()),
        "perturb_from": exp.perturb_from,
        "noise": noise_dict(exp.noise),
        "noise_seed": exp.noise_seed,
        **provenance(),
    }
    return ExperimentResult(
        samples=samples, years=years, series=series, valid=valid, meta=meta, final_state=final_state, mins=mins
    )


def check_supports(exp: Experiment, dt: float = 1 / 16, stop: float = 16.0) -> None:
    """Raise ``ValidationError`` if a sampled distribution's support leaves its parameter's domain, as
    ``run_experiment`` does before drawing (with every check on the fixed values)."""
    if exp.samples is None and support_errors(exp.sample):
        params, set_on_top = fixed_params(known_model(exp))
        _validate(params, set_on_top, exp, {}, dt, stop)


def known_model(exp: Experiment) -> Experiment:
    """``exp``, or with an unknown model ``exp`` on the default model (``DEFAULT_MODEL``): validation then checks every
    other rule against it and reports the unknown model in the same ``ValidationError`` (validate rule 10)."""
    return exp if exp.model in BASELINE_FILES else replace(exp, model=DEFAULT_MODEL)


def _columns(df: pd.DataFrame | None) -> set[str]:
    return set() if df is None else {str(c) for c in df.columns}


def _default_workers() -> int:
    return min(8, os.cpu_count() or 1)


def _validate(
    params: Params,
    set_on_top: Mapping[str, float | None],
    exp: Experiment,
    sampled: Mapping[str, F],
    dt: float,
    stop: float,
) -> None:
    # Any: a table override is one- or two-dimensional.
    tables: Mapping[str, Any] = exp.tables
    sample = exp.sample if exp.samples is None else None
    validate(
        params,
        init=load_initial_state(),
        dt=dt,
        overrides=set_on_top,
        tables=tables,
        sampled=sampled,
        sample=sample,
        perturb_from=exp.perturb_from,
        stop=stop,
        ai_on=exp.ai_on,
        noise=exp.noise,
        noise_seed=exp.noise_seed,
        model=exp.model,
    )
