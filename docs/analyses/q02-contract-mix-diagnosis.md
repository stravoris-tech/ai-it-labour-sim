> **Analysis Q02, from the development of this model.** Copied verbatim below the line from the analysis's findings note.
>
> - **Question:** Why does the contract mix move the way it does? A diagnosis of Q01's results.
> - **Ran on:** commit `20615ad`, model `phase7`. Commit ids refer to the private development repository.
> - **Model:** It ran on `phase7`, before the model selector existed (slice 8), so it names no model.
> - **Paths:** Paths under `temp/` (the analysis scripts, CSVs, charts and saved results it names) refer to the development workspace and are not in this repository.

---

# Q02 - why the contract mix moves the way it does (diagnosis of Q01)

Reproduce, from the repo root:

```
uv run --with matplotlib python temp/analysis/q02-contract-mix-diagnosis/run.py
uv run python temp/analysis/q02-contract-mix-diagnosis/phase5_repro.py
uv run python temp/analysis/q02-contract-mix-diagnosis/phase_bisect.py
```

- `run.py` reproduces sections A, B.1-B.2, C and D: every CSV, PNG, `tables.md`, `checks.csv`, `meta.json` and `summary.json`. It takes 35 s.
- The two prototype scripts are optional. `phase5_repro.py` covers B.3 (8 s) and `phase_bisect.py` covers B.6 (14 s). They run unmodified copies of prototype files in `proto/`. `run.py` reads their JSON for the comparison table if it is present.

Runs used commit `20615ad` on branch `main` (clean tree). No model change and no `analysis/` branch. Nothing tracked was changed and nothing was committed.

## Short answers

**1. Is the reversal real, and where does it come from?** Yes, and it is a deliberate Phase 7 change whose outcome is documented. Its mechanism is not.
- **Where it starts.** Phases 5, 6a and 6b all show effort billing (TM + SA) falling from 2024 to 2040 in their AI base case, at every vendor. Phase 6b already has three vendors: OIT 0.400 to 0.225, GSI 0.270 to 0.141, BQ 0.620 to 0.429. Phase 7 is the first phase with a rise: GSI 0.270 to 0.308 and BQ 0.620 to 0.735 by 2032.
- **What changed.** Between 6b and 7, the contract and type-choice code differs in one line: the price anchor gains the factor `1 + PriceHorizon x PU` (`phase6b_sim.py:317` against `phase7_sim.py:333`). The `TypeASC` constants and all contract parameters are identical.
- **The test.** Phase 7 run with `PriceHorizon` = 0 falls at every vendor, as 6b does. OIT goes from 0.400 to 0.246 by 2040, against Phase 5's 0.240.
- **The record.** The Phase 7 guide (`07:202-210`) and the change log (`00:518`) both record "rise to about 2031, then give way". So the rise is documented, contrary to Q01's reading of the change log. The Phase 5 row (`00:521`) records the earlier 40% to 24% fall, and no row notes that Phase 7 turns it around. By 2040, OIT and GSI are below their 2024 levels again (0.314 and 0.221), and only BQ stays above (0.641).
- **What the record gets wrong.** The guide attributes the rise to clients avoiding long fixed prices. The decomposition in C shows the vendor side drives it.

**2. Within versus between.** In the baseline, the 2024-2032 rise of 6.97 points in the revenue-weighted share splits into:
- within-vendor contract choice: 4.00 points;
- work moving between vendors: 2.02 points;
- interaction: 0.95 points.

By 2040 the split reverses. Within is -4.63 points, while between (+5.91) and interaction (+2.22) keep the total at +3.50. This is because BQ, the most effort-billed vendor, grows from 22.4% to 45.4% of vendor revenue. In the Q01 Monte Carlo (1,000 runs, 0 invalid):
- **2032:** the median within is +0.5 points (p10-p90 -2.8 to +3.5), between +1.7 (0.3 to 3.6), total +2.9.
- **2040:** within is -7.1 (-10.5 to -3.3), between +5.1 (2.6 to 7.7), total -0.4 (-4.3 to +3.9). Between exceeds within in every run, and within is negative in 99.7% of runs.

**3. `PriceHorizon`.** Every vendor's effort-billed share rises monotonically with `PriceHorizon`, at both 2032 and 2040, in Baseline, Fast AI and Slow AI. `HeadTotal` hardly moves (80,232 to 80,146 in 2032 across 0-12).
- **No-shift points (2032):** OIT 8.33, GSI 5.66, BQ 3.76, revenue-weighted 4.74.
- **No-shift points (2040):** none in 0-12 for OIT or GSI (they fall at every value); BQ 6.68.
- **Provenance.** The calibrated 7.877 was fitted by `least_squares` in `calibrate7.py`, with bounds 0-8 and a start at 3.0. It is one of eleven parameters fitted jointly to eleven 2024-2026 targets, and the guide says it pins down the 2026 Indian IT book price (target 0.96, model 0.964). It ends at 98.5% of its fit bound.
- **The sampled range.** The 4-8 range (`phase7_runs.py:41`) is absolute and shares its top with the fit bound. No text gives its origin. The tornado file reads the fit's output (`phase7_runs.py:6`), and two other ranges are set relative to fitted values, so it was written with the fit in hand. Whether 4-8 itself was chosen before the fit cannot be settled from the files.

**4. Client or vendor push?** Relative to FP, which is all the logit sees, the two sides push in opposite directions.
- **Vendor side, towards effort billing.** The vendor term raises the TM-FP score gap by +0.40 to +0.57 by 2028 and +0.46 to +0.79 by 2032. The cause is that `PriceHorizon` cuts the new FP, MS and OB price (`Anchor` about 0.67 in 2032, against 0.82 with `PriceHorizon` = 0), and so the vendor's fixed-price revenue term, while TM revenue is not anchored.
- **Client side, away from effort billing, and growing.** It lowers the TM-FP gap by -0.09 by 2028, -0.30 to -0.35 by 2032 and -0.64 to -0.75 by 2040, through distrust of effort billing as `ClientP` rises.
- **Net.** The vendor push dominates until about 2032, and the client push from then on.
- **At `PriceHorizon` = 0** the vendor term pushes towards FP (TM-FP -0.34 to -0.49 by 2028), so both sides push away from effort billing, as in Phase 5.

## A. Within versus between (Question 2)

E(t) = sum_v w_v(t) e_v(t), with w_v = `Revenue_v / RevenueTot` and e_v = `EffortShare_v`. The checks all pass:

| check | max abs diff |
| --- | --- |
| within + between + interaction = E(t) - E(2024), baseline | 1.0e-16 |
| the same identity, per Monte Carlo run | 1.7e-16 |
| sum_v w_v = 1 | 1.1e-16 |
| sum_v w_v e_v = derived `EffortShare_revenue_weighted` | 5.6e-17 |

### Baseline split (share, 0-1)

