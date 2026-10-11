# AI and the IT Job Market - SD Model Spec

Oct 9, 2026 · @Krishnaswamy Bharati Gandhi Mohan

## Purpose and model questions

The model simulates how AI adoption by technology consumers and IT vendors reshapes IT employment, contract structures and vendor viability from 2026 to 2040, with India and onshore (North America and Europe) as separate labour markets.

| Question | Primary outputs | Structures required |
| --- | --- | --- |
| Q1. What happens to IT headcount by 2035 and 2040? | Consumer in-house IT headcount and vendor headcount as separate lines, each split by region | Demand backlog, AI productivity, workforce aging chain, labour market |
| Q2. Does the contract mix skew toward specific types to balance consumer and vendor pressures? | Share of active contract value by contract type, by vendor archetype | Contract stocks, attractiveness-based shares, renewal repricing |
| Q3. Do vendors collapse, or does the system reach a new equilibrium by 2040? | Revenue, margin and capacity by vendor archetype; equilibrium test result | Vendor financials, viability index, capacity exit, sourcing choice between archetypes |

Secondary outputs: consumer line-of-business (LOB) headcount, IT unemployment and exits from the field by region, and spend flowing to hyperscalers, software vendors and AI providers, split into per-seat and consumption spend.

## Modeling conventions

All work is measured in baseline FTE-years, so AI shows up as a productivity multiplier rather than a change in units.

| Item | Choice |
| --- | --- |
| Tool | AnyLogic desktop, System Dynamics palette (stocks, flows, dynamic variables, parameters, table functions), dimensions for arrays |
| Horizon | 2024 to 2040; 2024-2026 is the calibration window, 2026-2040 the projection, with checkpoints at 2030 and 2035 |
| Time unit | Year |
| Time step (DT) | 1/16 year; Euler integration, spot-checked against RK4 |
| Work unit | Baseline FTE-year (BFY): one person-year of effort at pre-AI productivity |
| Headcount unit | Persons |
| Money | USD, real 2026 values; exchange rate held constant |
| Rates | Per year (e.g. persons/year, BFY/year, USD/year) |
| Unit checking | On in AnyLogic for every stock, flow and parameter |
| Naming | Stocks as nouns (`ITBacklog`), flows as verbs or rates (`HiringRate`), parameters with a clear suffix (`AvgContractDurationYrs`) |

## Integrity rules

Eight rules keep the model conserved and bounded; every module must satisfy them, and they were added after the design review.

1. **Conservation of people.** Every person sits in exactly one stock: EntrantPipeline, ActiveSeekers, RecoveringIT, Onboarding, Headcount, Founders (extension) or LeftField. The visa workforce and GCC staff are subsets of Headcount, never separate pools. Displaced LOB staff leave the model boundary rather than entering the IT labour pool.
2. **No negative stocks.** Every outflow is capped by stock / minimum residence time (first-order control). Hires are capped by both vacancies and seekers; layoffs and completions by the stock they drain.
3. **One budget.** `ConsumerITBudget[Sector](t)` caps total consumer IT spend: in-house labour, services contracts, seats, credits and cloud. Base, AI build and Jevons demand are only approved while committed spend is below the budget. R1 adds reinvested savings at a fraction below 1.
4. **Unmet demand is abandoned.** Work waiting longer than a tolerance time is cancelled, so a talent shortage raises abandonment instead of building an infinite backlog.
5. **One representation of work.** Demand enters `ITBacklog`, is allocated by sourcing share into `WorkQueue[Sector][Employer]`, and is completed by that employer's capacity. Contract value is a coflow of contracted work (value = work × price per BFY), not a second count of the same demand.
6. **Saturating effects.** Every effect function (Jevons elasticity, AI cost effect on adoption, enrolment response, wage effect on switching, regulatory drag) is a bounded table function. Adoption rates are clamped so fractions stay within 0-1 at DT 1/16.
7. **Floors and ceilings.** Contract duration ≥ 0.25 years; expected AI discount ≤ a ceiling; new-bid price ≥ the vendor's delivery cost; automatable share ≥ 0.
8. **One mechanism per effect.** Insourcing (B3) and GCC capture (R7) act only through value terms in the sourcing logit, never as separate flows.

Units: `AICostPerUnit` is USD per BFY of AI-performed work; agent work is in BFY; wages are USD per person-year.

## Scope and boundaries

The model represents archetypes, not individual companies: TCS, Infosys and Wipro sit inside "Offshore Indian IT", and hyperscalers and AI providers are aggregate recipients of spend.

| Dimension | Elements | Applies to |
| --- | --- | --- |
| `Region` | India, Onshore (North America and Europe) | Labour pools, headcount, wages, entrants |
| `Sector` | Financial, Legal, Medical, Government, Manufacturing, Logistics, Retail | Demand, contracts, consumer AI adoption, LOB headcount |
| `WorkType` | App development, Data migration and transformation, Security, Governance, Support and operations, End-user services | Backlog, AI automatable share |
| `Employer` | Consumer in-house, GCC (consumer-owned captive centre in India), Offshore Indian IT, Global SI, Boutique | Headcount, vendor AI adoption, financials |
| `ContractType` | Fixed price, T&M, Support, Staff augmentation, Licensing, Outcome-based / managed (proposed) | Contract stocks and shares |
| `Level` | Junior (0-3 yrs), Mid (3-8 yrs), Senior (8+ yrs) | Headcount, labour pool |
| Vendor (subset of Employer) | Offshore Indian IT, Global SI, Boutique | Contract stocks, vendor finance |
| Provider | Hyperscalers (cloud), Software platforms (seats and credits), AI model providers (direct tokens) | Spend and provider revenue |

`Employer` and `Region` connect through a delivery-mix parameter, `OffshoreShare[Employer]`: consumer in-house teams are mostly onshore, GCCs entirely India, offshore Indian IT mostly India plus an onsite visa workforce, global SIs mixed.

Dimensions are crossed only where the question needs it, to avoid stocks with 1,000+ elements. For example, headcount is `[Employer][Region][Level]` but not by sector.

