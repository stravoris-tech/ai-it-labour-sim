# Phase 7 build guide

Phase 7 turns the full model into an evidence-based tool. It calibrates the model to what actually happened in 2024-2026, runs the scenarios the spec asks for, measures how sensitive the answers are, and answers Q1-Q3. Calibration needed a few structural changes, described first: underlying growth in IT demand, AI measured relative to its 2024 level, and five new parameters for effects the 2024-2026 data showed the Phase 6b model was missing.

Phase 7 is done when the model reproduces the 2024-2026 targets below within a few per cent, the validation indicators (not used in the fit) are in range, the AI-off run grows smoothly at the demand growth rate, and the scenario, sensitivity and Monte Carlo results below are reproduced. Every number here comes from the prototype: `phase7_sim.py` (model), `calibrate7_ss.py` (2024 starting state), `calibrate7.py` (fit) and `phase7_runs.py` (tests, scenarios, sensitivity).

## What changes from Phase 6b

**1. Underlying demand growth.** Until now, demand without AI was flat. Real IT services spend grew 3.8-5.6% a year in 2024-2026 (about 3% after inflation), so a flat baseline makes every AI effect look like a job loss. Add a growth multiplier `G` and apply it to three things that grow together with the economy:

- `G = pow(1 + DemandGrowth, min(time, LateYear) - 2024) * pow(1 + DemandGrowthLate, max(0, time - LateYear))`, with `DemandGrowth = 0.03`, `LateYear = 2026.5` and `DemandGrowthLate` equal to `DemandGrowth` unless a scenario changes it (code: a value of -1 means "same as DemandGrowth").
- Base demand: `base[s] = BaseDemand * G * SectorShare[s] * (1 + step)`.
- Budgets: `BudgetGrowth = G * pow(1 + ITBudgetGrowth, time - 2024) * (1 - shock)`.
- Graduate supply: `Enrol[r] = BaseEnrolment[r] * G * EnrolEffect[r]`.

The business workforce (`LOB0`), the application portfolio and the visa cap do not grow: the H-1B cap is fixed in law, so growth slowly tightens it.

**2. AI measured from its 2024 level.** In 2024 AI was already in use (about a third of delivery work and 30% of firms scaling it), so the 2024 starting state must contain it. Set `A0 = 0.35`, `AC0 = 0.30` and `Att0 = 0.01`, and measure every AI effect relative to 2024, so that 2024 is still a steady state:

- `Pew[e][w] = (A[e] * PAI[w] + 1 - A[e]) / (A0 * PAI0[w] + 1 - A0)`, where `PAI0[w]` is `PAI[w]` evaluated at `a2024[w]`.
- `ShareJ[e] = Share0_J * max(0.05, 1 - JuniorCut * max(0, A[e] - A0))`.
- `AIexp[s] = max(0, AC[s] * LOBAuto - AC0 * aL_2024)`.
- `AIBuild[s] = (BuildRate * (AdoptC[s] - AdoptC0) + RunRate * (AC[s] - AC0)) * Jev * Approval`, with `AdoptC0 = (pC + qC * AC0) * (1 - AC0)`, the adoption rate already under way in 2024. AI build demand can now fall below its 2024 level as adoption saturates, so floor demand per work type: `Demand[s][w] = base[s] * max(0, dm[w] + AIBuild[s] * BuildMix[w])`.

**3. Five new parameters.** The fit showed effects the Phase 6b structure could not reproduce:

