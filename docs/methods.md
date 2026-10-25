# Methods Note — Forecasting, Allocation and Inventory Alerts (Gates 3–4; Gate 5 Block 1)

Updated October 24, 2026 (Gate 5 Block 1 added; prior historical evidence retained). **Applies to the ChiEAC Diaper & Period Supply Bank Allocator, not a validated measure of unmet community demand.**

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

`python -m pytest -q`, followed by `python run_gate4.py --section scale` (from the root in the pinned `.venv`). In Streamlit, run **Upload → Demo Mode → Clean & Validate → Forecast → Generate forecast → Allocate → Optimize allocation**, keep the worst-partner protection checked, and open CSV exports in a spreadsheet reader. **Historical October 16 instruction:** the final cleanup tests were then pending. A subsequent October 24 Windows full regression reported 346 passed, 17 warnings (including Gate 4 tests); the standalone 80×20 scale audit was not rerun as part of the Gate 5 Block 1 review.

---

## Gate 5 — Inventory Risk and Size-Mismatch Alerts (Block 1; October 24, 2026)

This is a **synthetic/local technical and business validation**, not the entire Gate 5 scenario/purchasing acceptance and not a real supply-bank field study. It reuses canonical Week 3 future forecasts and the Gate 4 vetted cycle supply inputs.

### Coverage formula and boundary semantics

For one canonical SKU `k` over the first `H` consecutive forecast weeks (`1 <= H <= 8`), let `F_k` be the sum of site-level weekly *distribution-proxy* forecasts for that SKU, `D_k = F_k/H` the mean weekly forecast, `Q_k` the counted on-hand snapshot, and `I_k` the **eligible confirmed** in-cycle inbound stock prepared under Decision 037.

- **On-hand WOS** = `Q_k / D_k` for a valid, positive `D_k` and a verified inventory row.
- **Projected-cycle WOS (Brief definition)** = `(Q_k + I_k) / D_k`; this does **not** imply `I_k` is available for immediate picking.
- Strict classifications: **short** if WOS `< short_weeks`; **long** if WOS `> long_weeks`; otherwise **adequate**. Defaults are three and 12 weeks respectively. Users can change the thresholds, with `0 <= short < long`.
- **Complete-horizon planning gap (units)** = `ceil(max(0, F_k - (Q_k + I_k)))` for assessable SKUs. This is not an allocation unmet-need objective, and it is **not** calculated by testing WOS against the short threshold. A SKU may have 3.64 projected WOS (not short under the three-week rule) but a positive four-week supply gap.
- Missing inventory rows are unverified, not zero physical stock; absent/zero/incomplete forecasts make WOS unavailable rather than infinite or proven demand-free. Forecast review metadata and upstream warnings are carried into the display.

Confirmed deliveries count only when dated after the inventory snapshot and through the cycle end; pending, unknown-size, pre-snapshot and after-cycle supply are excluded by the existing preparation contract. An aggregate cycle calculation is **not** a week-by-week shipment schedule or an immediate pick authorization. The separate Week 4 ready-now pick draft remains on-hand-only.

### Inventory-to-distribution size mismatch

Within each product family, the SKU's on-hand share is `100 * Q_k / sum_family(Q)`, and its forecast distribution share is `100 * F_k / sum_family(F)`. Their difference `on_hand_mix_pct - forecast_mix_pct` is the **size-mismatch index in percentage points**. Positive values mean relatively more of that size in counted stock than in forecast distributions; negative values mean relatively less. Suppress the comparison for a family with incomplete size coverage or zero denominators. Keep newborn (`N`) as a categorical diaper size, not a numeric-axis omission.

### Action interpretation and optional cost estimation

Recommendations distinguish on-hand shortfall, threshold-based projected risk and positive *full-cycle* gaps. Verify forecast assumptions, partner sizes, actual receipts and existing commitments before purchasing or promising fulfillment. Eight-week supply-gap CSVs list assessed positive-gap SKUs. Entering a trusted **USD cost per individual unit** permits an illustrative estimated price of `gap units × verified unit cost`; unknown prices remain `N/A` and cannot be assumed free. This is **not** the Week 5 budgeted purchasing optimizer, which has not yet been implemented.

### Reproducible synthetic checks and boundaries

