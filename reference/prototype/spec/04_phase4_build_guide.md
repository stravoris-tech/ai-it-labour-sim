# Phase 4 build guide

Phase 4 gives the vendor a profit and loss: revenue from work delivered at a price that tracks client-perceived AI productivity; costs for labour, visas, AI tooling and overhead; a margin smoothed into a viability index; and the two loops that decide Q3. When viability falls, clients move work away (R6, the death spiral); vendors respond with cost cuts, wage restraint and leaner overhead (B6, right-sizing). It is done when a forced revenue drop triggers R6 and B6 behaves as expected; every value below was verified in a prototype that conserves people exactly.

## Structure

The vendor now has a profit and loss. Prices follow the productivity clients see, revenue follows prices and the work clients send, and margin is smoothed into a viability index that drives two opposing responses.

&#91;embedded content: Phase 4 structure · loops R6 and B6\]

When viability falls, clients move work away, which cuts revenue further (R6, the death spiral). At the same time the vendor cuts costs through a cost programme and wage restraint, which lifts the margin back (B6, right-sizing). Which loop wins depends on the size of the squeeze; the tests below find the tipping point.

## What changes from Phase 3

Everything from Phase 3 stays; Phase 4 adds a money layer on top of the vendor units (`VI`, `OV`, `OL`) and two small changes to existing formulas.

- **Add:** seven stocks (`ClientP`, `PriceIndex`, `Overhead`, `Viability`, `VSE`, `CostProg`, and `WI[Unit]` wage indexes), the finance variables and Phase 4 parameters.
- **Change `UnitShare`:** vendor work is scaled by the vendor share effect `VSE`, and the share clients take away is redistributed to in-house and GCC in proportion to their existing shares.
- **Change the switching factors:** the four `G` wage factors now use current wages (`Wage[Unit] * WI[Unit]`), so vendor wage restraint pushes more people toward GCCs.
- **Refresh initial values:** Phase 4 was calibrated jointly with its finance layer, which settled the labour market more precisely, so the Stocks section gives a complete new set of starting values.

Five design decisions:

- **Wages are endogenous but switchable.** Each unit's wage index moves toward a target set by regional unemployment (high unemployment lowers wages) and, for vendors, by margin pressure. `WagesEndogenous = 0` holds every index at 1. This settles the open decision from Phase 2 by making both options available; it is what activates loops R5 and R10.
- **Prices track what clients can see.** The price index moves toward 1 / client-perceived productivity, so clients eventually capture all observed AI gains, after a perception lag (1.5 years) and a repricing lag (2 years). Vendor wage cuts and cost programmes are not visible to clients, so vendors keep those savings.
- **R6 acts through a vendor share effect for now.** Phase 5's sourcing logit doesn't exist yet, so viability below normal shrinks the vendor's work share (clients move work in-house or to GCCs), with an extra exit penalty once viability goes negative. Phase 5 replaces this with sourcing choice.
- **B6 has three levers:** a cost programme (up to 15% labour savings from pyramid, location and automation changes), wage restraint, and overhead that adjusts to 8% of revenue over two years.
- **A ±2-point dead band** around normal margin: clients don't move work, and vendors don't launch cost programmes, over small margin wobbles.

## AnyLogic setup

The money layer sits beside the labour model, so build it as its own group of variables and test it before wiring it back into work allocation.

1. **Save a copy** of your working Phase 3 model as Phase 4.
2. **Update every initial value** from the Stocks section (labour values changed slightly with the joint calibration), and change the three calibrated parameter arrays to their Phase 4 values.
3. **Add the six scalar stocks** `ClientP`, `PriceIndex`, `Overhead`, `Viability`, `VSE`, `CostProg`, and the array stock `WI[Unit]`, each with the derivative from the Stock equations table.
4. **Add the finance variables** in table order: prices, delivery and revenue, costs, margin, then the targets for viability responses and wages. At this point the money layer only reads the labour model.
5. **Check the steady state before closing any loop:** with `AIOn = false`, margin should sit near 17.8% and revenue near $3.78 billion a year.
6. **Close R6:** change `UnitShare` to use `VSE` as shown in the formulas. Re-run T1; nothing should move.
7. **Close the wage loop:** change the four switching `G` factors to use `Wage[Unit] * WI[Unit]`.
8. **Add a units check:** money is in real 2026 USD per year; AnyLogic's unit checking will flag any formula that adds dollars to people.
9. **Add plots:** revenue and costs; margin with viability; `VSE`; `WI` for `VI`, `GCC` and `IH`; vendor headcount (`VI + OV + OL`).
10. **Run T1, then T2 and T3:** the pair of shocks is the done-criterion for this phase.

