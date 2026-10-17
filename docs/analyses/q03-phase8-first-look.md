> **Analysis Q03, from the development of this model.** Copied verbatim below the line from the analysis's findings note.
>
> - **Question:** A first look at the phase 8 model: its headlines, uncertainty bands and scenarios, against `phase7` and `phase8_highadoption`.
> - **Ran on:** commit `207b290`, models `phase8` (the main runs), `phase7` and `phase8_highadoption`. Commit ids refer to the private development repository.
> - **Paths:** Paths under `temp/` (the analysis scripts, CSVs, charts and saved results it names) refer to the development workspace and are not in this repository.

---

# Q03 - a first look at phase 8

Reproduce from the repo root. One command writes every CSV, PNG, saved result, table, `meta.json`, `summary.json` and `report.html` in this folder, in about 36 s:

```
uv run python temp/analysis/q03-phase8-first-look/run.py
```

- **Code:** commit `207b290` on branch `main`, with a clean tree (`git_dirty` false in every result's meta).
- **Model:** no model change and no `analysis/` branch. Nothing tracked was changed and nothing was committed.
- **Report:** `report.html` takes its text sections from `report_text.md`.

## Short answers

**1. Headlines.** In Base, `phase8` shows total IT headcount slightly lower in 2040 than in 2024: 82,654 to 80,696 model units (-2.4%), against `phase7`'s 79,557 (-3.7%).
- **Against `phase7`:** `phase8` is 3.4% higher in 2030 and 1.4% higher in 2040.
- **Vendors to clients:** the mix moves from vendors to clients' own IT, much as in Phase 7. Vendor headcount falls 34% (48,597 to 32,099). In-house plus GCC headcount rises 43% (34,056 to 48,597), with GCCs nearly tripling (8,493 to 24,085).
- **By employer:** against `phase7`, `phase8` keeps more people at OIT (+21% in 2040) and GSI (+11%), and fewer at BQ (-16%) and in GCCs (-8%).
- **Revenue:** vendor revenue falls 21% in real terms (5.73 to 4.50 bn USD), against -27% in `phase7`.
- **Junior hiring:** ends at 0.50 of its 2024 level (`phase7` 0.60).
- **Unemployment:** 0.2-0.3 points higher than `phase7` (2040: India 7.1%, onshore 7.8%).
- **Adoption:** delivery AI adoption `A_mean` is 0.904 in 2030, against 0.957 in both `phase7` and `phase8_highadoption`.
- **Productivity:** realised productivity runs 3-4% below `phase7` from 2028.

**2. Contract mix.** Phase 7's rise in effort billing to about 2031 is gone.
- **The fall:** in `phase8` Base, the revenue-weighted effort-billed share (TM + SA) dips from 0.394 (2024) to about 0.381, stays flat over 2026-2029, then falls: 0.375 (2030), 0.360 (2032), 0.297 (2040). Phase 7 had 0.458, 0.464 and 0.429.
- **Everywhere:** the share is below its 2024 level in every reported year after 2024, at every vendor, in Base, Fast AI and Slow AI, and in both phase 8 models. In Slow AI it hovers at 0.376-0.391 rather than falling.
- **Shift-share:** within-vendor choice now lowers the share throughout (-4.6 points by 2032, -12.9 by 2040). Revenue moving towards BQ adds +1.0 and +3.3 points, against Phase 7's +2.0 and +5.9.
- **Prices:** the annuity T&M term shows in the new-signing prices. TM is now priced below SA (OIT 2032: TM 0.888, SA 0.914), where Phase 7 priced them equal (0.895). FP, MS and OB signings are cut less (OIT 2032: 0.719 against 0.601).

**3. Uncertainty.** The design: 1,000 LHS runs of `phase8` over the 13 tornado levers from 2026.5, seed 20261017, with 0 invalid runs.
- **The bands** are exactly zero-width before 2026.5. By 2040, p10-p90 is:
  - `HeadTotal`: 72,630-103,706 (median 86,348);
  - `RevenueTot`: 3.65-6.08 bn USD (median 4.77);
  - the revenue-weighted effort share: 0.241-0.322 (median 0.278).
- **Drivers** (Spearman):
  - headcount: demand growth after 2026 (rho +0.69 in 2032, +0.75 in 2040) and the verification decline (-0.56, -0.52);
  - revenue: sourcing cost sensitivity (-0.66 in 2032) and demand growth (+0.65; +0.61 in 2040), plus GCC appeal after 2030 in 2040 (-0.53);
  - effort share: `PriceHorizon` in 2032 (+0.65) and the verification decline in 2040 (-0.71).
- **The adoption-speed alternative:** `phase8_highadoption` falls inside the `phase8` p10-p90 band for 33 of 34 headline outputs in 2030 and in 2040. The exception is `A_mean` itself: 0.957 against a band of 0.900-0.912 in 2030. So the lever bands carry almost no adoption-speed uncertainty, but that model's outcomes lie inside the spread the other levers create.

**4. Sanity.** Nothing is broken.
- **Checks:** 35 of 35 internal checks pass, and both phase 8 models validate clean, with and without `perturb_from` 2026.5.
- **Integrity:** T1, T2 and no negative stocks hold for both models in Base, Fast AI, Slow AI and `EXTREME`. The Monte Carlo has 1,000 finite runs, no stock below -1e-12, `WorkCheckMax` at most 1.8e-15, and T2 per run over 2024-2027 at 4.0e-16.
- **Lever ranges:** no lever range excludes the model's own value. `JuniorCut` (0.761) sits at 81% of its range and `Verif` (0.544) at 93%; both ranges are centred on Phase 7.
- **Jumps at Y:** three keys exceed the jump ratio of 10 at 2026.5. Junior hires in India and onshore come from `JuniorCut` (rho -0.89 and -0.95); the revenue-weighted effort share comes from `PriceHorizon` (-0.85), at most 0.08 points. README lists both levers as immediate-effect.
- **Issues** (see "Issues found"):
  - the bands carry no adoption-speed uncertainty;
  - `PriceHorizon` sits at its fit bound of 7 in both phase 8 models;
  - the README says `phase8` adoption "saturates sooner", but it runs below `phase7` from 2026 and reaches 0.99 in 2035 rather than 2032;
  - after the temporary shocks (Compute shock, Downturn), headcount overshoots Base by up to 11%, an echo inherited from `phase7`;
  - the colour map repeats across 13 scenarios.

## A. Headlines (Question 1)

The design is nine deterministic runs: `phase7`, `phase8` and `phase8_highadoption` in Base, Fast AI and Slow AI, `record_every` 0.25.
- **D1:** these runs have no `perturb_from`, so levers act from 2024 as in Q01, Q02, the Phase 7 guide and slice 9's `09-effort-shares.csv`. Base is the same either way, and Fast and Slow AI from 2026.5 are in C.5.
- **Units:** headcounts are model units. `IndiaPeople` is persons, scaled to 5.43 million in 2024.

### Base (cell: phase7 / phase8 / phase8_highadoption, then phase8 against phase7)

| key | 2024 | 2026 | 2028 | 2030 | 2032 | 2036 | 2040 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HeadTotal | 82,654 / 82,654 / 82,654 (+0.00 %) | 84,044 / 84,031 / 84,318 (-0.01 %) | 80,646 / 82,955 / 81,985 (+2.86 %) | 79,435 / 82,111 / 80,826 (+3.37 %) | 80,163 / 82,672 / 81,916 (+3.13 %) | 79,556 / 81,016 / 81,050 (+1.83 %) | 79,557 / 80,696 / 80,915 (+1.43 %) |
| VendorHead | 48,597 / 48,597 / 48,597 (+0.00 %) | 47,807 / 47,690 / 47,979 (-0.25 %) | 44,381 / 45,350 / 45,015 (+2.18 %) | 41,404 / 42,714 / 42,101 (+3.16 %) | 37,054 / 38,882 / 38,178 (+4.93 %) | 30,321 / 32,478 / 31,761 (+7.11 %) | 29,953 / 32,099 / 31,483 (+7.16 %) |
| ConsIT | 34,056 / 34,056 / 34,056 (+0.00 %) | 36,236 / 36,341 / 36,339 (+0.29 %) | 36,265 / 37,605 / 36,970 (+3.69 %) | 38,031 / 39,397 / 38,725 (+3.59 %) | 43,108 / 43,790 / 43,738 (+1.58 %) | 49,235 / 48,538 / 49,289 (-1.42 %) | 49,603 / 48,597 / 49,432 (-2.03 %) |
| Head_IH | 25,563 / 25,563 / 25,563 (+0.00 %) | 25,788 / 25,879 / 25,865 (+0.35 %) | 24,168 / 25,278 / 24,732 (+4.59 %) | 23,644 / 24,961 / 24,289 (+5.57 %) | 23,594 / 25,049 / 24,530 (+6.17 %) | 22,497 / 23,911 / 23,490 (+6.29 %) | 23,298 / 24,512 / 24,152 (+5.21 %) |
| Head_GCC | 8,493 / 8,493 / 8,493 (+0.00 %) | 10,448 / 10,463 / 10,474 (+0.14 %) | 12,097 / 12,327 / 12,237 (+1.90 %) | 14,387 / 14,436 / 14,435 (+0.34 %) | 19,514 / 18,741 / 19,208 (-3.96 %) | 26,738 / 24,626 / 25,800 (-7.90 %) | 26,305 / 24,085 / 25,280 (-8.44 %) |
| Head_OIT | 24,913 / 24,913 / 24,913 (+0.00 %) | 24,441 / 24,376 / 24,503 (-0.26 %) | 22,312 / 22,865 / 22,698 (+2.48 %) | 19,922 / 20,941 / 20,591 (+5.11 %) | 16,769 / 18,307 / 17,898 (+9.17 %) | 11,612 / 13,656 / 13,242 (+17.61 %) | 10,364 / 12,536 / 12,192 (+20.95 %) |
| Head_GSI | 18,248 / 18,248 / 18,248 (+0.00 %) | 17,973 / 17,935 / 18,058 (-0.21 %) | 16,707 / 17,105 / 16,981 (+2.38 %) | 15,795 / 16,295 / 16,122 (+3.17 %) | 14,347 / 15,091 / 14,917 (+5.18 %) | 11,835 / 12,925 / 12,722 (+9.22 %) | 11,688 / 12,933 / 12,751 (+10.65 %) |
| Head_BQ | 5,437 / 5,437 / 5,437 (+0.00 %) | 5,393 / 5,379 / 5,419 (-0.26 %) | 5,362 / 5,380 / 5,336 (+0.35 %) | 5,687 / 5,478 / 5,388 (-3.67 %) | 5,938 / 5,484 / 5,363 (-7.64 %) | 6,874 / 5,896 / 5,796 (-14.22 %) | 7,901 / 6,630 / 6,540 (-16.08 %) |
| Q1_VendOnshore | 20,798 / 20,798 / 20,798 (+0.00 %) | 20,530 / 20,535 / 20,656 (+0.02 %) | 19,287 / 19,712 / 19,534 (+2.20 %) | 18,626 / 18,949 / 18,683 (+1.73 %) | 17,323 / 17,685 / 17,367 (+2.09 %) | 15,673 / 15,805 / 15,489 (+0.84 %) | 16,339 / 16,269 / 15,988 (-0.43 %) |
| Q1_VendIndia | 27,799 / 27,799 / 27,799 (+0.00 %) | 27,277 / 27,155 / 27,323 (-0.45 %) | 25,093 / 25,638 / 25,481 (+2.17 %) | 22,778 / 23,765 / 23,418 (+4.33 %) | 19,731 / 21,197 / 20,811 (+7.43 %) | 14,648 / 16,673 / 16,271 (+13.83 %) | 13,614 / 15,831 / 15,495 (+16.28 %) |
| OnshoreTotal | 46,361 / 46,361 / 46,361 (+0.00 %) | 46,318 / 46,413 / 46,521 (+0.21 %) | 43,455 / 44,990 / 44,267 (+3.53 %) | 42,270 / 43,910 / 42,972 (+3.88 %) | 40,917 / 42,734 / 41,897 (+4.44 %) | 38,170 / 39,716 / 38,979 (+4.05 %) | 39,637 / 40,781 / 40,140 (+2.88 %) |
| IndiaTotal | 36,292 / 36,292 / 36,292 (+0.00 %) | 37,725 / 37,618 / 37,797 (-0.28 %) | 37,191 / 37,965 / 37,718 (+2.08 %) | 37,164 / 38,201 / 37,853 (+2.79 %) | 39,246 / 39,938 / 40,019 (+1.76 %) | 41,386 / 41,300 / 42,071 (-0.21 %) | 39,919 / 39,916 / 40,775 (-0.01 %) |
| IndiaPeople | 5.43 / 5.43 / 5.43 m (+0.00 %) | 5.80 / 5.79 / 5.81 m (-0.21 %) | 5.89 / 6.01 / 5.97 m (+2.05 %) | 6.11 / 6.25 / 6.20 m (+2.23 %) | 6.87 / 6.88 / 6.94 m (+0.19 %) | 7.84 / 7.63 / 7.84 m (-2.74 %) | 7.61 / 7.40 / 7.62 m (-2.82 %) |
| HireJ_IN | 4,323 / 4,323 / 4,323 (+0.00 %) | 3,085 / 2,940 / 3,021 (-4.69 %) | 2,602 / 2,472 / 2,471 (-4.98 %) | 2,845 / 2,531 / 2,716 (-11.02 %) | 2,965 / 2,494 / 2,789 (-15.86 %) | 2,650 / 2,251 / 2,546 (-15.04 %) | 2,704 / 2,257 / 2,559 (-16.53 %) |
| HireJ_ON | 4,328 / 4,328 / 4,328 (+0.00 %) | 2,689 / 2,695 / 2,622 (+0.22 %) | 2,398 / 2,314 / 2,225 (-3.51 %) | 2,423 / 2,218 / 2,288 (-8.49 %) | 2,242 / 1,969 / 2,113 (-12.17 %) | 2,319 / 1,986 / 2,157 (-14.35 %) | 2,476 / 2,094 / 2,300 (-15.43 %) |
| JuniorHiringRatio | 1.000 / 1.000 / 1.000 (+0.00 %) | 0.667 / 0.651 / 0.652 (-2.40 %) | 0.578 / 0.553 / 0.543 (-4.27 %) | 0.609 / 0.549 / 0.578 (-9.85 %) | 0.602 / 0.516 / 0.567 (-14.28 %) | 0.574 / 0.490 / 0.544 (-14.72 %) | 0.599 / 0.503 / 0.562 (-16.01 %) |
| Unemp_IN | 0.050 / 0.050 / 0.050 (+0.00 pts) | 0.055 / 0.059 / 0.056 (+0.45 pts) | 0.071 / 0.071 / 0.074 (-0.04 pts) | 0.064 / 0.066 / 0.065 (+0.28 pts) | 0.057 / 0.062 / 0.058 (+0.48 pts) | 0.068 / 0.069 / 0.068 (+0.11 pts) | 0.068 / 0.071 / 0.070 (+0.23 pts) |
| Unemp_ON | 0.055 / 0.055 / 0.055 (+0.00 pts) | 0.070 / 0.070 / 0.070 (+0.00 pts) | 0.080 / 0.079 / 0.084 (-0.10 pts) | 0.073 / 0.077 / 0.076 (+0.34 pts) | 0.077 / 0.080 / 0.078 (+0.32 pts) | 0.074 / 0.076 / 0.075 (+0.20 pts) | 0.076 / 0.078 / 0.077 (+0.22 pts) |
| A_mean | 0.350 / 0.350 / 0.350 (+0.00 pts) | 0.630 / 0.622 / 0.630 (-0.81 pts) | 0.853 / 0.800 / 0.853 (-5.21 pts) | 0.957 / 0.904 / 0.957 (-5.25 pts) | 0.990 / 0.959 / 0.991 (-3.13 pts) | 1.000 / 0.993 / 1.000 (-0.62 pts) | 1.000 / 0.999 / 1.000 (-0.12 pts) |
| P_all | 1.000 / 1.000 / 1.000 (+0.00 %) | 1.061 / 1.046 / 1.050 (-1.46 %) | 1.140 / 1.103 / 1.117 (-3.26 %) | 1.211 / 1.162 / 1.181 (-4.00 %) | 1.271 / 1.221 / 1.237 (-3.94 %) | 1.374 / 1.327 / 1.338 (-3.42 %) | 1.466 / 1.422 / 1.431 (-2.99 %) |
| P_OIT | 1.000 / 1.000 / 1.000 (+0.00 %) | 1.059 / 1.045 / 1.048 (-1.33 %) | 1.139 / 1.103 / 1.116 (-3.12 %) | 1.211 / 1.164 / 1.181 (-3.94 %) | 1.272 / 1.223 / 1.238 (-3.86 %) | 1.376 / 1.329 / 1.339 (-3.35 %) | 1.467 / 1.424 / 1.432 (-2.98 %) |
| P_GSI | 1.000 / 1.000 / 1.000 (+0.00 %) | 1.062 / 1.048 / 1.050 (-1.25 %) | 1.141 / 1.107 / 1.118 (-2.93 %) | 1.211 / 1.167 / 1.181 (-3.67 %) | 1.271 / 1.224 / 1.237 (-3.69 %) | 1.374 / 1.328 / 1.338 (-3.32 %) | 1.465 / 1.421 / 1.430 (-2.96 %) |
| P_BQ | 1.000 / 1.000 / 1.000 (+0.00 %) | 1.056 / 1.046 / 1.045 (-0.91 %) | 1.129 / 1.103 / 1.109 (-2.34 %) | 1.200 / 1.161 / 1.173 (-3.29 %) | 1.265 / 1.219 / 1.233 (-3.61 %) | 1.373 / 1.326 / 1.337 (-3.40 %) | 1.464 / 1.421 / 1.430 (-2.99 %) |
| RevenueTot | 5.729 / 5.729 / 5.729 bn (+0.00 %) | 5.810 / 5.819 / 5.838 bn (+0.15 %) | 5.516 / 5.689 / 5.642 bn (+3.12 %) | 5.216 / 5.461 / 5.374 bn (+4.68 %) | 4.663 / 4.996 / 4.850 bn (+7.16 %) | 4.000 / 4.321 / 4.195 bn (+8.04 %) | 4.165 / 4.502 / 4.386 bn (+8.09 %) |
| Revenue_OIT | 2.012 / 2.012 / 2.012 bn (+0.00 %) | 2.024 / 2.021 / 2.029 bn (-0.16 %) | 1.865 / 1.928 / 1.918 bn (+3.33 %) | 1.634 / 1.764 / 1.735 bn (+7.98 %) | 1.310 / 1.514 / 1.468 bn (+15.58 %) | 0.856 / 1.087 / 1.041 bn (+27.00 %) | 0.773 / 1.024 / 0.987 bn (+32.53 %) |
| Revenue_GSI | 2.435 / 2.435 / 2.435 bn (+0.00 %) | 2.497 / 2.504 / 2.513 bn (+0.30 %) | 2.351 / 2.444 / 2.424 bn (+3.95 %) | 2.198 / 2.342 / 2.312 bn (+6.57 %) | 1.918 / 2.133 / 2.079 bn (+11.16 %) | 1.495 / 1.786 / 1.734 bn (+19.53 %) | 1.500 / 1.840 / 1.795 bn (+22.61 %) |
| Revenue_BQ | 1.282 / 1.282 / 1.282 bn (+0.00 %) | 1.289 / 1.294 / 1.297 bn (+0.36 %) | 1.300 / 1.317 / 1.300 bn (+1.33 %) | 1.385 / 1.354 / 1.327 bn (-2.22 %) | 1.434 / 1.350 / 1.302 bn (-5.88 %) | 1.650 / 1.448 / 1.420 bn (-12.22 %) | 1.892 / 1.638 / 1.604 bn (-13.41 %) |

`Q1_ConsOnshore` equals `Head_IH` and `Q1_ConsIndia` equals `Head_GCC` (catalogue definitions). `P_IH` and `P_GCC` track `P_all` within 0.5%. All are in `headlines_base_compact.csv`.

### Fast AI and Slow AI, 2030 and 2040 (phase8 against phase7)

| scenario | key | 2030 phase7 / phase8 (diff) | 2040 phase7 / phase8 (diff) |
| --- | --- | --- | --- |
| Fast AI | HeadTotal | 68,756 / 71,364 (+3.8%) | 64,241 / 64,039 (-0.3%) |
| Fast AI | RevenueTot (bn) | 4.59 / 4.85 (+5.6%) | 3.53 / 3.81 (+8.0%) |
| Fast AI | JuniorHiringRatio | 0.489 / 0.456 (-6.7%) | 0.492 / 0.402 (-18.2%) |
| Fast AI | Unemp_ON | 0.069 / 0.073 (+0.43 pts) | 0.078 / 0.081 (+0.28 pts) |
| Slow AI | HeadTotal | 88,053 / 91,296 (+3.7%) | 104,718 / 108,324 (+3.4%) |
| Slow AI | RevenueTot (bn) | 5.67 / 5.95 (+4.8%) | 5.13 / 5.62 (+9.6%) |
| Slow AI | JuniorHiringRatio | 0.703 / 0.627 (-10.8%) | 0.831 / 0.719 (-13.4%) |
| Slow AI | Unemp_ON | 0.070 / 0.073 (+0.23 pts) | 0.069 / 0.071 (+0.18 pts) |

Full grid: `headlines_wide.csv` (every key, scenario and year, with both phase 8 models against `phase7`) and `headlines_scenarios_2030_2040.csv`.

**What it shows:**
- The phase 8 recalibration lifts 2028-2036 headcount and revenue by 2-8%, as slice 9's attribution found (+3.4% and +4.7% in 2030).
- It does not change the direction of any headline.
- Lower junior hiring (`JuniorCut` 0.761 against 0.583) and slower adoption are the clearest model differences.

Charts: `headlines_HeadTotal.png`, `headlines_RevenueTot.png`.

## B. Contract mix (Question 2)

### Effort-billed share (TM + SA), deterministic runs

| model | scenario | series | 2024 | 2026 | 2030 | 2032 | 2036 | 2040 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase7 | Base | OIT | 0.400 | 0.395 | 0.420 | 0.394 | 0.328 | 0.314 |
| phase7 | Base | GSI | 0.270 | 0.268 | 0.322 | 0.308 | 0.248 | 0.221 |
| phase7 | Base | BQ | 0.620 | 0.622 | 0.719 | 0.735 | 0.705 | 0.641 |
| phase7 | Base | revenue-weighted | 0.394 | 0.391 | 0.458 | 0.464 | 0.454 | 0.429 |
| phase8 | Base | OIT | 0.400 | 0.387 | 0.364 | 0.335 | 0.291 | 0.258 |
| phase8 | Base | GSI | 0.270 | 0.259 | 0.246 | 0.226 | 0.189 | 0.159 |
| phase8 | Base | BQ | 0.620 | 0.610 | 0.615 | 0.600 | 0.547 | 0.476 |
| phase8 | Base | revenue-weighted | 0.394 | 0.381 | 0.375 | 0.360 | 0.334 | 0.297 |
| phase8 | Fast AI | revenue-weighted | 0.394 | 0.375 | 0.355 | 0.330 | 0.280 | 0.239 |
| phase8 | Slow AI | revenue-weighted | 0.394 | 0.385 | 0.391 | 0.382 | 0.386 | 0.376 |
| phase8_highadoption | Base | OIT | 0.400 | 0.386 | 0.358 | 0.327 | 0.279 | 0.250 |
| phase8_highadoption | Base | GSI | 0.270 | 0.258 | 0.243 | 0.222 | 0.181 | 0.153 |
| phase8_highadoption | Base | BQ | 0.620 | 0.610 | 0.612 | 0.597 | 0.535 | 0.464 |
| phase8_highadoption | Base | revenue-weighted | 0.394 | 0.381 | 0.371 | 0.354 | 0.325 | 0.289 |
| phase8_highadoption | Fast AI | revenue-weighted | 0.394 | 0.375 | 0.350 | 0.325 | 0.271 | 0.233 |
| phase8_highadoption | Slow AI | revenue-weighted | 0.394 | 0.385 | 0.387 | 0.377 | 0.377 | 0.367 |

Every vendor in every scenario is in `effort_shares.csv`. The `phase7` rows are Q01's and Q02's (B.3 below). Charts: `effort_OIT.png`, `effort_GSI.png`, `effort_BQ.png`, `effort_rw.png`.

### Book mix by type, Base

| model | vendor | year | FP | TM | MS | SA | OB | TM+SA |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| phase7 | OIT | 2032 | 0.312 | 0.282 | 0.265 | 0.113 | 0.029 | 0.394 |
| phase8 | OIT | 2032 | 0.361 | 0.225 | 0.273 | 0.109 | 0.032 | 0.335 |
| phase8_highadoption | OIT | 2032 | 0.363 | 0.222 | 0.278 | 0.105 | 0.033 | 0.327 |
| phase7 | OIT | 2040 | 0.377 | 0.207 | 0.275 | 0.107 | 0.033 | 0.314 |
| phase8 | OIT | 2040 | 0.417 | 0.158 | 0.288 | 0.100 | 0.036 | 0.258 |
| phase8_highadoption | OIT | 2040 | 0.422 | 0.156 | 0.291 | 0.094 | 0.037 | 0.250 |
| phase7 | GSI | 2032 | 0.328 | 0.241 | 0.318 | 0.067 | 0.045 | 0.308 |
| phase8 | GSI | 2032 | 0.384 | 0.168 | 0.339 | 0.058 | 0.052 | 0.226 |
| phase8_highadoption | GSI | 2032 | 0.385 | 0.166 | 0.342 | 0.056 | 0.052 | 0.222 |
| phase7 | GSI | 2040 | 0.397 | 0.164 | 0.330 | 0.057 | 0.053 | 0.221 |
| phase8 | GSI | 2040 | 0.436 | 0.112 | 0.347 | 0.048 | 0.057 | 0.159 |
| phase8_highadoption | GSI | 2040 | 0.439 | 0.109 | 0.350 | 0.045 | 0.057 | 0.153 |
| phase7 | BQ | 2032 | 0.205 | 0.494 | 0.039 | 0.241 | 0.021 | 0.735 |
| phase8 | BQ | 2032 | 0.315 | 0.371 | 0.053 | 0.229 | 0.031 | 0.600 |
| phase8_highadoption | BQ | 2032 | 0.318 | 0.372 | 0.054 | 0.225 | 0.031 | 0.597 |
| phase7 | BQ | 2040 | 0.289 | 0.413 | 0.042 | 0.228 | 0.028 | 0.641 |
| phase8 | BQ | 2040 | 0.422 | 0.273 | 0.061 | 0.203 | 0.041 | 0.476 |
| phase8_highadoption | BQ | 2040 | 0.432 | 0.272 | 0.062 | 0.192 | 0.041 | 0.464 |

The 2024 mix is the same in every model (OIT 0.35/0.30/0.22/0.10/0.03, GSI 0.38/0.22/0.30/0.05/0.05, BQ 0.30/0.45/0.05/0.17/0.03). Every year, scenario and model is in `book_mix.csv`.

In `phase8`, TM is the type that loses share: OIT's TM falls from 0.300 to 0.158 by 2040. FP gains most (0.350 to 0.417), and SA barely moves (0.100 to 0.100).

### B.2 Within, between and interaction (Q02's identity)

E(t) = sum_v w_v(t) e_v(t), with w_v = `Revenue_v / RevenueTot` and e_v = `EffortShare_v`. The split is from `aisim.experiment.shift_share`. The checks over the 9 runs all pass:
- within + between + interaction = E(t) - E(2024), at most 1.3e-16;
- `total` = E(t) - E(2024), at most 1.1e-16;
- sum w = 1, at most 2.2e-16;
- sum w e = the derived `EffortShare_revenue_weighted`, at most 1.1e-16.

| model | scenario | window | change | within | between | interaction |
| --- | --- | --- | --- | --- | --- | --- |
| phase7 | Base | 2024-2032 | +0.0697 | +0.0400 | +0.0202 | +0.0095 |
| phase7 | Base | 2024-2040 | +0.0350 | -0.0463 | +0.0591 | +0.0222 |
| phase8 | Base | 2024-2032 | -0.0341 | -0.0462 | +0.0100 | +0.0022 |
| phase8 | Base | 2024-2040 | -0.0969 | -0.1290 | +0.0329 | -0.0009 |
| phase8 | Fast AI | 2024-2032 | -0.0643 | -0.0833 | +0.0154 | +0.0036 |
| phase8 | Fast AI | 2024-2040 | -0.1552 | -0.1930 | +0.0460 | -0.0082 |
| phase8 | Slow AI | 2024-2032 | -0.0115 | -0.0197 | +0.0069 | +0.0013 |
| phase8 | Slow AI | 2024-2040 | -0.0183 | -0.0381 | +0.0191 | +0.0007 |
| phase8_highadoption | Base | 2024-2032 | -0.0398 | -0.0515 | +0.0093 | +0.0023 |
| phase8_highadoption | Base | 2024-2040 | -0.1052 | -0.1371 | +0.0332 | -0.0013 |
| phase8_highadoption | Fast AI | 2024-2032 | -0.0694 | -0.0887 | +0.0154 | +0.0039 |
| phase8_highadoption | Fast AI | 2024-2040 | -0.1613 | -0.1986 | +0.0465 | -0.0093 |
| phase8_highadoption | Slow AI | 2024-2032 | -0.0171 | -0.0249 | +0.0064 | +0.0014 |
| phase8_highadoption | Slow AI | 2024-2040 | -0.0273 | -0.0472 | +0.0193 | +0.0007 |

Every year and the `phase7` Fast and Slow AI rows are in `shift_share.csv`.

**Across the Monte Carlo** (C.1 design, 1,000 runs from 2026.5; `shift_share_mc.csv`):

| component | 2032 median (p10-p90) | 2040 median (p10-p90) |
| --- | --- | --- |
| within | -0.0645 (-0.0893 to -0.0426) | -0.1456 (-0.1808 to -0.1031) |
| between | +0.0092 (-0.0026 to +0.0255) | +0.0315 (+0.0101 to +0.0575) |
| interaction | +0.0014 | -0.0020 |
| total | -0.0544 (-0.0841 to -0.0205) | -0.1160 (-0.1534 to -0.0720) |

- **Within** is negative in every run at both years.
- **The total** is negative in 98.6% of runs at 2032 and in every run at 2040.
- **Not comparable with Q02's Monte Carlo:** that design had 14 levers acting from 2024.

Charts: `shift_share_phase8.png` (deterministic Base, as lines; D5) and `shift_share_mc.png`.

### B.3 Phase 7 cross-check

The live `phase7` Base reproduces Q02 to 4 decimals:
- 2032: within 0.0400, between 0.0202, interaction 0.0095, E 0.4637;
- 2040: within -0.0463, between 0.0591, interaction 0.0222, E 0.4290.

It also reproduces Q01's 2032 revenue-weighted share of 0.464 (`checks.csv`).

### B.4 New-signing prices (`PNew_<v>_<k>`, index 2024 = 1, Base)

| model | vendor | year | FP | TM | SA |
| --- | --- | --- | --- | --- | --- |
| phase7 | OIT | 2030 | 0.666 | 0.940 | 0.940 |
| phase8 | OIT | 2030 | 0.783 | 0.928 | 0.949 |
| phase8_highadoption | OIT | 2030 | 0.766 | 0.924 | 0.947 |
| phase7 | OIT | 2040 | 0.573 | 0.930 | 0.930 |
| phase8 | OIT | 2040 | 0.672 | 0.903 | 0.939 |
| phase8_highadoption | OIT | 2040 | 0.669 | 0.901 | 0.937 |
| phase7 | GSI | 2030 | 0.688 | 0.971 | 0.971 |
| phase8 | GSI | 2030 | 0.799 | 0.950 | 0.971 |
| phase7 | GSI | 2040 | 0.602 | 0.974 | 0.974 |
| phase8 | GSI | 2040 | 0.703 | 0.943 | 0.979 |
| phase7 | BQ | 2030 | 0.720 | 1.000 | 1.000 |
| phase8 | BQ | 2030 | 0.828 | 0.978 | 0.999 |
| phase7 | BQ | 2040 | 0.616 | 1.000 | 1.000 |
| phase8 | BQ | 2040 | 0.697 | 0.936 | 0.972 |

MS and OB move with FP (they share the anchor). Every vendor, type, year and scenario is in `pnew.csv`.

**The annuity term at work.**
- **Phase 7:** TM and SA always have the same new price, the effort discount only.
- **Phase 8:** 30% of new TM work carries `Anchor ** 0.4`, so TM falls below SA by 2.1 points (OIT 2030) to 3.6 points (BQ 2040).
- **The anchor itself:** with `PassThrough` 0.75 and `PriceHorizon` 7 instead of 1 and 7.877, it cuts FP, MS and OB prices less (OIT FP 0.783 against 0.666 in 2030).

**How the story changes.** Under Phase 7, Q01 and Q02 found effort billing rising to about 2031. The cause was on the vendor side: the client price anchor cut only non-effort prices, so vendors tilted towards TM and SA. Under `phase8` that rise is gone.
- **Prices:** part of TM now carries the anchor, and the anchor itself is weaker, so vendors gain less by moving work to effort billing. Meanwhile clients' distrust of effort billing keeps growing (Q02's client term).
- **The share:** the revenue-weighted effort share stays below its 2024 level in every scenario and model. In Base it goes from 0.394 to 0.297 by 2040, flat over 2026-2029 and falling after; in Slow AI it hovers at 0.38-0.39.
- **Shift-share:** the fall is within-vendor choice (-12.9 points), partly offset by revenue moving to BQ (+3.3 points, against +5.9 in Phase 7). Every vendor ends below its 2024 share, BQ included (0.476 against 0.620), and the mix moves towards fixed price and managed services.
- **The record:** this is the direction Phases 5-6b reported, and what slice 9's cores 1 and 2 were built to check (OIT -3.64 points and BQ -0.50 by 2030).

