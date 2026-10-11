"""S6 and S8, batched: unemployment, switching, visa flows, exits, hires, time to fill, pools and enrolment.

Mirrors ``aisim.scalar.labour_market``. The named flow dicts become trailing axes: ``sw`` ``(N, unit, level, 2)`` with
``SW_FLOWS``, ``fl`` ``(N, unit, level, 7)`` with ``LEVEL_FLOWS`` and ``pool`` ``(N, region, level, 5)`` with
``POOL_FLOWS``. Per-pool groups are summed over their units in unit order, with exact zeros for non-members (recon 03
C1, C2); the switching flows are a full ``(src, dst)`` matrix whose diagonal and cross-pool entries are exact zeros.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from aisim.batch.axes import (
    POOL_IX,
    POOL_MASK,
    REG_IX,
    SWITCH_DST,
    SWITCH_FROM,
    SWITCH_INTO,
    SWITCH_OTHERS,
    SWITCH_SRC,
    UNIT_IX,
)
from aisim.batch.params import BatchParams
from aisim.batch.state import BatchState
from aisim.batch.util import F, clamp, csum, csum_axis, group_sum, group_sum_ul, nsum, pw
from aisim.dims import LEVELS, REGIONS, UNITS

SW_FLOWS: Final = ("in", "out")
LEVEL_FLOWS: Final = ("quits", "leave", "retire", "promo_out", "openings", "layoffs", "onboard")
POOL_FLOWS: Final = ("rec_to_seek", "rec_to_left", "seek_exit", "rec_retire", "seek_retire")

OV: Final = UNIT_IX["OV"]
IN: Final = REG_IX["IN"]
ON: Final = REG_IX["ON"]


@dataclass(frozen=True, slots=True)
class Unemployment:
    """S6 intermediates, each ``(N, region)``."""

    UnempRate: F
    LeaveEffect: F
    EnrolEffect: F


@dataclass(frozen=True, slots=True)
class Switching:
    """S8a intermediates."""

    sw: F


@dataclass(frozen=True, slots=True)
class VisaFlows:
    """S8b intermediates: ``expiry``, ``conv`` ``(N, level)``, ``VisaCap`` ``(N,)``."""

    expiry: F
    conv: F
    VisaCap: F


@dataclass(frozen=True, slots=True)
class Exits:
    """S8c intermediates."""

    fl: F


@dataclass(frozen=True, slots=True)
class Hiring:
    """S8d intermediates: ``hires`` ``(N, unit, level)``."""

    hires: F


@dataclass(frozen=True, slots=True)
class TimeToFill:
    """S8e intermediates, each ``(N, region, level)``."""

    TTFr: F
    ext: F


@dataclass(frozen=True, slots=True)
class Pools:
    """S8f intermediates: ``pool`` ``(N, region, level, 5)``; ``Enrol``, ``Grad``, ``TTFratio`` ``(N, region)``."""

    pool: F
    Enrol: F
    Grad: F
    TTFratio: F


def unemployment(pr: BatchParams, st: BatchState) -> Unemployment:
    """S6: regional unemployment (see ``aisim.scalar.labour_market.unemployment``)."""
    unemp = csum_axis(st.R + st.U, 2)
    emp = group_sum_ul(st.H + st.O, POOL_MASK)
    UnempRate = unemp / (emp + unemp)
    norm = pr.fam("NormalUnempRate_", REGIONS)
    LeaveEffect = clamp(st.PUS / norm, 0.5, 3.0)
    EnrolEffect = clamp(1 - pr["EnrolSensitivity"][:, None] * (st.PUL / norm - 1), 0.4, 1.3)
    return Unemployment(UnempRate=UnempRate, LeaveEffect=LeaveEffect, EnrolEffect=EnrolEffect)


def switching(pr: BatchParams, st: BatchState, avail: F, promo: F) -> Switching:
    """S8a: job switching between units in the same pool (see ``aisim.scalar.labour_market.switching``).

    Works on the 18 same-pool ``(src, dst)`` pairs (``axes.SWITCH_PAIRS``), arrays ``(N, pair, level)``.
    ``vac_others`` and ``inflow`` are ``sum()`` in unit order (``csum``); ``in`` and ``out`` add the scaled flows from
    0.0 in the scalar engine's loop order (``in`` over sources, ``out`` over destinations). OV never switches: its
    flows are 0.0.
    """
    H, V, WI = st.H, st.V, st.WI
    wage_index = pr.fam("Wage_", UNITS) * WI
    ratio = wage_index[:, SWITCH_DST] / wage_index[:, SWITCH_SRC]
    gw = np.minimum(pr["SwitchMax"][:, None], pw(ratio, pr["SwitchElasticity"][:, None]))
    zero = np.zeros_like(V[:, 0, :])
    vac_others = np.stack([csum(V[:, d, :] for d in ds) if ds else zero for ds in SWITCH_OTHERS], axis=1)
    vo = vac_others[:, SWITCH_SRC, :]
    raw = np.where(
        vo > 0,
        H[:, SWITCH_SRC, :] * pr["SwitchRate"][:, None, None] * gw[:, :, None] * V[:, SWITCH_DST, :] / vo,
        0.0,
    )
    inflow = np.stack([csum(raw[:, p] for p in ps) if ps else zero for ps in SWITCH_INTO], axis=1)
    switch_room = np.maximum(0.0, avail - promo)
    scale = np.where(inflow > 0, np.minimum(1.0, switch_room / inflow), 0.0)
    flow = raw * scale[:, SWITCH_DST, :]
    sw_in = np.stack([nsum(flow[:, p] for p in ps) if ps else zero for ps in SWITCH_INTO], axis=1)
    sw_out = np.stack([nsum(flow[:, p] for p in ps) if ps else zero for ps in SWITCH_FROM], axis=1)
    return Switching(sw=np.stack([sw_in, sw_out], axis=3))


def visa_flows(pr: BatchParams, st: BatchState, VisaTight: F, G: F) -> VisaFlows:
    """S8b: visa expiry, conversion and the visa cap (see ``aisim.scalar.labour_market.visa_flows``)."""
    H_OV = st.H[:, OV, :]
    expiry = H_OV / pr["VisaTenure"][:, None]
    conv = H_OV * pr["ConvRate"][:, None] * (1 - VisaTight)[:, None]
    VisaCap = pr["BaseVisaCap"] * (1 - VisaTight) * np.where(pr["Burn"] >= 0.5, G, 1.0)
    return VisaFlows(expiry=expiry, conv=conv, VisaCap=VisaCap)


def exits(pr: BatchParams, st: BatchState, surplus: F, promo: F, sw: F, visa: VisaFlows) -> Exits:
    """S8c: exits, openings and layoffs (see ``aisim.scalar.labour_market.exits``)."""
    H, O, V = st.H, st.O, st.V
    quits = H * pr.fam("QuitRate_", LEVELS)[:, None, :]
    leave = H * pr.fam("LeaveITRate_", LEVELS)[:, None, :]
    retire = np.zeros_like(H)
    retire[:, :, 2] = H[:, :, 2] * pr["RetireRate_S"][:, None]
    promo_out = np.stack([promo[:, :, 1], promo[:, :, 2], np.zeros_like(promo[:, :, 0])], axis=2)
    visa_out = np.zeros_like(H)
    visa_out[:, OV, :] = visa.expiry + visa.conv
    netloss = quits + leave + retire + promo_out + sw[:, :, :, 1] + visa_out
    sp = surplus
    short = sp <= 0
    openings = np.where(short, np.maximum(0.0, netloss + (-sp - V) / pr["HireAdjTime"][:, None, None]), 0.0)
    layoffs = np.where(
        short,
        0.0,
        np.minimum(
            np.maximum(0.0, sp / pr["LayoffAdjTime"][:, None, None] - netloss),
            H / pr["MinLayoffTime"][:, None, None],
        ),
    )
    onboard = O / pr["OnboardTime"][:, None, None]
    fl = np.stack([quits, leave, retire, promo_out, openings, layoffs, onboard], axis=3)
    return Exits(fl=fl)


def hiring(pr: BatchParams, st: BatchState, avail: F, promo: F, sw: F, VisaCap: F) -> Hiring:
    """S8d: matching and hires (see ``aisim.scalar.labour_market.hiring``).

    A pool level with no vacancies or no seekers hires nothing. The pool cap and the visa cap scale hires only where
    they bind, as the scalar engine's conditional multiplications do; the visa cap does not feed back (recon 03 C2).
    """
    V, U = st.V, st.U
    vac_pool = group_sum(V, POOL_MASK)
    go = ~((vac_pool <= 0) | (U <= 0))
    alpha = pr["alpha"][:, None, None]
    match = pr["m"][:, None, None] * pw(U, alpha) * pw(vac_pool, 1 - alpha)
    hire_room = np.maximum(0.0, avail - promo - sw[:, :, :, 0])
    hires = np.minimum(match[:, POOL_IX, :] * V / vac_pool[:, POOL_IX, :], hire_room)
    hires = np.where(go[:, POOL_IX, :], hires, 0.0)
    total = group_sum(hires, POOL_MASK)
    capU = U / pr["MinFillTime"][:, None, None]
    over = go & (total > capU)
    hires = np.where(over[:, POOL_IX, :], hires * (capU / total)[:, POOL_IX, :], hires)
    h_ov = hires[:, OV, :]
    ov_tot = csum(h_ov[:, l] for l in range(len(LEVELS)))
    hires[:, OV, :] = np.where((ov_tot > VisaCap)[:, None], h_ov * (VisaCap / ov_tot)[:, None], h_ov)
    return Hiring(hires=hires)


def time_to_fill(pr: BatchParams, st: BatchState, hires: F, promo: F, sw: F) -> TimeToFill:
    """S8e: time to fill and external entry (see ``aisim.scalar.labour_market.time_to_fill``)."""
    H, V = st.H, st.V
    vs = group_sum(V, POOL_MASK)
    fills = group_sum(hires + promo + sw[:, :, :, 0], POOL_MASK)
    TTFr = vs / np.maximum(fills, 1.0)
    hsum = group_sum(H, POOL_MASK)
    excess = clamp(TTFr / pr.fam("NormalTTF_", REGIONS, LEVELS) - 1, 0.0, pr["ExtEntryMax"][:, None, None])
    ext_ms = pr.fam("ExtEntryRate_", LEVELS)[:, None, :] * hsum * excess
    ext = np.where(np.array([l == "J" for l in LEVELS])[None, None, :], 0.0, ext_ms)
    return TimeToFill(TTFr=TTFr, ext=ext)


def pools(pr: BatchParams, st: BatchState, G: F, unemp: Unemployment, TTFr: F) -> Pools:
    """S8f: pool flows, enrolment and graduation (see ``aisim.scalar.labour_market.pools``)."""
    R, U = st.R, st.U
    LeaveEffect = unemp.LeaveEffect[:, :, None]
    rec_out = R / pr["RecoveryTime"][:, None, None]
    lf = clamp(pr.fam("BaseLeaveFrac_", LEVELS)[:, None, :] * LeaveEffect, 0.0, 0.9)
    rec_retire = np.zeros_like(R)
    seek_retire = np.zeros_like(U)
    rec_retire[:, :, 2] = R[:, :, 2] * pr["RetireRate_S"][:, None]
    seek_retire[:, :, 2] = U[:, :, 2] * pr["RetireRate_S"][:, None]
    pool = np.stack(
        [
            rec_out * (1 - lf),
            rec_out * lf,
            U * pr["SeekerExitRate"][:, None, None] * LeaveEffect,
            rec_retire,
            seek_retire,
        ],
        axis=3,
    )
    Enrol = pr.fam("BaseEnrolment_", REGIONS) * G[:, None] * unemp.EnrolEffect
    Grad = st.Pipeline / pr["StudyTime"][:, None]
    TTFratio = TTFr[:, :, 1] / pr.fam("NormalTTF_", REGIONS, LEVELS)[:, :, 1]
    return Pools(pool=pool, Enrol=Enrol, Grad=Grad, TTFratio=TTFratio)
