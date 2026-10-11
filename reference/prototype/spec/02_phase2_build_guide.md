# Phase 2 build guide

Phase 2 replaces Phase 1's single Headcount stock with a labour market: a Junior/Mid/Senior career chain, vacancies filled through a matching function, onboarding, recovering and active job seekers, exits from IT, and an entrant pipeline that responds to job prospects. It is done when the talent-pipeline delay (B4) and discouraged-entry delay (B5) show up in test runs; every value below was verified in a prototype that conserves people exactly.

## Structure

Every level runs the same people cycle, built three times; promotions connect headcount at one level to vacancies at the next.

&#91;embedded content: Phase 2 people cycle per level · repeated for junior, mid and senior\]

People flow from job search through onboarding into headcount, and back out through quits, layoffs or leaving IT. Vacancies are slots rather than people: hires and promotions remove a slot as they move a person. Juniors arrive as graduates from the entrant pipeline; mids and seniors arrive mainly by promotion, plus experienced entry when roles stay hard to fill.

## What changes from Phase 1

The demand, AI and productivity parts of Phase 1 stay exactly as built; only the workforce is replaced.

- **Keep unchanged:** `Year`, `a`, `P_AI`, `P_eff`, `JevonsMult`, `Demand`, `Completion`, `Abandonment`, the `A` and `PerceivedP` stocks and their flows.
- **Delete:** the `Headcount` stock, `Hiring`, `Attrition`, `Layoffs`, `Adjustment`, `DesiredHeadcount` and the parameter `AvgTenure`.
- **Replace:** `Capacity` now counts every level and onboarding staff (formula below).
- **Add:** 20 stocks (plus one optional check stock), their flows and the Phase 2 parameters.

Three design decisions shape the build:

- **One aggregate employer.** Phase 2 still has one sector and one employer, so moving between IT employers is internal. Voluntary quits go into job search and are rehired at the same level, which is what creates normal frictional unemployment. Switching between distinct employers arrives in Phase 3.
- **Promotions fill vacancies.** People are promoted only into open upper-level roles, capped by how many are eligible below. Cutting junior hiring therefore starves future mid and senior supply, which is the mechanism behind loop B4.
- **Wages held constant.** Phase 2 has no money yet. Shortages instead draw in experienced people from other industries and career breaks once fill times rise above normal; endogenous wages are decided before Phase 4.

One insight from calibration worth knowing: near these settings the labour market has two possible steady states, a slack one and a chronic-shortage one, and which one you get depends on graduate supply. With `BaseEnrolment` at 6,100 the model sits in the slack one; at about 6,000 it tips into shortage.

## AnyLogic setup

Build on a copy of your working Phase 1 model, one level at a time, and re-run T1 after each step.

1. **Save a copy** of the Phase 1 model as Phase 2, then delete the Phase 1 workforce elements listed above.
2. **Use separate stocks per level** with the suffixes `_J`, `_M`, `_S`. AnyLogic's dimensions (arrays) could compress this, but separate stocks are far easier to debug; Phase 6 converts them to arrays.
3. **Add the labour pools for juniors first:** `H_J`, `O_J`, `V_J`, `R_J`, `U_J`, plus `Pipeline`, `LeftField` and `Retired`, with the initial values from the Stocks table.
4. **Draw people flows and slot flows separately.** A vacancy is a slot, not a person: a hire moves a person from `U_J` to `O_J` (flow `Hires_J`) and, as a second flow with the same formula, removes a slot from `V_J` to outside (`HireFill_J`). Promotions work the same way (`Promo_M` moves a person from `H_J` to `H_M`; `PromoFill_M` removes the slot from `V_M`).
5. **Repeat steps 3-4 for mid and senior**, adding promotions between levels, retirement flows for seniors, and the experienced-entry flows into `U_M` and `U_S`.
6. **Add the two perception stocks** `PercUnempShort` and `PercUnempLong` (first-order smooths of the unemployment rate).
7. **Add parameters and dynamic variables** from the tables, then draw dependency links until AnyLogic's error list is empty.
8. **Add a conservation check (recommended):** a stock `CumInflows` (initial 0) fed by `Graduation + ExtEntry_M + ExtEntry_S`, and a dynamic variable `PeopleCheck` = all `H`, `O`, `R`, `U` stocks + `LeftField` + `Retired` - `CumInflows`. It must stay at 93,960 in every run; if it drifts, a flow is attached to the wrong stock.
9. **Add plots:** headcount by level; `UnempRate`; `Enrolment` with `Graduation`; and `TTF_J`, `TTF_M`, `TTF_S`.
10. **Run T1.** Totals should hold at 84,288 people and 6.7% unemployment before you try anything else.