| year | E | change | within | between | interaction |
| --- | --- | --- | --- | --- | --- |
| 2024 | 0.3940 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| 2026 | 0.3908 | -0.0032 | -0.0021 | -0.0010 | 0.0000 |
| 2028 | 0.4274 | 0.0334 | 0.0305 | 0.0024 | 0.0004 |
| 2030 | 0.4583 | 0.0643 | 0.0515 | 0.0096 | 0.0031 |
| 2032 | 0.4637 | 0.0697 | 0.0400 | 0.0202 | 0.0095 |
| 2036 | 0.4536 | 0.0596 | -0.0155 | 0.0482 | 0.0269 |
| 2040 | 0.4290 | 0.0350 | -0.0463 | 0.0591 | 0.0222 |

### Monte Carlo split (Q01 design rerun)

The design is the 14 `TORNADO` levers, each `Uniform(lo, hi)`, 1,000 LHS runs, `seed=20261012`, with 0 invalid runs. It reproduces Q01: the samples match `q01-contract-mix/samples.csv` to 4.8e-10 (that file holds 10 significant digits), and the revenue-weighted bands match Q01's `summary.json` exactly.

| year | component | p10 | median | p90 |
| --- | --- | --- | --- | --- |
| 2032 | within | -0.0279 | 0.0048 | 0.0350 |
| 2032 | between | 0.0028 | 0.0167 | 0.0364 |
| 2032 | interaction | 0.0015 | 0.0067 | 0.0148 |
| 2032 | total | -0.0111 | 0.0287 | 0.0754 |
| 2040 | within | -0.1050 | -0.0710 | -0.0325 |
| 2040 | between | 0.0257 | 0.0514 | 0.0765 |
| 2040 | interaction | 0.0066 | 0.0137 | 0.0255 |
| 2040 | total | -0.0426 | -0.0041 | 0.0385 |

The total change is positive in 81.3% of runs at 2032 and 45.2% at 2040. Within is positive in 0.3% of runs at 2040. Between exceeds within in 100% of runs at 2040. Chart: `shift_share.png` (data `chart_shift_share.csv`).

### Revenue weights w_v and effort shares e_v, baseline

| year | w_OIT | w_GSI | w_BQ | e_OIT | e_GSI | e_BQ |
| --- | --- | --- | --- | --- | --- | --- |
| 2024 | 0.351 | 0.425 | 0.224 | 0.400 | 0.270 | 0.620 |
| 2026 | 0.348 | 0.430 | 0.222 | 0.395 | 0.268 | 0.622 |
| 2028 | 0.338 | 0.426 | 0.236 | 0.416 | 0.300 | 0.673 |
| 2030 | 0.313 | 0.421 | 0.266 | 0.420 | 0.322 | 0.719 |
| 2032 | 0.281 | 0.411 | 0.308 | 0.394 | 0.308 | 0.735 |
| 2036 | 0.214 | 0.374 | 0.412 | 0.328 | 0.248 | 0.705 |
| 2040 | 0.186 | 0.360 | 0.454 | 0.314 | 0.221 | 0.641 |

Every year with MC bands is in `chart_revenue_weights.csv`. Chart: `revenue_weights.png`.

## B. To 2040, and the Phase 5 comparison (Question 1)

### B.1 Book mix to 2040, deterministic scenarios (2024 is the same for all: OIT 0.35/0.30/0.22/0.10/0.03, GSI 0.38/0.22/0.30/0.05/0.05, BQ 0.30/0.45/0.05/0.17/0.03)

| scenario | vendor | year | FP | TM | MS | SA | OB | TM+SA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | OIT | 2032 | 0.312 | 0.282 | 0.265 | 0.113 | 0.029 | 0.394 |
| Baseline | OIT | 2036 | 0.349 | 0.226 | 0.291 | 0.102 | 0.032 | 0.328 |
| Baseline | OIT | 2040 | 0.377 | 0.207 | 0.275 | 0.107 | 0.033 | 0.314 |
| Baseline | GSI | 2032 | 0.328 | 0.241 | 0.318 | 0.067 | 0.045 | 0.308 |
| Baseline | GSI | 2036 | 0.367 | 0.190 | 0.335 | 0.058 | 0.050 | 0.248 |
| Baseline | GSI | 2040 | 0.397 | 0.164 | 0.330 | 0.057 | 0.053 | 0.221 |
| Baseline | BQ | 2032 | 0.205 | 0.494 | 0.039 | 0.241 | 0.021 | 0.735 |
| Baseline | BQ | 2036 | 0.235 | 0.465 | 0.037 | 0.240 | 0.023 | 0.705 |
| Baseline | BQ | 2040 | 0.289 | 0.413 | 0.042 | 0.228 | 0.028 | 0.641 |
| Baseline | revenue-weighted | 2032 / 2036 / 2040 | | | | | | 0.464 / 0.454 / 0.429 |
| Slow AI | OIT | 2032 | 0.319 | 0.277 | 0.257 | 0.118 | 0.029 | 0.395 |
| Slow AI | OIT | 2036 | 0.337 | 0.248 | 0.267 | 0.118 | 0.030 | 0.366 |
| Slow AI | OIT | 2040 | 0.351 | 0.241 | 0.250 | 0.128 | 0.030 | 0.369 |
| Slow AI | GSI | 2032 | 0.342 | 0.224 | 0.320 | 0.067 | 0.047 | 0.291 |
| Slow AI | GSI | 2036 | 0.364 | 0.198 | 0.326 | 0.064 | 0.049 | 0.261 |
| Slow AI | GSI | 2040 | 0.382 | 0.186 | 0.315 | 0.066 | 0.050 | 0.252 |
| Slow AI | BQ | 2032 | 0.235 | 0.462 | 0.045 | 0.234 | 0.024 | 0.696 |
| Slow AI | BQ | 2036 | 0.254 | 0.443 | 0.042 | 0.236 | 0.025 | 0.679 |
| Slow AI | BQ | 2040 | 0.284 | 0.413 | 0.044 | 0.231 | 0.028 | 0.644 |
| Slow AI | revenue-weighted | 2032 / 2036 / 2040 | | | | | | 0.435 / 0.432 / 0.422 |
| Fast AI | OIT | 2032 | 0.317 | 0.270 | 0.283 | 0.101 | 0.030 | 0.371 |
| Fast AI | OIT | 2036 | 0.377 | 0.180 | 0.326 | 0.082 | 0.035 | 0.262 |
| Fast AI | OIT | 2040 | 0.414 | 0.165 | 0.297 | 0.088 | 0.036 | 0.253 |
| Fast AI | GSI | 2032 | 0.327 | 0.241 | 0.324 | 0.063 | 0.046 | 0.304 |
| Fast AI | GSI | 2036 | 0.387 | 0.151 | 0.363 | 0.046 | 0.053 | 0.197 |
| Fast AI | GSI | 2040 | 0.423 | 0.129 | 0.346 | 0.046 | 0.056 | 0.174 |
| Fast AI | BQ | 2032 | 0.192 | 0.514 | 0.036 | 0.238 | 0.020 | 0.753 |
| Fast AI | BQ | 2036 | 0.276 | 0.432 | 0.041 | 0.224 | 0.027 | 0.656 |
| Fast AI | BQ | 2040 | 0.354 | 0.357 | 0.051 | 0.203 | 0.035 | 0.560 |
| Fast AI | revenue-weighted | 2032 / 2036 / 2040 | | | | | | 0.478 / 0.428 / 0.387 |
| Jevons rebound | OIT | 2032 | 0.312 | 0.278 | 0.265 | 0.115 | 0.029 | 0.394 |
| Jevons rebound | OIT | 2036 | 0.348 | 0.223 | 0.292 | 0.105 | 0.032 | 0.327 |
| Jevons rebound | OIT | 2040 | 0.377 | 0.206 | 0.276 | 0.108 | 0.033 | 0.314 |
| Jevons rebound | GSI | 2032 | 0.328 | 0.239 | 0.318 | 0.069 | 0.045 | 0.308 |
| Jevons rebound | GSI | 2036 | 0.367 | 0.187 | 0.337 | 0.060 | 0.050 | 0.247 |
| Jevons rebound | GSI | 2040 | 0.396 | 0.163 | 0.331 | 0.057 | 0.053 | 0.220 |
| Jevons rebound | BQ | 2032 | 0.205 | 0.489 | 0.039 | 0.247 | 0.021 | 0.735 |
| Jevons rebound | BQ | 2036 | 0.237 | 0.458 | 0.037 | 0.245 | 0.023 | 0.703 |
| Jevons rebound | BQ | 2040 | 0.292 | 0.407 | 0.043 | 0.229 | 0.028 | 0.637 |
| Jevons rebound | revenue-weighted | 2032 / 2036 / 2040 | | | | | | 0.464 / 0.452 / 0.427 |

