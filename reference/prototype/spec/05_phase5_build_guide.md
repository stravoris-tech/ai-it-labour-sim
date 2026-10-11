# Phase 5 build guide

Phase 5 replaces Phase 4's fixed work shares and single price index with contracts. Vendor work is held in contract stocks by type (fixed price, time and materials, managed services, staff augmentation, outcome-based) and by vintage (2024 legacy deals and new signings). Contracts reprice when they renew; their length is negotiated; the type signed is a logit choice that weighs what consumers and vendors each want; and every expiring contract, along with part of the work done in-house and in GCCs, is put back to a sourcing logit that decides who does the work next. It is done when contract shares respond to the pressure gap; every value below was verified in a prototype that conserves people and work exactly.

## Structure

Work is held in three places: in-house teams, GCCs and vendor contracts. Each year some of it comes up for a decision, and two choices decide where it goes next and on what terms.

&#91;embedded content: Phase 5 structure · work shares, contracts and the two choices\]

Half of the vendor work that expires is renewed with the vendor without competition. The other half, plus half of the in-house and GCC work that comes up for review, goes to the sourcing choice. Everything the vendor signs, renewals and wins alike, goes through the contract-type choice, which sets the type, the term and the price. Phase 4's margin and viability still drive the vendor's side: weak viability makes it a riskier supplier (R6), and lowers its bargaining power so that terms shorten (R8).

## What changes from Phase 4

The labour model and most of the money layer stay. What changes is how work is divided between in-house teams, GCCs and the vendor, and how the vendor is paid for it.

- **Remove:** the fixed `InHouseShare`, the `GCCShare` ramp, the vendor share effect `VSE` and its parameters (`ShareSens`, `VSEMin`, `VSEMax`, `ShareAdjTime`), and the single `PriceIndex` stock with `RepricingTime`.
- **Add:** two dimensions, `ContractType` {`FP`, `TM`, `MS`, `SA`, `OB`} and `Option` {`IH`, `GCC`, `VEND`}; contract stocks by type and vintage; work-share stocks for in-house and GCC; perceived sourcing shares; a competitive discount; a sales cost.
- **Change `UnitShare`:** in-house, GCC and vendor shares now come from stocks that only move when contracts expire or in-house work is reviewed.
- **Change revenue:** each contract type carries its own price index; time and materials and staff augmentation bill effort, so their revenue per unit of work falls as productivity rises.
- **Keep all labour initial values from Phase 4.** At 2024 the work shares are unchanged (30% in-house, 10% GCC, 60% vendor), so the labour steady state is the same. Only `Price[VI]` and the starting `Overhead` change, to absorb the new sales cost.

Eight design decisions:

- **Contract stocks measure shares of total work, not dollars.** The backlog still says how much work there is; the contract stocks say who does it and on what terms. In-house, GCC and vendor contracts always add up to 1, which is easy to check.
- **Legacy durations are the no-AI base durations.** For the model to sit still with AI off, new contracts must start at the same length as legacy ones. New-contract terms then shorten as AI makes future prices uncertain. The spec's shorter "new-contract base durations" are now roughly what the formula produces at peak AI pressure.
- **Outcome-based stays its own type** (this settles an open decision), with a small 2024 legacy share of 3% so the choice model has a starting point. Licensing moves to Phase 6, with seats and platform spend, because it isn't services labour.
- **Consumers distrust effort billing as AI spreads.** Under time and materials and staff augmentation, vendors have little reason to use AI fully, so consumers expect to pay for hours AI should have removed. This is the consumer side of loop B2.
- **Sourcing chooses between in-house, GCC and one vendor archetype.** Global SIs and boutiques arrive in Phase 6. The GCC ramp becomes a value lever, `GCCAppealEnd`; GCC setup capacity is also left for Phase 6.
- **Price competition (B12) has two triggers.** A vendor losing share cuts prices, but only while it is profitable. Rival vendors also bid away margin above normal. The second trigger was needed: without it, the AI windfall seen in Phase 4 persisted.
- **R6 and R8 change route.** R6 now runs through the sourcing choice: weak viability makes the vendor a riskier choice. R8 runs through vendor bargaining power, which shortens or lengthens new contracts.
- **`PriceShock` now cuts all vendor revenue at once** (contracts in force and new signings), and clients see the lower price when choosing a supplier.