## Stocks and initial values

The starting point is the joint labour-and-finance steady state with AI off: 84,135 employed, 49,786 of them at the vendor, revenue of $3.78 billion and a 17.8% margin.

**New finance stocks**

| Stock | Initial value | Unit | Meaning |
| --- | --- | --- | --- |
| `ClientP` | 1 | dimensionless | Vendor productivity as clients perceive it |
| `PriceIndex` | 1 | dimensionless | Price per unit of work relative to 2024 |
| `Overhead` | 302,400,000 | USD/yr | Vendor overhead, slow to adjust |
| `Viability` | 0.1776 | fraction | Margin smoothed over two years |
| `VSE` | 1 | dimensionless | Vendor share effect: 1 = normal work share |
| `CostProg` | 0 | fraction | Labour savings from the cost programme |
| `WI[Unit]` | 1 for every unit | dimensionless | Wage index relative to base wage |

**Refreshed labour stocks `[Unit, Level]`** (each cell: JUNIOR / MID / SENIOR)

| Unit | `H` employed | `O` onboarding | `V` vacancies |
| --- | --- | --- | --- |
| `IH` | 4,343 / 5,695 / 15,647 | 577 / 147 / 311 | 547 / 1,352 / 156 |
| `GCC` | 1,528 / 2,019 / 5,117 | 191 / 42 / 70 | 103 / 337 / 184 |
| `VI` | 6,792 / 8,708 / 22,529 | 918 / 230 / 451 | 491 / 1,853 / 1,190 |
| `OV` | 1,279 / 1,375 / 3,844 | 235 / 87 / 272 | 126 / 696 / 718 |
| `OL` | 888 / 1,192 / 3,179 | 109 / 25 / 31 | 104 / 230 / 35 |

| Stock | `INDIA` | `ONSHORE` |
| --- | --- | --- |
| `U[Region, Level]` | 2,510 / 90 / 301 | 724 / 43 / 1,047 |
| `R[Region, Level]` | 0 / 0 / 0 | 0 / 0 / 0 |
| `Pipeline[Region]` | 15,877 | 8,126 |
| `PercUnempShort`, `PercUnempLong` | 0.0495 | 0.0534 |
| `LeftField`, `Retired` | 0 | 0 |

**Scalars:** `Backlog` 55,056; `A` 0.05; `PerceivedP` 1; `TightPerc` 0.3; `CumInflows` 0. `PeopleCheck` must now stay at **92,546**.

## Formulas

All money is real 2026 USD per year. The Phase 3 relative-wage parameter `Wage[Unit]` keeps its name and role in switching; Phase 4's pay in dollars is a new variable, `PayRate`.

**A. Changed Phase 3 formulas**

| Name | Formula |
| --- | --- |
| `VendorBase` | `1 - InHouseShare - GCCShare` |
| `VendorShare` | `VendorBase * VSE` |
| `Lost` | `VendorBase - VendorShare` |
| `UnitShare[Unit]` | `IH`: `InHouseShare + Lost * InHouseShare / (InHouseShare + GCCShare)` · `GCC`: `GCCShare + Lost * GCCShare / (InHouseShare + GCCShare)` · `VI`, `OV`, `OL`: as in Phase 3, using the new `VendorShare` |
| `G_VI_GCC` and the other three `G` factors | `min(SwitchMax, pow((Wage[GCC] * WI[GCC]) / (Wage[VI] * WI[VI]), SwitchElasticity))`, and likewise with destination over source |

**B. Delivery, prices and revenue**

