"""Week 3 Gate 3: leakage-aware out-of-sample forecast evaluation.

At each of four historical origins, the caller MUST train only on data
known by that origin. Missing actual child-week records are never zero-filled.
Both scored-panel error and forecast coverage are reported. This diagnostic
alone does NOT certify Gate 3 or validate nominal prediction-band coverage.
"""
from datetime import timedelta
from time import perf_counter

import numpy as np
import pandas as pd

KEY = ["site_id", "product", "size", "week_start"]
DETAIL_COLUMNS = ["fold", "origin_week", *KEY, "actual_units", "forecast_units",
                  "is_imputed_zero", "method", "forecast_source", "quality_flags",
                  "status", "absolute_error", "signed_error"]


class Gate3EvaluationError(ValueError):
    """Unsafe inputs for independent historical evaluation."""


def _monday(value):
    try:
        date = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise Gate3EvaluationError("Invalid evaluation date.") from exc
    if pd.isna(date) or date.tzinfo is not None or date.weekday() != 0:
        raise Gate3EvaluationError("Evaluation end must be a timezone-naive Monday.")
    return date.normalize()


def raw_prefix_through_completed_week(raw, origin_week):
    """Keep only transactions through Sunday of the completed origin week.

    Re-aggregate this prefix for each historical fold; reusing a final
    zero-imputed training table could leak future observations.
    """
    origin = _monday(origin_week)
    if not isinstance(raw, pd.DataFrame) or "date" not in raw.columns:
        raise Gate3EvaluationError("Raw distribution log must have a date column.")
    dates = pd.to_datetime(raw["date"], errors="coerce")
    if dates.isna().any() or dates.dt.tz is not None:
        raise Gate3EvaluationError("Raw dates must be valid timezone-naive dates.")
    cutoff = origin + timedelta(days=6)
    return raw.loc[dates <= cutoff].copy()


def _numeric(frame, column):
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise Gate3EvaluationError(f"Invalid nonnegative units in {column}.")
    return values


def _validate_actual(weekly):
    if not isinstance(weekly, pd.DataFrame) or not set(KEY + ["quantity", "is_imputed_zero"]).issubset(weekly.columns):
        raise Gate3EvaluationError("Actual weekly table missing canonical columns.")
    actual = weekly[KEY + ["quantity", "is_imputed_zero"]].copy()
    actual["week_start"] = pd.to_datetime(actual["week_start"], errors="coerce")
    if (actual[KEY].isna().any().any() or actual.duplicated(KEY).any()
            or actual["week_start"].dt.weekday.ne(0).any()
            or actual["is_imputed_zero"].isna().any()
            or not actual["is_imputed_zero"].isin([True, False]).all()):
        raise Gate3EvaluationError("Invalid actual keys, ISO weeks or zero-imputation flags.")
    actual["quantity"] = _numeric(actual, "quantity")
    return actual


def _validate_forecast(predictions, origin, expected):
    if not isinstance(predictions, pd.DataFrame):
        raise Gate3EvaluationError("Prediction callback must return a DataFrame.")
    required = set(KEY + ["forecast_units", "method"])
    if not required.issubset(predictions.columns):
        raise Gate3EvaluationError("Forecasts missing canonical keys, units or method.")
    forecast = predictions.copy()
    forecast["week_start"] = pd.to_datetime(forecast["week_start"], errors="coerce")
    if (forecast[KEY + ["method"]].isna().any().any() or forecast.duplicated(KEY).any()
            or not forecast["week_start"].isin(expected).all()):
        raise Gate3EvaluationError("Forecasts contain duplicate, invalid or out-of-window keys.")
    if "origin_week" in forecast.columns:
        origins = pd.to_datetime(forecast["origin_week"], errors="coerce")
        if origins.isna().any() or not origins.eq(origin).all():
            raise Gate3EvaluationError("Forecast origin is not the historical cutoff.")
    forecast["forecast_units"] = _numeric(forecast, "forecast_units")
    for name in ["forecast_source", "quality_flags"]:
        if name not in forecast:
            forecast[name] = ""
    return forecast[KEY + ["forecast_units", "method", "forecast_source", "quality_flags"]]


