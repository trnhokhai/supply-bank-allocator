"""Week 3 CP5D: explicitly provisional 80% empirical plausible ranges.

Calibrate child-grain residuals from four-week rolling-origin evaluations
of the currently selected site-total method and historical size mix.
Never use observations after the forecast origin. Do not treat missing
children as zero demand; avoid fabricated ranges for cold-start or stale
series. This is *not* independent network Gate 3 accuracy certification.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from src.forecast import backtest_forecast
from src.hierarchy import (
    HierarchyError,
    disaggregate_parent_forecasts,
    historical_size_mix,
)

CHILD_KEY = ["site_id", "product", "size"]
FORECAST_KEY = CHILD_KEY + ["week_start"]
BAND_COLUMNS = [
    "lower_units", "upper_units", "range_label", "range_source",
    "range_reason", "range_residual_rows", "range_valid_folds",
]
STALENESS_FLAGS = (
    "trailing_child_history_gap", "zero_historical_mix_weight"
)


class PlausibleRangeError(ValueError):
    """Unsafe forecast / history for empirical ranges."""


def _monday(value):
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise PlausibleRangeError("Invalid forecast origin.") from exc
    if pd.isna(timestamp) or timestamp.tzinfo is not None or timestamp.weekday() != 0:
        raise PlausibleRangeError("Forecast origin must be a timezone-naive Monday.")
    return timestamp.normalize()


def _validate(forecasts, weekly, origin, horizon):
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise PlausibleRangeError("Horizon must be 4 to 8 calendar weeks.")
    if not isinstance(forecasts, pd.DataFrame) or not isinstance(weekly, pd.DataFrame):
        raise PlausibleRangeError("Forecasts and history must be DataFrames.")
    need_forecast = set(FORECAST_KEY + [
        "forecast_units", "method", "quality_flags", "wape_pct",
        "wape_reason", "parent_wape_pct", "origin_week",
    ])
    need_weekly = set(FORECAST_KEY + ["quantity", "is_imputed_zero"])
    if need_forecast - set(forecasts.columns):
        raise PlausibleRangeError("Forecast table is missing CP5C contract columns.")
    if need_weekly - set(weekly.columns):
        raise PlausibleRangeError("Weekly history is missing canonical columns.")

    out = forecasts.copy()
    wk = weekly.copy()
    out["week_start"] = pd.to_datetime(out["week_start"], errors="coerce")
    out["origin_week"] = pd.to_datetime(out["origin_week"], errors="coerce")
    wk["week_start"] = pd.to_datetime(wk["week_start"], errors="coerce")
    wk["quantity"] = pd.to_numeric(wk["quantity"], errors="coerce")
    out["forecast_units"] = pd.to_numeric(out["forecast_units"], errors="coerce")
    if (
        out[FORECAST_KEY + ["origin_week", "method"]].isna().any().any()
        or wk[FORECAST_KEY].isna().any().any()
        or out.duplicated(FORECAST_KEY).any()
        or wk.duplicated(FORECAST_KEY).any()
        or (out["origin_week"] != origin).any()
        or (out["week_start"].dt.weekday != 0).any()
        or (wk["week_start"].dt.weekday != 0).any()
        or not np.isfinite(out["forecast_units"].to_numpy(dtype=float)).all()
        or not np.isfinite(wk["quantity"].to_numpy(dtype=float)).all()
        or out["forecast_units"].lt(0).any()
        or wk["quantity"].lt(0).any()
    ):
        raise PlausibleRangeError("Invalid canonical history or forecast table.")
    expected = pd.date_range(origin + timedelta(days=7), periods=horizon, freq="W-MON")
    if not out.empty and not out["week_start"].isin(expected).all():
        raise PlausibleRangeError("Forecast weeks must fall inside the selected horizon.")
    out["quality_flags"] = out["quality_flags"].fillna("").astype(str)
    return out, wk.loc[wk["week_start"] <= origin].copy()


def _site_child_residuals(site_history, method, origin, folds):
    """Evaluate final-choice parent method at older rolling origins.

    IMPORTANT: the method was selected using more recent data. The derived
    residuals can estimate provisional uncertainty, but MUST NOT be used
    as an independent, nested model-selection Gate 3 WAPE claim.
    """
    parent = (
        site_history.groupby(["site_id", "week_start"], as_index=False)
        ["quantity"].sum().sort_values("week_start").reset_index(drop=True)
    )
    parent["product"] = "__site_total__"
    parent["size"] = "__all__"
    parent["is_imputed_zero"] = False
    evaluated = backtest_forecast(parent, method, origin, folds=folds)
    if evaluated.empty:
        return pd.DataFrame(columns=CHILD_KEY + ["fold", "residual", "actual_units"])

    chunks = []
    for fold, part in evaluated.groupby("fold", sort=True):
        fold_origin = pd.Timestamp(part["origin_week"].iloc[0])
        fold_history = site_history.loc[site_history["week_start"] <= fold_origin]
        if fold_history.empty:
            continue
        try:
            mix = historical_size_mix(fold_history, fold_origin, "site_total")
            parent_predictions = part[["week_start", "forecast_units"]].copy()
            parent_predictions["site_id"] = site_history["site_id"].iloc[0]
            predicted = disaggregate_parent_forecasts(
                parent_predictions[["site_id", "week_start", "forecast_units"]],
                mix, "site_total",
            )
        except HierarchyError:
            continue
        actual = site_history.loc[
            site_history["week_start"].isin(part["week_start"]),
            CHILD_KEY + ["week_start", "quantity"],
        ].rename(columns={"quantity": "actual_units"})
        # Inner join is intentional. Absent child-week record != true zero.
        matched = actual.merge(
            predicted[FORECAST_KEY + ["forecast_units"]],
            on=FORECAST_KEY, how="inner", validate="one_to_one",
        )
        if matched.empty:
            continue
        matched["residual"] = matched["actual_units"] - matched["forecast_units"]
        matched["fold"] = int(fold)
        chunks.append(matched[CHILD_KEY + ["fold", "residual", "actual_units"]])
    if not chunks:
        return pd.DataFrame(columns=CHILD_KEY + ["fold", "residual", "actual_units"])
    return pd.concat(chunks, ignore_index=True)


def add_empirical_plausible_ranges(
    forecasts,
    weekly,
    origin_week,
    horizon=4,
    folds=4,
    min_residual_rows=8,
    min_valid_folds=2,
):
    """Add nominal 80% empirical child-level plausible ranges and diagnostics.

    Signed residual 10th/90th empirical quantiles are pooled over valid
    four-week fold horizons, then expanded for leads 5..8 via sqrt(lead/4).
    Quantile+scaling is heuristic, NOT validated 80% predictive coverage.

    Returns {'forecasts', 'residuals', 'coverage'}; all original fields
    including site-level parent_wape_pct and child wape_pct are preserved.
    No fabricated child WAPE, zero demand, or range for survey/stale data.
    """
    origin = _monday(origin_week)
    if (type(folds) is not int or folds < 1
            or type(min_residual_rows) is not int or min_residual_rows < 4
            or type(min_valid_folds) is not int or not 1 <= min_valid_folds <= folds):
        raise PlausibleRangeError("Invalid empirical calibration requirements.")
    out, past = _validate(forecasts, weekly, origin, horizon)
    for field in BAND_COLUMNS:
        out[field] = np.nan if field in (
            "lower_units", "upper_units", "range_residual_rows", "range_valid_folds"
        ) else ""
    out["range_label"] = "N/A"
    out["range_source"] = "not_available"
    out["range_reason"] = "insufficient_backtest_residual_evidence"
    out["range_residual_rows"] = 0
    out["range_valid_folds"] = 0
    if out.empty:
        return {"forecasts": out, "residuals": pd.DataFrame(),
                "coverage": {"forecast_rows": 0, "range_rows": 0,
                             "range_unavailable_rows": 0}}

    all_residuals = []
    for site_id, site_forecasts in out.groupby("site_id", sort=True):
        methods = site_forecasts["method"].unique()
        if len(methods) != 1:
            raise PlausibleRangeError("One site must use one parent method per origin.")
        method = methods[0]
        site_mask = out["site_id"].eq(site_id)
        if method == "survey_based":
            out.loc[site_mask, "range_reason"] = "survey_based_no_independent_residuals"
            continue
        site_history = past.loc[past["site_id"].eq(site_id)].copy()
        if site_history.empty:
            out.loc[site_mask, "range_reason"] = "no_historical_site_activity"
            continue
        residuals = _site_child_residuals(site_history, method, origin, folds)
        if not residuals.empty:
            all_residuals.append(residuals)
        for idx in site_forecasts.index:
            row = out.loc[idx]
            if any(flag in row["quality_flags"] for flag in STALENESS_FLAGS):
                out.at[idx, "range_reason"] = "stale_or_zero_weight_child_requires_review"
                continue
            if residuals.empty:
                continue
            relevant = residuals.loc[
                residuals["product"].eq(row["product"])
                & residuals["size"].eq(row["size"])
            ]
            n = len(relevant)
            valid = int(relevant["fold"].nunique())
            out.at[idx, "range_residual_rows"] = int(n)
            out.at[idx, "range_valid_folds"] = valid
            if n < min_residual_rows or valid < min_valid_folds:
                continue
            signed_errors = relevant["residual"].to_numpy(dtype=float)
            low_error, high_error = np.quantile(signed_errors, [0.10, 0.90])
            lead = int((row["week_start"] - origin).days // 7)
            scale = max(1.0, float(np.sqrt(lead / 4.0)))
            point = float(row["forecast_units"])
            out.at[idx, "lower_units"] = max(0.0, point + min(0.0, float(low_error) * scale))
            out.at[idx, "upper_units"] = max(point, point + max(0.0, float(high_error) * scale))
            out.at[idx, "range_label"] = "80% plausible range (provisional)"
            out.at[idx, "range_source"] = "selected_parent_method_child_residual_quantiles"
            out.at[idx, "range_reason"] = "nominal_not_coverage_validated"

    pooled = pd.concat(all_residuals, ignore_index=True) if all_residuals else pd.DataFrame(
        columns=CHILD_KEY + ["fold", "residual", "actual_units"]
    )
    # No changes to forecast point values or original WAPE metadata.
    return {
        "forecasts": out,
        "residuals": pooled,
        "coverage": {
            "forecast_rows": int(len(out)),
            "range_rows": int(out["lower_units"].notna().sum()),
            "range_unavailable_rows": int(out["lower_units"].isna().sum()),
            "range_available_child_series": int(
                out.loc[out["lower_units"].notna(), CHILD_KEY].drop_duplicates().shape[0]
            ),
            "range_unavailable_child_series": int(
                out.loc[out["lower_units"].isna(), CHILD_KEY].drop_duplicates().shape[0]
            ),
        },
    }
