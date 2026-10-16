"""Calibrate a model against the Phase 7 targets of 2024-2026 with the batched engine, and write a fit JSON.

The targets, weights and scales are ``calibrate7.py``'s (``reference/prototype/code/calibrate7.py``), kept in
``tools/calibration_targets.csv``; ``tests/test_calibrate.py`` checks them, the ``FIT`` bounds, ``X0`` and the
optimiser settings below against that file, read by ``ast``. Each target's residual is
``weight x (model - target) / scale`` and the loss is scipy's ``cost``, ``0.5 x sum r^2``.

Two modes:

- **Least squares** (``--fit``): ``scipy.optimize.least_squares`` with ``calibrate7.py``'s settings (bounds, ``X0``,
  ``x_scale``, ``diff_step`` 1e-2, ``max_nfev`` 300; trust-region reflective, 2-point Jacobian). The points of each
  finite-difference Jacobian are evaluated in one ``run_batch`` (``least_squares(workers=...)``), which follows the
  same path as evaluating them one by one. A ``FIT`` parameter starts at ``X0``; any other at the model's value.
- **Profile** (``--profile name=lo,hi,step``): one parameter, for a loss that is smooth in it. The loss is evaluated on
  the grid ``lo, lo + step, ..., hi`` in one batch, then refined between the best grid point's neighbours with
  ``scipy.optimize.minimize_scalar(method="bounded")``. The fit JSON records the grid.

Every run starts from the model's baseline (``--model``), with ``--fix name=value`` overrides, from the shipped 2024
state; no fitted parameter enters the 2024 calibration (``calibrate7_ss``), so this state is the fit's initial state.

Usage (from the repository root):

    uv run python tools/calibrate.py --model phase7 --fit p,q,Verif,GCCAppealEnd,JuniorCut,GCCMomentum,qC,pAtt,\
PriceHorizon,SeekerExitRate,AICost2024 --out temp/fit.json
    uv run python tools/calibrate.py --model phase7 --profile PriceHorizon=4,7,0.05 --fix PassThrough=0.75 \
--fix AnnuityShare=0.3 --fix AnnuityAnchorW=0.4 --out temp/profile.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Final, cast

import numpy as np
from scipy.optimize import least_squares, minimize_scalar

# Run as a script, Python puts tools/ on sys.path; the repository root is needed to import the tools package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aisim.batch.engine import run_batch
from aisim.batch.params import BatchParams, Override
from aisim.batch.util import F
from aisim.experiment.meta import provenance
from aisim.params import Params

ROOT: Final = Path(__file__).resolve().parent.parent
TARGETS_CSV: Final = ROOT / "tools" / "calibration_targets.csv"

FIT_BOUNDS: Final = (
    ("p", 0.001, 0.3),
    ("q", 0.05, 2.0),
    ("Verif", 0.0, 1.5),
    ("GCCAppealEnd", 0.0, 6.0),
    ("JuniorCut", 0.0, 1.4),
    ("GCCMomentum", 0.0, 3.0),
    ("qC", 0.01, 1.0),
    ("pAtt", 0.001, 0.5),
    ("PriceHorizon", 0.0, 8.0),
    ("SeekerExitRate", 0.05, 1.0),
    ("AICost2024", 2_000.0, 60_000.0),
)
"""``calibrate7.py`` ``FIT``: the eleven fitted parameters and their bounds."""

X0: Final = (0.03, 0.5, 0.4, 0.5, 0.5, 1.0, 0.24, 0.012, 3.0, 0.6, 20_000.0)
"""``calibrate7.py`` ``X0``, in ``FIT_BOUNDS`` order."""

X_SCALE: Final = (0.01, 0.1, 0.1, 0.5, 0.1, 0.5, 0.05, 0.005, 1.0, 0.1, 5000.0)
"""``calibrate7.py``'s ``least_squares`` ``x_scale``, in ``FIT_BOUNDS`` order."""