| Name | Formula |
| --- | --- |
| `Capu[Unit]` | `W[JUNIOR]*(H[Unit, JUNIOR] + OnboardProductivity*O[Unit, JUNIOR]) + W[MID]*(...) + W[SENIOR]*(...)` |
| `Delivered[Unit]` | `Completion * Capu[Unit] / EffStaff` (work each unit completes, BFY/yr) |
| `PriceTarget` | `pow(1 / ClientP, PassThrough) * (Year >= PriceShockYear ? 1 - PriceShock : 1)` |
| `Revenue` | `(Delivered[VI]*Price[VI] + Delivered[OV]*Price[OV] + Delivered[OL]*Price[OL]) * PriceIndex` |

**C. Costs and margin**

| Name | Formula |
| --- | --- |
| `PayRate[Unit, Level]` | `BaseWage[Unit] * WageMult[Level] * WI[Unit]` |
| `LabourCost[Unit]` | `(H[Unit, JUNIOR] + O[Unit, JUNIOR]) * PayRate[Unit, JUNIOR]` + the same for `MID` and `SENIOR` |
| `AICostPerUnit` | `AICost2024 * pow(1 - AICostDecline, Year - 2024) * ((Year >= AIShockStart && Year < AIShockEnd) ? AIShockMult : 1)` |
| `AICost` | `AICostPerUnit * (Delivered[VI] + Delivered[OV] + Delivered[OL]) * (1 - 1 / P_eff)` |
| `VisaCost` | `VisaHires * VisaFeePerHire + H.sum(OV, INDEX_CAN_VARY) * VisaComplianceCost` |
| `VendorLabour` | `(LabourCost[VI] + LabourCost[OV] + LabourCost[OL]) * (1 - CostProg)` |
| `VendorCost` | `VendorLabour + VisaCost + AICost + Overhead` |
| `Margin` | `(Revenue - VendorCost) / max(Revenue, 1)` |
| `ConsumerSpend` (output) | `LabourCost[IH] + LabourCost[GCC] + Revenue` |
| `VendorHead` (output) | `H.sum(VI, INDEX_CAN_VARY) + H.sum(OV, INDEX_CAN_VARY) + H.sum(OL, INDEX_CAN_VARY)` |

**D. Viability responses (R6 and B6)**

| Name | Formula |
| --- | --- |
| `Dev` | `Viability - NormalMargin` |
| `DevEff` | `Dev > Deadband ? Dev - Deadband : (Dev < -Deadband ? Dev + Deadband : 0)` |
| `VSETarget` | `min(VSEMax, max(VSEMin, 1 + ShareSens * DevEff - ExitPenalty * max(0, ExitThreshold - Viability)))` |
| `CostProgTarget` | `min(MaxSavings, CostProgramSens * max(0, -DevEff))` |
| `Restraint[Unit]` | `VI`, `OV`, `OL`: `1 - WageRestraint * max(0, -DevEff)` · `IH`, `GCC`: 1 |
| `WITarget[Unit]` | `IndiaPoolUnits`: `WagesEndogenous ? min(WageMax, max(WageMin, pow(NormalUnempRate[INDIA] / PercUnempShort[INDIA], WageElasticity) * Restraint[Unit])) : 1` · `OnshorePoolUnits`: the same with `ONSHORE` |

**E. Stock equations**

| Stock | Derivative |
| --- | --- |
| `ClientP` | `(P_eff - ClientP) / ClientPerceptionTime` |
| `PriceIndex` | `(PriceTarget - PriceIndex) / RepricingTime` |
| `Overhead` | `(OverheadRate * Revenue - Overhead) / OverheadAdjTime` |
| `Viability` | `(Margin - Viability) / ViabilityTime` |
| `VSE` | `(VSETarget - VSE) / ShareAdjTime` |
| `CostProg` | `(CostProgTarget - CostProg) / CostProgramTime` |
| `WI[Unit]` | `(WITarget - WI) / WageAdjTime` |

