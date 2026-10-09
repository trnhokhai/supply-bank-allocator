"""CP5C: unified forecast demo; synthetic surveys have no dated provenance."""
from datetime import timedelta

import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.forecast_pipeline import build_unified_forecasts
from src.site_master import build_site_master

raw = pd.read_csv("data/sample/distribution_log_clean.csv")
survey = pd.read_csv("data/sample/partner_survey.csv")
all_weekly = aggregate_distribution_to_iso_weeks(raw)

print("=== HISTORICAL COLD-START TRANSITION (RETROSPECTIVE DEMO) ===")
for site in ["SITE_024", "SITE_025"]:
    site_weeks = sorted(all_weekly.loc[all_weekly["site_id"].eq(site), "week_start"].unique())
    for count in [7, 8]:
        origin = pd.Timestamp(site_weeks[count - 1])
        past_raw = raw.loc[pd.to_datetime(raw["date"]) <= origin + timedelta(days=6)].copy()
        weekly = aggregate_distribution_to_iso_weeks(past_raw)
        master = build_site_master(past_raw, survey_df=survey)
        result = build_unified_forecasts(
            weekly, master, origin,
            allow_undated_survey_for_demo=True,
        )
        target = result["forecasts"].loc[result["forecasts"]["site_id"].eq(site)]
        issues = result["issues"].loc[result["issues"]["site_id"].eq(site)]
        print(f"{site}, {count} observed weeks, origin {origin.date()}:")
        print("  rows:", len(target), "| method:", target["method"].iloc[0] if len(target) else "N/A")
        print("  units/week:", round(target.groupby("week_start")["forecast_units"].sum().iloc[0], 2) if len(target) else "N/A")
        print("  issue:", issues["reason"].iloc[0] if len(issues) else "none")
        if len(target):
            print("  child WAPE N/A:", bool(target["wape_pct"].isna().all()))

print("\n=== CURRENT NETWORK FORECAST ===")
latest = all_weekly["week_start"].max()
master = build_site_master(raw, survey_df=survey)
current = build_unified_forecasts(all_weekly, master, latest)
print("Origin:", latest.date())
print("Coverage:", current["coverage"])
print("Methods:\n", current["forecasts"].groupby("site_id")["method"].first().value_counts().to_string())
print("Issues:\n", current["issues"].to_string(index=False) if len(current["issues"]) else "none")
print("\nIMPORTANT: Undated synthetic survey is only used in retrospective cutoffs with explicit demo opt-in.")
print("Neither survey estimates nor parent WAPE prove child-level Gate 3 accuracy.")
