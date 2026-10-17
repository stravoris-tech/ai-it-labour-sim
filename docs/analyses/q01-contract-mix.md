> **Analysis Q01, from the development of this model.** Copied verbatim below the line from the analysis's findings note.
>
> - **Question:** How does the vendors' contract book shift between fixed price, time and materials, managed services, staff augmentation and outcome-based contracts from 2024 to 2032, by vendor (OIT, GSI, BQ)?
> - **Ran on:** commit `20615ad`, model `phase7`. Commit ids refer to the private development repository.
> - **Model:** It ran on `phase7`, before the model selector existed (slice 8), so it names no model.
> - **Paths:** Paths under `temp/` (the analysis scripts, CSVs, charts and saved results it names) refer to the development workspace and are not in this repository.

---

# Q01 - how the contract book shifts between contract types, 2024-2032

Reproduce (from the repo root, one command; writes every CSV, PNG and table in this folder):

```
uv run --with matplotlib python temp/analysis/q01-contract-mix/run.py
```

Runs used commit `20615ad` on branch `main` (clean tree). No model change; no `analysis/` branch.

## The question

How does the vendors' contract book shift between fixed price (FP), time and materials (TM), managed services (MS), staff augmentation (SA) and outcome-based (OB) from 2024 to 2032, by vendor (OIT, GSI, BQ)? (1) Which types gain and lose share, and how fast? (2) Does the new-signing mix lead the book, and by how much? (3) How sure is the answer, and which levers move the 2032 effort-billed share (TM + SA) most?

## Short answer

**1. Who gains and who loses.** Fixed price loses share at every vendor, fastest at BQ: there it falls from 0.300 in 2024 to 0.205 in 2032 in the baseline, about -1.2 points a year. The Monte Carlo median is 0.247, with p10-p90 0.211-0.284. GSI's FP share goes from 0.380 to 0.328 (median 0.349) and OIT's from 0.350 to 0.312 (median 0.330). The gainers differ by vendor:
- **OIT and GSI:** the book tilts to managed services. OIT's MS share goes from 0.220 to 0.265 (median 0.273), GSI's from 0.300 to 0.318 (median 0.329).
- **BQ:** the book tilts to effort billing. SA goes from 0.170 to 0.241 (median 0.225) and TM from 0.450 to 0.494 (median 0.456).
- **OB** stays at 2-5% everywhere.

Most of the movement happens from 2026 to 2030. It flattens by 2032 as the signing mix turns back.

In absolute terms, OIT's whole book shrinks to 0.61 of its 2024 size and every type shrinks with it (FP -46%, TM -43%), so OIT's MS share rises because MS shrinks least. GSI's book shrinks to 0.77. BQ's grows to 1.11, with its TM and SA books growing about 0.10 each.

The revenue-weighted effort-billed share goes from 0.394 in 2024 to 0.464 in 2032 in the baseline. The Monte Carlo median is 0.423, with p10-p90 0.383-0.469.

**2. Do signings lead the book?** Yes in direction, but the book does not converge to the raw signing mix. In 2024, signings are already far more effort-billed than the book: OIT signs 0.62 TM + SA against a 0.40 book. The book runs off by contract length (MS 6 years, SA 1 year), so it tends towards the duration-weighted signing mix (`implied_mix.csv`), and a large gap to the raw signing mix persists (about 0.27 for OIT TM + SA in 2032).

Timed by turning points in a fine-step baseline run, the signing mix turns around 2029.3 (FP trough, TM + SA peak) and the book follows:
- **FP book:** 1.6 years later at OIT, 1.8 at GSI and 2.2 at BQ.
- **TM + SA book:** about 0 years later at OIT, 0.8 at GSI and 2.4 at BQ.

The planned lag measure (inverse interpolation of signings) is undefined for 15 of 15 vendor-type pairs, because no signing series is monotone over 2024-2032. The same holds against the duration-weighted mix.

**3. How sure.** The p10-p90 bands are narrow until 2026. By 2032 they are 6-9 points wide for each vendor's effort share and up to 7 points for single types (OB under 1 point). The direction of change agrees between the baseline and the Monte Carlo median for every type except two: GSI's TM gains 2.1 points in the baseline but has a median change of -0.6, and OIT's OB is flat in both (-0.1 against +0.03). One lever dominates: the client price horizon (`PriceHorizon`):
- Spearman rho with the 2032 revenue-weighted effort share is +0.77.
- Rho with the 2032 FP share is -0.89 to -0.95 at each vendor.
- Next come sourcing cost sensitivity (rho -0.51 on effort share, almost none on FP shares, so it acts through the vendor revenue weights) and the junior cut (+0.25 on effort share, -0.29 to -0.44 on FP).
- The other 11 levers have |rho| below 0.1, including AI capability growth `g`.

The calibrated `PriceHorizon` (7.877) sits at the 97th percentile of its sampled range (4-8). So the baseline lies near the top of the effort-share band and the bottom of the FP band: most sampled runs have a shorter price horizon than the calibrated one. The four scenarios move the 2032 revenue-weighted effort share less than the band does: 0.435 (Slow AI) to 0.478 (Fast AI), with Jevons rebound equal to the baseline at 0.464.

## Evidence (files in this folder)

- Charts:
  - `book_mix_{OIT,GSI,BQ}.png`: book share by type, Monte Carlo median with p10-p90 band, baseline dashed.
  - `sign_mix_{v}.png`: the same for new signings.
  - `scenarios_{v}.png`: four-scenario small multiples.
  - `lead_{v}.png`: signing, duration-weighted and book shares, fine-step baseline.
  - `drivers.png`: Spearman bars, four targets.
- Each chart's data is in `chart_*.csv`. The drivers chart's data is `drivers.csv`.
- Tables (CSV, reproduced below):
  - mix: `book_mix.csv`, `sign_mix.csv`, `share_change.csv`, `book_volume.csv`;
  - lead: `sign_minus_book_gap.csv`, `implied_mix.csv`, `lag_baseline.csv`, `lag_behind_implied_baseline.csv`, `lag_effort_mc_2032.csv`, `turning_points_baseline.csv`;
  - other: `avg_new_duration.csv`, `scenarios_2032.csv`, `drivers.csv`, `aggregation_check.csv`, `sanity_checks.csv`, `band_widths.csv`, `keys.csv`.