- **Verification overhead that falls over time.** Replace the per-type `v[w]` with one parameter: `VerifNow = Verif * pow(1 - VerifDecline, time - 2024)` and `PAI[w] = 1 / ((1 - a[w]) + a[w] / s[w] + a[w] * VerifNow)`. The 2024-2026 data imply a large overhead (people checking AI output); `VerifDecline = 0.05` assumes it halves over about 14 years as models become more reliable.
- **Clients price in the productivity trend** (`PriceHorizon`). Clients now ask for 25-30% lower prices at renewal, ahead of the gains. Compute `PU[v]` first, then `Anchor[v] = pow(1 / (ClientP[v] * (1 + PriceHorizon * PU[v])), PassThrough)`. When productivity stops rising, `PU` goes to zero and prices return to following measured productivity.
- **GCC momentum** (`GCCMomentum`). The GCC build-out was decided before 2024 and is still being executed. At the start of the run, tilt the perceived shares: `SrcPerc[s][e] = softmax(ln(SrcPerc0[s][e]) + GCCMomentum * (e == GCC))`.
- **A GCC wave that partly fades.** `GCCAppeal` ramps from 0 in 2024 to `GCCAppealEnd` in 2030 (`GCCRampStart = 2024`, `GCCRampEnd = 2030`), then ramps to `GCCAppealEnd * GCCAppealKeep` by `GCCFadeEnd = 2035`. Base `GCCAppealKeep = 0.5`: half of the post-2030 pull stays.
- **AI enablement cost** (`AICost2024`, now fitted). Vendors spend on AI tools, platforms and retraining. The fitted value is the cost per unit of work AI saves.

**A calibration-only switch, `Burn`.** During the growth-path burn-in (Step 1), the visa cap and the IT part of seats must grow with `G` so that the model stays proportional: `VisaCap = BaseVisaCap * (1 - VisaTight) * (Burn ? G : 1)` and `Seats[s] = LOB[s] + ConsIT * CS[s] / (Burn ? G : 1)`. `Burn = 0` in every normal run.

## Step 1: the 2024 starting state on a growth path

If a growing model starts from a no-growth steady state, it first dips (headcount 3% below trend within two years) and then cycles for a decade. The fix is to start on the balanced growth path: the state the AI-off model would be in after growing at 3% for a long time, scaled back to 2024 size. `calibrate7_ss.py` does this in two phases.

- **Phase A: no growth, as in Phase 6b.** With `DemandGrowth = 0`, run ten 40-year burn-ins (sourcing frozen, finance feedback off) and adjust enrolment to hit unemployment of 5.0% in India and 5.5% onshore. This sets the normal times to fill: India mid 0.551 and senior 0.286 years, onshore mid 0.526 and senior 0.079 years.
- **Phase B: growth on.** Set `Burn = 1` and `EnrolSensitivity = 0`, run ten 100-year burn-ins, and after each one divide every extensive stock (staff, onboarding, vacancies, the two unemployment pools, backlog, student pipeline, left-field, retired) by `G(100)` to return to 2024 size. Between burn-ins, take a secant step on log enrolment toward the unemployment targets, then run three settle rounds that set the normal unemployment rates. Keep the normal times to fill from Phase A: on a growth path, times to fill sit above normal so that external entry fills the senior gap. Resetting them each round caused a runaway shortage.
- **Then, as in Phase 6b:** price multipliers for the target margins, sourcing and contract-type constants, cost bases, seats and budgets. Set vendor overhead to its growth-path value, `OverheadRate * Revenue / (1 + ln(1 + DemandGrowth) * OverheadAdjTime)`, because a first-order lag on a growing revenue runs behind it.

| Calibrated value | India | Onshore |
| --- | --- | --- |
| `BaseEnrolment` (2024 intake, people a year) | 3,750 | 3,830 |
| `NormalUnempRate` | 0.0502 | 0.0553 |

| Calibrated value | OIT | GSI | BQ |
| --- | --- | --- | --- |
| `PriceMult` | 1.0154 | 1.0360 | 1.0468 |
| `NormalMargin` | 0.1844 | 0.1556 | 0.1256 |
| `LabourCostPB0` (USD per BFY) | 43,680 | 82,100 | 149,090 |

Also: `LabourCostPB0` IH 134,270 and GCC 27,650; `CostRef = 131,000`; `CostPerBFY0 = 104,290`. In 2024 the model holds 82,654 IT staff: consumer onshore 25,563, GCC 8,493, vendor onshore 20,798 and vendor India 27,799.

**In AnyLogic,** a 100-year burn-in with rescaling is awkward to build inside the model. Instead, import the starting state: `phase7_init.csv` lists every stock's 2024 value by index. Load it into the stocks' initial values (for example from a database table or an Excel file read in `On startup`), and set the calibrated parameters from the tables above. With AI off, the model should then grow smoothly at 3% a year: total headcount divided by `G` stays within 1.2% of its 2024 value through 2040 (test T1).