- Local full regression after final Block 1 patch: **346 passed, 17 warnings** (October 24, 2026 Windows `python -m pytest -q` screenshot). Remaining warnings shown were associated with the pinned PuLP/CBC reference tests, not the Alerts timedelta regression. A passing suite does not substitute for live operational checks.
- Four-week Demo Mode: on-hand diaper N/1/2 long; 5/6 short. Size 5 had approximately **1.72 on-hand WOS**, **3.64 projected-cycle WOS**, and a **2,513-unit** complete-cycle supply gap. Both the corrected categorical mix chart and full-gap recommendation appeared in Streamlit.
- Eight-week Demo Mode (September 28–November 22, 2026): 13 positive-gap SKUs, **55,492** total planning-gap units; diaper 4=20,862, 5=16,988, 6=9,414, 7=2,011 (49,275 total). The exported `eight_week_supply_gap_ask.csv` was read and its counts/sums checked. Unit-cost columns were all `N/A` because no prices were entered.
- The eight-week screen showed **0 projected WOS short** under the three-week threshold **and 13 full-eight-week gap SKUs**. This is mathematically consistent. These planning gaps should not be described as independently measured unmet community demand.
- **Still pending:** manual verified-unit-cost entry and arithmetic/CSV check; final Git diff review before committing locally; scenarios, pending-donation what-ifs, new-partner scenarios, budgeted purchasing and sub-15-second scenario benchmarks.

### Verify locally

From the project root in the pinned environment, run `python -m pytest -q`. In Streamlit use **Upload → Demo Mode → Clean & Validate → Forecast (4 or 8 weeks) → Generate Forecast → Alerts → Calculate alerts**. Compare on-hand vs projected-cycle statuses and positive cycle gaps. For eight-week cost verification, enter a realistic *known* unit cost in a test row, confirm the calculated subtotal and CSV, then leave unknown products unpriced. Do not publish synthetic test costs as real purchasing recommendations.

## Gate 5 — What-if Scenario Methods (Block 2; October 24, 2026)

### Baseline and counterfactual calculations

- Original operational plan = persisted, signature-checked Gate 4 Allocate result. Scenario optimized = a re-solve after a single changed assumption. Scenario proportional = independent comparison **under the scenario's new conditions**, not the original plan.
- Supply-only: staff-verified named confirmed donation source scaled within snapshot→cycle arrival window (deterministic half-up rounding per record); or eligible pending arrivals assumed confirmed **only in the scenario copy**. Historical distribution forecast remains unchanged. Future arrivals do not become physical stock or an approved pick list.
- Size-mix: transfer a specified share of one product/size forecast to another within the **same partner-week**. The sum of fractional expected units is conserved. Affected child error/band metadata is invalidated and flagged prospective; no new historical model fit is claimed.
- Integer planning: Gate 4 converts expected cycle totals to integer units using product-size network-total rounding and largest-remainder distribution across sites. Even when the fractional size-mix transfer is conserved, independently rounded totals for the two changed sizes can produce an aggregate **+/-1 integer unit** difference. The separate demand audit records both figures; neither supply nor the solver is modified to conceal it.
- New partner: explicitly acknowledged survey-only or hypothetical partner, based on peer scaling with provisional, not-backtested provenance. Adding a partner changes total planning demand, worst-site fill population and potentially the fairness comparison denominator.
- UI summaries show assumptions **applied in the last run**; audit JSON remains available. Hypothetical on-hand-backed and future-inbound-backed planning allocations are **not** shipping commitments. Export adds a not-pick-authorized status.

### Synthetic evidence and remaining tests

- Existing October 24 manual Streamlit synthetic trials observed no-change consistency, donation -20/-50/+50, pending arrivals, diaper 2→5 size-mix and a prospective shelter partner (peer-sites=5). Observed runtimes were 0.63–0.88 seconds, below Gate 5's **15-second scenario target on those runs**. This does not prove performance for every network scale or configuration.
- Windows before this refinement: **374 passed, 17 warnings**, reported following the dropdown fix. **Final refinement regression remains pending**. Run `python -m pytest -q tests/test_scenarios.py tests/test_scenarios_integration.py` then full `python -m pytest -q`. In Streamlit, verify the submitted assumptions summary, collapsed audit JSON, rounded need disclosure on diaper size-mix 2→5, new-partner provisional metadata, and explicitly hypothetical CSV export.
- Budget-constrained purchasing is a separate Gate 5 Block 3 deliverable; it is **not** claimed as implemented here. Field use and practitioner feedback remain pending.