## AnyLogic setup

Build the contract layer first and check it holds still before letting it choose anything. Both choice models are calibrated so that, with AI off, they reproduce exactly the flows that keep 2024 steady.

1. **Save a copy** of your working Phase 4 model as Phase 5.
2. **Add the dimensions** `ContractType` {`FP`, `TM`, `MS`, `SA`, `OB`} and `Option` {`IH`, `GCC`, `VEND`}, and the subdimensions `EffortTypes` {`TM`, `SA`} and `PricedTypes` {`FP`, `MS`, `OB`}.
3. **Delete** `VSE`, `PriceIndex`, `PriceTarget`, `VendorBase`, `Lost`, `GCCShare` and their parameters (listed under What changes).
4. **Add the stocks** from the Stocks section, the parameters from the Parameters section, and change `Price[VI]` and the `Overhead` initial value.
5. **Build the contract block** (formula groups B and C) with the type shares temporarily fixed at the signing shares in the test table (`FP` 28.8%, `TM` 41.1%, `MS` 7.5%, `SA` 20.6%, `OB` 2.1%). With AI off, revenue should sit at $3.91 billion and margin near 18%.
6. **Add the sourcing flows** (group D) and change `UnitShare` (group A). With AI off, `IHWork` should stay at 0.30 and `GCCWork` at 0.10.
7. **Switch on the two choice models** (groups E and F). With AI off, nothing should move: the logit targets equal the initial perceived shares.
8. **Add competition and bargaining power** (group G), then run the tests in order.

Each logit is two array variables: `Score[ContractType]` (or `Value[Option]`) with a formula per element, then `TypeShare[k] = exp(Score[k]) / (exp(Score[FP]) + exp(Score[TM]) + exp(Score[MS]) + exp(Score[SA]) + exp(Score[OB]))`. Writing the five terms out avoids any doubt about array sum syntax.

## Stocks and initial values

The starting point is the Phase 4 steady state: 84,135 employed, 49,786 at the vendor, 60% of work outsourced. All labour stocks and the finance stocks not listed below keep their Phase 4 values.

**New stocks**

| Stock | Initial value | Unit | Meaning |
| --- | --- | --- | --- |
| `Leg[ContractType]` | FP 0.21 · TM 0.18 · MS 0.132 · SA 0.06 · OB 0.018 | share of total work | Legacy contracts in force at 2024 (vendor share 0.6 times the 2024 mix) |
| `NewVol[ContractType]` | 0 | share of total work | Contracts signed since 2024, including renewals |
| `NewDurW[ContractType]` | 0 | share × yr | Duration-weighted new volume; divided by `NewVol` it gives the average term in force |
| `NewPriceW[ContractType]` | 0 | share × index | Price-weighted new volume (rate-weighted for `TM` and `SA`); divided by `NewVol` it gives the average price index |
| `IHWork` | 0.30 | share of total work | Work done by consumer in-house teams |
| `GCCWork` | 0.10 | share of total work | Work done in GCCs |
| `SrcPerc[Option]` | IH 0.1938 · GCC 0.0517 · VEND 0.7545 | fraction | Perceived sourcing shares of contested work (they sum to 1) |
| `ClientPRef` | 1 | dimensionless | Smoothed `ClientP`, used to measure its trend |
| `Disc` | 0 | fraction | Competitive discount on new signings |
| `ShareRef` | 0.6 | share of total work | The work share the vendor regards as normal |

**Changed and removed**

- `Overhead` starts at 312,512,000 USD/yr (it was 302,400,000).
- `Viability` starts at 0.18, equal to the recalibrated `NormalMargin`.
- `VSE` and `PriceIndex` are deleted.

The new-vintage stocks start empty, so `AvgDur` and `AvgP` fall back to the current signing values until the first contracts arrive (see the formulas). The initial `SrcPerc` values are not the work shares: they are the shares of contested decisions, which favour the vendor because vendor contracts come up for renewal far more often than in-house work is reviewed.

## Formulas

