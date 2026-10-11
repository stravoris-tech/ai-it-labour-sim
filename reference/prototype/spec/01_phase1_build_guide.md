# Phase 1 build guide

Phase 1 builds the core loop - backlog, headcount, AI adoption and perceived productivity - for one sector and one employer, with no arrays. It is done when the model holds a steady state with AI off and shows a plausible decline with AI on; every value below was verified in a prototype run.

## Structure

Four stocks and eight flows make up Phase 1; the diagram is the layout to reproduce on the AnyLogic canvas.

&#91;embedded content: Phase 1 stock-and-flow structure · 4 stocks, 8 flows\]

Demand fills the backlog, the backlog sets desired headcount, and desired headcount drives hiring and layoffs. AI adoption raises effective productivity, which speeds completion at once but changes desired headcount only after managers perceive it, about a year later.

## AnyLogic setup

Ten steps take you from an empty model to a first run; menu locations vary slightly between AnyLogic versions.

1. Create a new model and set **model time units to years**.
2. In the Simulation experiment, set **start time 0 and stop time 16** (model years 2024-2040). The formulas use `Year = 2024 + time()`.
3. In the experiment's model time / advanced settings, set the **differential equations method to Euler** and the **fixed time step to 0.0625** (1/16 year).
4. From the System Dynamics palette, drag in four **Stocks** and name them `Backlog`, `Headcount`, `A`, `PerceivedP`. Enter the initial values from the Stocks table.
5. With the **Flow** tool, draw each flow from its source stock to its destination stock (or from/to empty space for flows that cross the model boundary), as listed in the Stocks table. AnyLogic builds each stock's equation from the flows attached to it.
6. Add every row of the Parameters table as a **Parameter**. Make `AIOn` a boolean, the rest doubles.
7. Add every auxiliary in the Flows and variables table as a **Dynamic Variable**, and type each flow's formula into the flow itself.
8. Draw a **Link** from each variable to every formula that uses it. AnyLogic expects a dependency link for every name a formula reads and flags missing ones in its error list.
9. Add a **Time Plot** showing `Headcount`, `DesiredHeadcount` and `P_eff`, and a second showing `Backlog` and `A`.
10. Run test T1 (AI off) first. If Headcount is not flat at 100,000, fix that before anything else: a steady state that drifts means an equation or initial value is wrong.

## Stocks

Four stocks start in equilibrium: with productivity at 1, demand of 100,000 BFY/yr needs 100,000 people and a backlog of half a year's work.

| Stock | Unit | Initial value | Inflows | Outflows |
| --- | --- | --- | --- | --- |
| `Backlog` | BFY | `BaseDemand * TargetClearanceTime` (50,000) | `Demand` (from outside) | `Completion`, `Abandonment` (to outside) |
| `Headcount` | persons | `BaseDemand / WorkPerPerson` (100,000) | `Hiring` (from outside) | `Attrition`, `Layoffs` (to outside) |
| `A` (delivery AI adoption) | fraction | `A0` (0.05) | `AdoptionRate` | None |
| `PerceivedP` (perceived productivity) | dimensionless | 1 | `PerceptionChange` (can be negative) | None |

In Phase 1, people hired come from, and people leaving go to, outside the model; Phase 2 replaces that boundary with the labour market.

## Flows and variables

Enter these formulas exactly; they are the equations the prototype ran, in AnyLogic (Java) syntax.

| Name | AnyLogic element | Formula | Unit |
| --- | --- | --- | --- |
| `Year` | Dynamic variable | `2024 + time()` | year |
| `a` | Dynamic variable | `max(0, a_max - (a_max - a_2024) * pow(1 - g, Year - 2024))` | fraction |
| `P_AI` | Dynamic variable | `1 / ((1 - a) + a / s + a * v)` | dimensionless |
| `P_eff` | Dynamic variable | `AIOn ? A * P_AI + (1 - A) : 1` | dimensionless |
| `JevonsMult` | Dynamic variable | `min(JevonsCap, pow(1 / P_eff, -JevonsEps))` | dimensionless |
| `Demand` | Flow into Backlog | `BaseDemand * (1 + (Year >= StepYear ? DemandStep : 0)) * JevonsMult` | BFY/yr |
| `Capacity` | Dynamic variable | `Headcount * WorkPerPerson * P_eff` | BFY/yr |
| `Completion` | Flow out of Backlog | `min(Capacity, Backlog / MinCompletionTime)` | BFY/yr |
| `Abandonment` | Flow out of Backlog | `max(0, Backlog - Completion * AbandonTolerance) / AbandonTime` | BFY/yr |
| `DesiredHeadcount` | Dynamic variable | `Backlog / (TargetClearanceTime * WorkPerPerson * PerceivedP)` | persons |
| `Attrition` | Flow out of Headcount | `Headcount / AvgTenure` | persons/yr |
| `Adjustment` | Dynamic variable | `DesiredHeadcount > Headcount ? (DesiredHeadcount - Headcount) / HireAdjTime : (DesiredHeadcount - Headcount) / LayoffAdjTime` | persons/yr |
| `Hiring` | Flow into Headcount | `max(0, Attrition + Adjustment)` | persons/yr |
| `Layoffs` | Flow out of Headcount | `min(max(0, -(Attrition + Adjustment)), Headcount / MinLayoffTime)` | persons/yr |
| `AdoptionRate` | Flow into A | `AIOn ? min((p + q * A) * (1 - A), (1 - A) / MinAdoptionTime) : 0` | 1/yr |
| `PerceptionChange` | Flow into PerceivedP | `(P_eff - PerceivedP) / PerceptionTime` | 1/yr |

