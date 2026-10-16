# Methods Note — Forecasting and Allocation (Gates 3–4)

Updated October 16, 2026. **Applies to the ChiEAC Diaper & Period Supply Bank Allocator, not a validated measure of unmet community demand.**

## Purpose and units

Forecasts estimate *weekly individual units historically distributed* at **site × canonical product × size × ISO week** for a user-selected **4–8-week** horizon. Missing observations are not automatically the same as zero distribution or zero underlying demand. The allocation module consumes these forecast units before physical case-pack rounding.

## Input preparation and missing weeks

Week 2 cleans, normalizes, and aggregates the distribution log to ISO weeks. Interior product-size gaps are imputed as zero only while a site is observed active. Inactive-site gaps and pre-onboarding periods are not filled with zeros. Trailing product-size history after its last recorded week is **not zero-filled**. Flags identify stale/zero-weight forecasts; these require human review.

## Model selection and hierarchy

Candidate portfolio: **Naive, MA4, MA8, SES, damped Holt, optimized Croston, and TSB**. Seasonal naive is not forced on the 78-week synthetic data without the requisite history. Eligible methods compete using **rolling-origin backtests**, four nonoverlapping four-week windows, WAPE primary with signed bias reporting. In candidate selection, only methods backtested on comparable folds compete; high absolute bias is flagged for review rather than silently suppressed. Selection can fall back to a labeled Naive forecast when there are too few valid folds.

Hierarchy comparison on a shared 5,344-observation panel, using a *fixed Naive* forecast for fairness:

| Hierarchy | WAPE |
|---|---:|
| Bottom-up | 21.337% |
| **Site-total top-down** | **18.083%** |
| Site-product top-down | 20.591% |

Site-total won each of the four folds in that experiment. It is the **preferred implementation candidate**, not proof of universal superiority. The current production prototype forecasts site totals and splits across canonical product × size using recent observed mix. **The implementation currently defaults to an eight-week mix lookback**, rather than the Brief's suggested 12-week blend; network blending is not claimed to be completed. Zero-weight or stale variants are flagged and are not interpreted as zero need.

## Survey cold-start

A site with **fewer than eight observed site-level weeks** is treated as cold start when eligible and a suitable survey is available. The estimator uses reported monthly families and calibrated observed weekly distributions from established peer sites, adjusted by agency type and historical product-size mix. Report **`method=survey_based`, WAPE=N/A**, with data-provenance reason. At eight observed weeks, the site becomes eligible for history-based forecasts (not a promise that WAPE can already be computed). Undated synthetic surveys may be used only with explicit retrospective-demo opt-in, **not** as if available historically.

## Plausible ranges

Provisional **nominal 80% plausible ranges** use historical child-level signed residual quantiles and heuristic lead scaling. The observed coverage of these ranges has **not** been independently calibrated to 80%. Historical residual scarcity or stale/zero historical mix means **range=N/A** with a reason. Summing child ranges does not produce a valid network interval.

## Independent Gate 3 evaluation — synthetic sample

`python run_gate3.py` regenerates historical training tables from the raw transaction prefix available at **each historical origin**, without leaking final-period zero-imputation into past training. Survey records without proven prior timestamps are excluded. It evaluates four historical holdouts of four weeks each. Recorded actual entries absent from forecasts would be counted separately; predictions without a recorded actual **are not scored as zeros**.

| Metric | Observed result |
|---|---:|
| Observed-panel network WAPE | **16.8637%** |
| Observed-panel signed bias | **+1.6464%** |
| Full evaluation job | **20.154 seconds** |
| Scored recorded actual rows | **5,398 / 5,398** |
| Forecast rows with no recorded actual | **58** |
| Units forecast on those unobservable rows | **1,648.66** |
| Child variants with complete-fold WAPE | **340 / 341** |
| Child variants without complete-fold WAPE | **1** |

`SITE_019 / period_cup / one_size` has **WAPE=N/A: no_complete_four_week_fold**. Of the 58 forecast rows without recorded actuals, 38 have stale-history/zero-mix flags and 20 lack those specific flags. The reported WAPE is for **observable historical distributions** only; no-actual rows may conceal unmet demand or missing logs. Distribution logs do not identify unconstrained true demand.

The Forecast Page can run this same historical audit **on the current uploaded clean dataset** in the Streamlit session. Child WAPEs from that test are the accuracy of the *historical forecasting pipeline at past cutoffs*, potentially using different parent methods. They are **not** the error of the single future-origin model shown beside them. Parent/site-total method-selection WAPE is kept separately. Never attach the checked-in synthetic CSV's error numbers to someone else's uploads.

## Limitations and decision rules

- The network accuracy benchmark (<20%) and observed job runtime (<60 s) are met on the **synthetic, recorded-observation evaluation**. Gate status additionally depends on usable UI/exports, documentation, and stakeholder acceptance; these results do not imply independent empirical coverage of the nominal 80% bands.
- Historical distributions are a constrained proxy, not measured need. Do not silently interpret stale zeros as no demand, and flag missing logs for manual review.
- Before use by the allocation optimizer, preserve canonical keys, data lineage, method, error provenance, and `requires_review`/`quality_flags`. Do not prematurely round fractional forecast units.
- Repeat evaluation on materially different real datasets; the synthetic result is not a guaranteed performance level.

## Reproduce

From the project root with `(.venv)` active:

```powershell
python -m pytest -q
python run_gate3.py
streamlit run app.py
```