- Reproducibility: `meta.json` (experiment, seed, outputs, versions, `NPY_DISABLE_CPU_FEATURES`, `n_invalid`, git commit and branch, platform), `samples.csv` (the 1,000 x 14 LHS design), `timings.json` and `summary.json`.

## D-rulings (minor decisions taken)

- **D1. Output location.** Everything is in `temp/analysis/q01-contract-mix/`, and the prompt's `report.md` is this `findings.md` (user ruling).
- **D2. Lag measure, as planned.** The book's lag behind signings is L with book(t) = sign(t - L), by inverse linear interpolation of the signing series. Where a signing series is not monotone over 2024-2032, it is reported as "n/a (signings not monotone)" (user ruling). That covers 15 of 15 vendor-type pairs, the 3 TM + SA aggregates and all 1,000 Monte Carlo runs, so the measure gives no number here.
- **D3. Two extra lead measures, so that Q2 has an answer:**
  - the steady-state book mix implied by the current signings and new-contract durations, `Sign_k x Dnew_k` normalised. This reads the extra `Dnew_{v}_{k}` (15 keys added to the outputs) and computes no new model formula;
  - the timing of the first turning point after 2026 of the same kind (peak or trough) in signings and in the book, from a baseline run recorded every dt (1/16 year). Turns before 2026 are a small transient at about 2024.5 in every signing series; they are listed in `turning_points_baseline.csv` and left out of the lead.
- **D4. Monotonicity tolerance.** Year-on-year changes within 1e-12 count as flat.
- **D5. Second sanity check added:** `EffortShare_v = Mix_TM + Mix_SA` (it passes).

## Tables (generated by run.py; also in tables.md)

### Resolved keys

- **contract mix (book)** (15): `Mix_OIT_FP`, `Mix_OIT_TM`, `Mix_OIT_MS`, `Mix_OIT_SA`, `Mix_OIT_OB`, `Mix_GSI_FP`, `Mix_GSI_TM`, `Mix_GSI_MS`, `Mix_GSI_SA`, `Mix_GSI_OB`, `Mix_BQ_FP`, `Mix_BQ_TM`, `Mix_BQ_MS`, `Mix_BQ_SA`, `Mix_BQ_OB`
- **contract mix (new signings)** (15): `Sign_OIT_FP`, `Sign_OIT_TM`, `Sign_OIT_MS`, `Sign_OIT_SA`, `Sign_OIT_OB`, `Sign_GSI_FP`, `Sign_GSI_TM`, `Sign_GSI_MS`, `Sign_GSI_SA`, `Sign_GSI_OB`, `Sign_BQ_FP`, `Sign_BQ_TM`, `Sign_BQ_MS`, `Sign_BQ_SA`, `Sign_BQ_OB`
- **contract book (extra)** (15): `Book_OIT_FP`, `Book_OIT_TM`, `Book_OIT_MS`, `Book_OIT_SA`, `Book_OIT_OB`, `Book_GSI_FP`, `Book_GSI_TM`, `Book_GSI_MS`, `Book_GSI_SA`, `Book_GSI_OB`, `Book_BQ_FP`, `Book_BQ_TM`, `Book_BQ_MS`, `Book_BQ_SA`, `Book_BQ_OB`
- **new signings (extra)** (15): `SignVol_OIT_FP`, `SignVol_OIT_TM`, `SignVol_OIT_MS`, `SignVol_OIT_SA`, `SignVol_OIT_OB`, `SignVol_GSI_FP`, `SignVol_GSI_TM`, `SignVol_GSI_MS`, `SignVol_GSI_SA`, `SignVol_GSI_OB`, `SignVol_BQ_FP`, `SignVol_BQ_TM`, `SignVol_BQ_MS`, `SignVol_BQ_SA`, `SignVol_BQ_OB`
- **effort-billed share** (3): `EffortShare_OIT`, `EffortShare_GSI`, `EffortShare_BQ`
- **derived** (1): `EffortShare_revenue_weighted`
- **vendor revenue** (4): `Revenue_OIT`, `Revenue_GSI`, `Revenue_BQ`, `RevenueTot`
- **work share by employer** (3): `WorkShare_OIT`, `WorkShare_GSI`, `WorkShare_BQ`
- **contract terms and pricing** (3): `AvgNewDur_OIT`, `AvgNewDur_GSI`, `AvgNewDur_BQ`
- **new-contract duration (extra)** (15): `Dnew_OIT_FP`, `Dnew_OIT_TM`, `Dnew_OIT_MS`, `Dnew_OIT_SA`, `Dnew_OIT_OB`, `Dnew_GSI_FP`, `Dnew_GSI_TM`, `Dnew_GSI_MS`, `Dnew_GSI_SA`, `Dnew_GSI_OB`, `Dnew_BQ_FP`, `Dnew_BQ_TM`, `Dnew_BQ_MS`, `Dnew_BQ_SA`, `Dnew_BQ_OB`

### Book mix (cell: baseline / MC median (p10-p90))

#### OIT

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.350 / 0.350 (0.350-0.350) | 0.348 / 0.352 (0.349-0.356) | 0.327 / 0.340 (0.329-0.353) | 0.311 / 0.330 (0.313-0.348) | 0.312 / 0.330 (0.312-0.348) |
| TM | 0.300 / 0.300 (0.300-0.300) | 0.293 / 0.290 (0.286-0.294) | 0.307 / 0.292 (0.280-0.306) | 0.304 / 0.283 (0.266-0.300) | 0.282 / 0.260 (0.241-0.278) |
| MS | 0.220 / 0.220 (0.220-0.220) | 0.227 / 0.228 (0.224-0.232) | 0.228 / 0.232 (0.225-0.240) | 0.240 / 0.247 (0.239-0.258) | 0.265 / 0.273 (0.262-0.286) |
| SA | 0.100 / 0.100 (0.100-0.100) | 0.101 / 0.100 (0.097-0.102) | 0.110 / 0.104 (0.095-0.114) | 0.117 / 0.109 (0.095-0.124) | 0.113 / 0.106 (0.091-0.124) |
| OB | 0.030 / 0.030 (0.030-0.030) | 0.030 / 0.030 (0.030-0.031) | 0.029 / 0.030 (0.029-0.031) | 0.028 / 0.030 (0.028-0.031) | 0.029 / 0.030 (0.029-0.032) |