The two loops read straight off these formulas. R6: a lower `Viability` lowers `VSETarget`, which shrinks vendor work, `Delivered` and `Revenue`, while `Overhead` lags, so `Margin` falls further. B6: a lower `Viability` raises `CostProgTarget` and lowers vendor `WITarget`, cutting `VendorLabour`, while `Overhead` follows revenue down.

## Parameters

Phase 1-3 parameters keep their values except the calibrated rows below. Money values are rough real-2026 figures chosen to give plausible margins and cost ratios, not company data; the calibrated rows are steady-state outcomes and must be recalibrated with the prototype if any other parameter changes.

**Recalibrated Phase 3 arrays**

| Parameter | Dimensions | Phase 4 values | Meaning |
| --- | --- | --- | --- |
| `NormalUnempRate` | `[Region]` | INDIA 0.0495 · ONSHORE 0.0534 | Calibrated steady-state unemployment |
| `NormalTTF` | `[Region, Level]` | INDIA: MID 0.606, SENIOR 0.354 · ONSHORE: MID 0.631, SENIOR 0.064 (yr) | Calibrated steady-state fill times |

**New arrays**

| Parameter | Dimensions | Values | Meaning |
| --- | --- | --- | --- |
| `BaseWage` | `[Unit]` | IH 125,000 · GCC 26,000 · VI 20,000 · OV 90,000 · OL 120,000 (USD/person/yr) | Fully loaded pay of a mid-level person at wage index 1 |
| `WageMult` | `[Level]` | JUNIOR 0.6 · MID 1.0 · SENIOR 1.5 | Pay relative to mid level |
| `Price` | `[Unit]` | VI 37,070 (calibrated) · OV 150,000 · OL 150,000 (USD/BFY); IH and GCC 0 | Price clients pay per unit of work delivered, before `PriceIndex` |

**Scalars**

| Parameter | Value | Unit | Meaning |
| --- | --- | --- | --- |
| `VisaFeePerHire` | 100,000 | USD/hire | One-off fee per new visa hire (the 2025 H-1B fee for new petitions; verify current rules before relying on it) |
| `VisaComplianceCost` | 5,000 | USD/person/yr | Legal and compliance cost per visa holder |
| `AICost2024` | 8,000 | USD/BFY | AI tooling cost per unit of AI-assisted work in 2024 |
| `AICostDecline` | 0.15 | 1/yr | Yearly fall in AI cost per unit |
| `AIShockMult` | 1 | dimensionless | Multiplier on AI cost during a shock window (1 = no shock; test lever for repricing by AI labs) |
| `AIShockStart`, `AIShockEnd` | 2030, 2032 | year | When the AI cost shock applies |
| `OverheadRate` | 0.08 | fraction of revenue | Overhead the vendor carries at steady state |
| `OverheadAdjTime` | 2 | yr | How slowly overhead follows revenue |
| `PassThrough` | 1.0 | dimensionless | Share of client-perceived productivity passed into lower prices (1 = clients capture all of it over time) |
| `ClientPerceptionTime` | 1.5 | yr | How long clients take to notice vendor productivity gains |
| `RepricingTime` | 2 | yr | How long contracts take to reprice (Phase 5 replaces this with contract vintages) |
| `PriceShock` | 0 | fraction | One-off cut in prices (test lever) |
| `PriceShockYear` | 2028 | year | When the price cut starts |
| `ViabilityTime` | 2 | yr | Smoothing time from margin to viability |
| `NormalMargin` | 0.1776 (calibrated) | fraction | Steady-state margin; the reference for responses |
| `Deadband` | 0.02 | fraction | Margin deviation ignored before anyone reacts |
| `ShareSens` | 2 | dimensionless | How strongly clients move work away per point of weak viability |
| `ExitThreshold` | 0 | fraction | Viability below which clients treat the vendor as a going-concern risk |
| `ExitPenalty` | 3 | dimensionless | Extra share loss per point of viability below the threshold |
| `VSEMin`, `VSEMax` | 0.2, 1.1 | dimensionless | Floor and ceiling on the vendor share effect |
| `ShareAdjTime` | 2 | yr | How fast clients move work |
| `CostProgramSens` | 1.5 | dimensionless | Labour savings sought per point of weak viability |
| `MaxSavings` | 0.15 | fraction | Ceiling on cost-programme savings |
| `CostProgramTime` | 2 | yr | How fast savings are achieved |
| `WagesEndogenous` | 1 | switch | 1 = wages respond to unemployment and margin pressure; 0 = all wage indexes stay at 1 |
| `WageElasticity` | 0.25 | dimensionless | Wage response to regional unemployment |
| `WageRestraint` | 1 | dimensionless | Vendor wage restraint per point of weak viability |
| `WageAdjTime` | 2 | yr | How fast wages move |
| `WageMin`, `WageMax` | 0.85, 1.3 | dimensionless | Floor and ceiling on wage indexes |