## Stocks and initial values

Initial values are the model's own steady state with AI off, so T1 stays flat; the senior level is largest because "8+ years" spans most of a career.

| Stock | Meaning | Junior `_J` | Mid `_M` | Senior `_S` | Inflows | Outflows |
| --- | --- | --- | --- | --- | --- | --- |
| `H` | Employed headcount | 14,876 | 19,044 | 50,368 | `OnboardDone`, `Promo` in (M, S) | `Promo` out (J, M), `Quits`, `LeaveIT`, `Layoffs`, `Retire` (S) |
| `O` | Onboarding (new hires ramping up) | 1,983 | 474 | 974 | `Hires` | `OnboardDone` |
| `V` | Vacancies (open slots) | 812 | 3,734 | 743 | `Openings` | `Cancel`, `HireFill`, `PromoFill` (M, S) |
| `R` | Recovering after layoff (not searching) | 0 | 0 | 0 | `Layoffs` | `RecToSeek`, `RecToLeft`, `RecRetire` (S) |
| `U` | Active job seekers | 4,844 | 119 | 1,278 | `Quits`, `RecToSeek`, `Graduation` (J), `ExtEntry` (M, S) | `Hires`, `SeekExit`, `SeekRetire` (S) |

| Stock | Initial value | Inflows | Outflows |
| --- | --- | --- | --- |
| `Backlog` | 53,387 | `Demand` | `Completion`, `Abandonment` |
| `Pipeline` (students in IT programmes) | 24,722 | `Enrolment` | `Graduation` |
| `LeftField` | 0 | `LeaveIT`, `RecToLeft`, `SeekExit` (all levels) | None |
| `Retired` | 0 | `Retire_S`, `RecRetire_S`, `SeekRetire_S` | None |
| `PercUnempShort` | 0.0673 | `ShortPerceptionChange` (can be negative) | None |
| `PercUnempLong` | 0.0673 | `LongPerceptionChange` (can be negative) | None |
| `A`, `PerceivedP` | 0.05, 1 | As in Phase 1 | As in Phase 1 |

`Backlog` starts at 53,387 rather than Phase 1's 50,000 because onboarding staff work at half productivity, so the steady state carries slightly more work in progress.

## Flows and variables

Formulas written with `_l` are entered three times, once each with `_J`, `_M` and `_S`; level-specific formulas follow in their own table.

**Shared variables**

| Name | Element | Formula |
| --- | --- | --- |
| `EffStaff` | Dynamic variable | `W_J*(H_J + OnboardProductivity*O_J) + W_M*(H_M + OnboardProductivity*O_M) + W_S*(H_S + OnboardProductivity*O_S)` |
| `Capacity` | Dynamic variable (replaces Phase 1) | `WorkPerPerson * P_eff * EffStaff` |
| `DesiredEff` | Dynamic variable | `Backlog / (TargetClearanceTime * WorkPerPerson * PerceivedP)` |
| `Share_J` | Dynamic variable | `Share0_J * (1 - JuniorCut * (AIOn ? A : 0))` |
| `Share_M` | Dynamic variable | `Share0_M * (1 - Share_J) / (Share0_M + Share0_S)` |
| `Share_S` | Dynamic variable | `Share0_S * (1 - Share_J) / (Share0_M + Share0_S)` |
| `ShareDenom` | Dynamic variable | `Share_J*W_J + Share_M*W_M + Share_S*W_S` |
| `Unemployed` | Dynamic variable | `R_J + R_M + R_S + U_J + U_M + U_S` |
| `UnempRate` | Dynamic variable | `Unemployed / (H_J + H_M + H_S + O_J + O_M + O_S + Unemployed)` |
| `LeaveEffect` | Dynamic variable | `min(3, max(0.5, PercUnempShort / NormalUnempRate))` |
| `EnrolEffect` | Dynamic variable | `min(1.3, max(0.4, 1 - EnrolSensitivity * (PercUnempLong / NormalUnempRate - 1)))` |
| `ShortPerceptionChange` | Flow into PercUnempShort | `(UnempRate - PercUnempShort) / UnempPerceptionTime` |
| `LongPerceptionChange` | Flow into PercUnempLong | `(UnempRate - PercUnempLong) / StudentPerceptionTime` |
| `Enrolment` | Flow into Pipeline | `BaseEnrolment * EnrolEffect` |
| `Graduation` | Flow Pipeline to U\_J | `Pipeline / StudyTime` |

**Per-level formulas (enter for J, M and S)**

