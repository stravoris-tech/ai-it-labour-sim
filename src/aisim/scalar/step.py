"""All intermediates of one time step, as the recording and integration blocks read them.

The engine builds one ``Step`` per time step from the section results, in section order. It is the port's stand-in
for the local variables that the prototype's ``run()`` keeps in scope between its sections.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from aisim.scalar.adoption import Adoption
from aisim.scalar.capability import Capability
from aisim.scalar.consumer import Consumer, ConsumerDrivers
from aisim.scalar.finance import Contracts, Costs, Spend, VendorBooks, WageTargets
from aisim.scalar.labour_market import Exits, Hiring, Pools, Switching, TimeToFill, Unemployment, VisaFlows
from aisim.scalar.sourcing import OptionCosts, SourcingFlows, SourcingTargets
from aisim.scalar.work import Work
from aisim.scalar.workforce import LevelMix, Staffing, Vacancies


@dataclass(frozen=True, slots=True)
class Step:
    """The intermediates of sections S1-S13 for one time step."""

    y: float
    W: Mapping[str, float]
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