Data: `scenarios_to_2040.csv`.
- In every scenario, OIT and GSI end 2040 below their 2024 effort-billed share.
- BQ ends above it in Baseline (0.641), Slow AI (0.644) and Jevons rebound (0.637), and below it in Fast AI (0.560).
- The revenue-weighted share ends above 2024 (0.394) in every scenario except Fast AI (0.387).
- These 2040 Baseline values match the Phase 7 guide's Q2 table (`07:204-208`: 31%, 22%, 64%), and the Fast AI values match its 25%, 17% and 56%.

### B.2 Comparison with Phase 5 T2

| source | year | FP | TM | MS | SA | OB | TM+SA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Phase 5 T2 reference (`05:266`), one vendor | 2040 | 0.440 | 0.162 | 0.283 | 0.078 | 0.038 | 0.240 |
| Phase 5 T2, rerun from copies | 2024 | 0.350 | 0.300 | 0.220 | 0.100 | 0.030 | 0.400 |
| Phase 5 T2, rerun from copies | 2040 | 0.440 | 0.162 | 0.283 | 0.078 | 0.038 | 0.240 |
| Phase 7 baseline, OIT | 2040 | 0.377 | 0.207 | 0.275 | 0.107 | 0.033 | 0.314 |
| Phase 7 baseline, GSI | 2040 | 0.397 | 0.164 | 0.330 | 0.057 | 0.053 | 0.221 |
| Phase 7 baseline, BQ | 2040 | 0.289 | 0.413 | 0.042 | 0.228 | 0.028 | 0.641 |
| Phase 7 baseline, revenue-weighted | 2024 / 2040 | | | | | | 0.394 / 0.429 |
| Phase 7 with `PriceHorizon` = 0, OIT (D.2) | 2040 | 0.422 | | | | | 0.246 |

**What is comparable.**
- Phase 5's single vendor starts from `Mix0` = 35/30/22/10/3 (`phase5_sim.py:65`). This is exactly Phase 7's OIT 2024 book, so OIT is the like-for-like line.
- The type-choice formulas, the parameters `ConsSens`, `EffortDistrust`, `VendSens`, `SATTFSens`, `BargainW0` and `BaseDur_*`, and the logit form are the same (B.4).
- Both runs use the same time step and horizon.

**What is not comparable.**
- **Vendors.** Phase 5 has one vendor with one in-house and one GCC option. Phase 7 has three vendors, competing for work across seven sectors.
- **Revenue weighting.** There is no Phase 5 equivalent of the revenue-weighted share. BQ (effort-heavy) gaining revenue share is a Phase 6b/7 mechanism.
- **Calibration.**
  - Phase 7 is refitted to 2024-2026 data: demand growth 3% a year, `Verif` 0.43, `GCCMomentum`, `AICost2024` and the AI parameters.
  - Phase 7 adds `PriceHorizon`.
  - Phase 5's `TypeASC` are its own (0 before its calibration, `phase5_sim.py:70`).
- **Initial state.** Phase 5's 2024 state is an AI-off equilibrium. Phase 7's lies on a balanced growth path.

### B.3 Phase 5 reproduced

`phase5_repro.py` ran the chain `phase3_tests.py` -> `phase4_tests.py` -> `phase5_tests.py` on unmodified copies, with the standard library only. The calibration chain needs `phase3_results.json` and `phase4_results.json`, which are not in the repo; the chain regenerates them (D-ruling D1). The T2 AI base case gives 2040 FP 44.0%, TM 16.2%, MS 28.3%, SA 7.8% and OB 3.8%. This matches the reference to one decimal place. Effort billing goes from 40.0% to 24.0% (`phase5_t2.csv`, `phase5_repro.json`).

### B.4 Formula diff, Phase 5 against Phase 7 (copies in `proto/`)

| item | Phase 5 | Phase 7 | change |
| --- | --- | --- | --- |
| Price anchor | `phase5_sim.py:246` `Anchor = (1 / ClientP) ** PassThrough` | `phase7_sim.py:333` `Anchor = (1 / (CP * (1 + PriceHorizon * PU))) ** PassThrough` | **New factor `1 + PriceHorizon x PU`.** It is the only change inside the contract and type-choice block between 6b and 7 (6b:317 has the Phase 5 form). `PriceHorizon` defaults to 0 in the uncalibrated code (`phase7_sim.py:107`) and is 7.877 after the fit. |
| Order of `PU` and `Anchor` | `:246-247` (Anchor first) | `:332-333` (PU first) | Needed, because the anchor now reads `PU`. No numerical effect. |
| `Pass` map | `:254` | `:326` | Same (FP 0, TM 1, MS `MSGlideShare`, SA 1, OB `OBGainShare`). |
| New price `PNew` | `:258` | `:344` | Same form: effort types `1 - Disc`, the others `Anchor x (1 - Disc)`. FP, MS and OB new prices therefore carry the `PriceHorizon` cut; TM and SA do not. |
| Durations `Dnew` | `:256`, `BaseDur` at `:66` | `:342`, `BaseDur` at `:79` | Same formula and same base durations (FP 2.5, TM 1.5, MS 6, SA 1, OB 3). |
| Price index `AvgIdx` (TM/SA revenue) | `:264-265`, effort volume over `P_eff`, normalised by `VendorShare` | `:348-349`, over `Pe[v]`, normalised by `Book` | Per-vendor productivity; a different normaliser for the same quantity (the book). TM and SA revenue still falls with productivity. |
| `CostIdx` | `:285`, over `BasePriceAvg` = `BaseRev / VendDel` (`:268`) | `:379`, over `BaseRev / VendDel` | Same quantity, per vendor. |
| Weights `wv`, `wc` | `:287` | `:380` | Same: `clamp(BargainW0 x Power, 0.1, 0.9)`, `wc = 1 - wv`. |
| Consumer utility | `:292-296` | `:383-387` | Same three terms: price uncertainty over the term, effort distrust `EffortDistrust x (1 - 1/ClientP)`, SA time-to-fill. Per-vendor `ClientP[v]`. |
| Vendor utility | `:297-299`, `Profit0 = NormalMargin` (`:286`) | `:388-390`, `f["nm"]` = `NormalMargin_v` | Same form, per-vendor normal margin. |
| Type score | `:300` `TypeASC_k` | `:392` `TypeASC_{v}_{k}` | Per-vendor constants, set the same way from the 2024 mix (`calibrate6b.py:28`, `calibrate7_ss.py:32`). The 15 values are identical in 6b and 7. |
| Logit | `:301-302`, inline | `:393`, `softmax` (`:145-147`) | Same expression. |
| Signings | `:303` `VendSign x TypeShare` | `:394` `Book x SignRate x TypeShare` | Per vendor; a different normalisation of the same flow. |
| Vendor option cost in sourcing | `:309` `BasePriceAvg x Anchor x ...` | `:445` | Same form. In Phase 7 `PriceHorizon` therefore also cheapens the vendor option for clients. |
| Effort brake on adoption | none | `:420` `1 - TMBrake x EffortShare` (from 6b, `phase6b_sim.py:405`) | Not part of the type choice. It touches TM and SA only through adoption speed. |

