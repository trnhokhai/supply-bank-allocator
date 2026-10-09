# Methods Note — Forecasting (Week 3 / Gate 3)

Updated October 9, 2026. **Applies to the ChiEAC Diaper & Period Supply Bank Allocator, not a validated measure of unmet community demand.**

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