## Step 2: fitting 2024-2026 history

Starting from the 2024 state, `calibrate7.py` fits eleven parameters so the model reproduces eleven observations by least squares. Each residual is relative (model minus target, over target); the two point-change targets are scaled per 10 points. `DemandGrowth` is set from data, not fitted, because headcount alone cannot separate faster demand from slower productivity.

| Target | Year | Observed | Model | Source |
| --- | --- | --- | --- | --- |
| AI share of delivery work | 2025 | 0.50 | 0.487 | Stack Overflow 2025: 84% use or plan to use AI, 51% of professionals daily (2024: 62% using) |
| AI share of delivery work | 2026 | 0.62 | 0.630 | DORA 2025: 90% of technologists use AI at work |
| Indian IT book price (2024 = 1) | 2026 | 0.96 | 0.964 | Deal deflation of 2-5% a year (HCL 2-3%, Kotak 3.5%), about -4% across the whole book |
| Indian IT headcount (2024 = 1) | 2026 | 1.003 | 0.981 | Top-5 Indian IT: 1,525,776 (Mar 2024) to 1,530,073 (Mar 2026) |
| Indian IT margin change (pts) | 2026 | 0 | +0.02 | TCS 24.6% to 25.0%, Infosys about 21%, HCL 18.2% to 17.2% |
| GCC headcount (2024 = 1) | 2026 | 1.24 | 1.230 | NASSCOM/Zinnov: 1.9M (FY24) to 2.36M (FY26) |
| GCC headcount (2024 = 1) | 2030 | 1.70 | 1.694 | Outlook, half weight: GCC workforce near 3.2-3.5M by 2030 (NASSCOM/Zinnov, Nov 2025) |
| Junior hiring (2024 = 1) | 2026 | 0.65 | 0.660 | TCS fresher intake 42-44k to about 25k offers; US new-grad hiring sharply down |
| Consumer AI scaling (share of firms) | 2026 | 0.42 | 0.420 | McKinsey State of AI: scaling 33% (2024) to 40%+ |
| AI seat attach | 2026 | 0.065 | 0.065 | Microsoft 365 Copilot 30M+ paid seats on about 450M commercial seats |
| Onshore unemployment change (pts) | 2026 | +1.45 | +1.45 | US tech unemployment 2.0% (Dec 2024) to 3.3-3.6% (2026) |

| Fitted parameter | Value | Range searched | What it pins down |
| --- | --- | --- | --- |
| `p`, `q` (delivery adoption) | 0.0437, 0.4948 | 0.001-0.3, 0.05-2 | AI share of work in 2025 and 2026 |
| `Verif` | 0.4323 | 0-1.5 | Indian IT headcount: realised productivity |
| `PriceHorizon` (years) | 7.88 | 0-8 | Book price |
| `AICost2024` (USD per BFY saved) | 34,797 | 2,000-60,000 | Flat margins |
| `GCCMomentum`, `GCCAppealEnd` | 1.839, 3.087 | 0-3, 0-6 | GCC headcount 2026 and 2030 |
| `JuniorCut` | 0.5833 | 0-1.4 | Junior hiring |
| `qC` (consumer adoption; `pC` fixed at 0.005) | 0.2364 | 0.01-1 | Consumer AI scaling |
| `pAtt` | 0.0123 | 0.001-0.5 | AI seat attach |
| `SeekerExitRate` | 0.50 | 0.05-1 | Onshore unemployment |
| `DemandGrowth` (set, not fitted) | 0.03 | - | Gartner IT services +3.8% to +5.6% nominal, about 3% real |

&#91;embedded content: prototype base run after the fit (calibrate7.py, phase7\_sim.py), 2024-2030\]