## C. Uncertainty (Question 3)

### C.1 The Monte Carlo

- **Design:** `phase8`, `perturb_from=2026.5`, `tornado_levers(perturb_from=2026.5, model="phase8")` (13 levers, each `Uniform(lo, hi)`; `Verif` dropped as a 2024 level), LHS, N = 1,000, seed 20261017, Base.
- **Run:** auto chunking (125 runs per chunk, 8 workers).
- **Result:** **0 invalid runs.** No vendor collapses in any run (`q3_counts.csv`: OIT 364 equilibrium / 636 adjusting, GSI 489 / 511, BQ 246 / 754).

| key | 2026 | 2028 | 2030 | 2032 | 2040 |
| --- | --- | --- | --- | --- | --- |
| HeadTotal | 84,031 (zero width) | 84,190 (82,807-85,517) | 83,916 (80,170-87,797) | 85,167 (79,118-92,025) | 86,348 (72,630-103,706) |
| RevenueTot (bn USD) | 5.819 (zero width) | 5.734 (5.666-5.800) | 5.534 (5.231-5.856) | 5.131 (4.664-5.656) | 4.774 (3.649-6.078) |
| EffortShare_revenue_weighted | 0.381 (zero width) | 0.375 (0.365-0.385) | 0.360 (0.337-0.385) | 0.340 (0.310-0.373) | 0.278 (0.241-0.322) |

