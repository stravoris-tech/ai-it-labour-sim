"""AI capability, verification, demand growth and employer productivity by work type.

Prototype: ``phase7_sim.py`` S2, lines 164-173. Spec modules: 7 AI capability (``aW``, ``PAI``, verification),
6 Delivery AI (``Pew`` from ``A``) and 1 IT work demand (``G``, Phase 7; 07).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.dims import EMPLOYERS, WTYPES
from aisim.params import Reanchor
from aisim.state import Mat, State, Vec


@dataclass(frozen=True, slots=True)
class Capability:
    """S2 intermediates."""

    aW: Vec
    VerifNow: float
    PAI: Vec
    PAI0: Vec
    G: float
    Pew: Mat


def capability(
    pr: Mapping[str, float],
    tb: Mapping[str, Mapping[str, float]],
    st: State,
    y: float,
    ai_on: bool,
    demand_growth_late: float | None,
    *,
    reanchor: Reanchor | None = None,
    nz: Mapping[str, float] | None = None,
) -> Capability:
    """S2: capability by work type and employer.

    - The automatable share ``aW`` of each work type closes the gap from ``a2024`` to ``amax`` at rate ``g`` a year.
    - ``VerifNow``, the verification overhead, falls from ``Verif`` at ``VerifDecline`` a year as models get more
      reliable.
    - ``PAI`` is the Amdahl productivity of AI-assisted work: the unautomated share plus the automated share sped up by
      ``SpeedUp``, plus the verification of automated work. ``PAI0`` is its 2024 value.
    - ``G`` is underlying demand growth, ``DemandGrowth`` a year to ``LateYear`` and ``DemandGrowthLate`` after it
      (``None``: same as ``DemandGrowth``).
    - ``Pew``, the productivity of employer ``e`` on work type ``w`` relative to 2024, blends AI and non-AI work by the
      adoption ``A[e]``. With AI off it is 1.

    No loop closes here; adoption ``A`` is the stock that R5 and B2 act on (S12).

    Two-phase runs (``aisim.perturb``): with ``reanchor``, ``aW`` and ``VerifNow`` continue from their base values at
    ``reanchor.Y`` when this run's ``g`` or ``VerifDecline`` differs from the base. ``nz`` holds this step's noise
    factors: ``cap`` multiplies ``PAI``, ``demand`` multiplies ``G``.
    """
    amax, a2024, speed_up = tb["amax"], tb["a2024"], tb["SpeedUp"]
    if reanchor is not None and pr["g"] != reanchor.g:
        decay = reanchor.g_decay * (1 - pr["g"]) ** (y - reanchor.Y)
        aW = {w: max(0.0, amax[w] - (amax[w] - a2024[w]) * decay) for w in WTYPES}
    else:
        aW = {w: max(0.0, amax[w] - (amax[w] - a2024[w]) * (1 - pr["g"]) ** (y - 2024)) for w in WTYPES}
    if reanchor is not None and pr["VerifDecline"] != reanchor.VerifDecline:
        VerifNow = reanchor.verif_Y * (1 - pr["VerifDecline"]) ** (y - reanchor.Y)
    else:
        VerifNow = pr["Verif"] * (1 - pr["VerifDecline"]) ** (y - 2024)
    PAI = {w: 1 / ((1 - aW[w]) + aW[w] / speed_up[w] + aW[w] * VerifNow) for w in WTYPES}
    if nz is not None and "cap" in nz:
        PAI = {w: PAI[w] * nz["cap"] for w in WTYPES}
    PAI0 = {w: 1 / ((1 - a2024[w]) + a2024[w] / speed_up[w] + a2024[w] * pr["Verif"]) for w in WTYPES}
    Aemp = st["A"]
    dgl = pr["DemandGrowth"] if demand_growth_late is None else demand_growth_late
    G = (1 + pr["DemandGrowth"]) ** (min(y, pr["LateYear"]) - 2024) * (1 + dgl) ** max(0.0, y - pr["LateYear"])
    if nz is not None and "demand" in nz:
        G = G * nz["demand"]
    Pew = {
        e: {
            w: (Aemp[e] * PAI[w] + (1 - Aemp[e])) / (pr["A0"] * PAI0[w] + (1 - pr["A0"])) if ai_on else 1.0
            for w in WTYPES
        }
        for e in EMPLOYERS
    }
    return Capability(aW=aW, VerifNow=VerifNow, PAI=PAI, PAI0=PAI0, G=G, Pew=Pew)