Three design choices to notice:

- **Hiring is slower than firing.** Gaps above target close over `HireAdjTime` (0.5 yr), gaps below over `LayoffAdjTime` (0.25 yr), the asymmetry described in the spec.
- **Managers react to perceived, not actual, productivity.** `PerceivedP` lags `P_eff` by about a year (a first-order smooth built as a stock), so headcount cuts trail productivity gains instead of jumping.
- **Every outflow is capped** (integrity rule 2): completion by `Backlog / MinCompletionTime`, layoffs by `Headcount / MinLayoffTime`, adoption by `(1 - A) / MinAdoptionTime`, so no stock can go negative or A above 1.

## Parameters

Values are illustrative and sized so the arithmetic is easy to check (100,000 people at baseline); calibration comes in Phase 7.

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `BaseDemand` | 100000 | BFY/yr | New IT work arriving each year |
| `WorkPerPerson` | 1 | BFY/person/yr | Output per person at baseline productivity |
| `TargetClearanceTime` | 0.5 | yr | How fast employers aim to clear the backlog |
| `MinCompletionTime` | 0.25 | yr | Fastest any backlog item can be finished |
| `AbandonTolerance` | 1.5 | yr | Backlog the system tolerates, in years of throughput |
| `AbandonTime` | 1 | yr | Time to cancel excess backlog |
| `AvgTenure` | 5 | yr | Average stay; attrition = 20%/yr |
| `HireAdjTime` | 0.5 | yr | Time to close a staffing shortfall |
| `LayoffAdjTime` | 0.25 | yr | Time to close a staffing surplus |
| `MinLayoffTime` | 0.25 | yr | Cap on how fast headcount can be cut |
| `PerceptionTime` | 1 | yr | Lag before managers recognise productivity gains |
| `AIOn` | true | boolean | Switches AI on or off for testing |
| `a_2024` | 0.20 | fraction | Automatable share of work in 2024 |
| `a_max` | 0.60 | fraction | Ceiling on the automatable share |
| `g` | 0.10 | 1/yr | Share of the remaining gap to a\_max closed each year |
| `s` | 5 | dimensionless | AI speed-up on automatable work |
| `v` | 0.05 | dimensionless | Verification overhead per unit of AI output |
| `p` | 0.03 | 1/yr | Bass innovation rate |
| `q` | 0.40 | 1/yr | Bass imitation rate |
| `A0` | 0.05 | fraction | Adoption in 2024 |
| `MinAdoptionTime` | 0.0625 | yr | Cap keeping A at or below 1 (equals the time step) |
| `JevonsEps` | 0 | dimensionless | Demand elasticity to cost; 0 switches the Jevons effect off |
| `JevonsCap` | 2 | dimensionless | Maximum demand multiplier from cheaper work |
| `DemandStep` | 0 | fraction | One-off demand change for testing |
| `StepYear` | 2028 | year | When the test step applies |

## Tests and reference results

Run the six tests in order; your AnyLogic results should land within about 1% of these prototype values. A bigger gap means a formula or link differs from the guide.

| Test | Settings changed from the Parameters table | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | Headcount flat at 100,000; Backlog flat at 50,000 |
| T2 Demand step | `AIOn = false`, `DemandStep = 0.2` | Adjusts to the new level without lasting oscillation | Brief overshoot to about 123,200 in 2030, settles at 120,000 by 2035 |
| T3 AI base case | None (`AIOn = true`) | Smooth decline that slows as adoption saturates | About 96,000 in 2026, 80,300 in 2030, 65,800 in 2035, 60,700 in 2040; `P_eff` 1.65 and `A` 0.99 in 2040 |
| T4 Jevons rebound | `JevonsEps = 0.5` | Cheaper work brings back some demand | About 77,600 in 2040, recovering roughly 40% of the T3 loss |
| T5 Time step check | Time step 0.03125 (1/32 yr) | Results barely change | Within 0.1% of T3 |
| T6 Extreme AI | `a_2024 = 0.5`, `a_max = 0.95`, `g = 0.5`, `s = 50`, `v = 0`, `p = 0.5`, `q = 1` | Nothing breaks under absurd inputs | Headcount falls to about 6,900 and levels off; no stock goes negative |

&#91;embedded content: prototype simulation of these exact equations (phase1\_sim.py), Euler, time step 1/16 yr, 2024-2040\]

T2's small overshoot is the hiring delay at work, an early glimpse of loop B13; T3 is loop B1 (productivity compression) on its own, and T4 adds R3.
