"""Process noise: seeded Ornstein-Uhlenbeck factors on six channels, off by default.

A run's noise is a factor ``exp(x)`` per channel and step, applied at one point in each engine (recon 06 C1):

- ``cap``: ``PAI``, the productivity of AI-assisted work (S2);
- ``demand``: ``G``, the underlying demand index, which also feeds budgets, enrolment, the visa cap and seats (S2);
- ``budget``: ``BudgetGrowth``, IT budget growth (S13a);
- ``aicost``: ``AICostPerUnit``, delivery AI cost per automated unit (S9);
- ``adoption``: ``AdoptC``, the consumer AI adoption flow (S13c);
- ``anchor``: ``Anchor``, the client price anchor on new FP, MS and OB prices (S10).

``x`` is an exact Ornstein-Uhlenbeck process, ``x[k+1] = phi x[k] + sigma sqrt(1 - phi^2) w[k]`` with
``phi = exp(-dt / tau)``: its stationary sd is ``sigma`` and its one-year autocorrelation ``exp(-1 / tau)`` at any dt
(recon 06 C2). It starts at 0 at the perturb year Y, so the factor is exactly 1 up to and including Y, and
``exp(x) > 0`` keeps every crash site safe.

**Streams.** Run ``i`` (its index in the design) draws from ``SeedSequence(noise_seed, spawn_key=(i,))``: one
``(steps after Y, 6)`` block of standard normals, in ``CHANNELS`` order, whatever channels are on. A run's noise
therefore depends only on the seed, its index and the noise spec: not on the chunking, the worker count, the other runs
or the other channels, and never on the lever-sampling stream. ``SeedSequence.spawn`` is not used (it is stateful).

No amplitude is built in: ``Noise`` has no default ``sigma``, and an experiment has no noise unless it names some.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from aisim.batch.util import F

Runs = Sequence[int] | NDArray[np.int64]
"""The runs' indices in their design, which key their streams."""

CHANNELS: Final = ("cap", "demand", "budget", "aicost", "adoption", "anchor")
"""The noise channels, in stream order."""


@dataclass(frozen=True, slots=True)
class Noise:
    """The noise on one channel: stationary sd ``sigma`` of ``x`` (the factor is ``exp(x)``) and correlation time
    ``tau`` in years. ``sigma = 0`` is off."""

    sigma: float
    tau: float = 1.0


def active(noise: Mapping[str, Noise]) -> list[str]:
    """The channels with ``sigma > 0``, in ``CHANNELS`` order. Raises ``KeyError`` for an unknown channel."""
    unknown = sorted(set(noise) - set(CHANNELS))
    if unknown:
        raise KeyError(f"unknown noise channel(s) {unknown}; channels: {list(CHANNELS)}")
    return [c for c in CHANNELS if c in noise and noise[c].sigma > 0]


def ou_paths(
    noise: Mapping[str, Noise], seed: int, runs: Runs, *, start_step: int, steps: int, dt: float
) -> dict[str, F]:
    """The OU state ``x`` of each active channel for the given runs, ``(len(runs), steps + 1)``, indexed by the global
    step from 2024: exactly 0 up to and including ``start_step``.

    The recursion is element-wise over runs, so a run's path does not depend on which runs share the call.
    """
    chans = active(noise)
    n = len(runs)
    m = steps - start_step
    if not chans:
        return {}
    w = np.empty((n, m, len(CHANNELS)))
    for j, i in enumerate(runs):
        rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(int(i),)))
        w[j] = rng.standard_normal((m, len(CHANNELS)))
    out: dict[str, F] = {}
    for c in chans:
        spec = noise[c]
        phi = math.exp(-dt / spec.tau)
        scale = spec.sigma * math.sqrt(1 - phi * phi)
        ci = CHANNELS.index(c)
        x = np.zeros((n, steps + 1))
        for k in range(m):
            x[:, start_step + k + 1] = phi * x[:, start_step + k] + scale * w[:, k, ci]
        out[c] = x
    return out


def ou_factors(
    noise: Mapping[str, Noise], seed: int, runs: Runs, *, start_step: int, steps: int, dt: float
) -> dict[str, F]:
    """The factors ``exp(x)`` of ``ou_paths``, per active channel, ``(len(runs), steps + 1)``; exactly 1 up to and
    including ``start_step``.

    ``exp`` is applied one run at a time, on the same contiguous layout whatever the chunk, so a run's factors never
    depend on its position in a batch.
    """
    out: dict[str, F] = {}
    for c, x in ou_paths(noise, seed, runs, start_step=start_step, steps=steps, dt=dt).items():
        f = np.empty_like(x)
        for j in range(x.shape[0]):
            f[j] = np.exp(x[j])
        out[c] = f
    return out