**In scope:** AI-driven productivity, adoption diffusion, demand creation from AI, talent pipeline and exits, contract mix, vendor finances, spend to hyperscalers and AI providers, visa policy (H-1B, PERM) as a scenario lever, GCC captive sourcing, sourcing choice between archetypes, AI cost curve, sector regulatory drag, macro budget scenarios.

**Out of scope for v1:** firm-level competition (including OpenAI vs Anthropic), recessions and macro shocks, exchange-rate movement, wage inflation other than shortage-driven, a separate EU region, Middle East conflicts and other geopolitical events (these enter only as a compute cost shock), AI providers selling services directly, recruiting firms as an actor (represented only by agency share and fee).

## Module map

AI capability feeds two adoption paths: consumer AI creates new IT demand, while vendor AI raises productivity and shifts vendor margins.

&#91;embedded content: module map · 9 modules shown, sourcing folded into contracts\]

Workforce (highlighted) carries the Q1 output. Vendor finance feeds back into contract mix through vendor margins (loop B2), and the labour market exchanges people with the workforce in both directions. US visa policy limits vendors' onsite workforce and raises their delivery cost.

## Stocks, flows and key auxiliaries

Ten modules hold about 24 stock families; every stock below is a candidate, to be confirmed as each build phase lands.

| Module | Stocks (dimensions, unit) | Inflows | Outflows | Key auxiliaries |
| --- | --- | --- | --- | --- |
| 1. IT work demand | `ITBacklog[Sector][WorkType]` (BFY) | Base demand, AI build demand, Jevons demand, AI governance demand | Allocation to work queues, abandonment | Required capacity, cost per unit of work |
| 1b. Applications and seats | AppPortfolio\[Sector\] (applications) | New apps built | Retirements (accelerated by agent replacement) | Seats\[Sector\], new-app demand, per-seat spend, end-user services demand |
| 1c. Work queues | WorkQueue\[Sector\]\[Employer\] (BFY) | Approved work allocated by sourcing share | Completion (capped by employer capacity), abandonment | Employer capacity; contract value as coflow (work × price per BFY) |
| 2. Contracts | `LegacyContractValue, NewContractValue [Sector][ContractType]`\[Vendor\] (USD) | Signings | Expiry (value / vintage duration) | New-contract share (logit), price index, expected AI discount, new-contract duration |
| 3. Workforce | `Headcount[Employer][Region][Level]` (persons) | Onboarding completions, promotion in, job switches in | Promotion out, layoffs, retirement, job switches out, exits | Desired headcount, hiring gap, bench |
| 3b. Hiring pipeline | Vacancies, Onboarding \[Employer\]\[Region\]\[Level\] (persons) | Openings; hires (matching function) | Hires; onboarding completion; cancellations | Time-to-fill, matching efficiency, agency share and fee, notice period, job-switch rate |
| 4. Labour market | `EntrantPipeline[Region]`, `RecoveringIT, ActiveSeekers [Region][Level]`, `LeftField[Region]` (persons) | Enrolment, graduation to seekers, layoffs | Hires, recovery to seekers, exits, retirement | Job prospects (smoothed unemployment rate), skill decay, `Wage[Employer][Region][Level]` |
| 5. Consumer AI | `ConsumerAIAdoption[Sector]` (fraction), `LOBHeadcount[Sector]` (persons) | Adoption (Bass), LOB hiring | LOB displacement | LOB automation rate, operating savings, AI budget |
| 6. Delivery AI (all employers) | `DeliveryAIAdoption[Employer]` (fraction) | Adoption (Bass, modulated by fixed-price share and competitive pressure) | None | Effective productivity |
| 7. AI capability | None (exogenous) | None | None | `AutomatableShare[WorkType](t)`, productivity multiplier, AICostPerUnit(t), RegulatoryDrag\[Sector\](t) |
| 8. Finance | `ViabilityIndex[Employer]` (smoothed margin), `CumulativeSpend[Provider]` (USD) | Margin, seat spend (base + AI add-on), credit spend | Smoothing adjustment | Revenue, labour cost, AI tooling cost, margin |
| 9. Visa policy and GCCs | VisaWorkforce\[Employer\] (subset of Headcount), GCCCapacity\[Sector\] (positions) | Visa approvals, GCC setup | Visa expiry, conversion to permanent residence | VisaPolicyTightness(t), onsite cost, win-rate penalty, GCC setup attractiveness |
| 10. Sourcing choice | SourcingShare\[Sector\]\[Employer\] (fraction, smoothed) | Share adjustment toward logit target | Share adjustment toward logit target | Cost per unit by archetype, proximity value, delivery risk, capacity, regulatory fit |

Three equations anchor the core loop. Work gets done at the rate capacity allows:

```latex
\text{WorkCompletion} = \sum_{\text{levels}} \text{Headcount} \times \text{LevelWeight} \times \text{Productivity}
```

Employers size their workforce to clear the backlog in a target time:

```latex
\text{DesiredHeadcount} = \frac{\text{ITBacklog}}{\text{TargetClearanceTime} \times \text{Productivity}}
```

Adoption follows the Bass diffusion model, where p is innovation and q is imitation:

```latex
\frac{dA}{dt} = \left(p + q \cdot A\right)\left(1 - A\right)
```

## Feedback loops

Twenty-two loops drive the behaviour; the questions are answered by which loops dominate, and when.