| Name | Element | Formula |
| --- | --- | --- |
| `Desired_l` | Dynamic variable | `DesiredEff * Share_l / ShareDenom` |
| `Surplus_l` | Dynamic variable | `H_l + O_l - Desired_l` |
| `Cancel_l` | Flow V\_l to outside | `min((Surplus_l <= 0 ? max(0, V_l + Surplus_l) : V_l) / CancelTime, V_l / MinFillTime)` |
| `Available_l` | Dynamic variable | `max(0, V_l / MinFillTime - Cancel_l)` |
| `Quits_l` | Flow H\_l to U\_l | `H_l * QuitRate_l` |
| `LeaveIT_l` | Flow H\_l to LeftField | `H_l * LeaveITRate_l` |
| `NetLoss_l` | Dynamic variable | `Quits_l + LeaveIT_l + PromoOut_l + RetireLoss_l` (see note) |
| `Openings_l` | Flow outside to V\_l | `Surplus_l <= 0 ? max(0, NetLoss_l + (-Surplus_l - V_l) / HireAdjTime) : 0` |
| `Layoffs_l` | Flow H\_l to R\_l | `Surplus_l > 0 ? min(max(0, Surplus_l / LayoffAdjTime - NetLoss_l), H_l / MinLayoffTime) : 0` |
| `Match_l` | Dynamic variable | `(U_l > 0 && V_l > 0) ? m * pow(U_l, alpha) * pow(V_l, 1 - alpha) : 0` |
| `Hires_l` | Flow U\_l to O\_l | `max(0, min(Match_l, min(Available_l - PromoIn_l, U_l / MinFillTime)))` |
| `HireFill_l` | Flow V\_l to outside | `Hires_l` |
| `TTF_l` | Dynamic variable (time to fill, yr) | `V_l / max(Hires_l + PromoIn_l, 1)` |
| `OnboardDone_l` | Flow O\_l to H\_l | `O_l / OnboardTime` |
| `LeaveFrac_l` | Dynamic variable | `min(0.9, BaseLeaveFrac_l * LeaveEffect)` |
| `RecToSeek_l` | Flow R\_l to U\_l | `R_l / RecoveryTime * (1 - LeaveFrac_l)` |
| `RecToLeft_l` | Flow R\_l to LeftField | `R_l / RecoveryTime * LeaveFrac_l` |
| `SeekExit_l` | Flow U\_l to LeftField | `U_l * SeekerExitRate * LeaveEffect` |

In `NetLoss_l` and `Hires_l`, use these level-specific terms: `PromoOut_J = Promo_M`, `PromoOut_M = Promo_S`, `PromoOut_S = 0`; `PromoIn_J = 0`, `PromoIn_M = Promo_M`, `PromoIn_S = Promo_S`; `RetireLoss_S = Retire_S`, and 0 for juniors and mids.

**Level-specific formulas**

| Name | Element | Formula |
| --- | --- | --- |
| `Promo_M` | Flow H\_J to H\_M | `min(H_J / TimeInJunior, min(V_M / PromoFillTime, Available_M))` |
| `PromoFill_M` | Flow V\_M to outside | `Promo_M` |
| `Promo_S` | Flow H\_M to H\_S | `min(H_M / TimeInMid, min(V_S / PromoFillTime, Available_S))` |
| `PromoFill_S` | Flow V\_S to outside | `Promo_S` |
| `Retire_S` | Flow H\_S to Retired | `H_S * RetireRate_S` |
| `RecRetire_S` | Flow R\_S to Retired | `R_S * RetireRate_S` |
| `SeekRetire_S` | Flow U\_S to Retired | `U_S * RetireRate_S` |
| `ExtEntry_M` | Flow outside to U\_M | `ExtEntryRate_M * H_M * min(ExtEntryMax, max(0, TTF_M / NormalTTF_M - 1))` |
| `ExtEntry_S` | Flow outside to U\_S | `ExtEntryRate_S * H_S * min(ExtEntryMax, max(0, TTF_S / NormalTTF_S - 1))` |

Why the vacancy flows are ordered (cancellations, then promotions, then hires, all within `V_l / MinFillTime`): it is the only way to guarantee a vacancy stock never goes negative. Keep `MinFillTime` at or above the time step.

## Parameters

All Phase 1 parameters keep their values except `AvgTenure`, which is deleted. The three calibrated values (`NormalUnempRate`, `NormalTTF_M`, `NormalTTF_S`) are the steady-state outcomes; change any other parameter and they must be recalibrated with the prototype.

