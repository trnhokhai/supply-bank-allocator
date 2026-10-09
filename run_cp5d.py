"""CP5D diagnostic: empirical plausible ranges for the existing CP5C output."""

from time import perf_counter
import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.site_master import build_site_master
from src.forecast_pipeline import build_unified_forecasts
from src.prediction_bands import add_empirical_plausible_ranges

raw = pd.read_csv("data/sample/distribution_log_clean.csv")
survey = pd.read_csv("data/sample/partner_survey.csv")
weekly = aggregate_distribution_to_iso_weeks(raw)
master = build_site_master(raw, survey_df=survey)
origin = weekly["week_start"].max()

start = perf_counter()
output = build_unified_forecasts(weekly, master, origin, horizon=4)
forecast_seconds = perf_counter() - start
ranges = add_empirical_plausible_ranges(output["forecasts"], weekly, origin, horizon=4)
range_seconds = perf_counter() - start - forecast_seconds
results = ranges["forecasts"]

print("=== CHECKPOINT 5D — PLAUSIBLE RANGES ===")
print("Origin:", pd.Timestamp(origin).date())
print("Forecast rows:", len(results))
print("Nominal range coverage:", ranges["coverage"])
print("Forecast seconds:", round(forecast_seconds, 3))
print("Range calculation seconds:", round(range_seconds, 3))
print("Total step seconds:", round(perf_counter() - start, 3))
print("\nRange reasons:\n", results["range_reason"].value_counts(dropna=False).to_string())
print("\nFirst 8 rows:\n", results[[
    "site_id", "product", "size", "week_start", "forecast_units",
    "lower_units", "upper_units", "range_residual_rows", "range_reason"
]].head(8).to_string(index=False))
print("\nSITE_003 / period_cup / one_size (stale candidate):")
print(results.loc[
    results["site_id"].eq("SITE_003")
    & results["product"].eq("period_cup")
    & results["size"].eq("one_size"),
    ["forecast_units", "lower_units", "upper_units", "range_reason"]
].head(1).to_string(index=False))
print("\nIMPORTANT: Provisional ranges, NOT measured 80% coverage or independent Gate 3 WAPE.")
