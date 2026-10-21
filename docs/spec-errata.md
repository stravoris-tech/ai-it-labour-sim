# Specification errata

The original specification (`reference/prototype/spec/`, frozen, never edited) is wrong or inconsistent in the places
below. Each entry quotes the spec, says what is wrong with it, and says what the model does instead, with the code
site or the section of the phase 9 design note (`docs/model-changes-phase9.md`) that carries it. Line references are
to the frozen spec. Entries are grouped by the engine module where the model's replacement lives. Source: recon 13g
C3, which merges recon 11 and recon 12b's spec notes.

## AI capability

### E22: Two definitions of AI productivity

- **Spec:** `reference/prototype/spec/00_model_spec.md:154`; `reference/prototype/spec/00_model_spec.md:244`
- **The spec says:** "P_{AI} = \frac{1}{(1 - a) + a / s}"
- **What is wrong:** The spec defines the AI productivity multiplier twice: as the Amdahl speed-up alone (line 154)
  and with a verification term `a x v` (line 244). The two disagree whenever verification costs anything.
- **What the model does instead:** One definition, with the verification overhead: `PAI = 1 / ((1 - a) + a / s + a x
  VerifNow)`, where `VerifNow` falls from `Verif` at `VerifDecline` a year (`reference/prototype/spec/07_phase7_build_guide.md:27`)
  (`src/aisim/scalar/capability.py:68`; `src/aisim/scalar/capability.py:67`)

### E31: The AI capability and delivery AI rows of the stock table are incomplete

- **Spec:** `reference/prototype/spec/00_model_spec.md:94`; `reference/prototype/spec/00_model_spec.md:95`; `reference/prototype/spec/00_model_spec.md:231-233`; `reference/prototype/spec/00_model_spec.md:235-239`
- **The spec says:** "Adoption (Bass, modulated by fixed-price share and competitive pressure)"
- **What is wrong:** The delivery AI row (line 94) omits the AI-cost effect on the Bass rates p and q (lines
  235-239), and the AI capability row (line 95) omits `VerificationOverhead`, `ITBudgetGrowth` and
  `CyberThreatMultiplier` (lines 231-233), which the module sections define.
- **What the model does instead:** It follows the module sections: the verification overhead in capability, IT budget
  growth and the cyber multiplier in the consumer drivers, and a cost effect on the Bass rate of delivery adoption
  (`src/aisim/scalar/capability.py:67`; `src/aisim/scalar/consumer.py:122`; `src/aisim/scalar/consumer.py:114`; `src/aisim/scalar/adoption.py:55`)

## Delivery AI adoption

### E10: R5 is labelled reinforcing

- **Spec:** `reference/prototype/spec/00_model_spec.md:128`
- **The spec says:** "Fewer seniors → higher wages → AI relatively cheaper → faster AI adoption → less hiring"
- **What is wrong:** "Less hiring" can close back through higher unemployment and lower wages, which is balancing; the
  loop reinforces only through the pipeline delay (fewer juniors now, fewer seniors later). Its sign is not fixed.
- **What the model does instead:** Both branches are live. Delivery adoption speeds up as labour cost per unit of
  effective staff rises against AI cost, and wage targets read perceived unemployment
  (`reference/prototype/spec/04_phase4_build_guide.md:24`), so less hiring lowers wages and damps adoption
  (`src/aisim/scalar/adoption.py:55`; `src/aisim/scalar/finance.py:401`)

### E11: R6 says vendors invest less in AI under margin pressure

- **Spec:** `reference/prototype/spec/00_model_spec.md:129`; `reference/prototype/spec/00_model_spec.md:342`
- **The spec says:** "layoffs and less AI investment"
- **What is wrong:** The evidence reverses the sign: vendors raise AI investment under margin pressure (Accenture,
  Cognizant, TCS, Capgemini, Atos; `docs/research/loop-strength-evidence.md:84-86`). Line 342's "(less investment,
  weaker delivery)" repeats the error.