#### GSI

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.380 / 0.380 (0.380-0.380) | 0.377 / 0.380 (0.377-0.384) | 0.352 / 0.366 (0.353-0.378) | 0.330 / 0.350 (0.332-0.368) | 0.328 / 0.349 (0.331-0.365) |
| TM | 0.220 / 0.220 (0.220-0.220) | 0.217 / 0.213 (0.209-0.216) | 0.240 / 0.223 (0.208-0.238) | 0.253 / 0.227 (0.205-0.250) | 0.241 / 0.214 (0.192-0.235) |
| MS | 0.300 / 0.300 (0.300-0.300) | 0.305 / 0.307 (0.306-0.309) | 0.301 / 0.307 (0.302-0.313) | 0.303 / 0.314 (0.304-0.323) | 0.318 / 0.329 (0.319-0.340) |
| SA | 0.050 / 0.050 (0.050-0.050) | 0.051 / 0.050 (0.048-0.051) | 0.060 / 0.055 (0.049-0.061) | 0.069 / 0.062 (0.053-0.072) | 0.067 / 0.060 (0.051-0.072) |
| OB | 0.050 / 0.050 (0.050-0.050) | 0.050 / 0.050 (0.050-0.051) | 0.047 / 0.049 (0.047-0.050) | 0.045 / 0.047 (0.045-0.050) | 0.045 / 0.048 (0.046-0.050) |

#### BQ

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.300 / 0.300 (0.300-0.300) | 0.297 / 0.303 (0.292-0.313) | 0.255 / 0.278 (0.255-0.299) | 0.217 / 0.253 (0.220-0.285) | 0.205 / 0.247 (0.211-0.284) |
| TM | 0.450 / 0.450 (0.450-0.450) | 0.446 / 0.441 (0.436-0.448) | 0.473 / 0.454 (0.437-0.474) | 0.491 / 0.460 (0.434-0.489) | 0.494 / 0.456 (0.427-0.487) |
| MS | 0.050 / 0.050 (0.050-0.050) | 0.051 / 0.051 (0.047-0.055) | 0.046 / 0.048 (0.042-0.054) | 0.041 / 0.046 (0.040-0.052) | 0.039 / 0.045 (0.039-0.052) |
| SA | 0.170 / 0.170 (0.170-0.170) | 0.176 / 0.174 (0.165-0.184) | 0.199 / 0.191 (0.175-0.209) | 0.228 / 0.215 (0.193-0.241) | 0.241 / 0.225 (0.199-0.257) |
| OB | 0.030 / 0.030 (0.030-0.030) | 0.030 / 0.030 (0.029-0.032) | 0.026 / 0.028 (0.025-0.030) | 0.022 / 0.026 (0.022-0.029) | 0.021 / 0.025 (0.022-0.028) |

### New-signing mix (cell: baseline / MC median (p10-p90))

#### OIT

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.283 / 0.283 (0.283-0.283) | 0.265 / 0.279 (0.267-0.291) | 0.228 / 0.252 (0.230-0.276) | 0.223 / 0.248 (0.224-0.275) | 0.252 / 0.274 (0.249-0.300) |
| TM | 0.405 / 0.405 (0.405-0.405) | 0.421 / 0.409 (0.399-0.421) | 0.442 / 0.419 (0.400-0.442) | 0.427 / 0.404 (0.384-0.426) | 0.401 / 0.380 (0.361-0.400) |
| MS | 0.074 / 0.074 (0.074-0.074) | 0.069 / 0.072 (0.069-0.075) | 0.059 / 0.065 (0.059-0.071) | 0.058 / 0.064 (0.058-0.071) | 0.066 / 0.071 (0.065-0.078) |
| SA | 0.218 / 0.218 (0.218-0.218) | 0.226 / 0.220 (0.210-0.228) | 0.254 / 0.244 (0.221-0.267) | 0.276 / 0.263 (0.236-0.295) | 0.263 / 0.253 (0.224-0.288) |
| OB | 0.020 / 0.020 (0.020-0.020) | 0.019 / 0.020 (0.019-0.021) | 0.016 / 0.018 (0.016-0.020) | 0.016 / 0.018 (0.016-0.020) | 0.018 / 0.020 (0.018-0.022) |

#### GSI

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.363 / 0.363 (0.363-0.363) | 0.340 / 0.357 (0.343-0.371) | 0.290 / 0.322 (0.292-0.352) | 0.280 / 0.316 (0.284-0.347) | 0.311 / 0.342 (0.314-0.369) |
| TM | 0.350 / 0.350 (0.350-0.350) | 0.374 / 0.357 (0.342-0.373) | 0.419 / 0.384 (0.355-0.417) | 0.415 / 0.379 (0.349-0.409) | 0.383 / 0.351 (0.325-0.373) |
| MS | 0.119 / 0.119 (0.119-0.119) | 0.111 / 0.117 (0.112-0.121) | 0.095 / 0.105 (0.096-0.114) | 0.092 / 0.103 (0.094-0.114) | 0.102 / 0.112 (0.103-0.121) |
| SA | 0.128 / 0.128 (0.128-0.128) | 0.137 / 0.131 (0.123-0.137) | 0.164 / 0.152 (0.135-0.171) | 0.182 / 0.167 (0.146-0.192) | 0.169 / 0.158 (0.136-0.185) |
| OB | 0.040 / 0.040 (0.040-0.040) | 0.037 / 0.039 (0.037-0.040) | 0.032 / 0.035 (0.032-0.038) | 0.031 / 0.035 (0.031-0.038) | 0.034 / 0.038 (0.035-0.041) |

#### BQ

| type | 2024 | 2026 | 2028 | 2030 | 2032 |
| --- | --- | --- | --- | --- | --- |
| FP | 0.193 / 0.193 (0.193-0.193) | 0.172 / 0.187 (0.174-0.201) | 0.128 / 0.154 (0.130-0.180) | 0.112 / 0.141 (0.116-0.170) | 0.122 / 0.154 (0.127-0.183) |
| TM | 0.483 / 0.483 (0.483-0.483) | 0.499 / 0.487 (0.477-0.500) | 0.516 / 0.495 (0.473-0.520) | 0.504 / 0.480 (0.455-0.508) | 0.497 / 0.469 (0.442-0.497) |
| MS | 0.013 / 0.013 (0.013-0.013) | 0.012 / 0.013 (0.012-0.014) | 0.009 / 0.011 (0.009-0.012) | 0.008 / 0.010 (0.008-0.012) | 0.009 / 0.011 (0.009-0.013) |
| SA | 0.294 / 0.294 (0.294-0.294) | 0.304 / 0.297 (0.285-0.307) | 0.336 / 0.326 (0.301-0.353) | 0.367 / 0.355 (0.324-0.390) | 0.362 / 0.351 (0.319-0.390) |
| OB | 0.016 / 0.016 (0.016-0.016) | 0.014 / 0.015 (0.014-0.017) | 0.011 / 0.013 (0.011-0.015) | 0.009 / 0.012 (0.010-0.014) | 0.010 / 0.013 (0.011-0.015) |

