"""Leakage-safe comparison of three forecast hierarchies.

Checkpoint 4B is a *hierarchy-only experiment*: all three approaches
use the same fixed naive forecasting rule. This isolates the effect of
aggregation/disaggregation. It is not the final seven-model evaluation.
"""

from datetime import timedelta

import numpy as np
import pandas as pd

from src.hierarchy import (
    CHILD_KEYS,
    HIERARCHY_PARENTS,
    HierarchyError,
    disaggregate_parent_forecasts,
    historical_size_mix,
)


APPROACHES = ("bottom_up", "site_total", "site_product")
KEYS = CHILD_KEYS + ["week_start"]


def _naive_four_week_forecast(train, parent_keys, origin, test_weeks):
    """Forecast from the origin week's *observed* parent quantity only.

    Do not backfill absent recent observations or invent zero demand.
    """
    weekly_parent = (
        train.groupby(parent_keys + ["week_start"], as_index=False)["quantity"]
        .sum()
    )
    current = weekly_parent.loc[
        weekly_parent["week_start"].eq(origin), parent_keys + ["quantity"]
    ].copy()
    if current.empty:
        return pd.DataFrame(columns=parent_keys + ["week_start", "forecast_units"])

    future = current.loc[current.index.repeat(len(test_weeks))].reset_index(drop=True)
    future["week_start"] = np.tile(test_weeks.to_numpy(), len(current))
    return future.rename(columns={"quantity": "forecast_units"})[
        parent_keys + ["week_start", "forecast_units"]
    ]


def compare_hierarchies(weekly, evaluation_end_week, folds=4, lookback_weeks=8):
    """Compare bottom-up / site-total / site-product on identical actuals.

    - Four-calendar-week rolling-origin evaluation, by default four folds.
    - Only children with all four observed evaluation weeks are scored.
    - The comparison panel is the intersection of forecast availability
      across all three approaches, so no method benefits from easier dates.
    - Forecast at each origin uses solely data available by that origin.
    - A missing site week or trailing product-size week is NEVER zero-filled.

    Returns a dict with 'rows' (per evaluated child-week) and 'summary'
    (three pooled WAPEs/biases), plus coverage diagnostics. This is not
    an unbiased final network Gate 3 accuracy score or a model-selection
    replacement: the same fixed naive method powers every hierarchy.
    """
    if type(folds) is not int or folds < 1:
        raise HierarchyError("folds must be a positive integer")
    if type(lookback_weeks) is not int or lookback_weeks < 1:
        raise HierarchyError("lookback_weeks must be a positive integer")
    try:
        end = pd.Timestamp(evaluation_end_week)
    except (TypeError, ValueError) as exc:
        raise HierarchyError("Invalid evaluation end week") from exc
    if pd.isna(end) or end.weekday() != 0:
        raise HierarchyError("Evaluation end must be an ISO-week Monday")

    required = set(KEYS + ["quantity", "is_imputed_zero"])
    if not required.issubset(weekly.columns):
        raise HierarchyError(f"Missing columns: {sorted(required - set(weekly.columns))}")
    if weekly.empty:
        raise HierarchyError("Weekly distribution cannot be empty")

    data = weekly.copy()
    data["week_start"] = pd.to_datetime(data["week_start"], errors="coerce")
    data["quantity"] = pd.to_numeric(data["quantity"], errors="coerce")
    if (
        data[KEYS].isna().any().any()
        or data.duplicated(KEYS).any()
        or (data["week_start"].dt.weekday != 0).any()
        or not np.isfinite(data["quantity"].to_numpy(dtype=float)).all()
        or data["quantity"].lt(0).any()
        or data["is_imputed_zero"].isna().any()
        or not data["is_imputed_zero"].isin([True, False]).all()
    ):
        raise HierarchyError("Invalid canonical weekly distribution data")

    all_panels = []
    fold_stats = []

    for fold in range(1, folds + 1):
        test_start = end - timedelta(days=7 * (4 * (folds - fold + 1) - 1))
        origin = test_start - timedelta(days=7)
        test_weeks = pd.date_range(test_start, periods=4, freq="W-MON")
        train = data.loc[data["week_start"] <= origin].copy()
        test = data.loc[data["week_start"].isin(test_weeks)].copy()
        if train.empty or test.empty:
            fold_stats.append({"fold": fold, "actual_rows": int(len(test)), "common_rows": 0})
            continue

        # Require the *same four actual calendar weeks* per evaluated child.
        # A missing row is unknown, not an actual of zero.
        complete_children = (
            test.groupby(CHILD_KEYS, as_index=False)["week_start"].nunique()
        )
        complete_children = complete_children.loc[
            complete_children["week_start"].eq(4), CHILD_KEYS
        ]
        truth = test.merge(complete_children, on=CHILD_KEYS, how="inner")
        truth = truth[KEYS + ["quantity", "is_imputed_zero"]].rename(
            columns={"quantity": "actual_units"}
        )

        forecast_frames = {}
        for approach in APPROACHES:
            parent = CHILD_KEYS if approach == "bottom_up" else HIERARCHY_PARENTS[approach]
            parent_pred = _naive_four_week_forecast(train, parent, origin, test_weeks)
            if approach == "bottom_up":
                predicted = parent_pred
            else:
                if parent_pred.empty:
                    predicted = pd.DataFrame(columns=KEYS + ["forecast_units"])
                else:
                    mix = historical_size_mix(train, origin, approach, lookback_weeks)
                    predicted = disaggregate_parent_forecasts(parent_pred, mix, approach)
            forecast_frames[approach] = predicted[KEYS + ["forecast_units"]].rename(
                columns={"forecast_units": f"{approach}_units"}
            )

        comparable = truth.copy()
        for approach in APPROACHES:
            comparable = comparable.merge(
                forecast_frames[approach], on=KEYS, how="inner", validate="one_to_one"
            )
        comparable["fold"] = fold
        comparable["origin_week"] = origin
        all_panels.append(comparable)
        fold_stats.append({
            "fold": fold,
            "actual_rows": int(len(test)),
            "four_week_child_rows": int(len(truth)),
            "common_rows": int(len(comparable)),
        })

    columns = ["fold", "origin_week"] + KEYS + [
        "actual_units", "is_imputed_zero"
    ] + [f"{x}_units" for x in APPROACHES]
    rows = (
        pd.concat(all_panels, ignore_index=True)[columns]
        if all_panels else pd.DataFrame(columns=columns)
    )
    denominator = float(rows["actual_units"].sum()) if len(rows) else 0.0
    summary = []
    for approach in APPROACHES:
        predicted = rows[f"{approach}_units"].to_numpy(dtype=float)
        actual = rows["actual_units"].to_numpy(dtype=float)
        summary.append({
            "approach": approach,
            "wape_pct": float(100 * np.abs(actual - predicted).sum() / denominator)
            if denominator > 0 else None,
            "bias_pct": float(100 * (predicted - actual).sum() / denominator)
            if denominator > 0 else None,
            "scored_rows": int(len(rows)),
            "scored_folds": int(rows["fold"].nunique()),
        })

    return {"rows": rows, "summary": pd.DataFrame(summary), "folds": pd.DataFrame(fold_stats)}
