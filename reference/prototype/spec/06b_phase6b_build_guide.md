# Phase 6b build guide

Phase 6b completes the full-dimension model by building the supply side. The single vendor of Phases 4-5 becomes three archetypes: offshore Indian IT (`OIT`), global SIs (`GSI`) and boutiques (`BQ`), each with its own staff, contracts and finances. AI delivery adoption is tracked per employer, and vendors with effort-billed books adopt more slowly (loop B2). Each of the seven sectors chooses between five sourcing options at every renewal. Phase 6b is done when the Q1 headcount lines, the Q2 contract mix by archetype and the Q3 outcome test are all reported, adoption responds to the contract mix, and sourcing differs by sector; every value below was verified in a prototype that conserves people and work exactly.

## Structure

Each sector's work is held by five employers: two consumer-owned (in-house teams and GCCs) and three vendor archetypes. Work comes up for decision as contracts expire and in-house work is reviewed, and each sector re-chooses using its own preferences.

&#91;embedded content: Phase 6b structure · five employers, three vendors, sourcing by sector\]

Each vendor has its own contract book, prices, costs and viability. Its viability feeds back into how risky clients find it (R6), its losses of share trigger price cuts (B12), and the effort-billed part of its book slows its own AI adoption (B2).

## What changes from Phase 6a

The demand side and the labour market mechanics stay. The supply side is rebuilt around employers and vendors, so most Phase 4-5 variables gain a `[Vendor]` or `[Employer]` index.

- **Extend `Unit`** to eight elements: `IH`, `GCC`, `VI`, `OV`, `OL`, `SI_IN` (global SI delivery centre in India), `SI_ON` (global SI onshore) and `BQ` (boutique, onshore).
- **Add dimensions** `Employer` {`IH`, `GCC`, `OIT`, `GSI`, `BQ`} and its subdimension `Vendor` {`OIT`, `GSI`, `BQ`}. Each unit belongs to one employer: `VI`, `OV` and `OL` to `OIT`; `SI_IN` and `SI_ON` to `GSI`.
- **Index by employer:** delivery adoption `A`, `PerceivedP`, `ClientP`, `ClientPRef`, the level mix and productivity. Each employer completes its own share of every sector's backlog with its own capacity.
- **Index by vendor:** the contract stocks, revenue, costs, margin, `Viability`, `Overhead`, `CostProg`, `Disc`, `ShareRef`, bargaining power and the type choice.
- **Replace Phase 5's sourcing stocks** with `IHW[Sector]`, `GCCW[Sector]`, `VW[Sector, Vendor]` and `SrcPerc[Sector, Employer]`: each sector now chooses between five options.
- **Generalise job switching** to every pair of units in the same labour pool (visa holders still excluded).
- **Recalibrate the labour market:** the new units move jobs onshore, so enrolment and the regional normals were re-solved. Every labour initial value changes (Stocks section).

Eight design decisions:

- **Contracts are tracked by type and vendor, not by sector.** In Phase 6b the type choice does not depend on the sector, so a sector index on contracts would only repeat the same mix seven times. The contract stocks hold each vendor's book composition (type, vintage, term, price); `VW[Sector, Vendor]` holds how much of each sector's work each vendor has. Contracts by sector stay possible if Phase 7 data show sector-specific mixes.
- **One backlog, five shares.** Each employer works its share of every backlog cell at its own clearing rate, so a more productive employer clears its share faster. This replaces a separate work queue per employer while keeping one representation of work.
- **The T&M brake (B2).** A vendor's adoption speed falls in proportion to the effort-billed share of its book (`TMBrake`). Vendors losing share speed up (`PushSens`). In-house teams start 20% slower (`AdoptMult`), boutiques 20% faster before the brake.
- **Global SIs deliver half from India and half onshore** without visas; only Indian IT carries the visa workforce and visa risk.
- **Sector differences enter through constants and regulation.** Each sector's 2024 sourcing mix sets its constants (financial services use GCCs most; government and legal use global SIs and boutiques). Regulated sectors penalise offshore options in proportion to AI use and regulatory drag (`RegFitSens`).
- **GCC capacity is a value term, not a stock.** The spec's `GCCCapacity` is replaced by the GCC appeal lever plus a term that grows with the sector's consumer AI adoption (AI lowers the minimum viable GCC size). A capacity stock can return if GCC setup delays turn out to matter.
- **Target margins differ by archetype:** 18% for Indian IT, 15% for global SIs, 12% for boutiques. Each vendor's prices were scaled to reach them.
- **The Q3 test is computed.** Each vendor is classed as collapse, new equilibrium or still adjusting over 2038-2040 using the spec's thresholds.

