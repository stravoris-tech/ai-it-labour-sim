# Phase 9: four feedback loops from outside evidence

`phase9` is `phase8` plus four feedback loops that the model specification names but earlier models did not close:
R7 (GCC scale learning), R6 (vendor capacity exit, client flight and two price rules), R10 (attrition cost) and R4
(skill erosion). Each loop is set at the base strength of an outside evidence report, and all 11 calibrated
parameters are refitted with the loops in place.

`phase9` is the library default since slice 14 (`aisim.state.DEFAULT_MODEL`), after the Q05 first-look analysis;
`phase8` stays registered as the earlier, loop-free structure.

Every loop is an extension parameter whose strength defaults to 0, which turns it off. With every strength at 0 the
engine reproduces every earlier model bit for bit: `phase7` against the prototype, and `phase8` and
`phase8_highadoption` against their goldens.

## Why the loops were added

A gap review compared the specification with the engine, link by link. It found loops that the specification
describes but the engine leaves open. The largest by effect was R7: the GCC wave alone decides the split of work
between vendors and GCCs, and over the range of `GCCAppealKeep` the 2040 GCC headcount moves by 60 points while total
headcount moves by 0.1. The next were B8 (political pressure on visa policy), R4 (skill erosion) and R10 (talent
poaching). R6 existed only in part: margin fed a viability index and a risk term, but not capacity or prices.

Prototypes of these loops showed something important for the model's design: the 2024-2026 calibration data
constrain none of their strengths. For each loop, the calibration loss rose with the strength without a refit, and a
single refit brought it back to the `phase8` level by moving the parameters that carry the same channel. The data
cannot choose a strength, so the strengths came from outside evidence:
[`research/loop-strength-evidence.md`](research/loop-strength-evidence.md) (the evidence report below). Phase 9
closes R7, R6, R10 and R4. B8 stays a scenario input (see "What was left out").

## Common rules

- **Off at 0.** One strength parameter per term; at 0 the term is not evaluated into the step. The shape parameters
  (caps, thresholds, time constants) hold their base values and are inert while their strength is 0.