The 6b-to-7 diff of the whole contract block (`phase6b_sim.py:309-386` against `phase7_sim.py:325-402`) shows only the anchor line, the `AICostPerUnit` line moved out, and `WITarget = {}` moved in.

### B.5 The written record (copied specs)

- **00 model spec, contract-mix mechanism (`00:251-297`):** no statement about the direction of the mix. It defines the test only: "The Q2 answer is "the mix balances" if shares stop changing (under 2 percentage points per year) before 2040" (`00:297`).
- **00 change log, Phase 7 row (`00:518`):** "...effort-billed contracts rise to about 2031 then give way to fixed price and managed services...". The same row lists "new parameters for ... clients pricing in the productivity trend".
- **00 change log, Phase 6b row (`00:519`):** its findings name no contract-mix direction ("the T&M brake changes timing more than outcomes").
- **00 change log, Phase 6a row (`00:520`):** no statement about the contract mix.
- **00 change log, Phase 5 row (`00:521`):** "Findings: with AI, effort-billed work falls from 40% to 24% of vendor contracts and the mix settles by the mid-2030s".
- **05 guide, T2 (`05:266`):** "2040 mix FP 44.0%, TM 16.2%, MS 28.3%, SA 7.8%, OB 3.8% (effort-billed work falls from 40% to 24%)".
- **05 guide, reading the results (`05:278`):** "The contract mix moves from effort billing to fixed price and managed services, then settles. ... Vendors earn more per unit of work under fixed price while their real productivity runs ahead of what clients perceive."
- **06a guide, reading the results (`06a:266-275`):** no statement about the contract mix (demand-side phase).
- **06b guide, reading the results (`06b:297`):** "Q2: the mix moves away from effort billing for every archetype, but boutiques keep the most time and materials and staff augmentation."
- **07 guide, new parameter (`07:28`):** "Clients price in the productivity trend (`PriceHorizon`). Clients now ask for 25-30% lower prices at renewal, ahead of the gains." No statement about the effect on the mix.
- **07 guide, sensitivity (`07:174`):** "The contract parameters (T&M brake, client price horizon) barely move headcount: they change vendor margins and contract mix, not jobs."
- **07 guide, answers, Q2 (`07:202-210`):** a table of effort-billed share (OIT 40% / 42% / 31% / 25%; GSI 27% / 32% / 22% / 17%; BQ 62% / 72% / 64% / 56% for 2024, 2030, 2040 base and 2040 fast AI). Then: "The mix swings twice. Until about 2031, while productivity and prices are moving fast, clients avoid locking in long fixed prices, and new business tilts toward short effort-billed work. Once gains slow, fixed price and managed services take back share..."
- **07 guide, limitations (`07:234`):** "`PriceHorizon` ended at the top of its range."

So the record documents the 2024-2031 rise and the 2040 fall at OIT and GSI. It does not link the rise to `PriceHorizon`, and it does not say that Phase 7 reverses the direction Phase 5 and 6b reported for 2024-2031. Its stated mechanism (clients avoiding fixed prices) is not what section C finds.

### B.6 Phase bisect (user addition)

The 6a and 6b chains ran from copies (6a reads `phase5_results.json`, 6b reads `phase6a_results.json`). Phase 7 is the copied `phase7_sim.run` with the `calib7.json` parameters applied as `phase7_runs.py:6-10` does (D2). It equals `aisim.run()` exactly, with a max abs diff of 0.0 over every recorded effort and mix key.

| phase | vendor | 2024 | 2032 | 2040 | 2024 to 2032 | 2024 to 2040 |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | single | 0.400 | 0.260 | 0.240 | falls | falls |
| 6a | single | 0.400 | 0.231 | 0.232 | falls | falls |
| 6b | OIT | 0.400 | 0.238 | 0.225 | falls | falls |
| 6b | GSI | 0.270 | 0.140 | 0.141 | falls | falls |
| 6b | BQ | 0.620 | 0.403 | 0.429 | falls | falls |
| 7 | OIT | 0.400 | 0.394 | 0.314 | falls (-0.006) | falls |
| 7 | GSI | 0.270 | 0.308 | 0.221 | **rises** | falls |
| 7 | BQ | 0.620 | 0.735 | 0.641 | **rises** | **rises** |
| 7, `PriceHorizon` = 0 | OIT | 0.400 | 0.259 | 0.246 | falls | falls |
| 7, `PriceHorizon` = 0 | GSI | 0.270 | 0.164 | 0.157 | falls | falls |
| 7, `PriceHorizon` = 0 | BQ | 0.620 | 0.473 | 0.464 | falls | falls |

The first phase in which the direction turns from falling to rising is **Phase 7**. Data: `phase_bisect.csv`, `phase_bisect.json`.

## C. Client versus vendor push (Question 4)

### Recording

`aisim.run(params, trace=cb, record_every=1/16)` was run on the scalar engine, every step from 2024 to 2040, for the baseline and for `PriceHorizon` = 0. The engine keeps `Ucons`, `Uvend` and `Score` only as loop locals (`src/aisim/scalar/finance.py:280-291`), so the components are rebuilt from traced intermediates (D3):
- S3 `Work.Pe`;
- S8f `Pools.TTFratio["ON"]` (`labour_market.py:319`);
- S10 `Contracts.Pass` and `VF[v]` (`PU`, `Dnew`, `PNew`, `nm`, `Anchor`; `finance.py:162-239`);
- S11b `VB[v]` (`wv`, `CostIdx`, `TypeShare`; `finance.py:276-292`).