| Loop | Type | Mechanism | Main delay | Informs |
| --- | --- | --- | --- | --- |
| R1 Savings reinvestment | Reinforcing | Consumer AI automates LOB work → LOB headcount falls → savings → larger AI budget → more adoption | Budget cycle (\~1 yr) | Q1 |
| R2 AI begets IT work | Reinforcing | Consumer AI adoption creates build demand (RAG, agents, pipelines, data readiness, AI governance) → larger IT backlog | Project start-up | Q1 |
| R3 Jevons effect | Reinforcing | Vendor productivity up → cost per unit of work down → more projects approved → more demand | Price perception, renewals | Q1, Q3 |
| R4 Skill erosion | Reinforcing | Longer unemployment → skill decay and exits → smaller senior pool → shortage | Years unemployed | Q1 |
| R5 Shortage accelerates AI | Reinforcing | Fewer seniors → higher wages → AI relatively cheaper → faster AI adoption → less hiring | Wage adjustment | Q1, Q3 |
| R6 Vendor death spiral | Reinforcing | Revenue down → margin down → layoffs and less AI investment → weaker bids → fewer contracts → revenue down | Bid cycle, contract duration | Q3 |
| B1 Productivity compression | Balancing | Same backlog, more output per head → fewer heads needed | Hiring and layoff decisions | Q1 |
| B2 T&M paradox | Balancing | Under T&M, AI adoption cuts billable hours and revenue → vendors slow adoption; fixed-price share removes the brake | Contract renewal | Q2, Q3 |
| B3 Insourcing | Balancing | AI makes consumer in-house teams more capable → work moves in-house → outsourced backlog shrinks (staff aug hit hardest); acts through the in-house value term in the sourcing logit | Capability build-up | Q1, Q2 |
| B4 Talent pipeline gap | Balancing (delayed) | Junior hiring cut → 5-8 years later too few seniors → capacity shortage → hiring resumes | Aging chain (5-8 yrs) | Q1 |
| B5 Discouraged entry | Balancing (delayed) | IT unemployment up → fewer students choose IT → fewer juniors → eventual shortage → prospects improve. Two stacked delays can produce oscillation | Perception (\~2 yrs) + education (3-4 yrs) | Q1 |
| B6 Right-sizing | Balancing | Margin pressure → cost cuts and shift to fixed price → margin recovers at a smaller size | Restructuring | Q3 |
| R7 Captive learning | Reinforcing | GCC capability grows → more work moved to GCCs → more scale and capability; drains vendor revenue and feeds R6 | GCC setup (1-2 yrs) | Q1, Q3 |
| B7 Local hiring substitution | Balancing | Visa tightness → onsite shortfall → vendors hire onshore at higher wages → onshore IT unemployment falls, vendor margin falls | Recruiting | Q1, Q3 |
| B8 Political pressure (optional) | Sign ambiguous | Onshore IT unemployment up → political pressure → visa tightness; balancing if vendors hire locally, reinforcing if they shift work offshore | Policy cycle | Q1, Q3 |
| R8 Repricing acceleration | Reinforcing | Shorter terms → faster repricing → vendor margin falls → weaker vendor bargaining power → even shorter terms | Contract duration | Q2, Q3 |
| B9 Application displacement | Balancing | Consumer AI adoption → agents replace forms-based apps → fewer new apps, faster retirement → smaller portfolio → less app development and support demand; counters R2 | App retirement cycle | Q1 |
| B10 Seat contraction | Balancing | LOB headcount falls → fewer seats → less end-user services work and per-seat spend; the savings also feed the AI budget, strengthening R1 | Device refresh, licence renewal | Q1, Q3 |
| B11 Budget crowding-out | Balancing (for vendors) | AI seat and credit spend rise → less budget for IT services → smaller outsourced backlog → more work handed to agents → more credit spend | Annual budget cycle | Q1, Q3 |
| B12 Price competition | Balancing | Archetype loses sourcing share (e.g. from arbitrage erosion) → cuts price → cost advantage partly restored → share recovers, at the expense of margin (feeds R6) | Share perception (1-2 yrs), renewals | Q3 |
| B13 Hiring delay | Balancing (delayed) | Backlog up → desired headcount up → vacancies → hires after time-to-fill and onboarding → capacity catches up; long delays cause overshoot and undershoot | Time-to-fill + onboarding | Q1 |
| R10 Talent poaching | Reinforcing | GCC wage premium → vendor attrition up → delivery strain and replacement cost up → weaker vendor bids → more work to GCCs → more GCC hiring from vendors | Notice period, sourcing perception | Q1, Q3 |

## AI capability formulation

AI capability grows at a small fixed annual rate, applied through Amdahl's law so the non-automatable part of each work type caps the productivity gain.

Productivity for a fully AI-enabled team, where a is the automatable share and s is the AI speed-up on that share:

```latex
P_{AI} = \frac{1}{(1 - a) + a / s}
```

The automatable share closes a fraction g of its remaining gap to the ceiling each year, anchored at the 2024 model start and clamped at zero so the calibration years stay valid:

```latex
a(t) = \max\left(0,\; a_{max} - (a_{max} - a_{2024})(1 - g)^{t - 2024}\right)
```

Effective productivity blends AI-enabled and conventional work by adoption fraction A:

```latex
P_{eff} = A \cdot P_{AI} + (1 - A)
```

Starting assumptions (illustrative, to be calibrated):

| Work type | a in 2024 | a\_max | s |
| --- | --- | --- | --- |
| App development | 0.25 | 0.60 | 5 |
| Data migration and transformation | 0.35 | 0.80 | 5 |
| Security | 0.15 | 0.45 | 4 |
| Governance | 0.10 | 0.35 | 3 |
| Support and operations | 0.30 | 0.70 | 5 |
| End-user services | 0.35 | 0.80 | 5 |

Scenario slider for g: slow 5%/yr, base 10%/yr, fast 20%/yr. Over a 2040 horizon the a\_max ceilings matter more than g, so they get their own sensitivity runs. Consumer AI adoption also adds governance work to the backlog, so governance demand can rise while its automatable share stays low.

## Application portfolio and seat contraction

As consumers automate LOB work they need fewer new applications and fewer seats, so part of IT demand shrinks with the workforce it serves.

### Application portfolio

- Stock `AppPortfolio[Sector]` (applications): inflow = new LOB apps built, outflow = retirements.
- New-app demand falls as agents and AI workflows replace forms-and-screens applications, where d (0-1) is displacement strength:

```latex
\text{NewAppDemand} = \text{BaseNewAppDemand} \times (1 - d \times \text{ConsumerAIAdoption} \times \text{LOBAutomationShare})
```

- Retirement speeds up when agentic workflows replace legacy apps. Each retirement adds a one-off data migration load, then its support load disappears.
- App development inflow = new apps × effort per app + enhancements in proportion to the portfolio. Application support demand is proportional to portfolio size.
- Net effect: app development and support demand fall while AI build and governance demand rise; the balance of R2 against B9 sets the direction.

### Seat-driven demand and spend