### Change in book share 2024-2032 (percentage points)

| vendor | type | baseline_2024 | baseline_2032 | baseline_change_pp | baseline_pp_per_year | median_change_pp |
| --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | 0.35 | 0.31 | -3.79 | -0.47 | -1.98 |
| OIT | TM | 0.30 | 0.28 | -1.85 | -0.23 | -4.00 |
| OIT | MS | 0.22 | 0.26 | 4.49 | 0.56 | 5.33 |
| OIT | SA | 0.10 | 0.11 | 1.25 | 0.16 | 0.58 |
| OIT | OB | 0.03 | 0.03 | -0.11 | -0.01 | 0.03 |
| GSI | FP | 0.38 | 0.33 | -5.16 | -0.65 | -3.13 |
| GSI | TM | 0.22 | 0.24 | 2.09 | 0.26 | -0.59 |
| GSI | MS | 0.30 | 0.32 | 1.80 | 0.23 | 2.91 |
| GSI | SA | 0.05 | 0.07 | 1.74 | 0.22 | 1.03 |
| GSI | OB | 0.05 | 0.05 | -0.47 | -0.06 | -0.23 |
| BQ | FP | 0.30 | 0.20 | -9.52 | -1.19 | -5.31 |
| BQ | TM | 0.45 | 0.49 | 4.43 | 0.55 | 0.57 |
| BQ | MS | 0.05 | 0.04 | -1.08 | -0.14 | -0.48 |
| BQ | SA | 0.17 | 0.24 | 7.08 | 0.88 | 5.53 |
| BQ | OB | 0.03 | 0.02 | -0.91 | -0.11 | -0.51 |

### Book volume by type (vendor 2024 book = 1)

| vendor | type | baseline_2024 | baseline_2032 | baseline_change | median_2032 | p10_2032 | p90_2032 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | 0.350 | 0.189 | -0.161 | 0.201 | 0.183 | 0.217 |
| OIT | TM | 0.300 | 0.171 | -0.129 | 0.158 | 0.141 | 0.175 |
| OIT | MS | 0.220 | 0.160 | -0.060 | 0.166 | 0.157 | 0.175 |
| OIT | SA | 0.100 | 0.068 | -0.032 | 0.064 | 0.054 | 0.076 |
| OIT | OB | 0.030 | 0.018 | -0.012 | 0.018 | 0.017 | 0.020 |
| OIT | total | 1.000 | 0.606 | -0.394 | 0.610 | 0.568 | 0.645 |
| GSI | FP | 0.380 | 0.252 | -0.128 | 0.266 | 0.251 | 0.284 |
| GSI | TM | 0.220 | 0.185 | -0.035 | 0.164 | 0.147 | 0.181 |
| GSI | MS | 0.300 | 0.244 | -0.056 | 0.252 | 0.242 | 0.263 |
| GSI | SA | 0.050 | 0.052 | 0.002 | 0.046 | 0.039 | 0.056 |
| GSI | OB | 0.050 | 0.035 | -0.015 | 0.036 | 0.035 | 0.039 |
| GSI | total | 1.000 | 0.768 | -0.232 | 0.769 | 0.741 | 0.788 |
| BQ | FP | 0.300 | 0.226 | -0.074 | 0.257 | 0.200 | 0.351 |
| BQ | TM | 0.450 | 0.547 | 0.097 | 0.485 | 0.358 | 0.668 |
| BQ | MS | 0.050 | 0.043 | -0.007 | 0.047 | 0.040 | 0.059 |
| BQ | SA | 0.170 | 0.266 | 0.096 | 0.235 | 0.172 | 0.344 |
| BQ | OB | 0.030 | 0.023 | -0.007 | 0.026 | 0.021 | 0.035 |
| BQ | total | 1.000 | 1.106 | 0.106 | 1.053 | 0.810 | 1.451 |

### Signing minus book share (gap), baseline and MC

| vendor | type | year | baseline_gap | median_gap | p10_gap | p90_gap |
| --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | 2026 | -0.083 | -0.073 | -0.082 | -0.064 |
| OIT | FP | 2032 | -0.060 | -0.056 | -0.066 | -0.045 |
| OIT | TM | 2026 | 0.127 | 0.119 | 0.112 | 0.128 |
| OIT | TM | 2032 | 0.120 | 0.120 | 0.109 | 0.130 |
| OIT | MS | 2026 | -0.158 | -0.156 | -0.161 | -0.152 |
| OIT | MS | 2032 | -0.199 | -0.202 | -0.210 | -0.195 |
| OIT | SA | 2026 | 0.125 | 0.120 | 0.112 | 0.127 |
| OIT | SA | 2032 | 0.150 | 0.147 | 0.133 | 0.166 |
| OIT | OB | 2026 | -0.011 | -0.011 | -0.011 | -0.010 |
| OIT | OB | 2032 | -0.011 | -0.010 | -0.011 | -0.010 |
| GSI | FP | 2026 | -0.036 | -0.023 | -0.034 | -0.012 |
| GSI | FP | 2032 | -0.017 | -0.007 | -0.019 | 0.005 |
| GSI | TM | 2026 | 0.157 | 0.144 | 0.133 | 0.157 |
| GSI | TM | 2032 | 0.142 | 0.136 | 0.129 | 0.144 |
| GSI | MS | 2026 | -0.194 | -0.191 | -0.194 | -0.187 |
| GSI | MS | 2032 | -0.216 | -0.217 | -0.221 | -0.214 |
| GSI | SA | 2026 | 0.086 | 0.081 | 0.075 | 0.086 |
| GSI | SA | 2032 | 0.102 | 0.097 | 0.085 | 0.112 |
| GSI | OB | 2026 | -0.013 | -0.011 | -0.013 | -0.010 |
| GSI | OB | 2032 | -0.011 | -0.010 | -0.011 | -0.009 |
| BQ | FP | 2026 | -0.125 | -0.115 | -0.127 | -0.104 |
| BQ | FP | 2032 | -0.083 | -0.093 | -0.101 | -0.082 |
| BQ | TM | 2026 | 0.053 | 0.046 | 0.037 | 0.057 |
| BQ | TM | 2032 | 0.002 | 0.013 | -0.002 | 0.028 |
| BQ | MS | 2026 | -0.039 | -0.038 | -0.042 | -0.034 |
| BQ | MS | 2032 | -0.031 | -0.034 | -0.040 | -0.029 |
| BQ | SA | 2026 | 0.127 | 0.122 | 0.113 | 0.131 |
| BQ | SA | 2032 | 0.122 | 0.126 | 0.117 | 0.137 |
| BQ | OB | 2026 | -0.016 | -0.015 | -0.016 | -0.014 |
| BQ | OB | 2032 | -0.011 | -0.012 | -0.014 | -0.011 |

