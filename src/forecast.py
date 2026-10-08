
"""Baseline forecasting methods for weekly distribution series."""
from datetime import timedelta
import numpy as np
import pandas as pd

from statsforecast.models import (
    AutoETS,
    CrostonOptimized,
    SimpleExponentialSmoothingOptimized,
    TSB,
)

class ForecastError(ValueError):
    """Raised when a forecasting input cannot be used safely."""


def prepare_forecast_series(weekly, site_id, product, size):
    """
    Select a single canonical site/product/size series.

    Use only existing Week 2 rows. Never create missing weeks
    or treat an inactive site period as zero demand.
    """
    required = {
        "site_id", "product", "size",
        "week_start", "quantity", "is_imputed_zero",
    }

    missing = required - set(weekly.columns)
    if missing:
        raise ForecastError(
            f"Missing forecasting columns: {sorted(missing)}"
        )

    selected = weekly.loc[
        weekly["site_id"].eq(site_id)
        & weekly["product"].eq(product)
        & weekly["size"].eq(size)
    ].copy()

    if selected.empty:
        raise ForecastError(
            "No historical rows for the selected series."
        )

    selected["week_start"] = pd.to_datetime(
        selected["week_start"], errors="coerce"
    )

    quantities = pd.to_numeric(
        selected["quantity"], errors="coerce"
    )

    if (
        selected["week_start"].isna().any()
        or (selected["week_start"].dt.weekday != 0).any()
        or selected["week_start"].duplicated().any()
        or quantities.isna().any()
        or not np.isfinite(quantities.to_numpy(dtype=float)).all()
        or (quantities < 0).any()
    ):
        raise ForecastError(
            "Invalid dates, duplicate weeks, or invalid quantities."
        )

    if (
        selected["is_imputed_zero"].isna().any()
        or not selected["is_imputed_zero"].isin(
            [True, False]
        ).all()
    ):
        raise ForecastError("Invalid imputed-zero flags.")

    selected["quantity"] = quantities.astype(float)

    return selected.sort_values("week_start").reset_index(drop=True)


def baseline_forecast(series, method, horizon=4):
    """
    Forecast weekly distribution using a simple baseline.

    Naive: repeat last historical value.
    MA4: mean of last four available rows.
    MA8: mean of last eight available rows.

    Missing site weeks are never inserted or converted to zeros.
    """
    if not isinstance(horizon, int) or not 4 <= horizon <= 8:
        raise ForecastError("Horizon must be an integer from 4 to 8.")

    windows = {"naive": 1, "ma4": 4, "ma8": 8}

    if method not in windows:
        raise ForecastError(f"Unknown forecast method: {method}")

    values = pd.to_numeric(
        series["quantity"], errors="coerce"
    ).to_numpy(dtype=float)

    if (
        len(values) < windows[method]
        or not np.isfinite(values).all()
        or (values < 0).any()
    ):
        raise ForecastError(
            f"{method} requires {windows[method]} "
            "valid historical observations."
        )

    if "week_start" not in series.columns:
        raise ForecastError("Missing week_start column.")

    dates = pd.to_datetime(
        series["week_start"], errors="coerce"
    )

    if (
        dates.isna().any()
        or dates.duplicated().any()
        or not dates.is_monotonic_increasing
        or (dates.dt.weekday != 0).any()
    ):
        raise ForecastError(
            "History must have unique, sorted ISO-week Mondays."
        )

    if method in {"ma4", "ma8"}:
        if not _has_consecutive_tail(
            series, windows[method]
        ):
            raise ForecastError(
                f"{method} requires consecutive calendar weeks."
            )


    forecast_value = float(
        np.mean(values[-windows[method]:])
    )

    return np.full(horizon, forecast_value, dtype=float)



def _has_consecutive_tail(series, weeks):
    """Require consecutive calendar weeks for moving averages."""
    if len(series) < weeks:
        return False

    dates = pd.to_datetime(
        series["week_start"], errors="coerce"
    )

    if dates.isna().any():
        return False

    dates = dates.sort_values().reset_index(drop=True)
    tail = dates.tail(weeks)

    return tail.diff().iloc[1:].dt.days.eq(7).all()


