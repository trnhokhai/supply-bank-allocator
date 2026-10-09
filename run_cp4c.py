"""Inspect provisional site-total forecasts and outstanding CP5 issues."""
import time
import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.forecast_output import build_site_total_forecasts

raw = pd.read_csv("data/sample/distribution_log_clean.csv")
weekly = aggregate_distribution_to_iso_weeks(raw)
origin = weekly["week_start"].max()
start = time.perf_counter()
result = build_site_total_forecasts(weekly, origin, horizon=4)
seconds = time.perf_counter() - start
forecasts, issues = result["forecasts"], result["issues"]
print("=== CP4C PROVISIONAL SITE-TOTAL OUTPUT ===")
print("Origin:", origin.date())
print("Forecast rows:", len(forecasts))
print("Forecast sites:", forecasts["site_id"].nunique())
print("Distinct product-size series:", forecasts[["site_id", "product", "size"]].drop_duplicates().shape[0])
print("Forecast weeks:", forecasts["week_start"].nunique())
print("Rows needing review:", int(forecasts["requires_review"].sum()))
print("Issues:", len(issues))
print("Runtime (seconds):", round(seconds, 2))
print("\nParent methods:")
print(forecasts[["site_id", "method"]].drop_duplicates()["method"].value_counts().to_string())
print("\nFlagged child series:")
print(forecasts.loc[forecasts["requires_review"], ["site_id", "product", "size", "quality_flags"]].drop_duplicates().head(12).to_string(index=False))
print("\nIssues:")
print(issues.to_string(index=False) if not issues.empty else "None")
print("\nFirst eight forecast rows:")
print(forecasts[["site_id", "product", "size", "week_start", "forecast_units", "method", "wape_pct", "parent_wape_pct"]].head(8).to_string(index=False))
print("\nNOTE: provisional forecasts; CP5 and independent Gate 3 accuracy not yet complete.")