Cells are median (p10-p90).

2030 and 2040 for the other headline keys:

| key | 2030 median (p10-p90) | 2040 median (p10-p90) |
| --- | --- | --- |
| VendorHead | 43,654 (41,549-45,871) | 34,347 (27,123-42,849) |
| ConsIT | 40,216 (38,472-42,118) | 52,018 (41,954-64,050) |
| Head_GCC | 14,790 (14,036-15,627) | 25,811 (18,703-35,388) |
| IndiaPeople (m) | 6.39 (6.08-6.71) | 8.00 (6.28-10.28) |
| HireJ_IN | 3,024 (2,371-3,864) | 2,937 (2,061-4,194) |
| HireJ_ON | 2,711 (2,075-3,347) | 2,652 (1,889-3,625) |
| Unemp_IN | 0.062 (0.052-0.070) | 0.066 (0.059-0.075) |
| Unemp_ON | 0.072 (0.063-0.080) | 0.074 (0.068-0.082) |
| A_mean | 0.906 (0.900-0.912) | 0.999 (0.9985-0.9990) |
| P_all | 1.163 (1.128-1.201) | 1.416 (1.239-1.572) |
| EffortShare_OIT | 0.350 (0.333-0.366) | 0.244 (0.206-0.289) |
| EffortShare_GSI | 0.233 (0.216-0.249) | 0.148 (0.124-0.180) |
| EffortShare_BQ | 0.594 (0.563-0.626) | 0.448 (0.393-0.503) |

