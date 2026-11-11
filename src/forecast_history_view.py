"""Read-only historical weekly series for the Forecast page.

The function in this module is presentation-only. It never changes forecasts,
method selection, WAPE, allocation, or application session state. Missing
calendar weeks remain NaN, rather than fabricated zero distributions.
"""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd


class ForecastHistoryViewError(ValueError):
    """Invalid history supplied to the display-only timeline."""


def build_historical_window(
    weekly: pd.DataFrame,
    *,
    site_id: str,
    product: str,
    size: str,
    origin_week,
    lookback_weeks: int = 26,
) -> pd.DataFrame:
    """Return the last N calendar weeks for one site/product/size.

    Output has week_start, actual_units, is_imputed_zero, and has_record.
    A calendar week without any recorded/imputed row has actual_units=NaN and
    has_record=False. Those gaps MUST NOT be connected across on a chart.
    Previously imputed zero distribution remains 0 but is explicitly flagged.
    The supplied tables are never mutated.
    """
    if not isinstance(weekly, pd.DataFrame):
        raise ForecastHistoryViewError("Weekly history must be a DataFrame.")
    required = {"site_id", "product", "size", "week_start", "quantity", "is_imputed_zero"}
    missing = required - set(weekly.columns)
    if missing:
        raise ForecastHistoryViewError(f"Missing history columns: {sorted(missing)}")
    if type(lookback_weeks) is not int or not 1 <= lookback_weeks <= 104:
        raise ForecastHistoryViewError("History window must be 1 to 104 whole weeks.")
    try:
        origin = pd.Timestamp(origin_week)
    except (TypeError, ValueError) as exc:
        raise ForecastHistoryViewError("Invalid forecast origin.") from exc
    if pd.isna(origin) or origin.weekday() != 0 or origin != origin.normalize():
        raise ForecastHistoryViewError("Forecast origin must be an ISO-week Monday.")

    start = pd.Timestamp(origin.date() - timedelta(days=7 * (lookback_weeks - 1)))
    subset = weekly.loc[
        weekly["site_id"].eq(site_id)
        & weekly["product"].eq(product)
        & weekly["size"].eq(size),
        ["week_start", "quantity", "is_imputed_zero"],
    ].copy()
    subset["week_start"] = pd.to_datetime(subset["week_start"], errors="coerce")
    if (
        subset["week_start"].isna().any()
        or (subset["week_start"].dt.weekday != 0).any()
        or subset["week_start"].duplicated().any()
    ):
        raise ForecastHistoryViewError("Historical weeks must be unique ISO-week Mondays.")
    subset = subset.loc[subset["week_start"].between(start, origin)].copy()
    if not subset.empty:
        values = pd.to_numeric(subset["quantity"], errors="coerce")
        if values.isna().any() or (~np.isfinite(values.to_numpy(dtype=float))).any() or values.lt(0).any():
            raise ForecastHistoryViewError("Historical distributions must be finite and nonnegative.")
        if subset["is_imputed_zero"].isna().any() or not subset["is_imputed_zero"].isin([True, False]).all():
            raise ForecastHistoryViewError("Historical imputation flags must be Boolean.")
        subset["quantity"] = values.astype(float)
        subset["is_imputed_zero"] = subset["is_imputed_zero"].astype(bool)

    calendar = pd.DataFrame({
        "week_start": pd.date_range(start=start, periods=lookback_weeks, freq="W-MON"),
    })
    view = calendar.merge(
        subset.rename(columns={"quantity": "actual_units"}),
        on="week_start",
        how="left",
        validate="one_to_one",
    )
    view["has_record"] = view["actual_units"].notna()
    view["is_imputed_zero"] = view["is_imputed_zero"].eq(True).astype(bool)
    return view[["week_start", "actual_units", "is_imputed_zero", "has_record"]]