- **What the model does instead:** No AI-investment rule. Vendor adoption is Bass diffusion with a cost effect, a T&M
  brake and a share-loss push, and reads neither margin nor viability, so vendors keep adopting under stress
  (`src/aisim/scalar/adoption.py:63`; `docs/model-changes-phase9.md:150`)

### E35: B2, the T&M paradox, is reinforcing in the code

- **Spec:** `reference/prototype/spec/00_model_spec.md:131`
- **The spec says:** "Under T&M, AI adoption cuts billable hours and revenue → vendors slow adoption; fixed-price share removes the brake"
- **What is wrong:** The spec labels B2 balancing, through revenue: adoption cuts T&M revenue and vendors slow
  adoption. The code has no link from revenue to the brake; the brake reads the effort-billed share of the book. The
  one closed loop through the brake is reinforcing: adoption raises productivity, signings shift from effort billing to
  fixed price, the effort-billed share falls and the brake weakens, so adoption speeds up (recon 10b B1).
- **What the model does instead:** The chain `A -> Pew -> EffE -> Pe -> VB.TypeShare -> VB.Sign -> NewV ->
  VB.EffortShare -> brake -> AdoptE -> A` (signs + - - - + + + - + +: four negative links, an even number, so the
  loop is reinforcing), with a second path through client distrust of effort billing (`Pe -> ClientP ->
  VB.TypeShare`). The revenue path (`Pe -> VF.IdxVol -> VF.AvgIdx -> VF.Revenue`) stops at revenue
  (`src/aisim/scalar/capability.py:79`; `src/aisim/scalar/work.py:64-65`; `src/aisim/scalar/finance.py:355`;
  `src/aisim/scalar/finance.py:360`; `src/aisim/scalar/integrate.py:120`; `src/aisim/scalar/finance.py:368`;
  `src/aisim/scalar/adoption.py:60`; `src/aisim/scalar/adoption.py:65`; `src/aisim/scalar/integrate.py:103`)

## Client demand and consumer AI

### E1: R2 is an open chain

- **Spec:** `reference/prototype/spec/00_model_spec.md:125`
- **The spec says:** "Consumer AI adoption creates build demand (RAG, agents, pipelines, data readiness, AI governance)"
- **What is wrong:** R2 is labelled a reinforcing loop, but the chain stops at "larger IT backlog": no link leads back
  to consumer AI adoption.
- **What the model does instead:** AI build demand (new adoption at `BuildRate`, the adopted stock at `RunRate`) adds
  to each sector's demand. Nothing closes the chain, and nothing needs to (`src/aisim/scalar/consumer.py:223`)

### E2: R3's closure is not stated

- **Spec:** `reference/prototype/spec/00_model_spec.md:126`
- **The spec says:** "Vendor productivity up → cost per unit of work down → more projects approved → more demand"
- **What is wrong:** An open chain: "more demand" does not lead back to vendor productivity, and the spec does not say
  what closes the loop.