def eligible_baselines(series):
    """Baseline methods eligible for this historical window."""
    methods = []

    if len(series) >= 1:
        methods.append("naive")

    if _has_consecutive_tail(series, 4):
        methods.append("ma4")

    if _has_consecutive_tail(series, 8):
        methods.append("ma8")

    return methods


BACKTEST_COLUMNS = [
    "fold",
    "method",
    "origin_week",
    "week_start",
    "actual_units",
    "forecast_units",
    "is_imputed_zero",
]


def backtest_baseline(
    series,
    method,
    evaluation_end_week,
    folds=4,
):
    """
    Rolling-origin backtest with four-week calendar horizons.

    All series can share the same evaluation_end_week,
    keeping network-level evaluation windows aligned.

    Missing evaluation weeks invalidate a fold.
    No missing site weeks are converted to zero.
    """
    if method not in {"naive", "ma4", "ma8"}:
        raise ForecastError(f"Unknown method: {method}")

    if type(folds) is not int or folds < 1:
        raise ForecastError("folds must be a positive integer.")

    if series.empty:
        raise ForecastError("Cannot backtest an empty series.")

    identifiers = ["site_id", "product", "size"]

    if not set(identifiers).issubset(series.columns):
        raise ForecastError("Missing series identifiers.")

    first = series.iloc[0]

    history = prepare_forecast_series(
        series,
        first["site_id"],
        first["product"],
        first["size"],
    )

    if len(history) != len(series):
        raise ForecastError(
            "Backtesting requires exactly one product-size series."
        )

    try:
        end_week = pd.Timestamp(evaluation_end_week)
    except (TypeError, ValueError):
        raise ForecastError("Invalid evaluation end week.")

    if pd.isna(end_week) or end_week.weekday() != 0:
        raise ForecastError(
            "Evaluation end must be a valid ISO-week Monday."
        )

    records = []
    horizon = 4

    for fold in range(1, folds + 1):
        weeks_before_end = horizon * (folds - fold + 1) - 1

        test_start = end_week - timedelta(
        days=7 * weeks_before_end
        )
        origin = test_start - timedelta(days=7)

        expected_weeks = pd.date_range(
            start=test_start,
            periods=horizon,
            freq="W-MON",
        )

        train = history.loc[
            history["week_start"] <= origin
        ].copy()

        actual = history.loc[
            history["week_start"].isin(expected_weeks)
        ].copy()

        # All four actual calendar weeks must exist.
        if (
            len(actual) != horizon
            or actual["week_start"].tolist()
            != list(expected_weeks)
        ):
            continue

        # Require a valid observation at the forecast origin.
        if train.empty or train["week_start"].iloc[-1] != origin:
            continue

        if method not in eligible_baselines(train):
            continue

        predictions = baseline_forecast(
            train, method, horizon
        )

        for index, actual_row in enumerate(
            actual.itertuples(index=False)
        ):
            records.append({
                "fold": fold,
                "method": method,
                "origin_week": origin,
                "week_start": actual_row.week_start,
                "actual_units": float(actual_row.quantity),
                "forecast_units": float(predictions[index]),
                "is_imputed_zero": bool(
                    actual_row.is_imputed_zero
                ),
            })

    return pd.DataFrame(records, columns=BACKTEST_COLUMNS)


def summarize_backtest(rows, method):
    """
    Pooled WAPE and signed bias across evaluated folds.

    Positive bias means overforecasting.
    Negative bias means underforecasting.
    """
    summary = {
        "method": method,
        "folds_evaluated": int(
            rows["fold"].nunique()
        ),
        "tested_weeks": len(rows),
        "wape_pct": None,
        "bias_pct": None,
        "reason": None,
    }

    if rows.empty:
        summary["reason"] = (
            "No valid four-week backtest folds. "
            "History may be too short or contain gaps."
        )
        return summary

    actual = rows["actual_units"].to_numpy(dtype=float)
    predicted = rows["forecast_units"].to_numpy(dtype=float)

    denominator = float(np.sum(actual))

    if denominator == 0:
        summary["reason"] = (
            "WAPE and percentage bias are undefined "
            "because total actual units equal zero."
        )
        return summary

    summary["wape_pct"] = float(
        100 * np.abs(actual - predicted).sum()
        / denominator
    )

    summary["bias_pct"] = float(
        100 * (predicted - actual).sum()
        / denominator
    )

    return summary