- `Seats[Sector]` = LOB headcount + consumer IT headcount (auxiliary, persons).
- End-user services work (service desk, device management, endpoint security, identity) is proportional to seats; it is now its own work type.
- Per-seat spend (devices on a roughly 4-year refresh cycle, per-seat software such as Microsoft 365) follows seats, adjusting only at device refresh and licence renewal.
- Seat-based licensing contracts reprice at renewal on seat count × price per seat, and the price per seat rises as AI add-ons attach.
- Offsetting growth comes from consumption credits metered on agent work, plus cloud compute (next subsection).

### Seats plus credits

Software platforms now run two meters, a per-seat price that rises as AI add-ons attach and consumption credits for agent work, so revenue per remaining employee can rise while seats fall ([NPI Financial](https://www.npifinancial.com/knowledge-center/the-new-economics-of-microsoft-copilot-managing-seats-and-consumption/), [Redress Compliance](https://redresscompliance.com/enterprise-genai-pricing-report-2026)).

```latex
\text{PlatformRevenue} = \text{Seats} \times (\text{BaseSeatPrice} + \text{AttachRate} \times \text{AISeatPrice}) + \text{AgentWork} \times \text{CreditsPerUnit} \times \text{CreditPrice}
```

- AttachRate (share of seats with an AI add-on) diffuses like adoption from a low 2026 base.
- AgentWork is the LOB and IT work agents do instead of people, so credits grow exactly where headcount shrinks: labour spend converts into credit spend.
- Seats act as a floor, since agentic products require an AI seat as a prerequisite ([NPI Financial brief](https://www.npifinancial.com/wp-content/uploads/2026/07/MSFT-Copilot-SSB-FINAL.pdf)).
- A leakage share sends part of agent spend straight to AI model providers through connectors, bypassing the platform seat ([Creative Strategies](https://creativestrategies.com/?p=10576)).
- The consumer IT budget is shared: rising seat and credit spend competes with IT services spend and squeezes outsourced work (loop B11).

Output: platform revenue split into base seats, AI seats and credits, answering whether seat-plus-credit revenue per employee rises fast enough to offset fewer employees.

## AI cost and external levers

Five exogenous levers bring in forces outside the model boundary without modelling their causes; each is a time series with named scenarios.

| Lever | Variable | Acts on | Scenarios |
| --- | --- | --- | --- |
| AI cost curve | `AICostPerUnit(t)` | Adoption speed (AI cost vs labour cost), vendor AI tooling cost, credit price | Base decline; compute shock (conflict, energy, chip export controls) raising cost for 2-3 years |
| Regulatory drag | `RegulatoryDrag[Sector](t)` | Slows consumer AI adoption for high-risk uses; adds Governance demand | EU AI Act steps; light-touch; strict |
| Verification and rework tax | `VerificationOverhead[WorkType]` | Lowers the effective AI speed-up; adds remediation and security work from AI-generated systems | Low, base, high |
| Macro IT budget | `ITBudgetGrowth(t)` | Base demand growth and the consumer AI budget | Steady; 2-year downturn; boom |
| AI-driven cyber threat | `CyberThreatMultiplier(t)` | Security base demand growth | Base; elevated |

**AI cost drives adoption speed.** The Bass innovation and imitation rates (p, q) scale with the cost advantage of AI over labour, so falling AI cost and rising wages both accelerate adoption:

```latex
p_{eff} = p \cdot f\left(\frac{\text{LabourCostPerUnit}}{\text{AICostPerUnit}}\right), \quad q_{eff} = q \cdot f(\cdot)
```

**Verification overhead** v (review time per unit of AI output) enters the Amdahl formula, so cheap but unreliable AI gains less:

```latex
P_{AI} = \frac{1}{(1 - a) + a / s + a \cdot v}
```

**Regulatory drag** follows the EU AI Act timeline after the Digital Omnibus: high-risk obligations apply from December 2, 2027 for stand-alone (Annex III) systems and August 2, 2028 for AI in regulated products (Annex I) ([CASRAI](https://www.casrai.org/news/eu-ai-act-digital-omnibus-deadline-delay)). Annex III covers recruitment, credit scoring, education and essential services ([Compliance Hub](https://compliancehub.wiki/blog/eu-digital-omnibus-ai-act-deadline-deferral-annex-iii-2027)), so drag is strongest in Financial, Medical and Government. The same lever represents US state AI laws and sector regulators.

Middle East conflicts and other geopolitical events enter only through the compute shock scenario.

## Contract mix mechanism

The contract mix emerges from the gap between what consumers expect AI to save and what vendors actually save, resolved only when contracts come up for renewal.

**Pressure gap.** Consumers form an expected AI discount from perceived vendor productivity, smoothed over about 2 years. Vendors realise their actual productivity gain. Under T&M the vendor absorbs any gain as lost billable hours; under fixed price the vendor keeps it as margin until repricing.

**Shares of new contracts** use a logit attractiveness formulation, where each contract type k scores utility from both sides:

```latex
\text{Share}_k = \frac{e^{\beta_c U^{cons}_k + \beta_v U^{vend}_k}}{\sum_j e^{\beta_c U^{cons}_j + \beta_v U^{vend}_j}}
```

- Consumer utility: price relative to expected AI discount, risk transfer, flexibility, lock-in; staff augmentation gains appeal when time-to-fill is long, as a way around hiring friction.
- Vendor utility: expected margin at current productivity, revenue predictability, delivery risk.
- β\_c and β\_v set relative bargaining power; a lower vendor margin or more vendor capacity shifts power to consumers.

**Contract vintages.** Each contract type is split into two stocks, because one stock with one average duration would wrongly shorten legacy deals when new ones get shorter.

- `LegacyContractValue[Sector][ContractType]`\[Vendor\]: contracts in force at the 2024 model start, long terms, pre-AI prices. Initial value only, no inflow; drains at its original duration.
- `NewContractValue[Sector][ContractType]`\[Vendor\]: every signing during the simulation, including renewals of expiring legacy deals, with shorter, endogenous durations.

**Expiry is the decision point.** An expiring contract is renewed with the incumbent, rebid to another vendor archetype, moved to a GCC or in-house, or dropped. Renewals and rebids re-enter as new signings at current prices and new-contract durations.

**New-contract duration is negotiated.** Consumers want short terms while AI keeps lowering the cost of work, so they avoid locking in today's price. Vendors want long fixed-price and managed terms so they keep productivity gains longer.

```latex
\text{Duration}^{new}_k = \text{BaseDuration}_k \times f(\text{PriceUncertainty}, \text{VendorPower})
```

- PriceUncertainty = expected annual decline in cost per unit of work, from the trend in perceived vendor productivity.
- f is a table function that falls as uncertainty rises and as vendor bargaining power weakens; calibrated to deal-tenure data, with a floor of 0.25 years so loop R8 cannot drive terms to zero.

**Effective repricing.** The price index of in-force contracts snaps to the expected AI discount at renewal (rate 1 / duration). Where a contract carries a productivity glide path (committed annual price reductions), it also declines at that rate in between, so a long glide-path deal behaves like a short one.

**Consequences.** Shorter terms close the pressure gap faster, so vendors keep productivity gains for less time. They also bring more frequent rebids (higher sales cost, more volatile revenue) and more chances for work to move to GCCs.

| Contract type | Legacy duration (yrs) | New-contract base duration (yrs) | Who keeps AI gains before repricing |
| --- | --- | --- | --- |
| Fixed price | 2-3 | 1-1.5 | Vendor |
| T&M | 1-2 (framework) | 0.5-1 | Consumer (fewer hours billed) |
| Support / managed | 5-7 | 2-3 | Vendor, unless a glide path applies |
| Staff augmentation | 1 | 0.25-0.5 | Consumer (fewer heads needed) |
| Licensing | 3-5 | 1 (annual subscription) | Licensor |
| Outcome-based (proposed) | None | 2-3 | Shared via price per outcome |

Durations are illustrative starting values, to be calibrated against vendor deal-tenure disclosures.

The Q2 answer is "the mix balances" if shares stop changing (under 2 percentage points per year) before 2040. The average duration of new contracts by type is reported alongside the shares, since term length is a second way the two sides settle the pressure.

## Sourcing choice between vendor archetypes

Work goes to the sourcing option with the best overall value, and AI erodes the labour-cost arbitrage that has favoured offshore vendors.

**Options per sector:** consumer in-house (onshore), GCC, offshore Indian IT, global SI, boutique.

**Shares of work coming up for signing or renewal** follow a logit on each option's value V:

```latex
\text{SourcingShare}_e = \frac{e^{\beta V_e}}{\sum_j e^{\beta V_j}}
```

Value combines five terms, weighted per sector:

- Total cost per unit of work: labour cost / effective productivity + AI cost + onsite and visa cost + vendor margin.
- Proximity and domain value: higher for onshore teams and specialist boutiques.
- Delivery risk: visa exposure, the vendor's viability index, enforcement actions.
- Capacity: whether the archetype can staff the work at all (labour market link).
- Regulatory fit: data residency and oversight expectations in regulated sectors.

**Arbitrage erosion.** The cost gap between onshore and India delivery per unit of work is the wage gap divided by productivity:

```latex
\text{CostGap} = \frac{W_{onshore} - W_{India}}{P_{eff}}
```

As AI raises productivity, the absolute gap shrinks, so proximity, risk and regulatory fit carry more weight in V. This shifts share toward onshore teams, boutiques and GCCs unless offshore vendors cut price.

**Timing.** Shares adjust toward their logit target with a 1-2 year perception delay, and only on contracts that are being signed, renewed or rebid, so the contract vintages set the pace.

**Output:** share of IT work by archetype over time, the core of the Q3 answer.

## Vendor viability, collapse and equilibrium tests

An archetype collapses when its smoothed margin stays negative and capacity drains; the system is in equilibrium when its major stocks stop moving.

**Financial structure per vendor archetype:**

- Revenue by contract type: T&M and staff augmentation bill effort delivered (heads × rate), so revenue falls as productivity rises (loop B2); fixed price and outcome-based recognise contract value as work is delivered; support and licensing recognise value / duration
- Cost = billable and bench headcount × regional wage + AI tooling and token spend + overhead
- Margin = (Revenue − Cost) / Revenue
- `ViabilityIndex` = margin smoothed over 2 years (a first-order smooth, so short dips don't trigger exit)
- Bid win rate falls as viability falls (less investment, weaker delivery), closing loop R6
- Capacity exit: when the viability index is below a threshold, layoffs accelerate beyond what demand alone requires

**Outcome tests, evaluated over 2038-2040, with a 2035 checkpoint:**

| Outcome | Test |
| --- | --- |
| Collapse | Viability index below 0 for 3 or more consecutive years and headcount falling more than 15%/yr |
| New equilibrium | Every major stock (headcount by employer and region, contract value by type, backlog) changing less than 2%/yr |
| Still adjusting | Neither test met; report which loops still dominate |

Thresholds are first guesses and become sensitivity parameters.

## Visa policy and GCCs

US visa policy enters as an exogenous tightness index that limits offshore vendors' onsite workforce, while GCCs give consumers a captive route to India talent that bypasses vendors.

**Context, October 2026.** On September 8, 2026 the DOL Inspector General suspended PERM filings by Cognizant and Cloudera, later extended to H-1B processing, under a fraud probe opened in July 2026 ([Outlook India](https://www.outlookindia.com/international/us-suspends-cognizant-cloudera-perm-filings-amid-visa-fraud-probe), [Alma](https://www.tryalma.com/learn/cognizant-cloudera-hit-with-perm-and-h-1b-suspension)). Cognizant's H-1B approvals fell from 9,413 in 2020 to 3,510 in fiscal 2026 ([The Week](https://www.theweek.in/news/biz-tech/2026/09/09/us-suspends-cognizant-from-filing-green-cards-what-it-means-for-indian-workers.amp.html)). A $100,000 fee on new H-1B petitions has applied since September 2025 (approximate, to verify).

### Policy lever

`VisaPolicyTightness(t)` runs from 0 (open) to 1 (closed). Values are set at calibration; the scenarios define its shape.

| Scenario | Path 2026-2040 |
| --- | --- |
| Status quo | Holds at the 2026 level |
| Escalating crackdown | Rises steadily as PERM and H-1B suspensions spread across offshore vendors |
| Relaxation | Eases after a policy change, e.g. from 2029 |

### Onsite visa workforce

- Stock `VisaWorkforce[Employer]` (persons): India-origin staff of offshore vendors working onshore. It is a coflow inside Headcount\[Offshore Indian IT\]\[Onshore\], not a separate pool.
- Inflow: new visa approvals = base visa capacity × (1 − tightness), limited by onsite role demand.
- Outflows: visa expiry and return to India, and conversion to permanent residence (slowed by PERM suspensions; converts join the onshore pool).
- Onsite cost per head includes visa fees and compliance, and rises with tightness.
- An onsite shortfall is filled by local onshore hires (higher wage) or by shifting work offshore. The split responds to onsite margin and to how far AI-assisted remote delivery has spread.

### Consumer responses

- Win-rate penalty on vendors under enforcement action, strongest in Government and Financial, scaled by tightness.
- Faster GCC setup when vendor cost or risk rises.

### GCCs (Global Capability Centres)

- `GCCCapacity[Sector]` (open positions, a ceiling on GCC vacancies; GCC staff are counted in Headcount\[GCC\]\[India\]) grows through a setup decision driven by the cost gap versus vendor prices, vendor risk (visa exposure, viability), consumer scale and consumer AI maturity. AI lowers the minimum viable GCC size.
- Setup takes 1-2 years; capability then ramps along a learning curve.
- GCC headcount draws on the India labour pool and competes with offshore vendors for talent and wages.
- Work moved to a GCC leaves the outsourced backlog and counts as consumer IT headcount located in India.

Q1 therefore reports four lines: consumer onshore, consumer India (GCC), vendor onshore (including the visa workforce), vendor India.

## Hiring friction and personnel movement

People move into, between and out of employers with delays: hiring takes months, layoffs take weeks, and that asymmetry shapes the headcount curves more than the 2040 endpoint.

### Vacancies and matching

- Stock `Vacancies[Employer][Region][Level]`: openings arise when desired headcount exceeds headcount + vacancies + onboarding; vacancies are cancelled when demand falls.
- Hires follow a matching function on job seekers U and vacancies V, where m is matching efficiency:

```latex
\text{Hires} = \min\left(m \cdot U^{\alpha} \cdot V^{1 - \alpha},\; \frac{V}{\tau_{min}},\; \frac{U}{\tau_{min}}\right)
```

- Graduates join Active seekers at junior level. Hires at every level come from Active seekers and from employees of other employers in the same region (job switching), and total hires are capped by vacancies and by seekers.
- Implied time-to-fill = V / Hires, which stretches in a shortage and shrinks when unemployment is high.
- m is the lever for recruiters and AI screening. AI can raise it, or lower it when AI-written applications flood employers; scenarios low, base, high.

### Onboarding

- Stock `Onboarding[Employer][Region][Level]`: new hires work at partial productivity (around 50%, illustrative) for a few months before joining Headcount.
- AI-assisted onboarding (assistants that help newcomers learn codebases and processes) shortens onboarding time, a small vendor-side AI benefit.

### Exits and notice periods

- Layoffs take effect within weeks. Voluntary exits and switches wait out notice periods, which are longer in India (60-90 days is common) than onshore.
- The asymmetry means cuts land fully while rebounds lag, deepening the shortage phase of loops B4 and B5.

### Recovery after layoff

- The unemployed are split into `RecoveringIT[Region][Level]` (not yet searching) and `ActiveSeekers[Region][Level]`. Only active seekers enter the matching function as U.
- Laid-off staff enter Recovering and move to Active seekers after a recovery time of a few months, longer with generous severance, so onshore and India can differ.
- The decision to leave IT is taken mainly during recovery: exits to Left the field rise when job prospects are poor and with seniority (career change, early retirement). Long-term active seekers also exit as skills decay, and every pool loses people to retirement, so no pool accumulates indefinitely.
- Effect: after a layoff wave, unemployment can be high while vacancies stay hard to fill, reproducing the pattern of large layoffs alongside hard-to-fill roles.

### Extension: laid-off seniors founding startups

- Some seniors leaving Recovering found AI-native startups instead of re-entering employment or leaving the field. The founding rate rises with AI leverage (capability up, AI cost down) and the funding climate, and falls when job prospects are good.
- Stock `Startups[Region]` (firms) plus a Founders\[Region\] stock (persons), with small teams: founders plus a few hires drawn from active seekers.
- Most startups fail within a few years. Founders then return to Active seekers with current skills (no skill decay), so failure is not a loss to the field.
- Survivors sell AI-native products to consumers, shifting spend from services contracts toward licensing and consumption. That adds pressure on vendors (Q3) while creating a small number of product jobs.
- Consulting overall is likely shrinking, so independents are modelled as startups rather than as added boutique capacity.
- Status: built after Phase 6, if early runs show exit and re-entry flows are material.

### Job switching between employers

- Voluntary attrition mostly moves people to other employers rather than into unemployment. The flow from employer i to employer j depends on the wage gap and on j's open vacancies:

```latex
\text{Switch}_{i \to j} = \text{Headcount}_i \times r_{switch} \times g\left(\frac{W_j}{W_i}\right) \times \frac{V_j}{\sum_k V_k}
```

- The main case is GCCs hiring from offshore vendors in India, which raises vendor attrition and replacement hiring and onboarding costs (loop R10). Switches fill vacancies at j and count against j's hire cap, so they can never exceed j's open roles.

### Recruiting firms

- Represented by two parameters: the share of hires made through agencies, and the agency fee as a fraction of first-year salary, added to employer hiring cost. Their own headcount sits outside the model.
- Staff augmentation acts as a way around hiring friction: consumers value it more when time-to-fill is long, through a term in contract-type attractiveness.

## Build plan

The model is built in seven runnable phases, each tested before the next is added.

- [ ] Phase 1. Core loop: one sector, one employer, no arrays. Backlog → desired headcount → hiring and attrition, with the Amdahl productivity multiplier. Done when the model reaches steady state with AI off and shows plausible decline with AI on.
- [ ] Phase 2. Labour market: Junior/Mid/Senior aging chain, unemployed pool, exits, entrant pipeline with job-prospect feedback, vacancies with a matching function, onboarding, recovering vs active job seekers. Done when B4 and B5 delays are visible in test runs.
- [ ] Phase 3. Region dimension: India and Onshore labour pools, wages, `OffshoreShare[Employer]`. Adds the GCC employer element, the onsite visa workforce, the visa policy tightness lever and job switching between employers. Done when headcount plots split by region and policy scenarios move the onsite workforce.
- [ ] Phase 4. Vendor financials: revenue, cost, margin, viability index, capacity exit. Done when a forced revenue drop triggers R6 and B6 behaves as expected.
- [ ] Phase 5. Contracts and sourcing: contract stocks, logit shares, renewal repricing, sourcing choice between vendor archetypes. Done when contract shares respond to the pressure gap.
- [ ] Phase 6. Full dimensions: sectors, work types, all employer archetypes; consumer AI adoption, LOB headcount, application portfolio and seat-driven demand. Built in two steps: 6a, the demand side (done when demand by work type responds to consumer AI, LOB and seats fall, and the budget binds in a downturn); 6b, the supply side (global SIs, boutiques, AI adoption per employer, sourcing and contracts by sector, GCC capacity).
- [ ] Phase 7. Calibration and scenarios: fit 2024-2026 history, run slow/base/fast AI scenarios plus regulation, compute shock, visa and downturn scenarios, sensitivity on key parameters.

Step-by-step instructions and reference results for Phase 1: Phase 1 build guide

Step-by-step instructions and reference results for Phase 2: Phase 2 build guide

Step-by-step instructions and reference results for Phase 3: Phase 3 build guide

Step-by-step instructions and reference results for Phase 4: Phase 4 build guide

Step-by-step instructions and reference results for Phase 5: Phase 5 build guide

Step-by-step instructions and reference results for Phase 6a: Phase 6a build guide

Step-by-step instructions and reference results for Phase 6b: Phase 6b build guide

Calibration to 2024-2026, scenarios, sensitivity and answers to Q1-Q3 (Phase 7): Phase 7 build guide

## Calibration data sources

The sources actually consulted (gathered 9-10 October 2026), grouped by whether they fed the Phase 7 fit, validation, scenarios or only context, are listed in the Sources tab (spec/08_sources.md in this project). The table below is the original map of data needs.

| Data need | Candidate sources |
| --- | --- |
| Vendor headcount, revenue, utilization, attrition, onsite/offshore mix | TCS, Infosys, Wipro, HCLTech, Cognizant, Accenture annual reports and quarterly filings |
| India IT workforce size and growth | NASSCOM strategic review |
| Onshore IT employment and wages | US BLS Occupational Employment and Wage Statistics; Eurostat ICT specialists; Statistics Canada |
| IT spend by sector | Gartner and IDC IT spending forecasts |
| Entrant pipeline (computing graduates) | AICTE (India), NCES (US), Eurostat education statistics |
| Contract-type mix | Vendor revenue disclosures by contract type (fixed price vs T&M) |
| AI adoption rates | Industry surveys of enterprise and developer AI adoption |
| Visa approvals by employer, enforcement actions | USCIS H-1B Employer Data Hub; DOL H-1B debarment list; DOL Inspector General announcements |
| GCC count, headcount and growth | NASSCOM and Zinnov GCC landscape reports |
| AI cost per unit of work | Published model API price histories; platform credit price lists |
| Sourcing share by archetype | Vendor revenue by geography and vertical; sourcing advisory market reports |
| Regulatory timelines | EU AI Act and Digital Omnibus (Regulation (EU) 2026/1744); US state AI laws |
| Vacancies, time-to-fill, attrition, job switching | US BLS JOLTS (job openings and labor turnover); vendor quarterly attrition disclosures; recruiting industry benchmarks |

## Open decisions and change log

**Open decisions**

- [ ] Keep outcome-based / managed service as its own contract type, or merge it into Support? Resolved in Phase 5: kept as its own type, because its gain-share pricing behaves differently; revisit if it stays niche against real deal data.
- [ ] Is wage endogenous (driven by shortage) from Phase 2, or held constant until Phase 4? Loops R5 and R10 only operate with endogenous wages. Resolved in Phase 4: constant through Phase 3, endogenous from Phase 4, with a switch (WagesEndogenous = 0) to hold them constant for comparison.
- [ ] Should consumer LOB headcount cover all LOB staff, or only roles exposed to AI automation?
- [ ] Does the Onshore region need a later split into North America and Europe?
- [ ] Initial values for 2024: which headcount and contract figures anchor the base year?
- [ ] Keep visa policy exogenous, or activate the political pressure loop (B8) once the base model is calibrated?
- [ ] Add nearshore (Canada, Mexico, Eastern Europe) as a third Region element, since visa pressure may push work there?
- [x] Resolved: agent-based pricing is modelled as seats plus consumption credits, following Microsoft's 2026 model.
- [ ] Revisit AI providers selling services directly (their own engineers at client sites) once there is data to parameterize it?
- [ ] Build the startup pathway (Startups stock, founding and failure flows, product substitution for services) after Phase 6, or leave it as a narrative extension?

**Change log**

| Date | Change |
| --- | --- |
| 2026-10-10 | Phase 7 calibration and scenarios: underlying demand growth (3% a year real) applied to demand, budgets and graduate supply; AI rebased to its 2024 level (A0 0.35, AC0 0.30) so 2024 stays a steady state; 2024 starting state rebuilt on the balanced growth path (100-year burn-ins rescaled to 2024); new parameters for falling verification overhead, clients pricing in the productivity trend, GCC momentum and a GCC wave that half-fades after 2030; eleven parameters fitted to eleven 2024-2026 observations, with validation on revenue, onshore headcount and business workforce; 14 scenarios, a 14-parameter tornado and a 300-run Monte Carlo. Findings: total IT jobs end near their 2024 level (0.96; 10th-90th percentile 0.84-1.24) as 3% demand growth and AI productivity roughly cancel; onshore jobs fall to 0.86, India rises to 1.10 as GCCs triple and vendor India halves; demand growth, verification decline and AI speed drive the total, the GCC wave drives vendor India; effort-billed contracts rise to about 2031 then give way to fixed price and managed services; no collapse in any run, Indian IT reaches a smaller equilibrium at 42% of 2024 headcount |
| 2026-10-10 | Phase 6b build: eight employment units (adds global SI India and onshore, boutique) under five employers and three vendor archetypes; production, adoption and productivity per employer; finance, contracts and competition per vendor; contracts tracked by type and vendor, with sector shares held in VW\[Sector, Vendor\] instead of contracts by sector; T&M brake on vendor adoption (B2) and a competitive push; sourcing logit per sector over five options with sector constants, regulatory fit and a GCC term rising with consumer AI adoption (replaces the GCCCapacity stock); job switching between any units in the same pool; labour market recalibrated (enrolment 3,030 India, 3,040 onshore); Q1 lines and the Q3 outcome test computed. Findings: by 2040 vendor India jobs fall 57%, vendor onshore 40%, consumer onshore 40%, GCC 50%; Indian IT loses about a third of its work share, boutiques nearly double theirs, global SIs hold share; no archetype collapses but none has settled (Q3: still adjusting); the T&M brake changes timing more than outcomes |
| 2026-10-10 | Phase 6 split into 6a (demand) and 6b (supply), all 7 sectors kept. Phase 6a build: backlog by sector and work type with the spec's capability table; P\_eff is the backlog-weighted blend; the 2024 work-type mix is common to all sectors; AIOn = false also switches off consumer AI; consumer adoption with regulatory drag (ramped December 2027 to August 2028), AI cost effect and reinvested savings (R1); LOB automatable share 5% rising to 35%; app portfolio (B9), seats billed with a lag (B10), seats plus credits with 20% leakage, cloud; one budget per sector as a ceiling on discretionary demand (B11); delivery adoption sped up by cheaper AI (R5); Jevons lever moved onto consumer cost per unit, default 0. Findings: AI projects (R2) lift IT demand about 9% to 2032, then app and seat contraction win, leaving demand 3% below 2024 in 2040; governance and data work grow, support and end-user services shrink; employment falls to about 45,000 by 2040 (48,000 in Phase 5); platform revenue per seat almost doubles by 2032; whether freed budget is spent (Jevons) is the largest open Q1 assumption |
| 2026-10-10 | Phase 5 build: contract stocks measured as shares of total work (types FP, TM, MS, SA, OB; legacy and new vintages, with duration and price coflows); legacy durations double as no-AI base durations, and new terms shorten with AI price uncertainty (the table's new-contract durations are now roughly what this produces at peak pressure); outcome-based kept as its own type with a 3% 2024 base; licensing moved to Phase 6; consumer distrust of effort billing added (B2, consumer side); sourcing choice between in-house, GCC and one vendor archetype replaces the fixed shares and the VSE placeholder (global SIs and boutiques in Phase 6); price competition B12 triggered by share loss and by rivals bidding away excess margin; sales cost added. Findings: with AI, effort-billed work falls from 40% to 24% of vendor contracts and the mix settles by the mid-2030s; outcome-based stays niche; competition cuts the 2040 vendor margin from 29% to 22%; the vendor's work share drifts from 60% to 51% by 2040; the price-cut tipping point moves to 30-35% |
| 2026-10-09 | Phase 4 build: wages made endogenous but switchable (WagesEndogenous; responds to regional unemployment and vendor margin pressure), settling the open decision; a vendor share effect (VSE) stands in for R6 until sourcing choice in Phase 5; a 2-point dead band on margin responses; full price pass-through of client-perceived productivity; initial values refreshed by joint labour-finance calibration. Finding: a tipping point between a 35% and 40% price cut separates B6 right-sizing from the R6 death spiral; when vendors shrink, consumer spend rises; AI lifts vendor margins until Phase 5 competition is added |
| 2026-10-09 | Phase 3 build: AnyLogic arrays introduced now rather than in Phase 6 (dimensions Unit, Level, Region); the vendor is split into Vendor India, Onsite visa and Onsite local units; work shares are fixed until sourcing choice in Phase 5; vendors respond to perceived visa tightness by moving onsite work offshore and hiring locally; visa holders hire from and return to the India pool |
| 2026-10-09 | Phase 2 build: promotions now fill upper-level vacancies (capped by eligible staff); experienced entry from other industries switches on when fill times exceed normal; level mix recalibrated to career flows (19/25/56%); wages held constant until Phase 4 |
| 2026-10-09 | Design review: integrity rules added (people conservation, no negative stocks, one budget, demand abandonment, single work representation, saturating effects, floors, one mechanism per effect); work queues; Vendor and Provider dimensions; employer-specific wages; T&M revenue by effort; legacy vintage = 2024 stock; capability curve anchored at 2024; capped matching and switching; GCC capacity and visa workforce no longer double-count people |
| 2026-10-09 | Unemployed split into recovering and active seekers; leave-IT decision moved into recovery; startup pathway for laid-off seniors added as an extension |
| 2026-10-09 | Hiring friction added: vacancies with a matching function, onboarding, notice periods, job switching between employers, recruiting firms as parameters; loops B13, R10 |
| 2026-10-09 | Scope review: added sourcing choice between archetypes (loop B12), AI cost curve, sector regulatory drag, verification tax, macro budget and cyber levers; Middle East and EU region split kept out |
| 2026-10-09 | Seats-plus-credits platform revenue added; connector leakage to AI providers; loop B11 budget crowding-out |
| 2026-10-09 | Horizon extended to 2040; application portfolio and seat contraction added (End-user services work type, per-seat vs consumption spend, loops B9, B10) |
| 2026-10-09 | Contracts split into legacy and new vintages; new-contract duration made endogenous and negotiated; glide-path repricing; loop R8 |
| 2026-10-09 | Added visa policy (H-1B, PERM) as a scenario lever, the onsite visa workforce, the GCC employer archetype and loops R7, B7, B8 |
| 2026-10-09 | Region dimension adopted from the start (India, Onshore) |
| 2026-10-09 | Initial spec: questions Q1-Q3, modules, loops, Amdahl capability formulation, contract mechanism, build plan |
