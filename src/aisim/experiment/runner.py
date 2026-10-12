"""The experiment API: ``Experiment`` (the question) and ``run_experiment`` (many runs across cores).

A question combines four layers, applied lowest to highest: the baseline, an optional named scenario
(``aisim.scenarios.SCENARIOS``), fixed ``overrides`` (and ``tables``), and sampled or explicit per-run values. A
parameter both fixed and sampled is an error.

- **Seeding.** Every sample is drawn in the parent from one ``np.random.default_rng(seed)``, in the order the levers
  are declared (``aisim.experiment.sampling``).
- **Chunks.** All batch inputs are built in the parent, split into contiguous chunks of ``chunk_size`` runs, run with
  ``run_batch`` in a spawn-context process pool, and reassembled in chunk order whatever order they finish in. Runs in
  a batch never interact, so the result is bit-identical for any worker count and chunk size.
- **Validation.** With ``validate=True`` (the default) every rule of ``aisim.experiment.validate`` is checked before
  any run starts; ``validate=False`` skips them, and ``valid`` (``BatchResult.finite``) still marks each run.

Levers act from 2024, as in the prototype (and the goldens): 11 of the 23 scenario and tornado levers change the
2024-2026 calibration window (recon 04 H). Windows spawns worker processes by importing the caller's script, so a
script that calls ``run_experiment`` with more than one worker must guard its entry point with
``if __name__ == "__main__":``.
"""

from __future__ import annotations

import multiprocessing
import os
import warnings
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
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
from aisim.experiment.results import ExperimentResult
from aisim.experiment.sampling import Distribution, Method, draw
from aisim.experiment.validate import support_errors, validate
from aisim.params import Params, Table
from aisim.scenarios import SCENARIOS
from aisim.state import load_initial_state

MEMORY_WARN_BYTES: Final = 4 * 2**30
"""Warn when the parent's estimated peak memory for the recorded series (about twice the data) exceeds this."""

RECORDABLE: Final = (*ROW_KEYS, *EXTRA_KEYS)


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
    res = run_batch(
        params, ai_on=chunk.ai_on, dt=chunk.dt, stop=chunk.stop, record_every=chunk.record_every, outputs=chunk.keys
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
    the baseline. ``AdoptC0`` keeps its shipped value unless ``pC``, ``qC`` or ``AC0`` is overridden."""
    p = Params.baseline()
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
    base = Params.baseline().scalars
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
    chunk_size: int = 500,
    validate: bool = True,
    keep_state: bool = False,
) -> ExperimentResult:
    """Run the experiment and return its results.

    - ``outputs`` (required): row keys, extras and derived names (``aisim.catalogue()``), or ``"all"`` for every row
      key and extra. A derived name records the keys it needs.
    - ``workers`` defaults to ``min(8, os.cpu_count())``; with one worker (or one chunk) the runs execute in this
      process, with no pool. ``chunk_size`` is the runs per ``run_batch`` call.
    - ``validate=False`` skips the input checks (``valid`` still marks failed runs).
    - ``keep_state=True`` also returns every run's final state and stock minimums.

    Raises ``ValidationError`` (before any run) for invalid inputs, ``KeyError`` for unknown names and ``ValueError``
    for an inconsistent experiment. Warns when the recorded series would need more than ``MEMORY_WARN_BYTES``.
    """
    record, derived = resolve_outputs(outputs, record_every)
    conflict = sorted(set(exp.overrides) & set(exp.sample) | set(exp.overrides) & set(_columns(exp.samples)))
    if conflict:
        raise ValueError(f"parameter(s) both fixed and sampled: {conflict}")
    params, set_on_top = fixed_params(exp)
    if validate and exp.samples is None and support_errors(exp.sample):
        # The values cannot be drawn: raise the support errors with every check on the fixed values.
        _validate(params, set_on_top, exp, {}, dt)
    samples = design(exp)
    n = len(samples)
    sampled = {str(c): samples[c].to_numpy(dtype=np.float64) for c in samples.columns}
    if validate:
        _validate(params, set_on_top, exp, sampled, dt)

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
    bounds = [(a, min(a + chunk_size, n)) for a in range(0, n, max(1, chunk_size))]
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
        )
        for i, (lo, hi) in enumerate(bounds)
    ]
    n_workers = min(_default_workers() if workers is None else workers, len(chunks))
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
        "experiment": exp,
        "seed": exp.seed,
        "outputs": outputs if isinstance(outputs, str) else list(outputs),
        "record_every": record_every,
        "dt": dt,
        "stop": stop,
        "workers": n_workers,
        "chunk_size": chunk_size,
        "validate": validate,
        "versions": {pkg: version(pkg) for pkg in ("ai-it-labour-sim", "numpy", "pandas", "scipy")},
        "NPY_DISABLE_CPU_FEATURES": os.environ.get("NPY_DISABLE_CPU_FEATURES"),
        "n_invalid": int((~valid).sum()),
    }
    return ExperimentResult(
        samples=samples, years=years, series=series, valid=valid, meta=meta, final_state=final_state, mins=mins
    )


def _columns(df: pd.DataFrame | None) -> set[str]:
    return set() if df is None else {str(c) for c in df.columns}


def _default_workers() -> int:
    return min(8, os.cpu_count() or 1)


def _validate(
    params: Params, set_on_top: Mapping[str, float | None], exp: Experiment, sampled: Mapping[str, F], dt: float
) -> None:
    # Any: a table override is one- or two-dimensional.
    tables: Mapping[str, Any] = exp.tables
    sample = exp.sample if exp.samples is None else None
    validate(
        params, init=load_initial_state(), dt=dt, overrides=set_on_top, tables=tables, sampled=sampled, sample=sample
    )