Every key at 2026, 2028, 2030, 2032 and 2040 is in `mc_bands.csv`. Charts: `mc_HeadTotal.png`, `mc_RevenueTot.png`, `mc_EffortShare_rw.png`. The dashed line is `phase8_highadoption`; the legend labels it "baseline run", the label `charts.bands` gives its `baseline=` line.

**The deterministic `phase8` Base is not the centre of the bands.**
- **Headcounts** are at the 16th-37th percentile: `HeadTotal` at the 29th in 2030 and 32nd in 2040.
- **Effort shares** are at the 66th-85th percentile.

The reasons, from `lever_ranges.csv`: `JevonsEps` is 0 at the bottom of its 0-0.5 range (rho +0.14 to +0.15 on headcount), and `PriceHorizon` 7.0 sits at 75% of 4-8.

### C.2 Zero width before Y

- **Annual rows:** for every one of the 38 recorded series, max - min over runs (stricter than p90 - p10) is exactly 0 at 2024, 2025 and 2026.
- **Every step:** in the continuity run, recorded every dt, it is exactly 0 at every one of the 40 steps before 2026.5 in all 40 series.
- **The row at Y:** at 2026.5 itself, which is phase 2's row, only three flows differ across runs: `HireJ_IN`, `HireJ_ON` and `Ext_total`, all through `JuniorCut`.