DIFF_STEP: Final = 1e-2
MAX_NFEV: Final = 300
STOP: Final = 6.5
"""``calibrate7.py`` runs to 2030.5 with rows every quarter year."""
RECORD_EVERY: Final = 0.25

OBSERVABLES: Final = {
    "A_mean": "A_mean",
    "PriceIdx_OIT": "AvgIdx_OIT",
    "HeadOIT_ratio": "Head_OIT / Head_OIT(2024)",
    "MarginOIT_change": "Margin_OIT - Margin_OIT(2024)",
    "GCC_ratio": "Head_GCC / Head_GCC(2024)",
    "JuniorHires_ratio": "HireJ_IN + HireJ_ON, mean of year - 0.25, year and year + 0.25, / 2024",
    "AC_mean": "AC_mean",
    "Att": "Att",
    "UnempON_change": "Unemp_ON - Unemp_ON(2024)",
}
"""How each target metric is read from the rows (``calibrate7.py`` ``metrics``)."""

OUTPUTS: Final = ("A_mean", "AC_mean", "Att", "AvgIdx_OIT", "Head_OIT", "Margin_OIT", "Head_GCC", "Unemp_ON")
OUTPUTS_J: Final = ("HireJ_IN", "HireJ_ON")


@dataclass(frozen=True)
class Target:
    """One row of ``calibration_targets.csv``."""

    metric: str
    year: float
    observable: str
    target: float
    weight: float
    scale: float
    source: str


def load_targets(path: Path = TARGETS_CSV) -> list[Target]:
    """The targets, in file order."""
    with path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [
        Target(
            r["metric"],
            float(r["year"]),
            r["observable"],
            float(r["target"]),
            float(r["weight"]),
            float(r["scale"]),
            r["source"],
        )
        for r in rows
    ]


def metric_values(series: Mapping[str, F], years: F, i: int, targets: Sequence[Target]) -> list[float]:
    """Run ``i``'s model value of each target, as ``calibrate7.py`` computes it."""
    at = {round(float(y), 2): j for j, y in enumerate(years)}

    def g(key: str, year: float) -> float:
        return float(series[key][i, at[year]])

    def jh(year: float) -> float:
        return g("HireJ_IN", year) + g("HireJ_ON", year)

    out = []
    for t in targets:
        y = t.year
        if t.metric in ("A_mean", "AC_mean", "Att"):
            out.append(g(t.metric, y))
        elif t.metric == "PriceIdx_OIT":
            out.append(g("AvgIdx_OIT", y))
        elif t.metric == "HeadOIT_ratio":
            out.append(g("Head_OIT", y) / g("Head_OIT", 2024.0))
        elif t.metric == "MarginOIT_change":
            out.append(g("Margin_OIT", y) - g("Margin_OIT", 2024.0))
        elif t.metric == "GCC_ratio":
            out.append(g("Head_GCC", y) / g("Head_GCC", 2024.0))
        elif t.metric == "JuniorHires_ratio":
            out.append((jh(y - 0.25) + jh(y) + jh(y + 0.25)) / 3 / jh(2024.0))
        elif t.metric == "UnempON_change":
            out.append(g("Unemp_ON", y) - g("Unemp_ON", 2024.0))
        else:
            raise KeyError(f"unknown target metric {t.metric!r}")
    return out


def loss(r: F) -> float:
    """scipy's ``cost``: half the sum of squared residuals."""
    return 0.5 * float(r @ r)