Formulas with `[ContractType]` or `[Option]` apply to every element unless split by element. `k` stands for the current contract type. Phase 4 variables used here (`Dev`, `DevEff`, `Delivered`, `LabourCost`, `VendorLabour`, `VisaCost`, `AICost`, `AICostPerUnit`) keep their Phase 4 formulas.

**A. Changed Phase 4 formulas**

| Name | Formula |
| --- | --- |
| `VendorShare` | `Leg[FP] + ... + Leg[OB] + NewVol[FP] + ... + NewVol[OB]` |
| `UnitShare[Unit]` | `IH`: `IHWork` · `GCC`: `GCCWork` · `VI`: `VendorShare * (1 - OnsiteShare)` · `OV`: `VendorShare * OnsiteShare * VisaMix` · `OL`: `VendorShare * OnsiteShare * (1 - VisaMix)` |
| `Revenue` | `BaseRev * AvgIdx * (1 - ShockNow)` |
| `VendorCost` | `VendorLabour + VisaCost + AICost + Overhead + SalesCost` |
| `ConsumerSpend` (output) | `LabourCost[IH] + LabourCost[GCC] * (1 + GCCOverhead) + Revenue + AICostPerUnit * (1 - 1 / P_eff) * (Delivered[IH] + Delivered[GCC])` |
| `WorkCheck` (check) | `IHWork + GCCWork + VendorShare` (must stay at 1) |

**B. Contract terms and prices**

| Name | Formula |
| --- | --- |
| `PU` | `max(0, (ClientP - ClientPRef) / (ClientPRef * TrendTime))` (expected yearly fall in cost per unit of work) |
| `Power` | `min(PowerMax, max(PowerMin, 1 + PowerSens * Dev))` (vendor bargaining power) |
| `PassShare[ContractType]` | `FP`: 0 · `TM`: 1 · `MS`: `MSGlideShare` · `SA`: 1 · `OB`: `OBGainShare` (share of in-term productivity gains passed to the consumer) |
| `Dnew[ContractType]` | `max(MinDur, BaseDur[k] / (1 + DurPUSens * PU) * pow(Power, DurPowerElast))` |
| `AvgDur[ContractType]` | `NewVol[k] > 1e-12 ? NewDurW[k] / NewVol[k] : Dnew[k]` |
| `Anchor` | `pow(1 / ClientP, PassThrough)` (price consumers expect after AI) |
| `PNew[ContractType]` | `PricedTypes`: `Anchor * (1 - Disc)` · `EffortTypes`: `1 - Disc` (a rate; revenue divides it by `P_eff`) |
| `AvgP[ContractType]` | `NewVol[k] > 1e-12 ? NewPriceW[k] / NewVol[k] : PNew[k]` |
| `Glide[ContractType]` | `MS`, `OB`: `PassShare[k] * PU` · `FP`, `TM`, `SA`: 0 |

**C. Expiries and revenue**

| Name | Formula |
| --- | --- |
| `ExpLeg[ContractType]` | `Leg[k] / BaseDur[k]` |
| `ExpNew[ContractType]` | `NewVol[k] / AvgDur[k]` |
| `Expiry` | sum of `ExpLeg` and `ExpNew` over all five types |
| `IdxVol[ContractType]` | `PricedTypes`: `Leg[k] + NewPriceW[k]` · `EffortTypes`: `(Leg[k] + NewPriceW[k]) / P_eff` |
| `AvgIdx` | `(IdxVol[FP] + ... + IdxVol[OB]) / VendorShare` |
| `VendDel` | `Delivered[VI] + Delivered[OV] + Delivered[OL]` |
| `BaseRev` | `Delivered[VI] * Price[VI] + Delivered[OV] * Price[OV] + Delivered[OL] * Price[OL]` |
| `BasePriceAvg` | `BaseRev / VendDel` |
| `ShockNow` | `Year >= PriceShockYear ? PriceShock : 0` |
| `SalesCost` | `SalesCostRate * Revenue * BookTurnover` |

**D. Sourcing flows**