In Streamlit: Upload → Demo Mode → Clean & Validate → Forecast → Generate → Run historical accuracy audit. Confirm 4- and 8-week horizons, site and product-size filters, warning display, and CSV/XLSX exports.

---

## Gate 4 — Equity-aware allocation methods (October 16, 2026)

### Demand and supply contract

Input demand is the **distribution-based forecast** at `site_id × product × size × ISO week`; sum across the selected 1–8 forecast weeks and use network-SKU largest-remainder rounding to individual units. This is *planning need*, not a measured unconstrained community demand estimate. Missing/flagged series remain reviewable. Inventory must be a single dated stock snapshot; only confirmed size-identified incoming quantities arriving after the snapshot and on or before the cycle end are added to *cycle* supply. Pending/unknown-size deliveries are excluded. Pick drafts are derived separately from **on-hand** supply. These do not account for already promised units or physical discrepancies after the snapshot: staff must verify before picking. Storage capacities entered in *cases* remain unenforced until a trusted SKU-aware unit conversion or explicitly verified individual-unit cap exists.

### Optimization model and fairness trade-off

For site `s` and SKU `k`: forecast cycle need `D_sk`, allocated integer units `x_sk`, unmet planning units `u_sk = D_sk - x_sk`, site equity weight `w_s`, SKU supply `A_k`, and `z` maximum site shortfall rate. The objective is:

`min sum_s,k(w_s * u_sk) + lambda * z`, where `lambda = penalty_share * total_network_planning_need`.

Constraints include `0 <= x_sk <= D_sk` integer, `sum_s x_sk <= A_k`, per-site optional verified-unit storage caps, `x_sk >= adjusted_fairness_floor_sk`, and `sum_k u_sk <= z * sum_k D_sk` for sites with positive total need. Scarce SKU-level minimum floors are reduced transparently where requested minima are infeasible or integer rounding would over-allocate. The UI's default baseline protection additionally constrains worst-site shortfall to be **no worse** than the proportional baseline, with the same need, supply and cap constraints. Turning off protection exposes the soft-only trade-off. Equity weights: `1 + alpha * poverty_band_score + beta * priority_population_flag_count`; missing survey equity fields default to weight 1.

### Baseline and reported metrics

Proportional allocation uses a deterministic supply-limited integer apportionment with the same adjusted fairness minima, or a capacity-aware constrained comparator where explicit shared site caps apply. Evaluate (a) equity-weighted planning unmet, (b) *physical* planning unmet units, (c) worst-site fill from aggregate allocated / aggregate need across products, and (d) runtime. A lower weighted unmet score does not mean less total physical shortage. Baseline protection can preserve, but does not promise to improve, worst-site fill.

### Solver implementation and reproducibility

`src/allocation_highs.py` uses SciPy HiGHS mixed-integer optimization, validates allocation integrality and per-SKU/site material constraints after solving, and requires certified relative MIP gap no larger than `1e-5` (within numerical tolerance). PuLP/CBC remains a small-case reference implementation in `src/allocate.py`; both obey the same mathematical restrictions but may choose different equivalent integer allocations. Some high-penalty MILPs can time out; a solve without a satisfactory certificate is not accepted as a successful plan. The sample-scale runtime is **not** the full historical forecasting time.

On **October 16, 2026**, the Windows project environment reported (synthetic only):

| Scenario | Protected weighted unmet | Proportional weighted unmet | Relative improvement | Worst-site fill (optimized / baseline) | Runtime |
|---|---:|---:|---:|---:|---|
| 25-site Demo Mode | ~3,846.4 | ~3,972.6 | **+3.18%** | **98.27% / 98.27%** | UI end-to-end allocation ~0.49 s |
| 80 partners × 20 SKUs (1,600 decision cells) | 96,103.6 | 98,882.9 | **+2.81%** | **79.94% / 79.94%** | complete benchmark worker ~1.048 s; HiGHS ~0.146 s |

The 80×20 report gave certified MIP relative gap ~`1.2e-7`, below the `1e-5` requested bound; measured network demand 498,303 units and available supply 414,296. The benchmark is on a **single fixed seeded stress case**, not a guarantee for arbitrary real data. Streamlit Demo Mode reported 191,137 cycle units allocated, 170,737 ready-now and 20,400 awaiting incoming. In contrast, 25-site soft-only penalty 0.01 yielded **12.22%** weighted improvement but worst-site fill of **93.50%** versus **98.27%** baseline, demonstrating an actual cost-of-fairness trade-off. With protection ON, worst-site fill is unchanged, not strictly increased.

### Known limitations

- Forecasting may underestimate unconstrained need where historical distributions were supply-constrained.
- The synthetic results are not a practitioner pilot, and 22 cycle site/SKU series were flagged for review in the demo; survey case-capacity limitations remain visible.
- Cycle supply may arrive only near the cycle end; there is no intracycle shipping schedule. Ready-now pick lists remain a physical-stock **draft**, not fulfillment authorization.
- PuLP 3.3.2 emits future-API warnings in the reference tests; dependency upgrades need separate review rather than silence-through-filtering.

### Verify locally

`python -m pytest -q`, followed by `python run_gate4.py --section scale` (from the root in the pinned `.venv`). In Streamlit, run **Upload → Demo Mode → Clean & Validate → Forecast → Generate forecast → Allocate → Optimize allocation**, keep the worst-partner protection checked, and open CSV exports in a spreadsheet reader. Current final cleanup tests need to be rerun on the Windows project environment before claiming Gate 4 closeout.