The fit leaves one notable gap: Indian IT headcount falls 1.9% by 2026 in the model against +0.3% observed. Closing it would need a smaller productivity gain, which would then miss the price and margin targets. The fitted values also carry a message of their own. The 2024-2026 data are consistent with realised productivity of about 6% over two years, much less than headline claims, because a large verification overhead (`Verif` 0.43) absorbs most of the raw speed-up. Clients are pricing several years of future gains into today's deals (`PriceHorizon` near 8 years, at the top of its range), and vendors are holding margins by spending heavily on AI enablement.

## Validation against data not used in the fit

| Indicator, 2026 vs 2024 | Model | Observed | Verdict |
| --- | --- | --- | --- |
| Indian IT revenue, real | 1.006 | 1.00-1.02 (constant-currency growth about 4% in FY25 and 1% in FY26, less US inflation) | In range |
| Business workforce (`LOB`) | 0.990 | 0.98-0.99 (AI-attributed layoffs are small next to the workforce) | In range |
| Onshore IT headcount | 0.999 | 1.00-1.02 (US OEWS computer and mathematical occupations +1.3% in 2024-25) | Low edge of range |
| Vendor India headcount | 0.981 | About 1.02 (NASSCOM 5.43M to 5.95M, less GCCs 1.9M to 2.36M) | About 4 points low |
| Realised productivity `P_all` | 1.061 | Not measured directly | Implied, see Step 2 |
| India unemployment change | +0.4 pts | No reliable series | Not testable |

The model runs a little cold on India: it has vendor India shrinking slightly where the data show slight growth. This is the same gap as the Indian IT headcount target. Read the India vendor results below as slightly pessimistic for the first years.

## AnyLogic experiments

Build four experiments on top of the Phase 6b model, after making the changes above and loading the 2024 state.

**1. Calibration experiment (reproduces Step 2).** Use AnyLogic's Calibration experiment (OptQuest).

- Stop time: 2030.5 (6.5 model years).
- Parameters: the eleven fitted parameters with the ranges in the Step 2 table, starting at the fitted values. Fix `DemandGrowth = 0.03`. Make `AdoptC0` a dependent parameter with default value `(pC + qC * AC0) * (1 - AC0)`, so it follows `qC`.
- Recording: in `Main`, add one-shot events at 2025.0, 2025.75, 2026.0, 2026.25 and 2030.0 that copy the measured values into plain variables: the work-weighted adoption `A_mean = sum(A[e] * CompE[e]) / sum(CompE[e])`, the sector-weighted `AC_mean`, `Att`, OIT book price `AvgIdx[OIT]`, headcount ratios for OIT and GCC, OIT margin, onshore unemployment, and junior hires (average the 2025.75, 2026.0 and 2026.25 values).
- Objective (minimise), with each term a relative miss and weights squared:

```
sq((A25 - 0.50) / 0.50) + sq((A26 - 0.62) / 0.62)
+ sq((Price26 - 0.96) / 0.96) + sq((HeadOIT26 - 1.003) / 1.003)
+ sq(MarginChange26 / 0.10) + sq((GCC26 - 1.24) / 1.24)
+ 0.25 * sq((GCC30 - 1.70) / 1.70) + sq((Junior26 - 0.65) / 0.65)
+ sq((AC26 - 0.42) / 0.42) + 0.25 * sq((Att26 - 0.065) / 0.065)
+ sq((UnempONChange26 - 0.0145) / 0.10)
```

OptQuest is not a least-squares solver, so expect slightly different values. Accept the result when every target is within 2% of the Model column in Step 2 (0.5 points for the two change targets).

**2. Scenarios.** Use a Parameter Variation experiment in freeform mode, with one run per scenario in the Scenarios section (fourteen runs, stop time 2040). Simplest: add an integer parameter `ScenarioId` and set the scenario's parameters in `Main`'s `On startup`. Save the annual values of the four Q1 lines, total headcount, unemployment, vendor margins and viability, and the contract mix to datasets after each run.

**3. Sensitivity (tornado).** Use a second freeform Parameter Variation with 28 runs: each parameter in the Sensitivity section at its low and its high value, everything else at base. Record 2040 values relative to the base run.