### Lag of the book behind signings (years), baseline

| vendor | type | lag_2026 | lag_2028 | lag_2030 | lag_2032 |
| --- | --- | --- | --- | --- | --- |
| OIT | FP | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| OIT | TM | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| OIT | MS | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| OIT | SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| OIT | OB | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | FP | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | TM | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | MS | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | OB | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | FP | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | TM | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | MS | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | OB | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| OIT | TM+SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| GSI | TM+SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |
| BQ | TM+SA | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) | n/a (signings not monotone) |

### Lag of the effort-billed book share (TM + SA) behind signings at 2032, per MC run

| vendor | runs_ok | runs_not_monotone | runs_behind | runs_ahead | lag_p10 | lag_median | lag_p90 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OIT | 0 | 1000 | 0 | 0 | n/a | n/a | n/a |
| GSI | 0 | 1000 | 0 | 0 | n/a | n/a | n/a |
| BQ | 0 | 1000 | 0 | 0 | n/a | n/a | n/a |

### Implied (duration-weighted) signing mix against the book

| vendor | type | year | sign_baseline | implied_baseline | book_baseline | implied_median | implied_p10 | implied_p90 | book_minus_implied_median |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | 2024 | 0.283 | 0.347 | 0.350 | 0.347 | 0.347 | 0.347 | 0.003 |
| OIT | FP | 2028 | 0.228 | 0.302 | 0.327 | 0.323 | 0.303 | 0.344 | 0.017 |
| OIT | FP | 2032 | 0.252 | 0.324 | 0.312 | 0.343 | 0.323 | 0.363 | -0.013 |
| OIT | TM | 2024 | 0.405 | 0.298 | 0.300 | 0.298 | 0.298 | 0.298 | 0.002 |
| OIT | TM | 2028 | 0.442 | 0.350 | 0.307 | 0.322 | 0.299 | 0.348 | -0.030 |
| OIT | TM | 2032 | 0.401 | 0.310 | 0.282 | 0.285 | 0.265 | 0.305 | -0.025 |
| OIT | MS | 2024 | 0.074 | 0.218 | 0.220 | 0.218 | 0.218 | 0.218 | 0.002 |
| OIT | MS | 2028 | 0.059 | 0.188 | 0.228 | 0.200 | 0.188 | 0.213 | 0.032 |
| OIT | MS | 2032 | 0.066 | 0.203 | 0.265 | 0.214 | 0.202 | 0.226 | 0.059 |
| OIT | SA | 2024 | 0.218 | 0.107 | 0.100 | 0.107 | 0.107 | 0.107 | -0.007 |
| OIT | SA | 2028 | 0.254 | 0.134 | 0.110 | 0.125 | 0.110 | 0.141 | -0.020 |
| OIT | SA | 2032 | 0.263 | 0.135 | 0.113 | 0.127 | 0.109 | 0.149 | -0.021 |
| OIT | OB | 2024 | 0.020 | 0.030 | 0.030 | 0.030 | 0.030 | 0.030 | 0.000 |
| OIT | OB | 2028 | 0.016 | 0.026 | 0.029 | 0.028 | 0.026 | 0.029 | 0.002 |
| OIT | OB | 2032 | 0.018 | 0.028 | 0.029 | 0.030 | 0.028 | 0.032 | 0.001 |
| GSI | FP | 2024 | 0.363 | 0.379 | 0.380 | 0.379 | 0.379 | 0.379 | 0.001 |
| GSI | FP | 2028 | 0.290 | 0.332 | 0.352 | 0.354 | 0.334 | 0.374 | 0.011 |
| GSI | FP | 2032 | 0.311 | 0.348 | 0.328 | 0.368 | 0.351 | 0.384 | -0.019 |
| GSI | TM | 2024 | 0.350 | 0.219 | 0.220 | 0.219 | 0.219 | 0.219 | 0.001 |
| GSI | TM | 2028 | 0.419 | 0.288 | 0.240 | 0.254 | 0.226 | 0.286 | -0.031 |
| GSI | TM | 2032 | 0.383 | 0.256 | 0.241 | 0.226 | 0.204 | 0.249 | -0.013 |
| GSI | MS | 2024 | 0.119 | 0.299 | 0.300 | 0.299 | 0.299 | 0.299 | 0.001 |
| GSI | MS | 2028 | 0.095 | 0.261 | 0.301 | 0.277 | 0.262 | 0.291 | 0.030 |
| GSI | MS | 2032 | 0.102 | 0.274 | 0.318 | 0.289 | 0.277 | 0.301 | 0.040 |
| GSI | SA | 2024 | 0.128 | 0.054 | 0.050 | 0.054 | 0.054 | 0.054 | -0.004 |
| GSI | SA | 2028 | 0.164 | 0.075 | 0.060 | 0.067 | 0.058 | 0.077 | -0.012 |
| GSI | SA | 2032 | 0.169 | 0.076 | 0.067 | 0.068 | 0.057 | 0.082 | -0.008 |
| GSI | OB | 2024 | 0.040 | 0.050 | 0.050 | 0.050 | 0.050 | 0.050 | 0.000 |
| GSI | OB | 2028 | 0.032 | 0.044 | 0.047 | 0.046 | 0.044 | 0.049 | 0.002 |
| GSI | OB | 2032 | 0.034 | 0.046 | 0.045 | 0.049 | 0.046 | 0.051 | -0.001 |
| BQ | FP | 2024 | 0.193 | 0.296 | 0.300 | 0.296 | 0.296 | 0.296 | 0.004 |
| BQ | FP | 2028 | 0.128 | 0.211 | 0.255 | 0.247 | 0.214 | 0.281 | 0.031 |
| BQ | FP | 2032 | 0.122 | 0.205 | 0.205 | 0.249 | 0.213 | 0.287 | -0.003 |
| BQ | TM | 2024 | 0.483 | 0.444 | 0.450 | 0.444 | 0.444 | 0.444 | 0.006 |
| BQ | TM | 2028 | 0.516 | 0.511 | 0.473 | 0.477 | 0.448 | 0.511 | -0.022 |
| BQ | TM | 2032 | 0.497 | 0.498 | 0.494 | 0.455 | 0.425 | 0.487 | 0.001 |
| BQ | MS | 2024 | 0.013 | 0.049 | 0.050 | 0.049 | 0.049 | 0.049 | 0.001 |
| BQ | MS | 2028 | 0.009 | 0.035 | 0.046 | 0.041 | 0.036 | 0.046 | 0.007 |
| BQ | MS | 2032 | 0.009 | 0.034 | 0.039 | 0.041 | 0.036 | 0.047 | 0.004 |
| BQ | SA | 2024 | 0.294 | 0.181 | 0.170 | 0.181 | 0.181 | 0.181 | -0.011 |
| BQ | SA | 2028 | 0.336 | 0.222 | 0.199 | 0.210 | 0.188 | 0.232 | -0.019 |
| BQ | SA | 2032 | 0.362 | 0.243 | 0.241 | 0.228 | 0.200 | 0.261 | -0.002 |
| BQ | OB | 2024 | 0.016 | 0.030 | 0.030 | 0.030 | 0.030 | 0.030 | 0.000 |
| BQ | OB | 2028 | 0.011 | 0.021 | 0.026 | 0.024 | 0.021 | 0.028 | 0.004 |
| BQ | OB | 2032 | 0.010 | 0.020 | 0.021 | 0.025 | 0.021 | 0.028 | 0.000 |