### C.3 Drivers (Spearman rho; `drivers_2032.csv`, `drivers_2040.csv`, `drivers_top5.csv`)

| target | year | #1 | #2 | #3 | #4 | #5 |
| --- | --- | --- | --- | --- | --- | --- |
| HeadTotal | 2032 | DemandGrowthLate (+0.694) | VerifDecline (-0.555) | g (-0.285) | JuniorCut (-0.174) | JevonsEps (+0.143) |
| RevenueTot | 2032 | SrcCostSens (-0.655) | DemandGrowthLate (+0.651) | VerifDecline (-0.341) | g (-0.176) | JevonsEps (+0.152) |
| EffortShare_revenue_weighted | 2032 | PriceHorizon (+0.646) | SrcCostSens (-0.594) | VerifDecline (-0.303) | JuniorCut (+0.239) | DemandGrowthLate (+0.110) |
| HeadTotal | 2040 | DemandGrowthLate (+0.754) | VerifDecline (-0.524) | g (-0.206) | JevonsEps (+0.150) | aL_max (-0.132) |
| RevenueTot | 2040 | DemandGrowthLate (+0.605) | GCCAppealKeep (-0.526) | SrcCostSens (-0.479) | VerifDecline (-0.276) | JevonsEps (+0.149) |
| EffortShare_revenue_weighted | 2040 | VerifDecline (-0.710) | SrcCostSens (-0.480) | PriceHorizon (+0.338) | JuniorCut (+0.211) | g (-0.209) |

- **No single lever dominates.** In Q01's Phase 7 Monte Carlo, `PriceHorizon` dominated the mix (rho +0.77 in 2032). Here it shares the lead with sourcing cost sensitivity in 2032 and gives way to the verification decline by 2040.
- **Weak levers:** `TMBrake`, `EnrolSensitivity`, `AICostDecline` and `RegScenario` have |rho| below 0.1 on all three targets in both years.
- **Significance:** with n = 1,000, |rho| above about 0.062 differs from 0 at the 5% level.

Charts: `drivers_2032.png`, `drivers_2040.png`.

### C.4 The adoption-speed model against the spread (`adoption_vs_band.csv`)

- **The run:** `phase8_highadoption` in Base with `perturb_from=2026.5`.
- **Check:** it equals the plain `phase8_highadoption` Base run bit for bit. Phase 1 runs that model's own baseline, so the run is the model's whole path.
- **Before Y:** it already differs from `phase8` before 2026.5. In 2026, `A_mean` is 0.630 against 0.622, and the three core keys differ by up to 0.34%. The models differ in calibration from 2024, not only after Y.

| key | 2030 value (rank) | 2030 p10-p90 | where | 2040 value (rank) | 2040 p10-p90 | where |
| --- | --- | --- | --- | --- | --- | --- |
| HeadTotal | 80,826 (16%) | 80,170-87,797 | inside | 80,915 (32%) | 72,630-103,706 | inside |
| RevenueTot (bn) | 5.374 (28%) | 5.231-5.856 | inside | 4.386 (34%) | 3.649-6.078 | inside |
| EffortShare_revenue_weighted | 0.371 (71%) | 0.337-0.385 | inside | 0.289 (61%) | 0.241-0.322 | inside |
| VendorHead | 42,101 (19%) | 41,549-45,871 | inside | 31,483 (33%) | 27,123-42,849 | inside |
| ConsIT | 38,725 (13%) | 38,472-42,118 | inside | 49,432 (38%) | 41,954-64,050 | inside |
| Unemp_ON | 0.076 (75%) | 0.063-0.080 | inside | 0.077 (69%) | 0.068-0.082 | inside |
| A_mean | 0.957 (100%) | 0.900-0.912 | **above p90** | 1.000 (100%) | 0.9985-0.9990 | **above p90** |

Rank is the share of Monte Carlo runs below the value. Across all 34 headline keys, 33 are inside p10-p90 in both years, and only `A_mean` is outside.

**Reading:**
- The adoption-speed alternative moves the outcomes by less than the other levers' spread: it sits in the lower-middle of the headcount bands and the upper-middle of the effort-share band.
- It also sits outside the adoption band, because none of the 13 levers moves adoption much: the 2030 `A_mean` band is 1.3 points wide.
- So the bands do not represent adoption-speed uncertainty, and the comparison between models is the only route to it (README "Models"). See issue 1.

### C.5 Scenarios on `phase8` from 2026.5

- **Run:** `run_scenarios(<C.1 experiment>, [None, ...])` on the same 1,000 draws. The Baseline block equals the C.1 Monte Carlo bit for bit (`checks.csv`).
- **Validates (12 named scenarios plus Baseline):** Slow AI, Fast AI, Strict regulation, Light regulation, Compute shock, Visa relaxation, Downturn, Jevons rebound, Demand stalls, Demand boom, GCC wave persists, GCC wave fades. "Base" was not run separately because it equals `None`.
- **Does not validate:** Visa crackdown, rule `window`. Its visa tightness ramp (`VTRampStart` 2025.7 to 2027.7) "starts at 2025.7, before perturb_from = 2026.5, and changes the run before it". Evidence `workforce.py:79` (`scenarios_invalid.csv`).
- **Pinned levers** (`ScenarioResult.pinned`): each named lever is set to the scenario's value in that block, with the other levers as drawn.
  - Slow AI and Fast AI: `g`, `VerifDecline`;
  - Strict and Light regulation: `RegScenario`;
  - Jevons rebound: `JevonsEps`;
  - Demand stalls and Demand boom: `DemandGrowthLate`;
  - both GCC waves: `GCCAppealKeep`.