**4. Monte Carlo.** Use a Parameter Variation with 300 iterations and a fixed seed. In each iteration, draw every sensitivity parameter independently with `uniform(low, high)`. Collect each output's 2024-2040 path, divided by its 2024 value, into a `Histogram2DData` object, and read off the 10th, 50th and 90th percentiles each year. AnyLogic's random streams differ from the prototype's, so expect the bands to match within about 0.02.

In every experiment, apply the GCC momentum tilt on startup, after the 2024 state is loaded, so that each run starts from the same perceived shares.

## Scenarios

Each scenario changes only the parameters listed; everything else stays at the fitted base. Scenario levers act from the year shown, so 2024-2026 history is unchanged in every run.

&#91;embedded content: prototype scenario runs (phase7\_runs.py), 2040 vs 2024\]

| Scenario | Settings | Unemployment 2040, India / onshore | Indian IT margin 2040 | Q3 test, OIT / GSI / BQ |
| --- | --- | --- | --- | --- |
| Base | `g = 0.10`, `VerifDecline = 0.05`, demand +3% a year, EU AI Act timing (`RegScenario = 1`), half the GCC pull kept | 6.8% / 7.6% | 15.9% | equilibrium / equilibrium / adjusting 3.3% a yr |
| Slow AI | `g = 0.05`, `VerifDecline = 0` | 5.8% / 6.9% | 16.6% | adjusting 2.1% / 3.3% / 3.1% |
| Fast AI | `g = 0.20`, `VerifDecline = 0.10` | 7.3% / 7.8% | 15.4% | equilibrium / adjusting 2.3% / 2.8% |
| Strict regulation | `RegScenario = 1.5` | 6.8% / 7.5% | 15.8% | equilibrium / equilibrium / adjusting 3.5% |
| Light regulation | `RegScenario = 0.5` | 6.9% / 7.6% | 15.9% | equilibrium / equilibrium / adjusting 3.2% |
| Compute shock | AI costs x3 from 2027 to mid-2029 (`AIShockMult = 3`, 2027.0-2029.5) | 6.7% / 7.3% | 14.9% | equilibrium / adjusting 2.6% / 3.0% |
| Visa crackdown | `VTEnd = 0.8`, ramp Sep 2025 to Sep 2027 | 6.9% / 7.5% | 16.5% | adjusting 3.4% / equilibrium / adjusting 3.7% |
| Visa relaxation | `VTEnd = 0.1`, ramp 2027-2028 | 6.9% / 7.5% | 15.2% | adjusting 2.0% / equilibrium / adjusting 3.4% |
| Downturn | Budgets -15% in 2027-2028 (`BudgetShock = 0.15`) | 6.9% / 7.6% | 15.8% | equilibrium / equilibrium / adjusting 3.0% |
| Jevons rebound | `JevonsEps = 0.5` | 6.6% / 7.3% | 15.6% | equilibrium / equilibrium / adjusting 3.5% |
| Demand stalls | `DemandGrowthLate = 0` from mid-2026 | 7.2% / 8.0% | 16.3% | adjusting 4.3% / 2.6% / equilibrium |
| Demand boom | `DemandGrowthLate = 0.05` from mid-2026 | 6.6% / 7.3% | 15.6% | equilibrium / adjusting 3.5% / 4.9% |
| GCC wave persists | `GCCAppealKeep = 1` | 6.3% / 8.2% | 14.4% | adjusting 8.1% / 4.5% / equilibrium |
| GCC wave fades | `GCCAppealKeep = 0` | 7.1% / 7.3% | 17.2% | adjusting 2.9% / 3.6% / 3.7% |

**Reading the scenarios**