### Lag of the book behind the implied mix (years), baseline run every dt

| vendor | type | lag_2026 | lag_2028 | lag_2030 | lag_2032 |
| --- | --- | --- | --- | --- | --- |
| OIT | FP | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| OIT | TM | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| OIT | MS | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| OIT | SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| OIT | OB | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| OIT | TM+SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | FP | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | TM | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | MS | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | OB | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| GSI | TM+SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | FP | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | TM | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | MS | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | OB | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |
| BQ | TM+SA | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) | n/a (implied mix not monotone) |

### Main turning points after 2026, baseline run every dt, 2024-2040 (book turn of the same kind; NaN = none by 2040)

| vendor | type | kind | sign_turn | implied_turn | book_turn | book_minus_sign | sign_early_turns |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OIT | FP | trough | 2029.31 | 2029.19 | 2030.88 | 1.56 | 2024.50 |
| OIT | TM | peak | 2028.00 | 2028.56 | 2028.81 | 0.81 | 2024.44 |
| OIT | MS | trough | 2029.25 | 2029.12 | 2027.00 | -2.25 | 2024.50 |
| OIT | SA | peak | 2030.00 | 2030.00 | 2030.19 | 0.19 | 2024.62 |
| OIT | OB | trough | 2029.19 | 2029.06 | 2029.81 | 0.62 | 2024.50 |
| OIT | TM+SA | peak | 2029.31 | 2029.19 | 2029.25 | -0.06 | 2024.50 |
| GSI | FP | trough | 2029.31 | 2029.31 | 2031.12 | 1.81 | 2024.50 |
| GSI | TM | peak | 2028.75 | 2029.00 | 2029.88 | 1.12 | 2024.50 |
| GSI | MS | trough | 2029.31 | 2029.25 | 2028.75 | -0.56 | 2024.50 |
| GSI | SA | peak | 2030.00 | 2030.00 | 2030.69 | 0.69 | 2024.56 |
| GSI | OB | trough | 2029.31 | 2029.25 | 2030.75 | 1.44 | 2024.50 |
| GSI | TM+SA | peak | 2029.31 | 2029.31 | 2030.12 | 0.81 | 2024.50 |
| BQ | FP | trough | 2030.00 | 2030.00 | 2032.19 | 2.19 | 2024.50 |
| BQ | TM | peak | 2027.81 | 2028.81 | 2032.06 | 4.25 | 2024.44 |
| BQ | MS | trough | 2030.00 | 2030.00 | 2035.12 | 5.12 | 2024.50 |
| BQ | SA | peak | 2030.50 | 2030.38 | 2033.69 | 3.19 | 2024.62 |
| BQ | OB | trough | 2030.00 | 2030.00 | 2032.69 | 2.69 | 2024.50 |
| BQ | TM+SA | peak | 2030.00 | 2030.00 | 2032.38 | 2.38 | 2024.50 |

### Average new-contract duration (years)

| vendor | year | baseline | median | p10 | p90 |
| --- | --- | --- | --- | --- | --- |
| OIT | 2024 | 2.04 | 2.04 | 2.04 | 2.04 |
| OIT | 2026 | 1.78 | 1.81 | 1.75 | 1.87 |
| OIT | 2028 | 1.45 | 1.50 | 1.40 | 1.61 |
| OIT | 2030 | 1.34 | 1.40 | 1.29 | 1.55 |
| OIT | 2032 | 1.35 | 1.42 | 1.28 | 1.58 |
| GSI | 2024 | 2.39 | 2.39 | 2.39 | 2.39 |
| GSI | 2026 | 2.07 | 2.12 | 2.04 | 2.18 |
| GSI | 2028 | 1.70 | 1.78 | 1.65 | 1.91 |
| GSI | 2030 | 1.59 | 1.69 | 1.54 | 1.85 |
| GSI | 2032 | 1.61 | 1.71 | 1.55 | 1.90 |
| BQ | 2024 | 1.63 | 1.63 | 1.63 | 1.63 |
| BQ | 2026 | 1.42 | 1.44 | 1.40 | 1.49 |
| BQ | 2028 | 1.18 | 1.21 | 1.12 | 1.29 |
| BQ | 2030 | 1.10 | 1.13 | 1.03 | 1.24 |
| BQ | 2032 | 1.11 | 1.14 | 1.04 | 1.27 |