2040, median (p10-p90); 0 invalid runs in every block:

| scenario | pinned | HeadTotal | RevenueTot (bn) | EffortShare_revenue_weighted |
| --- | --- | --- | --- | --- |
| Baseline | none | 86,348 (72,630-103,706) | 4.77 (3.65-6.08) | 0.278 (0.241-0.322) |
| Slow AI | VerifDecline, g | 106,827 (92,592-123,968) | 5.61 (4.31-7.05) | 0.338 (0.313-0.367) |
| Fast AI | VerifDecline, g | 70,812 (60,955-83,380) | 4.12 (3.25-5.17) | 0.229 (0.207-0.256) |
| Strict regulation | RegScenario | 87,737 (73,861-105,345) | 4.85 (3.71-6.13) | 0.280 (0.242-0.324) |
| Light regulation | RegScenario | 85,181 (71,424-102,361) | 4.73 (3.61-5.99) | 0.276 (0.238-0.319) |
| Compute shock | none | 87,881 (73,112-105,940) | 4.79 (3.67-6.13) | 0.282 (0.244-0.327) |
| Visa relaxation | none | 86,295 (72,539-103,544) | 4.78 (3.65-6.10) | 0.278 (0.241-0.322) |
| Downturn | none | 86,619 (72,564-104,551) | 4.78 (3.65-6.09) | 0.279 (0.242-0.323) |
| Jevons rebound | JevonsEps | 90,865 (76,380-108,148) | 5.01 (3.90-6.29) | 0.277 (0.240-0.322) |
| Demand stalls | DemandGrowthLate | 59,076 (52,819-67,460) | 3.28 (2.65-3.91) | 0.276 (0.238-0.320) |
| Demand boom | DemandGrowthLate | 110,023 (98,459-125,662) | 6.13 (5.00-7.29) | 0.279 (0.242-0.324) |
| GCC wave persists | GCCAppealKeep | 86,947 (73,154-104,671) | 3.84 (3.11-4.85) | 0.274 (0.236-0.318) |
| GCC wave fades | GCCAppealKeep | 85,967 (72,155-103,393) | 5.48 (4.52-6.69) | 0.279 (0.242-0.324) |

The 2030 values and five more keys are in `scenarios_bands.csv`.

**What moves the 2040 outcomes:**
- **Headcount:** demand (59k to 110k) and AI speed (71k to 107k) move it most.
- **Revenue:** the GCC wave moves vendor revenue most (3.84 against 5.48 bn).
- **Effort share:** only the AI speed moves it (0.229 to 0.338); every other scenario stays within 0.005 of Baseline.

Chart: `scenarios_HeadTotal.png`, small multiples (D7).

## D. Sanity checks (Question 4)

### D.1 Lever ranges against the model (`lever_ranges.csv`, `fit_bounds.csv`)

| lever | range | phase7 | phase8 | phase8_highadoption | position (phase8) | sampled at 2026.5 |
| --- | --- | --- | --- | --- | --- | --- |
| g | 0.06-0.15 | 0.10 | 0.10 | 0.10 | 44% | yes |
| DemandGrowthLate | 0.015-0.045 | 0.03 (None = DemandGrowth) | 0.03 | 0.03 | 50% | yes |
| Verif | 0.303-0.562 (x0.7 / x1.3 of phase7) | 0.432 | 0.544 | 0.521 | **93%** | no (2024 level) |
| VerifDecline | 0-0.1 | 0.05 | 0.05 | 0.05 | 50% | yes |
| JevonsEps | 0-0.5 | 0 | 0 | 0 | **0%** | yes |
| GCCAppealKeep | 0-1 | 0.5 | 0.5 | 0.5 | 50% | yes |
| JuniorCut | 0.292-0.875 (x0.5 / x1.5 of phase7) | 0.583 | 0.761 | 0.663 | **81%** | yes |
| TMBrake | 0.2-0.6 | 0.4 | 0.4 | 0.4 | 50% | yes |
| PriceHorizon | 4-8 | 7.877 | 7.000 | 7.000 | 75% | yes |
| aL_max | 0.25-0.45 | 0.35 | 0.35 | 0.35 | 50% | yes |
| SrcCostSens | 2-4 | 3 | 3 | 3 | 50% | yes |
| AICostDecline | 0.08-0.25 | 0.15 | 0.15 | 0.15 | 41% | yes |
| RegScenario | 0.5-1.5 | 1 | 1 | 1 | 50% | yes |
| EnrolSensitivity | 0.5-1.5 | 1 | 1 | 1 | 50% | yes |

- **Containment:** every range contains `phase8`'s value, so no range misses.
- **Recon's flag:** recon flagged `JuniorCut`. Its range (built from Phase 7's 0.583) does contain 0.761, but at 81%: about 80% of the sampled runs have a lower junior cut than the model.
- **`Verif`:** at 93%, but it is not sampled under `perturb_from`.
- **`JevonsEps`** is at the bottom of its range in every model, as in Q01.
- **At the fit bound:** `PriceHorizon` is fitted at 6.99999954 in `phase8` and 6.99999999999 in `phase8_highadoption`, against a bound of [0, 7]. That is within 1e-7 of the bound in both. No other fitted parameter is within 0.1% of its bound.

### D.2 Validation and integrity (`validation.csv`, `integrity.csv`)

| check | phase8 | phase8_highadoption |
| --- | --- | --- |
| `validate`, no `perturb_from` | clean | clean |
| `validate`, `perturb_from` 2026.5 | clean | clean |
| T1 (AI off), max abs(HeadTotal / H2024 / G - 1), limit 0.012 | 0.00995 | 0.01088 |
| T2 relative residual, Base / Fast AI / Slow AI / `EXTREME` (limit 1e-9) | 2.4e-16 / 1.3e-15 / 2.0e-16 / 1.6e-16 | 3.6e-16 / 1.0e-15 / 3.1e-16 / 4.7e-16 |
| lowest stock, the same four cases (at least -1e-12) | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 |

T1 and T2 reproduce slice 9's STOP-check values (0.00995 and 0.01088; 2.4e-16 and 3.6e-16).

**The Monte Carlo (1,000 runs):**
- 1,000 finite runs;
- 0 runs with a stock below -1e-12 (lowest stock 0);
- `WorkCheckMax` at most 1.8e-15;
- T2 per run over 2024-2027 (phase 1 and the restart, from the every-dt run) at most 4.0e-16.

### D.3 Continuity at Y (slice 6's B5 ratio; `continuity.csv`)

- **Method:** the ratio is abs(run at Y + dt - base at Y) / max(median abs(base step) over the 8 steps before Y, 1e-6 abs(base at Y)), per run and key.
- **Data:** a rerun of the C.1 design recorded every dt to 2027. Its annual rows equal the main Monte Carlo's bit for bit.
- **Flag:** above 10.

| key | max ratio | median ratio | runs above 10 | largest jump | levers behind it (Spearman of ratio with lever) |
| --- | --- | --- | --- | --- | --- |
| **HireJ_ON** | **111.5** | 67.1 | 962 | 1,701 per year | JuniorCut -0.95 |
| **HireJ_IN** | **73.5** | 42.5 | 954 | 1,568 per year | JuniorCut -0.89 |
| **EffortShare_revenue_weighted** | **18.7** | 6.0 | 323 | 0.0008 | PriceHorizon -0.85 |
| Revenue_BQ | 9.1 | 5.1 | 0 | 1.24e6 USD per year | VerifDecline +0.58, PriceHorizon -0.44, JuniorCut -0.34 |
| EffortShare_GSI | 7.1 | 2.8 | 0 | 0.0008 | PriceHorizon -0.97 |
| EffortShare_OIT | 6.7 | 2.8 | 0 | 0.0008 | PriceHorizon -0.98 |
| EffortShare_BQ | 6.3 | 2.5 | 0 | 0.0009 | PriceHorizon -0.50 |
| Revenue_GSI | 4.2 | 1.2 | 0 | 3.1e6 USD per year | VerifDecline -0.52 |

All headcount stocks stay at or below 1.23, which is the base path's own step.

**The three flagged keys come from levers README lists as immediate-effect** ("Perturb from year Y": `SrcCostSens`, `JuniorCut`, `PriceHorizon`, `JevonsEps`). Slice 6 pinned them as expected jumps (`EXPECTED_JUMPS`).
- **`JuniorCut`:** it sets junior hiring directly, so a run's junior hires step at Y.
- **`PriceHorizon`:**
  - it moves new-contract prices at once, and with them vendor revenue and the revenue weights;
  - the jump in the revenue-weighted effort share is at most 0.08 points, large only against the share's very slow base drift (4e-5 per step);
  - the rho is negative because the jump grows as a run's `PriceHorizon` moves below the model's 7, and most of the 4-8 range lies below it.