| Name | Formula |
| --- | --- |
| `IHTurn` | `IHWork / IHReviewTime` |
| `GCCTurn` | `GCCWork / GCCReviewTime` |
| `Contested` | `Contest * (Expiry + IHTurn + GCCTurn)` (work put out to choice each year) |
| `VendSign` | `(1 - Contest) * Expiry + Contested * SrcPerc[VEND]` (renewals with the incumbent plus contested wins) |
| `BookTurnover` | `VendSign / VendorShare` |
| `Signings[ContractType]` | `VendSign * TypeShare[k]` |

**E. Contract-type choice**

| Name | Formula |
| --- | --- |
| `CostIdx` | `(VendorCost / VendDel) / BasePriceAvg` (vendor cost per unit of work relative to the base price) |
| `WV` | `min(0.9, max(0.1, BargainW0 * Power))` (vendor weight); `WC = 1 - WV` |
| `TTFRatio[Region]` | `TTFPool[Region, MID] / NormalTTF[Region, MID]` |
| `Ucons[ContractType]` | `-ConsSens * (1 - PassShare[k]) * PU * Dnew[k] / 2`, plus for `EffortTypes` `- ConsSens * EffortDistrust * (1 - 1 / ClientP)`, plus for `SA` `+ SATTFSens * min(2, max(-1, TTFRatio[ONSHORE] - 1))` |
| `Rterm[ContractType]` | `PricedTypes`: `PNew[k] * (1 - PassShare[k] * PU * Dnew[k] / 2)` · `EffortTypes`: `PNew[k] / P_eff * (1 - PU * Dnew[k] / 2)` (expected revenue per unit of work over the term) |
| `ProfitK[ContractType]` | `Rterm[k] - CostIdx * (1 - PU * Dnew[k] / 2)` |
| `Uvend[ContractType]` | `VendSens * (ProfitK[k] - NormalMargin) / NormalMargin` |
| `Score[ContractType]` | `TypeASC[k] + WC * Ucons[k] + WV * Uvend[k]` |
| `TypeShare[ContractType]` | `exp(Score[k]) / (exp(Score[FP]) + exp(Score[TM]) + exp(Score[MS]) + exp(Score[SA]) + exp(Score[OB]))` |

**F. Sourcing choice**

| Name | Formula |
| --- | --- |
| `AvgWageMult` | `Share[JUNIOR] * WageMult[JUNIOR] + Share[MID] * WageMult[MID] + Share[SENIOR] * WageMult[SENIOR]` |
| `AvgWork` | `Share[JUNIOR] * W[JUNIOR] + Share[MID] * W[MID] + Share[SENIOR] * W[SENIOR]` |
| `AICostPB` | `AICostPerUnit * (1 - 1 / ClientP)` |
| `SrcCost[Option]` | `IH`: `BaseWage[IH] * WI[IH] * AvgWageMult / (AvgWork * ClientP) + AICostPB` · `GCC`: `BaseWage[GCC] * WI[GCC] * AvgWageMult * (1 + GCCOverhead) / (AvgWork * ClientP) + AICostPB` · `VEND`: `BasePriceAvg * Anchor * (1 - Disc) * (1 - ShockNow)` (USD per unit of work) |
| `VendRisk` | `ViabSens * min(0, DevEff) - ExitPenalty * max(0, ExitThreshold - Viability) - VisaRiskSens * max(0, TightPerc - VTBase)` |
| `GCCAppeal` | `GCCAppealEnd * min(1, max(0, (Year - GCCRampStart) / (GCCRampEnd - GCCRampStart)))` |
| `SrcValue[Option]` | `SrcASC[e] - SrcCostSens * SrcCost[e] / CostRef - CapSens * max(0, TTFRatio[pool] - 1)`, where the pool is `ONSHORE` for `IH` and `INDIA` for `GCC` and `VEND`; add `GCCAppeal` for `GCC` and `VendRisk` for `VEND` |
| `SrcTarget[Option]` | `exp(SrcValue[e]) / (exp(SrcValue[IH]) + exp(SrcValue[GCC]) + exp(SrcValue[VEND]))` |

**G. Competition**

| Name | Formula |
| --- | --- |
| `ShareLoss` | `max(0, (ShareRef - VendorShare) / ShareRef)` |
| `Afford` | `min(1, max(0, Viability / NormalMargin))` (vendors defend share with price only while profitable) |
| `DiscTarget` | `min(MaxDisc, max(0, ShareLossSens * ShareLoss * Afford + RivalSens * max(0, DevEff)))` |

