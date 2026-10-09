"""Gate 3 audit/report integration for the active upload, without disk persistence.

Historical holdout WAPE measures the changing pipeline at prior cutoffs;
it is NOT accuracy of the model chosen for the next forecast origin.
Do not merge static synthetic reports with uploads.
"""
from time import perf_counter

import numpy as np
import pandas as pd

KEY = ["site_id", "product", "size"]


class Gate3ReportingError(ValueError):
    """Raised for incompatible or unsafe audit/report inputs."""


def attach_child_wape(forecasts: pd.DataFrame, per_child: pd.DataFrame) -> pd.DataFrame:
    """Join in-session, independent historical child WAPEs by canonical key.

    Leaves survey-based estimates at N/A. Metadata records which historical
    methods participated: it is NOT the current forecast method's own WAPE.
    Keeps the original forecast quantities, parent WAPE and quality flags.
    """
    if not isinstance(forecasts, pd.DataFrame) or not isinstance(per_child, pd.DataFrame):
        raise Gate3ReportingError("Forecasts and audit results must be DataFrames.")
    required_forecast = set(KEY + ["wape_pct", "wape_reason", "method", "forecast_units"])
    required_report = set(KEY + ["wape_pct", "wape_reason", "evaluated_folds", "methods_used"])
    if required_forecast - set(forecasts.columns) or required_report - set(per_child.columns):
        raise Gate3ReportingError("Missing canonical forecast or historical audit columns.")
    if forecasts[KEY].isna().any().any() or per_child[KEY].isna().any().any():
        raise Gate3ReportingError("Missing site/product/size audit identifiers.")
    if per_child.duplicated(KEY).any():
        raise Gate3ReportingError("Duplicate product-size series in audit report.")
    base = forecasts.copy()
    report = per_child[KEY + ["wape_pct", "wape_reason", "evaluated_folds", "methods_used"]].copy()
    report["wape_pct"] = pd.to_numeric(report["wape_pct"], errors="coerce")
    numeric = report["wape_pct"].dropna().to_numpy(dtype=float)
    if not np.isfinite(numeric).all() or (numeric < 0).any():
        raise Gate3ReportingError("Invalid historical audit WAPE.")
    report = report.rename(columns={
        "wape_pct": "audit_child_wape_pct", "wape_reason": "audit_child_reason",
        "evaluated_folds": "audit_evaluated_folds", "methods_used": "audit_methods_used",
    })
    merged = base.merge(report, on=KEY, how="left", validate="many_to_one", sort=False)
    survey = merged["method"].eq("survey_based")
    has_evidence = merged["audit_child_wape_pct"].notna() & ~survey
    merged["wape_pct"] = np.where(has_evidence, merged["audit_child_wape_pct"], np.nan)
    merged["wape_reason"] = np.where(
        survey,
        "survey_based_no_historical_accuracy",
        np.where(
            has_evidence, "historical_pipeline_asof_four_folds",
            merged["audit_child_reason"].fillna("no_matching_historical_audit"),
        ),
    )
    merged["accuracy_evaluation"] = np.where(
        has_evidence, "historical_pipeline_holdout_not_current_model", "not_available"
    )
    return merged.drop(columns=["audit_child_wape_pct", "audit_child_reason"])


def run_in_memory_audit(raw_clean_distribution: pd.DataFrame, actual_weekly: pd.DataFrame) -> dict:
    """Rebuild as-of historical training from the current cleaned distribution log.

    Surveys have no verified prior timestamps in the project demo, so they
    are excluded from this historical retrospective test. Never persist
    partner uploads to the reports/ folder.
    """
    from src.aggregate import aggregate_distribution_to_iso_weeks
    from src.forecast_pipeline import build_unified_forecasts
    from src.gate3_eval import evaluate_historical_forecasts, raw_prefix_through_completed_week
    from src.site_master import build_site_master

    if not isinstance(raw_clean_distribution, pd.DataFrame) or "date" not in raw_clean_distribution:
        raise Gate3ReportingError("Cleaned Distribution Log (date column) is required.")
    if not isinstance(actual_weekly, pd.DataFrame) or actual_weekly.empty or "week_start" not in actual_weekly:
        raise Gate3ReportingError("A nonempty derived weekly distribution table is required.")

    end = pd.to_datetime(actual_weekly["week_start"], errors="coerce").max()
    if pd.isna(end):
        raise Gate3ReportingError("Cannot identify historical evaluation end.")
    start = perf_counter()

    def predict_as_of(origin, horizon):
        past_raw = raw_prefix_through_completed_week(raw_clean_distribution, origin)
        if past_raw.empty:
            raise Gate3ReportingError("Insufficient history at an earlier evaluation cutoff.")
        asof_weekly = aggregate_distribution_to_iso_weeks(past_raw)
        asof_master = build_site_master(past_raw, survey_df=None)
        return build_unified_forecasts(
            asof_weekly, asof_master, origin, horizon=horizon,
            allow_undated_survey_for_demo=False,
        )

    result = evaluate_historical_forecasts(
        actual_weekly, predict_as_of, end_week=end, folds=4, horizon=4,
    )
    brief = dict(result["summary"])
    brief["full_job_seconds"] = round(perf_counter() - start, 3)
    brief["full_job_under_60s"] = brief["full_job_seconds"] < 60
    # Deliberately do not change gate3_certified; this is a diagnostic.
    return {
        "summary": brief, "per_child": result["per_child"],
        "per_fold": result["per_fold"], "issues": result["issues"],
    }