- **Two levers set the total:** how fast AI improves (with how fast verification overhead falls) and how fast underlying demand grows. Together they span 0.66 to 1.27 times the 2024 job count in 2040. Dropping demand growth after 2026 from 3% to zero costs 31% of 2040 jobs against base; halving AI's improvement rate adds 32% and doubling it removes 19%.
- **The GCC wave decides where the jobs are,** not how many. Keeping or dropping the post-2030 GCC pull leaves the total unchanged but moves vendor India between 0.36 and 0.60 and GCCs between 2.3 and 4.3 times their 2024 size.
- **Shocks shift timing more than the end state.** Regulation, a compute shock, a downturn and visa changes all move the 2040 totals by 2% or less. A visa crackdown mainly moves onsite vendor work to GCCs and offshore.
- **Jevons is the only lever that adds jobs at a given AI speed:** at elasticity 0.5, cheaper delivery creates enough new work to put 2040 jobs 7% above 2024.
- **No scenario produces a collapse.** Vendor viability never stays negative for three years. The vendor archetypes end 2040 either at a smaller equilibrium or still changing by 2-8% a year ("adjusting" counts growth as well as decline: boutiques are mostly still growing).

## Sensitivity

Fourteen uncertain parameters, each moved on its own to a low and a high value with everything else at base.

&#91;embedded content: prototype one-at-a-time runs (phase7\_runs.py), 2040 vs base\]

- **Total jobs** respond most to demand growth after 2026, to how fast verification overhead falls, to Jevons and to AI's improvement rate. Halving or doubling the junior cut, the maximum business automation and the 2024 verification level each move the total by 4% or less.
- **Vendor India** responds as strongly to the GCC wave (+23% / -26%) and to how price-driven sourcing is (-8% / +6%) as to AI speed. The contract parameters (T&M brake, client price horizon) barely move headcount: they change vendor margins and contract mix, not jobs.
- **Regulation strength** moves the total by under 2%: it delays consumer adoption but adds governance work.

**Monte Carlo.** 300 runs, with all fourteen parameters drawn independently and uniformly from their ranges.

&#91;embedded content: prototype Monte Carlo, 300 runs, seed 7 (phase7\_runs.py)\]

The median total (1.03 in 2040) sits above the base run (0.96) because the ranges are not centred on base: Jevons runs from 0 to 0.5 against a base of 0, and verification decline from 0 to 0.10 around 0.05 has an asymmetric effect. On Q3, none of the 300 runs produced a collapse. Indian IT reached equilibrium by 2040 in 31% of runs and was still adjusting in 69%; global SIs 39% / 61%; boutiques 21% / 79%.

## Answers to Q1-Q3

These are the calibrated model's answers. The base run is one path; the 10th-90th percentile range from the Monte Carlo shows how far the answer moves when the uncertain parameters move. Model units are converted to people only for India, where NASSCOM gives a 2024 base (vendor India about 3.53M, GCCs 1.9M). The conversion assumes the model's proportions hold at national scale, so treat those numbers as indicative.

**Q1: How many IT jobs, and where?**

| Line | 2024 (model units) | Base 2035 | Base 2040 | 2040, 10th-90th percentile | Indicative people, 2024 to 2040 (base) |
| --- | --- | --- | --- | --- | --- |
| Consumer IT, onshore | 25,563 | 0.89 | 0.91 | 0.78-1.15 | - |
| Consumer IT, India (GCCs) | 8,493 | 3.08 | 3.10 | 2.28-4.66 | 1.9M to 5.9M (range 4.3-8.9M) |
| Vendor IT, onshore | 20,798 | 0.76 | 0.79 | 0.62-1.00 | - |
| Vendor IT, India | 27,799 | 0.56 | 0.49 | 0.39-0.68 | 3.53M to 1.73M (range 1.36-2.41M) |
| All IT jobs | 82,654 | 0.97 | 0.96 | 0.84-1.24 | - |

- **In total, AI roughly cancels growth.** Demand grows 47% by 2040 and realised productivity rises 47%, so total IT jobs end close to their 2024 level in the base run (0.96). The range runs from a 16% fall to a 24% rise, almost all of it from demand growth and how fast AI improves.
- **By region, India gains and onshore loses.** Onshore IT jobs (consumer and vendor) fall to 0.86 of 2024 by 2040. India rises to 1.10, but only because GCCs triple while vendor India halves: the base run moves about 1.8M vendor jobs out of Indian IT firms and adds about 4M GCC jobs.
- **Consumer vs vendor:** consumers (in-house plus GCCs) hold 62% of IT work by 2040, up from 41%; vendors hold 38%, down from 59%.
- **Entry-level work shrinks most.** Junior hiring settles at about 60% of its 2024 rate. Unemployment peaks in 2028 at 7.1% in India and 8.0% onshore (from 5.0% and 5.5%), then settles near 6.8% and 7.6%.