`CostProgTarget`, `Restraint` and `WITarget` keep their Phase 4 formulas.

**H. Stock equations**

| Stock | Derivative |
| --- | --- |
| `Leg[ContractType]` | `-ExpLeg[k]` |
| `NewVol[ContractType]` | `Signings[k] - ExpNew[k]` |
| `NewDurW[ContractType]` | `Signings[k] * Dnew[k] - NewVol[k]` |
| `NewPriceW[ContractType]` | `Signings[k] * PNew[k] - ExpNew[k] * AvgP[k] - NewPriceW[k] * Glide[k]` |
| `IHWork` | `Contested * SrcPerc[IH] - Contest * IHTurn` |
| `GCCWork` | `Contested * SrcPerc[GCC] - Contest * GCCTurn` |
| `SrcPerc[Option]` | `(SrcTarget[e] - SrcPerc[e]) / SrcPerceptionTime` |
| `ClientPRef` | `(ClientP - ClientPRef) / TrendTime` |
| `Disc` | `(DiscTarget - Disc) / DiscAdjTime` |
| `ShareRef` | `(VendorShare - ShareRef) / ShareRefTime` |

`ClientP`, `Overhead`, `Viability`, `CostProg` and `WI` keep their Phase 4 equations.

`NewDurW` and `NewPriceW` are coflows: each tracks an attribute (term length, price) carried by the contract volume in `NewVol`. A contract leaving at expiry takes the average attribute with it, so the averages change only through what is signed and, for price, through glide paths.

The pressure gap is in group E. Under fixed price the vendor is paid at `Anchor`, set by the productivity clients perceive (`ClientP`). Under time and materials it is paid `1 / P_eff`, set by the productivity it actually achieves. When `P_eff` runs ahead of `ClientP`, fixed price earns more per unit of work, and vendors push for it.

## Parameters

Phase 1-4 parameters keep their values, except the two recalibrated ones below and those removed with the vendor share effect and the single price index. The new values are illustrative first guesses, chosen so the behaviour is plausible; contract mix and durations should be checked against vendor disclosures in Phase 7. Calibrated rows are steady-state outcomes: recompute them with the prototype (`calibrate5.py`) if any other parameter changes.

**Recalibrated**

| Parameter | Phase 5 value | Meaning |
| --- | --- | --- |
| `Price[VI]` | 39,880 USD/BFY (was 37,070) | Vendor India price, raised to cover the sales cost |
| `NormalMargin` | 0.18 (was 0.1776) | Steady-state margin |

**Contract arrays `[ContractType]`**

| Parameter | FP · TM · MS · SA · OB | Unit | Meaning |
| --- | --- | --- | --- |
| `Mix0` | 0.35 · 0.30 · 0.22 · 0.10 · 0.03 | fraction | 2024 contract mix by volume, used for the `Leg` initial values |
| `BaseDur` | 2.5 · 1.5 · 6 · 1 · 3 | yr | Contract length without AI pressure; also the legacy length |
| `TypeASC` | -1.2459 · -0.8893 · -2.5857 · -1.5824 · -3.885 (calibrated) | dimensionless | Constants that make the type logit reproduce the 2024 signing shares |

**Contract scalars**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `MinDur` | 0.25 | yr | Floor on new-contract length (stops R8 driving terms to zero) |
| `DurPUSens` | 15 | yr | How strongly expected AI price declines shorten new contracts |
| `DurPowerElast` | 1 | dimensionless | How strongly vendor bargaining power lengthens them |
| `TrendTime` | 2 | yr | Window for the trend in client-perceived productivity |
| `MSGlideShare` | 0.5 | fraction | Share of in-term productivity gains passed on by managed-service glide paths |
| `OBGainShare` | 0.5 | fraction | Share of in-term gains passed on by outcome-based pricing |
| `ConsSens` | 10 | dimensionless | Consumer utility per unit of expected overpayment |
| `EffortDistrust` | 0.5 | fraction | Share of perceived AI gains consumers expect to lose under effort billing |
| `SATTFSens` | 0.5 | dimensionless | Extra appeal of staff augmentation when onshore hiring is slow |
| `VendSens` | 2 | dimensionless | Vendor utility per unit of relative profit change |
| `BargainW0` | 0.5 | fraction | Vendor weight in the type choice at normal bargaining power |
| `PowerSens` | 3 | dimensionless | Change in vendor bargaining power per point of margin deviation |
| `PowerMin`, `PowerMax` | 0.5, 1.2 | dimensionless | Limits on bargaining power |
| `SalesCostRate` | 0.05 | fraction | Sales cost as a share of the annual value of contracts signed |

