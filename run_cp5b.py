"""Checkpoint 5B survey cold-start retrospective synthetic demonstration.

IMPORTANT: Sample survey is undated. This is only a scenario to check
mechanics at historical cutoffs, NOT leakage-safe historical accuracy.
"""
import pandas as pd

from src.aggregate import aggregate_distribution_to_iso_weeks
from src.cold_start import build_survey_cold_start
from src.site_master import build_site_master
from datetime import timedelta

raw = pd.read_csv("data/sample/distribution_log_clean.csv")
survey = pd.read_csv("data/sample/partner_survey.csv")

for site in ["SITE_024", "SITE_025"]:
    # Compute cutoffs using only the site-weeks actually observed.
    weekly_full = aggregate_distribution_to_iso_weeks(raw)
    site_weeks = sorted(weekly_full.loc[
        weekly_full["site_id"].eq(site), "week_start"
    ].unique())
    print("\n===", site, "===")
    for count in [7, 8]:
        origin = pd.Timestamp(site_weeks[count - 1])
        # Rebuild BOTH distribution history and master as of this origin.
        past_raw = raw.loc[pd.to_datetime(raw["date"]) <= origin + timedelta(days=6)].copy()
        weekly = aggregate_distribution_to_iso_weeks(past_raw)
        master = build_site_master(past_raw, survey_df=survey)
        result = build_survey_cold_start(
            weekly, master, origin, [site],
            allow_undated_survey_for_demo=True,
        )
        print("Observed weeks:", count, "Origin:", origin.date())
        print("Forecast rows:", len(result["forecasts"]))
        if not result["calibration"].empty:
            c = result["calibration"].iloc[0]
            print("Weekly units:", round(c["site_forecast_units_per_week"], 2))
            print("Peer sites:", int(c["calibration_peer_sites"]))
            print("Mix source:", c["mix_source"])
            print("WAPE:", result["forecasts"]["wape_pct"].iloc[0])
        if not result["issues"].empty:
            print("Issue:", result["issues"].iloc[0]["reason"])

print("\nWARNING: This uses an undated synthetic survey with EXPLICIT demo opt-in.")
print("Do not report retrospective cold-start accuracy or Gate 3 WAPE from these estimates.")