class Objective:
    """The residuals of parameter vectors ``names``, every evaluation one ``run_batch``."""

    def __init__(self, model: str, names: Sequence[str], fixed: Mapping[str, float], targets: Sequence[Target]) -> None:
        self.model = model
        self.names = list(names)
        self.fixed = dict(fixed)
        self.targets = list(targets)
        self.runs = 0
        self.batches = 0

    def values(self, xs: Sequence[Sequence[float]]) -> list[list[float]]:
        """Each vector's model value of every target."""
        n = len(xs)
        over: dict[str, Override] = {name: [float(x[j]) for x in xs] for j, name in enumerate(self.names)}
        over.update(self.fixed)
        params = BatchParams.baseline(n, model=self.model, **over)
        res = run_batch(params, stop=STOP, record_every=RECORD_EVERY, outputs=[*OUTPUTS, *OUTPUTS_J])
        self.runs += n
        self.batches += 1
        return [metric_values(res.series, res.years, i, self.targets) for i in range(n)]

    def evaluate(self, xs: Sequence[Sequence[float]]) -> list[F]:
        """Each vector's residuals."""
        out = []
        for vals in self.values(xs):
            r = [t.weight * (v - t.target) / t.scale for t, v in zip(self.targets, vals, strict=True)]
            out.append(np.array(r, dtype=np.float64))
        return out

    def residuals(self, x: F) -> F:
        return self.evaluate([list(x)])[0]

    def map[VT, RT](self, func: Callable[[VT], RT], points: Iterable[VT], /) -> Iterable[RT]:
        """Map-like for ``least_squares(workers=...)``: all the Jacobian's points in one batch.

        scipy passes its wrapper of ``self.residuals`` as ``func``, so evaluating the points here in one batch gives
        what mapping ``func`` would (the cast states that ``RT`` is a residual vector).
        """
        return cast(Iterable[RT], self.evaluate([list(np.asarray(p, dtype=np.float64)) for p in points]))


def fit_least_squares(
    obj: Objective, x0: Sequence[float], lower: Sequence[float], upper: Sequence[float], x_scale: Sequence[float]
) -> dict[str, Any]:
    """``calibrate7.py``'s ``least_squares`` call. ``Any``: JSON-ready values."""
    res = least_squares(
        obj.residuals,
        np.array(x0, dtype=np.float64),
        bounds=(list(lower), list(upper)),
        x_scale=np.array(x_scale, dtype=np.float64),
        diff_step=np.full(len(x0), DIFF_STEP),
        max_nfev=MAX_NFEV,
        workers=obj.map,
    )
    return {
        "x": [float(v) for v in res.x],
        "loss": float(res.cost),
        "nfev": int(res.nfev),
        "njev": None if res.njev is None else int(res.njev),
        "status": int(res.status),
        "message": str(res.message),
    }


def grid_of(lo: float, hi: float, step: float) -> list[float]:
    """``lo, lo + step, ..., hi`` without accumulated round-off (``hi - lo`` must be a whole number of steps)."""
    k = round((hi - lo) / step)
    if k < 1 or abs(lo + k * step - hi) > 1e-9 * max(1.0, abs(hi)):
        raise ValueError(f"the profile {lo}..{hi} is not a whole number of steps of {step}")
    return [float(v) for v in np.linspace(lo, hi, k + 1)]


def fit_profile(obj: Objective, lo: float, hi: float, step: float) -> dict[str, Any]:
    """Grid then bounded refinement of one parameter. ``Any``: JSON-ready values."""
    grid = grid_of(lo, hi, step)
    losses = [loss(r) for r in obj.evaluate([[g] for g in grid])]
    j = int(np.argmin(losses))
    a, b = grid[max(j - 1, 0)], grid[min(j + 1, len(grid) - 1)]
    ref = minimize_scalar(lambda x: loss(obj.residuals(np.array([x]))), bounds=(a, b), method="bounded")
    x, best = (float(ref.x), float(ref.fun)) if float(ref.fun) <= losses[j] else (grid[j], losses[j])
    return {
        "x": [x],
        "loss": best,
        "profile": {
            "name": obj.names[0],
            "grid": [{"x": g, "loss": v} for g, v in zip(grid, losses, strict=True)],
            "best_grid": {"x": grid[j], "loss": losses[j]},
            "refine": {"bounds": [a, b], "x": float(ref.x), "loss": float(ref.fun), "nfev": int(ref.nfev)},
        },
    }


def parse_pairs(items: Sequence[str]) -> dict[str, str]:
    out = {}
    for item in items:
        name, sep, value = item.partition("=")
        if not sep or not name:
            raise ValueError(f"expected name=value, not {item!r}")
        out[name] = value
    return out