- **Neutral at 2024.** Every term is zero, or a ratio of 1, at the calibrated 2024 state, so the 2024 row of a run
  with any loop on is bit-equal to the run without it. A loop that reads an absolute level (R4's spell length, R10's
  attrition rate, R7's work share) is normalised by its own 2024 value.
- **References and signals are stock families.** The 2024 references and the smoothed signals are six new state
  families: `WS0`, `ECost`, `Attr0` and `Dur0` (filled on the first step) and `VMarg` and `C4Hab` (smoothed
  signals). They are carried through a restart, so a two-phase run (`perturb_from`) is exact.
- **No new numerics.** The terms use only operations the engines already use; R7's logarithm is the pair the
  engines already use for the GCC momentum tilt. The batched engine matches the scalar engine on every loop.
- **Integrity.** R4 adds to an outflow, so it is capped by the seeker stock over a minimum residence time
  (`MinSeekTime`), as integrity rule 2 of the specification requires.
- **Outputs.** Four new extras make the loops visible: `Vrel_<v>` (relative viability), `ClientFlight_<v>` (the
  client-flight term), `GCCScaleTerm` (the R7 term) and `VoluntaryAttrition_<v>` (voluntary exits per head over
  their 2024 value). They are recorded for every model, at 1 or 0 where the loops are off.

## The loops

The ranges below are the evidence report's, by section, with the translations of the loop recons (12 and 12b) where
the report gives a behaviour rather than a number.

### R7: GCC scale learning

**Mechanism.** As GCCs take a larger share of IT work, the next GCC is easier to set up and run: deeper talent
pools, setup playbooks and providers. The report finds centres set up since FY21 take under 5 years to mature,
against 5-10 years for those of 2002-2015, while the GCC base roughly doubled.

**Form.** Every sector's GCC sourcing value gains `kR7 x clamp(ln(WS / WS_2024), -R7Lcap, R7Lcap)`. `WS` is the
economy-wide GCC work share, the recorded `WorkShare_GCC` (0.0984 in 2024). The logarithm makes the term concave, as
the report recommends, and the cap is its stability cap. The term can reverse: below its 2024 share the GCC loses
value, as captives were sold back to vendors in 2008-2009.

**Parameters.** `kR7` 0.15 / 0.4 / 0.75 (low / base / high) and `R7Lcap` 1.0. The report's high is 0.8, but it also
asks that `kR7 x (1 - WS_2024)` stay below 0.7, so no sweep lands near tipping: at 0.8 that measure is 0.721, at 0.75
it is 0.676. Values above 1.0 are rejected by validation, as the report rejects them. In `phase9`'s Base run the cap
binds from 2032.

**The cap.** `R7Lcap` 1.0 is a design judgement with no evidence range. The report asks for a cap "to reflect
talent-pool and wage-inflation limits" but calls its level "a design judgement, not a sourced number" (recon 13, A1).
- **It is not a stability device in the log form.** The loop gain `kR7 x (1 - WS)` is largest at the 2024 share,
  where the cap never binds: 0.676 at `kR7` 0.75, inside the report's 0.7. It falls as the share rises, and the
  uncapped term is bounded anyway, by `kR7 x ln(1 / WS_2024)` = 2.32 x `kR7` (recon 13, A1).
- **It binds from about 2032:** first from 2031.1 to 2033.6, across the six scenarios recon 13 A2 ran (Base, Fast AI,
  Slow AI, the two GCC waves and the stress set) at the three strengths; it never binds in GCC wave fades at `kR7`
  0.15 (recon 13, A2).
- **At base strength it trims little.** It cuts the 2040 term from 0.474 to 0.400 logit units, about 1% on the 2040
  headlines in Base: lifting it moves VendorHead by -0.89%, Head_GCC by +1.44% and RevenueTot by -0.94% (recon 13,
  A2).
- **At the high strength it matters more.** At `kR7` 0.75, lifting it would move 2040 VendorHead by 3.6% in Base and
  by 6.6% in GCC wave persists (recon 13, A2).
- **It leaves the calibration window alone.** Every row to 2030 is bit-identical across caps from 1.0 to 10, and the
  calibration loss at `phase9`'s fitted values is the same at every cap (recon 13, A3).
- **It barely moves the Monte Carlo.** A cap of 1.25 moves the 2040 medians by at most 2.3%, and caps of 1.5 and above
  are within 0.1% of no cap (recon 13, A4).

### R6: vendor stress

All four R6 terms read **relative viability**, `Vrel = VMarg / NormalMargin`: the vendor's margin smoothed over 0.75
years (`R6MargTime`), as the report asks (0.5-1.0 years), over its normal margin. `Vrel` is 1 in 2024. The 2-year
viability index the engine already had is unchanged for its existing uses.

- **C2, capacity exit.** Below the threshold `R6Theta`, the vendor cuts its desired staff by `min(R6Cap, R6e x margin
  points below the threshold)`. The cut executes through the existing openings and layoffs logic, mostly as reduced
  hiring. Ranges: `R6Theta` 0.65 / 0.80 / 0.92 and `R6e` 0.002 / 0.005 / 0.012 per point, with `R6Cap` 0.08 (the
  report: cuts start on relative shortfall at healthy margins and run 1-4% of headcount).
- **C4, client flight.** Below the same threshold the vendor loses sourcing value, `kViab x max(0, s - C4Hab)` logit
  units, where `s = max(0, R6Theta - Vrel)` is the shortfall and `C4Hab` is the shortfall smoothed over `C4FadeTime`
  (2 years). The fade means clients stop leaving once the distress is habituated: under constant distress the term
  decays. `kViab` 0 / 5.8562 / 10.6511 reproduces Atos's bookings: OIT's signings at its viability trough fall 21.5%
  against the run without the term (Atos's book-to-bill fell from 93% to 73% while renewals held at 88%), at troughs
  of 0.25 (base) and 0.47 (high). `C4Cap` (0 = no cap) limits the size of client flight, and `C4FadeTime` sets its
  persistence. In the stress set (Fast AI plus a 20% OIT price shock), the term peaks at 2.07 logit units. A cap of
  1.0 lessens the loss (OIT at 0.946 / 0.876 / 0.954 of its no-distress revenue after 2, 5 and 12 years, against
  0.939 / 0.852 / 0.944 with no cap), and a cap of 2.0 or more changes nothing. With the fade made inert
  (`C4FadeTime` 1,000 years), the loss persists: 0.938 / 0.755 / 0.545. A stress test of persistent client flight
  therefore lengthens `C4FadeTime`, not the cap.
- **C5, price floor.** Each new-bid price is at least `PriceFloor` times the vendor's expected delivery cost per unit
  (its cost index smoothed over the book's duration): 0.85 / 1.00 / 1.08.
- **C6, AI-discount ceiling.** The AI discount a client can extract, `1 - Anchor`, is at most `AIDiscCeil`: 0.20 /
  0.30 / 0.45 (the report: client asks run at 20-30%).

### R10: attrition cost

**Mechanism.** The 2022 attrition spike, at 1.6-2.3 times the 2024 level, coincided with the best growth year in a
decade. Its documented effects were replacement cost and capacity limits, not clients switching vendors.

**Form.** Vendor cost gains `R10rc x wage x voluntary exits x max(0, 1 - VA_2024 / VA)`, where voluntary exits are
quits, leaving the field and switches to another employer, and `VA` is voluntary exits per head. `R10rc` is in years
of wage per excess exit: 0.0748 / 0.1816 / 0.3223, which costs OIT 100, 150 and 200 bps of margin at a
voluntary-attrition ratio of 2.3, 1.8 and 1.6 (the report's 100-200 bps per doubling). In Base the ratio peaks at
1.01, so the cost acts only when attrition itself spikes.

### R4: skill erosion

**Mechanism.** The report finds that the hazard of leaving the labour force barely moves with spell length and falls
in slumps, so skill erosion is weak and belongs inside a threshold-saturation form.

**Form.** A seeker's exit rate is multiplied by `1 + a x clamp((Dur - 0.5) / 0.5, 0, 1)` over its 2024 value, where
`Dur` is the expected spell length, and the exit is capped at `U / MinSeekTime`. `R4a` (onshore) and `R4aIN` (India)
are 0 / 0.10 / 0.25; India is at or below onshore, and both are 0.10 in `phase9`.

### Parameters

| Loop | Strength (0 = off) | Shapes (default) | Low / base / high |
| --- | --- | --- | --- |
| R7 | `kR7` | `R7Lcap` 1.0 | 0.15 / 0.4 / 0.75 |
| R6 C2 | `R6e` | `R6Theta` 0.80, `R6Cap` 0.08, `R6MargTime` 0.75 | `R6e` 0.002 / 0.005 / 0.012; `R6Theta` 0.65 / 0.80 / 0.92 |
| R6 C4 | `kViab` | `C4FadeTime` 2.0, `C4Cap` 0 (none); shares `R6Theta` | 0 / 5.8562 / 10.6511 |
| R6 C5 | `PriceFloor` | none | 0.85 / 1.00 / 1.08 |
| R6 C6 | `AIDiscCeil` | none | 0.20 / 0.30 / 0.45 |
| R10 | `R10rc` | none | 0.0748 / 0.1816 / 0.3223 |
| R4 | `R4a`, `R4aIN` | `MinSeekTime` 0.25 | 0 / 0.10 / 0.25 |

No new parameter describes 2024 itself, since every term is neutral there, so every one can vary from any perturb
year.

## What the evidence showed against the specification

- **R6's AI investment runs the other way.** The specification says margin pressure means less AI investment. The
  evidence shows AI investment rising under margin pressure (Accenture, Cognizant, TCS, Capgemini; Atos raised capex
  with negative free cash flow). This is a correction to the specification, not a gap: vendor adoption in the engine
  does not read margin, so no rule is added.
- **R6's capacity exit starts on relative shortfall,** at healthy margins, not on absolute distress, and runs mostly
  through reduced hiring.
- **R6's signal is faster.** Margin should be smoothed over 0.5-1.0 years for these responses, not the 2 years of the
  viability index.
- **R6's main channel is client flight,** not excess layoffs, and client flight fades once a vendor stabilises:
  without the fade, a sustained shortfall compounds to near-exit (a single-vendor price shock drove the vendor to a
  tenth of its business by 2040). With the 2-year fade a permanently distressed vendor settles about 10% below its
  no-distress path.
- **The distress calibration target is attributable revenue.** Atos's 16.2% organic revenue fall is all-cause. The
  distress channel is its bookings drop, so the target is revenue against a no-distress counterfactual; the 16.2% is
  an upper limit, not a target.
- **R10 is a cost, not a choice term.** The 2022 spike left costs and capacity limits but no client defections.
- **R10's attrition is total voluntary exits,** and its 2024 anchor is a trough, so the cost is negligible in Base.
- **R4 is a threshold,** weak, with India at or below onshore, and its added exit needs a minimum residence.
- **R7 is driven by economy-wide GCC scale,** with one strength for every sector (the per-sector form gives the same
  results within 0.2 points), concave and capped, and refitted jointly with the exogenous GCC trend.
- **The price rules get values:** a floor on new-bid prices at expected cost and a ceiling on the AI discount. The
  realised book deflation stays a calibration check (about -3% a year for OIT).

## What was left out, and why

- **The AI-investment rule (C3).** The evidence reverses the specification's sign, and the engine already behaves as
  the evidence does: vendors keep adopting AI under stress.
- **R10's choice term.** A small penalty on vendor choice for high attrition was prototyped. The evidence documents
  no client switching, so R10 is a cost only.
- **B8, political pressure on visa policy.** It stays a scenario input: visa tightness is an exogenous index whose
  path the visa scenarios set, as the specification's policy lever does.
- **A cap on client flight.** A cap alone limits the speed of client flight but not its duration, so a sustained
  shortfall still compounds. The fade alone is used. The cap stays as a parameter (`C4Cap`, off) that limits the size
  of client flight; persistence is set by `C4FadeTime`.
- **Sector-specific R7 strengths.** One national driver and one strength, since the data cannot separate them.

## The refit

`phase9` sets every loop at its base value (spec `tools/models/phase9/spec.json`) and refits phase 8's 11 calibrated
parameters with the same settings as `phase8`: 32 Latin hypercube starts (seed 20261016), tolerance 1e-10,
difference step 1e-3, `PriceHorizon` in [0, 7], and phase 8's design held fixed (`tools/models/phase9/fit.json`).

- **Loss** 0.000421, 0.995 of `phase8`'s 0.000423: the loops cost the fit nothing. 28 of the 32 starts land within
  5% of the best.
- **What absorbs the loops.** `GCCAppealEnd` falls 12.6% (2.695 to 2.355): R7 now carries part of the GCC trend, as
  the report asks of a joint refit. `SeekerExitRate` falls 1.9% (R4) and `AICost2024` rises 1.2%. Every other
  parameter moves less than 1%.
- **Checks.** The four calibration cores stay in band (OIT's book price drift -2.96% a year, as `phase8`), `A_mean`
  in 2030 is 0.904, and the 2024 row differs from `phase8`'s only through the refitted parameters. Integrity holds in
  Base and `EXTREME`, and with every strength at its high value.

## What the loops change

Base, against `phase8`:

| Quantity | 2030 | 2040 | 2040 without the refit |
| --- | --- | --- | --- |
| `HeadTotal` | +0.05% | -0.03% | +0.00% |
| `VendorHead` | +0.07% | -3.24% | -8.86% |
| `Head_GCC` | -0.00% | +5.56% | +16.10% |
| `Head_OIT` | +0.06% | -4.13% | -11.93% |
| `RevenueTot` | +0.07% | -3.31% | -8.61% |
| `WorkShare_GCC` | -0.56% | +6.72% | +17.63% |

- **The loops move the split, not the total.** Total IT headcount is unchanged; by 2040 work and staff shift from
  vendors to GCCs, and vendor revenue falls with them. R7 carries most of it.
- **The refit absorbs two thirds of R7 by 2040.** Without it, the loops on top of a GCC trend fitted to history
  overshoot (VendorHead -8.9% against -3.2%). This is the report's reason for a joint refit.
- **No single-vendor collapse.** Under a 20% price shock on one vendor from 2028, the vendor's revenue against the
  same run without the distress terms is 0.79 (BQ) and 0.93 (OIT) two years after distress begins, 0.66 and 0.85
  after five, and 0.94 and 0.88 in 2040. Without the fade, the same shock took BQ to about a tenth.

## The Fast AI price-rule result

In the model's fastest-AI scenario, vendor margins rise rather than fall, but only if clients cannot extract more than
about a 30% AI discount on new contracts. OIT's 2040 margin is about 25% at a 30% ceiling, 27% at 20%, and 19-20% at
45%, which is no higher than with no ceiling at all. Across 1,000 uncertain runs from mid-2026 it is 18-27% (p10-p90,
median 23%), and the ceiling binds by 2035 in about 6 runs in 10. The ceiling also shifts vendor books toward
fixed-price work (an effort-billed revenue share of about 17% against 24%), while moving little work to GCCs or
in-house teams (recon 13, B5).

**The result rests on the ceiling's value.** `AIDiscCeil` 0.30 comes from current client asks (20-30%), not from
calibration data, which do not pin the loop strengths (see "Limitations"). In Fast AI the ceiling first binds in 2030.

**How it works** (recon 13, B1).
- **The ceiling holds the anchor up.** As AI raises client productivity, the anchor that new prices follow falls. C6
  holds it at 0.70 (`1 - AIDiscCeil`), so new fixed prices stay higher (OIT's FP price 0.630 against 0.567 without
  the ceiling in 2040).
- **That shifts the book toward fixed-price work.** Fixed types become more profitable to sign, so the effort-billed
  share of new signings falls from 0.445 to 0.324, and the book follows.
- **C6 alone accounts for it.** With C6 off, the effort share returns to `phase8`'s; with C5 off it barely moves.

**By ceiling value.** Deterministic runs from 2024 on `phase9`, Fast AI, 2040, with no refit (recon 13, B2). The bold
row is `phase9` as shipped.

| `AIDiscCeil` | `PriceFloor` | Margin OIT / GSI / BQ | Effort share (revenue-weighted) | `RevenueTot` (USD bn) | `VendorHead` | C6 first binds (OIT) |
| --- | --- | --- | --- | --- | --- | --- |
| 0.20 | 0.85 | 0.274 / 0.254 / 0.226 | 0.101 | 4.043 | 25,413 | 2028.06 |
| 0.20 | 1.00 | 0.273 / 0.254 / 0.224 | 0.138 | 3.989 | 25,105 | 2028.06 |
| 0.20 | 1.08 | 0.273 / 0.254 / 0.223 | 0.181 | 3.967 | 24,985 | 2028.06 |
| 0.30 | 0.85 | 0.251 / 0.226 / 0.196 | 0.162 | 3.842 | 24,876 | 2030.38 |
| **0.30** | **1.00** | **0.251 / 0.227 / 0.197** | **0.166** | **3.865** | **25,023** | **2030.38** |
| 0.30 | 1.08 | 0.245 / 0.221 / 0.201 | 0.207 | 4.020 | 26,187 | 2030.38 |
| 0.45 | 0.85 | 0.188 / 0.200 / 0.170 | 0.239 | 3.694 | 24,754 | never |
| 0.45 | 1.00 | 0.191 / 0.201 / 0.170 | 0.237 | 3.749 | 25,284 | never |
| 0.45 | 1.08 | 0.201 / 0.192 / 0.172 | 0.255 | 4.027 | 27,197 | never |

- **The ceiling sets the margin;** the floor moves it by at most 0.013. At 0.45 the ceiling never binds, and OIT's
  margin is within 0.007 of `phase8`'s 0.195.
- **The floor moves the effort share** (+0.02-0.04 at 1.08 against 1.00) and, at 1.08, revenue and vendor headcount.
- **In Slow AI neither rule binds** at any of these values.

**The Monte Carlo band.** `run_scenarios` on the 1,000-run design of the structural levers' Monte Carlo (Latin
hypercube, seed 20261017, from 2026.5, 21 levers), with the Fast AI block pinning `g` and `VerifDecline`, 0 invalid
runs (recon 13, B3):

| Quantity (2040) | Baseline p10 / median / p90 | Fast AI p10 / median / p90 |
| --- | --- | --- |
| `Margin_OIT` | 0.166 / 0.189 / 0.232 | 0.175 / 0.226 / 0.266 |
| `Margin_GSI` | 0.166 / 0.192 / 0.219 | 0.187 / 0.218 / 0.245 |
| `Margin_BQ` | 0.156 / 0.164 / 0.188 | 0.168 / 0.187 / 0.214 |
| Effort share (revenue-weighted) | 0.205 / 0.278 / 0.327 | 0.133 / 0.197 / 0.247 |
| `RevenueTot` (USD bn) | 3.64 / 4.55 / 5.84 | 3.28 / 4.05 / 5.07 |
| `VendorHead` | 25,878 / 32,027 / 40,330 | 21,899 / 26,943 / 32,939 |

- **How often C6 binds:** for some vendor by 2035 in 59.2% of the Fast AI runs, and by 2040 in 70.6%. The extras
  `AIDiscCeilBinds_<v>` record it.
- **`AIDiscCeil` decides it.** Its Spearman rho with the 2040 margins is -0.81 to -0.95, and with binding by 2035 it is
  -0.83. The next is `PriceHorizon` (+0.12), and every other lever is under 0.07 in absolute value.

## The stress set

`aisim.scenarios.STRESS_SCENARIOS` holds one named override set, "Fast AI + OIT price shock": Fast AI (`g` 0.20,
`VerifDecline` 0.10) plus a 20% price shock on OIT from `PriceShockYear` (2028). It is an explicit opt-in, like
`EXTREME`: it is not in `SCENARIOS`, so no scenario count, chart default or golden changes. `run_experiment` and
`run_scenarios` accept its name like a scenario's.

**What it is for.** It is the smallest set of overrides in which all seven phase 9 terms act (Q05, B3). No scenario
does so alone: Fast AI has C5 and C6 but not C2 or C4, and a price shock has C2 and C4 but not C5 or C6. A regression
test pins every term's onset in it (`tests/test_loops.py`). The onsets, on `phase9` from 2024, are:

| Term | Onset | Active | Vendors |
| --- | --- | --- | --- |
| R7 | 2024.06 | to 2040; at the cap 2032-2040 | economy-wide |
| R10 | 2024.06 | to 2040 | all |
| R4 | 2024.75 | to 2040 | IN and ON pools |
| C5 | 2028.0 | to 2040 | GSI, BQ |
| C2 | 2028.25 | to 2039.06 | OIT |
| C4 | 2028.25 | to 2034.94 | OIT |
| C6 | 2030.375 | to 2040 | OIT, GSI, BQ |

**Headlines against Base** (`phase9`, deterministic from 2024; Q05, B3):

| Quantity | 2026 | 2030 | 2035 | 2040 |
| --- | --- | --- | --- | --- |
| `HeadTotal` | -1.6% | -13.2% | -19.9% | -20.6% |
| `VendorHead` | -1.8% | -14.5% | -26.6% | -25.2% |
| `Head_GCC` | -0.6% | -10.8% | -14.7% | -19.8% |
| `RevenueTot` | -1.0% | -16.0% | -18.7% | -16.6% |
| `Head_OIT` | -1.4% | -18.9% | -46.2% | -44.0% |

- **Most of the gap is the scenario's own inputs.** Faster AI and the price shock drive it. The loops together offset
  about a quarter of the revenue gap and a twelfth of the vendor headcount gap, and add about an eighth to the GCC gap.
- **OIT's distress stays inside the envelope.** OIT's revenue against the run without C2 and C4 is 0.939, 0.852 and
  0.944 two, five and twelve years after distress begins, inside recon 12b's [0.48, 1.0].

## The structural levers

The strengths are not pinned by the calibration data, so their uncertainty enters a Monte Carlo through structural
levers. `tornado_levers(model="phase9")` (`aisim.scenarios`) appends to the model's 14 tornado levers the eight
strengths with the ranges above: `kR7`, `R6Theta`, `R6e`, `kViab`, `PriceFloor`, `AIDiscCeil`, `R10rc` and `R4a`
(`aisim.scenarios.STRUCTURAL_LEVERS`). Every other model's levers are unchanged.

A 1,000-run Latin hypercube from 2026.5 (seed 20261017) over these 21 levers (`Verif` cannot vary after 2024) has no
invalid run. Its 2040 bands, p10 / median / p90:

| Quantity (2040) | p10 | Median | p90 |
| --- | --- | --- | --- |
| `HeadTotal` | 70,980 | 84,830 | 102,600 |
| `VendorHead` | 25,880 | 32,030 | 40,330 |
| `Head_GCC` | 19,660 | 27,160 | 37,690 |
| `RevenueTot` (USD bn) | 3.64 | 4.55 | 5.84 |
| Revenue-weighted effort share | 0.205 | 0.278 | 0.327 |

In the loop recon's measurement the eight strengths explained none of the band width of total or vendor headcount,
about 7% of the GCC headcount band (mostly `kR7`), and 14-21% of the bands of the effort share and the vendor margins
(mostly `AIDiscCeil`).

## `phase9_highadoption`

**What it is.** `phase9` with the adoption parameter `p` fixed at Phase 7's 0.044, and the other 10 calibrated
parameters refitted (`tools/models/phase9_highadoption/`). It is to `phase9` what `phase8_highadoption` is to
`phase8`: the like-for-like adoption-speed alternative. It has the same loops at the same base values, and so the same
eight structural levers.

**Its fit.** `phase9`'s settings: 32 Latin hypercube starts (seed 20261016), tolerance 1e-10, difference step 1e-3,
`PriceHorizon` in [0, 7], and `phase9`'s fixed values plus `p`.
- **Loss** 0.000748, 0.9992 of `phase8_highadoption`'s. 31 of the 32 starts land within 5% of the best.
- **What absorbs the loops**, against `phase8_highadoption`: as in `phase9`, `GCCAppealEnd` falls 11.8% (2.865 to
  2.528), `SeekerExitRate` falls 1.5% and `AICost2024` rises 0.9%. Every other parameter moves less than 0.3%.
- **Checks.** The four calibration cores stay in band (OIT's book price drift -3.23% a year, as
  `phase8_highadoption`). `A_mean` is 0.853 in 2028 and 0.958 in 2030 (`phase8_highadoption`: 0.853 and 0.957). The 2024 row
  differs from `phase9`'s only through the refitted parameters. Integrity holds in Base and `EXTREME`, and with every
  strength at its high value (T1 0.0089 and 0.0091).

**Like-for-like.** The adoption effect is each high-adoption model against its own base model, in 2040 (% for levels,
points for shares; deterministic from 2024; recon 13, C3):

| Scenario | Quantity | `phase8_highadoption` - `phase8` | `phase9_highadoption` - `phase9` | `phase8_highadoption` - `phase9` |
| --- | --- | --- | --- | --- |
| Base | `HeadTotal` | +0.27% | +0.25% | +0.30% |
| Base | `VendorHead` | -1.92% | -2.21% | +1.36% |
| Base | `Head_GCC` | +4.96% | +5.03% | -0.57% |
| Base | `Head_OIT` | -2.75% | -3.27% | +1.45% |
| Base | `RevenueTot` | -2.58% | -2.84% | +0.76% |
| Base | `WorkShare_GCC` | +1.39 pt | +1.50 pt | -0.60 pt |
| Fast AI | `VendorHead` | -1.42% | -1.33% | +0.81% |
| Fast AI | `RevenueTot` | -2.09% | -2.21% | -3.45% |
| Fast AI | `Margin_OIT` | +0.31 pt | +0.17 pt | -5.28 pt |
| Slow AI | `VendorHead` | -2.53% | -3.11% | +0.69% |
| Slow AI | `Head_OIT` | -3.95% | -5.45% | -0.11% |
| any | `A_mean` 2030 | +5.34 pt | +5.35 pt | |

- **Within each pair the adoption effect agrees** in sign and nearly in size: the gaps are 0.02-0.6 points, and 1.5
  points for Slow AI's `Head_OIT`.
- **Across the pairs it does not.** `phase8_highadoption` against `phase9` mixes the adoption effect with the loops'
  effect: it has the wrong sign for `VendorHead`, `Head_GCC` and revenue in Base, and a 5.3-point margin gap in Fast AI.

**When to use it.** For a question that depends on adoption speed under `phase9`, compare `phase9` with
`phase9_highadoption`, never with `phase8_highadoption`. `p` and the 2024 levels it moves cannot change under
`perturb_from`, so the comparison has to be between models, as it is for `phase8`.

## Limitations

- **The strengths come from translations, not estimates.** No econometric estimate of any of these parameters
  exists. Each range translates case data, flow statistics and industry series into model units (R7's attribution
  fraction, C4's Atos mapping, R10 at OIT's margin), and each translation is a judgement.
- **The calibration data do not pin the strengths.** The 2024-2026 targets are matched equally well with the loops on
  or off, so the base values are the evidence's, and their uncertainty enters only through the structural levers.
  With `perturb_from`, the levers act from the perturb year; before it, every run is at the base values.
- **Several terms are quiet in Base.** C2, C4, C5 and C6 never act in `phase9`'s Base run: OIT's relative viability
  bottoms at 0.82, above the 0.80 threshold, and neither price rule binds. R10 and R4 are small. They matter under
  stress (price shocks, attrition spikes, deep AI deflation), which is what they are for.
  - **That holds at the base values.** Within their ranges the price rules can act in Base: C6 at `AIDiscCeil` 0.20
    (from 2031.25, when it lifts OIT's 2040 margin to 0.228) and C5 at `PriceFloor` 1.08 (from 2026.44) (recon 13,
    B2).
- **Fast exits are out of reach.** Satyam's months-scale exodus needs a renewal channel that a sourcing logit on
  contested turnover cannot give.
- **R7's high is set by a stability rule,** not by the evidence's own high, and the term binds at its cap from the
  early 2030s.
