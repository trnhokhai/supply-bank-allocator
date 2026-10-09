"""Leakage-safe hierarchical size mixes and forecast disaggregation."""

from datetime import timedelta

import numpy as np
import pandas as pd


class HierarchyError(ValueError):
    """Raised when hierarchical forecasting inputs are unsafe."""


HIERARCHY_PARENTS = {
    "site_total": ["site_id"],
    "site_product": ["site_id", "product"],
}
CHILD_KEYS = ["site_id", "product", "size"]


def historical_size_mix(weekly, origin_week, hierarchy, lookback_weeks=8):
    """Compute disaggregation proportions using ONLY history <= origin.

    Recent positive distributions determine the mix. A parent with no
    recent positive distributions falls back to its pre-origin history.
    Never zero-fill missing site or trailing product-size weeks.
    """
    if hierarchy not in HIERARCHY_PARENTS:
        raise HierarchyError("Unknown hierarchy.")
    if type(lookback_weeks) is not int or lookback_weeks < 1:
        raise HierarchyError("lookback_weeks must be a positive integer.")
    try:
        origin = pd.Timestamp(origin_week)
    except (TypeError, ValueError) as exc:
        raise HierarchyError("Invalid origin week.") from exc
    if pd.isna(origin) or origin.weekday() != 0:
        raise HierarchyError("Origin must be an ISO-week Monday.")

    required = set(CHILD_KEYS + ["week_start", "quantity", "is_imputed_zero"])
    if not required.issubset(weekly.columns):
        raise HierarchyError(f"Missing columns: {sorted(required - set(weekly.columns))}")

    df = weekly.copy()
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    quantities = df["quantity"].to_numpy(dtype=float)
    if (
        df[CHILD_KEYS].isna().any().any()
        or df["week_start"].isna().any()
        or (df["week_start"].dt.weekday != 0).any()
        or df.duplicated(CHILD_KEYS + ["week_start"]).any()
        or not np.isfinite(quantities).all()
        or (quantities < 0).any()
        or df["is_imputed_zero"].isna().any()
        or not df["is_imputed_zero"].isin([True, False]).all()
    ):
        raise HierarchyError("Invalid canonical weekly distribution data.")

    history = df.loc[df["week_start"] <= origin]
    if history.empty:
        raise HierarchyError("No history available before forecast origin.")

    parent = HIERARCHY_PARENTS[hierarchy]
    full = (
        history.groupby(CHILD_KEYS, as_index=False, dropna=False)["quantity"]
        .sum().rename(columns={"quantity": "full_units"})
    )
    start = origin - timedelta(days=7 * (lookback_weeks - 1))
    recent = (
        history.loc[history["week_start"] >= start]
        .groupby(CHILD_KEYS, as_index=False, dropna=False)["quantity"]
        .sum().rename(columns={"quantity": "recent_units"})
    )
    mix = full.merge(recent, on=CHILD_KEYS, how="left", validate="one_to_one")
    mix["recent_units"] = mix["recent_units"].fillna(0.0)
    mix["parent_recent_units"] = mix.groupby(parent)["recent_units"].transform("sum")
    mix["parent_full_units"] = mix.groupby(parent)["full_units"].transform("sum")

    if (mix["parent_full_units"] <= 0).any():
        raise HierarchyError(
            "A hierarchy parent has no positive historical distribution; "
            "its size mix is unavailable."
        )

    use_recent = mix["parent_recent_units"].gt(0)
    mix["weight"] = np.where(
        use_recent,
        mix["recent_units"] / mix["parent_recent_units"].replace(0, np.nan),
        mix["full_units"] / mix["parent_full_units"],
    )
    mix["mix_source"] = np.where(
        use_recent, "recent_observed_distribution", "full_history_fallback"
    )
    mix["origin_week"] = origin
    mix["hierarchy"] = hierarchy
    return mix[CHILD_KEYS + ["weight", "mix_source", "origin_week", "hierarchy"]].sort_values(CHILD_KEYS).reset_index(drop=True)


def disaggregate_parent_forecasts(parent_forecasts, mix, hierarchy):
    """Distribute parent forecasts to canonical product-size children.

    Units remain fractional until Week 4 chooses physical rounding rules.
    """
    if hierarchy not in HIERARCHY_PARENTS:
        raise HierarchyError("Unknown hierarchy.")
    parent = HIERARCHY_PARENTS[hierarchy]
    required_forecast = set(parent + ["week_start", "forecast_units"])
    required_mix = set(CHILD_KEYS + ["weight"])
    if not required_forecast.issubset(parent_forecasts.columns):
        raise HierarchyError("Missing parent forecast columns.")
    if not required_mix.issubset(mix.columns):
        raise HierarchyError("Missing size-mix columns.")
    if parent_forecasts.empty or mix.empty:
        raise HierarchyError("Parent forecasts and size mix cannot be empty.")
    forecasts = parent_forecasts.copy()
    forecasts["week_start"] = pd.to_datetime(forecasts["week_start"], errors="coerce")
    forecasts["forecast_units"] = pd.to_numeric(forecasts["forecast_units"], errors="coerce")
    weights = pd.to_numeric(mix["weight"], errors="coerce")
    if (
        forecasts[parent].isna().any().any()
        or forecasts["week_start"].isna().any()
        or (forecasts["week_start"].dt.weekday != 0).any()
        or forecasts.duplicated(parent + ["week_start"]).any()
        or not np.isfinite(forecasts["forecast_units"].to_numpy(dtype=float)).all()
        or (forecasts["forecast_units"] < 0).any()
        or mix[CHILD_KEYS].isna().any().any()
        or mix.duplicated(CHILD_KEYS).any()
        or not np.isfinite(weights.to_numpy(dtype=float)).all()
        or (weights < 0).any()
    ):
        raise HierarchyError("Invalid parent forecasts or size weights.")

    checked_mix = mix.copy()
    checked_mix["weight"] = weights.astype(float)
    parent_sums = checked_mix.groupby(parent)["weight"].sum()
    if not np.allclose(parent_sums.to_numpy(), 1.0, atol=1e-8):
        raise HierarchyError("Child weights must sum to one per parent.")

    expanded = forecasts.merge(
        checked_mix[parent + [c for c in CHILD_KEYS if c not in parent] + ["weight", "mix_source"]],
        on=parent, how="left", validate="many_to_many", indicator=True,
    )
    if (expanded["_merge"] != "both").any():
        raise HierarchyError("No size mix for at least one parent forecast.")
    expanded["forecast_units"] *= expanded["weight"]
    expected = forecasts.set_index(parent + ["week_start"])["forecast_units"].sort_index()
    actual = expanded.groupby(parent + ["week_start"])["forecast_units"].sum().sort_index()
    if not expected.index.equals(actual.index) or not np.allclose(expected, actual):
        raise HierarchyError("Disaggregation does not conserve forecast units.")
    expanded["hierarchy"] = hierarchy
    return expanded[
        ["week_start"] + CHILD_KEYS + ["forecast_units", "weight", "mix_source", "hierarchy"]
    ].sort_values(["site_id", "product", "size", "week_start"]).reset_index(drop=True)