**Q2: How does the contract mix change?**

| Effort-billed share of book (T&M plus staff augmentation) | 2024 | 2030 | 2040 base | 2040 fast AI |
| --- | --- | --- | --- | --- |
| Indian IT (OIT) | 40% | 42% | 31% | 25% |
| Global SIs | 27% | 32% | 22% | 17% |
| Boutiques | 62% | 72% | 64% | 56% |

The mix swings twice. Until about 2031, while productivity and prices are moving fast, clients avoid locking in long fixed prices, and new business tilts toward short effort-billed work. Once gains slow, fixed price and managed services take back share: by 2040 Indian IT's book is 38% fixed price and 28% managed services, against 35% and 22% in 2024. Outcome-based contracts stay at 3-5% of every book in every scenario. Faster AI pushes harder toward fixed price and managed services.

**Q3: Collapse or a new equilibrium?**

A new, smaller equilibrium, not a collapse. No scenario and none of the 300 Monte Carlo runs meets the collapse test (viability negative for three years and headcount falling more than 15% a year). In the base run:

- **Indian IT** shrinks to 42% of its 2024 headcount and 38% of its real revenue by 2040, and is stable by 2038-2040. Its share of all IT work falls from 32% to 14%, mostly to GCCs. Margins dip to 12% around 2035 and recover to 16%.
- **Global SIs** settle at 64% of their 2024 headcount and 62% of revenue.
- **Boutiques** grow: 1.45 times their 2024 headcount, still growing 3% a year in 2040.

In the model, the main threat to Indian IT is not AI efficiency itself but the GCC wave: clients moving work into their own captive centres. The model takes the size of that wave from the 2024-2026 data and the 2030 outlook rather than explaining it, and its strength after 2030 is the largest single uncertainty for vendor India. The "GCC wave persists" scenario cuts vendor India to 0.36 and leaves Indian IT still shrinking 8% a year in 2040. The "GCC wave fades" scenario keeps it at 0.60.

## Tests

| Test | Setting | Result |
| --- | --- | --- |
| T1 AI-off growth path | AI off, 2024-2040 | Headcount divided by `G` within 1.2% of 2024 throughout; no negative stocks |
| T2 Conservation | Base, step 1/16 | People: residual 6e-11 after 16 years (stocks change exactly by graduates plus external entrants); work: shares sum to 1 within 1e-15; no negative stocks |
| T3 Time step | Base, step 1/32 vs 1/16 | Every Q1 line within 0.3% in 2040 |
| T4 Extreme | `g = 0.5`, `VerifDecline = 0.3`, `JevonsEps = 1`, AI costs x5, budgets -60%, `RegScenario = 2.5`, visas closed, `GCCAppealKeep = 2`, Indian IT price cut 50%, demand -3% a year after 2026, `aL_max = 0.9` | No negative stocks; 2040 headcount 0.43 of 2024 |

## Limitations

- **The GCC wave is an input, not a result.** Its size comes from two years of data and one outlook. It is the biggest driver of vendor India after 2030; a later phase could make GCC set-up decisions endogenous (scale, cost gap, talent availability).
- **Two years of history pin down eleven parameters.** The fit is close to exactly determined, so matching the targets is not itself evidence. The validation indicators are the real test, and only four of them are testable. `PriceHorizon` ended at the top of its range.
- **The model runs slightly cold on India in 2024-2026:** Indian IT headcount -1.9% against +0.3% observed, vendor India -1.9% against about +2%.
- **Verification decline (5% a year) is an assumption** with no data behind it yet, and it is the second-largest driver of total jobs. Watch evidence on review effort per AI-generated change as it appears.
- **Everything is in real terms.** Revenue comparisons strip out US inflation; wages and prices have no inflation.
- **Model units are proportions, not national counts.** India is converted to people as an indication; onshore lines are reported only as ratios.