- **Re-anchored rate levers:** `g`, `VerifDecline`, `aL_max` and `AICostDecline` cause no flags, so re-anchoring works on phase 8.

### D.4 Anything surprising

1. **The bands carry no adoption-speed uncertainty** (C.4). The 2030 `A_mean` band is 0.900-0.912, while the alternative model sits at 0.957.
2. **`PriceHorizon` is at its fit bound in both phase 8 models** (D.1). Phase 7's was at 98.5% of its bound 8 (Q02). The fit keeps pushing the client price horizon to whatever ceiling it is given. Phase 8 meets the "PriceHorizon 4-7 years" D target only because the bound is 7.
3. **README describes `phase8`'s adoption path inaccurately.** README "Models" says `phase8` "adopts faster early and saturates sooner". The runs show otherwise:
   - **Early:** it is above `phase7` only until about 2025.5 (2025: 0.497 against 0.487).
   - **From 2026:** it is below (0.622 against 0.630 in 2026, 0.800 against 0.853 in 2028, 0.904 against 0.957 in 2030).
   - **0.99:** it reaches 0.99 in 2035.25, against 2032.0 for `phase7` and `phase8_highadoption`.
4. **Temporary shocks overshoot** (`shock_response.csv`; deterministic, from 2024):

   | model | scenario | HeadTotal trough against Base | later peak against Base |
   | --- | --- | --- | --- |
   | phase7 | Compute shock | -13.5% (2030) | +7.7% (2034) |
   | phase8 | Compute shock | -16.0% (2030) | +11.4% (2034) |
   | phase7 | Downturn | -6.6% (2030) | +3.2% (2033) |
   | phase8 | Downturn | -8.5% (2030) | +4.7% (2033) |

   - **The echo:** after the shock ends (2029.5 and 2029), headcount does not return to Base but overshoots by 5-11%, two to four years later, then settles. Vendor and consumer headcounts both do it. The same shape shows in the Monte Carlo medians (C.5 chart).
   - **Inherited:** it is present in `phase7` and larger in `phase8`. It looks like an under-damped hiring loop. Its cause was not diagnosed here.
   - **The direction during the shock:** headcount falls during the compute-cost shock even though adoption also falls (`A_mean` -3.0 points). The cost shock lowers employment more than lower AI use raises it. This may be intended (budgets), but no spec text was checked.
5. **The scenario colour map repeats.** In a 13-scenario overlay, Compute shock and Downturn share a colour, as do Slow AI and GCC wave persists. The legend also runs into the title. The overlay was replaced by small multiples (D7).

## Story for the README

What `phase8` shows, in its Base case, for a reader outside the project. "Model units" are the model's headcount units, not persons.

- **Total IT employment** is roughly flat to 2040. The model shows 82,654 model units in 2024 and 80,696 in 2040 (-2.4%). With the calibrated history held to mid-2026 and 13 uncertain inputs sampled, the 2040 range (p10-p90) is 72,600 to 103,700.
- **Work moves from IT vendors to clients' own teams.** Vendor headcount falls 34% by 2040, while in-house and captive-centre (GCC) headcount rises 43%; captive centres in India nearly triple.
- **Vendor revenue** falls 21% in real terms by 2040 (5.73 to 4.50 bn USD a year), as AI raises productivity and clients price it in.
- **Entry-level hiring** drops to half its 2024 level and stays there (0.50 in 2040).
- **AI is near-universal in delivery by about 2030:** adoption reaches 90% in 2030 (96% in the faster-adoption variant).
- **Effort billing declines.** Time-and-materials and staff augmentation fall from 39% of vendor contracts (revenue-weighted) to 30% by 2040, and fixed price and managed services gain.
- **Demand growth matters most for jobs.** Demand growth after 2026 and how fast AI's verification overhead falls drive most of the spread in 2040 employment. A stalled demand path gives 59,100 model units in 2040; a boom gives 110,000.
- **How fast AI is adopted after 2026 matters less than these inputs.** The faster-adoption variant's 2040 employment (80,900) lies inside the range above.

## Issues found (ranked by severity)

1. **The Monte Carlo bands carry no adoption-speed uncertainty (medium).**
   - **Evidence:** C.4. The 13 tornado levers move the 2030 `A_mean` by 1.3 points in total (0.900-0.912). `phase8_highadoption`, the documented adoption-speed alternative, sits at 0.957, far above p90. `p` cannot be sampled under `perturb_from` (README "Models"), and no lever moves adoption from Y. The headline bands still contain that model's outcomes, but a reader of the bands alone would not see adoption uncertainty.
   - **Suggested fix:**
     - now: state this in README "Models" and in the analyze rule;
     - later: a slice adding an adoption-speed lever that acts from Y, with a re-anchored adoption path (like the five re-anchored paths), so it can be sampled.
2. **`PriceHorizon` sits at its fit bound in both phase 8 models (medium-low).**
   - **Evidence:** D.1. It is fitted at 6.9999995 and 6.99999999999 against the bound 7. Phase 7's value was at 98.5% of its bound 8. The D target "PriceHorizon 4-7 years" is met by the bound, not by the data. `PriceHorizon` is the top 2032 driver of the effort share (rho +0.65).
   - **Suggested fix:** profile the loss over `PriceHorizon` (`tools/calibrate.py --profile PriceHorizon=4,10,0.5`, the other ten refitted at each point). Record in README that the value is bound-constrained and how much loss the bound costs.
3. **The README wording on `phase8`'s adoption path is wrong (low; documentation).**
   - **Evidence:** D.4 item 3. "Adopts faster early and saturates sooner" does not match the runs: `phase8` is below `phase7` from 2026 and reaches 0.99 three years later.
   - **Suggested fix:** reword. For example: "`phase8` adopts slightly faster in 2024-2025, then more slowly: `A_mean` 0.800 in 2028 and 0.904 in 2030, against Phase 7's 0.853 and 0.957; it passes 0.99 in 2035."
4. **Overshoot after temporary shocks (low; behaviour, inherited).**
   - **Evidence:** D.4 item 4. Headcount overshoots Base by 11% (Compute shock) and 5% (Downturn) two to four years after the shock ends, in `phase8`, and by 8% and 3% in `phase7`. No calibration target sees it.
   - **Suggested fix:** a diagnosis question through `/analyze` (trace the hiring and openings loop through the shock), before the public release describes shock scenarios.
5. **The tornado ranges for `JuniorCut` and `Verif` are centred on Phase 7 (low).**
   - **Evidence:** D.1. `phase8`'s `JuniorCut` sits at 81% of its range and `Verif` at 93%. They are inside, so nothing is excluded, but about 80% of sampled runs use a lower junior cut than the model. This is slice 9's open question 1.
   - **Suggested fix:** a slice prompt to recentre the relative ranges on the selected model (`tornado_levers(model=...)`). `TORNADO` itself stays, for Phase 7 parity.
6. **The colour map repeats beyond eight scenarios (low; charts).**
   - **Evidence:** D.4 item 5. In a 13-scenario overlay, two pairs of scenarios share colours.
   - **Suggested fix:** extend `aisim/charts/colours.py` with line styles or more colours for scenarios beyond the Okabe-Ito eight, or have `charts.scenarios` refuse an overlay of more than eight.

## Caveats

- **Calibration.** The 2024-2026 data identify the early adoption path but not its speed after 2026. That is why every adoption-sensitive result is shown on both `phase8` and `phase8_highadoption` (README "Models"). The two models also differ before 2026.5 (C.4), so they are two calibrations, not one history with two futures. The `phase7` figures carry Phase 7's caveat: its optimiser stalled on a junior-hiring discontinuity that phase 8 removes.
- **The core 4 band.** The OIT book price drift check (`AvgIdx_OIT` CAGR 2026-2030) uses the band [-3.5%, -2%] a year, widened from [-3%, -2%] by an operator ruling on 2026-10-16, after recon 09's results were seen. `phase8` gives -2.96% a year, inside both bands; `phase8_highadoption` gives -3.23%, inside the widened band only.
- **Hiring and layoffs together after 2030.** Under continuous openings, a unit-level can hire and lay off in the same step. In `phase8` this is absent in Base and peaks at 2.9% of staff a year for onshore seniors in Fast AI after 2030 (slice 9). No calibration target sees it, and the Fast AI headcounts after 2030 include it.
- **Missed targets.** `phase8` misses two of slice 8's D targets:
  - the renewal step-down on annuity contracts of about 20% (all three models miss it);
  - the per-unit discount of 25-40% within 3-5 years, at 21.7% in 2030 (Phase 7 met it).

  The new-signing prices in B.4 should be read with that in mind.