def select_baseline_method(
    series,
    evaluation_end_week,
    folds=4,
    min_valid_folds=2,
):
    """
    Compare baseline methods using identical historical folds.

    WAPE is the primary selection metric.
    Absolute signed bias breaks exact WAPE ties.

    The selected method is provisional until the complete
    Week 3 method portfolio has been evaluated.
    """
    if (
        type(folds) is not int
        or folds < 1
        or type(min_valid_folds) is not int
        or not 1 <= min_valid_folds <= folds
    ):
        raise ForecastError("Invalid fold requirements.")

    methods = ["naive", "ma4", "ma8"]
    eligible_results = {}

    for method in methods:
        rows = backtest_baseline(
            series,
            method,
            evaluation_end_week,
            folds=folds,
        )

        if rows["fold"].nunique() >= min_valid_folds:
            eligible_results[method] = rows

    unavailable = {
        "method": None,
        "wape_pct": None,
        "bias_pct": None,
        "compared_folds": [],
        "scores": [],
        "reason": "Insufficient comparable backtest folds.",
    }

    if not eligible_results:
        return unavailable

    common_folds = sorted(
        int(fold)
        for fold in set.intersection(
            *(
                set(rows["fold"].unique())
                for rows in eligible_results.values()
            )
        )
    )

    if len(common_folds) < min_valid_folds:
        return unavailable

    scores = []

    for method in methods:
        if method not in eligible_results:
            continue

        rows = eligible_results[method]

        comparable_rows = rows.loc[
            rows["fold"].isin(common_folds)
        ].copy()

        metrics = summarize_backtest(
            comparable_rows, method
        )

        scores.append({
            "method": method,
            "wape_pct": metrics["wape_pct"],
            "bias_pct": metrics["bias_pct"],
            "folds_evaluated": metrics["folds_evaluated"],
        })

    ranked = [
        score for score in scores
        if score["wape_pct"] is not None
        and score["bias_pct"] is not None
    ]

    if not ranked:
        return {
            **unavailable,
            "compared_folds": common_folds,
            "scores": scores,
            "reason": (
                "Backtest WAPE is undefined for the "
                "available comparison period."
            ),
        }

    winner = min(
        ranked,
        key=lambda score: (
            score["wape_pct"],
            abs(score["bias_pct"]),
            methods.index(score["method"]),
        ),
    )

    return {
        "method": winner["method"],
        "wape_pct": winner["wape_pct"],
        "bias_pct": winner["bias_pct"],
        "compared_folds": common_folds,
        "scores": scores,
        "reason": None,
    }


# ---------------------------------------------------------
# Checkpoint 3B — Exponential smoothing candidates
# ---------------------------------------------------------

SMOOTHING_MIN_WEEKS = {
    "ses": 8,
    "damped_holt": 12,
}


def _recent_contiguous_history(series):
    """
    Return the most recent uninterrupted site/product/size history.

    A missing calendar week breaks the historical segment.
    Never manufacture zero-demand weeks across inactive gaps.
    """
    if series.empty:
        raise ForecastError("Cannot forecast an empty series.")

    first = series.iloc[0]

    history = prepare_forecast_series(
        series,
        first["site_id"],
        first["product"],
        first["size"],
    )

    if len(history) != len(series):
        raise ForecastError(
            "Forecasting requires exactly one product-size series."
        )

    gaps = history["week_start"].diff().dt.days.ne(7)

    last_start = int(
        np.flatnonzero(gaps.to_numpy())[-1]
    )

    return history.iloc[last_start:].copy()


def eligible_smoothing(series):
    """
    Determine which smoothing models have enough
    consecutive calendar history.
    """
    history = _recent_contiguous_history(series)
    count = len(history)

    return [
        method
        for method, minimum in SMOOTHING_MIN_WEEKS.items()
        if count >= minimum
    ]


