# Phase 6a build guide

Phase 6 is split in two. Phase 6a builds the demand side: seven consumer sectors and six work types, AI capability by work type, consumer AI adoption with regulatory drag, line-of-business (LOB) headcount, the application portfolio, seats, platform and cloud spend, and one IT budget per sector. The supply side (global SIs, boutiques, AI adoption per employer, sourcing and contracts by sector) stays as in Phase 5 and arrives in Phase 6b. Phase 6a is done when IT demand by work type responds to consumer AI (loop R2 against B9), LOB headcount and seats fall, and the budget binds in a downturn; every value below was verified in a prototype that conserves people and work exactly.

## Structure

Consumer AI adoption is the hub of Phase 6a. It creates IT work through AI projects, removes IT work by shrinking app portfolios and seats, and moves spend from services to AI seats and credits.

&#91;embedded content: Phase 6a structure · the demand side\]

The supply side reads only the total backlog and its blended productivity, so the Phase 5 model does not change. Each backlog cell is a sector and work type; work types differ in how much AI can automate, which is why the mix of work matters as much as its size.

## What changes from Phase 5

The labour market, vendor finance, contracts and sourcing all stay. What changes is where the work comes from and how productive AI makes each kind of work.

- **Add dimensions** `Sector` {`FIN`, `LEG`, `MED`, `GOV`, `MFG`, `LOG`, `RET`} and `WorkType` {`APP`, `DATA`, `SEC`, `GOVN`, `SUP`, `EUS`}: financial, legal, medical, government, manufacturing, logistics and retail; app development, data migration and transformation, security, governance, support and operations, end-user services.
- **Replace the scalar `Backlog`** with `BL[Sector, WorkType]`, and Phase 1's single demand with demand per cell, each work type driven by its own source (apps, retirements, cyber threat, regulation, seats, AI projects).
- **Replace the single automatable share** with one per work type (the spec's capability table). `P_eff` becomes the backlog-weighted blend across work types, and every formula that used `P_eff` keeps using it.
- **Add the consumer side:** consumer AI adoption per sector, LOB headcount, the application portfolio, billed seats, AI seat attach rate, and spend on seats, credits and cloud.
- **Add one IT budget per sector** that throttles discretionary demand when committed spend exceeds it (loop B11).
- **Delivery AI adoption** (`A`) now speeds up as AI gets cheaper relative to labour (loop R5).
- **Initial values:** all Phase 5 stocks keep their values; the old `Backlog` (55,056 BFY) is split across sectors and work types.

Nine design decisions:

- **The supply side waits for 6b.** One delivery adoption `A` still serves every employer, and Phase 5's sourcing shares apply to all sectors alike.
- **Every backlog cell clears at the same rate.** Employers work the whole backlog, so `P_eff` is the harmonic blend of work-type productivities weighted by backlog. Each cell's completion is its share of total completion.
- **The 2024 work-type mix is the same in every sector** (30% app development, 12% data, 10% security, 5% governance, 33% support, 10% end-user services). Sector-specific mixes are a calibration task for Phase 7.
- **`AIOn = false` switches off every AI effect,** consumer side included, so 2024 is a true steady state.
- **AI exposure of LOB work** = consumer adoption × the LOB automatable share. Displaced LOB staff leave the model, as the integrity rules require.
- **The budget is a ceiling, not a target.** It cuts app development, data and AI project demand only when committed spend exceeds it. Budget freed by cheaper IT is not spent automatically: whether it turns into more IT work is the Jevons lever (`JevonsEps`, default 0), now measured against the consumer's cost per unit of work rather than productivity.
- **Reinvested savings (R1)** add 20% of net LOB savings to the IT budget and speed up consumer adoption.
- **Regulation slows consumer adoption and adds governance work,** both in proportion to how much AI a sector uses. Drag ramps in between the EU AI Act dates (December 2027 to August 2028).
- **Seats are billed with a lag** (device refresh and licence renewal), and each AI seat or credit dollar is platform revenue except a 20% leakage straight to AI model providers.

## AnyLogic setup

Build the demand side next to the Phase 5 model and connect it at two points only: total backlog and `P_eff`. Check the steady state after each step with `AIOn = false`.

1. **Save a copy** of your working Phase 5 model as Phase 6a.
2. **Add the dimensions** `Sector` and `WorkType`, and the subdimension `Discretionary` {`APP`, `DATA`} of `WorkType`.
3. **Replace `Backlog`** with the stock `BL[Sector, WorkType]` and its flows (group A). Set every cell's demand temporarily to `BaseDemand * SectorShare[Sector] * WTMix[WorkType]`. With `AIOn = false` the model should behave exactly as Phase 5: demand 100,000 BFY a year, 84,135 employed, margin near 18%.
4. **Add capability by work type** (group B). Point `Capacity`, `PerceivedP`, `ClientP` and every other user of `P_eff` at the new blended `P_eff`.
5. **Add the consumer stocks** `AC`, `LOB`, `Port`, `SeatsB`, `Att` and their formulas (groups C and D). With AI off they must stay at their initial values.
6. **Add spend and the budget** (group E) and the stocks `SpendRatio` and `CostPerc`. With AI off, committed spend should be $12.81 billion against budgets totalling $13.49 billion (utilisation 0.95) in every sector.
7. **Switch demand to the full formulas** (group F), then add the cost effect on delivery adoption (group G). Run the tests.

Several formulas sum over the 42 backlog cells. If AnyLogic's array sum syntax gives trouble, add one dynamic variable per work type that adds up the seven sectors, then a total.

## Stocks and initial values

All Phase 5 stocks keep their values. `Backlog` is deleted and replaced by `BL`.

| Stock | Dimensions | Initial value | Unit | Meaning |
| --- | --- | --- | --- | --- |
| `BL` | `[Sector, WorkType]` | `55056 * SectorShare[Sector] * WTMix[WorkType]` (e.g. `BL[FIN, APP]` 4,129) | BFY | IT work waiting, by sector and work type |
| `AC` | `[Sector]` | 0.05 | fraction | Consumer AI adoption |
| `LOB` | `[Sector]` | `LOB0[Sector]` | persons | Line-of-business headcount |
| `Port` | `[Sector]` | `Port0[Sector]` | applications | Application portfolio |
| `SeatsB` | `[Sector]` | `Seats0[Sector]` | seats | Seats billed (follows actual seats at refresh and renewal) |
| `Att` | scalar | 0.02 | fraction | Share of seats with an AI add-on |
| `SpendRatio` | `[Sector]` | 0.95 | fraction | Committed IT spend over budget, smoothed over the budget cycle |
| `CostPerc` | scalar | 1 | index | Consumers' perceived cost per unit of IT work, relative to 2024 |

`LOB0`, `Port0` and `Seats0` are listed with the sector parameters. With AI off, 2024 totals are 2,017,800 LOB staff, 25,240 applications and 2,052,149 seats.

## Formulas

`s` stands for the current sector and `w` for the current work type. Sums run over all elements of the dimension named. Phase 5 formulas not listed here are unchanged; they keep using `P_eff`, which is now the blend from group A.

**A. Backlog and completion (replace Phase 1's scalar versions)**

| Name | Formula |
| --- | --- |
| `TotBL` | sum of `BL[s, w]` over all sectors and work types |
| `EffortBL` | sum of `BL[s, w] / Pw[w]` over all sectors and work types |
| `P_eff` | `TotBL / EffortBL` (backlog-weighted blend of work-type productivity) |
| `Capacity` | `WorkPerPerson * P_eff * EffStaff` (unchanged) |
| `Completion` | `min(Capacity, TotBL / MinCompletionTime)` |
| `ClearRate` | `Completion / TotBL` |
| `Comp[Sector, WorkType]` | `BL[s, w] * ClearRate` |
| `Aband[Sector, WorkType]` | `max(0, BL[s, w] * (1 - ClearRate * AbandonTolerance)) / AbandonTime` |
| `DesiredEff` | `TotBL / (TargetClearanceTime * WorkPerPerson * PerceivedP)` |
| `CompS[Sector]` | sum of `Comp[s, w]` over work types |
| `CS[Sector]` | `CompS[s] / Completion` (sector share of completed work) |

**B. AI capability by work type**

| Name | Formula |
| --- | --- |
| `aW[WorkType]` | `max(0, amax[w] - (amax[w] - a2024[w]) * pow(1 - g, Year - 2024))` |
| `PAI[WorkType]` | `1 / ((1 - aW[w]) + aW[w] / SpeedUp[w] + aW[w] * Verif[w])` |
| `Pw[WorkType]` | `AIOn ? A * PAI[w] + (1 - A) : 1` |

**C. Consumer AI and LOB headcount**

| Name | Formula |
| --- | --- |
| `LOBAuto` | `max(0, aL_max - (aL_max - aL_2024) * pow(1 - g, Year - 2024))` (share of LOB work AI can do) |
| `AIShockNow` | `(Year >= AIShockStart && Year < AIShockEnd) ? AIShockMult : 1` |
| `CreditCostPB` | `CreditCost2024 * pow(1 - AICostDecline, Year - 2024) * AIShockNow` (USD per BFY of agent work) |
| `CEc` | `min(CEMax, max(CEMin, pow(CreditCost2024 / CreditCostPB, CostAdoptElast)))` |
| `RegRamp` | `min(1, max(0, (Year - RegStart) / (RegEnd - RegStart)))` |
| `RegDrag[Sector]` | `min(0.95, RegScenario * RegDragLevel[s] * RegRamp)` |
| `AIexp[Sector]` | `AIOn ? AC[s] * LOBAuto : 0` (share of LOB work automated) |
| `LOBTarget[Sector]` | `LOB0[s] * (1 - AIexp[s])` |
| `AgentWork[Sector]` | `LOB0[s] - LOBTarget[s]` (BFY of LOB work done by agents) |
| `CreditSpend[Sector]` | `AgentWork[s] * CreditCostPB` |
| `NetSavings[Sector]` | `(LOB0[s] - LOB[s]) * LOBWage[s] - CreditSpend[s]` |
| `ReinvEff[Sector]` | `1 + ReinvestAdoptSens * min(1, max(0, ReinvestFrac * NetSavings[s] / Budget0[s]))` |
| `AdoptC[Sector]` | `AIOn ? min((pC + qC * AC[s]) * CEc * (1 - RegDrag[s]) * ReinvEff[s] * (1 - AC[s]), (1 - AC[s]) / MinAdoptionTime) : 0` |

**D. Applications and seats**

| Name | Formula |
| --- | --- |
| `NewApps0[Sector]` | `Port0[s] / AppLife` |
| `NewApps[Sector]` | `NewApps0[s] * (1 - AppDisplacement * AIexp[s])` |
| `Retire[Sector]` | `Port[s] / AppLife * (1 + RetireAccel * AIexp[s])` |
| `ConsIT` | total `H` of units `IH` and `GCC` over all levels |
| `Seats[Sector]` | `LOB[s] + ConsIT * CS[s]` |
| `AttAdopt` | `AIOn ? min((pAtt + qAtt * Att) * (1 - Att), (1 - Att) / MinAdoptionTime) : 0` |

**E. Spend and the budget**

| Name | Formula |
| --- | --- |
| `ServicesSpend` | `ConsumerSpend` (Phase 5 formula) |
| `CostIdx` | `(ServicesSpend / Completion) / CostPerBFY0` |
| `SeatSpend[Sector]` | `SeatsB[s] * (BaseSeatPrice + Att * AISeatPrice)` |
| `CloudPB` | `CloudPerBFY * (1 + CloudAISens * (1 - 1 / P_eff))` |
| `CloudSpend[Sector]` | `CloudPB * CompS[s]` |
| `Committed[Sector]` | `ServicesSpend * CS[s] + SeatSpend[s] + CreditSpend[s] + CloudSpend[s]` |
| `BudgetGrowth` | `pow(1 + ITBudgetGrowth, Year - 2024) * ((Year >= BudgetShockStart && Year < BudgetShockEnd) ? 1 - BudgetShock : 1)` |
| `Budget[Sector]` | `Budget0[s] * BudgetGrowth + ReinvestFrac * max(0, NetSavings[s])` |
| `Approval[Sector]` | `min(1, max(MinApproval, 1 - ApprovalSens * max(0, SpendRatio[s] - 1)))` |
| `PlatformRevenue` (output) | sum of `SeatSpend` + sum of `CreditSpend` × `(1 - Leakage)` |
| `AIProviderSpend` (output) | sum of `CreditSpend` × `Leakage` + `AICost` + `AICostPerUnit * (1 - 1 / P_eff) * (Delivered[IH] + Delivered[GCC])` |
| `HyperscalerSpend` (output) | sum of `CloudSpend` |

**F. Demand by sector and work type**

| Name | Formula |
| --- | --- |
| `Jev` | `min(JevonsCap, pow(CostPerc, -JevonsEps))` (replaces Phase 1's `JevonsMult`) |
| `CyberMult` | `1 + (CyberEnd - 1) * min(1, max(0, (Year - CyberStart) / (CyberRampEnd - CyberStart)))` |
| `Base[Sector]` | `BaseDemand * SectorShare[s] * (Year >= StepYear ? 1 + DemandStep : 1)` |
| `PortRatio[Sector]` | `Port[s] / Port0[s]` |
| `DemMult[Sector, WorkType]` | `APP`: `WTMix[APP] * ((1 - NewAppWeight) * PortRatio[s] + NewAppWeight * NewApps[s] / NewApps0[s]) * Jev * Approval[s]` · `DATA`: `WTMix[DATA] * ((1 - MigWeight) + MigWeight * Retire[s] / NewApps0[s]) * Jev * Approval[s]` · `SEC`: `WTMix[SEC] * CyberMult` · `GOVN`: `WTMix[GOVN] * (1 + (AIOn ? GovRegSens * RegDrag[s] * AC[s] : 0))` · `SUP`: `WTMix[SUP] * ((1 - SupPortShare) + SupPortShare * PortRatio[s])` · `EUS`: `WTMix[EUS] * SeatsB[s] / Seats0[s]` |
| `AIBuild[Sector]` | `(AIOn ? BuildRate * AdoptC[s] + RunRate * AC[s] : 0) * Jev * Approval[s]` (AI projects and the work of running them, as a share of base demand) |
| `Demand[Sector, WorkType]` | `Base[s] * (DemMult[s, w] + AIBuild[s] * BuildMix[w])` |

**G. Delivery AI adoption (replaces Phase 1's adoption flow)**

| Name | Formula |
| --- | --- |
| `LabourCostPB` | sum of `LabourCost` over all units, divided by `EffStaff` (USD per BFY of capacity) |
| `CE` | `min(CEMax, max(CEMin, pow((LabourCostPB / LabourCostPB0) * (AICost2024 / AICostPerUnit), CostAdoptElast)))` |
| `Adoption` | `AIOn ? min((p + q * A) * CE * (1 - A), (1 - A) / MinAdoptionTime) : 0` |

**H. Stock equations**

| Stock | Derivative |
| --- | --- |
| `BL[Sector, WorkType]` | `Demand[s, w] - Comp[s, w] - Aband[s, w]` |
| `AC[Sector]` | `AdoptC[s]` |
| `LOB[Sector]` | `(LOBTarget[s] - LOB[s]) / LOBAdjTime` |
| `Port[Sector]` | `NewApps[s] - Retire[s]` |
| `SeatsB[Sector]` | `(Seats[s] - SeatsB[s]) / SeatAdjTime` |
| `Att` | `AttAdopt` |
| `SpendRatio[Sector]` | `(Committed[s] / Budget[s] - SpendRatio[s]) / BudgetCycle` |
| `CostPerc` | `(CostIdx - CostPerc) / CostPerceptionTime` |
| `A` | `Adoption` |

The two demand loops sit in group F. R2: consumer adoption adds AI project work through `AIBuild`. B9: the same adoption shrinks the portfolio through `NewApps` and `Retire`, cutting app development and support. The balance between them sets the direction of IT demand.

## Parameters

Phase 1-5 parameters keep their values, except that Phase 1's scalar `a_2024`, `a_max`, `s` and `v` give way to the work-type arrays below (`g` stays). Every value is an illustrative first guess for Phase 7 to calibrate. Rows marked calibrated come from `calibrate6a.py` and must be recomputed if other parameters change.

**Sector arrays `[Sector]`**

| Parameter | FIN · LEG · MED · GOV · MFG · LOG · RET | Unit | Meaning |
| --- | --- | --- | --- |
| `SectorShare` | 0.25 · 0.03 · 0.12 · 0.18 · 0.17 · 0.08 · 0.17 | fraction | Share of 2024 IT work |
| `LOBWage` | 90,000 · 85,000 · 65,000 · 70,000 · 55,000 · 50,000 · 40,000 | USD/person/yr | Blended LOB pay, India and onshore together |
| `RegDragLevel` | 0.30 · 0.20 · 0.30 · 0.35 · 0.10 · 0.10 · 0.05 | fraction | Cut in consumer adoption speed once regulation applies (base scenario) |
| `LOB0` | 189,300 · 60,600 · 242,300 · 287,700 · 462,500 · 217,600 · 557,800 | persons | 2024 LOB headcount (IT staff as 10%, 4%, 4%, 5%, 3%, 3% and 2.5% of all staff) |
| `Port0` | 6,310 · 757 · 3,029 · 4,543 · 4,291 · 2,019 · 4,291 | applications | 2024 portfolio (0.3 applications per IT employee) |
| `Seats0` | 197,887 · 61,630 · 246,422 · 293,883 · 468,339 · 220,348 · 563,639 | seats | 2024 seats: LOB plus the sector's in-house and GCC IT staff |
| `Budget0` | 2,872.3 · 404.8 · 1,619.0 · 2,308.3 · 2,482.7 · 1,168.3 · 2,633.9 (calibrated) | USD million/yr | 2024 IT budget: committed spend divided by `NormalUtil` |

**Work-type arrays `[WorkType]`**

| Parameter | APP · DATA · SEC · GOVN · SUP · EUS | Unit | Meaning |
| --- | --- | --- | --- |
| `WTMix` | 0.30 · 0.12 · 0.10 · 0.05 · 0.33 · 0.10 | fraction | 2024 mix of IT work (every sector) |
| `a2024` | 0.25 · 0.35 · 0.15 · 0.10 · 0.30 · 0.35 | fraction | Automatable share in 2024 (spec table) |
| `amax` | 0.60 · 0.80 · 0.45 · 0.35 · 0.70 · 0.80 | fraction | Ceiling on the automatable share |
| `SpeedUp` | 5 · 5 · 4 · 3 · 5 · 5 | dimensionless | AI speed-up on automatable work |
| `Verif` | 0.05 for every type | dimensionless | Verification overhead per unit of AI output |
| `BuildMix` | 0.35 · 0.35 · 0.10 · 0.15 · 0.05 · 0 | fraction | Split of AI project work across work types |

**Scalars**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `CostAdoptElast` | 0.3 | dimensionless | How strongly cheaper AI speeds adoption (delivery and consumer) |
| `CEMin`, `CEMax` | 0.5, 1.5 | dimensionless | Limits on that cost effect |
| `LabourCostPB0` | 68,990 (calibrated) | USD/BFY | 2024 labour cost per unit of capacity |
| `MinAdoptionTime` | 0.0625 | yr | Clamp that keeps adoption fractions below 1 |
| `pC`, `qC` | 0.02, 0.30 | 1/yr | Consumer AI innovation and imitation rates |
| `AC0` | 0.05 | fraction | Consumer AI adoption in 2024 (initial value of `AC`) |
| `aL_2024`, `aL_max` | 0.05, 0.35 | fraction | LOB automatable share in 2024 and its ceiling |
| `LOBAdjTime` | 2 | yr | How fast LOB headcount follows its target (mostly through attrition) |
| `CreditCost2024` | 30,000 | USD/BFY | 2024 credit cost of one FTE-year of agent work; falls with `AICostDecline` |
| `ReinvestFrac` | 0.2 | fraction | Share of net LOB savings added to the IT budget (R1) |
| `ReinvestAdoptSens` | 0.5 | dimensionless | Extra adoption speed from reinvested savings |
| `RegScenario` | 1 | multiplier | 0 light-touch, 1 base, 1.5 strict |
| `RegStart`, `RegEnd` | 2027.9, 2028.6 | year | Ramp of regulatory drag (EU AI Act stand-alone, then product rules) |
| `GovRegSens` | 2 | dimensionless | Extra governance work per unit of drag × adoption |
| `AppLife` | 8 | yr | Average application life |
| `AppDisplacement` | 0.6 | fraction | How strongly agents displace new applications (d in the spec) |
| `RetireAccel` | 1 | dimensionless | Extra retirement rate at full AI exposure |
| `NewAppWeight` | 0.5 | fraction | Share of app development that builds new apps (the rest enhances the portfolio) |
| `MigWeight` | 0.3 | fraction | Share of data work driven by retirements |
| `SupPortShare` | 0.8 | fraction | Share of support work that scales with the portfolio |
| `SeatAdjTime` | 2 | yr | Lag of billed seats behind actual seats |
| `BaseSeatPrice` | 1,500 | USD/seat/yr | Devices and per-seat software |
| `AISeatPrice` | 360 | USD/seat/yr | AI add-on per seat |
| `pAtt`, `qAtt`, `Att0` | 0.05, 0.5, 0.02 | 1/yr, 1/yr, fraction | AI seat attach diffusion |
| `CloudPerBFY` | 13,000 | USD/BFY | Cloud spend per unit of IT work completed in 2024 |
| `CloudAISens` | 0.5 | dimensionless | Extra cloud per unit as AI does more of the work |
| `Leakage` | 0.2 | fraction | Share of credit spend going straight to AI model providers |
| `BuildRate` | 0.6 | dimensionless | AI project work per unit of adoption flow, as a share of base demand |
| `RunRate` | 0.10 | dimensionless | Ongoing work of running AI, at full adoption, as a share of base demand |
| `JevonsEps`, `JevonsCap` | 0, 2 | dimensionless | Demand response to cheaper IT work (now on consumer cost) and its cap |
| `CostPerceptionTime` | 1.5 | yr | Delay before consumers notice cost changes |
| `CostPerBFY0` | 84,220 (calibrated) | USD/BFY | 2024 consumer cost per unit of IT services work |
| `NormalUtil` | 0.95 | fraction | Normal ratio of committed spend to budget |
| `ApprovalSens` | 2 | dimensionless | Cut in discretionary demand per unit of overspend |
| `MinApproval` | 0.2 | fraction | Floor on approvals |
| `BudgetCycle` | 1 | yr | Budget smoothing time |
| `ITBudgetGrowth` | 0 | 1/yr | Real budget growth (macro lever) |
| `BudgetShock`, `BudgetShockStart`, `BudgetShockEnd` | 0, 2030, 2032 | fraction, year | Downturn lever |
| `CyberEnd`, `CyberStart`, `CyberRampEnd` | 1, 2026, 2030 | multiplier, year | AI-driven cyber threat lever on security demand |

## Tests and reference results

Run the ten runs in order; results should land within about 1% of these prototype values. `PeopleCheck` must stay at 92,546 and `WorkCheck` at 1 in every run.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | Demand 100,000 BFY a year; 84,135 employed; 2,017,800 LOB staff, 25,240 applications, 2,052,149 seats; spend $8.42 billion on services, $3.09 billion on seats, $1.30 billion on cloud; budget utilisation 0.95 in every sector; margin between 17.6% and 18.0% |
| T2 AI base case | None (`AIOn = true`) | Demand rises, then falls; LOB and seats shrink | IT demand jumps to 102,482 when AI switches on, peaks at 108,635 in 2032 and is 97,306 in 2040. By work type, 2024 to 2040 (thousand BFY): app development 30.0 to 27.4, data 12.0 to 15.5, security 10.0 to 11.0, governance 5.0 to 8.6, support 33.0 to 27.1, end-user services 10.0 to 7.7. Employed 44,967 in 2040 (vendor 22,603, in-house 18,483, GCC 3,882). Consumer adoption in 2032: FIN 0.62, GOV 0.60, RET 0.71. By 2040 LOB staff 1.48 million (-27%), applications 19,120 (-24%), seats 1.50 million. Platform revenue per seat $1,566, then $2,955 in 2032, then $2,636 in 2040; credits peak at $2.48 billion in 2033. Budget utilisation peaks at 1.03 in 2027 (approvals cut to 0.87), then falls to 0.54 by 2040. Margin about 30% at its 2029-2030 peak and 22.3% in 2040 |
| T3 R2 against B9 | AI on; run a: `AppDisplacement = 0`, `RetireAccel = 0`; run b: `BuildRate = 0`, `RunRate = 0` | Which loop wins | 2040 demand 110,042 without app displacement (a) and 87,010 without AI projects (b), against 97,306 in T2. Employed 50,295 (a) and 40,116 (b) |
| T4 Jevons | AI on, `JevonsEps = 0.5` | Cheaper IT creates work | Demand peaks at 119,515 in 2034 and is 111,320 in 2040; employed 51,247 in 2040 |
| T5 Regulation | AI on; run a: `RegScenario = 1.5`; run b: `RegScenario = 0` | Regulated sectors adopt later | Consumer adoption in 2032, strict (a) vs none (b): FIN 0.55 vs 0.73, GOV 0.52 vs 0.73, RET 0.70 vs 0.73. Governance demand in 2040 9,500 vs 6,500 BFY a year; employed 45,846 vs 43,232 |
| T6 Budget downturn | AI on, `BudgetShock = 0.2` (2030-2032) | The budget binds (B11) | Utilisation jumps to 1.19 in 2030; demand 101,920 in 2032 (108,635 in T2) and employed 54,405 (58,043); back in line by 2035 |
| T7 Time step check | Time step 1/32 yr only | Results barely change | Within 0.3% of T2 |
| T8 Extreme | Phase 2 extreme AI settings plus `pC = 0.5`, `qC = 1`, `aL_max = 0.9`, `AIShockMult = 5`, `BudgetShock = 0.6`, `CyberEnd = 2`, `RegScenario = 2.5`, `JevonsEps = 1`, `PriceShock = 0.5` | Nothing breaks | No stock goes negative; `PeopleCheck` and `WorkCheck` hold |

&#91;embedded content: prototype simulation of these exact equations (phase6a\_sim.py), Euler, time step 1/16 yr\]

**Reading the results**

- **Consumer AI first adds IT work, then removes it.** AI projects (R2) lift demand by about 9% to 2032. After that, shrinking app portfolios and seats (B9, B10) win, and by 2040 demand is 3% below 2024. The balance is fragile: T3 shows the two loops are each worth 10-13% of demand by 2040.
- **The mix of IT work changes more than its size.** Governance work grows 72% and data work 29%; support falls 18% and end-user services 23%. App development falls only 9%, because AI projects partly replace the apps agents displace.
- **IT employment falls further than in Phase 5** (45,000 against 48,000 by 2040). Cheaper AI speeds delivery adoption (R5), and that outweighs the extra demand.
- **AI spend crowds out services early.** Credits and AI seats push committed spend above budget in 2026-2028, trimming discretionary IT projects by up to 13%. Once AI makes services much cheaper, budgets have room to spare.
- **That spare budget is the biggest open assumption for Q1.** With `JevonsEps = 0` it simply goes unspent; with 0.5 it buys 14% more IT work in 2040 and keeps 6,000 more people employed. Phase 7 should calibrate it against how IT spending responded to past price falls.
- **Platform revenue per seat almost doubles by 2032,** so seats plus credits more than offset fewer seats until falling credit prices catch up in the late 2030s.
