"""Run Gate 3 out-of-sample diagnostic on the repo's cleaned synthetic log.

Does NOT modify trained models or the Streamlit app; writes local reports
under reports/gate3/ for inspection before acceptance/handoff.
"""
import json
from pathlib import Path
from time import perf_counter

import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.site_master import build_site_master
from src.forecast_pipeline import build_unified_forecasts
from src.gate3_eval import (
    evaluate_historical_forecasts, raw_prefix_through_completed_week,
)

SOURCE = Path("data/sample/distribution_log_clean.csv")
OUT = Path("reports/gate3")
full_run_start = perf_counter()
raw = pd.read_csv(SOURCE)
raw["date"] = pd.to_datetime(raw["date"], errors="raise")
actual_weekly = aggregate_distribution_to_iso_weeks(raw)
end = pd.Timestamp(actual_weekly["week_start"].max())


def predict_as_of(origin, horizon):
    """Rebuild both training table and site identities at each cutoff.

    origin is the Monday identifying the LAST COMPLETED historical week.
    Raw transactions through its following Sunday are eligible; all later
    raw transactions are completely unavailable, even for zero-imputation.
    Undated synthetic survey rows are intentionally excluded from the
    independent backtest (no retroactive survey knowledge).
    """
    past_raw = raw_prefix_through_completed_week(raw, origin)
    if past_raw.empty:
        raise RuntimeError("No distribution history before historical origin")
    asof_weekly = aggregate_distribution_to_iso_weeks(past_raw)
    asof_master = build_site_master(past_raw, survey_df=None)
    return build_unified_forecasts(
        asof_weekly, asof_master, origin,
        horizon=horizon, allow_undated_survey_for_demo=False,
    )


results = evaluate_historical_forecasts(
    actual_weekly, predict_as_of, end_week=end, folds=4, horizon=4
)
full_run_seconds = perf_counter() - full_run_start
results["summary"]["full_job_seconds"] = round(full_run_seconds, 3)
results["summary"]["full_job_under_60s"] = full_run_seconds < 60.0
OUT.mkdir(parents=True, exist_ok=True)
for name, filename in [
    ("detail", "observed_panel.csv"),
    ("per_child", "per_child_wape.csv"),
    ("per_site", "per_site_wape.csv"),
    ("per_fold", "per_fold_wape.csv"),
    ("per_method", "per_method_wape.csv"),
    ("issues", "unresolved_issues.csv"),
    ("timings", "runtime_by_fold.csv"),
]:
    results[name].to_csv(OUT / filename, index=False)
(OUT / "gate3_summary.json").write_text(
    json.dumps(results["summary"], indent=2, allow_nan=False), encoding="utf-8"
)
s = results["summary"]
print("=== WEEK 3 GATE 3 — HISTORICAL OUT-OF-SAMPLE DIAGNOSTIC ===")
print("Backtest end:", end.date(), "| outer folds: 4 | horizon: 4 weeks")
print("Core evaluation runtime (seconds):", s["total_elapsed_seconds"])
print("Full job incl. initial aggregation (seconds):", s["full_job_seconds"])
print("Full job under 60 seconds:", s["full_job_under_60s"])
print("Observable-panel network WAPE (%):", s["observable_panel_wape_pct"])
print("Observable-panel network bias (%):", s["observable_panel_bias_pct"])
print("Observable-panel WAPE under 20%:", s["observable_panel_wape_under_20pct"])
print("Recorded actual rows:", s["observed_actual_rows"])
print("Rows scored:", s["scored_rows"])
print("Rows lacking forecasts:", s["unforecasted_actual_rows"])
print("Units in recorded actual rows without forecasts:", s["unforecasted_actual_units"])
print("Recorded actual-unit coverage (%):", s["recorded_actual_unit_coverage_pct"])
print("Forecast rows with no recorded actual:", s["forecast_rows_without_recorded_actual"])
print("Child series with full-fold WAPE:", s["per_child_wape_available"])
print("Child series WAPE N/A:", s["per_child_wape_na"])
print("Open issues:", len(results["issues"]))
print("\n=== PER FOLD ===")
print(results["per_fold"][["fold", "wape_pct", "bias_pct", "scored_rows"]].to_string(index=False))
print("\n=== CHILD SERIES WITHOUT WAPE (FIRST 10) ===")
child = results["per_child"]
print(child.loc[child["wape_pct"].isna(),
    ["site_id", "product", "size", "wape_reason", "unforecasted_actual_rows"]
].head(10).to_string(index=False))
print("\nReport files written to:", OUT.as_posix())
print("NOTE: Gate 3 NOT automatically certified. Review report and missing actual coverage first.")
