> **Analysis Q04, from the development of this model.** Copied verbatim below the line from the analysis's findings note.
>
> - **Question:** Why does headcount overshoot Base after the temporary shocks (Compute shock and Downturn)?
> - **Ran on:** commit `207b290`, models `phase8` (the main runs), `phase7` and `phase8_highadoption`. Commit ids refer to the private development repository.
> - **Paths:** Paths under `temp/` (the analysis scripts, CSVs, charts and saved results it names) refer to the development workspace and are not in this repository.

---

# Q04 - why headcount overshoots after temporary shocks

Reproduce from the repo root. One command writes every CSV, PNG, saved result, `meta.json`, `summary.json`, `tables.md` and `report.html` in this folder, in about 75 s:

```
uv run python temp/analysis/q04-shock-overshoot/run.py
```

- **Code:** commit `207b290` on branch `main`, with a clean tree (`git_dirty` false in every result's meta, `git status --porcelain` empty).
- **Model changes:** none. There is no `analysis/` branch, nothing tracked was changed and nothing was committed. Every variant uses existing parameters or the `ai_on` run argument.
- **Checks:** 109 internal checks pass (`checks.csv`):
  - the scalar and batched engines agree bit for bit;
  - Q03's annual figures reproduce exactly;
  - the backlog identity closes to 4e-11 BFY;
  - section C's step 0 equals `phase7` and step 3 equals `phase8`, bit for bit.
- **Not part of the deliverable:** `scratch/explore.py`, an exploratory trace written before `run.py`. My attempt to delete it was declined, so it is still in the folder.

## Short answers

**Continuation or reversal (operator refinement).** For both shocks and all three models, the `HeadTotal` gap to Base has the same shape: negative during the window, negative for 2.6-2.8 more years (a continuation), then a sign change. So the post-window excess is a **reversal, a true overshoot**, in all six cases. No case has a continuation above Base. Peaks are at 1/16-year resolution, so they sit slightly above Q03's annual figures (+11.4% and +4.7% for `phase8`).

| model | shock | during window | after window: continuation | then reversal | second swing | post-window excess |
| --- | --- | --- | --- | --- | --- | --- |
| phase7 | Compute shock | - (extreme -12.5%) | - to 2032.12 (trough in it) | + peak +9.0% in 2033.44 | -1.4% in 2036.56 | reversal |
| phase7 | Downturn | - (extreme -5.0%) | - to 2031.56 (trough in it) | + peak +3.4% in 2032.62 | -1.0% in 2036.00 | reversal |
| phase8 | Compute shock | - (extreme -14.3%) | - to 2032.25 (trough in it) | + peak +12.2% in 2033.75 | -2.4% in 2036.31 | reversal |
| phase8 | Downturn | - (extreme -5.8%) | - to 2031.62 (trough in it) | + peak +4.8% in 2032.81 | -1.5% in 2036.00 | reversal |
| phase8_highadoption | Compute shock | - (extreme -14.0%) | - to 2032.25 (trough in it) | + peak +11.2% in 2033.69 | -2.4% in 2036.25 | reversal |
| phase8_highadoption | Downturn | - (extreme -5.7%) | - to 2031.62 (trough in it) | + peak +4.4% in 2032.81 | -1.4% in 2036.00 | reversal |

**1. Mechanism.** The overshoot runs through two stocks, the work backlog `BL` and the headcount pipeline (vacancies, onboarding, headcount). In order:
- **The shock cuts approved demand.**
  - Downturn: the budget falls 14.9% from 2027.0, so committed spend exceeds it, the smoothed spend ratio `SpendRatio` rises, and `Approval` falls by up to 19.5% (budget-weighted; lowest sector 0.69). App, data and AI-build demand fall, and total demand is 8.2% below Base at 2028.4.
  - Compute shock: tripled AI unit and credit costs raise committed spend (+26% against budget), and `Approval` falls by up to 35%. Demand is 15.2% below Base.
- **Desired staff follows the backlog.** The backlog falls 14.2% by 2029.0 (Downturn). Desired staff, sized to the backlog (`BL / (TargetClearanceTime x PerceivedP)`), falls with it, within 0.03 points.
- **Headcount falls through attrition.** Openings drop and vacancies fall 51%, and headcount shrinks through quits and exits. Layoffs barely move: at most 0.1% of Base headcount a year in Downturn.
- **After the window, demand returns at once but staff do not.** `Approval` is back at 1 by 2029.9 (Downturn; 2030.4 in the Compute shock). Headcount keeps falling to its trough at 2029.8-2030.1, because openings, matching and onboarding take time. Work then arrives faster than the reduced staff can complete it.
- **The backlog overshoots.** It is above Base from 2030.25 and peaks at +11.1% in 2031.6 (Compute shock +26.3%).
- **Hiring overshoots.** Desired staff tracks the backlog, so openings peak at +12.1% of Base headcount a year (2030.5), vacancies at +58%, and hires at +7.2% of headcount a year (2031.4).
- **Headcount overshoots.** It passes Base in 2031.75 and peaks at +4.8% in 2032.8, just as the backlog surplus is being cleared.
- **Ringing.** The extra staff then drain the backlog below Base (-3.7% in 2034.5), and hiring falls again. Headcount undershoots by 1.5% in 2036.0, with a smaller third swing. In the Compute shock the overshoot is unwound partly by layoffs: 2.4% of headcount a year in 2034.

**2. Real or artefact?** Nothing is double counted and recovery creates almost no work:
- **The backlog identity closes:** `BL` gap = sum of dt x (demand gap - completion gap - abandonment gap), to 4e-11 BFY.
- **Lost demand is not deferred.** In Downturn, 16,389 BFY of demand is lost (13,799 in the window, 2,590 while `Approval` recovers). Only 11 BFY of new demand appears after the window.
- **The completion surplus is delayed work.** The extra completions after the window (13,001 BFY) are work that arrived while staff were short and waited in the backlog.
- **Abandonment never acts** in any run.

There is no pent-up demand in the model's sense: demand that `Approval` cuts is lost for good. Step by step:
- **The continuation** (the gap staying negative 2.6-2.8 years past the window) is the hiring lag after a demand recovery. That is real behaviour and the spec's stated design (`00_model_spec.md:395`, `:418`).
- **The reversal** is the spec's loop B13, whose "long delays cause overshoot and undershoot" (`00_model_spec.md:144`): staff sized to a backlog that grew while hiring lagged. The direction is plausible.
- **The size is not validated.** It is set by two time constants no calibration target constrains on a shock: `TargetClearanceTime` and `HireAdjTime`. The formulation also has a property that real firms may not share: desired staff responds one for one to a temporary backlog bulge, with no forecast that the bulge will clear (`workforce.py:94`).
- **The ringing** (a second undershoot of 1.0-2.4% around 2036 and a third swing) follows from the same loop and is the least supported part.
- **The Compute shock is mainly a budget squeeze in this model.** AI costs count fully in committed spend against budget. Switching off AI cost's effect on adoption (`CostAdoptElast` 0) leaves the trough at -15.9% (against -16.0%) and the peak at +10.9% (against +12.2%). The "less AI, more human work" channel is a small continuation: +0.4% demand after 2031 (3,488 BFY of non-AI-build demand) and about a tenth of the headcount peak.

**3. Why bigger in phase 8?** Mostly the recalibration, then the continuous-openings fix; pricing adds nothing.
- **Downturn:** the peak rises from +3.42% to +4.81% (+1.39 points): the fix +0.38, the recalibration +1.00, pricing +0.00.
- **Compute shock:** +9.02% to +12.18% (+3.16 points): the fix +0.98, the recalibration +2.19, pricing -0.02.
- **How the recalibration acts:** mainly by deepening the trough (Downturn -7.2% to -8.5%), because Base has less budget headroom (committed spend over budget at 2027.0 is 0.990 in `phase7` and 1.000 in `phase8`), so the same cut bites harder. It also raises the rebound ratio (peak over trough depth) from 0.53 to 0.57.
- **The fitted values one at a time:** on step 1, `q` (0.495 to 0.064, the slower delivery adoption after 2026) adds the most, +1.59 and +1.89 points (Downturn, Compute shock), then `Verif` (+0.60, +0.70) and `GCCAppealEnd` (+0.28, +0.69). `p` lowers the peak (-0.49, -0.20).
- **Recon 09b's separate refit** gives the same result within 0.1 points.

**4. Sensitivity** (`phase8` Downturn, 0.5x to 2x). The peak above Base ranges:
- **`HireAdjTime`:** 3.4% to 6.7%, peaking 3.5 to 4.4 years after the window; it settles by 2033.9 at 0.5x and not by 2040 at 1.5x and above.
- **`TargetClearanceTime`:** 10.4% at 0.5x, 4.3% at 0.75x, 4.8% at 1x, 2.3% at 1.5x and 1.1% at 2x, peaking 2.8 to 6.6 years after the window. It is not monotone at the low end because 0.5x equals `MinCompletionTime` (0.25), where the completion cap binds.
- **`OnboardTime`:** 4.3% to 5.6%.
- **`CancelTime`:** 4.2% to 5.3%.
- **`m`** (matching efficiency, the main lever on time to fill): 6.4% at 0.5x and 4.5% at 2x.
- **`MinFillTime`:** 4.4% and 4.1% at 1.5x and 2x; 0.5x and 0.75x fail validation (a floor below dt).
- **`BudgetCycle`:** 5.9% to 3.2%, mostly through the trough depth.
- **Nearly flat:** `PerceptionTime` (4.7% to 5.1%), `LayoffAdjTime` (4.7% to 4.9%), `SrcPerceptionTime`, `ViabilityTime` and `MinLayoffTime` (within 0.1 points).

## A. The overshoot, measured

**The design:**
- `run_scenarios(Experiment(model=m), [None, "Compute shock", "Downturn"], record_every=1/16)` for m in `phase7`, `phase8` and `phase8_highadoption`, deterministic, with levers from 2024 (no `perturb_from`, as Q03 A);
- the same nine runs on the scalar engine with a `trace`, for the quantities that are not catalogue keys (openings, vacancies, hires, onboarding, layoffs, desired staff, `Approval`).

**Measures:** gaps are against Base of the same model. A level is measured as ratio minus 1; a flow (openings, hires, layoffs) as its gap divided by Base `HeadTotal`, per year.
- **Trough:** the minimum from the window start.
- **Peak:** the maximum from the window end.
- **"Gap below 1% from":** the first time after which |gap| stays under 1% to 2040.

**Windows** (`windows.csv`): `AIShockMult` 3 over 2027.0-2029.5 and `BudgetShock` 0.15 over 2027.0-2029.0, active while `start <= year < end` (`finance.py:146`, `consumer.py:123`). They are the same in all three models.

### A.1 Headcount (`overshoot_head.csv`)

**phase8, Downturn**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -8.6% (2029.81) | +4.8% (2032.81, 3.81) | 2036.88 |
| VendorHead | -8.7% (2029.75) | +4.9% (2032.69, 3.69) | 2036.38 |
| ConsIT | -8.5% (2029.94) | +4.8% (2032.88, 3.88) | 2037.06 |
| Head_GCC | -7.0% (2030.50) | +2.5% (2033.56, 4.56) | 2037.75 |
| Head_IH | -9.9% (2029.75) | +8.0% (2032.75, 3.75) | not by 2040 |
| Head_OIT | -8.0% (2029.88) | +3.8% (2032.94, 3.94) | 2036.88 |
| Head_GSI | -9.3% (2029.62) | +4.9% (2032.56, 3.56) | 2036.44 |
| Head_BQ | -10.1% (2029.56) | +9.1% (2032.44, 3.44) | not by 2040 |

**phase8, Compute shock**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -16.0% (2030.06) | +12.2% (2033.75, 4.25) | not by 2040 |
| VendorHead | -16.4% (2030.00) | +12.0% (2033.56, 4.06) | 2038.50 |
| ConsIT | -15.6% (2030.19) | +12.6% (2033.81, 4.31) | not by 2040 |
| Head_GCC | -13.7% (2030.69) | +8.4% (2034.25, 4.75) | 2038.31 |
| Head_IH | -16.9% (2030.12) | +17.5% (2033.75, 4.25) | not by 2040 |
| Head_OIT | -16.4% (2030.06) | +9.3% (2033.81, 4.31) | not by 2040 |
| Head_GSI | -16.4% (2029.88) | +12.4% (2033.56, 4.06) | not by 2040 |
| Head_BQ | -16.9% (2029.88) | +20.2% (2033.44, 3.94) | not by 2040 |

**phase7, Downturn**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -6.7% (2029.88) | +3.4% (2032.62, 3.62) | 2036.25 |
| VendorHead | -7.0% (2029.69) | +3.8% (2032.62, 3.62) | 2034.00 |
| ConsIT | -6.5% (2030.06) | +3.2% (2032.81, 3.81) | 2036.62 |
| Head_GCC | -5.8% (2030.56) | +2.0% (2033.69, 4.69) | 2037.56 |
| Head_IH | -7.4% (2029.81) | +6.3% (2032.50, 3.50) | 2039.88 |
| Head_OIT | -6.8% (2029.69) | +3.2% (2032.81, 3.81) | 2036.94 |
| Head_GSI | -7.3% (2029.62) | +3.4% (2032.38, 3.38) | 2037.00 |
| Head_BQ | -6.8% (2029.50) | +7.3% (2032.19, 3.19) | 2039.81 |

**phase7, Compute shock**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -13.6% (2030.19) | +9.0% (2033.44, 3.94) | not by 2040 |
| VendorHead | -14.2% (2030.00) | +9.1% (2033.38, 3.88) | 2038.25 |
| ConsIT | -13.2% (2030.38) | +9.1% (2033.56, 4.06) | not by 2040 |
| Head_GCC | -11.4% (2030.75) | +8.3% (2034.25, 4.75) | 2035.56 |
| Head_IH | -14.9% (2030.25) | +13.4% (2033.25, 3.75) | not by 2040 |
| Head_OIT | -14.6% (2030.06) | +7.1% (2033.44, 3.94) | not by 2040 |
| Head_GSI | -13.7% (2029.81) | +9.8% (2033.12, 3.62) | 2039.38 |
| Head_BQ | -14.2% (2030.12) | +13.8% (2033.12, 3.62) | not by 2040 |

**phase8_highadoption, Downturn**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -8.1% (2029.81) | +4.4% (2032.81, 3.81) | 2036.81 |
| VendorHead | -8.3% (2029.69) | +4.6% (2032.62, 3.62) | 2036.19 |
| ConsIT | -7.9% (2030.00) | +4.4% (2032.88, 3.88) | 2037.00 |
| Head_GCC | -6.6% (2030.50) | +2.4% (2033.62, 4.62) | 2037.62 |
| Head_IH | -9.3% (2029.75) | +7.5% (2032.69, 3.69) | not by 2040 |
| Head_OIT | -7.6% (2029.88) | +3.6% (2032.88, 3.88) | 2037.12 |
| Head_GSI | -8.9% (2029.62) | +4.6% (2032.56, 3.56) | 2036.25 |
| Head_BQ | -9.5% (2029.50) | +8.7% (2032.38, 3.38) | not by 2040 |

**phase8_highadoption, Compute shock**

| key | trough (year) | peak above Base after window (year, years after end) | gap below 1% from |
| --- | --- | --- | --- |
| HeadTotal | -15.5% (2030.06) | +11.2% (2033.69, 4.19) | not by 2040 |
| VendorHead | -16.0% (2029.94) | +11.1% (2033.50, 4.00) | 2038.56 |
| ConsIT | -15.0% (2030.25) | +11.6% (2033.75, 4.25) | not by 2040 |
| Head_GCC | -13.3% (2030.69) | +7.8% (2034.25, 4.75) | 2038.06 |
| Head_IH | -16.5% (2030.19) | +16.6% (2033.62, 4.12) | not by 2040 |
| Head_OIT | -16.1% (2030.12) | +8.5% (2033.75, 4.25) | not by 2040 |
| Head_GSI | -16.0% (2029.88) | +11.4% (2033.44, 3.94) | not by 2040 |
| Head_BQ | -16.5% (2029.88) | +18.9% (2033.31, 3.81) | not by 2040 |

Every employer overshoots. In-house (`Head_IH`) and BQ overshoot most (+6-20%); GCC least (+2-8%) and latest (4.6-4.8 years after the window); the runs do not show why. The charts are `head_<model>.png` and `stocks_<model>_<shock>.png`.

### A.2 Demand, budget, backlog, revenue and hiring (`overshoot_flows.csv`, `overshoot_all.csv`)

`Approval`, `Openings`, `Vacancies`, `Hires` and `Layoffs` come from the trace.

**phase8, Downturn**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -14.9% (2027.00) | +0.0% (2029.00) | 2029.00 |
| Committed | ratio to Base - 1 | -6.9% (2029.62) | +4.8% (2032.62) | 2039.25 |
| Demand | ratio to Base - 1 | -8.2% (2028.38) | +0.0% (2030.00) | 2029.56 |
| Backlog | ratio to Base - 1 | -14.2% (2029.00) | +11.1% (2031.62) | 2038.50 |
| Completion | ratio to Base - 1 | -8.6% (2029.75) | +4.9% (2032.69) | 2036.81 |
| ServicesSpend | ratio to Base - 1 | -10.6% (2029.69) | +7.6% (2032.56) | 2039.81 |
| RevenueTot | ratio to Base - 1 | -9.3% (2029.50) | +5.6% (2032.44) | 2035.31 |
| Openings | flow gap / Base HeadTotal | -8.7% (2028.44) | +12.1% (2030.50) | 2037.50 |
| Vacancies | ratio to Base - 1 | -50.9% (2028.94) | +58.2% (2031.50) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -7.0% (2028.75) | +7.2% (2031.38) | 2037.88 |
| Layoffs | flow gap / Base HeadTotal | +0.0% (2027.00) | +0.1% (2032.88) | never above 1% |
| HireJ_IN | ratio to Base - 1 | -28.8% (2028.50) | +21.7% (2030.94) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -31.9% (2028.56) | +29.3% (2031.00) | not by 2040 |
| Approval | ratio to Base - 1 | -19.5% (2028.38) | +0.0% (2030.00) | 2029.69 |
| A_mean | ratio to Base - 1 | -0.0% (2031.44) | +0.0% (2029.00) | never above 1% |
| AC_mean | ratio to Base - 1 | +0.0% (2027.00) | +0.0% (2029.00) | never above 1% |

**phase8, Compute shock**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -4.3% (2029.44) | -0.2% (2040.00) | 2029.50 |
| Committed | ratio to Base - 1 | -13.7% (2029.81) | +12.6% (2033.56) | not by 2040 |
| Demand | ratio to Base - 1 | -15.2% (2028.69) | +0.4% (2035.25) | 2030.19 |
| Backlog | ratio to Base - 1 | -24.9% (2029.19) | +26.3% (2032.31) | 2039.50 |
| Completion | ratio to Base - 1 | -17.0% (2029.88) | +12.0% (2033.69) | not by 2040 |
| ServicesSpend | ratio to Base - 1 | -19.0% (2029.88) | +20.8% (2033.56) | not by 2040 |
| RevenueTot | ratio to Base - 1 | -17.5% (2029.75) | +15.2% (2033.38) | 2039.69 |
| Openings | flow gap / Base HeadTotal | -17.2% (2028.38) | +24.4% (2030.94) | not by 2040 |
| Vacancies | ratio to Base - 1 | -81.7% (2029.00) | +149.8% (2032.25) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -10.5% (2028.75) | +11.5% (2032.56) | not by 2040 |
| Layoffs | flow gap / Base HeadTotal | +0.0% (2027.00) | +2.4% (2034.19) | 2034.69 |
| HireJ_IN | ratio to Base - 1 | -42.4% (2028.44) | +36.0% (2031.69) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -48.6% (2028.69) | +53.0% (2031.62) | not by 2040 |
| Approval | ratio to Base - 1 | -34.8% (2028.69) | +0.0% (2030.44) | 2030.31 |
| A_mean | ratio to Base - 1 | -3.7% (2029.50) | -0.0% (2040.00) | 2032.50 |
| AC_mean | ratio to Base - 1 | -7.1% (2029.50) | -0.5% (2040.00) | 2037.56 |

**phase7, Downturn**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -14.9% (2027.00) | +0.0% (2029.00) | 2029.00 |
| Committed | ratio to Base - 1 | -5.4% (2029.69) | +3.6% (2032.44) | 2034.06 |
| Demand | ratio to Base - 1 | -7.0% (2028.25) | +0.0% (2034.50) | 2029.50 |
| Backlog | ratio to Base - 1 | -11.3% (2028.94) | +8.2% (2031.50) | 2037.88 |
| Completion | ratio to Base - 1 | -6.8% (2029.81) | +3.4% (2032.50) | 2036.38 |
| ServicesSpend | ratio to Base - 1 | -8.3% (2029.69) | +6.0% (2032.44) | 2039.31 |
| RevenueTot | ratio to Base - 1 | -7.3% (2029.50) | +4.8% (2032.31) | 2033.88 |
| Openings | flow gap / Base HeadTotal | -13.1% (2028.25) | +9.1% (2030.38) | 2037.25 |
| Vacancies | ratio to Base - 1 | -51.6% (2028.81) | +48.0% (2031.44) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -6.7% (2028.38) | +5.7% (2031.19) | 2035.06 |
| Layoffs | flow gap / Base HeadTotal | +0.0% (2027.00) | +0.0% (2029.00) | never above 1% |
| HireJ_IN | ratio to Base - 1 | -53.2% (2028.38) | +13.8% (2030.75) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -96.1% (2027.75) | +21.4% (2030.94) | not by 2040 |
| Approval | ratio to Base - 1 | -16.7% (2028.25) | +0.0% (2029.88) | 2029.62 |
| A_mean | ratio to Base - 1 | -0.0% (2030.56) | -0.0% (2040.00) | never above 1% |
| AC_mean | ratio to Base - 1 | +0.0% (2027.00) | +0.0% (2029.00) | never above 1% |

**phase7, Compute shock**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -4.3% (2029.44) | -0.2% (2040.00) | 2029.50 |
| Committed | ratio to Base - 1 | -12.0% (2029.88) | +9.1% (2033.12) | not by 2040 |
| Demand | ratio to Base - 1 | -13.8% (2028.56) | +0.4% (2035.31) | 2030.19 |
| Backlog | ratio to Base - 1 | -21.4% (2029.06) | +20.5% (2032.19) | 2039.44 |
| Completion | ratio to Base - 1 | -14.6% (2030.00) | +8.9% (2033.31) | 2039.94 |
| ServicesSpend | ratio to Base - 1 | -16.8% (2029.94) | +15.7% (2033.12) | not by 2040 |
| RevenueTot | ratio to Base - 1 | -15.1% (2029.69) | +11.7% (2033.00) | 2036.75 |
| Openings | flow gap / Base HeadTotal | -25.8% (2028.31) | +20.3% (2030.88) | 2038.62 |
| Vacancies | ratio to Base - 1 | -89.0% (2028.62) | +124.3% (2032.06) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -13.3% (2028.38) | +10.6% (2032.25) | 2038.62 |
| Layoffs | flow gap / Base HeadTotal | +0.0% (2027.00) | +0.1% (2033.94) | never above 1% |
| HireJ_IN | ratio to Base - 1 | -80.1% (2028.38) | +24.3% (2031.38) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -100.0% (2028.00) | +37.3% (2031.44) | not by 2040 |
| Approval | ratio to Base - 1 | -31.5% (2028.62) | +0.0% (2030.44) | 2030.25 |
| A_mean | ratio to Base - 1 | -3.4% (2029.06) | -0.0% (2040.00) | 2031.31 |
| AC_mean | ratio to Base - 1 | -7.1% (2029.50) | -0.5% (2040.00) | 2037.56 |

**phase8_highadoption, Downturn**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -14.9% (2027.00) | +0.0% (2029.00) | 2029.00 |
| Committed | ratio to Base - 1 | -6.5% (2029.62) | +4.5% (2032.56) | 2039.25 |
| Demand | ratio to Base - 1 | -7.8% (2028.31) | +0.0% (2034.25) | 2029.56 |
| Backlog | ratio to Base - 1 | -13.5% (2029.00) | +10.4% (2031.62) | 2038.44 |
| Completion | ratio to Base - 1 | -8.1% (2029.75) | +4.5% (2032.69) | 2036.75 |
| ServicesSpend | ratio to Base - 1 | -10.0% (2029.62) | +7.3% (2032.56) | 2039.81 |
| RevenueTot | ratio to Base - 1 | -8.8% (2029.50) | +5.4% (2032.38) | 2035.56 |
| Openings | flow gap / Base HeadTotal | -8.5% (2028.44) | +11.3% (2030.44) | 2037.44 |
| Vacancies | ratio to Base - 1 | -50.3% (2028.88) | +55.4% (2031.50) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -6.8% (2028.69) | +6.7% (2031.38) | 2037.81 |
| Layoffs | flow gap / Base HeadTotal | +0.0% (2027.00) | +0.1% (2032.88) | never above 1% |
| HireJ_IN | ratio to Base - 1 | -27.7% (2028.44) | +18.0% (2031.00) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -31.7% (2028.50) | +25.0% (2031.00) | not by 2040 |
| Approval | ratio to Base - 1 | -18.6% (2028.31) | +0.0% (2029.94) | 2029.69 |
| A_mean | ratio to Base - 1 | -0.0% (2030.75) | -0.0% (2040.00) | never above 1% |
| AC_mean | ratio to Base - 1 | +0.0% (2027.00) | +0.0% (2029.00) | never above 1% |

**phase8_highadoption, Compute shock**

| key | measure | trough (year) | peak after window (year) | gap below 1% from |
| --- | --- | --- | --- | --- |
| Budget | ratio to Base - 1 | -4.3% (2029.44) | -0.2% (2040.00) | 2029.50 |
| Committed | ratio to Base - 1 | -13.2% (2029.81) | +11.8% (2033.50) | not by 2040 |
| Demand | ratio to Base - 1 | -14.8% (2028.62) | +0.4% (2035.25) | 2030.19 |
| Backlog | ratio to Base - 1 | -24.3% (2029.12) | +24.8% (2032.31) | 2039.44 |
| Completion | ratio to Base - 1 | -16.4% (2029.88) | +11.3% (2033.62) | not by 2040 |
| ServicesSpend | ratio to Base - 1 | -18.4% (2029.88) | +19.8% (2033.44) | not by 2040 |
| RevenueTot | ratio to Base - 1 | -17.1% (2029.75) | +14.4% (2033.31) | 2039.62 |
| Openings | flow gap / Base HeadTotal | -17.0% (2028.31) | +23.2% (2030.88) | 2039.88 |
| Vacancies | ratio to Base - 1 | -82.1% (2028.94) | +143.1% (2032.25) | not by 2040 |
| Hires | flow gap / Base HeadTotal | -10.3% (2028.69) | +11.2% (2032.62) | not by 2040 |
| Layoffs | flow gap / Base HeadTotal | -0.0% (2032.44) | +2.0% (2034.12) | 2034.56 |
| HireJ_IN | ratio to Base - 1 | -41.2% (2028.44) | +27.8% (2031.50) | not by 2040 |
| HireJ_ON | ratio to Base - 1 | -52.0% (2028.62) | +44.2% (2031.62) | not by 2040 |
| Approval | ratio to Base - 1 | -33.9% (2028.62) | +0.0% (2030.44) | 2030.31 |
| A_mean | ratio to Base - 1 | -3.4% (2029.06) | -0.0% (2040.00) | 2031.31 |
| AC_mean | ratio to Base - 1 | -7.1% (2029.50) | -0.5% (2040.00) | 2037.56 |

- **Demand** never rises meaningfully above Base after a Downturn (+0.01%). After a Compute shock it is +0.4% from 2031 to 2040.
- **Backlog, completion, committed spend, services spend and revenue** all reverse, because they follow headcount.
- **Junior hires** swing most: in `phase8`, -29% to -49%, then +22% to +53%.

### A.3 Budget headroom (`headroom.csv`)

`Approval` cuts demand only when the smoothed committed spend exceeds the budget (`consumer.py:209`). How close Base sits to that threshold at the shock start therefore sets the trough depth.

| model | shock | Base committed / budget, 2027.0 | Base max sector, 2027.0 | shock min sector Approval | shock max sector committed / budget after window | Approval below 1 until |
| --- | --- | --- | --- | --- | --- | --- |
| phase7 | Compute shock | 0.990 | 1.039 | 0.452 | 0.872 | 2030.38 |
| phase7 | Downturn | 0.990 | 1.039 | 0.720 | 0.929 | 2029.81 |
| phase8 | Compute shock | 1.000 | 1.048 | 0.419 | 0.893 | 2030.38 |
| phase8 | Downturn | 1.000 | 1.048 | 0.687 | 0.940 | 2029.94 |
| phase8_highadoption | Compute shock | 0.999 | 1.046 | 0.430 | 0.885 | 2030.38 |
| phase8_highadoption | Downturn | 0.999 | 1.046 | 0.698 | 0.933 | 2029.88 |

The phase 8 models start the shock with almost no headroom (1.000 and 0.999 against 0.990). After the window, committed spend stays below budget in every sector (at most 0.94 in Downturn and 0.89 in the Compute shock), so `Approval` stays at 1 through the overshoot. **The budget does not brake the hiring surge.**

## B. Mechanism (Questions 1 and 2)

### B.1 The chain, traced (`chain_timing.csv`)

`phase8`, from the scalar trace, against Base. The largest gap in the window is signed: `SpendPressure` (committed spend over budget) rises in the window and falls below Base after it, while headcount is low.

**Downturn**

| link | onset | largest gap in window | trough (year) | turns positive | reversal peak (year) | second swing (year) | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Budget | 2027.00 | -14.9% | -14.9% (2027.00) | - | - (-) | - (-) | no post-window gap |
| SpendPressure | 2027.00 | +17.5% | -6.9% (2029.62) | 2029.00 | -6.9% (2029.62) | +4.8% (2032.62) | reversal |
| Approval | 2027.06 | -19.5% | -19.5% (2028.38) | - | - (-) | - (-) | continuation |
| A_mean | - | +0.0% | -0.0% (2031.44) | - | - (-) | - (-) | no post-window gap |
| Demand | 2027.06 | -8.2% | -8.2% (2028.38) | - | - (-) | - (-) | continuation |
| Backlog | 2027.19 | -14.1% | -14.2% (2029.00) | 2030.25 | +11.1% (2031.62) | -3.7% (2034.50) | continuation then reversal |
| Completion | 2027.50 | -6.5% | -8.6% (2029.75) | 2031.69 | +4.9% (2032.69) | -1.5% (2035.94) | continuation then reversal |
| ImpliedPerceivedP | - | -0.0% | -0.0% (2029.69) | - | - (-) | - (-) | no post-window gap |
| Desired | 2027.19 | -14.1% | -14.2% (2029.00) | 2030.25 | +11.1% (2031.62) | -3.7% (2034.50) | continuation then reversal |
| Openings | 2027.12 | -8.7% | -8.7% (2028.44) | 2029.38 | +12.1% (2030.50) | -5.0% (2033.19) | continuation then reversal |
| Vacancies | 2027.19 | -50.9% | -50.9% (2028.94) | 2030.19 | +58.2% (2031.50) | -21.6% (2034.50) | continuation then reversal |
| Hires | 2027.19 | -7.0% | -7.0% (2028.75) | 2029.88 | +7.2% (2031.38) | -3.5% (2033.94) | continuation then reversal |
| Onboarding | 2027.25 | -42.7% | -42.7% (2028.88) | 2030.12 | +42.2% (2031.62) | -21.5% (2034.12) | continuation then reversal |
| Layoffs | - | +0.1% | +0.0% (2027.00) | - | - (-) | - (-) | no post-window gap |
| HeadTotal | 2027.62 | -5.8% | -8.6% (2029.81) | 2031.75 | +4.8% (2032.81) | -1.5% (2036.00) | continuation then reversal |
| VendorHead | 2027.56 | -6.2% | -8.7% (2029.75) | 2031.62 | +4.9% (2032.69) | -1.2% (2035.56) | continuation then reversal |
| ConsIT | 2027.75 | -5.3% | -8.5% (2029.94) | 2031.81 | +4.8% (2032.88) | -1.8% (2036.06) | continuation then reversal |

**Compute shock**

| link | onset | largest gap in window | trough (year) | turns positive | reversal peak (year) | second swing (year) | classification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Budget | 2027.00 | -4.3% | -4.3% (2029.44) | - | - (-) | - (-) | continuation |
| SpendPressure | 2027.00 | +26.1% | -13.4% (2029.75) | 2029.50 | -13.4% (2029.75) | +13.3% (2033.56) | reversal |
| Approval | 2027.06 | -34.8% | -34.8% (2028.69) | - | - (-) | - (-) | continuation |
| A_mean | 2027.06 | -3.7% | -3.7% (2029.50) | - | - (-) | - (-) | continuation |
| Demand | 2027.00 | -15.2% | -15.2% (2028.69) | 2031.44 | +0.4% (2035.25) | - (-) | continuation then reversal |
| Backlog | 2027.06 | -24.9% | -24.9% (2029.19) | 2030.62 | +26.3% (2032.31) | -8.5% (2035.25) | continuation then reversal |
| Completion | 2027.31 | -16.2% | -17.0% (2029.88) | 2032.31 | +12.0% (2033.69) | -2.7% (2036.12) | continuation then reversal |
| ImpliedPerceivedP | 2028.00 | -0.4% | -0.5% (2030.19) | - | - (-) | - (-) | continuation |
| Desired | 2027.06 | -24.6% | -24.6% (2029.19) | 2030.56 | +26.7% (2032.31) | -8.4% (2035.25) | continuation then reversal |
| Openings | 2027.06 | -17.2% | -17.2% (2028.38) | 2029.75 | +24.4% (2030.94) | -11.1% (2034.19) | continuation then reversal |
| Vacancies | 2027.12 | -81.7% | -81.7% (2029.00) | 2030.50 | +149.8% (2032.25) | -51.6% (2035.12) | continuation then reversal |
| Hires | 2027.12 | -10.5% | -10.5% (2028.75) | 2030.25 | +11.5% (2032.56) | -8.3% (2034.69) | continuation then reversal |
| Onboarding | 2027.19 | -63.5% | -63.5% (2028.88) | 2030.44 | +70.8% (2032.81) | -50.1% (2035.06) | continuation then reversal |
| Layoffs | 2027.75 | +3.6% | +0.0% (2027.00) | 2033.38 | +2.4% (2034.19) | - (-) | reversal |
| HeadTotal | 2027.50 | -14.3% | -16.0% (2030.06) | 2032.31 | +12.2% (2033.75) | -2.4% (2036.31) | continuation then reversal |
| VendorHead | 2027.44 | -14.8% | -16.4% (2030.00) | 2032.19 | +12.0% (2033.56) | -2.9% (2036.25) | continuation then reversal |
| ConsIT | 2027.69 | -13.8% | -15.6% (2030.19) | 2032.50 | +12.6% (2033.81) | -2.0% (2036.38) | continuation then reversal |

**Reading the chain** (Downturn; the Compute shock has the same order, larger):
1. **2027.0:** the budget drops 14.9%, so spend pressure and then `Approval` move within a step. `Approval` reaches its low (-19.5%) at 2028.4, a year after the cut, through the 1-year `BudgetCycle`. Demand follows (-8.2%).
2. **2027.1-2027.2:** openings and the backlog start falling. Desired staff falls with the backlog, within 0.03 points, because perceived productivity barely moves (-0.03%).
3. **2027.6:** headcount starts falling, half a year after demand, through attrition with openings cut.
4. **2029.0:** the budget is restored. `Approval` is back at 1 by 2029.9 and demand within 1% of Base by 2029.6.
5. **2029.4:** openings turn positive. Vacancies follow at 2030.2, the backlog at 2030.25 and onboarding at 2030.1.
6. **2029.8:** headcount reaches its trough (-8.6%), 0.8 years after the window. This is the continuation.
7. **2031.6:** the backlog peaks at +11.1%. Hires peak at 2031.4.
8. **2031.75:** headcount passes Base and peaks at +4.8% in 2032.8, 3.8 years after the window. This is the reversal.
9. **2034.5:** the backlog is 3.7% below Base, so openings and hires drop again. Headcount undershoots by 1.5% in 2036.0.

### B.2 Pent-up work: a conservation check (`pentup.csv`)

All figures are in BFY. The identity is `BL` gap (2040) = sum over steps of dt x (demand gap - completion gap - abandonment gap); its residual is the last row.

| BFY | phase7 Compute shock | phase7 Downturn | phase8 Compute shock | phase8 Downturn | phase8_highadoption Compute shock | phase8_highadoption Downturn |
| --- | --- | --- | --- | --- | --- | --- |
| base_demand_per_year_at_start | 112,518 | 112,518 | 112,268 | 112,268 | 112,302 | 112,302 |
| demand_lost_in_window | 31,595 | 11,808 | 34,044 | 13,799 | 33,408 | 13,248 |
| demand_lost_after_window | 4,815 | 1,954 | 5,340 | 2,590 | 5,119 | 2,299 |
| demand_excess_after_window | 4,039 | 8.5 | 4,037 | 11 | 4,035 | 9.3 |
| ai_build_lost_in_window | 5,305 | 963 | 5,407 | 1,118 | 5,385 | 1,076 |
| ai_build_excess_after_window | 689 | 0 | 694 | 0.15 | 694 | 0 |
| other_demand_excess_after_window | 3,507 | 8.5 | 3,488 | 11 | 3,490 | 9.3 |
| completion_deficit | 55,410 | 22,550 | 65,568 | 28,633 | 63,002 | 26,955 |
| completion_surplus | 22,837 | 9,246 | 30,394 | 13,001 | 28,692 | 12,098 |
| net_completion_gap | -32,573 | -13,304 | -35,174 | -15,632 | -34,309 | -14,858 |
| net_demand_gap | -32,371 | -13,753 | -35,347 | -16,377 | -34,493 | -15,538 |
| abandonment_gap | 0 | 0 | 0 | 0 | 0 | 0 |
| backlog_gap_at_end | -13,641 | -7,224 | -16,037 | -9,242 | -15,497 | -8,707 |
| backlog_gap_max_after | 14,977 | 5,887 | 19,329 | 8,061 | 18,268 | 7,546 |
| backlog_gap_max_year | 2032.19 | 2031.56 | 2032.38 | 2031.62 | 2032.31 | 2031.62 |
| backlog_gap_2040 | 202 | -449 | -174 | -745 | -183 | -680 |
| identity_residual | -7.3e-12 | 0 | -1.1e-11 | -1.2e-11 | -3.3e-11 | -3.7e-11 |

**Is there a stock of deferred or pent-up work?** No. Demand that `Approval` cuts is never created (`consumer.py:213-228`), so nothing deferred is released later.
- **Downturn (`phase8`):** 16,389 BFY is lost for good, 14.6% of a year's Base demand. Recovery creates 11 BFY of new demand (0.01% of a year's).
- **Compute shock (`phase8`):** recovery adds 4,037 BFY (3.6% of a year's demand):
  - 694 BFY is AI-build demand catching up (13% of the 5,407 lost in the window);
  - 3,488 BFY is other demand that rises while consumer AI adoption lags (`AC_mean` -7.1% at 2029.5, back within 1% by 2037.6). About half is in app and data work and half in security, governance, support and end-user work.

**The only work that "waits" is in the backlog.** Completions fall short of Base by 28,633 BFY (Downturn) and exceed it by 13,001 BFY after the window.
- The net completion gap (-15,632) equals the net demand gap (-16,377) less the backlog gap in 2040 (-745); no work is abandoned.
- **So the catch-up is consistent with conservation.** The post-window surplus is work that arrived at the normal rate while staff were short. It is not work that was never deferred.

### B.3 Loop dominance (`loops_Downturn.csv`, `loops_Compute_shock.csv`)

**The design:** each variant is one row of an explicit samples design run through `run_scenarios([None, shock])`, so it has its own Base. "AI off" is a separate run with `ai_on=False`.
- **Rebound ratio:** the peak above Base after the window divided by the trough depth. It separates loops that change how deep the shock goes from loops that change how much the system rings.
- **Peak vs full:** the variant's peak over the full model's.

**Downturn**

| variant | Base committed / budget at start | trough | peak after window (year) | rebound ratio | second swing | peak vs full |
| --- | --- | --- | --- | --- | --- | --- |
| full model | 1.000 | -8.6% | +4.8% (2032.81) | 0.56 | -1.5% | 1.00 |
| sourcing frozen (FreezeSourcing 1) | 1.016 | -9.5% | +6.5% (2032.94) | 0.68 | -1.8% | 1.34 |
| wages exogenous (WagesEndogenous 0) | 1.007 | -9.3% | +5.2% (2032.88) | 0.56 | -1.6% | 1.07 |
| no reinvestment (ReinvestFrac 0) | 1.009 | -10.1% | +6.2% (2033.00) | 0.61 | -1.9% | 1.28 |
| no AI build/run demand (BuildRate, RunRate 0) | 0.981 | -6.5% | +3.5% (2032.69) | 0.54 | -1.2% | 0.72 |
| AI cost does not move adoption (CostAdoptElast 0) | 0.994 | -7.9% | +4.4% (2032.75) | 0.55 | -1.5% | 0.91 |
| approval loop fast (BudgetCycle x0.25) | 0.996 | -9.9% | +6.1% (2032.38) | 0.61 | -2.0% | 1.27 |
| approval loop slow (BudgetCycle x4) | 1.001 | -3.3% | +1.4% (2033.62) | 0.41 | -0.5% | 0.28 |
| productivity perception fast (PerceptionTime x0.25) | 0.996 | -8.5% | +4.6% (2032.88) | 0.55 | -1.4% | 0.96 |
| productivity perception slow (PerceptionTime x4) | 1.007 | -9.1% | +5.5% (2032.75) | 0.61 | -1.8% | 1.15 |
| hiring adjustment fast (HireAdjTime x0.25) | 0.998 | -7.6% | +2.6% (2032.38) | 0.34 | -0.6% | 0.53 |
| hiring adjustment slow (HireAdjTime x4) | 0.998 | -9.4% | +8.1% (2034.38) | 0.86 | -3.9% | 1.69 |
| layoffs as slow as hiring (LayoffAdjTime = HireAdjTime) | 1.000 | -8.6% | +4.9% (2032.81) | 0.57 | -1.6% | 1.01 |
| backlog clearance target x0.5 (TargetClearanceTime) | 0.971 | -11.0% | +10.4% (2031.75) | 0.95 | -4.2% | 2.16 |
| backlog clearance target x2 (TargetClearanceTime) | 0.880 | -4.2% | +1.1% (2035.62) | 0.26 | -0.2% | 0.22 |
| fast matching (m x4) | 1.002 | -8.4% | +4.5% (2032.81) | 0.54 | -1.2% | 0.94 |
| slow matching (m x0.25) | 0.964 | -8.0% | +4.6% (2034.94) | 0.57 | -3.0% | 0.95 |
| onboarding fast (OnboardTime x0.25) | 0.993 | -8.1% | +4.0% (2032.56) | 0.50 | -1.1% | 0.83 |
| viability near frozen (ViabilityTime x10) | 1.000 | -8.6% | +4.8% (2032.81) | 0.56 | -1.5% | 0.99 |
| sourcing perception near frozen (SrcPerceptionTime x10) | 0.988 | -7.6% | +4.4% (2032.81) | 0.58 | -1.4% | 0.92 |
| openings step rule (OpeningsContinuous 0) | 1.000 | -7.9% | +4.3% (2032.75) | 0.55 | -1.3% | 0.90 |
| AI off (ai_on=False) | 0.928 | -4.5% | +2.2% (2033.31) | 0.49 | -1.1% | 0.46 |

**Compute shock**

| variant | Base committed / budget at start | trough | peak after window (year) | rebound ratio | second swing | peak vs full |
| --- | --- | --- | --- | --- | --- | --- |
| full model | 1.000 | -16.0% | +12.2% (2033.75) | 0.76 | -2.4% | 1.00 |
| sourcing frozen (FreezeSourcing 1) | 1.016 | -16.5% | +14.6% (2033.94) | 0.88 | -2.6% | 1.20 |
| wages exogenous (WagesEndogenous 0) | 1.007 | -16.5% | +12.6% (2033.88) | 0.76 | -2.4% | 1.03 |
| no reinvestment (ReinvestFrac 0) | 1.009 | -15.4% | +11.7% (2033.75) | 0.76 | -2.3% | 0.96 |
| no AI build/run demand (BuildRate, RunRate 0) | 0.981 | -13.4% | +9.6% (2033.44) | 0.71 | -2.2% | 0.79 |
| AI cost does not move adoption (CostAdoptElast 0) | 0.994 | -15.9% | +10.9% (2033.69) | 0.68 | -2.8% | 0.89 |
| approval loop fast (BudgetCycle x0.25) | 0.996 | -16.7% | +12.7% (2033.31) | 0.76 | -2.6% | 1.04 |
| approval loop slow (BudgetCycle x4) | 1.001 | -8.2% | +4.2% (2034.06) | 0.52 | -0.6% | 0.35 |
| productivity perception fast (PerceptionTime x0.25) | 0.996 | -16.1% | +11.9% (2033.75) | 0.74 | -2.3% | 0.98 |
| productivity perception slow (PerceptionTime x4) | 1.007 | -16.2% | +13.2% (2033.69) | 0.81 | -2.6% | 1.08 |
| hiring adjustment fast (HireAdjTime x0.25) | 0.998 | -14.5% | +7.8% (2033.19) | 0.54 | -0.8% | 0.64 |
| hiring adjustment slow (HireAdjTime x4) | 0.998 | -17.6% | +17.7% (2034.94) | 1.01 | -4.5% | 1.45 |
| layoffs as slow as hiring (LayoffAdjTime = HireAdjTime) | 1.000 | -16.9% | +13.4% (2033.94) | 0.79 | -3.5% | 1.10 |
| backlog clearance target x0.5 (TargetClearanceTime) | 0.971 | -18.3% | +16.5% (2032.88) | 0.90 | -3.4% | 1.36 |
| backlog clearance target x2 (TargetClearanceTime) | 0.880 | -12.2% | +3.6% (2035.69) | 0.29 | -0.3% | 0.29 |
| fast matching (m x4) | 1.002 | -15.8% | +11.8% (2033.62) | 0.75 | -2.1% | 0.97 |
| slow matching (m x0.25) | 0.964 | -19.1% | +13.4% (2036.50) | 0.70 | -5.0% | 1.10 |
| onboarding fast (OnboardTime x0.25) | 0.993 | -15.5% | +10.6% (2033.38) | 0.68 | -1.6% | 0.87 |
| viability near frozen (ViabilityTime x10) | 1.000 | -16.0% | +12.1% (2033.75) | 0.76 | -2.4% | 1.00 |
| sourcing perception near frozen (SrcPerceptionTime x10) | 0.988 | -15.6% | +11.9% (2033.69) | 0.77 | -2.4% | 0.98 |
| openings step rule (OpeningsContinuous 0) | 1.000 | -15.0% | +11.3% (2033.69) | 0.75 | -1.6% | 0.93 |
| AI off (ai_on=False) | 0.928 | -0.0% | +0.0% (2033.25) | - | - | 0.00 |

**The loops fall into three groups:**
- **The ringing loop: backlog staffing with the hiring delay (B13).** It carries the reversal.
  - `TargetClearanceTime` x2 cuts the Downturn peak from +4.8% to +1.1% (rebound ratio 0.56 to 0.26); x0.5 raises it to +10.4% (0.95).
  - `HireAdjTime` x0.25 gives +2.6% (0.34); x4 gives +8.1% (0.86).
  - Faster onboarding (`OnboardTime` x0.25) gives +4.0% (0.50).
  - The Compute shock behaves the same way: 0.29 and 1.01 at `TargetClearanceTime` x2 and `HireAdjTime` x4.
- **The depth loops: the budget and approval chain.** They set how deep the trough is; the rebound ratio moves less.
  - **`BudgetCycle`:** x4 gives a trough of -3.3% and a peak of +1.4% (ratio 0.41); x0.25 gives -9.9% and +6.1%.
  - **Anything that changes Base headroom** changes the depth:
    - AI off: headroom 0.928, trough -4.5%, peak +2.2%;
    - no AI build demand: 0.981, -6.5%, +3.5%;
    - frozen sourcing: 1.016, -9.5%, +6.5%;
    - no reinvestment: 1.009, -10.1%, +6.2%.
  - With AI off, the Compute shock has no effect at all.
- **Little role** (peak within 0.5 points in Downturn):
  - **parameters:** layoff speed (`LayoffAdjTime` = `HireAdjTime`), `ViabilityTime` x10, `SrcPerceptionTime` x10, `PerceptionTime` x0.25, wages (`WagesEndogenous` 0), faster matching (`m` x4) and the Phase 7 openings rule (`OpeningsContinuous` 0, +4.3%);
  - **slower productivity perception (`PerceptionTime` x4):** raises the peak to +5.6%;
  - **slower matching (`m` x0.25):** keeps the size (+4.6%) but delays the peak to 2034.9;
  - **the AI-cost effect on adoption (`CostAdoptElast` 0):** +4.4% in Downturn, and in the Compute shock +10.9% against +12.2% (ratio 0.68 against 0.76). So less AI use carries about a tenth of the Compute shock's overshoot.

**The shares do not add up.** The loops interact, and every variant also moves its own Base.

### B.4 Verdict, step by step

- **Continuation** (the gap keeps its negative sign for 2.6-2.8 years after the window):
  - **real:** the budget cycle delays approval recovery by 0.8-0.9 years after the window;
  - **real:** hiring restarts slowly, so headcount bottoms 0.6-0.9 years after the window. The spec designs this asymmetry: "hiring takes months, layoffs take weeks" (`00_model_spec.md:395`) and "cuts land fully while rebounds lag" (`:418`).
  - **Compute shock only:** a small positive demand continuation from slower consumer AI adoption. It is real in direction (the operator's example of less AI use leaving more human work) and small in size.
- **Reversal** (headcount above Base 2.6-2.8 years after the window):
  - **real:** the backlog builds above Base while staff are short; the conservation check shows this is delayed work, not new work;
  - **real mechanism, size unvalidated:** staffing to the backlog with a hiring delay produces the overshoot. This is loop B13 as the spec defines it (`00_model_spec.md:144`). The size comes from `TargetClearanceTime` and `HireAdjTime`, which no 2024-2026 target constrains on a shock. The rule sizes permanent staff to a temporary backlog bulge with no forecast that the bulge will clear (`workforce.py:94`).
  - **modelling simplification, least supported:** the ringing after the overshoot (an undershoot of 1.0-2.4% around 2036, then a third swing), which leaves the Compute shock not settled by 2040.
- **Not artefacts:**
  - no double counting (the identity closes);
  - no work created on recovery beyond the Compute shock's adoption effects;
  - abandonment never acts;
  - layoffs play no part in the Downturn trough.

## C. Why bigger in phase 8 (Question 3)

**The design:** each step runs on `model="phase7"` with overrides, from 2024, as its own `run_scenarios` call over Base and both shocks.
- **Step 0** is shipped `phase7`.
- **Step 1, the fix:** `OpeningsContinuous` 1.
- **Step 2, the recalibration:** step 1 plus the 11 `phase8` fitted values (`tools/models/phase8/fit.json`) on Phase 7 pricing (`PassThrough` 1, `AnnuityShare` 0, `AnnuityAnchorW` 0).
- **Step 3, pricing:** step 2 with `PassThrough` 0.75, `AnnuityShare` 0.3 and `AnnuityAnchorW` 0.4. It equals `phase8` bit for bit (`checks.csv`).
- **Step 2b** (D1) is recon 09b E's step 2, the separate 32-start refit on Phase 7 pricing (`temp/scratch/09b/fits/d_p7.json`), as a side row against step 1.

| shock | step | Base committed / budget at start | trough | peak after window (year) | rebound ratio | peak change (points) | against |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Compute shock | 0 shipped phase7 | 0.990 | -13.6% | +9.0% (2033.44) | 0.664 | - | - |
| Compute shock | 1 the fix (OpeningsContinuous 1) | 0.990 | -14.6% | +10.0% (2033.50) | 0.684 | +0.98 | 0 shipped phase7 |
| Compute shock | 2 the recalibration (phase8 FIT on Phase 7 pricing) | 0.999 | -15.9% | +12.2% (2033.75) | 0.766 | +2.19 | 1 the fix (OpeningsContinuous 1) |
| Compute shock | 2b recon 09b refit on Phase 7 pricing (side row) | 0.999 | -15.9% | +12.1% (2033.75) | 0.763 | +2.12 | 1 the fix (OpeningsContinuous 1) |
| Compute shock | 3 pricing (full phase8) | 1.000 | -16.0% | +12.2% (2033.75) | 0.763 | -0.02 | 2 the recalibration (phase8 FIT on Phase 7 pricing) |
| Downturn | 0 shipped phase7 | 0.990 | -6.7% | +3.4% (2032.62) | 0.515 | - | - |
| Downturn | 1 the fix (OpeningsContinuous 1) | 0.990 | -7.2% | +3.8% (2032.69) | 0.529 | +0.38 | 0 shipped phase7 |
| Downturn | 2 the recalibration (phase8 FIT on Phase 7 pricing) | 0.999 | -8.5% | +4.8% (2032.81) | 0.566 | +1.00 | 1 the fix (OpeningsContinuous 1) |
| Downturn | 2b recon 09b refit on Phase 7 pricing (side row) | 0.999 | -8.5% | +4.8% (2032.81) | 0.565 | +0.98 | 1 the fix (OpeningsContinuous 1) |
| Downturn | 3 pricing (full phase8) | 1.000 | -8.6% | +4.8% (2032.81) | 0.562 | +0.00 | 2 the recalibration (phase8 FIT on Phase 7 pricing) |

**The 11 fitted values one at a time,** each set alone on step 1 (`steps_fit_oat.csv`). The changes do not add up to step 2.

| shock | value set on step 1 | trough | peak after window | peak change vs step 1 (points) | trough change (points) | rebound ratio change |
| --- | --- | --- | --- | --- | --- | --- |
| Compute shock | step 1 + p = 0.249606 (phase7 0.0437) | -15.1% | +9.8% | -0.20 | -0.50 | -0.036 |
| Compute shock | step 1 + q = 0.0636445 (phase7 0.4948) | -16.6% | +11.9% | +1.89 | -1.98 | +0.032 |
| Compute shock | step 1 + Verif = 0.543594 (phase7 0.4323) | -15.4% | +10.7% | +0.70 | -0.76 | +0.011 |
| Compute shock | step 1 + GCCAppealEnd = 2.69452 (phase7 3.0871) | -14.7% | +10.7% | +0.69 | -0.08 | +0.043 |
| Compute shock | step 1 + JuniorCut = 0.761344 (phase7 0.5833) | -14.7% | +10.4% | +0.37 | -0.12 | +0.020 |
| Compute shock | step 1 + GCCMomentum = 1.89822 (phase7 1.8393) | -14.6% | +10.0% | -0.02 | +0.02 | -0.000 |
| Compute shock | step 1 + qC = 0.236856 (phase7 0.2364) | -14.6% | +10.0% | +0.02 | -0.02 | +0.000 |
| Compute shock | step 1 + pAtt = 0.012256 (phase7 0.0123) | -14.6% | +10.0% | -0.00 | +0.00 | -0.000 |
| Compute shock | step 1 + PriceHorizon = 7 (phase7 7.877) | -14.7% | +10.0% | +0.02 | -0.03 | -0.000 |
| Compute shock | step 1 + SeekerExitRate = 0.485169 (phase7 0.5) | -14.6% | +9.9% | -0.07 | +0.03 | -0.003 |
| Compute shock | step 1 + AICost2024 = 44474.8 (phase7 34796.9) | -14.9% | +10.2% | +0.21 | -0.25 | +0.003 |
| Downturn | step 1 + p = 0.249606 (phase7 0.0437) | -6.4% | +3.3% | -0.49 | +0.80 | -0.011 |
| Downturn | step 1 + q = 0.0636445 (phase7 0.4948) | -9.8% | +5.4% | +1.59 | -2.65 | +0.019 |
| Downturn | step 1 + Verif = 0.543594 (phase7 0.4323) | -8.2% | +4.4% | +0.60 | -1.00 | +0.008 |
| Downturn | step 1 + GCCAppealEnd = 2.69452 (phase7 3.0871) | -7.3% | +4.1% | +0.28 | -0.09 | +0.031 |
| Downturn | step 1 + JuniorCut = 0.761344 (phase7 0.5833) | -7.1% | +3.8% | +0.02 | +0.06 | +0.008 |
| Downturn | step 1 + GCCMomentum = 1.89822 (phase7 1.8393) | -7.2% | +3.8% | -0.02 | +0.03 | -0.000 |
| Downturn | step 1 + qC = 0.236856 (phase7 0.2364) | -7.2% | +3.8% | +0.00 | -0.01 | +0.000 |
| Downturn | step 1 + pAtt = 0.012256 (phase7 0.0123) | -7.2% | +3.8% | -0.00 | +0.00 | -0.000 |
| Downturn | step 1 + PriceHorizon = 7 (phase7 7.877) | -7.2% | +3.8% | +0.02 | -0.03 | -0.000 |
| Downturn | step 1 + SeekerExitRate = 0.485169 (phase7 0.5) | -7.1% | +3.8% | -0.03 | +0.04 | -0.001 |
| Downturn | step 1 + AICost2024 = 44474.8 (phase7 34796.9) | -7.3% | +3.9% | +0.06 | -0.12 | +0.000 |

- **The fix** (continuous openings) adds 0.38 and 0.98 points, through a deeper trough (-0.5 and -1.0 points) and a slightly higher rebound ratio (+0.014 and +0.020). The runs show what changes, not why; the fix changes the Base path too.
- **The recalibration** adds 1.00 and 2.19 points. It deepens the trough by 1.3 points and raises the rebound ratio (+0.037 and +0.081). Base headroom at 2027.0 falls from 0.990 to 0.999.
  - The biggest single contributor is `q`, the delivery-adoption imitation coefficient (0.495 to 0.064, the slower adoption path after 2026). It deepens the Downturn trough by 2.7 points.
  - `Verif` and `GCCAppealEnd` add smaller amounts.
- **Pricing** (`PassThrough`, `AnnuityShare`, `AnnuityAnchorW`) changes the peak by 0.00 and -0.02 points.

## D. Sensitivity (Question 4)

`phase8` Downturn, one parameter at a time, at 0.5x, 0.75x, 1x, 1.5x and 2x its value. All rows are one samples design through `run_scenarios([None, "Downturn"])`, and the 1x row equals the section A run bit for bit (`sensitivity.csv`).

**Parameters and where they act** (catalogue of parameters `parameters.csv`; the file:line is every `pr["name"]` read in `src/aisim/scalar`):

| parameter | phase8 value | role | used at |
| --- | --- | --- | --- |
| `HireAdjTime` | 0.5 | hiring adjustment: closes the staff gap net of vacancies | `labour_market.py:207`, `:213` |
| `LayoffAdjTime` | 0.25 | layoff adjustment | `labour_market.py:211`, `:217` |
| `MinLayoffTime` | 0.25 | layoff rate cap | `labour_market.py:211`, `:217` |
| `OnboardTime` | 0.25 | onboarding delay | `labour_market.py:225` |
| `CancelTime` | 0.25 | vacancy cancellation in surplus | `workforce.py:129` |
| `m` | 4.0 | matching efficiency (time to fill) | `labour_market.py:255` |
| `MinFillTime` | 0.0625 | fill-rate floor (time to fill) | `labour_market.py:260`, `workforce.py:130` |
| `PerceptionTime` | 1.0 | productivity perception (`PerceivedP`) | `integrate.py:102` |
| `BudgetCycle` | 1.0 | spend-ratio smoothing (`SpendRatio`, then `Approval`) | `integrate.py:40` |
| `TargetClearanceTime` | 0.5 | backlog clearance target in desired staff | `workforce.py:94` |
| `SrcPerceptionTime` | 1.5 | sourcing perception | `integrate.py:48` |
| `ViabilityTime` | 2.0 | vendor viability smoothing | `integrate.py:112` |

Time to fill is emergent (`TTFr = V / fills`, `labour_market.py:289`), so `m` and `MinFillTime` stand in for it (D4). The trace in B shows `BudgetCycle` and `TargetClearanceTime` on the path. `PerceptionTime` is off it in Downturn (perceived productivity moves 0.03%) and slightly on it in the Compute shock (0.5%). The sourcing and viability times are side loops.

| parameter | x | value | trough | peak after window (year) | years after end | rebound ratio | gap below 1% from |
| --- | --- | --- | --- | --- | --- | --- | --- |
| HireAdjTime | 0.5 | 0.25 | -8.0% | +3.4% (2032.50) | 3.50 | 0.42 | 2033.88 |
| HireAdjTime | 0.75 | 0.375 | -8.3% | +4.1% (2032.62) | 3.62 | 0.50 | 2036.38 |
| HireAdjTime | 1.0 | 0.5 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| HireAdjTime | 1.5 | 0.75 | -8.9% | +6.0% (2033.19) | 4.19 | 0.67 | not by 2040 |
| HireAdjTime | 2.0 | 1 | -9.2% | +6.7% (2033.44) | 4.44 | 0.74 | not by 2040 |
| LayoffAdjTime | 0.5 | 0.125 | -8.4% | +4.7% (2032.75) | 3.75 | 0.55 | 2036.81 |
| LayoffAdjTime | 0.75 | 0.1875 | -8.5% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| LayoffAdjTime | 1.0 | 0.25 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| LayoffAdjTime | 1.5 | 0.375 | -8.6% | +4.8% (2032.81) | 3.81 | 0.57 | 2036.94 |
| LayoffAdjTime | 2.0 | 0.5 | -8.6% | +4.9% (2032.81) | 3.81 | 0.57 | 2036.94 |
| MinLayoffTime | 0.5 | 0.125 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| MinLayoffTime | 0.75 | 0.1875 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| MinLayoffTime | 1.0 | 0.25 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| MinLayoffTime | 1.5 | 0.375 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| MinLayoffTime | 2.0 | 0.5 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| OnboardTime | 0.5 | 0.125 | -8.2% | +4.3% (2032.62) | 3.62 | 0.52 | 2036.38 |
| OnboardTime | 0.75 | 0.1875 | -8.4% | +4.6% (2032.69) | 3.69 | 0.54 | 2036.62 |
| OnboardTime | 1.0 | 0.25 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| OnboardTime | 1.5 | 0.375 | -8.8% | +5.3% (2033.06) | 4.06 | 0.60 | 2039.56 |
| OnboardTime | 2.0 | 0.5 | -9.0% | +5.6% (2033.31) | 4.31 | 0.62 | not by 2040 |
| CancelTime | 0.5 | 0.125 | -7.9% | +4.2% (2032.69) | 3.69 | 0.53 | 2036.50 |
| CancelTime | 0.75 | 0.1875 | -8.3% | +4.5% (2032.75) | 3.75 | 0.55 | 2036.69 |
| CancelTime | 1.0 | 0.25 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| CancelTime | 1.5 | 0.375 | -8.8% | +5.1% (2032.94) | 3.94 | 0.59 | 2039.31 |
| CancelTime | 2.0 | 0.5 | -8.9% | +5.3% (2033.00) | 4.00 | 0.60 | 2039.56 |
| m | 0.5 | 2 | -9.1% | +6.4% (2033.44) | 4.44 | 0.70 | not by 2040 |
| m | 0.75 | 3 | -8.8% | +5.4% (2032.94) | 3.94 | 0.61 | 2039.44 |
| m | 1.0 | 4 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| m | 1.5 | 6 | -8.4% | +4.5% (2032.81) | 3.81 | 0.54 | 2037.00 |
| m | 2.0 | 8 | -8.4% | +4.5% (2032.81) | 3.81 | 0.54 | 2037.06 |
| MinFillTime | 0.5 | 0.03125 | - | dropped | - | - | - |
| MinFillTime | 0.75 | 0.04688 | - | dropped | - | - | - |
| MinFillTime | 1.0 | 0.0625 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| MinFillTime | 1.5 | 0.09375 | -8.3% | +4.3% (2032.69) | 3.69 | 0.53 | 2036.62 |
| MinFillTime | 2.0 | 0.125 | -8.0% | +4.1% (2032.69) | 3.69 | 0.51 | 2036.38 |
| PerceptionTime | 0.5 | 0.5 | -8.5% | +4.7% (2032.81) | 3.81 | 0.55 | 2036.88 |
| PerceptionTime | 0.75 | 0.75 | -8.5% | +4.7% (2032.81) | 3.81 | 0.56 | 2036.88 |
| PerceptionTime | 1.0 | 1 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| PerceptionTime | 1.5 | 1.5 | -8.7% | +4.9% (2032.81) | 3.81 | 0.57 | 2036.88 |
| PerceptionTime | 2.0 | 2 | -8.8% | +5.1% (2032.81) | 3.81 | 0.58 | 2036.88 |
| BudgetCycle | 0.5 | 0.5 | -9.9% | +5.9% (2032.62) | 3.62 | 0.60 | 2039.06 |
| BudgetCycle | 0.75 | 0.75 | -9.3% | +5.4% (2032.69) | 3.69 | 0.58 | 2036.88 |
| BudgetCycle | 1.0 | 1 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| BudgetCycle | 1.5 | 1.5 | -7.2% | +3.9% (2033.00) | 4.00 | 0.54 | 2036.81 |
| BudgetCycle | 2.0 | 2 | -6.2% | +3.2% (2033.12) | 4.12 | 0.51 | 2036.50 |
| TargetClearanceTime | 0.5 | 0.25 | -11.0% | +10.4% (2031.75) | 2.75 | 0.95 | not by 2040 |
| TargetClearanceTime | 0.75 | 0.375 | -8.0% | +4.3% (2032.31) | 3.31 | 0.54 | 2038.06 |
| TargetClearanceTime | 1.0 | 0.5 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| TargetClearanceTime | 1.5 | 0.75 | -7.8% | +2.3% (2034.25) | 5.25 | 0.29 | 2035.56 |
| TargetClearanceTime | 2.0 | 1 | -4.2% | +1.1% (2035.62) | 6.62 | 0.26 | 2036.19 |
| SrcPerceptionTime | 0.5 | 0.75 | -8.7% | +4.8% (2032.81) | 3.81 | 0.55 | 2036.75 |
| SrcPerceptionTime | 0.75 | 1.125 | -8.7% | +4.8% (2032.81) | 3.81 | 0.55 | 2036.81 |
| SrcPerceptionTime | 1.0 | 1.5 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| SrcPerceptionTime | 1.5 | 2.25 | -8.4% | +4.8% (2032.81) | 3.81 | 0.57 | 2036.94 |
| SrcPerceptionTime | 2.0 | 3 | -8.2% | +4.8% (2032.81) | 3.81 | 0.58 | 2036.94 |
| ViabilityTime | 0.5 | 1 | -8.6% | +4.8% (2032.81) | 3.81 | 0.57 | 2036.88 |
| ViabilityTime | 0.75 | 1.5 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| ViabilityTime | 1.0 | 2 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| ViabilityTime | 1.5 | 3 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |
| ViabilityTime | 2.0 | 4 | -8.6% | +4.8% (2032.81) | 3.81 | 0.56 | 2036.88 |

- **Size:**
  - the hiring-side delays raise the overshoot monotonically: `HireAdjTime` most (3.4% to 6.7%), then `OnboardTime` and `CancelTime`, and slower matching (`m` 0.5x: 6.4%);
  - `TargetClearanceTime` is the strongest lever above 1x (2x: 1.1%);
  - the layoff and perception times hardly matter.
- **Timing:**
  - longer hiring delays push the peak later (`HireAdjTime` 2x: 4.4 years after the window) and stop it settling by 2040;
  - a longer clearance target pushes it much later (6.6 years) but makes it small.
- **Rebound ratio:** it ranges from 0.26 (`TargetClearanceTime` 2x) to 0.95 (0.5x), and from 0.42 to 0.74 across the `HireAdjTime` range.
- **Charts:** `sens_size_*.png` and `sens_timing_*.png`.

## E. Comparison with the real analogue

**What the repo's sources say:** nothing on IT hiring after the 2020 shock, on the 2021-2022 surge or the 2023 cuts, or on hiring after 2009. The relevant passages:
- `reference/prototype/spec/00_model_spec.md:70`: "**Out of scope for v1:** firm-level competition ..., recessions and macro shocks, ...". The model is not built to represent recessions.
- `00_model_spec.md:144`: "B13 Hiring delay | Balancing (delayed) | Backlog up → desired headcount up → vacancies → hires after time-to-fill and onboarding → capacity catches up; long delays cause overshoot and undershoot". (The arrows are as in the spec.)
- `00_model_spec.md:395`: "hiring takes months, layoffs take weeks, and that asymmetry shapes the headcount curves more than the 2040 endpoint."
- `00_model_spec.md:418`: "The asymmetry means cuts land fully while rebounds lag".
- `00_model_spec.md:232`: the macro IT budget driver has the scenarios "Steady; 2-year downturn; boom".
- `01_phase1_build_guide.md:109` and `:117`: test T2 (a demand step) expects "Adjusts to the new level without lasting oscillation", with a "Brief overshoot to about 123,200 in 2030, settles at 120,000 by 2035": "T2's small overshoot is the hiring delay at work, an early glimpse of loop B13".
- `06a_phase6a_build_guide.md:32`: "The budget is a ceiling, not a target. It cuts app development, data and AI project demand only when committed spend exceeds it."
- `06a_phase6a_build_guide.md:260`: test T6, a budget downturn of 0.2 over 2030-2032, gives "back in line by 2035". No overshoot is mentioned.
- `07_phase7_build_guide.md:163`: "**Shocks shift timing more than the end state.** Regulation, a compute shock, a downturn and visa changes all move the 2040 totals by 2% or less."
- **Downturn evidence on pricing only:**
  - `temp/inputs/08-pricing-analogues.md:43`: "In 2009, a large US financial client sought rate cuts of up to 15-20%, ... tier-1 pricing and margins fell 2-4%";
  - `reference/prototype/spec/08_sources.md:82`: only a link title, "highest Q4 layoffs since 2008".

**The comparison:**
- **The model's shape:** after a two-year 15% budget cut, headcount bottoms about 0.8 years after the cut ends. It overshoots Base by 4-5% about 3.8 years after the end, about 3 years after the trough. It undershoots by 1-1.5% around seven years after the end.
- **After the Compute shock:** the overshoot (9-12%) is unwound partly by layoffs about 4.7 years after the shock ends.
- **Against the history the prompt describes:** that pattern (a surge in 2021-2022 after the 2020 shock, then cuts in 2023) has the same qualitative shape: a hiring surge after recovery, then a correction. The repo holds no numbers to compare size or timing.
- **The 2020 shock was not a budget cut:** demand shifted towards digital work rather than falling, so the Downturn scenario is not a like-for-like analogue.

**What would settle it:**
- quarterly headcount, net additions, attrition and utilisation (bench) for the large Indian IT vendors and GCCs over 2019-2024 and 2008-2012;
- US openings, hires and layoffs for computer systems design services (JOLTS) over the same years;
- client IT budget and discretionary-project data for the same years, to size the demand shock.

From these, the measures to compare with the model are:
- the lag from demand recovery to the hiring peak;
- whether headcount rose above its pre-shock trend, and by how much against the depth of the cut;
- whether the excess was unwound by attrition or layoffs.

## The causal chain

All line references are under `src/aisim/scalar/`.

1. **The shock enters.**
   - **Downturn:** `BudgetGrowth` is multiplied by (1 - `BudgetShock`) while `BudgetShockStart <= y < BudgetShockEnd` (`consumer.py:120-124`), and `Budget` follows (`consumer.py:208`). **Real:** budget cuts.
   - **Compute shock:** `AIShockNow` (`finance.py:146`) multiplies the AI cost per unit (`finance.py:151`) and the credit cost (`consumer.py:111`). These raise consumer AI cost (`finance.py:390`) inside services spend (`finance.py:391`), and credit spend (`consumer.py:193`). **Real in direction**, but an assumption in size: AI bills count fully against the IT budget.
2. **Committed spend against budget.** `Committed` is services spend plus seats, credits and cloud (`consumer.py:207`). The stock `SpendRatio` smooths `Committed / Budget` over `BudgetCycle` 1.0 (`integrate.py:40`). **Real:** the annual budget cycle.
3. **Approval cuts demand.** `Approval = clamp(1 - ApprovalSens x max(0, SpendRatio - 1), MinApproval, 1)` (`consumer.py:209`). It scales app and data demand (`consumer.py:213-217`) and AI build demand (`consumer.py:223-227`) into `Demand` (`consumer.py:228`). **Real:** discretionary projects are cut first. Cut demand is lost, not deferred: a simplification that, if anything, understates pent-up demand.
4. **The backlog stock.** `BL += dt x (Demand - Comp - Aband)` (`integrate.py:35`), split to employers by work share (`work.py:63`). **Real:** conservation holds.
5. **Desired staff.** `DesiredE = BLe / (TargetClearanceTime x WorkPerPerson x PerceivedP)` (`workforce.py:94`), with `PerceivedP` smoothed over `PerceptionTime` (`integrate.py:102`). **Real mechanism; its strength is an assumption:** staff respond one for one to the backlog stock, with no forecast that a bulge will clear. This sets the overshoot's size.
6. **Surplus, cancellations, openings and layoffs.**
   - the surplus is `H + O - Desired` (`workforce.py:128`);
   - vacancies are cancelled over `CancelTime` (`workforce.py:129-130`);
   - openings close the gap net of vacancies over `HireAdjTime` (`labour_market.py:207`);
   - layoffs act only when the surplus over `LayoffAdjTime` exceeds natural losses (`labour_market.py:211`; natural losses at `:204`).

   **Real:** hiring freezes first, attrition does the cutting, and the supply line (vacancies and onboarding) is counted.
7. **Hires and onboarding.**
   - matching `m x U^alpha x V^(1 - alpha)` (`labour_market.py:255`, `:258`);
   - the vacancy stock (`integrate.py:62`);
   - onboarding over `OnboardTime` (`integrate.py:63`, `labour_market.py:225`);
   - headcount (`integrate.py:64`).

   **Real:** the hiring delay.
8. **Capacity closes the loop.**
   - capacity from effective staff and productivity (`work.py:66-71`);
   - completion in proportion to backlog (`work.py:73`), which drains `BL` (`integrate.py:35`).

   **Real.** The backlog-to-headcount loop (B13) rings because both stocks lag. **The reversal and the ringing are this loop's dynamics:** the mechanism is real, its size is unvalidated, and the ringing is the least supported part.
9. **Output.** `HeadTotal` is the sum of `H` (`record.py:132`).

## Options for the operator

Each option is factual, without a recommendation.

- **Keep the behaviour and document it as backlog catch-up, not pent-up demand.**
  - **Evidence:**
    - the conservation check: no new work after a Downturn; the catch-up is delayed work;
    - the mechanism is loop B13 as specified (`00_model_spec.md:144`);
    - 07's own reading is that "shocks shift timing more than the end state" (`07_phase7_build_guide.md:163`).
  - **Possible README wording:** "after a temporary shock, headcount falls for about a year after the shock ends, then overshoots Base by 4-12% three to four years later as employers hire to clear the backlog that built up while they were short-staffed, and then oscillates with a smaller amplitude for several years".
- **Change the staffing equation `DesiredE` (`workforce.py:94`).** For example, size staff to a smoothed demand flow plus a backlog correction over its own time constant, so a temporary bulge is cleared without permanent hiring. Smoothing the backlog signal is a variant.
  - **Evidence:** `TargetClearanceTime` x2 already cuts the Downturn rebound ratio from 0.56 to 0.26.
  - **Cost:** the scalar engine must stay bit-identical to the prototype, so this would be an extension switch (like `OpeningsContinuous`) through a slice, with a refit and new phase 8 goldens.
- **Change existing time constants instead.**
  - `HireAdjTime` 0.5x gives +3.4% (Downturn); `TargetClearanceTime` 2x gives +1.1%.
  - **Cost:** both are structural, not fitted. Changing them changes Base, so the calibration would need checking, and no target pins them.
- **Add deferral of approved-out demand** (a pent-up stock in `consumer.py:213-228`).
  - This would add the real-economics channel the model lacks: 16,389 BFY are lost in the `phase8` Downturn.
  - It would make the overshoot larger, not smaller.
- **Reword or drop the shock scenarios in the README.**
  - **Option 1:** describe them as timing scenarios, with the overshoot and ringing stated.
  - **Option 2:** describe the Compute shock as a budget squeeze through AI spend. Its trough is the same without the adoption channel (-15.9% against -16.0%).
  - **Option 3:** report shocks by cumulative headcount-years or by the 2040 level rather than by the peak.
  - **Option 4:** drop them until the staffing rule or the evidence is settled.

## Caveats

- **Deterministic, levers from 2024** (no `perturb_from`), as Q03 A. The windows start in 2027, after the calibration period, so the runs match a perturb from 2026.5 until the window. No noise and no sampling are used.
- **Model units.** Headcount is in model units; demand, backlog and completion in BFY.
- **Recessions are out of scope in the spec** (`00_model_spec.md:70`). The shock scenarios exercise the model's loops; they are not a calibrated recession model, and no target constrains the response to a shock.
- **Adoption path.** The 2024-2026 data identify the early adoption path, not its speed after 2026. That is why every result is shown on both `phase8` and `phase8_highadoption` (README "Models"). The two differ by 1 point or less in the peak (4.4% against 4.8% in Downturn, 11.2% against 12.2% in the Compute shock).
- **Phase 7 caveat.** The `phase7` figures carry Phase 7's caveat: its optimiser stalled on a junior-hiring discontinuity that phase 8 removes.
- **Loop shares are not additive.** Each variant changes its own Base as well as the response. The rebound ratio separates depth from ringing only roughly.
- **The trace-derived quantities** are read from intermediates, not catalogue keys:
  - vacancies as `(avail + cancel) x MinFillTime`;
  - onboarding as onboarding flow x `OnboardTime`;
  - AI build demand as the `AIBuild` field x the sum of `BuildMix`;
  - desired staff, approval and spend pressure, budget-weighted or summed over sectors.
- **Peaks are at 1/16-year resolution,** slightly above Q03's annual figures. Q03's annual numbers reproduce exactly from the annual rows (`checks.csv`).
- **Not a forecast.** The model shows how its mechanisms combine under these assumptions. It does not say what will happen.

## Settings and seeds

- **Code:** commit `207b2902e0aee335d07205b9a7672e38c01996bc`, branch `main`, clean tree.
- **Package versions:** `ai-it-labour-sim` 0.1.0, numpy 2.5.4, pandas 3.0.6, scipy 1.18.1.
- **Platform:** Python 3.12.10 on Windows 11 ARM64. `NPY_DISABLE_CPU_FEATURES` is unset; it does not apply on ARM64.
- **Runs:** dt 1/16, `record_every` 1/16, stop 16 (2040), validation on, auto chunking, no `perturb_from`, no noise, no seeds (no sampling).
- **Scenarios:** `aisim.scenarios.SCENARIOS`:
  - Compute shock: `AIShockMult` 3, `AIShockStart` 2027.0, `AIShockEnd` 2029.5;
  - Downturn: `BudgetShock` 0.15, `BudgetShockStart` 2027.0, `BudgetShockEnd` 2029.0.
- **Designs:**
  - A: `run_scenarios` per model over Base and both shocks, plus nine scalar traced runs;
  - B.3: 22 runs per shock: the full model and 20 parameter variants as one explicit samples design, plus `ai_on=False`;
  - C: 5 steps and 11 one-at-a-time fitted values, each its own `run_scenarios` call on `phase7` with overrides;
  - D: 47 rows (12 parameters x 4 multipliers, with the 2 `MinFillTime` rows below dt dropped by validation, plus 1x).
  - The samples designs are in `results/*_samples.csv`.
- **Invalid runs:** `n_invalid` is 0 in every block.
- **Inputs:**
  - `tools/models/phase8/fit.json`;
  - `temp/scratch/09b/fits/d_p7.json` (step 2b).

  Their sha256 hashes are in `meta.json`.
- **Saved results:** `results/*.npz`. Each result's `meta` is in `meta.json`.
