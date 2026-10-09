"""Week 3 CP5C: unified historical + survey cold-start forecast routing.

Do not confuse a site-level backtest WAPE with child-level accuracy. The
survey estimator is only an explicitly dated (or clearly demo-opted-in)
proxy, NOT proof of demand or an independently backtested forecast.
"""

import numpy as np
import pandas as pd

from src.cold_start import build_survey_cold_start
from src.forecast_output import OUTPUT_COLUMNS, build_site_total_forecasts


class ForecastPipelineError(ValueError):
    """Raised if unified forecast output would be misleading or unsafe."""


ISSUE_COLUMNS = ["site_id", "reason", "detail"]
KEY = ["site_id", "product", "size", "week_start"]


def _origin(value):
    try:
        origin = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ForecastPipelineError("Invalid forecast origin.") from exc
    if pd.isna(origin) or origin.tzinfo is not None or origin.weekday() != 0:
        raise ForecastPipelineError("Origin must be a timezone-naive ISO Monday.")
    return origin.normalize()


def build_unified_forecasts(
    weekly,
    site_master,
    origin_week,
    horizon=4,
    allow_undated_survey_for_demo=False,
):
    """One canonical forecast table for historical and survey-based sites.

    Sites with 8+ observed site-weeks are routed to CP4C's historical
    site-total hierarchy. Sites with 0..7 weeks are routed to CP5B's
    survey estimator *only* if currently observed or survey-only; an
    inactive partner is not treated as a new partner. Unresolved sites
    are returned as issues, rather than silently forecast as zero.

    Historical cutoffs with undated synthetic survey data require an
    explicit demo flag and remain flagged as retrospective assumptions.
    """
    origin = _origin(origin_week)
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise ForecastPipelineError("Horizon must be 4..8 whole weeks.")
    if type(allow_undated_survey_for_demo) is not bool:
        raise ForecastPipelineError("Demo opt-in must be boolean.")
    if not isinstance(weekly, pd.DataFrame) or not isinstance(site_master, pd.DataFrame):
        raise ForecastPipelineError("Weekly history and site master must be DataFrames.")
    required = {"site_id", "week_start"}
    if not required.issubset(weekly.columns) or "site_id" not in site_master.columns:
        raise ForecastPipelineError("Missing site or calendar identifiers.")
    if site_master["site_id"].isna().any() or site_master["site_id"].duplicated().any():
        raise ForecastPipelineError("Site master has missing or duplicate site IDs.")

    historical = build_site_total_forecasts(weekly, origin, horizon=horizon)
    historical_forecasts = historical["forecasts"]
    historical_issues = historical["issues"]

    # Only past-to-origin rows can affect eligibility. Never count weeks
    # after origin or require product-size positive units for site history.
    dates = pd.to_datetime(weekly["week_start"], errors="coerce")
    if dates.isna().any():
        raise ForecastPipelineError("Invalid week_start in weekly history.")
    past = weekly.loc[dates <= origin].copy()
    past["week_start"] = dates.loc[dates <= origin]
    counts = past.groupby("site_id")["week_start"].nunique().to_dict()
    latest = past.groupby("site_id")["week_start"].max().to_dict()

    cold_targets = [
        site_id
        for site_id in site_master["site_id"]
        if int(counts.get(site_id, 0)) < 8
        and (
            int(counts.get(site_id, 0)) == 0
            or latest[site_id] == origin
        )
    ]

    if cold_targets:
        cold = build_survey_cold_start(
            weekly,
            site_master,
            origin,
            cold_targets,
            horizon=horizon,
            allow_undated_survey_for_demo=allow_undated_survey_for_demo,
        )
        survey_forecasts = cold["forecasts"]
        cold_issues = cold["issues"]
        calibration = cold["calibration"]
    else:
        survey_forecasts = pd.DataFrame(columns=OUTPUT_COLUMNS)
        cold_issues = pd.DataFrame(columns=ISSUE_COLUMNS)
        calibration = pd.DataFrame()

    # Replace generic CP4C cold-start issue with CP5B's specific result.
    # Keep all inactivity / missing-history / mix failures visible.
    issues = historical_issues.loc[
        ~(
            historical_issues["site_id"].isin(cold_targets)
            & historical_issues["reason"].eq("site_cold_start")
        )
    ].copy()
    issues = pd.concat([issues, cold_issues], ignore_index=True)

    frames = [f for f in (historical_forecasts, survey_forecasts) if not f.empty]
    output = (
        pd.concat(frames, ignore_index=True)
        if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )
    if not output.empty:
        if not set(OUTPUT_COLUMNS).issubset(output.columns):
            raise ForecastPipelineError("Forecast output schema mismatch.")
        if output[KEY].isna().any().any() or output.duplicated(KEY).any():
            raise ForecastPipelineError("Duplicate or missing canonical forecast keys.")
        amounts = pd.to_numeric(output["forecast_units"], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(amounts).all() or (amounts < 0).any():
            raise ForecastPipelineError("Invalid unified forecast units.")
        output = output[OUTPUT_COLUMNS].sort_values(KEY).reset_index(drop=True)

    historical_sites = int(historical_forecasts["site_id"].nunique()) if not historical_forecasts.empty else 0
    survey_sites = int(survey_forecasts["site_id"].nunique()) if not survey_forecasts.empty else 0
    return {
        "forecasts": output,
        "issues": issues[ISSUE_COLUMNS].reset_index(drop=True),
        "calibration": calibration,
        "coverage": {
            "forecast_rows": int(len(output)),
            "sites_forecast": int(output["site_id"].nunique()) if not output.empty else 0,
            "historical_sites": historical_sites,
            "survey_sites": survey_sites,
            "unresolved_sites": int(issues["site_id"].nunique()),
            "review_rows": int(output["requires_review"].sum()) if not output.empty else 0,
        },
    }
