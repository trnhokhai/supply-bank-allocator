"""Checkpoint 4B standalone diagnostic on ChiEAC's synthetic sample."""
import time

import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.hierarchy_eval import compare_hierarchies


raw = pd.read_csv("data/sample/distribution_log_clean.csv")
weekly = aggregate_distribution_to_iso_weeks(raw)
end = weekly["week_start"].max()
start = time.perf_counter()
result = compare_hierarchies(weekly, end)
elapsed = time.perf_counter() - start

print("=== CHECKPOINT 4B: FAIR HIERARCHY COMPARISON ===")
print("Backtest end:", end.date())
print("Input series:", weekly.groupby(["site_id", "product", "size"]).ngroups)
print("Comparison model: fixed naive for ALL approaches")
print("Evaluation: 4 rolling folds × 4 calendar weeks")
print("Runtime (s):", round(elapsed, 3))
print("\nApproach comparison on the SAME eligible observations:")
print(result["summary"].round(3).to_string(index=False))
print("\nFold coverage:")
print(result["folds"].to_string(index=False))
all_actual = result["folds"]["actual_rows"].sum()
common_rows = len(result["rows"])
print("\nCommon scored child-week rows:", common_rows)
print("All recorded child-week rows in evaluation window:", int(all_actual))
print("Common panel share of recorded rows:",
      f"{100 * common_rows / all_actual:.1f}%" if all_actual else "N/A")
print("\nIMPORTANT: WAPE here is on a shared observable subset, not the")
print("final network Gate 3 WAPE. Method selection and cold start")
print("are NOT yet included. Do not mark Gate 3 passed from this result.")