def smoothing_forecast(series, method, horizon=4):
    """
    Produce SES or damped Holt forecasts.

    Only the most recent consecutive historical segment
    is fitted. Missing site activity is never filled with zero.

    SES: optimized simple exponential smoothing.
    Damped Holt: additive level/trend with trend damping.
    """
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise ForecastError(
            "Horizon must be an integer from 4 to 8."
        )

    if method not in SMOOTHING_MIN_WEEKS:
        raise ForecastError(
            f"Unknown smoothing method: {method}"
        )

    history = _recent_contiguous_history(series)

    minimum = SMOOTHING_MIN_WEEKS[method]

    if len(history) < minimum:
        raise ForecastError(
            f"{method} requires at least {minimum} "
            "consecutive historical weeks."
        )

    values = history["quantity"].to_numpy(dtype=float)

    try:
        if method == "ses":
            model = SimpleExponentialSmoothingOptimized()
        else:
            model = AutoETS(
                season_length=1,
                model="AAN",
                damped=True,
            )

        result = model.forecast(y=values, h=horizon)

        predictions = np.asarray(
            result["mean"], dtype=float
        )

    except (
        ValueError,
        RuntimeError,
        FloatingPointError,
        OverflowError,
        np.linalg.LinAlgError,
    ) as exc:
        raise ForecastError(
            f"{method} could not fit the historical data: {exc}"
        ) from exc

    if (
        predictions.shape != (horizon,)
        or not np.isfinite(predictions).all()
    ):
        raise ForecastError(
            f"{method} produced invalid forecast values."
        )

    # Physical distribution units cannot be negative.
    return np.maximum(predictions, 0.0)


# ---------------------------------------------------------
# Checkpoint 3B.2 — Intermittent demand candidates
# ---------------------------------------------------------

INTERMITTENT_MIN_WEEKS = 16
INTERMITTENT_ZERO_THRESHOLD = 0.30


def eligible_intermittent(series):
    """
    Eligible when recent contiguous history has:
    - at least 16 weeks;
    - more than 30% zero-distribution weeks;
    - at least two positive observations.

    These are model-eligibility rules, not the
    site's eight-week cold-start rule.
    """
    history = _recent_contiguous_history(series)

    if len(history) < INTERMITTENT_MIN_WEEKS:
        return []

    values = history["quantity"].to_numpy(dtype=float)

    zero_share = float(np.mean(values == 0))
    positive_count = int(np.count_nonzero(values > 0))

    if (
        zero_share <= INTERMITTENT_ZERO_THRESHOLD
        or positive_count < 2
    ):
        return []

    return ["croston", "tsb"]


def intermittent_forecast(series, method, horizon=4):
    """
    Forecast intermittent weekly distributions.

    Uses recent contiguous history only.
    Missing inactive-site weeks are never filled.
    """
    if type(horizon) is not int or not 4 <= horizon <= 8:
        raise ForecastError(
            "Horizon must be an integer from 4 to 8."
        )

    if method not in {"croston", "tsb"}:
        raise ForecastError(
            f"Unknown intermittent method: {method}"
        )

    history = _recent_contiguous_history(series)

    if method not in eligible_intermittent(history):
        raise ForecastError(
            f"{method} requires sufficient consecutive "
            "intermittent history with multiple "
            "positive observations."
        )

    values = history["quantity"].to_numpy(dtype=float)

    try:
        if method == "croston":
            model = CrostonOptimized()
        else:
            model = TSB(
                alpha_d=0.2,
                alpha_p=0.2,
            )

        result = model.forecast(
            y=values,
            h=horizon,
        )

        predictions = np.asarray(
            result["mean"],
            dtype=float,
        )

    except (
        ValueError,
        RuntimeError,
        FloatingPointError,
        OverflowError,
        ZeroDivisionError,
        np.linalg.LinAlgError,
    ) as exc:
        raise ForecastError(
            f"{method} could not fit the data: {exc}"
        ) from exc

    if (
        predictions.shape != (horizon,)
        or not np.isfinite(predictions).all()
    ):
        raise ForecastError(
            f"{method} produced invalid forecast values."
        )

    return np.maximum(predictions, 0.0)
