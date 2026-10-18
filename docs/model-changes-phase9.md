# Phase 9: four feedback loops from outside evidence

`phase9` is `phase8` plus four feedback loops that the model specification names but earlier models did not close:
R7 (GCC scale learning), R6 (vendor capacity exit, client flight and two price rules), R10 (attrition cost) and R4
(skill erosion). Each loop is set at the base strength of an outside evidence report, and all 11 calibrated
parameters are refitted with the loops in place.

`phase9` is a registered model, not the default: `Experiment(model="phase9")` or `Params.baseline("phase9")` selects
it, and the library default stays `phase8`. A first-look analysis comes before any change of default.

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
  of 0.25 (base) and 0.47 (high). `C4Cap` (0 = no cap) remains for stress tests of persistent client flight.
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
  shortfall still compounds. The fade alone is used, with the cap kept as a parameter (`C4Cap`, off) for stress tests.
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

## Limitations

- **The strengths come from translations, not estimates.** No econometric estimate of any of these parameters
  exists. Each range translates case data, flow statistics and industry series into model units (R7's attribution
  fraction, C4's Atos mapping, R10 at OIT's margin), and each translation is a judgement.
- **The calibration data do not pin the strengths.** The 2024-2026 targets are matched equally well with the loops on
  or off, so the base values are the evidence's, and their uncertainty enters only through the structural levers.
  With `perturb_from`, the levers act from the perturb year; before it, every run is at the base values.
- **Several terms are quiet in Base.** C2, C4, C5 and C6 never act in `phase9`'s Base run: OIT's relative viability
  bottoms at 0.82, above the 0.80 threshold, and neither price rule binds. R10 and R4 are small. They matter under stress (price shocks, attrition spikes, deep AI deflation), which is what they
  are for.
- **Fast exits are out of reach.** Satyam's months-scale exodus needs a renewal channel that a sourcing logit on
  contested turnover cannot give.
- **R7's high is set by a stability rule,** not by the evidence's own high, and the term binds at its cap from the
  early 2030s.