### 2032 book mix by scenario

| scenario | vendor | FP | TM | MS | SA | OB | TM+SA |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | OIT | 0.312 | 0.282 | 0.265 | 0.113 | 0.029 | 0.394 |
| Baseline | GSI | 0.328 | 0.241 | 0.318 | 0.067 | 0.045 | 0.308 |
| Baseline | BQ | 0.205 | 0.494 | 0.039 | 0.241 | 0.021 | 0.735 |
| Baseline | revenue-weighted | n/a | n/a | n/a | n/a | n/a | 0.464 |
| Slow AI | OIT | 0.319 | 0.277 | 0.257 | 0.118 | 0.029 | 0.395 |
| Slow AI | GSI | 0.342 | 0.224 | 0.320 | 0.067 | 0.047 | 0.291 |
| Slow AI | BQ | 0.235 | 0.462 | 0.045 | 0.234 | 0.024 | 0.696 |
| Slow AI | revenue-weighted | n/a | n/a | n/a | n/a | n/a | 0.435 |
| Fast AI | OIT | 0.317 | 0.270 | 0.283 | 0.101 | 0.030 | 0.371 |
| Fast AI | GSI | 0.327 | 0.241 | 0.324 | 0.063 | 0.046 | 0.304 |
| Fast AI | BQ | 0.192 | 0.514 | 0.036 | 0.238 | 0.020 | 0.753 |
| Fast AI | revenue-weighted | n/a | n/a | n/a | n/a | n/a | 0.478 |
| Jevons rebound | OIT | 0.312 | 0.278 | 0.265 | 0.115 | 0.029 | 0.394 |
| Jevons rebound | GSI | 0.328 | 0.239 | 0.318 | 0.069 | 0.045 | 0.308 |
| Jevons rebound | BQ | 0.205 | 0.489 | 0.039 | 0.247 | 0.021 | 0.735 |
| Jevons rebound | revenue-weighted | n/a | n/a | n/a | n/a | n/a | 0.464 |

### Drivers (Spearman rho with 2032 outputs, ranked by |rho| on EffortShare_revenue_weighted)

| rank | lever | label | rho_EffortShare_revenue_weighted | rho_Mix_OIT_FP | rho_Mix_GSI_FP | rho_Mix_BQ_FP | rank_Mix_OIT_FP | rank_Mix_GSI_FP | rank_Mix_BQ_FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | PriceHorizon | Client price horizon (years) | 0.773 | -0.891 | -0.951 | -0.919 | 1 | 1 | 1 |
| 2 | SrcCostSens | Sourcing cost sensitivity | -0.509 | 0.021 | -0.073 | 0.126 | 9 | 3 | 3 |
| 3 | JuniorCut | Junior cut per unit of adoption | 0.249 | -0.435 | -0.294 | -0.290 | 2 | 2 | 2 |
| 4 | AICostDecline | AI cost decline per year | 0.070 | -0.149 | -0.056 | -0.046 | 3 | 4 | 6 |
| 5 | TMBrake | T&M brake on vendor adoption | -0.044 | 0.016 | 0.002 | 0.029 | 10 | 14 | 8 |
| 6 | JevonsEps | Jevons elasticity | 0.033 | -0.026 | -0.014 | -0.017 | 7 | 9 | 11 |
| 7 | GCCAppealKeep | GCC appeal kept after 2030 | -0.025 | 0.006 | -0.008 | 0.023 | 13 | 12 | 10 |
| 8 | VerifDecline | Verification decline per year | 0.024 | 0.077 | -0.054 | -0.096 | 5 | 5 | 4 |
| 9 | DemandGrowthLate | Underlying demand growth after 2026 | -0.023 | 0.011 | 0.013 | 0.017 | 12 | 11 | 12 |
| 10 | Verif | Verification overhead (2024) | -0.016 | -0.096 | -0.025 | 0.037 | 4 | 7 | 7 |
| 11 | RegScenario | Regulation strength | 0.016 | 0.005 | 0.007 | 0.002 | 14 | 13 | 14 |
| 12 | EnrolSensitivity | Enrolment response to unemployment | -0.014 | -0.012 | -0.014 | 0.003 | 11 | 10 | 13 |
| 13 | g | AI capability growth g | 0.010 | 0.045 | -0.024 | -0.057 | 6 | 8 | 5 |
| 14 | aL_max | Max business-process automation | -0.008 | 0.026 | 0.031 | 0.027 | 8 | 6 | 9 |

### Aggregation check

max relative residual |WorkShare_v(2024) x sum_k Book_v_k(t) / WorkShare_v(t) - 1| = 0.005259 (2024-2032: 0.002613); tolerance 1e-6; valid: False

| vendor | rel_residual |
| --- | --- |
| OIT | 0.005259 |
| GSI | 0.003888 |
| BQ | 0.002791 |

### Sanity checks

| check | result | detail |
| --- | --- | --- |
| 2024 book mix = initial Leg state (Leg / sum Leg), what run() starts from | pass | max |diff| = 0 over 1000 MC runs and the baseline; bit-equal: True; Leg sums per vendor: OIT 1, GSI 1, BQ 1; max |NewV(2024)| = 0 |
| 2024 book mix = Mix0 table (not read by run(), recon 04) | pass | max |diff| = 0; bit-equal: True |
| Book shares sum to 1 per vendor and year | pass | max |sum - 1| = 3.33e-16 (all runs, 2024-2040) |
| Signing shares sum to 1 per vendor and year | pass | max |sum - 1| = 2.22e-16 (all runs, 2024-2040) |
| Book_v_k / sum_k Book_v_k = Mix_v_k | pass | max |diff| = 2.22e-16 (all runs, 2024-2040) |
| EffortShare_v = Mix TM + Mix SA | pass | max |diff| = 1.11e-16 |
| History-period book bands not zero-width in 2025-2026 | pass | book-share p10-p90 width: 2024 max 0 (initial state), 2025 median 0.0018, 2026 median 0.0068, 2032 median 0.0332; 2026/2032 width ratio median 0.20 (range 0.14-0.59) |

### Band widths (p90 - p10), summary