- **The bands are conditional.** They cover only the 13 tornado ranges, sampled uniformly and independently from 2026.5, with everything else at `phase8`'s calibrated values. The ranges are not centred on `phase8` (C.1, D.1), and they exclude adoption speed (issue 1).
- **Immediate levers.** `JuniorCut` and `PriceHorizon` step junior hiring and prices at 2026.5 (D.3). The jump is part of the "levers act from Y" design, not a defect, but a run's first year after Y carries it.
- **Volume, not value.** Book shares are contract volume (each vendor's 2024 book = 1). The revenue weights are USD, so the revenue-weighted share mixes a volume share inside each vendor with revenue weights across vendors (as in Q01 and Q02).
- **Scenario pinning.** In C.5, a scenario that sets a sampled lever runs with that lever fixed and the others as drawn. So, for example, the Slow AI band has no `g` or `VerifDecline` uncertainty.
- **Not a forecast.** The model shows how its mechanisms combine under these assumptions. It does not say what will happen.

## Settings and seeds

- **Code:** commit `207b2902e0aee335d07205b9a7672e38c01996bc`, branch `main`, clean tree (`git status --porcelain` empty in `meta.json`).
- **Package versions:** `ai-it-labour-sim` 0.1.0, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1; matplotlib 3.11.2 (dev group).
- **Platform:** Python 3.12.10 on Windows 11 ARM64. `NPY_DISABLE_CPU_FEATURES` is unset; it does not apply on ARM64.
- **Deterministic runs (A, B, D.4):** `Experiment(model=m, scenario=s)` for m in `phase7`, `phase8`, `phase8_highadoption` and s in Base (`None`), Fast AI (g 0.20, VerifDecline 0.10) and Slow AI (g 0.05, VerifDecline 0.0). No `perturb_from`, `record_every` 0.25, `stop` 16, `dt` 1/16, `workers` 1, validation on. D.4 adds Compute shock and Downturn for `phase7` and `phase8` at `record_every` 1.
- **Monte Carlo (C.1-C.3):**
  - design: `Experiment(model="phase8", sample=tornado_levers(perturb_from=2026.5, model="phase8"), n=1000, method="lhs", seed=20261017, perturb_from=2026.5)`;
  - the 13 levers: g, DemandGrowthLate, VerifDecline, JevonsEps, GCCAppealKeep, JuniorCut, TMBrake, PriceHorizon, aL_max, SrcCostSens, AICostDecline, RegScenario, EnrolSensitivity;
  - run settings: `record_every` 1, `stop` 16, `keep_state` True, auto chunking (125 per chunk, 8 workers), validation on;
  - **0 invalid runs**; no noise; the samples are in `samples.csv`.
- **Continuity run (C.2, D.2, D.3):** the same experiment with `record_every` 1/16 and `stop` 3 (to 2027), `keep_state` True. Base path: `Experiment(model="phase8")` at `record_every` 1/16, `stop` 3.
- **Adoption-speed run (C.4):** `Experiment(model="phase8_highadoption", perturb_from=2026.5)`, one run.
- **Scenarios (C.5):** `run_scenarios(<the Monte Carlo experiment>, [None, 12 scenarios])`, 13 blocks of 1,000 runs, 0 invalid in each.
- **Integrity (D.2):**
  - `aisim.run` (scalar engine) on `Params.baseline(m)` with the scenario or `EXTREME` overrides, at `record_every` 1/16 for T2 and 1 for T1 (AI off);
  - `validate(Params.baseline(m), model=m, perturb_from=...)`;
  - `people()` and `annual()` copied from `tests/helpers.py:105-117` (D3).
- **Statistics:** percentiles from `ExperimentResult.bands` (the prototype's `pct`), over valid runs; Spearman from `aisim.experiment.drivers`, and `scipy.stats.spearmanr` for the continuity attribution.
- **Records and timings:**
  - `meta.json` holds every result's meta (experiment, seed, outputs, versions, `NPY_DISABLE_CPU_FEATURES`, `git_commit`, `git_dirty`, platform) plus timings;
  - `summary.json` holds the key numbers, and `checks.csv` the 35 checks (all pass);
  - timings: deterministic runs 6.8 s, Monte Carlo 2.6 s, scenarios (13,000 runs) 11.5 s, continuity run 1.7 s, whole script about 36 s.

## D-rulings (minor decisions taken)

- **D1. Levers from 2024 in A and B.** The deterministic headline and mix runs leave `perturb_from` unset.
  - **Why:** they compare with `phase7` like-for-like and with Q01, Q02, the Phase 7 guide and `09-effort-shares.csv`.
  - **Effect:** Base is identical either way. Fast and Slow AI from 2026.5 are reported with bands in C.5.
- **D2. `DemandGrowthLate`'s model value.** It is `None` in every baseline, meaning "equal to `DemandGrowth`" (`domains.csv`, `engine.py:120`). D.1 uses 0.03.
- **D3. Integrity helpers copied.** `people()` and `annual()` are copied from `tests/helpers.py:105-117`, with citations.
  - **Why:** importing `tests.helpers` pulls in pytest and the prototype runner. The two helpers are stock sums, not model formulas.
  - **Per-run T2:** sums the same six stocks over the `BatchState` arrays.
- **D4. `validate()` takes the parameters with the overrides applied.** My first scenario check passed the bare baseline and missed Visa crackdown's window violation. It now passes `Params.baseline(m).with_overrides(**ov)` and `overrides=ov`, as the runner does. `run_scenarios` caught the miss.
- **D5. Shift-share as lines, not bars.** The package has no bar chart for a decomposition (`charts.drivers` is Spearman-specific). The components are drawn as `charts.lines` (deterministic) and `charts.bands` on an array mapping (Monte Carlo); the numbers are in B.2.
- **D6. The `bands` baseline line from another model.** `charts.bands(mc, key, baseline=<phase8_highadoption run>)` accepts a one-run result from another model and labels it "baseline run". The title and caption say it is `phase8_highadoption`.
- **D7. Scenario chart as small multiples.** The overlay of 13 scenarios repeats colours (issue 6).
- **D8. Added checks and tables.** The prompt did not ask for these:
  - Q3 counts;
  - the Monte Carlo shift-share;
  - the deterministic `phase8` Base's rank in its own band;
  - the bit-equality checks (scenario Baseline block against the Monte Carlo, continuity run against the Monte Carlo, `phase8_highadoption` from Y against plain);
  - fit-bound positions;
  - the shock-response table (D.4).

## Files

- **Script and text:** `run.py`, `report_text.md` (the report's text sections), `report.html`, `findings.md` (this file), `tables.md` (every table, generated).
- **Charts (PNG, each with `chart_<name>.csv`):**
  - headlines: `headlines_HeadTotal`, `headlines_RevenueTot`;
  - effort shares: `effort_OIT`, `effort_GSI`, `effort_BQ`, `effort_rw`;
  - shift-share: `shift_share_phase8`, `shift_share_mc`;
  - Monte Carlo bands: `mc_HeadTotal`, `mc_RevenueTot`, `mc_EffortShare_rw`;
  - drivers: `drivers_2032`, `drivers_2040`;
  - scenarios: `scenarios_HeadTotal`.
- **Tables (CSV):**
  - A: `headlines`, `headlines_wide`, `headlines_base_compact`, `headlines_scenarios_2030_2040`;
  - B: `book_mix`, `effort_shares`, `shift_share`, `pnew`;
  - C: `mc_bands`, `shift_share_mc`, `q3_counts`, `drivers_2032`, `drivers_2040`, `drivers_top5`, `adoption_vs_band`, `scenarios_invalid`, `scenarios_bands`;
  - D: `lever_ranges`, `fit_bounds`, `validation`, `integrity`, `continuity`, `shock_response`;
  - checks: `checks.csv`.
- **Saved results (`results/`, `.npz` plus a `.json` sidecar each, loadable with `ExperimentResult.load`):**
  - `mc_phase8`, `continuity_mc` and `phase8_highadoption_from_Y`;
  - the 9 deterministic runs (`det_<model>_<scenario>`);
  - the 13 scenario blocks (`scen_<scenario>`).
- **Reproducibility:** `meta.json`, `summary.json`, `samples.csv`.

## Notes for the release slice

- **No saving a whole `ScenarioResult`:** it has no `save`, so each block is saved separately.
- **No decomposition chart:** `charts` has no bar chart for a decomposition (D5).
- **A `validate()` trap:** its contract (parameters with overrides applied, plus their names) is easy to misuse from analysis code (D4). A `validate(experiment)` helper would avoid it.
- **`charts.bands`** labels any `baseline=` run "baseline run", even one from another model (D6). A `baseline_label=` argument would help.