def _pct(numerator, denominator):
    return float(100.0 * numerator / denominator) if denominator > 0 else None


def _metric(scored):
    if scored.empty:
        return {"wape_pct": None, "bias_pct": None, "actual_units": 0.0,
                "absolute_error_units": 0.0, "scored_rows": 0}
    total = float(scored["actual_units"].sum())
    return {
        "wape_pct": _pct(float(scored["absolute_error"].sum()), total),
        "bias_pct": _pct(float(scored["signed_error"].sum()), total),
        "actual_units": total,
        "absolute_error_units": float(scored["absolute_error"].sum()),
        "scored_rows": int(len(scored)),
    }


def _report_by_group(detail, keys, minimum_complete_child_fold=False):
    records = []
    for group_key, frame in detail.groupby(keys, dropna=False, sort=True):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        scored = frame.loc[frame["status"].eq("scored")].copy()
        eligible = scored
        valid_folds = []
        if minimum_complete_child_fold:
            # A complete four-week child panel is needed for a defensible
            # per-series four-week WAPE. Partial weeks are still in the
            # network observable-panel diagnostic, never silently erased.
            for fold, block in scored.groupby("fold"):
                if len(block) == 4 and block["week_start"].nunique() == 4:
                    valid_folds.append(int(fold))
            eligible = scored.loc[scored["fold"].isin(valid_folds)]
        metrics = _metric(eligible)
        if metrics["wape_pct"] is None:
            reason = ("no_complete_four_week_fold" if minimum_complete_child_fold and not eligible.shape[0]
                      else "zero_actual_units_or_no_scored_rows")
        else:
            reason = ""
        methods = sorted(set(scored["method"].dropna().astype(str)))
        row = dict(zip(keys, group_key))
        row.update(metrics)
        row.update({
            "wape_reason": reason,
            "evaluated_folds": int(eligible["fold"].nunique()),
            "methods_used": ";".join(methods),
            "matched_rows_all": int(len(scored)),
            "unforecasted_actual_rows": int(frame["status"].eq("missing_prediction").sum()),
            "unforecasted_actual_units": float(frame.loc[frame["status"].eq("missing_prediction"), "actual_units"].sum()),
        })
        records.append(row)
    return pd.DataFrame(records)