## AnyLogic setup

This is the biggest restructuring so far. Work in this order, and check the AI-off steady state at every step: with all values from the Stocks section, nothing should move.

1. **Save a copy** of your working Phase 6a model as Phase 6b.
2. **Extend the dimensions.** Add `SI_IN`, `SI_ON` and `BQ` to `Unit`; add `Employer` and its subdimension `Vendor`; add a parameter array `EmpOf[Unit]` (or a lookup) giving each unit's employer. Add `SI_IN` to the `IndiaPoolUnits` subdimension and `SI_ON`, `BQ` to `OnshorePoolUnits`.
3. **Load the new labour initial values** and the recalibrated `BaseEnrolment`, `NormalUnempRate` and `NormalTTF`. With sourcing frozen (step 5 not yet built), the labour market alone should sit still at 84,255 employed.
4. **Re-index production by employer** (group A of the formulas): adoption, productivity, completion, desired headcount. Then re-index the finance and contract variables by vendor (groups B and C). At this point keep the work shares fixed at their initial values.
5. **Build sourcing by sector** (group D) and switch the shares on. With AI off the sourcing targets must equal the initial `SrcPerc` values.
6. **Generalise job switching** (group E) and run the tests.

No three-way array is needed. Group A works through a two-way variable `BLew[Employer, WorkType]` (each employer's share of the backlog, by work type), and the sector-level completion uses each employer's clearing rate. Build the four Q1 lines (group F) as dynamic variables so they can be plotted directly.

## Stocks and initial values

The starting point is a new AI-off steady state with eight units: 84,255 employed, unemployment 5.0% in India and 5.5% onshore, and `PeopleCheck` at 92,687.

**Labour stocks `[Unit, Level]`** (each cell: JUNIOR / MID / SENIOR)

| Unit | `H` employed | `O` onboarding | `V` vacancies |
| --- | --- | --- | --- |
| `IH` | 4,529 / 5,698 / 15,652 | 633 / 169 / 411 | 381 / 1,426 / 274 |
| `GCC` | 1,510 / 2,040 / 5,103 | 177 / 33 / 39 | 92 / 269 / 102 |
| `VI` | 3,537 / 4,389 / 11,542 | 506 / 139 / 318 | 262 / 1,136 / 829 |
| `OV` | 673 / 720 / 2,021 | 124 / 45 / 143 | 64 / 368 / 373 |
| `OL` | 487 / 657 / 1,677 | 57 / 11 / 7 | 34 / 92 / 19 |
| `SI_IN` | 1,618 / 2,138 / 5,470 | 205 / 44 / 60 | 106 / 358 / 158 |
| `SI_ON` | 1,610 / 2,152 / 5,567 | 200 / 41 / 55 | 120 / 346 / 66 |
| `BQ` | 942 / 1,269 / 3,254 | 113 / 22 / 21 | 68 / 188 / 38 |

**Labour pools `[Region, Level]`:** `ActiveSeekers` INDIA 1,956 / 65 / 215, ONSHORE 1,667 / 61 / 895; `RecoveringIT` 0 everywhere. `EntrantPipeline` INDIA 12,129, ONSHORE 12,175. `PercUnempShort` and `PercUnempLong` INDIA 0.0499, ONSHORE 0.0548. `WI` 1 for every unit.

**Backlog:** `BL[Sector, WorkType]` starts at `54517 * SectorShare[Sector] * WTMix[WorkType]` (e.g. `BL[FIN, APP]` 4,088).

**Employer stocks `[Employer]`:** `A` 0.05; `PerceivedP`, `ClientP`, `ClientPRef` 1.

**Vendor stocks `[Vendor]`**

| Stock | OIT · GSI · BQ |
| --- | --- |
| `Overhead` (USD/yr) | 163,566,000 · 243,696,000 · 127,706,000 |
| `Viability` | 0.18 · 0.15 · 0.12 |
| `ShareRef` (share of all work) | 0.3174 · 0.2143 · 0.0624 |
| `CostProg`, `Disc` | 0 |
| `Leg[Vendor, ContractType]` | each vendor's `Mix0` row (the book is an index that starts at 1) |
| `NewVol`, `NewDurW`, `NewPriceW` | 0 |

**Sourcing stocks `[Sector]`:** `IHW`, `GCCW` and `VW[Sector, Vendor]` start at the 2024 sourcing mix `Src0` in the Parameters section, so each sector's five shares add up to 1. `SrcPerc[Sector, Employer]` starts at the decision shares below; they differ from the work shares because vendor contracts come up for renewal far more often than in-house work is reviewed.

| `SrcPerc` | IH · GCC · OIT · GSI · BQ |
| --- | --- |
| `FIN` | 0.1467 · 0.0960 · 0.4544 · 0.2216 · 0.0812 |
| `LEG` | 0.2562 · 0.0102 · 0.1870 · 0.2660 · 0.2805 |
| `MED` | 0.2283 · 0.0313 · 0.3809 · 0.2167 · 0.1428 |
| `GOV` | 0.3113 · 0.0055 · 0.1347 · 0.4138 · 0.1347 |
| `MFG` | 0.1618 · 0.0621 · 0.5039 · 0.1935 · 0.0787 |
| `LOG` | 0.1940 · 0.0414 · 0.5034 · 0.1826 · 0.0787 |
| `RET` | 0.1964 · 0.0524 · 0.5352 · 0.1523 · 0.0637 |

**Demand-side stocks** keep their Phase 6a values, except `SeatsB`, which starts at the new `Seats0`.

**Removed:** the Phase 5 scalars `IHWork`, `GCCWork`, `SrcPerc[Option]`, and the scalar versions of every stock now indexed by employer or vendor.

## Formulas

`s` is the sector, `w` the work type, `e` the employer, `v` the vendor, `u` the unit and `k` the contract type. "Units of `e`" means the units whose `EmpOf` is `e`. Phase 6a demand formulas are unchanged except where listed; Phase 5 contract and type-choice formulas keep their form, gaining a `[Vendor]` index and using `P[v]` and `ClientP[v]` where they used `P_eff` and `ClientP`.

**A. Production by employer**

| Name | Formula |
| --- | --- |
| `EmpShare[Sector, Employer]` | `IH`: `IHW[s]` · `GCC`: `GCCW[s]` · `Vendor`: `VW[s, v]` |
| `Pw[Employer, WorkType]` | `AIOn ? A[e] * PAI[w] + (1 - A[e]) : 1` |
| `BLew[Employer, WorkType]` | sum over sectors of `EmpShare[s, e] * BL[s, w]` |
| `BLe[Employer]` | sum over work types of `BLew[e, w]` |
| `EffortE[Employer]` | sum over work types of `BLew[e, w] / Pw[e, w]` |
| `P[Employer]` | `BLe[e] / EffortE[e]` |
| `EffStaffE[Employer]` | sum over units of `e` and levels of `W[l] * (H[u, l] + OnboardProductivity * O[u, l])` |
| `CompE[Employer]` | `min(WorkPerPerson * P[e] * EffStaffE[e], BLe[e] / MinCompletionTime)` |
| `RateE[Employer]` | `CompE[e] / BLe[e]` |
| `Comp[Sector, WorkType]` | `BL[s, w] * (sum over employers of EmpShare[s, e] * RateE[e])` |
| `Aband[Sector, WorkType]` | sum over employers of `EmpShare[s, e] * max(0, BL[s, w] * (1 - RateE[e] * AbandonTolerance)) / AbandonTime` |
| `Completion` | sum of `CompE` |
| `P_all` | `Completion / (sum over employers of CompE[e] / P[e])` (replaces `P_eff` in `CloudPB`) |
| `Share[Employer, Level]` | Phase 2 level mix, using `A[e]` |
| `UnitIn[Unit]` | `IH`, `GCC`, `BQ`: 1 · `VI`: `1 - OnsiteShare` · `OV`: `OnsiteShare * VisaMix` · `OL`: `OnsiteShare * (1 - VisaMix)` · `SI_IN`: `GSIOffshore` · `SI_ON`: `1 - GSIOffshore` |
| `DesiredE[Employer]` | `BLe[e] / (TargetClearanceTime * WorkPerPerson * PerceivedP[e])` |
| `Desired[Unit, Level]` | `DesiredE[e] * UnitIn[u] * Share[e, l] / (sum over levels of Share[e, l] * W[l])`, with `e = EmpOf[u]` |
| `Delivered[Unit]` | `CompE[e] * Capu[u] / EffStaffE[e]`, with `e = EmpOf[u]` |

**B. Vendor finance**

| Name | Formula |
| --- | --- |
| `BaseRev[Vendor]` | sum over units of `v` of `Delivered[u] * Price[u] * PriceMult[v]` |
| `BasePriceAvg[Vendor]` | `PriceMult[v] * (sum of UnitIn[u] * Price[u]) / (sum of UnitIn[u])` over units of `v` |
| `ShockNow[Vendor]` | `Year >= PriceShockYear ? PriceShock[v] : 0` |
| `Revenue[Vendor]` | `BaseRev[v] * AvgIdx[v] * (1 - ShockNow[v])` |
| `Book[Vendor]` | sum over types of `Leg[v, k] + NewVol[v, k]` |
| `ExpRate[Vendor]` | sum over types of `ExpLeg[v, k] + ExpNew[v, k]`, divided by `Book[v]` |
| `AvgIdx[Vendor]` | sum over types of `IdxVol[v, k]`, divided by `Book[v]` (effort types divide by `P[v]`) |
| `VendDel[Vendor]` | sum over units of `v` of `Delivered[u]` |
| `AICost[Vendor]` | `AICostPerUnit * VendDel[v] * (1 - 1 / P[v])` |
| `VisaCost[Vendor]` | `OIT`: Phase 4 formula · `GSI`, `BQ`: 0 |
| `VendorLabour[Vendor]` | sum over units of `v` of `LabourCost[u]`, times `(1 - CostProg[v])` |
| `SignRate[Vendor]` | `(sum over sectors of Sign[s, v] * CompS[s]) / (sum over sectors of VW[s, v] * CompS[s])` |
| `SalesCost[Vendor]` | `SalesCostRate * Revenue[v] * SignRate[v]` |
| `VendorCost[Vendor]` | `VendorLabour[v] + VisaCost[v] + AICost[v] + Overhead[v] + SalesCost[v]` |
| `Margin[Vendor]` | `(Revenue[v] - VendorCost[v]) / Revenue[v]` |
| `CostIdx[Vendor]` | `VendorCost[v] / BaseRev[v]` |
| `Signings[Vendor, ContractType]` | `Book[v] * SignRate[v] * TypeShare[v, k]` |
| `VShare[Vendor]` | sum over sectors of `VW[s, v] * CS[s]` (share of all completed work) |
| `ShareLoss`, `Afford`, `DiscTarget`, `CostProgTarget`, `Power`, `Dev`, `DevEff` | Phase 5 formulas per vendor, with `NormalMargin[v]` |
| `Restraint[Unit]` | units of a vendor: `1 - WageRestraint * max(0, -DevEff[EmpOf[u]])` · `IH`, `GCC`: 1 |
| `ServicesSpend` | `LabourCost[IH] + LabourCost[GCC] * (1 + GCCOverhead) + (sum of Revenue[v]) + AICostPerUnit * ((1 - 1 / P[IH]) * Delivered[IH] + (1 - 1 / P[GCC]) * Delivered[GCC])` |

**C. Delivery AI adoption per employer**

| Name | Formula |
| --- | --- |
| `LabPB[Employer]` | sum over units of `e` of `LabourCost[u]`, divided by `EffStaffE[e]` |
| `CE[Employer]` | `min(CEMax, max(CEMin, pow((LabPB[e] / LabourCostPB0[e]) * (AICost2024 / AICostPerUnit), CostAdoptElast)))` |
| `EffortShare[Vendor]` | `(Leg + NewVol summed over TM and SA) / Book[v]` |
| `Brake[Employer]` | vendors: `1 - TMBrake * EffortShare[v]` · `IH`, `GCC`: 1 |
| `Push[Employer]` | vendors: `1 + PushSens * ShareLoss[v]` · `IH`, `GCC`: 1 |
| `Adoption[Employer]` | `AIOn ? min((p * AdoptMult[e] + q * A[e]) * CE[e] * Brake[e] * Push[e] * (1 - A[e]), (1 - A[e]) / MinAdoptionTime) : 0` |

**D. Sourcing by sector**

| Name | Formula |
| --- | --- |
| `IHTurn[Sector]`, `GCCTurn[Sector]` | `IHW[s] / IHReviewTime`, `GCCW[s] / GCCReviewTime` |
| `VExp[Sector, Vendor]` | `VW[s, v] * ExpRate[v]` |
| `Contested[Sector]` | `Contest * (IHTurn[s] + GCCTurn[s] + sum over vendors of VExp[s, v])` |
| `Sign[Sector, Vendor]` | `(1 - Contest) * VExp[s, v] + Contested[s] * SrcPerc[s, v]` |
| `SrcCost[Employer]` | `IH`: `BaseWage[IH] * WI[IH] * AvgWageMult[IH] / (AvgWork[IH] * ClientP[IH]) + AICostPerUnit * (1 - 1 / ClientP[IH])` · `GCC`: the same with GCC values times `(1 + GCCOverhead)` on the wage term · vendors: `BasePriceAvg[v] * Anchor[v] * (1 - Disc[v]) * (1 - ShockNow[v])` |
| `VendRisk[Vendor]` | `ViabSens * min(0, DevEff[v]) - ExitPenalty * max(0, ExitThreshold - Viability[v])`, and for `OIT` also `- VisaRiskSens * max(0, TightPerc - VTBase)` |
| `RegFit[Sector, Employer]` | `AIOn ? RegFitSens * RegDrag[s] * AC[s] * OffExp[e] : 0` |
| `GCCTerm[Sector]` | `GCCAppeal + (AIOn ? GCCAISens * (AC[s] - AC0) : 0)` |
| `SrcValue[Sector, Employer]` | `SrcASC[s, e] - SrcCostSens * SrcCost[e] / CostRef - CapSens * max(0, TTFRatio[pool of e] - 1) - RegFit[s, e]`, plus `GCCTerm[s]` for `GCC` and `VendRisk[v]` for vendors; the pool is `ONSHORE` for `IH` and `BQ`, `INDIA` for the others |
| `SrcTarget[Sector, Employer]` | `exp(SrcValue[s, e])` divided by the sum of `exp(SrcValue[s, ·])` over the five employers |

**E. Job switching (replaces the Phase 3 pairs)**

| Name | Formula |
| --- | --- |
| `RawSwitch[i → j, Level]` | for units `i` and `j` in the same labour pool, `OV` excluded: `H[i, l] * SwitchRate * min(SwitchMax, pow((Wage[j] * WI[j]) / (Wage[i] * WI[i]), SwitchElasticity)) * V[j, l] / (sum of V[k, l] over the other units k of the pool)` |
| `SwitchScale[Unit, Level]` | `min(1, Room[j, l] / (sum over i of RawSwitch[i → j, l]))`, where `Room` is Phase 3's vacancy room after promotions |
| `Switch[i → j, Level]` | `RawSwitch[i → j, l] * SwitchScale[j, l]`; `SwitchIn[j]` and `SwitchOut[i]` are its sums |

In AnyLogic, a two-unit pair loop becomes an array over `[Unit, Unit, Level]`; with eight units that is 192 elements, most of them zero because the units sit in different pools.

**F. Q1 to Q3 outputs**

| Name | Formula |
| --- | --- |
| `Q1ConsumerOnshore` | total `H` of `IH` |
| `Q1ConsumerIndia` | total `H` of `GCC` |
| `Q1VendorOnshore` | total `H` of `OV`, `OL`, `SI_ON` and `BQ` |
| `Q1VendorIndia` | total `H` of `VI` and `SI_IN` |
| `Q2Mix[Vendor, ContractType]` | `(Leg[v, k] + NewVol[v, k]) / Book[v]` |
| `Q3Outcome[Vendor]` (computed after the run) | collapse if `Viability[v]` stayed below 0 for 3 or more consecutive years and the vendor's headcount fell more than 15% in 2039 or 2040; new equilibrium if the vendor's headcount and revenue, in-house and GCC headcount and total demand each changed less than 2% in both 2039 and 2040; otherwise still adjusting |

**G. Stock equations**

| Stock | Derivative |
| --- | --- |
| `IHW[Sector]` | `Contested[s] * SrcPerc[s, IH] - Contest * IHTurn[s]` |
| `GCCW[Sector]` | `Contested[s] * SrcPerc[s, GCC] - Contest * GCCTurn[s]` |
| `VW[Sector, Vendor]` | `Sign[s, v] - VExp[s, v]` |
| `SrcPerc[Sector, Employer]` | `(SrcTarget[s, e] - SrcPerc[s, e]) / SrcPerceptionTime` |
| `A[Employer]` | `Adoption[e]` |
| `PerceivedP[Employer]`, `ClientP[Employer]` | `(P[e] - PerceivedP[e]) / PerceptionTime`, `(P[e] - ClientP[e]) / ClientPerceptionTime` |
| `ClientPRef[Employer]` | `(ClientP[e] - ClientPRef[e]) / TrendTime` |
| Vendor stocks | Phase 4-5 equations per vendor; `Overhead[v]` targets `OverheadRate[v] * Revenue[v]` |
| Contract stocks `[Vendor, ContractType]` | Phase 5 equations per vendor, with `Signings[v, k]` from group B |

## Parameters

Parameters not listed keep their Phase 6a values. Vendor-specific values are illustrative first guesses; rows marked calibrated come from `calibrate6b.py` and must be recomputed if other parameters change.

**New unit elements `[Unit]`** (existing units unchanged)

| Parameter | SI\_IN · SI\_ON · BQ | Meaning |
| --- | --- | --- |
| `Wage` | 1.1 · 1.05 · 1.1 | Relative wage within the region (drives switching) |
| `BaseWage` | 22,000 · 130,000 · 140,000 USD/yr | Mid-level pay at wage index 1 |
| `Price` | 45,000 · 170,000 · 190,000 USD/BFY | Price per unit of work before `PriceMult` and the contract price index |

**Vendor arrays `[Vendor]`**

| Parameter | OIT · GSI · BQ | Meaning |
| --- | --- | --- |
| `PriceMult` | 1.0035 · 1.0303 · 1.0420 (calibrated) | Scales each vendor's unit prices to reach its target margin |
| `TargetMargin` | 0.18 · 0.15 · 0.12 | Calibration target |
| `NormalMargin` | 0.18 · 0.15 · 0.12 (calibrated) | Steady-state margin; replaces the scalar |
| `OverheadRate` | 0.08 · 0.10 · 0.10 | Overhead as a share of revenue |
| `PriceShock` | 0 · 0 · 0 | One-off revenue cut per vendor (test lever; replaces the scalar) |

**Contract arrays `[Vendor, ContractType]`** (FP · TM · MS · SA · OB)

| Vendor | `Mix0` | `TypeASC` (calibrated) |
| --- | --- | --- |
| `OIT` | 0.35 · 0.30 · 0.22 · 0.10 · 0.03 | -1.2459 · -0.8893 · -2.5857 · -1.5824 · -3.8850 |
| `GSI` | 0.38 · 0.22 · 0.30 · 0.05 · 0.05 | -1.0052 · -1.0409 · -2.1171 · -2.1171 · -3.2157 |
| `BQ` | 0.30 · 0.45 · 0.05 · 0.17 · 0.03 | -1.6232 · -0.7069 · -4.2905 · -1.2749 · -4.1081 |

**Employer arrays `[Employer]`** (IH · GCC · OIT · GSI · BQ)

| Parameter | Values | Meaning |
| --- | --- | --- |
| `AdoptMult` | 0.8 · 1.0 · 1.0 · 1.1 · 1.2 | Multiplier on the Bass innovation rate `p` |
| `OffExp` | 0 · 0.3 · 0.8 · 0.5 · 0 | Offshore exposure, for regulatory fit |
| `LabourCostPB0` | 133,770 · 27,560 · 43,250 · 81,060 · 148,400 USD/BFY (calibrated) | 2024 labour cost per unit of capacity; replaces the scalar |

**Sourcing arrays `[Sector, Employer]`** (IH · GCC · OIT · GSI · BQ)

| Sector | `Src0` (2024 work shares) | `SrcASC` (calibrated) |
| --- | --- | --- |
| `FIN` | 0.22 · 0.18 · 0.35 · 0.20 · 0.05 | 0.3227 · -2.1667 · 0 · 0.2692 · 1.2620 |
| `LEG` | 0.40 · 0.02 · 0.15 · 0.25 · 0.18 | 1.7678 · -3.5166 · 0 · 1.3396 · 3.3902 |
| `MED` | 0.35 · 0.06 · 0.30 · 0.20 · 0.09 | 0.9411 · -3.1111 · 0 · 0.4233 · 2.0039 |
| `GOV` | 0.45 · 0.01 · 0.10 · 0.36 · 0.08 | 2.2910 · -3.8043 · 0 · 2.1097 · 2.9847 |
| `MFG` | 0.25 · 0.12 · 0.40 · 0.18 · 0.05 | 0.3170 · -2.7057 · 0 · 0.0303 · 1.1285 |
| `LOG` | 0.30 · 0.08 · 0.40 · 0.17 · 0.05 | 0.4993 · -3.1111 · 0 · -0.0269 · 1.1285 |
| `RET` | 0.30 · 0.10 · 0.42 · 0.14 · 0.04 | 0.4505 · -2.9368 · 0 · -0.2698 · 0.8565 |

**Scalars**

| Parameter | Value | Meaning |
| --- | --- | --- |
| `GSIOffshore` | 0.5 | Share of global SI work delivered from India |
| `TMBrake` | 0.4 | Cut in a vendor's adoption speed per unit of effort-billed book (B2) |
| `PushSens` | 2 | Extra adoption speed per unit of relative share loss |
| `RegFitSens` | 1 | Value lost by offshore options per unit of drag × adoption × exposure |
| `GCCAISens` | 0.5 | Extra GCC value per unit of sector AI adoption above 2024 |

**Recalibrated:** `BaseEnrolment` INDIA 3,030, ONSHORE 3,040; `NormalUnempRate` INDIA 0.0499, ONSHORE 0.0548; `NormalTTF` INDIA: MID 0.551, SENIOR 0.289; ONSHORE: MID 0.526, SENIOR 0.079; `CostRef` 131,000; `CostPerBFY0` 103,120; `Seats0` FIN 197,933, LEG 61,636, MED 246,444, GOV 293,916, MFG 468,370, LOG 220,362, RET 563,670; `Budget0` (USD million) FIN 3,369.8, LEG 464.5, MED 1,857.8, GOV 2,666.5, MFG 2,821.0, LOG 1,327.5, RET 2,972.2.

**Removed:** the Phase 5 `SrcASC[Option]`, `InHouseShare0`, `GCCShare0`, the scalars `PriceShock`, `NormalMargin`, `OverheadRate`, `LabourCostPB0` and `Mix0`, and Phase 5's `TypeASC[ContractType]`.

## Tests and reference results

Run the ten runs in order; totals should land within about 1% of these prototype values. `PeopleCheck` must stay at 92,687 and every sector's `WorkCheck` at 1.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | 84,255 employed: IH 25,878, GCC 8,653, OIT 25,703, GSI 18,555, BQ 5,466 (all within 0.1% in 2040). Work shares 30.7%, 9.8%, 31.7%, 21.4%, 6.2%. Margins 18%, 15%, 12%. Unemployment 5.0% India, 5.5% onshore. Q3: equilibrium for all three vendors |
| T2 AI base case | None (`AIOn = true`) | Q1-Q3 by archetype | 45,042 employed in 2040. Q1 lines, 2024 to 2040: consumer onshore 25,878 to 15,631 (-40%), consumer India (GCC) 8,653 to 4,348 (-50%), vendor onshore 21,030 to 12,640 (-40%), vendor India 28,694 to 12,423 (-57%). By vendor: Indian IT 25,703 to 9,841 (-62%), revenue $2.06 billion to $0.78 billion; global SIs 18,555 to 10,013 (-46%), $2.46 billion to $1.31 billion; boutiques 5,466 to 5,209 (-5%), $1.28 billion to $1.20 billion. 2040 work shares: in-house 35.5%, GCC 9.3%, OIT 21.9%, GSI 21.7%, BQ 11.6%. Peak margins 30.3%, 28.2%, 22.3%; 22.2%, 20.0%, 16.7% in 2040. Effort-billed share of each book falls from 40% to 22.5% (OIT), 27% to 14.1% (GSI) and 62% to 42.9% (BQ). Unemployment peaks at 19.8% in India (2033) and 16.6% onshore (2030). Q3: all three still adjusting in 2038-2040 (OIT headcount falling 5.2% a year) |
| T3 T&M brake | AI on; run a: `TMBrake = 0`; run b: `TMBrake = 0.8` | B2 slows effort-billed vendors | 2030 adoption, a / T2 / b: OIT 0.71 / 0.61 / 0.50; BQ 0.72 / 0.57 / 0.38. Vendor headcount in 2030: 38,046 / 39,362 / 40,835. Boutique 2040 work share 12.3% / 11.6% / 10.6% |
| T4 GCC push | AI on, `GCCAppealEnd = 1` (ramp 2027-2031) | Captives grow where they already are | GCC share 16.2% in 2040 (9.3% in T2), GCC headcount 7,334; FIN 28.8%, MFG 20.4%, GOV 1.5%. India unemployment 14.2% in 2040 (17.3%) |
| T5 Indian IT price war | `AIOn = false`, `PriceShock[OIT] = 0.40` | Work moves between archetypes | OIT margin -35.1% in 2028, viability negative for about 11 years; OIT 11,953 by 2040 (-53%) and work share 14.9%; global SIs take most of the work (28.4%, 24,013 people), then in-house (35.2%) and GCCs (14.2%). Q3: OIT still adjusting, GSI and BQ in equilibrium |
| T6 Strict regulation | AI on, `RegScenario = 1.5` | Regulated sectors move away from offshore | OIT 2040 share in FIN 23.2% (23.9% in T2), GOV 5.3% (5.6%); 45,927 employed |
| T7 Time step check | Time step 1/32 yr only | Results barely change | Totals within 0.1% of T2; each employer within 1% |
| T8 Extreme | Extreme AI, consumer and budget settings from Phase 6a, `PriceShock` OIT 0.5 and GSI 0.3, `VTEnd = 1`, `GCCAppealEnd = 3`, `TMBrake = 1` | Nothing breaks | No stock goes negative; `PeopleCheck` and `WorkCheck` hold |

&#91;embedded content: prototype simulation of these exact equations (phase6b\_sim.py), Euler, time step 1/16 yr\]

**Reading the results**

- **Q1: everyone shrinks, vendor India most.** Consumer IT jobs fall about 40% onshore and 50% in GCCs; vendor jobs fall 40% onshore and 57% in India. India's IT unemployment peaks near 20%.
- **Q2: the mix moves away from effort billing for every archetype,** but boutiques keep the most time and materials and staff augmentation. The T&M brake (B2) changes when vendors adopt AI more than where they end up: by 2036 every employer is fully adopted.
- **Q3: no archetype collapses, but none has settled by 2040.** Indian IT is still shrinking 5% a year in 2040, so the spec's answer is "still adjusting", with R6 and arbitrage erosion still dominant for offshore delivery.
- **Arbitrage erosion favours boutiques and in-house teams.** As AI cuts every option's cost per unit of work, the absolute gap between onshore and offshore narrows, and proximity, domain knowledge and lower risk carry more weight. Boutiques almost double their share; Indian IT loses a third of its share.
- **Global SIs hold share but lose people,** because half their delivery is already onshore and their books are mostly fixed price and managed services.
- **When Indian IT is squeezed, global SIs are the main winners** (T5): they offer offshore delivery without the risk of a loss-making supplier.
- **Regulation matters less for sourcing than for adoption.** Strict regulation barely moves offshore shares; its main effect (Phase 6a) is slower consumer adoption and more governance work.
