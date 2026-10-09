"""Gate 3 evaluation tests: no leakage, no fabricated zeros, honest coverage."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from src.gate3_eval import (
    Gate3EvaluationError, evaluate_historical_forecasts,
    raw_prefix_through_completed_week,
)


END = pd.Timestamp("2026-09-21")
KEY = ["site_id", "product", "size", "week_start"]


def actuals(values=None, site="SITE_001"):
    weeks = pd.date_range(end=END, periods=16, freq="W-MON")
    values = values if values is not None else [100] * len(weeks)
    return pd.DataFrame([{
        "site_id": site, "product": "diaper", "size": "5", "week_start": week,
        "quantity": value, "is_imputed_zero": value == 0,
    } for week, value in zip(weeks, values)])


def predictor(value=90, missing_last=False, extra=False):
    calls = []
    def predict(origin, horizon):
        calls.append(origin)
        forecast_weeks = pd.date_range(origin + timedelta(days=7), periods=horizon, freq="W-MON")
        rows = [{
            "site_id": "SITE_001", "product": "diaper", "size": "5",
            "week_start": w, "forecast_units": value, "method": "naive",
            "origin_week": origin, "quality_flags": "",
        } for w in forecast_weeks]
        if missing_last:
            rows.pop()
        if extra:
            rows.append({**rows[0], "product": "period_cup", "size": "one_size"})
        return pd.DataFrame(rows)
    return predict, calls


def test_four_nonoverlapping_historical_cutoffs():
    predict, calls = predictor()
    r = evaluate_historical_forecasts(actuals(), predict, END)
    assert len(calls) == 4
    assert calls == [pd.Timestamp("2026-06-01"), pd.Timestamp("2026-06-29"),
                     pd.Timestamp("2026-07-27"), pd.Timestamp("2026-08-24")]
    assert len(r["detail"]) == 16
    assert r["summary"]["scored_rows"] == 16
    assert r["per_child"].iloc[0]["evaluated_folds"] == 4


def test_pooled_wape_and_signed_bias_calculation():
    predict, _ = predictor(value=90)
    r = evaluate_historical_forecasts(actuals(), predict, END)
    assert r["summary"]["observable_panel_wape_pct"] == pytest.approx(10.0)
    assert r["summary"]["observable_panel_bias_pct"] == pytest.approx(-10.0)
    assert r["summary"]["recorded_actual_unit_coverage_pct"] == pytest.approx(100.0)
    assert r["per_child"].iloc[0]["wape_pct"] == pytest.approx(10.0)


def test_missing_forecast_is_reported_not_filled_as_zero():
    predict, _ = predictor(value=90, missing_last=True)
    r = evaluate_historical_forecasts(actuals(), predict, END)
    s = r["summary"]
    assert s["scored_rows"] == 12
    assert s["unforecasted_actual_rows"] == 4
    assert s["unforecasted_actual_units"] == pytest.approx(400)
    assert s["recorded_actual_unit_coverage_pct"] == pytest.approx(75.0)
    assert r["per_child"].iloc[0]["wape_pct"] is None or pd.isna(r["per_child"].iloc[0]["wape_pct"])
    assert (r["detail"].loc[r["detail"]["status"].eq("missing_prediction"), "forecast_units"].isna()).all()


def test_predictions_without_actual_are_unverified_not_scored_zero():
    predict, _ = predictor(extra=True)
    r = evaluate_historical_forecasts(actuals(), predict, END)
    s = r["summary"]
    assert s["forecast_rows_without_recorded_actual"] == 4
    assert s["scored_rows"] == 16
    assert s["observable_panel_wape_pct"] == pytest.approx(10)


def test_valid_week2_imputed_zeros_are_scored():
    predict, _ = predictor(value=0)
    r = evaluate_historical_forecasts(actuals([0] * 8 + [100] * 8), predict, END)
    assert r["summary"]["scored_rows"] == 16
    assert r["summary"]["observable_panel_wape_pct"] == pytest.approx(100)


def test_zero_total_actual_has_explicit_undefined_wape():
    predict, _ = predictor(value=0)
    r = evaluate_historical_forecasts(actuals([0] * 16), predict, END)
    assert r["summary"]["observable_panel_wape_pct"] is None
    assert r["per_child"].iloc[0]["wape_pct"] is None or pd.isna(r["per_child"].iloc[0]["wape_pct"])


def test_rejects_future_week_or_wrong_origin():
    def broken(origin, horizon):
        df = predictor()[0](origin, horizon)
        df.loc[0, "week_start"] = origin + timedelta(days=35)
        return df
    with pytest.raises(Gate3EvaluationError, match="out-of-window"):
        evaluate_historical_forecasts(actuals(), broken, END)


def test_rejects_duplicate_and_negative_predictions():
    def broken(origin, horizon):
        df = predictor()[0](origin, horizon)
        df.loc[0, "forecast_units"] = -1
        return df
    with pytest.raises(Gate3EvaluationError, match="Invalid nonnegative"):
        evaluate_historical_forecasts(actuals(), broken, END)
    def duplicate(origin, horizon):
        df = predictor()[0](origin, horizon)
        return pd.concat([df, df.head(1)], ignore_index=True)
    with pytest.raises(Gate3EvaluationError, match="duplicate"):
        evaluate_historical_forecasts(actuals(), duplicate, END)


def test_per_child_uses_only_complete_four_week_folds():
    weekly = actuals()
    # One observed child week is absent, not interpreted as zero.
    weekly = weekly.loc[weekly["week_start"] != pd.Timestamp("2026-08-03")]
    predict, _ = predictor(value=90)
    r = evaluate_historical_forecasts(weekly, predict, END)
    ch = r["per_child"].iloc[0]
    assert ch["evaluated_folds"] == 3
    assert ch["wape_pct"] == pytest.approx(10)
    assert r["summary"]["forecast_rows_without_recorded_actual"] == 1


def test_unknown_forecast_zero_demand_not_used_for_gate_certification():
    predict, _ = predictor(value=100)
    r = evaluate_historical_forecasts(actuals(), predict, END)
    assert r["summary"]["observable_panel_wape_under_20pct"] is True
    assert r["summary"]["gate3_certified"] is False


def test_raw_prefix_excludes_future_records_even_inside_next_week():
    raw = pd.DataFrame({
        "date": ["2026-06-01", "2026-06-07", "2026-06-08", "2026-09-21"],
        "quantity": [1, 2, 900, 999],
    })
    past = raw_prefix_through_completed_week(raw, "2026-06-01")
    assert past["quantity"].tolist() == [1, 2]
    assert 900 not in past["quantity"].tolist()


def test_raw_prefix_rejects_bad_dates():
    raw = pd.DataFrame({"date": ["not-a-date"], "quantity": [1]})
    with pytest.raises(Gate3EvaluationError, match="Raw dates"):
        raw_prefix_through_completed_week(raw, "2026-06-01")