`ClientP[v]` is state and is not traced. It is recovered by inverting `finance.py:169`: `ClientP = 1 / (Anchor x (1 + PriceHorizon x PU))`, which is valid because `PassThrough` = 1 (asserted). The reconstruction follows `finance.py:283-291` term by term:
- constant `TypeASC_{v}_{k}` (`:291`);
- client term `wc x Ucons` (`:278`, `:283-287`);
- vendor term `wv x Uvend` (`:277`, `:288-290`).

Checks (all pass):

| check | max abs diff |
| --- | --- |
| softmax of rebuilt scores = traced `TypeShare`, baseline | 2.2e-16 |
| the same, `PriceHorizon` = 0 | 0 |
| traced `TypeShare` = `Sign_v_k` from a normal `run()` (no trace), every dt | 0 |
| rebuilt shares = `Sign_v_k` from a normal `run()`, every dt | 2.2e-16 |
| traced `TypeShare` = `Sign_v_k` from `run_experiment` (batch engine), annual | 0 |

Data: `choice_components.csv` and `choice_components_PH0.csv` (every step, vendor and type, with sub-terms).

### Movements (logit units; client = wc x Ucons, vendor = wv x Uvend)

| vendor | type | TypeASC | client 2024 | client 2028 | client 2032 | client 2040 | vendor 2024 | vendor 2028 | vendor 2032 | vendor 2040 | share 2024 | share 2032 | share 2040 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | -1.246 | 0.000 | -0.102 | -0.121 | -0.083 | 0.016 | -0.706 | -1.041 | -0.557 | 0.283 | 0.252 | 0.348 |
| OIT | TM | -0.889 | 0.000 | -0.194 | -0.471 | -0.835 | 0.016 | -0.310 | -0.583 | -0.303 | 0.405 | 0.401 | 0.302 |
| OIT | SA | -1.582 | 0.073 | -0.058 | -0.204 | -0.398 | 0.016 | -0.307 | -0.581 | -0.301 | 0.218 | 0.263 | 0.234 |
| OIT | MS | -2.586 | 0.000 | -0.123 | -0.145 | -0.100 | 0.016 | -0.695 | -1.021 | -0.555 | 0.074 | 0.066 | 0.090 |
| GSI | FP | -1.005 | 0.000 | -0.104 | -0.120 | -0.083 | 0.012 | -0.746 | -1.024 | -0.509 | 0.363 | 0.311 | 0.413 |
| GSI | TM | -1.041 | 0.000 | -0.194 | -0.456 | -0.807 | 0.012 | -0.253 | -0.446 | -0.186 | 0.350 | 0.383 | 0.267 |
| GSI | SA | -2.117 | 0.073 | -0.061 | -0.197 | -0.384 | 0.012 | -0.250 | -0.443 | -0.184 | 0.128 | 0.169 | 0.139 |
| GSI | MS | -2.117 | 0.000 | -0.124 | -0.144 | -0.100 | 0.012 | -0.730 | -1.000 | -0.506 | 0.119 | 0.102 | 0.134 |
| BQ | FP | -1.623 | 0.000 | -0.097 | -0.120 | -0.085 | 0.021 | -0.639 | -0.858 | -0.572 | 0.193 | 0.122 | 0.201 |
| BQ | TM | -0.707 | 0.000 | -0.182 | -0.422 | -0.723 | 0.021 | -0.075 | -0.071 | -0.112 | 0.483 | 0.497 | 0.420 |
| BQ | SA | -1.275 | 0.073 | -0.046 | -0.174 | -0.343 | 0.021 | -0.071 | -0.066 | -0.109 | 0.294 | 0.362 | 0.349 |
| BQ | MS | -4.290 | 0.000 | -0.117 | -0.144 | -0.102 | 0.021 | -0.621 | -0.831 | -0.564 | 0.013 | 0.009 | 0.014 |