def versions() -> dict[str, str]:
    return {name: version(name) for name in ("ai-it-labour-sim", "numpy", "scipy")}


def run(argv: Sequence[str]) -> tuple[dict[str, Any], Path]:
    """Run the fit ``argv`` asks for; return the fit JSON and its ``--out`` path. ``Any``: JSON-ready values."""
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    ap.add_argument("--model", default="phase7")
    ap.add_argument("--fit", default="", help="comma-separated parameters for least squares")
    ap.add_argument("--fix", action="append", default=[], help="name=value, held fixed")
    ap.add_argument("--bounds", action="append", default=[], help="name=lo,hi, replacing the FIT bounds")
    ap.add_argument("--profile", default=None, help="name=lo,hi,step: profile one parameter instead")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(list(argv))
    fixed = {k: float(v) for k, v in parse_pairs(a.fix).items()}
    targets = load_targets()
    base = Params.baseline(a.model)
    unknown = sorted(k for k in fixed if k not in base.scalars)
    if unknown:
        raise KeyError(f"unknown parameter(s): {unknown}")
    result: dict[str, Any]
    if a.profile is not None:
        if a.fit or a.bounds:
            raise ValueError("--profile fits one parameter: it excludes --fit and --bounds")
        name, spec = next(iter(parse_pairs([a.profile]).items()))
        lo, hi, step = (float(v) for v in spec.split(","))
        names = [name]
        obj = Objective(a.model, names, fixed, targets)
        result = fit_profile(obj, lo, hi, step)
        lower, upper = [lo], [hi]
    else:
        names = [s for s in a.fit.split(",") if s]
        if not names:
            raise ValueError("name the parameters to fit (--fit) or a --profile")
        index = {n: j for j, (n, _, _) in enumerate(FIT_BOUNDS)}
        bounds = {n: (lo, hi) for n, lo, hi in FIT_BOUNDS}
        for n, spec in parse_pairs(a.bounds).items():
            lo, hi = (float(v) for v in spec.split(","))
            bounds[n] = (lo, hi)
        missing = sorted(n for n in names if n not in bounds)
        if missing:
            raise ValueError(f"no bounds for {missing}: give --bounds")
        x0 = [X0[index[n]] if n in index else Params.float_of(base.scalars, n) for n in names]
        lower, upper = [bounds[n][0] for n in names], [bounds[n][1] for n in names]
        x0 = [min(max(x, lo), hi) for x, lo, hi in zip(x0, lower, upper, strict=True)]
        x_scale = [X_SCALE[index[n]] if n in index else 1.0 for n in names]
        obj = Objective(a.model, names, fixed, targets)
        result = fit_least_squares(obj, x0, lower, upper, x_scale)
    x = result.pop("x")
    model_vals = obj.values([x])[0]
    prov = provenance()
    out = {
        "model": a.model,
        "fitted": dict(zip(names, x, strict=True)),
        "bounds": {n: [lo, hi] for n, lo, hi in zip(names, lower, upper, strict=True)},
        "fixed": fixed,
        **result,
        "targets": [
            {
                "metric": t.metric,
                "year": t.year,
                "target": t.target,
                "weight": t.weight,
                "scale": t.scale,
                "model": v,
                "miss": v - t.target,
                "residual": t.weight * (v - t.target) / t.scale,
            }
            for t, v in zip(targets, model_vals, strict=True)
        ],
        "runs": obj.runs,
        "batches": obj.batches,
        "command": "uv run python tools/calibrate.py " + " ".join(argv),
        "git_commit": prov["git_commit"],
        "git_dirty": prov["git_dirty"],
        "versions": versions(),
    }
    return out, Path(a.out)


def main(argv: Sequence[str] | None = None) -> int:
    out, path = run(sys.argv[1:] if argv is None else list(argv))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(json.dumps({k: out[k] for k in ("model", "fitted", "loss", "runs", "batches")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