- **What the model does instead:** R3 acts through the consumer's perceived cost per unit of work, `Jev =
  CostPerc^-JevonsEps` (capped at `JevonsCap`), on app and data demand
  (`reference/prototype/spec/06a_phase6a_build_guide.md:32`). `JevonsEps` is 0 in Base, so the effect is off unless
  a scenario sets it (`src/aisim/scalar/consumer.py:118`)

### E5: B9 is an open chain

- **Spec:** `reference/prototype/spec/00_model_spec.md:140`
- **The spec says:** "less app development and support demand; counters R2"
- **What is wrong:** B9 is labelled a balancing loop, but the chain ends at demand: no link leads back to consumer AI
  adoption.
- **What the model does instead:** AI exposure displaces new applications (`AppDisplacement`) and speeds their
  retirement (`RetireAccel`); the smaller portfolio lowers app, data and support demand. No link closes it
  (`src/aisim/scalar/consumer.py:202`; `src/aisim/scalar/consumer.py:203`)

### E8: B11 is labelled balancing but its last steps reinforce

- **Spec:** `reference/prototype/spec/00_model_spec.md:142`
- **The spec says:** "more work handed to agents → more credit spend"
- **What is wrong:** B11 is labelled "Balancing (for vendors)", but its last steps, from a smaller outsourced backlog
  to more work for agents and more credit spend, reinforce credit spend. The label holds only for vendors.
- **What the model does instead:** No budget-to-agent link. Agent work is the line-of-business work that AI exposure
  automates, whatever the budget; the budget acts only through approval of app and data demand
  (`src/aisim/scalar/consumer.py:192`; `src/aisim/scalar/consumer.py:209`)

### E9: B10 is balancing with a reinforcing branch

- **Spec:** `reference/prototype/spec/00_model_spec.md:141`
- **The spec says:** "the savings also feed the AI budget, strengthening R1"
- **What is wrong:** A balancing loop carries a reinforcing branch inside it, and the seat savings it names are not
  part of the savings the model reinvests.
- **What the model does instead:** It reinvests a share (`ReinvestFrac`, 0.2) of net line-of-business savings only:
  the LOB wage bill saved, less credit spend (`reference/prototype/spec/06a_phase6a_build_guide.md:33`). Seat savings
  do not enter (`src/aisim/scalar/consumer.py:194`; `src/aisim/scalar/consumer.py:208`)

### E29: CumulativeSpend[Provider] appears in no module section

- **Spec:** `reference/prototype/spec/00_model_spec.md:96`
- **The spec says:** "CumulativeSpend[Provider]"
- **What is wrong:** The stock is listed in the finance row of the stock table, but no module section develops it or
  says what flows into it by provider.
- **What the model does instead:** Not built. Seat, credit and cloud spend are computed per sector each step as parts
  of committed spend, but they are not accumulated or split by provider (`src/aisim/scalar/consumer.py:207`)

### E32: AI governance demand is listed as its own inflow

- **Spec:** `reference/prototype/spec/00_model_spec.md:86`; `reference/prototype/spec/00_model_spec.md:180`; `reference/prototype/spec/00_model_spec.md:230`
- **The spec says:** "AI governance demand"
- **What is wrong:** The stock table lists AI governance demand as a separate backlog inflow, while the module
  sections (lines 180 and 230) derive it from consumer AI adoption and regulation.
- **What the model does instead:** Governance is one work type of base demand, its mix raised by regulatory drag
  times consumer adoption (`GovRegSens`), as lines 180 and 230 describe (`src/aisim/scalar/consumer.py:219`)

## Work and productivity

### E23: Work completion and desired headcount have inconsistent units

- **Spec:** `reference/prototype/spec/00_model_spec.md:103`; `reference/prototype/spec/00_model_spec.md:109`
- **The spec says:** "\text{WorkCompletion} = \sum_{\text{levels}} \text{Headcount} \times \text{LevelWeight} \times \text{Productivity}"
- **What is wrong:** Work completion comes out in persons, while desired headcount (line 109) divides a backlog in BFY
  by a time and a productivity. The units agree only with an implicit work per person of 1.
- **What the model does instead:** Capacity is `WorkPerPerson x Pe x` effective staff, the level-weighted (`W_l`)
  headcount plus onboarding staff, in BFY a year; desired headcount divides by `WorkPerPerson` too
  (`src/aisim/scalar/work.py:70`; `src/aisim/scalar/work.py:67`; `src/aisim/scalar/workforce.py:97`)

### E28: The WorkQueue stock is required but never developed

- **Spec:** `reference/prototype/spec/00_model_spec.md:42`; `reference/prototype/spec/00_model_spec.md:88`
- **The spec says:** "is allocated by sourcing share into `WorkQueue[Sector][Employer]`"
- **What is wrong:** Integrity rule 5 and the stock table require a work queue per sector and employer, but no module
  section develops it.
- **What the model does instead:** One backlog per sector and work type, held by the employers in proportion to their
  work shares (`IHW`, `GCCW`, `VW`); each employer works its share at its own clearing rate
  (`reference/prototype/spec/06b_phase6b_build_guide.md:28`) (`src/aisim/scalar/work.py:60`; `src/aisim/scalar/work.py:63`)

### E36: The work unit BFY is defined at pre-AI productivity

- **Spec:** `reference/prototype/spec/00_model_spec.md:27`
- **The spec says:** "Baseline FTE-year (BFY): one person-year of effort at pre-AI productivity"
- **What is wrong:** The code measures work at 2024 productivity, the blend of AI-assisted and unassisted work at 2024
  delivery AI adoption (`A0` 0.35), not at pre-AI productivity. A person working without AI completes 0.4% to 3.3%
  less than one BFY a year, by work type (`phase9`).
- **What the model does instead:** A BFY is one person-year of 2024 delivery. Productivity is
  "`(Aemp[e] * PAI[w] + (1 - Aemp[e])) / (pr["A0"] * PAI0[w] + (1 - pr["A0"]))`", 1 in 2024
  (`src/aisim/scalar/capability.py:77-81`), and capacity is "`CapE = {e: pr["WorkPerPerson"] * Pe[e] * EffStaffE[e]
  ...}`" with `WorkPerPerson` 1 BFY per person a year (`src/aisim/scalar/work.py:70`). The units vocabulary says the
  same: "BFY is a unit of IT work (one person-year of 2024 delivery)" (`tools/model_docs.py:972`)

## Workforce planning

### E7: B8's sign is ambiguous and its decision is open

- **Spec:** `reference/prototype/spec/00_model_spec.md:138`; `reference/prototype/spec/00_model_spec.md:508`
- **The spec says:** "Sign ambiguous"
- **What is wrong:** The sign of B8 is left undetermined (balancing if vendors hire locally, reinforcing if they shift
  work offshore), and the open decision on whether to activate it (line 508) is never settled.
- **What the model does instead:** Decided: visa policy stays a scenario input, an exogenous ramp of `VisaTight` from
  `VTBase` to `VTEnd` that the visa scenarios set. Measured on phase 9 (recon 13g B2), the B8 link acts as a
  one-signed extra tightening (`src/aisim/scalar/workforce.py:82`; `docs/model-changes-phase9.md:179`)

### E12: Capacity exit starts on an absolute threshold, through layoffs

- **Spec:** `reference/prototype/spec/00_model_spec.md:343`
- **The spec says:** "when the viability index is below a threshold, layoffs accelerate beyond what demand alone requires"
- **What is wrong:** The evidence shows cuts starting on a relative shortfall at healthy margins, running 1-4% of
  headcount, and executed mostly through intake (`docs/research/loop-strength-evidence.md:76-80`).
- **What the model does instead:** C2: below `R6Theta` (0.65 / 0.80 / 0.92) in relative viability, a vendor's desired
  staff is cut by `min(R6Cap, R6e x points below R6Theta)`, executed by the existing openings and
  layoffs logic, mostly as fewer openings (`src/aisim/scalar/workforce.py:100`; `src/aisim/scalar/loops.py:64`; `docs/model-changes-phase9.md:93`)

### E30: Two descriptions of the visa workforce

- **Spec:** `reference/prototype/spec/00_model_spec.md:97`; `reference/prototype/spec/00_model_spec.md:373`
- **The spec says:** "VisaWorkforce\[Employer\] (subset of Headcount)"
- **What is wrong:** The stock table has a visa stock per employer, a subset of headcount; the visa section (line 373)
  has a coflow inside the Indian vendor's onshore headcount.
- **What the model does instead:** Visa staff are a unit of their own, `OV` (onsite visa) of the Indian vendor, taking
  `OnsiteShare x VisaMix` of its work, hired from and returning to the India pool
  (`reference/prototype/spec/03_phase3_build_guide.md:28`) (`src/aisim/scalar/workforce.py:90`; `src/aisim/dims.py:22`)

## Labour market

### E3: R4's closing step has the opposite sign

- **Spec:** `reference/prototype/spec/00_model_spec.md:127`; `reference/prototype/spec/00_model_spec.md:424`
- **The spec says:** "Longer unemployment → skill decay and exits → smaller senior pool → shortage"
- **What is wrong:** The step that closes the loop has the opposite sign: a shortage shortens unemployment spells. The
  evidence finds exit hazards barely move with spell length (`docs/research/loop-strength-evidence.md:111`), and
  skill erosion acts through hiring and wages (`docs/research/loop-strength-evidence.md:115`).
- **What the model does instead:** A weak threshold multiplier on seeker exits, `1 + a x clamp((Dur - 0.5) / 0.5, 0,
  1)` over its 2024 value, with `a` (`R4a` onshore, `R4aIN` India) at 0 / 0.10 / 0.25 and India at or below onshore
  (`src/aisim/scalar/labour_market.py:331`; `src/aisim/scalar/loops.py:167`; `docs/model-changes-phase9.md:124`)

### E18: No minimum residence time for seeker exits

- **Spec:** `reference/prototype/spec/00_model_spec.md:39`
- **The spec says:** "Every outflow is capped by stock / minimum residence time"
- **What is wrong:** No residence time is named for seeker exits, the outflow that R4 raises.
- **What the model does instead:** `MinSeekTime` (0.25 years) caps R4's exit at `U / MinSeekTime`
  (`src/aisim/scalar/loops.py:176`)

### E20: R6's delay omits the execution delay

- **Spec:** `reference/prototype/spec/00_model_spec.md:129`
- **The spec says:** "Bid cycle, contract duration"
- **What is wrong:** The delay column omits the further 12-18 month delay between a margin signal and the staff change
  (`docs/research/loop-strength-evidence.md:101`).
- **What the model does instead:** The existing `HireAdjTime` (0.5 years) and `LayoffAdjTime` (0.25 years) carry it,
  since C2's cut is executed through openings and layoffs (`src/aisim/scalar/labour_market.py:215`; `src/aisim/scalar/labour_market.py:219`)

### E27: The people stocks omit Retired and include Founders

- **Spec:** `reference/prototype/spec/00_model_spec.md:38`; `reference/prototype/spec/00_model_spec.md:434`
- **The spec says:** "EntrantPipeline, ActiveSeekers, RecoveringIT, Onboarding, Headcount, Founders (extension) or LeftField"
- **What is wrong:** Rule 1 has no Retired stock, though every pool loses people to retirement (line 424), and it lists
  Founders, the start-up extension, which is deferred (line 434) and not built.
- **What the model does instead:** A `Retired` stock (`reference/prototype/spec/02_phase2_build_guide.md:62`) takes
  senior retirement from headcount, recovering staff and seekers; there is no Founders stock
  (`src/aisim/scalar/integrate.py:82`; `src/aisim/scalar/integrate.py:96`)

## Sourcing choice

### E4: B3 is an open chain with an undeveloped staff augmentation effect

- **Spec:** `reference/prototype/spec/00_model_spec.md:132`
- **The spec says:** "outsourced backlog shrinks (staff aug hit hardest)"
- **What is wrong:** An open chain: no link leads back to in-house capability, and "staff aug hit hardest" is not
  developed anywhere.
- **What the model does instead:** Insourcing acts only through the in-house cost term of the sourcing logit (rule 8,
  `reference/prototype/spec/00_model_spec.md:45`): in-house wage cost over client-perceived productivity, plus AI
  cost. There is no effect specific to staff augmentation (`src/aisim/scalar/sourcing.py:104`; `src/aisim/scalar/sourcing.py:158`)

### E14: The win-rate penalty is not the main distress channel

- **Spec:** `reference/prototype/spec/00_model_spec.md:342`; `reference/prototype/spec/06b_phase6b_build_guide.md:172`
- **The spec says:** "Bid win rate falls as viability falls"
- **What is wrong:** The main channel is client flight on relative margin, hitting new bookings first
  (`docs/research/loop-strength-evidence.md:82`). Without a fade, a sustained shortfall compounds to near-exit.
- **What the model does instead:** C4: a vendor's sourcing value falls by `kViab x max(0, s - C4Hab)`, with `s =
  max(0, R6Theta - Vrel)` and `C4Hab` the shortfall smoothed over `C4FadeTime` (2 years); `kViab` 0 / 5.8562 /
  10.6511 reproduces Atos's bookings. The `VendRisk` term of line 172 is kept
  (`src/aisim/scalar/sourcing.py:122`; `src/aisim/scalar/loops.py:69`; `docs/model-changes-phase9.md:97`)

### E19: R7 has no form, strength or stability limit

- **Spec:** `reference/prototype/spec/00_model_spec.md:136`; `reference/prototype/spec/00_model_spec.md:45`; `reference/prototype/spec/00_model_spec.md:386-387`
- **The spec says:** "GCC capability grows → more work moved to GCCs → more scale and capability"
- **What is wrong:** No form, strength or stability limit is given, and the capacity stock with a 1-2 year setup
  (lines 386-387) contradicts rule 8 (line 45), which allows GCC capture only as a logit value term.
- **What the model does instead:** R7: every sector's GCC value gains `kR7 x clamp(ln(WS / WS_2024), -R7Lcap,
  R7Lcap)`, on the economy-wide GCC work share; `kR7` 0.15 / 0.4 / 0.75 (stability `kR7 x (1 - WS_2024) < 0.7`), one
  strength for all sectors, refitted jointly with the GCC trend
  (`src/aisim/scalar/sourcing.py:166`; `src/aisim/scalar/loops.py:91`; `docs/model-changes-phase9.md:53`)

### E21: No calibration target for vendor distress

- **Spec:** none (a new calibration target)
- **The spec says:** nothing: it sets no calibration target for the distress channel.
- **What is wrong:** The obvious datum, an all-cause revenue fall (Atos's organic revenue, -16.2%), is not the
  distress channel's effect.
- **What the model does instead:** The target is distress-attributable revenue against a no-distress counterfactual:
  Atos's booking drop (-21.5%, with renewals at 88%) calibrates `kViab`, and the 16.2% is an upper limit
  (`docs/model-changes-phase9.md:162`; `docs/model-changes-phase9.md:97`)

### E24: The GCCCapacity stock contradicts rule 8

- **Spec:** `reference/prototype/spec/00_model_spec.md:97`; `reference/prototype/spec/00_model_spec.md:386`; `reference/prototype/spec/00_model_spec.md:460`; `reference/prototype/spec/00_model_spec.md:519`; `reference/prototype/spec/06b_phase6b_build_guide.md:32`
- **The spec says:** "GCCCapacity\[Sector\] (positions)"
- **What is wrong:** A capacity stock that caps GCC vacancies (line 386) contradicts rule 8
  (`reference/prototype/spec/00_model_spec.md:45`). The change log supersedes it (line 519), yet the Phase 6 build
  plan (line 460) still lists "GCC capacity", stale against the Phase 6b guide (06b line 32).
- **What the model does instead:** No capacity stock. The GCC's sourcing value carries the GCC appeal ramp
  (`GCCAppeal`), a term rising with consumer AI adoption (`GCCAISens`) and R7
  (`src/aisim/scalar/sourcing.py:164`; `src/aisim/scalar/consumer.py:128`; `src/aisim/scalar/sourcing.py:166`)

## Vendor finance and contracts

### E6: Viability is indexed by employer and by vendor

- **Spec:** `reference/prototype/spec/00_model_spec.md:96`; `reference/prototype/spec/00_model_spec.md:336`
- **The spec says:** "ViabilityIndex[Employer]"
- **What is wrong:** The stock table indexes viability by employer, while the finance section gives the financial
  structure per vendor archetype (line 336). In-house teams and GCCs have no revenue, so no margin.
- **What the model does instead:** Viability is per vendor (`Viab[vendor]`, margin smoothed over `ViabilityTime`), and
  phase 9's relative viability `Vrel` is per vendor too
  (`src/aisim/scalar/integrate.py:114`; `src/aisim/scalar/finance.py:220`; `src/aisim/scalar/loops.py:53`)

### E13: The viability signal is too slow for capacity and client responses

- **Spec:** `reference/prototype/spec/00_model_spec.md:341`
- **The spec says:** "margin smoothed over 2 years"
- **What is wrong:** Two years is too slow for the capacity and client responses; the evidence gives 0.5-1.0 years
  (`docs/research/loop-strength-evidence.md:101`).
- **What the model does instead:** A separate signal, `VMarg`, smoothed over `R6MargTime` (0.75 years), feeds C2 and
  C4 through `Vrel`; the 2-year index is kept for its existing uses
  (`src/aisim/scalar/loops.py:205`; `src/aisim/scalar/loops.py:53`; `src/aisim/scalar/integrate.py:114`)

### E15: The price floor's cost is undefined and has no value

- **Spec:** `reference/prototype/spec/00_model_spec.md:44`
- **The spec says:** "new-bid price ≥ the vendor's delivery cost"
- **What is wrong:** "Delivery cost" is undefined (current or expected), and the floor has no value.
- **What the model does instead:** C5: each new-bid price is at least `PriceFloor` (0.85 / 1.00 / 1.08) times the
  vendor's expected cost per unit, its cost index smoothed over the book's duration (`ECost`), times `Pe` for effort
  types (`src/aisim/scalar/finance.py:245`; `src/aisim/scalar/loops.py:108`; `src/aisim/scalar/loops.py:206`)

### E16: The AI-discount ceiling has no value

- **Spec:** `reference/prototype/spec/00_model_spec.md:44`; `reference/prototype/spec/00_model_spec.md:255`; `reference/prototype/spec/00_model_spec.md:283`
- **The spec says:** "expected AI discount ≤ a ceiling"
- **What is wrong:** No value is given for the ceiling, here or in the pricing sections (lines 255 and 283).
- **What the model does instead:** C6: the client's AI discount, `1 - Anchor`, is at most `AIDiscCeil` (0.20 / 0.30 /
  0.45), applied after noise; the realised book deflation of about -3 to -3.5% a year is a calibration check
  (`src/aisim/scalar/finance.py:216`; `src/aisim/scalar/loops.py:99`; `docs/model-changes-phase9.md:110`)

### E17: R10 is a choice loop with an undefined attrition rate

- **Spec:** `reference/prototype/spec/00_model_spec.md:145`; `reference/prototype/spec/00_model_spec.md:444`
- **The spec says:** "GCC wage premium → vendor attrition up → delivery strain and replacement cost up → weaker vendor bids → more work to GCCs"
- **What is wrong:** The evidence shows costs and capacity limits but no client switching
  (`docs/research/loop-strength-evidence.md:54`). Attrition and its reference are undefined, and 2024 is a trough
  (`docs/research/loop-strength-evidence.md:72`).
- **What the model does instead:** R10 is a cost only: vendor cost gains `R10rc` (0.0748 / 0.1816 / 0.3223 years of
  wage) per voluntary exit above the 2024 rate, voluntary exits being quits, leaving the field and switch-outs
  (`src/aisim/scalar/finance.py:341`; `src/aisim/scalar/loops.py:117`; `src/aisim/scalar/loops.py:142`)

### E33: Licensing and managed are each used twice

- **Spec:** `reference/prototype/spec/00_model_spec.md:59`; `reference/prototype/spec/00_model_spec.md:89`; `reference/prototype/spec/00_model_spec.md:204`; `reference/prototype/spec/00_model_spec.md:291`; `reference/prototype/spec/00_model_spec.md:293`; `reference/prototype/spec/00_model_spec.md:338`
- **The spec says:** "Fixed price, T&M, Support, Staff augmentation, Licensing, Outcome-based / managed (proposed)"
- **What is wrong:** Licensing is a vendor contract type (lines 59, 89, 293, 338) and also seat-based licensing on the
  platform side (line 204); "managed" appears both in "Support / managed" (line 291) and in "Outcome-based / managed
  (proposed)" (line 59).
- **What the model does instead:** No licensing contract type (`reference/prototype/spec/05_phase5_build_guide.md:27`):
  five types, fixed price, T&M, managed services (support), staff augmentation and outcome-based, kept separate; seat
  licensing is the consumers' seat spend (`src/aisim/dims.py:29`; `src/aisim/scalar/finance.py:203`; `src/aisim/scalar/consumer.py:205`)

## Whole model

### E25: Resolved open decisions are still marked open

- **Spec:** `reference/prototype/spec/00_model_spec.md:503`; `reference/prototype/spec/00_model_spec.md:504`
- **The spec says:** "[ ] Keep outcome-based / managed service as its own contract type, or merge it into Support? Resolved in Phase 5"
- **What is wrong:** Both decisions are marked open ("[ ]"), though each line says it was resolved, in Phase 5 and
  Phase 4.
- **What the model does instead:** It treats both as resolved: outcome-based is its own contract type, and wages are
  endogenous with the switch `WagesEndogenous` (`src/aisim/dims.py:29`; `src/aisim/scalar/finance.py:399`)

### E26: The module counts disagree

- **Spec:** `reference/prototype/spec/00_model_spec.md:82`; `reference/prototype/spec/00_model_spec.md:76`; `reference/prototype/spec/00_model_spec.md:86-98`
- **The spec says:** "Ten modules hold about 24 stock families"
- **What is wrong:** Line 82 says ten modules, the module map (line 76) says 9 modules shown, and the stock table has
  13 rows (lines 86-98).
- **What the model does instead:** It follows the build guides: the step runs the prototype's sections S1-S13, ported
  as eight engine modules, from capability to finance (`src/aisim/scalar/step.py:6`)

### E34: Named quantities without a definition or value

- **Spec:** `reference/prototype/spec/00_model_spec.md:238`; `reference/prototype/spec/00_model_spec.md:277`; `reference/prototype/spec/00_model_spec.md:212`; `reference/prototype/spec/00_model_spec.md:192`; `reference/prototype/spec/00_model_spec.md:90`; `reference/prototype/spec/00_model_spec.md:92`; `reference/prototype/spec/00_model_spec.md:97`
- **The spec says:** "p_{eff} = p \cdot f\left(\frac{\text{LabourCostPerUnit}}{\text{AICostPerUnit}}\right)"
- **What is wrong:** These quantities are undefined or unquantified: `LabourCostPerUnit` and `f` (line 238),
  `VendorPower` (277), `CreditsPerUnit` and `CreditPrice` (212), `LOBAutomationShare` and `BaseNewAppDemand` (192),
  the bench (90), skill decay (92), and the onsite cost, win-rate penalty and GCC setup attractiveness (97).
- **What the model does instead:** Values come from the build guides and the Phase 7 fit; the Phase 1-6 values were
  illustrative (`reference/prototype/spec/08_sources.md:3`). Every parameter is read from the selected model's
  baseline file (`src/aisim/params.py:138`; `src/aisim/state.py:130`)

## Counts

| Module | Entries |
| --- | --- |
| AI capability | 2 |
| Delivery AI adoption | 3 |
| Client demand and consumer AI | 7 |
| Work and productivity | 3 |
| Workforce planning | 3 |
| Labour market | 4 |
| Sourcing choice | 5 |
| Vendor finance and contracts | 6 |
| Whole model | 3 |
| Total | 36 |
