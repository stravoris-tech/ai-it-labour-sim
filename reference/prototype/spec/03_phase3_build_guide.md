# Phase 3 build guide

Phase 3 splits the workforce across two regions and three employers: consumer in-house teams onshore, consumer GCCs in India, and a vendor with offshore staff in India plus onsite staff onshore, some on visas. It adds the visa policy lever and job switching between employers. It is done when headcount plots split by region and visa scenarios move the onsite workforce; every value below was verified in a prototype that conserves people exactly.

## Structure

Five employment units hire from two regional labour pools; the onsite visa unit works onshore but draws on, and returns people to, the India pool.

&#91;embedded content: Phase 3 structure · 5 units, 2 regional pools\]

Each unit keeps Phase 2's full people cycle (vacancies, onboarding, promotions, quits, layoffs, exits) by level. Visa policy acts on the highlighted unit: tighter policy caps visa hiring, slows green-card conversion, and prompts vendors to shift onsite work offshore or to local hires.

## What changes from Phase 2

Phase 2's single workforce becomes five employment units, and its single labour pool becomes two regional pools; the demand, AI and productivity parts stay unchanged.

| Unit | Element | Employer | Work is done in | Hires from and exits to |
| --- | --- | --- | --- | --- |
| In-house | `IH` | Consumer | Onshore | Onshore pool |
| GCC | `GCC` | Consumer (captive centre) | India | India pool |
| Vendor India | `VI` | Vendor | India | India pool |
| Onsite visa | `OV` | Vendor | Onshore | India pool (visa holders) |
| Onsite local | `OL` | Vendor | Onshore | Onshore pool |

Five design decisions shape the build:

- **Work shares are fixed in Phase 3.** In-house takes 30% of the work, GCCs 10% and the vendor the rest, of which 25% is done onsite. Endogenous sourcing choice arrives in Phase 5; until then a GCC ramp lets you test captive growth.
- **Onsite visa staff hire from, and return to, the India pool.** They work onshore (so they count in onshore headcount) but are drawn from India seekers. When a visa expires they rejoin the India pool; conversion to permanent residence moves them, still employed, into Onsite local.
- **Firms respond to perceived visa tightness.** As tightness rises above its 2024 level, vendors move part of the onsite work offshore and staff more onsite roles with local hires. A hard cap on visa approvals also applies.
- **Job switching is direct, within a region.** People move between GCC and Vendor India, and between In-house and Onsite local, pulled by wage ratios and open vacancies. Visa holders do not switch. Switches fill the destination's vacancies and create replacement vacancies at the source.
- **Wages only drive switching.** Wages are relative indexes in each region (GCC pays 30% more than Vendor India); money enters in Phase 4.

## AnyLogic setup