def evaluate_historical_forecasts(actual_weekly, predict_as_of, end_week, folds=4, horizon=4):
    """Evaluate as-of forecasts on independent, nonoverlapping 4-week blocks.

    predict_as_of(origin: pandas.Timestamp, horizon: int) -> DataFrame or dict
    with a `forecasts` DataFrame and optional `issues` DataFrame. Callback
    MUST rebuild or obtain historical inputs only through the supplied origin.
    Actual series absent from the holdout are NEVER assumed to be zero.
    """
    end = _monday(end_week)
    if type(folds) is not int or folds < 1 or type(horizon) is not int or horizon != 4:
        raise Gate3EvaluationError("Gate 3 requires positive folds and four-week holdouts.")
    if not callable(predict_as_of):
        raise Gate3EvaluationError("predict_as_of must be callable.")
    actual = _validate_actual(actual_weekly)
    all_details = []
    issues = []
    durations = []
    total_start = perf_counter()
    for fold in range(1, folds + 1):
        start_week = end - timedelta(days=7 * (horizon * (folds - fold + 1) - 1))
        origin = start_week - timedelta(days=7)
        expected = pd.date_range(start_week, periods=horizon, freq="W-MON")
        tic = perf_counter()
        result = predict_as_of(origin, horizon)
        duration = perf_counter() - tic
        durations.append({"fold": fold, "origin_week": origin, "forecast_seconds": duration})
        if isinstance(result, dict):
            predictions = result["forecasts"]
            current_issues = result.get("issues", pd.DataFrame())
        else:
            predictions = result
            current_issues = pd.DataFrame()
        pred = _validate_forecast(predictions, origin, expected)
        observed = actual.loc[actual["week_start"].isin(expected)].rename(
            columns={"quantity": "actual_units"}
        )
        if observed.empty:
            raise Gate3EvaluationError("No recorded actuals in a historical holdout window.")
        merged = observed.merge(pred, on=KEY, how="outer", indicator=True, validate="one_to_one")
        merged["status"] = merged["_merge"].map({
            "both": "scored", "left_only": "missing_prediction", "right_only": "no_recorded_actual"
        }).astype(str)
        merged["fold"] = fold
        merged["origin_week"] = origin
        good = merged["status"].eq("scored")
        merged["absolute_error"] = np.where(
            good, (merged["forecast_units"] - merged["actual_units"]).abs(), np.nan
        )
        merged["signed_error"] = np.where(
            good, merged["forecast_units"] - merged["actual_units"], np.nan
        )
        all_details.append(merged[DETAIL_COLUMNS])
        if not current_issues.empty:
            errors = current_issues.copy()
            errors["fold"] = fold
            errors["origin_week"] = origin
            issues.append(errors)
    total_seconds = perf_counter() - total_start
    detail = pd.concat(all_details, ignore_index=True)
    scored = detail.loc[detail["status"].eq("scored")]
    all_actual = detail.loc[detail["status"].ne("no_recorded_actual")]
    missed = detail.loc[detail["status"].eq("missing_prediction")]
    common = _metric(scored)
    total_actual_units = float(all_actual["actual_units"].sum())
    missing_actual_units = float(missed["actual_units"].sum())
    percent_coverage = _pct(float(scored["actual_units"].sum()), total_actual_units)
    row_coverage = _pct(len(scored), len(all_actual))
    site = _report_by_group(detail, ["site_id"])
    children = _report_by_group(detail, ["site_id", "product", "size"], minimum_complete_child_fold=True)
    fold_report = _report_by_group(detail, ["fold"])
    per_method = _report_by_group(detail, ["method"])
    issue_frame = pd.concat(issues, ignore_index=True) if issues else pd.DataFrame(
        columns=["site_id", "reason", "detail", "fold", "origin_week"]
    )
    # Threshold on a scored observable panel is NOT identical to full-network
    # coverage. Gate3 cannot be automatically certified by this experiment.
    status = {
        "evaluation_type": "as_of_outer_four_fold_four_week_holdouts",
        "folds": folds, "horizon": horizon,
        "total_elapsed_seconds": round(total_seconds, 3),
        "full_backtest_under_60s": total_seconds < 60.0,
        "observable_panel_wape_pct": common["wape_pct"],
        "observable_panel_bias_pct": common["bias_pct"],
        "observable_panel_wape_under_20pct": (
            common["wape_pct"] is not None and common["wape_pct"] < 20.0
        ),
        "observed_actual_rows": int(len(all_actual)),
        "scored_rows": int(len(scored)),
        "unforecasted_actual_rows": int(len(missed)),
        "unforecasted_actual_units": missing_actual_units,
        "scored_actual_units": common["actual_units"],
        "all_recorded_actual_units": total_actual_units,
        "recorded_actual_row_coverage_pct": row_coverage,
        "recorded_actual_unit_coverage_pct": percent_coverage,
        "forecast_rows_without_recorded_actual": int(detail["status"].eq("no_recorded_actual").sum()),
        "per_child_wape_available": int(children["wape_pct"].notna().sum()),
        "per_child_wape_na": int(children["wape_pct"].isna().sum()),
        "gate3_certified": False,
        "gate3_reason": "Benchmark diagnostic only. Review missing observations, incomplete per-child fold coverage, survey provenance and final UI/report integration.",
    }
    return {
        "summary": status, "detail": detail, "per_child": children,
        "per_site": site, "per_fold": fold_report,
        "per_method": per_method, "issues": issue_frame,
        "timings": pd.DataFrame(durations),
    }