| series | width_2025 | width_2026 | width_2032 | ratio_2026_to_2032 |
| --- | --- | --- | --- | --- |
| EffortShare | 0.0045 | 0.0135 | 0.0597 | 0.2267 |
| Mix | 0.0018 | 0.0068 | 0.0332 | 0.1997 |
| Sign | 0.0057 | 0.0185 | 0.0482 | 0.4812 |



## Settings and seeds

- Package `ai-it-labour-sim` 0.1.0, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1; matplotlib via `uv run --with` (not a project dependency).
- Platform: Windows 11 on ARM64 (Qualcomm), so no AVX-512 and `NPY_DISABLE_CPU_FEATURES` unset. This does not affect the analysis; the flag only matters for batch-scalar parity on x86 AVX-512.
- Deterministic runs: `Experiment(scenario=s)` for the baseline (`None`), `Slow AI` (g 0.05, VerifDecline 0.0), `Fast AI` (g 0.20, VerifDecline 0.10) and `Jevons rebound` (JevonsEps 0.5). Settings: `record_every=1.0`, `stop=16`, `dt=1/16`, `workers=1`, validation on. One extra baseline run uses `record_every=1/16` for D3.
- Monte Carlo: baseline with the 14 `aisim.scenarios.TORNADO` levers, each `Uniform(lo, hi)`, no correlation:
  - 1,000 runs, method `"lhs"`, `seed=20261012`;
  - `record_every=1.0`, `stop=16`, `chunk_size=500`, default workers (2 were used: one per chunk);
  - validation on, **0 invalid runs**.
- Percentiles use `aisim.experiment.results.pct` (through `bands()` and directly for hand-built series), over valid runs. Spearman uses `scipy.stats.spearmanr`. With n = 1,000, |rho| above about 0.062 differs from 0 at the 5% level.

## Caveats

- **Volume, not value.** Shares and books are contract volume (each vendor's 2024 book = 1), not USD contract value. USD value by type is a slice 8 item. An FP or OB contract whose price holds while effort falls would weigh more by value than these shares show.
- **No industry-wide mix.** The aggregation test fails (max relative residual 5.3e-3 at OIT in 2040, and 2.6e-3 within 2024-2032, against a tolerance of 1e-6). `WorkShare_v` is a vendor's share of all completed IT work, including in-house and GCCs, driven by sourcing and productivity. The book is a contract stock that signs and runs off on its own timescales. Scaling a vendor's book by its 2024 work share therefore does not track its later work share, so the books cannot be put on one scale, and the industry view is the revenue-weighted effort share only.
- **History window.** 11 of the 14 sampled levers act from 2024: all but `DemandGrowthLate`, `RegScenario` and `GCCAppealKeep` (recon 04 H). The bands are zero-width at 2024, the initial state, but not over 2025-2026. Book-share bands are a median 0.007 wide in 2026 against 0.033 in 2032 (ratio 0.20, range 0.14-0.59 across the 15 pairs); signing-share bands are 0.019 against 0.048. So the runs disagree slightly about the calibration years 2024-2026, which in reality are history.
- **The bands are conditional.** They cover only the 14 tornado ranges, sampled uniformly and independently, with all other parameters at their calibrated values. The baseline is not at the centre of these ranges: `PriceHorizon` sits at 97% of its range and `JevonsEps` at 0%. So the baseline run and the Monte Carlo median differ, by up to 4 points for BQ's FP share in 2032.
- **Scenarios are single lines.** A scenario and sampled levers cannot both set the same parameter, so the scenario comparison has no bands.
- **Lead and lag.** The turning-point lags come from one deterministic run and are not given bands. The 2032 window cuts off book turns that come later (BQ's MS book turns in 2035).
- **Not a forecast.** This is a calibrated system-dynamics model. The model shows how the mix responds to its own mechanisms (price horizon, logit type choice, contract durations) under these assumptions. It does not say what will happen.

## Model change

None. The question was answered with the public API on `main` at `20615ad`.

## Notes for slice 5

- **Hand-written chart and report code:**
  - percentile bands with a baseline overlay, history shading, direct end labels and a style legend (book and signing mix, 6 PNGs);
  - 2 x 2 scenario small multiples per vendor;
  - a multi-target drivers bar chart (Spearman per lever, shared order);
  - a signing / implied / book lead chart;
  - markdown tables of "baseline / median (p10-p90)" cells pivoted by year. `tabulate` is not installed, so the markdown writer is hand-rolled too.
- **Bands of hand-built series:** `bands()` accepts only recorded key names. The total book, the signing-minus-book gap, the signing effort share (TM + SA) and the implied mix all needed `pct()` on a masked, windowed array by hand. A `bands_of(array)` or expression support would remove this.
- **Key resolution:**
  - `keys(family=...)` takes free-text family names ("contract mix (book)").
  - The vendor and type dimensions had to be parsed from the catalogue `dims` string (`vendor=OIT;type=FP`).
  - A `keys(family, vendor=..., type=...)` filter, or a dims accessor, would help.
  - The derived `EffortShare_revenue_weighted` silently pulls `RevenueTot`, which is fine.
- **Aggregation across vendors:** the books are normalised per vendor and there is no common scale, as the failed test shows. A helper needs either USD contract value (slice 8) or a stated base-year book weight.
- **Scenarios with sampling:** these cannot be combined when they set the same parameters, and one `Experiment` holds one scenario. Four deterministic scenario runs took four `run_experiment` calls. A scenario-list helper returning one result with a scenario axis would help.
- **Workers:** with the default `chunk_size=500`, 1,000 runs use only 2 workers on a 12-core machine. The default chunking could scale with n and the number of workers.
- **`meta`:** holds the `Experiment` dataclass, which `json.dumps` cannot serialise. It was converted by hand.
- **Tables:** `Params.table()` refuses two-dimensional tables, so `Mix0` was read through `Params.baseline().tables["Mix0"]`.
- **No lead or lag helper:** the turning-point and lag code (about 60 lines) is analysis-specific, but a "first extremum after year Y" utility would be reusable.
- **Timings:**
  - Monte Carlo (1,000 runs x 88 recorded keys, 2 workers): **3.0 s** wall.
  - Full script (five deterministic runs including one fine-step run, the Monte Carlo, tables and 13 PNGs): **10.6 s** wall.
  - First invocation with `uv run --with matplotlib` (environment build and download): about 19 s.