Phase 3 is where separate stocks per level stop being practical (they would number over 60), so it switches to AnyLogic array variables. Element references use names in square brackets, such as `H[GCC, MID]`, and partial sums use `.sum(...)` with `INDEX_CAN_VARY` ([AnyLogic help: arrays](https://anylogic.help/anylogic/system-dynamics/arrays.html)).

1. **Save a copy** of your working Phase 2 model as Phase 3.
2. **Create three Dimensions** (System Dynamics palette): `Unit` = {`IH`, `GCC`, `VI`, `OV`, `OL`}, `Level` = {`JUNIOR`, `MID`, `SENIOR`}, `Region` = {`INDIA`, `ONSHORE`}.
3. **Create subdimensions** used for per-element formulas: on `Unit`, `IndiaPoolUnits` = {`GCC`, `VI`, `OV`} and `OnshorePoolUnits` = {`IH`, `OL`}; on `Level`, `Experienced` = {`MID`, `SENIOR`}.
4. **Rebuild the labour stocks as arrays:** `H`, `O`, `V` with dimensions `[Unit, Level]`; `R`, `U` with `[Region, Level]`; `Pipeline`, `LeftField`, `Retired`, `PercUnempShort`, `PercUnempLong` with `[Region]`. Delete the Phase 2 per-level stocks once each array is in place.
5. **Use custom stock equations.** Several stocks receive flows of a different dimension (a regional pool collects layoffs from three units), which ordinary flow arrows cannot connect. Type each stock's derivative from the Stock equations table, using AnyLogic's option to give different formulas to sub-arrays. Rates become array dynamic variables. If your AnyLogic version does not allow custom stock equations, draw one flow per term instead.
6. **Add the scalar Phase 3 variables** (visa tightness, work allocation) and the new parameters, making `BaseEnrolment`, `NormalUnempRate`, `NormalTTF` and `Wage` array parameters as listed.
7. **Add the array rates** group by group in the order of the formula tables: unit flows, visa flows, switching, matching, pools. Re-run after each group to catch errors early.
8. **Add the conservation check:** a stock `CumInflows` (initial 0) with derivative `Graduation.sum() + ExtEntry.sum()`, and `PeopleCheck = H.sum() + O.sum() + R.sum() + U.sum() + LeftField.sum() + Retired.sum() - CumInflows`. It must stay at 93,437.
9. **Add plots:** headcount by unit; onshore-located headcount (`IH + OV + OL`) versus India-located (`GCC + VI`); `UnempRate` by region; `VisaHires` against `VisaCap`.
10. **Run T1** and confirm 84,134 people, flat, before testing scenarios.

## Stocks and initial values

Initial values are the model's own steady state with AI off and visa policy at its 2024 level: 84,134 employed, 46,725 working in India and 37,409 onshore.

**Unit arrays `[Unit, Level]`** (each cell: JUNIOR / MID / SENIOR)

| Unit | `H` employed | `O` onboarding | `V` vacancies |
| --- | --- | --- | --- |
| `IH` | 4,352 / 5,714 / 15,480 | 578 / 148 / 303 | 477 / 1,253 / 154 |
| `GCC` | 1,525 / 2,013 / 5,111 | 191 / 42 / 70 | 86 / 317 / 131 |
| `VI` | 6,781 / 8,695 / 22,600 | 916 / 230 / 454 | 413 / 1,747 / 852 |
| `OV` | 1,281 / 1,383 / 3,969 | 235 / 87 / 283 | 106 / 664 / 530 |
| `OL` | 889 / 1,194 / 3,147 | 109 / 25 / 29 | 90 / 212 / 34 |

**Regional arrays**

| Stock | Dimensions | `INDIA` | `ONSHORE` |
| --- | --- | --- | --- |
| `U` active seekers | `[Region, Level]` | 2,977 / 90 / 431 | 833 / 43 / 1,229 |
| `R` recovering | `[Region, Level]` | 0 / 0 / 0 | 0 / 0 / 0 |
| `Pipeline` | `[Region]` | 16,037 | 8,182 |
| `LeftField`, `Retired` | `[Region]` | 0 | 0 |
| `PercUnempShort`, `PercUnempLong` | `[Region]` | 0.0589 | 0.0618 |

**Scalars:** `Backlog` 54,454; `A` 0.05; `PerceivedP` 1; new stock `TightPerc` (perceived visa tightness) 0.3; check stock `CumInflows` 0.

## Formulas

Formulas written with dimension names (`[Unit, Level]`) apply to every element; rows marked by element or subdimension are per-element formulas. Phase 2's per-level parameters become arrays over `Level` (for example `QuitRate[Level]` replaces `QuitRate_J`, `QuitRate_M`, `QuitRate_S`). Phase 1 variables stay unchanged.

**A. Visa lever and work allocation (scalars unless shown)**

| Name | Formula |
| --- | --- |
| `VisaTight` | `VTBase + (VTEnd - VTBase) * min(1, max(0, (Year - VTRampStart) / (VTRampEnd - VTRampStart)))` |
| `dTight` | `TightPerc - VTBase` |
| `OnsiteShare` | `min(1, max(0, OnsiteShare0 * (1 - OffshoreShiftSens * dTight)))` |
| `VisaMix` | `min(1, max(0, VisaMix0 * (1 - VisaMixSens * dTight)))` |
| `GCCShare` | `GCCShare0 + (GCCShareEnd - GCCShare0) * min(1, max(0, (Year - GCCRampStart) / (GCCRampEnd - GCCRampStart)))` |
| `VendorShare` | `1 - InHouseShare - GCCShare` |
| `UnitShare[Unit]` | `IH`: `InHouseShare` · `GCC`: `GCCShare` · `VI`: `VendorShare * (1 - OnsiteShare)` · `OV`: `VendorShare * OnsiteShare * VisaMix` · `OL`: `VendorShare * OnsiteShare * (1 - VisaMix)` |
| `Share[Level]` | `JUNIOR`: `Share0[JUNIOR] * (1 - JuniorCut * (AIOn ? A : 0))` · `Experienced`: `Share0[Level] * (1 - Share[JUNIOR]) / (Share0[MID] + Share0[SENIOR])` |
| `ShareDenom` | `Share[JUNIOR]*W[JUNIOR] + Share[MID]*W[MID] + Share[SENIOR]*W[SENIOR]` |
| `EffStaff` | `W[JUNIOR]*(H.sum(INDEX_CAN_VARY, JUNIOR) + OnboardProductivity*O.sum(INDEX_CAN_VARY, JUNIOR))` + the same for `MID` and `SENIOR` |
| `Desired[Unit, Level]` | `DesiredEff * UnitShare[Unit] * Share[Level] / ShareDenom` |

**B. Unit flows `[Unit, Level]`**

| Name | Formula |
| --- | --- |
| `Surplus` | `H[Unit, Level] + O[Unit, Level] - Desired[Unit, Level]` |
| `Cancel` | `min((Surplus <= 0 ? max(0, V + Surplus) : V) / CancelTime, V / MinFillTime)` (all terms `[Unit, Level]`) |
| `Avail` | `max(0, V / MinFillTime - Cancel)` |
| `Promo` | `JUNIOR`: 0 · `MID`: `min(H[Unit, JUNIOR] / TimeInJunior, min(V[Unit, MID] / PromoFillTime, Avail[Unit, MID]))` · `SENIOR`: `min(H[Unit, MID] / TimeInMid, min(V[Unit, SENIOR] / PromoFillTime, Avail[Unit, SENIOR]))` |
| `PromoOut` | `JUNIOR`: `Promo[Unit, MID]` · `MID`: `Promo[Unit, SENIOR]` · `SENIOR`: 0 |
| `Quits` | `H * QuitRate[Level]` |
| `LeaveIT` | `H * LeaveITRate[Level]` |
| `Retire` | `SENIOR`: `H * RetireRate_S` · others: 0 |
| `OnboardDone` | `O / OnboardTime` |
| `VisaOut` | `OV`: `Expiry[Level] + Conversion[Level]` · others: 0 |
| `ConvIn` | `OL`: `Conversion[Level]` · others: 0 |
| `NetLoss` | `Quits + LeaveIT + Retire + PromoOut + SwitchOut + VisaOut` |
| `Openings` | `Surplus <= 0 ? max(0, NetLoss + (-Surplus - V) / HireAdjTime) : 0` |
| `Layoffs` | `Surplus > 0 ? min(max(0, Surplus / LayoffAdjTime - NetLoss), H / MinLayoffTime) : 0` |

**C. Job switching (arrays over `Level`)**

| Name | Formula |
| --- | --- |
| `G_VI_GCC` (scalar) | `min(SwitchMax, pow(Wage[GCC] / Wage[VI], SwitchElasticity))`; likewise `G_GCC_VI`, `G_OL_IH`, `G_IH_OL` with the wage ratio destination / source |
| `SwVItoGCC[Level]` | `(V[GCC, Level] + V[VI, Level] > 0) ? min(H[VI, Level] * SwitchRate * G_VI_GCC * V[GCC, Level] / (V[GCC, Level] + V[VI, Level]), max(0, Avail[GCC, Level] - Promo[GCC, Level])) : 0` |
| `SwGCCtoVI`, `SwOLtoIH`, `SwIHtoOL` | Same pattern: source headcount × `SwitchRate` × its `G` factor × destination's share of the pair's vacancies, capped by the destination's room |
| `SwitchIn[Unit, Level]` | `GCC`: `SwVItoGCC` · `VI`: `SwGCCtoVI` · `IH`: `SwOLtoIH` · `OL`: `SwIHtoOL` · `OV`: 0 |
| `SwitchOut[Unit, Level]` | `GCC`: `SwGCCtoVI` · `VI`: `SwVItoGCC` · `IH`: `SwIHtoOL` · `OL`: `SwOLtoIH` · `OV`: 0 |

**D. Visa flows**

| Name | Formula |
| --- | --- |
| `Expiry[Level]` | `H[OV, Level] / VisaTenure` |
| `Conversion[Level]` | `H[OV, Level] * ConvRate * (1 - VisaTight)` |
| `VisaCap` | `BaseVisaCap * (1 - VisaTight)` |

**E. Regional matching**

| Name | Formula |
| --- | --- |
| `VPool[Region, Level]` | `INDIA`: `V[GCC, Level] + V[VI, Level] + V[OV, Level]` · `ONSHORE`: `V[IH, Level] + V[OL, Level]` |
| `Match[Region, Level]` | `(U > 0 && VPool > 0) ? m * pow(U, alpha) * pow(VPool, 1 - alpha) : 0` |
| `Room[Unit, Level]` | `max(0, Avail - Promo - SwitchIn)` |
| `RawHires[Unit, Level]` | `IndiaPoolUnits`: `VPool[INDIA, Level] > 0 ? min(Match[INDIA, Level] * V[Unit, Level] / VPool[INDIA, Level], Room[Unit, Level]) : 0` · `OnshorePoolUnits`: the same with `ONSHORE` |
| `RawPool[Region, Level]` | `INDIA`: `RawHires[GCC, Level] + RawHires[VI, Level] + RawHires[OV, Level]` · `ONSHORE`: `RawHires[IH, Level] + RawHires[OL, Level]` |
| `PoolScale[Region, Level]` | `RawPool > U / MinFillTime ? (U / MinFillTime) / RawPool : 1` |
| `VisaDemand` | `RawHires[OV, JUNIOR]*PoolScale[INDIA, JUNIOR] + RawHires[OV, MID]*PoolScale[INDIA, MID] + RawHires[OV, SENIOR]*PoolScale[INDIA, SENIOR]` |
| `VisaScale` | `VisaDemand > VisaCap ? VisaCap / VisaDemand : 1` |
| `Hires[Unit, Level]` | `OV`: `RawHires[OV, Level] * PoolScale[INDIA, Level] * VisaScale` · `GCC`, `VI`: `RawHires * PoolScale[INDIA, Level]` · `IH`, `OL`: `RawHires * PoolScale[ONSHORE, Level]` |
| `Fills[Unit, Level]` | `Hires + Promo + SwitchIn` |
| `TTF[Unit, Level]` | `V / max(Fills, 1)` |
| `TTFPool[Region, Level]` | `INDIA`: `VPool[INDIA, Level] / max(Fills[GCC, Level] + Fills[VI, Level] + Fills[OV, Level], 1)` · `ONSHORE`: same with `IH`, `OL` |
| `HPool[Region, Level]` | `INDIA`: `H[GCC, Level] + H[VI, Level] + H[OV, Level]` · `ONSHORE`: `H[IH, Level] + H[OL, Level]` |
| `ExtEntry[Region, Level]` | `JUNIOR`: 0 · `Experienced`: `ExtEntryRate[Level] * HPool * min(ExtEntryMax, max(0, TTFPool / NormalTTF[Region, Level] - 1))` |

**F. Regional pools**

| Name | Formula |
| --- | --- |
| `Unemployed[Region]` | `R.sum(Region, INDEX_CAN_VARY) + U.sum(Region, INDEX_CAN_VARY)` |
| `EmployedPool[Region]` | `INDIA`: H plus O summed over `GCC`, `VI`, `OV` (for example `H.sum(GCC, INDEX_CAN_VARY) + O.sum(GCC, INDEX_CAN_VARY) + ...`) · `ONSHORE`: over `IH`, `OL` |
| `UnempRate[Region]` | `Unemployed / (EmployedPool + Unemployed)` |
| `LeaveEffect[Region]` | `min(3, max(0.5, PercUnempShort / NormalUnempRate))` |
| `EnrolEffect[Region]` | `min(1.3, max(0.4, 1 - EnrolSensitivity * (PercUnempLong / NormalUnempRate - 1)))` |
| `LeaveFrac[Region, Level]` | `min(0.9, BaseLeaveFrac[Level] * LeaveEffect[Region])` |
| `RecToSeek`, `RecToLeft` | `R / RecoveryTime * (1 - LeaveFrac)` and `R / RecoveryTime * LeaveFrac` |
| `SeekExit[Region, Level]` | `U * SeekerExitRate * LeaveEffect[Region]` |
| `RecRetire`, `SeekRetire` | `SENIOR`: `R * RetireRate_S` and `U * RetireRate_S` · others: 0 |
| `Enrolment[Region]` | `BaseEnrolment[Region] * EnrolEffect[Region]` |
| `Graduation[Region]` | `Pipeline / StudyTime` |
| `PoolLayoffs`, `PoolQuits`, `PoolHires` `[Region, Level]` | `INDIA`: the unit rate summed over `GCC`, `VI`, `OV` · `ONSHORE`: over `IH`, `OL` |
| `PoolLeaveIT`, `PoolRetire` `[Region]` | The same pooling, also summed over levels |

**G. Stock equations**

| Stock | Derivative |
| --- | --- |
| `V[Unit, Level]` | `Openings - Cancel - Promo - SwitchIn - Hires` |
| `O[Unit, Level]` | `Hires - OnboardDone` |
| `H[Unit, Level]` | `OnboardDone + Promo - PromoOut + SwitchIn - SwitchOut + ConvIn - Quits - LeaveIT - Retire - Layoffs - VisaOut` |
| `R[Region, Level]` | `PoolLayoffs - RecToSeek - RecToLeft - RecRetire` |
| `U[INDIA, Level]` | `PoolQuits + RecToSeek + ExtEntry + Expiry[Level] - PoolHires - SeekExit - SeekRetire`, plus `Graduation[INDIA]` for `JUNIOR` |
| `U[ONSHORE, Level]` | `PoolQuits + RecToSeek + ExtEntry - PoolHires - SeekExit - SeekRetire`, plus `Graduation[ONSHORE]` for `JUNIOR` |
| `Pipeline[Region]` | `Enrolment - Graduation` |
| `LeftField[Region]` | `PoolLeaveIT + RecToLeft.sum(Region, INDEX_CAN_VARY) + SeekExit.sum(Region, INDEX_CAN_VARY)` |
| `Retired[Region]` | `PoolRetire + RecRetire.sum(Region, INDEX_CAN_VARY) + SeekRetire.sum(Region, INDEX_CAN_VARY)` |
| `PercUnempShort[Region]`, `PercUnempLong[Region]` | `(UnempRate - PercUnempShort) / UnempPerceptionTime` and `(UnempRate - PercUnempLong) / StudentPerceptionTime` |
| `TightPerc` | `(VisaTight - TightPerc) / TightPerceptionTime` |

The order of vacancy fills matters: cancellations first, then promotions, then switches in, then external hires, each limited by the room the previous ones left. That ordering keeps every vacancy stock non-negative.

## Parameters

Phase 1 and Phase 2 parameters keep their values; Phase 2's per-level parameters become `[Level]` arrays and its three calibrated values become regional arrays. The calibrated rows are steady-state outcomes and must be recalibrated with the prototype if any other parameter changes.

**Regional and unit arrays**

| Parameter | Dimensions | Values | Meaning |
| --- | --- | --- | --- |
| `BaseEnrolment` | `[Region]` | INDIA 3,900 · ONSHORE 2,000 (persons/yr) | Students entering IT programmes at normal prospects (replaces the Phase 2 scalar) |
| `NormalUnempRate` | `[Region]` | INDIA 0.0589 · ONSHORE 0.0618 | Calibrated steady-state unemployment |
| `NormalTTF` | `[Region, Level]` | INDIA: MID 0.573, SENIOR 0.254 · ONSHORE: MID 0.583, SENIOR 0.064 (yr); JUNIOR unused | Calibrated steady-state fill times |
| `Wage` | `[Unit]` | IH 1.0 · GCC 1.3 · VI 1.0 · OV 1.0 · OL 0.95 | Relative wage within each region; only ratios inside a region matter |

**Scalars**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `InHouseShare` | 0.30 | fraction | Share of work done by consumer in-house teams |
| `GCCShare0` | 0.10 | fraction | GCC share of work at the start |
| `GCCShareEnd` | 0.10 | fraction | GCC share after the ramp (test lever; equal to start = no change) |
| `GCCRampStart`, `GCCRampEnd` | 2027, 2031 | year | When the GCC ramp runs |
| `OnsiteShare0` | 0.25 | fraction | Share of vendor work done onsite at 2024 visa tightness |
| `OffshoreShiftSens` | 0.5 | dimensionless | How strongly onsite work moves offshore as tightness rises |
| `VisaMix0` | 0.6 | fraction | Share of onsite roles staffed by visa holders at 2024 tightness |
| `VisaMixSens` | 0.8 | dimensionless | How strongly vendors switch onsite roles to local hires as tightness rises |
| `VTBase` | 0.3 | index 0-1 | Visa tightness in 2024 (0 open, 1 closed) |
| `VTEnd` | 0.3 | index 0-1 | Tightness after the ramp (scenario lever) |
| `VTRampStart`, `VTRampEnd` | 2027, 2031 | year | When the tightness ramp runs |
| `TightPerceptionTime` | 1 | yr | How long firms take to respond to a policy change |
| `BaseVisaCap` | 8,000 | persons/yr | Visa approvals available at zero tightness |
| `VisaTenure` | 6 | yr | Average time before a visa expires |
| `ConvRate` | 0.05 | 1/yr | Conversion to permanent residence at zero tightness (PERM pressure lowers it) |
| `SwitchRate` | 0.04 | 1/yr | Base rate of direct moves between paired employers |
| `SwitchElasticity` | 2 | dimensionless | Response of switching to the wage ratio |
| `SwitchMax` | 2 | dimensionless | Cap on the wage effect |

## Tests and reference results

Run the seven tests in order; results should land within about 1% of these prototype values, and `PeopleCheck` must stay at 93,437 in every run.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | 84,134 employed, flat to within 0.05%; 46,725 working in India and 37,409 onshore; unemployment 5.9% India, 6.2% onshore; about 2,420 visa hires a year against a cap of 5,600 |
| T2 Visa crackdown | `AIOn = false`, `VTEnd = 0.8` (ramp 2027-2031) | Policy moves the onsite workforce | Onsite visa staff fall from 6,633 to 3,068 by 2040 (-54%); onsite local hires rise to 6,086 (+16%); Vendor India rises to 41,041 (+8%); onshore-located headcount falls to 34,529 and India-located rises to 49,624; onshore unemployment dips to 4.4% in 2031 |
| T3 Visa relaxation | `AIOn = false`, `VTEnd = 0.1`, ramp 2029-2030 | The reverse | Onsite visa staff rise to 8,378 (+26%); onsite local hires fall to 4,519 (-14%); onshore unemployment peaks at 7.4% in 2034 |
| T4 GCC expansion | `AIOn = false`, `GCCShareEnd = 0.2` (ramp 2027-2031) | Work and people move to captives | GCC grows from 8,649 to 17,253; Vendor India falls from 38,076 to 31,588; switches into GCCs peak at about 1,120 a year in 2031 (373 normally); Vendor India turnover rises from 10.7% to 13.1% a year |
| T5 AI base case | None (`AIOn = true`) | Both regions decline | 47,824 employed by 2040 (-43%): 26,413 in India, 21,411 onshore; unemployment peaks near 17.2% in India and 18.0% onshore in 2031, 10.4% and 10.3% by 2040 |
| T6 Time step check | Time step 1/32 yr only | Results barely change | Within about 0.1% of T5 |
| T7 Extreme | Phase 2 extreme AI settings, `VTEnd = 1`, `GCCShareEnd = 0.35` | Nothing breaks | No stock goes negative; onsite visa staff fall to under 10; `PeopleCheck` holds |

&#91;embedded content: prototype simulation of these exact equations (phase3\_sim.py), scenarios T2 and T4, AI off, Euler, time step 1/16 yr\]

T5 shows both regions falling by the same 43% because every employer still shares one AI adoption curve and fixed work shares. Regional differences come from per-employer adoption (Phase 6) and from sourcing choice, where AI erodes India's cost advantage (Phase 5).
