"""Week 3 CP4C: provisional site-total top-down forecast output contract.

This module stages forecasts for CP5 and the allocation handoff. It does
NOT certify child-level accuracy, cold-start, prediction bands or Gate 3.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from src.forecast import (
    ForecastError,
    forecast_with_method,
    select_forecast_method,
)
from src.hierarchy import (
    HierarchyError,
    disaggregate_parent_forecasts,
    historical_size_mix,
)


OUTPUT_COLUMNS = [
    "site_id", "product", "size", "week_start", "forecast_units",
    "hierarchy", "method", "method_level", "forecast_source",
    "weight", "mix_source", "origin_week", "parent_wape_pct",
    "parent_bias_pct", "parent_backtest_folds", "wape_pct",
    "wape_reason", "quality_flags", "requires_review", "forecast_status",
]
ISSUE_COLUMNS = ["site_id", "reason", "detail"]


class ForecastOutputError(ValueError):
    """Invalid input contract or unsafe forecast-output request."""


def _validate_weekly(weekly, origin):
    required = {
        "site_id", "product", "size", "week_start", "quantity",
        "is_imputed_zero",
    }
    missing = required - set(weekly.columns)
    if missing:
        raise ForecastOutputError(f"Missing columns: {sorted(missing)}")
    if weekly.empty:
        raise ForecastOutputError("Weekly distribution cannot be empty.")

    data = weekly.copy()
    data["week_start"] = pd.to_datetime(data["week_start"], errors="coerce")
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
    values = data["quantity"].to_numpy(dtype=float)
    if (
        data[["site_id", "product", "size", "week_start"]].isna().any().any()
        or data.duplicated(["site_id", "product", "size", "week_start"]).any()
        or (data["week_start"].dt.weekday != 0).any()
        or not np.isfinite(values).all()
        or (values < 0).any()
        or data["is_imputed_zero"].isna().any()
        or not data["is_imputed_zero"].isin([True, False]).all()
    ):
        raise ForecastOutputError("Invalid canonical weekly distribution data.")

    return data.loc[data["week_start"] <= origin].copy()


def build_site_total_forecasts(weekly, origin_week, horizon=4):
    """Build provisional site-total top-down forecasts at canonical child grain.

    Returns {'forecasts': DataFrame, 'issues': DataFrame}.

    Only history through origin is visible. Each active site must have at
    least 8 distinct observed site-weeks (NOT 8 positive weeks per size).
    Newly onboarded or currently inactive sites are returned as issues for
    CP5 cold-start/inactive handling, NEVER zero-filled or silently dropped.

    Method/WAPE are measured at the *site-total* parent level. Per-child
    WAPE remains N/A until child-level evaluation in a subsequent gate.
    A zero mix weight or trailing missing child history is flagged for review
    rather than represented as evidence of zero unconstrained demand.
    """
    try:
        origin = pd.Timestamp(origin_week)
    except (TypeError, ValueError) as exc:
        raise ForecastOutputError("Invalid origin week.") from exc
    if pd.isna(origin) or origin.weekday() != 0:
        raise ForecastOutputError("Origin must be an ISO-week Monday.")
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise ForecastOutputError("Horizon must be 4–8 whole weeks.")

    history = _validate_weekly(weekly, origin)
    if history.empty:
        raise ForecastOutputError("No historical data at or before origin.")

    prediction_weeks = pd.date_range(
        start=origin + timedelta(days=7), periods=horizon, freq="W-MON"
    )
    output_parts = []
    issues = []

    for site_id, child_history in history.groupby("site_id", sort=True):
        observed_weeks = int(child_history["week_start"].nunique())
        last_site_week = child_history["week_start"].max()

        if last_site_week != origin:
            issues.append({
                "site_id": site_id,
                "reason": "site_not_observed_at_origin",
                "detail": "Missing site-level activity at the forecast origin; CP5 review required.",
            })
            continue
        if observed_weeks < 8:
            issues.append({
                "site_id": site_id,
                "reason": "site_cold_start",
                "detail": f"Only {observed_weeks} observed site-weeks; survey-based CP5 forecast required.",
            })
            continue

        parent_history = (
            child_history.groupby(["site_id", "week_start"], as_index=False)["quantity"]
            .sum().sort_values("week_start").reset_index(drop=True)
        )
        # Trusted 'active site-week' aggregation. No missing weeks created.
        parent_history["product"] = "__site_total__"
        parent_history["size"] = "__all__"
        parent_history["is_imputed_zero"] = False

        try:
            selected = select_forecast_method(parent_history, origin)
            method = selected["method"]
            method_fallback = method is None
            if method_fallback:
                # Explicit, unbacktested historical fallback. Never claim a
                # zero WAPE or that this is a certified final forecast.
                method = "naive"

            try:
                parent_units = forecast_with_method(parent_history, method, horizon)
            except ForecastError:
                if method == "naive":
                    raise
                method = "naive"
                method_fallback = True
                parent_units = forecast_with_method(parent_history, method, horizon)

            mix = historical_size_mix(child_history, origin, "site_total")
            parent_forecasts = pd.DataFrame({
                "site_id": site_id,
                "week_start": prediction_weeks,
                "forecast_units": np.asarray(parent_units, dtype=float),
            })
            children = disaggregate_parent_forecasts(
                parent_forecasts, mix, "site_total"
            )

        except (ForecastError, HierarchyError, ValueError) as exc:
            issues.append({
                "site_id": site_id,
                "reason": "forecast_or_mix_unavailable",
                "detail": str(exc),
            })
            continue

        # Preserve source-specific quality metadata for downstream review.
        bounds = child_history.groupby(
            ["site_id", "product", "size"], as_index=False
        )["week_start"].max().rename(columns={"week_start": "last_child_week"})
        children = children.merge(
            bounds, on=["site_id", "product", "size"], how="left",
            validate="many_to_one",
        )
        children["origin_week"] = origin
        children["method"] = method
        children["method_level"] = "site_total"
        children["forecast_source"] = (
            "site_total_provisional_naive" if method_fallback
            else "site_total_historical"
        )
        children["parent_wape_pct"] = (
            np.nan if method_fallback else selected["wape_pct"]
        )
        children["parent_bias_pct"] = (
            np.nan if method_fallback else selected["bias_pct"]
        )
        children["parent_backtest_folds"] = (
            0 if method_fallback else len(selected["compared_folds"])
        )
        children["wape_pct"] = np.nan
        children["wape_reason"] = "child_level_backtesting_pending"
        children["forecast_status"] = "provisional_cp4c"

        # Flags are explanatory; 0 forecast from 0 recent mix is NOT proof
        # of zero demand. CP5 must address stale products and size fallback.
        def flags_for_row(row):
            flags = []
            if row.last_child_week < origin:
                flags.append("trailing_child_history_gap")
            if float(row.weight) == 0:
                flags.append("zero_historical_mix_weight")
            if method_fallback:
                flags.append("unbacktested_parent_naive_fallback")
            elif selected.get("bias_flag"):
                flags.append("parent_bias_warning")
            if row.mix_source == "full_history_fallback":
                flags.append("full_history_mix_fallback")
            return ";".join(flags)

        children["quality_flags"] = [
            flags_for_row(row) for row in children.itertuples(index=False)
        ]
        children["requires_review"] = children["quality_flags"].ne("")
        output_parts.append(children[OUTPUT_COLUMNS])

    forecast_df = (
        pd.concat(output_parts, ignore_index=True)
        if output_parts else pd.DataFrame(columns=OUTPUT_COLUMNS)
    )
    issue_df = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    if not forecast_df.empty:
        forecast_df = forecast_df.sort_values(
            ["site_id", "product", "size", "week_start"]
        ).reset_index(drop=True)
        if forecast_df.duplicated(
            ["site_id", "product", "size", "week_start"]
        ).any():
            raise ForecastOutputError("Duplicate forecast output keys.")
        if not np.isfinite(forecast_df["forecast_units"].to_numpy(dtype=float)).all():
            raise ForecastOutputError("Non-finite forecast units.")

    return {"forecasts": forecast_df, "issues": issue_df}