Every type's score falls after 2024, and the logit sees only differences between types. So the side that drives each type's rise or fall is read from its score gap against FP. `choice_movements.csv` also gives the per-type "driver" (the side with the larger absolute change in that type's own score), but a shift common to all types does not change any share.

### Score gaps against FP, and which side moves them

| vendor | gap | 2024 | 2028 (client / vendor change) | 2032 (client / vendor change) | 2040 (client / vendor change) | driver 2028 / 2032 / 2040 |
| --- | --- | --- | --- | --- | --- | --- |
| OIT | TM-FP | 0.357 | 0.661 (-0.091 / +0.395) | 0.464 (-0.350 / +0.457) | -0.141 (-0.752 / +0.254) | vendor / vendor / client |
| OIT | SA-FP | -0.263 | 0.106 (-0.029 / +0.398) | 0.040 (-0.156 / +0.459) | -0.396 (-0.388 / +0.256) | vendor / vendor / client |
| OIT | MS-FP | -1.340 | -1.349 (-0.020 / +0.011) | -1.344 (-0.024 / +0.020) | -1.354 (-0.017 / +0.002) | client / client / client |
| GSI | TM-FP | -0.036 | 0.367 (-0.090 / +0.493) | 0.206 (-0.336 / +0.578) | -0.437 (-0.724 / +0.323) | vendor / vendor / client |
| GSI | SA-FP | -1.039 | -0.573 (-0.030 / +0.496) | -0.608 (-0.150 / +0.581) | -1.087 (-0.373 / +0.325) | vendor / vendor / client |
| GSI | MS-FP | -1.112 | -1.116 (-0.021 / +0.016) | -1.112 (-0.024 / +0.024) | -1.125 (-0.017 / +0.003) | client / client / client |
| BQ | TM-FP | 0.916 | 1.396 (-0.085 / +0.565) | 1.402 (-0.302 / +0.788) | 0.738 (-0.638 / +0.460) | vendor / vendor / client |
| BQ | SA-FP | 0.421 | 0.968 (-0.022 / +0.568) | 1.087 (-0.127 / +0.793) | 0.553 (-0.331 / +0.463) | vendor / vendor / vendor |
| BQ | MS-FP | -2.667 | -2.668 (-0.019 / +0.018) | -2.664 (-0.024 / +0.027) | -2.676 (-0.017 / +0.009) | client / vendor / client |

Data: `choice_gaps_vs_FP.csv`. Charts: `utility_{OIT,GSI,BQ}.png`, which plot the FP and TM panels every step, with dashed lines for `PriceHorizon` = 0 (data `chart_utility.csv`).

**What the terms show.**
- **Vendor side.** By 2032 the vendor's FP and MS terms fall about twice as far as its TM and SA terms at OIT and GSI, and twelve times as far at BQ. For OIT, FP moves from 0.016 to -1.041 while TM moves from 0.016 to -0.583.
  - At OIT in 2032 (`choice_subterms_2032.csv`), moving from `PriceHorizon` 0 to 7.877 lowers the FP revenue sub-term by 0.99 (4.18 to 3.19). The FP cost sub-term rises by 0.45 (-3.70 to -3.25), and the constant part by 0.14. FP's vendor term falls from -0.635 to -1.041.
  - TM's revenue sub-term falls by only 0.28, because effort prices are not anchored. With the same cost change, TM's vendor term rises from -0.895 to -0.583.
  - So it is the anchored price on non-effort types that turns vendors from fixed price towards effort billing.
  - Vendor pressure peaks around 2030-2032, when `PU` peaks (0.027-0.028), and eases as `PU` falls to 0.017 by 2040.
- **Client side.** The price-uncertainty term does penalise FP (-0.12 at 2032), which is the guide's "clients avoid locking in long fixed prices". But distrust of effort billing (-0.41 to -0.47 on TM and SA at 2032, growing with `1 - 1/ClientP` to -0.72 to -0.84 by 2040) outweighs it. The client side's net TM-FP change is therefore negative in every reported year.
- **Within the non-effort types.** MS-FP hardly moves on either side, because MS and FP share the anchored price.
- **At `PriceHorizon` = 0** (`choice_components_PH0.csv`), the vendor's TM-FP change is negative: -0.34 / -0.42 / -0.49 for OIT / GSI / BQ by 2028, and -0.26 / -0.32 / -0.42 by 2032. Both sides then push towards FP, and signings of TM + SA fall from 2024 on (OIT 0.622 to 0.503 by 2032, against 0.622 to 0.664 at 7.877).

## D. `PriceHorizon` (Question 3)

### D.1 Provenance

- **Meaning.** The client's price horizon, in years: clients price `PriceHorizon` years of the perceived productivity trend `PU` into new non-effort contract prices.
  - Engine: `src/aisim/scalar/finance.py:168-169` (`PU`, then `Anchor`), used in `PNew` (`:188`) for FP, MS and OB.
  - Through `Anchor`, it also sets the vendor option cost in the sourcing choice (prototype `phase7_sim.py:445`).
  - Spec: `07:28` ("Clients price in the productivity trend"). It is not in `00_model_spec.md` apart from the change log (`00:518`).
- **The calibrated value 7.877 was fitted, not set by hand.**
  - `calibrate7.py:23-24` lists it in `FIT` with bounds (0.0, 8.0); the start value is 3.0 (`calibrate7.py:26`). It is fitted jointly with ten others by `scipy.optimize.least_squares` (`calibrate7.py:81`) to the eleven targets in `calibrate7.py:9-21`.
  - `calib7.json` `fitted` holds `PriceHorizon: 7.877`.
  - The guide says it pins down "Book price" (`07:80`), the target `PriceIdx_OIT` 2026 = 0.96 (model 0.964, `calib7.json` `targets`), the 2-5% a year deal deflation.
  - The fit is close to exactly determined: eleven parameters for eleven targets (`07:234`). The value ends at 98.5% of its upper bound, and the guide notes it "ended at the top of its range" (`07:91`, `07:234`).
- **The sampled range.**
  - `phase7_runs.py:41` gives `("PriceHorizon", 4.0, 8.0, ...)`. Its top equals the fit's upper bound, and it is absolute. `Verif` and `JuniorCut` are relative to the fitted `BASE` (`phase7_runs.py:35`, `:39`).
  - `phase7_runs.py` loads `calib7.json` at line 6, so the tornado list was written to run on the fitted parameters.
  - No file says how 4-8 was chosen or whether it predates the fit. The prototype has no history, so this is not settled.
  - The calibrated value sits at 97% of 4-8. The fit's start value (3.0) lies outside the range.

### D.2 Baseline sweep (deterministic, everything else as shipped, validation on)

`PriceHorizon` in {0, 1, 2, 3, 4, 5, 6, 7, 7.877, 8, 9, 10, 12}. Validation accepted every point, including 0 and 1 (domain `non_negative`), so no point needed `validate=False` and `price_horizon_sweep_flags.csv` is empty. The 7.877 point reproduces the baseline run exactly.

2032:

| PriceHorizon | FP OIT | FP GSI | FP BQ | Eff OIT | Eff GSI | Eff BQ | Eff revenue-weighted | HeadTotal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.403 | 0.416 | 0.419 | 0.259 | 0.164 | 0.473 | 0.272 | 80,232 |
| 1 | 0.389 | 0.405 | 0.384 | 0.279 | 0.182 | 0.515 | 0.299 | 80,222 |
| 2 | 0.376 | 0.393 | 0.351 | 0.298 | 0.201 | 0.556 | 0.325 | 80,209 |
| 3 | 0.364 | 0.382 | 0.320 | 0.317 | 0.220 | 0.593 | 0.350 | 80,198 |
| 4 | 0.352 | 0.370 | 0.291 | 0.335 | 0.239 | 0.628 | 0.376 | 80,186 |
| 5 | 0.340 | 0.359 | 0.265 | 0.352 | 0.258 | 0.660 | 0.400 | 80,176 |
| 6 | 0.330 | 0.347 | 0.242 | 0.367 | 0.276 | 0.689 | 0.424 | 80,174 |
| 7 | 0.320 | 0.337 | 0.221 | 0.382 | 0.294 | 0.715 | 0.446 | 80,167 |
| 7.877 | 0.312 | 0.328 | 0.205 | 0.394 | 0.308 | 0.735 | 0.464 | 80,163 |
| 8 | 0.311 | 0.327 | 0.203 | 0.396 | 0.310 | 0.738 | 0.466 | 80,165 |
| 9 | 0.302 | 0.318 | 0.186 | 0.409 | 0.326 | 0.758 | 0.486 | 80,162 |
| 10 | 0.294 | 0.309 | 0.171 | 0.421 | 0.341 | 0.777 | 0.504 | 80,157 |
| 12 | 0.279 | 0.293 | 0.146 | 0.445 | 0.370 | 0.809 | 0.539 | 80,146 |

2040:

| PriceHorizon | FP OIT | FP GSI | FP BQ | Eff OIT | Eff GSI | Eff BQ | Eff revenue-weighted |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.422 | 0.434 | 0.431 | 0.246 | 0.157 | 0.464 | 0.291 |
| 1 | 0.417 | 0.429 | 0.410 | 0.255 | 0.166 | 0.490 | 0.308 |
| 2 | 0.410 | 0.424 | 0.389 | 0.264 | 0.175 | 0.515 | 0.325 |
| 3 | 0.404 | 0.419 | 0.369 | 0.273 | 0.183 | 0.540 | 0.343 |
| 4 | 0.398 | 0.415 | 0.350 | 0.282 | 0.190 | 0.564 | 0.360 |
| 5 | 0.392 | 0.411 | 0.332 | 0.291 | 0.197 | 0.587 | 0.378 |
| 6 | 0.387 | 0.406 | 0.316 | 0.299 | 0.205 | 0.607 | 0.396 |
| 7 | 0.382 | 0.401 | 0.301 | 0.308 | 0.214 | 0.626 | 0.414 |
| 7.877 | 0.377 | 0.397 | 0.289 | 0.314 | 0.221 | 0.641 | 0.429 |
| 8 | 0.377 | 0.396 | 0.287 | 0.315 | 0.222 | 0.643 | 0.431 |
| 9 | 0.372 | 0.392 | 0.274 | 0.323 | 0.230 | 0.659 | 0.448 |
| 10 | 0.368 | 0.387 | 0.262 | 0.330 | 0.237 | 0.675 | 0.464 |
| 12 | 0.360 | 0.380 | 0.239 | 0.343 | 0.252 | 0.703 | 0.495 |

2024 levels: OIT 0.400, GSI 0.270, BQ 0.620, revenue-weighted 0.394. `HeadTotal` 2024: 82,654.

**No-shift points** (the `PriceHorizon` at which the 2032 effort-billed share equals its 2024 value, by linear interpolation; `price_horizon_no_shift.csv`):

| series | 2032 | 2040 |
| --- | --- | --- |
| OIT | 8.33 | none in 0-12 (falls at every value) |
| GSI | 5.66 | none in 0-12 (falls at every value) |
| BQ | 3.76 | 6.68 |
| revenue-weighted | 4.74 | 5.89 |

**At `PriceHorizon` = 0, every vendor's effort-billed share falls from 2024 to 2040** (`price_horizon_zero.csv`, all validated):

| scenario | OIT | GSI | BQ | revenue-weighted |
| --- | --- | --- | --- | --- |
| Baseline | 0.400 -> 0.246, falls | 0.270 -> 0.157, falls | 0.620 -> 0.464, falls | 0.394 -> 0.291, falls |
| Fast AI | 0.400 -> 0.204, falls | 0.270 -> 0.132, falls | 0.620 -> 0.416, falls | 0.394 -> 0.266, falls |
| Slow AI | 0.400 -> 0.333, falls | 0.270 -> 0.220, falls | 0.620 -> 0.573, falls | 0.394 -> 0.363, falls |

Charts: `price_horizon_sweep.png` (a line per vendor and revenue-weighted, for 2032 and 2040, with the 2024 levels, the calibrated value and the 4-8 range marked; data `price_horizon_sweep.csv`).

### D.3 Fast AI and Slow AI, revenue-weighted effort share

| PriceHorizon | Slow AI 2032 | Baseline 2032 | Fast AI 2032 | Slow AI 2040 | Baseline 2040 | Fast AI 2040 |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 0.325 | 0.272 | 0.229 | 0.363 | 0.291 | 0.266 |
| 1 | 0.340 | 0.299 | 0.264 | 0.371 | 0.308 | 0.281 |
| 2 | 0.354 | 0.325 | 0.298 | 0.378 | 0.325 | 0.297 |
| 3 | 0.369 | 0.350 | 0.332 | 0.385 | 0.343 | 0.313 |
| 4 | 0.383 | 0.376 | 0.365 | 0.392 | 0.360 | 0.329 |
| 5 | 0.397 | 0.400 | 0.397 | 0.400 | 0.378 | 0.345 |
| 6 | 0.411 | 0.424 | 0.427 | 0.407 | 0.396 | 0.360 |
| 7 | 0.424 | 0.446 | 0.455 | 0.415 | 0.414 | 0.374 |
| 7.877 | 0.435 | 0.464 | 0.478 | 0.422 | 0.429 | 0.387 |
| 8 | 0.437 | 0.466 | 0.481 | 0.423 | 0.431 | 0.388 |
| 9 | 0.449 | 0.486 | 0.505 | 0.431 | 0.448 | 0.402 |
| 10 | 0.462 | 0.504 | 0.528 | 0.438 | 0.464 | 0.416 |
| 12 | 0.485 | 0.539 | 0.569 | 0.454 | 0.495 | 0.445 |

No-shift points for the revenue-weighted share: Fast AI 4.91 (2032) and 8.39 (2040); Slow AI 4.79 (2032) and 4.26 (2040).
- **2032.** The three curves cross near `PriceHorizon` = 5. Below it, faster AI means less effort billing in 2032; above it, more. This is consistent with `PriceHorizon` multiplying `PU`, which faster AI raises.
- **2040.** Fast AI is lowest at every value.

Chart: `price_horizon_scenarios.png`.

## Options for the operator (factual, no recommendation)

1. **Keep the current behaviour and document its mechanism.** The 2024-2031 rise and the 2040 outcome are already recorded (`07:202-210`, `00:518`), and the parameter behind them was fitted to a 2026 price target (`calibrate7.py:24`, `calib7.json`). Documentation would add what is not recorded:
   - the rise is driven by the vendor side through `PriceHorizon` (C);
   - Phase 7 reverses the 2024-2031 direction that Phases 5-6b reported (B.6);
   - the guide's "clients avoid locking in fixed prices" accounts for -0.12 on FP, against the vendor term's -1.0 (C).
2. **Re-centre or widen the `PriceHorizon` range.** The evidence:
   - The calibrated 7.877 sits at 97% of the sampled 4-8 range and at 98.5% of the fit bound 0-8 (D.1).
   - The fit is nearly exactly determined (`07:234`).
   - The answer is monotone in the parameter (D.2), so the range sets the Monte Carlo's centre. With the current range, the median 2032 revenue-weighted share is 0.423 against the baseline's 0.464 (Q01).
   - The no-shift points (3.8-8.3 at 2032) all lie inside or near the sampled range, so whether the mix "rises" by 2032 depends on where in the range a run falls.
   - A range that includes 0 would include the Phase 5-6b behaviour.
3. **Investigate the anchor formula found in B.4.** The only type-choice change between 6b and 7 is `Anchor = (1 / (ClientP x (1 + PriceHorizon x PU))) ** PassThrough` (`phase7_sim.py:333`, `finance.py:169`). It enters three places:
   - the price that clients pay on FP, MS and OB;
   - the vendor's revenue term for those types in the type choice (`finance.py:288`);
   - the vendor option cost in sourcing.

   Effort types are not anchored, so trend pricing makes effort billing relatively more profitable for vendors (C). The spec text (`07:28`) motivates the term only by renewal prices. Whether vendors should also price this trend into their own type choice is not stated anywhere. Any change here alters the scalar engine and needs a slice prompt and a recalibration.
4. **Report the mix over 2024-2040, not 2024-2032.** Q01's window ends at 2032, near the peak. By 2040, OIT and GSI are below their 2024 effort share in every scenario (B.1), and the Monte Carlo median of the revenue-weighted change is -0.4 points (A).
5. **Report the within and between parts separately.** By 2040 the revenue-weighted share rises only through between-vendor shifts, from BQ's revenue share growing from 0.22 to 0.45. Within-vendor choice lowers it by 4.6 points in the baseline and in 99.7% of Monte Carlo runs (A).

## Caveats

- **Volume, not value.** Shares are contract volume, with each vendor's 2024 book equal to 1, as in Q01. The revenue weights are USD revenue, so E(t) mixes a volume share inside each vendor with revenue weights across vendors.
- **Rebuilt components.** The C components are rebuilt in the analysis from traced intermediates, mirroring `finance.py:283-291`. They are not read from the engine. The rebuild is exact to 2.2e-16 against the traced and recorded signing shares. The `ClientP` recovery relies on `PassThrough` = 1 and would not hold if that changed.
- **Attribution.** "Which side drives" is a first-order split of score changes. The logit is non-linear, and a type's share also depends on every other type's score. The per-type "driver" in `choice_movements.csv` is not invariant to shifts common to all types, which is why the gaps against FP are the main reading.
- **C uses deterministic runs only** (baseline, and `PriceHorizon` = 0). The split was not computed per Monte Carlo run.
- **One parameter at a time.** The sweeps vary `PriceHorizon` with everything else as shipped. The model was not recalibrated at each value, so off-calibration points (for example 0, or above the fit bound 8) do not reproduce the 2026 targets: the 2026 book price target in particular depends on `PriceHorizon`. Validation accepts 0-12 (domain `non_negative`), which is a numerical check, not a plausibility check.
- **Phase comparisons.** Each phase has its own calibration, initial state and structure (B.2). The bisect shows where the direction turned and that `PriceHorizon` = 0 restores the old direction in Phase 7. It does not show that `PriceHorizon` is the only difference between 6b and 7, since demand growth, `Verif`, GCC terms and AI parameters also changed. Those other differences leave the direction falling at `PriceHorizon` = 0.
- **The prototype chain** regenerates `phase3_results.json`, `phase4_results.json`, `phase5_results.json`, `phase6a_results.json` and `phase6b_results.json` in `proto/` by running the copied test scripts. The Phase 5 result matches its published reference to one decimal. 6a and 6b were not checked against their guides' tables, beyond 6b's T2 matching the "every archetype moves away" statement.
- **The bands are conditional.** As in Q01, they cover only the 14 tornado ranges, sampled uniformly and independently.
- **Not a forecast.** The model shows how its mechanisms combine under these assumptions. It does not say how contract mixes will move.

## D-rulings (minor decisions taken)

- **D1. "Copied files alone".** The Phase 5, 6a and 6b test scripts need calibration JSON that the repo does not hold (`calibrate5.py:5` reads `phase4_results.json`; `calibrate4.py:7` reads `phase3_results.json`; `calibrate6a.py:5` and `calibrate6b.py:8` read the previous phase). Each is regenerated by running the earlier copied script. Nothing was installed or edited; standard library only, `python -B`, with cwd `proto/`.
- **D2. Phase 7 in the bisect** uses a child process that applies `calib7.json` exactly as `phase7_runs.py:6-10` does and calls `phase7_sim.run`. Running `phase7_runs.py` itself would also run its whole Monte Carlo and write `phase7_results.json`. The result is cross-checked against `aisim.run()` (0.0 difference).
- **D3. Section C rebuilds the type-choice terms from traced intermediates**, with `ClientP` recovered from `Anchor`. The package does not expose `Ucons`, `Uvend`, `Score` or `ClientP` to `trace`, and the prompt forbids tracked changes, so this is the only route. It mirrors about eight lines of the formula, cited line by line, and is checked to 1e-12.
- **D4.** The `PriceHorizon` sweep charts put `PriceHorizon` on the x-axis, not years, because the prompt asks for a line per vendor with the calibrated value marked. Year charts use 2024-2040 with 2024-2026 shaded.
- **D5.** Added the `PriceHorizon` = 0 trace (C), the revenue-weights chart and the scenario sweep chart, as contrast for the main results.
- **D6.** "Which side drives" is reported both per type and as score gaps against FP. The gaps are the primary reading, because softmax ignores common shifts.

## Settings and seeds

- **Code and environment.**
  - Commit `20615ad`, branch `main`, clean tree.
  - Package `ai-it-labour-sim` 0.1.0, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1; matplotlib through `uv run --with`.
  - Python 3.12.10 on Windows 11 ARM64. `NPY_DISABLE_CPU_FEATURES` unset; it does not apply on ARM64.
- **Deterministic runs.**
  - `Experiment(scenario=s)` for Baseline, `Slow AI` (g 0.05, VerifDecline 0), `Fast AI` (g 0.20, VerifDecline 0.10) and `Jevons rebound` (JevonsEps 0.5).
  - Settings: `record_every=1`, `stop=16`, `dt=1/16`, `workers=1`, validation on.
- **Monte Carlo.**
  - The 14 `aisim.scenarios.TORNADO` levers, each `Uniform(lo, hi)`: 1,000 runs, `method="lhs"`, `seed=20261012`.
  - Settings: `record_every=1`, `stop=16`, `chunk_size=500`, 2 workers, validation on, **0 invalid runs**.
- **Traces.** `aisim.run(trace=..., record_every=1/16)` on the scalar engine, for the baseline and `PriceHorizon=0`.
- **Sweeps.** `Experiment(scenario=s, overrides={"PriceHorizon": x})` for Baseline, Fast AI and Slow AI, x in {0, 1, 2, 3, 4, 5, 6, 7, 7.877, 8, 9, 10, 12}: 39 deterministic runs, all validated, 0 rejected.
- **Percentiles** use `aisim.experiment.results.pct` over valid runs.
- **Records.** `meta.json` holds the experiment, seed, outputs, versions, git state and platform. `checks.csv` holds the 13 checks (all pass).

## Files

- **Charts:**
  - `shift_share.png`;
  - `utility_OIT.png`, `utility_GSI.png`, `utility_BQ.png`;
  - `price_horizon_sweep.png`;
  - `price_horizon_scenarios.png`;
  - `revenue_weights.png`.
- **Chart data:** `chart_shift_share.csv`, `chart_utility.csv`, `chart_revenue_weights.csv`, `price_horizon_sweep.csv`.
- **Tables:**
  - A: `shift_share_baseline.csv`, `shift_share_mc.csv`, `revenue_weights_baseline.csv`;
  - B: `scenarios_to_2040.csv`, `phase5_comparison.csv`, `phase5_t2.csv`, `phase_bisect.csv`;
  - C: `choice_components.csv`, `choice_components_PH0.csv`, `choice_movements.csv`, `choice_gaps_vs_FP.csv`, `choice_subterms_2032.csv`;
  - D: `price_horizon_sweep.csv`, `price_horizon_sweep_flags.csv`, `price_horizon_no_shift.csv`, `price_horizon_zero.csv`;
  - other: `keys.csv`, `samples.csv`, `checks.csv`, `tables.md`.
- **Scripts:** `run.py`, `phase5_repro.py`, `phase_bisect.py`.
- **Copies:** `proto/` (prototype code, `calib7.json` and the regenerated JSON) and `spec/` (copied specs; the line numbers above refer to these copies).

## Notes for slice 5 (new beyond Q01)

- **The type-choice components are not observable.** `Ucons`, `Uvend` and `Score` per type are loop locals (`finance.py:280-291`), and `ClientP` is state that `trace` never sees. Answering "who pushes" took a reconstruction of the formula. Two possible routes:
  - extras such as `ClientP_{v}` (a state read, allowed under the extras rule);
  - stored `Score` and term fields on `VendorBook`. This is a scalar engine change and would need its own slice prompt.
- **No shift-share helper.** A derived decomposition of `EffortShare_revenue_weighted` into within, between and interaction would remove about 20 lines of analysis code.
- **One-parameter sweeps** took 39 `run_experiment` calls (scenario x grid). An explicit `samples` design would batch them, but one invalid point rejects the whole design, so per-point validation fallback forces separate calls. A sweep helper with per-point validation results would help.
- **Prototype phase chains.** Reproducing an earlier phase means regenerating the phase-to-phase calibration JSON. A tool next to `tools/reference_runner.py` that runs a phase's tests in a scratch copy would make phase bisects routine.