## Gate 5 — Budgeted Purchasing Optimization (Block 3; October 24, 2026)

### Model and cost validity

Let `p_k` be nonnegative integer purchase units for SKU `k`, `c_k` its positive USD *per individual unit* represented exactly as integer cents, `B` the scenario budget in cents, `u_sk` integer partner/SKU unmet planning units, and `z` worst-site shortfall rate. Joint purchasing solves:

- `sum_k c_k p_k <= B`, with explicit maximum quantities for each priced SKU and no treating a blank or invalid price as free.
- `sum_s (need_sk - u_sk) <= available_cycle_supply_k + p_k`, with site-level verified individual-unit capacity constraints when supplied, original saved fairness minima, and optionally protected original worst-partner fill.
- Primary objective: Gate 4 `sum_sk equity_weight_s * u_sk + penalty_share * total_need * z`. Secondary objective: minimize purchase cost while preserving the primary feasible incumbent to a tight objective tolerance; both solves require acceptable HiGHS relative MIP-gap certificates (`<= 1e-5` within numerical tolerance).
- Purchased units remain **hypothetical plan supply**; neither on-hand physical inventory, receipt status nor approved pick lists are changed.

### Reoptimization, benchmark and measurement provenance

The purchase MILP fixes fairness minima from the saved original Gate 4 result. It returns a certified candidate under those floors. Displayed purchase and shortest-size comparison allocations are then solved again using **current Gate 4 fairness rules**, which may recompute floors. Accordingly, the technical `objective_weighted_unmet` is the *joint candidate* and need not equal the `Equity-weighted unmet` in the displayed reoptimized Gate 4 result (observed 49,593.25 versus 50,285.75). Do not claim global purchasing optimality for a model with recomputed fairness floors without a corresponding proof or formulation.

For both strategies, compute reductions against the **same saved original operational plan**. `physical reduction/$ = (original physical unmet - scenario physical unmet) / actual USD spent`; analogously for equity-weighted reduction/$. Zero spending produces N/A, not infinite performance. The one-shortest-size comparator purchases a single shortest-WOS SKU, subject to its gap, cap and budget, then stops; it can spend materially less than the optimizer. Report actual spend for each and avoid implying equal-spend causal comparison. The Brief's primary observed test is strictly **higher physical reduction per actual dollar**, with the run completing under 15 seconds; weighted per-dollar performance is additional decision evidence.

### Synthetic benchmark outcomes (Windows Streamlit)

- Four weeks, one shortage SKU, $200 at a scenario-only $0.20/unit: both strategies bought 1,000 diaper size-5 units, attained 5 physical units/$ and 7.6475 weighted units/$; a **tie**.
- Eight weeks, 13 shortage SKUs, same scenario $0.20/unit throughout: optimizer spent $3,000 vs comparator $183.40; both attained 5 physical units/$; weighted 7.8097 vs 8.5575. Under these equal prices and full unit effectiveness, a strict physical per-dollar advantage is mathematically impossible.
- Eight weeks, *predeclared heterogeneous retail-reference scenario assumptions* (not vendor quotes), $3,000 budget: optimized 23,130 units of physical planning unmet reduced, **7.7100 physical units/$**, **12.0183 weighted units/$**, worst-site fill ~90.27%; comparator 917 units for $238.42, **3.8470 physical units/$**, **6.5827 weighted units/$**. Streamlit elapsed ~1.64 s, purchasing HiGHS ~0.8573 s, MIP gaps ~2.77e-6 and ~3.33e-6. This demonstrates the stated benchmark **in that synthetic run only**.
- Latest local Windows tests reported: **38 focused passed, 418 full-suite passed, 17 pre-existing PuLP reference deprecation warnings**. Treat as evidence for the tested local code, not a guarantee under different inputs, vendor prices or larger networks.

### Operational exclusions

Unit prices are **assumptions** unless accompanied by verifiable supplier quotes. The present MILP does not implement supplier pack multiples, MOQ, shipping, taxes, delivery calendars or vendor purchase authorization. A future purchased shipment cannot be counted as physical ready-to-pick stock until verified receipt. Reconsider all outcomes if missing/flagged forecasts, case-unit storage capacity or demand provenance materially changes. Keep primary model and post-reoptimization result distinct in export/audit narratives.