**Sourcing**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `InHouseShare0`, `GCCShare0` | 0.30, 0.10 | share of work | Initial values of `IHWork` and `GCCWork` |
| `IHReviewTime` | 4 | yr | How often in-house work is reconsidered |
| `GCCReviewTime` | 5 | yr | How often GCC work is reconsidered |
| `Contest` | 0.5 | fraction | Share of expiring or reviewed work actually put out to choice; the rest stays with the incumbent |
| `SrcPerceptionTime` | 1.5 | yr | Delay before sourcing preferences catch up with value |
| `SrcCostSens` | 3 | dimensionless | Value lost per unit of cost relative to `CostRef` |
| `CostRef` | 131,000 (calibrated) | USD/BFY | 2024 in-house cost per unit of work; fixed, so AI shrinks absolute cost gaps |
| `GCCOverhead` | 0.5 | fraction | GCC management, facilities and setup cost on top of wages |
| `SrcASC[Option]` | IH 0.1293 · GCC -3.258 · VEND 0 (calibrated) | dimensionless | Non-cost value of each option (proximity, control, setup barriers) at 2024 |
| `ViabSens` | 5 | dimensionless | Value lost per point of weak vendor viability beyond the dead band |
| `ExitPenalty` | 7.5 | dimensionless | Extra value lost per point of viability below `ExitThreshold` |
| `VisaRiskSens` | 1 | dimensionless | Value lost as visa tightness rises above its 2024 level |
| `CapSens` | 0.5 | dimensionless | Value lost when an option's labour pool is slow to hire |
| `GCCAppealEnd` | 0 | dimensionless | Extra GCC value after the ramp (scenario lever; replaces `GCCShareEnd`) |
| `GCCRampStart`, `GCCRampEnd` | 2027, 2031 | year | When the GCC appeal ramps up (kept from Phase 3) |

**Competition**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `ShareRefTime` | 4 | yr | How slowly the vendor's idea of its normal share adapts |
| `ShareLossSens` | 0.5 | dimensionless | Discount offered per unit of relative share loss |
| `RivalSens` | 3 | dimensionless | Discount per point of excess viability, as rivals bid margins away |
| `MaxDisc` | 0.4 | fraction | Ceiling on the competitive discount |
| `DiscAdjTime` | 1 | yr | How fast discounts follow their target |

**Removed:** `InHouseShare`, `GCCShareEnd`, `RepricingTime`, `ShareSens`, `VSEMin`, `VSEMax`, `ShareAdjTime`. `ExitThreshold` (0) is kept and now acts in the sourcing choice.

## Tests and reference results