| Parameter | Junior | Mid | Senior | Unit | Meaning |
| --- | --- | --- | --- | --- | --- |
| `W_l` | 0.6 | 1.0 | 1.4 | dimensionless | Output per person relative to a mid-level |
| `Share0_l` | 0.19 | 0.25 | 0.56 | fraction | Desired level mix without AI |
| `QuitRate_l` | 0.15 | 0.10 | 0.08 | 1/yr | Voluntary moves into job search |
| `LeaveITRate_l` | 0.05 | 0.06 | 0.04 | 1/yr | Employed people leaving IT |
| `BaseLeaveFrac_l` | 0.05 | 0.10 | 0.20 | fraction | Share of laid-off people who leave IT at normal prospects |
| `ExtEntryRate_l` | none | 0.05 | 0.05 | 1/yr | Experienced entry per unit of excess fill time, as a share of headcount |

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `JuniorCut` | 0.5 | fraction | Share of junior roles AI removes at full adoption |
| `TimeInJunior` | 3 | yr | Time until a junior is eligible for promotion |
| `TimeInMid` | 5 | yr | Time until a mid is eligible for promotion |
| `PromoFillTime` | 0.125 | yr | How fast internal candidates fill upper vacancies |
| `RetireRate_S` | 0.033 | 1/yr | Senior retirement, employed and unemployed |
| `OnboardTime` | 0.25 | yr | Ramp-up period for new hires |
| `OnboardProductivity` | 0.5 | fraction | Output of onboarding staff relative to fully productive |
| `CancelTime` | 0.25 | yr | Time to withdraw unneeded vacancies |
| `m` | 4 | 1/yr | Matching efficiency (where recruiters and AI screening act) |
| `alpha` | 0.5 | dimensionless | Weight of seekers versus vacancies in matching |
| `MinFillTime` | 0.0625 | yr | Fastest a vacancy can be filled; equals the time step |
| `RecoveryTime` | 0.33 | yr | Time laid-off people take before searching |
| `SeekerExitRate` | 0.10 | 1/yr | Long-term seekers giving up on IT at normal prospects |
| `UnempPerceptionTime` | 0.5 | yr | How quickly workers sense the job market |
| `BaseEnrolment` | 6100 | persons/yr | Students entering IT programmes at normal prospects |
| `StudyTime` | 4 | yr | Length of study |
| `StudentPerceptionTime` | 2 | yr | How slowly students sense the job market |
| `EnrolSensitivity` | 1 | dimensionless | Enrolment response to unemployment above normal |
| `ExtEntryMax` | 3 | dimensionless | Cap on the excess fill-time ratio for experienced entry |
| `NormalUnempRate` | 0.0673 | fraction | Calibrated: steady-state IT unemployment |
| `NormalTTF_M` | 0.542 | yr | Calibrated: steady-state mid time to fill |
| `NormalTTF_S` | 0.095 | yr | Calibrated: steady-state senior time to fill |

## Tests and reference results

Run the six tests in order; your results should land within about 1% of these prototype values, and `PeopleCheck` must stay at 93,960 in every run.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | 84,288 employed, flat to within 0.01%; unemployment 6.7%; fill times about 1.2 months (junior), 6.5 months (mid), 1.2 months (senior) |
| T2 Demand step | `AIOn = false`, `DemandStep = 0.2` | Shortage, then the B5 boom/bust cycle | Mid fill time peaks at about 15 months and unemployment dips to 2.1% around 2030; employment reaches about 100,800 by 2034; enrolment swings from 7,630 (2030) to 5,400 (2034) and back to 7,640 (2040) |
| T3 AI base case | None (`AIOn = true`) | B5 and B4 both visible | Employment 74,600 (2028), 66,300 (2030), 54,100 (2034), 48,000 (2040); 2040 split 4,600 junior, 9,900 mid, 33,500 senior; unemployment peaks near 18.3% in 2031 and is 11.6% in 2040; enrolment at its floor (2,440) from 2028; graduates down to 2,570; mid fill time 18 months by 2040 |
| T4 Rebound | `DemandStep = 0.35`, `StepYear = 2034` | Experience shortage despite plentiful juniors | In 2036 mid roles take about 31 months and senior roles 15 months to fill while juniors fill in under 2 months; unemployment dips to 3.2% in 2037 |
| T5 Time step check | Time step 1/32 yr `only (leave MinFillTime at 0.0625)` | Results barely change | Within 0.1% of T3 |
| T6 Extreme AI | Phase 1 extreme settings plus `JuniorCut = 0.9` | Nothing breaks | No stock goes negative; employment falls to about 5,100; `PeopleCheck` holds |

&#91;embedded content: prototype simulation of these exact equations (phase2\_sim.py), AI base run T3, Euler, time step 1/16 yr\]

B5 shows as the four-year gap between enrolment collapsing and graduates falling. B4 shows as mid-level roles getting steadily harder to fill from 2031, even with double-digit unemployment, because fewer juniors were hired and promoted five years earlier.
