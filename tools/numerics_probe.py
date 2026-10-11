"""Probe numpy's float64 maths kernels against Python's, in the forms the batched engine uses them.

The batched engine matches the scalar engine to 1e-12 only if ``np.power`` and ``np.log`` return the same doubles as
Python's ``**`` and ``math.log`` (libm). On some x86-64 CPUs numpy dispatches them to SIMD kernels that can differ by
an ulp or so (recon 04 A2, slice 03b). This tool prints the CPU and numpy's CPU dispatch, then compares each form on a
fixed sample (``default_rng(0)``, 10^6 values per form, in the ranges of recon 03 E2) and reports the mismatch count
and the max ulp difference.

- Exit 0 only if every form the engine uses is bit-identical. The ``exp`` forms are for information only.
- ``--end-to-end`` also runs the 27 batch parity cases through ``run_batch`` and the scalar ``run``, and reports the
  differences that result. Information only: it does not change the exit code.
- ``--json PATH`` writes everything, with up to 20 mismatching inputs per form, as JSON.

Usage: ``uv run python tools/numerics_probe.py [--end-to-end] [--json PATH]``
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import platform
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import aisim and tests.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim.batch.util import E, F, pw

SEED = 0
N = 1_000_000
MAX_SAVED = 20

Q1_KEYS = ("HeadTotal", "Q1_ConsOnshore", "Q1_ConsIndia", "Q1_VendOnshore", "Q1_VendIndia")
"""The keys whose 2040 values ``--end-to-end`` reports separately."""

Draw = Callable[[np.random.Generator, int], tuple[F, F]]


@dataclass(frozen=True)
class Form:
    """An element-wise form: numpy's version, Python's version and how to draw its two operands."""

    name: str
    engine: bool
    """True if the batched engine uses the form; False for information only."""
    batch: Callable[[F, F], F]
    python: Callable[[float, float], float]
    draw: Draw


@dataclass(frozen=True)
class FormResult:
    """The comparison of one form: mismatches, the max ulp difference and up to ``MAX_SAVED`` mismatching inputs."""

    name: str
    engine: bool
    n: int
    mismatches: int
    max_ulp: int
    inputs: list[list[float]]


# ---- forms -----------------------------------------------------------------------------------------------------------


def np_power(a: F, b: F) -> F:
    return pw(a, b)


def py_power(a: float, b: float) -> float:
    return float(a**b)


def np_log(a: F, b: F) -> F:
    """The form of ``aisim.batch.engine.tilt_sourcing_perception``: ``np.log(np.maximum(x, 1e-12))``."""
    out: F = np.log(np.maximum(a, 1e-12))
    return out


def py_log(a: float, b: float) -> float:
    return math.log(max(a, 1e-12))


def np_exp(a: F, b: F) -> F:
    out: F = np.exp(a)
    return out


def py_exp(a: float, b: float) -> float:
    return math.exp(a)


def spread(rng: np.random.Generator, n: int, lo: float, hi: float) -> F:
    """``n`` doubles drawn uniformly over the representable doubles in ``[lo, hi]`` (``0 < lo < hi``).

    That is close to log-uniform, and it calls no maths kernel, so the inputs are the same on every machine.
    """
    a, b = (int(v) for v in np.array([lo, hi]).view(np.int64))
    out: F = rng.integers(a, b, n, endpoint=True).view(np.float64)
    return out


def base_and_exponent(lo: float, hi: float, ex: float) -> Draw:
    """A base uniform in ``[lo, hi]`` and the exponent ``ex`` at full shape."""
    return lambda rng, n: (rng.uniform(lo, hi, n), np.full(n, ex))


def forms() -> list[Form]:
    """The forms, in draw order. Ranges from recon 03 E2; its exponent list gives no base range, so [0.1, 10]."""
    power: list[tuple[str, Draw]] = [
        ("softmax E ** x, x in [-40, 0]", lambda rng, n: (np.full(n, E), rng.uniform(-40.0, 0.0, n))),
        ("x ** 0.5 (alpha), x in [1e2, 1e7]", base_and_exponent(1e2, 1e7, 0.5)),
        ("x ** 2.0 (SwitchElasticity), x in [0.2, 5]", base_and_exponent(0.2, 5.0, 2.0)),
        ("x ** 0.3 (CostAdoptElast), x in [0.1, 10]", base_and_exponent(0.1, 10.0, 0.3)),
        ("x ** 0.25 (WageElasticity), x in [0.1, 10]", base_and_exponent(0.1, 10.0, 0.25)),
        ("x ** 1.0 (DurPowerElast), x in [0.1, 10]", base_and_exponent(0.1, 10.0, 1.0)),
        ("x ** -0.5, x in [0.1, 10]", base_and_exponent(0.1, 10.0, -0.5)),
        ("x ** -0.0, x in [0.1, 10]", base_and_exponent(0.1, 10.0, -0.0)),
        (
            "(1 - g) ** (k / 16), base in [0.5, 1.2], k in 0..256",
            lambda rng, n: (rng.uniform(0.5, 1.2, n), rng.integers(0, 256, n, endpoint=True) / 16),
        ),
        ("x ** y, x in [0.1, 10], y in [-2, 2]", lambda rng, n: (rng.uniform(0.1, 10.0, n), rng.uniform(-2.0, 2.0, n))),
    ]
    out = [Form(name, True, np_power, py_power, draw) for name, draw in power]
    out += [
        Form(f"log(max(x, 1e-12)), x in [{lo:g}, {hi:g}]", True, np_log, py_log, log_draw(lo, hi))
        for lo, hi in ((1e-12, 1.0), (1.0, 1e6))
    ]
    out += [
        Form(f"exp(x), x in [{lo:g}, {hi:g}]", False, np_exp, py_exp, uniform_draw(lo, hi))
        for lo, hi in ((-40.0, 0.0), (-5.0, 5.0))
    ]
    return out


def log_draw(lo: float, hi: float) -> Draw:
    return lambda rng, n: (spread(rng, n, lo, hi), np.zeros(n))


def uniform_draw(lo: float, hi: float) -> Draw:
    return lambda rng, n: (rng.uniform(lo, hi, n), np.zeros(n))


# ---- comparison ------------------------------------------------------------------------------------------------------


def ordered(x: F) -> NDArray[np.int64]:
    """The doubles of ``x`` as int64 in the same order, so that adjacent doubles differ by 1 (and -0.0 is 0)."""
    i = np.ascontiguousarray(x, dtype=np.float64).view(np.int64)
    out: NDArray[np.int64] = np.where(i < 0, np.iinfo(np.int64).min - i, i)
    return out


def compare(got: F, want: F) -> tuple[NDArray[np.bool_], int]:
    """The elements of ``got`` that are not bit-identical to ``want``, and the max ulp difference over them."""
    bad = np.ascontiguousarray(got, dtype=np.float64).view(np.int64) != np.ascontiguousarray(want).view(np.int64)
    ulp = int(np.abs(ordered(got) - ordered(want)).max()) if bad.any() else 0
    return bad, ulp


def check(form: Form, a: F, b: F) -> FormResult:
    """Compare numpy's version of ``form`` with Python's, element by element, on the operands ``a`` and ``b``."""
    got = form.batch(a, b)
    want = np.array([form.python(x, y) for x, y in zip(a.tolist(), b.tolist(), strict=True)], dtype=np.float64)
    bad, ulp = compare(got, want)
    idx = np.flatnonzero(bad)
    saved = [[float(a[i]), float(b[i])] for i in idx[:MAX_SAVED]]
    return FormResult(form.name, form.engine, int(a.size), int(idx.size), ulp, saved)


def run_forms(
    n: int = N,
    seed: int = SEED,
    extra: Mapping[str, Sequence[Sequence[float]]] | None = None,
    engine_only: bool = False,
) -> list[FormResult]:
    """Compare every form (or only the engine's) on ``n`` drawn operands plus any ``extra`` ``[a, b]`` points by name.

    The operands come from one ``default_rng(seed)``, drawn form by form in ``forms()`` order.
    """
    rng = np.random.default_rng(seed)
    out = []
    for form in forms():
        a, b = form.draw(rng, n)
        if engine_only and not form.engine:
            continue
        points = (extra or {}).get(form.name, [])
        if points:
            p = np.array(points, dtype=np.float64).reshape(-1, 2)
            a, b = np.concatenate([a, p[:, 0]]), np.concatenate([b, p[:, 1]])
        out.append(check(form, a, b))
    return out


# ---- environment -----------------------------------------------------------------------------------------------------


def umath() -> Any:
    """numpy's ``_multiarray_umath`` module, which holds the CPU dispatch information.

    ``Any``: a private compiled module without type information.
    """
    return importlib.import_module("numpy._core._multiarray_umath")


def cpuinfo(field: str) -> str | None:
    """The first ``field`` line of ``/proc/cpuinfo``, or None where there is no such file or line."""
    path = Path("/proc/cpuinfo")
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip() == field:
            return value.strip()
    return None


def cpu_model() -> str:
    """The CPU model: ``/proc/cpuinfo`` on Linux, ``platform.processor()`` elsewhere."""
    return cpuinfo("model name") or platform.processor() or platform.machine()


def has_avx512f() -> bool:
    """Whether the CPU has ``avx512f``: its ``/proc/cpuinfo`` flags on Linux, numpy's runtime detection elsewhere."""
    flags = cpuinfo("flags")
    if flags is not None:
        return "avx512f" in flags.split()
    return bool(umath().__cpu_features__.get("AVX512F", False))


def environment() -> dict[str, Any]:
    """The CPU, Python, numpy and numpy's CPU dispatch information."""
    m = umath()
    return {
        "cpu": cpu_model(),
        "machine": platform.machine(),
        "avx512f": has_avx512f(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "cpu_baseline": list(m.__cpu_baseline__),
        "cpu_dispatch": list(m.__cpu_dispatch__),
        "avx512_features_on": sorted(k for k, v in m.__cpu_features__.items() if v and k.startswith("AVX512")),
        "dispatch_features": {k: m.__cpu_features__.get(k) for k in m.__cpu_dispatch__},
        "NPY_DISABLE_CPU_FEATURES": os.environ.get("NPY_DISABLE_CPU_FEATURES"),
    }


# ---- end to end ------------------------------------------------------------------------------------------------------


def end_to_end() -> list[dict[str, Any]]:
    """Run the 27 batch parity cases through both engines and size the differences, per case.

    The cases come from ``tests.test_batch_parity`` and run in batches by ``(dt, record_every)``, as the parity tests
    run them. Per case:

    - ``at_2040``: the relative difference at 2040 of ``HeadTotal`` and the four Q1 lines;
    - ``worst_key`` and ``worst_rel``: the largest relative difference over every row key and recorded time, counting
      only points where the scalar value is not exactly 0;
    - ``zero_keys``: the keys whose scalar value is exactly 0 throughout, and ``zero_max_abs``: the largest absolute
      difference at any point where the scalar value is exactly 0.
    """
    # Imported here: the test module needs pytest and the prototype's test helpers, which the plain probe does not.
    from tests.test_batch_parity import ALL_CASES, Case, rel_diff, run_cases

    groups: dict[tuple[float, float], list[Case]] = {}
    for case in ALL_CASES.values():
        groups.setdefault((case.dt, case.record_every), []).append(case)
    out = []
    for (_, every), cases in groups.items():
        result = run_cases(cases, record_every=every)
        last = len(result.years) - 1
        assert result.years[last] == 2040.0, result.years[last]
        for i, case in enumerate(cases):
            rows = case.scalar(record_every=every).rows
            worst_key, worst_rel, zero_keys, zero_abs = "", 0.0, 0, 0.0
            for key, series in result.series.items():
                got, want = series[i], np.array([r[key] for r in rows])
                zero = want == 0.0
                if zero.all():
                    zero_keys += 1
                if zero.any():
                    zero_abs = max(zero_abs, float(np.abs(got[zero]).max()))
                d = rel_diff(got[~zero], want[~zero])
                if d.size and (np.isnan(d).any() or float(d.max()) > worst_rel):
                    worst_key, worst_rel = key, math.inf if np.isnan(d).any() else float(d.max())
            at_2040 = {
                k: float(rel_diff(result.series[k][i][last : last + 1], np.array([rows[last][k]]))[0]) for k in Q1_KEYS
            }
            out.append(
                {
                    "case": case.name,
                    "at_2040": at_2040,
                    "worst_key": worst_key,
                    "worst_rel": worst_rel,
                    "zero_keys": zero_keys,
                    "zero_max_abs": zero_abs,
                }
            )
    return out


def e2e_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The worst values over every case."""
    worst = max(cases, key=lambda c: c["worst_rel"])
    return {
        "at_2040_max": max(max(c["at_2040"].values()) for c in cases),
        "worst_rel": worst["worst_rel"],
        "worst_key": f"{worst['case']}: {worst['worst_key']}",
        "zero_max_abs": max(c["zero_max_abs"] for c in cases),
    }


# ---- report ----------------------------------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    """Print the environment and the comparisons; return 0 only if every engine form is bit-identical."""
    parser = argparse.ArgumentParser(
        description="Compare numpy's maths kernels with Python's, as the engine uses them."
    )
    parser.add_argument("--end-to-end", action="store_true", help="also run the 27 batch parity cases")
    parser.add_argument("--json", type=Path, help="write the results to this JSON file")
    parser.add_argument("--n", type=int, default=N, help=f"operands per form (default {N})")
    args = parser.parse_args(argv)

    env = environment()
    print("numerics probe")
    for k, v in env.items():
        print(f"  {k}: {v}")

    results = run_forms(args.n)
    width = max(len(r.name) for r in results)
    print(f"\n{'form':<{width}}  {'use':<6}  {'mismatches':>10}  {'max ulp':>7}")
    for r in results:
        use = "engine" if r.engine else "info"
        print(f"{r.name:<{width}}  {use:<6}  {r.mismatches:>10}  {r.max_ulp:>7}")
    ok = all(r.mismatches == 0 for r in results if r.engine)

    e2e = end_to_end() if args.end_to_end else None
    if e2e is not None:
        print(
            f"\n{'case':<34}  {'2040 max rel':>12}  {'worst rel':>9}  {'zero keys':>9}  {'zero max abs':>12}  worst key"
        )
        for c in e2e:
            print(
                f"{c['case']:<34}  {max(c['at_2040'].values()):>12.3e}  {c['worst_rel']:>9.3e}  {c['zero_keys']:>9}  "
                f"{c['zero_max_abs']:>12.3e}  {c['worst_key']}"
            )
        print(f"worst over all cases: {e2e_summary(e2e)}")

    print(f"\nprobe: {'kernels match' if ok else 'KERNELS DIFFER'} (exit {0 if ok else 1})")
    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        doc = {
            "environment": env,
            "kernels_match": ok,
            "forms": [asdict(r) for r in results],
            "end_to_end": e2e,
            "end_to_end_summary": None if e2e is None else e2e_summary(e2e),
        }
        with args.json.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