Run the eight tests in order; results should land within about 1% of these prototype values. `PeopleCheck` must stay at 92,546 and `WorkCheck` at 1 in every run. Phase 5 is done when T3 shows the contract mix responding to the pressure gap.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | 84,135 employed; vendor 49,786 (49,746 in 2040); work shares 60% vendor, 30% in-house, 10% GCC; in-force mix FP 35.0%, TM 30.0%, MS 22.0%, SA 10.0%, OB 3.0%; signing shares FP 28.8%, TM 41.1%, MS 7.5%, SA 20.6%, OB 2.1%; average new term 2.05 years; revenue $3.91 billion; margin between 17.6% and 18.0% |
| T2 AI base case | None (`AIOn = true`) | Mix shifts from effort billing; work moves in-house | 2040 mix FP 44.0%, TM 16.2%, MS 28.3%, SA 7.8%, OB 3.8% (effort-billed work falls from 40% to 24%); yearly mix changes stay under 2 points and under 0.5 points after 2036; average new term falls from 2.08 to 1.72 years in 2032, back to 2.07 by 2040; work shares in 2040 vendor 51.2%, in-house 40.4%, GCC 8.4%; vendor 24,572 (-47% from 2027), in-house 19,170, GCC 4,196, total 47,938; margin peaks at 28.9% in 2029 and is 21.9% in 2040; discount peaks at 0.21 in 2032; consumer spend falls from $8.45 billion to $5.13 billion |
| T3 Pressure gap | AI on; run a: `ClientPerceptionTime = 3`; run b: `ClientPerceptionTime = 0.5` | Mix responds to the gap | `P_eff / ClientP` in 2030: 1.116 (a), 1.071 (T2), 1.026 (b). FP share of 2030 signings: 42.7% (a), 40.3% (T2), 37.8% (b); TM: 29.4%, 31.3%, 33.3%. Peak margin 29.9% (a) vs 28.0% (b); average new term in 2030 2.07 vs 1.70 years |
| T4 No price competition | AI on, `RivalSens = 0`, `ShareLossSens = 0` | B12 switched off | Margin peaks at 34.3% in 2032 and is 29.3% in 2040 (21.9% in T2); vendor work share 49.6% (more work lost at higher prices); consumer spend $5.42 billion in 2040 |
| T5 GCC push | `AIOn = false`, `GCCAppealEnd = 1` (ramp 2027-2031) | Work moves to captives at the pace of renewals | GCC share rises from 10% to 17.9% by 2040; GCC headcount 8,664 to 14,964; vendor 44,345 (-11%); vendor margin 16.8% |
| T6 Price war | `AIOn = false`, `PriceShock = 0.40` | R6 and R8 together | Margin -35.4% in 2028, viability negative for about 11 years; vendor share falls to 35.7%; vendor 28,913 by 2040 (-42%); in-house 36,170, GCC 17,343; new terms halve to 1.0 year as bargaining power hits its floor; consumer spend rises from $8.42 billion to a peak of $8.74 billion in 2035 |
| T7 Time step check | Time step 1/32 yr only | Results barely change | Within 0.4% of T2 (vendor 24,557 in 2040; margin within 0.25 points) |
| T8 Extreme | `PriceShock = 0.6`, `VTEnd = 1`, `GCCAppealEnd = 3`, `AIShockMult = 5`, `ClientPerceptionTime = 0.0625`, Phase 2 extreme AI settings | Nothing breaks | No stock goes negative; `PeopleCheck` and `WorkCheck` hold; terms stay above the 0.25-year floor |

&#91;embedded content: prototype simulation of these exact equations (phase5\_sim.py), Euler, time step 1/16 yr\]

**Reading the results**

- **The contract mix moves from effort billing to fixed price and managed services, then settles.** Two forces drive it. Consumers increasingly expect effort-billed vendors to keep AI's savings for themselves. Vendors earn more per unit of work under fixed price while their real productivity runs ahead of what clients perceive. By the mid-2030s the mix stops moving, so on the spec's Q2 test the mix balances. Who does the work has not settled: the vendor's share is still falling by about half a point a year in 2040.
- **The pressure gap shifts the mix, but less than you might expect.** A wider gap makes vendors push fixed price harder, but clients who perceive less AI also distrust effort billing less, so the two effects partly cancel.
- **Outcome-based deals stay niche at about 4%.** In this model they are a compromise that neither side ranks first: consumers prefer them to fixed price, vendors prefer fixed price. If real deal data show outcome-based pricing growing, the model is missing a mechanism, such as better outcome measurement.
- **Contract terms shorten only while AI is improving fast.** Vendors' strong margins in the early 2030s give them the bargaining power to resist shorter terms. In the price war (T6), power collapses and terms halve: that is loop R8.
- **Competition removes most of the AI windfall, but not all of it.** Without B12 the 2040 margin is 29%; with it, 22%. The rest comes from wages: high unemployment holds vendor wages at their floor.
- **The tipping point moves earlier.** A price-cut scan (`scan5.py`) puts it between 30% and 35%, against 35-40% in Phase 4. Small cuts now hurt less: a 10% cut costs 1.9% of vendor headcount, against 4.1% in Phase 4, because a cheaper vendor wins some work back. Large cuts hurt more, because the whole book reprices at once and clients avoid a loss-making supplier.
