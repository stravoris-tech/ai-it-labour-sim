"""All intermediates of one time step of N runs, as the recording and integration blocks read them.

The batched counterpart of ``aisim.scalar.step.Step``: the same fields, each a section dataclass of arrays.
"""

from __future__ import annotations

from dataclasses import dataclass

from aisim.batch.adoption import Adoption
from aisim.batch.capability import Capability
from aisim.batch.consumer import Consumer, ConsumerDrivers
from aisim.batch.finance import Contracts, Costs, Spend, VendorBooks, WageTargets
from aisim.batch.labour_market import Exits, Hiring, Pools, Switching, TimeToFill, Unemployment, VisaFlows
from aisim.batch.sourcing import OptionCosts, SourcingFlows, SourcingTargets
from aisim.batch.util import F
from aisim.batch.work import Work
from aisim.batch.workforce import LevelMix, Staffing, Vacancies


@dataclass(frozen=True, slots=True)
class Step:
    """The intermediates of sections S1-S13 for one time step. ``y`` is shared by all runs; ``W`` is ``(N, level)``."""

    y: float
    W: F
    cap: Capability  # S2
    work: Work  # S3
    mix: LevelMix  # S4
    staffing: Staffing  # S5
    unemp: Unemployment  # S6
    vac: Vacancies  # S7
    switching: Switching  # S8a
    visa: VisaFlows  # S8b
    exits: Exits  # S8c
    hiring: Hiring  # S8d
    ttf: TimeToFill  # S8e
    pools: Pools  # S8f
    costs: Costs  # S9
    contracts: Contracts  # S10
    flows: SourcingFlows  # S11a
    books: VendorBooks  # S11b
    wages: WageTargets  # S11c
    spend: Spend  # S11d
    adoption: Adoption  # S12
    drivers: ConsumerDrivers  # S13a
    options: OptionCosts  # S13b
    consumer: Consumer  # S13c
    targets: SourcingTargets  # S13d