## Tests and reference results

Run the seven tests in order; results should land within about 1% of these prototype values, and `PeopleCheck` must stay at 92,546 in every run. Phase 4 is done when T2 and T3 behave as shown: a moderate price cut is absorbed by B6, a severe one tips into R6.

| Test | Settings changed | What to check | Reference result |
| --- | --- | --- | --- |
| T1 Steady state | `AIOn = false` | Nothing moves | 84,135 employed, flat; 49,786 at the vendor; revenue $3.78 billion a year; margin between 17.6% and 18.1% |
| T2 Moderate price cut | `AIOn = false`, `PriceShock = 0.10` | B6 absorbs it | Margin falls to a low of 11.8% in 2031 and recovers to about 13-14%; vendor headcount 47,709 by 2040 (-4%); `VSE` 0.962; cost programme saves about 3% of labour |
| T3 Severe price cut | `AIOn = false`, `PriceShock = 0.40` | R6 takes over | Margin falls to -7.0% and viability stays negative for about 8 years; vendor headcount 28,722 by 2040 (-42%) and still falling; `VSE` 0.564; in-house rises to 39,598 and GCC to 14,356; consumer spend rises from $8.15 billion to $9.07 billion a year |
| T4 AI base case | None (`AIOn = true`) | AI with endogenous wages | Margin peaks at 36.3% around 2032 and is 31.1% in 2040; vendor headcount 30,989; `VSE` at its 1.1 ceiling; revenue $2.67 billion; vendor wage index near its 0.85 floor; 47,774 employed in total; consumer spend falls from $8.19 billion to $4.61 billion |
| T5 Constant wages | `AIOn = true`, `WagesEndogenous = 0` | The wage channel's share | Margin peaks at 28.1% and is 21.9% in 2040; vendor headcount 30,896; consumer spend $4.96 billion in 2040 |
| T6 Time step check | Time step 1/32 yr only | Results barely change | Within 0.15% of T4 (margin within 0.25 points) |
| T7 Extreme | `PriceShock = 0.6`, `VTEnd = 1`, `GCCShareEnd = 0.35`, `AIShockMult = 5`, Phase 2 extreme AI settings | Nothing breaks | No stock goes negative; `PeopleCheck` holds |

&#91;embedded content: prototype simulation of these exact equations (phase4\_sim.py and scan4.py), AI off, Euler, time step 1/16 yr\]

**Reading the results**

- **There is a tipping point between a 35% and a 40% price cut.** Below it, cost programmes and wage restraint pull viability back before clients move much work (B6 dominates). Above it, viability goes negative, the exit penalty switches on and lost work outruns the cost cuts (R6 dominates). The spec's collapse test (viability below zero for 3+ years and headcount falling over 15% a year) is met on the viability part in T3, but headcount falls about 7% a year, so in this phase the spiral is a steady slide rather than a sudden collapse. Phase 5 contract vintages and Phase 6 credibility effects can make it sharper.
- **When vendors shrink, consumers pay more, not less.** In T3 the work moves in-house at onshore wages, so total consumer spend rises 11%. This is the cost argument that keeps vendors alive.
- **AI raises vendor margins for a decade (T4, T5).** Productivity arrives faster than clients reprice it, and in T4 high unemployment also lowers wages. In reality competition would erode this; Phase 5's contract choice and sourcing competition is where that pressure comes from, so treat T4's margins as an upper bound.
