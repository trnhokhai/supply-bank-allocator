"""Tests for CP4C provisional production forecast table."""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from src.forecast_output import (
    ForecastOutputError,
    build_site_total_forecasts,
)


def make_weekly(weeks=28):
    dates = pd.date_range("2026-01-05", periods=weeks, freq="W-MON")
    rows = []
    for week in dates:
        for product, size, quantity in [
            ("diaper", "regular", 100),
            ("period_pad", "regular", 50),
        ]:
            rows.append({
                "site_id": "SITE_001", "product": product, "size": size,
                "week_start": week, "quantity": quantity,
                "is_imputed_zero": False,
            })
    return pd.DataFrame(rows)


def test_canonical_grain_and_conservation():
    weekly = make_weekly()
    origin = weekly["week_start"].max()
    result = build_site_total_forecasts(weekly, origin, horizon=4)
    f = result["forecasts"]
    assert result["issues"].empty
    assert len(f) == 8
    assert not f.duplicated(["site_id", "product", "size", "week_start"]).any()
    assert set(f["product"]) == {"diaper", "period_pad"}
    assert set(f["forecast_units"].round(6)) == {100, 50}
    assert f.groupby("week_start")["forecast_units"].sum().eq(150).all()


def test_child_wape_not_mislabeled_as_site_wape():
    f = build_site_total_forecasts(make_weekly(), "2026-07-13")["forecasts"]
    assert f["wape_pct"].isna().all()
    assert f["wape_reason"].eq("child_level_backtesting_pending").all()
    assert f["method_level"].eq("site_total").all()
    assert f["forecast_status"].eq("provisional_cp4c").all()


def test_future_rows_do_not_change_origin_forecast():
    earlier = make_weekly(28)
    origin = earlier["week_start"].max()
    future = earlier.iloc[-2:].copy()
    future["week_start"] = origin + timedelta(days=7)
    future["quantity"] = 100000
    combined = pd.concat([earlier, future], ignore_index=True)
    a = build_site_total_forecasts(earlier, origin)["forecasts"]
    b = build_site_total_forecasts(combined, origin)["forecasts"]
    pd.testing.assert_frame_equal(a, b)


def test_site_level_eight_week_threshold_not_per_child_positive():
    data = make_weekly(8)
    pad_mask = data["product"].eq("period_pad")
    data.loc[pad_mask, "quantity"] = 0
    data.loc[pad_mask, "is_imputed_zero"] = True
    result = build_site_total_forecasts(data, data["week_start"].max())
    assert result["issues"].empty
    assert not result["forecasts"].empty
    assert result["forecasts"]["parent_backtest_folds"].eq(0).all()
    assert result["forecasts"]["wape_pct"].isna().all()


def test_true_new_site_is_explicit_issue():
    data = make_weekly(7)
    result = build_site_total_forecasts(data, data["week_start"].max())
    assert result["forecasts"].empty
    assert result["issues"].iloc[0]["reason"] == "site_cold_start"


def test_inactive_current_site_is_not_zero_filled():
    data = make_weekly(20)
    origin = data["week_start"].max() + timedelta(days=7)
    result = build_site_total_forecasts(data, origin)
    assert result["forecasts"].empty
    assert result["issues"].iloc[0]["reason"] == "site_not_observed_at_origin"


def test_trailing_child_gap_flagged_not_filled():
    data = make_weekly(28)
    cutoff = data["week_start"].max() - timedelta(days=35)
    data = data.loc[
        ~((data["product"] == "period_pad") & (data["week_start"] > cutoff))
    ]
    result = build_site_total_forecasts(data, data["week_start"].max())
    f = result["forecasts"]
    pad = f.loc[f["product"].eq("period_pad")]
    assert pad["requires_review"].all()
    assert pad["quality_flags"].str.contains("trailing_child_history_gap").all()
    assert pad["wape_pct"].isna().all()


def test_bad_input_rejected():
    data = make_weekly(20)
    data.loc[0, "quantity"] = -1
    with pytest.raises(ForecastOutputError):
        build_site_total_forecasts(data, data["week_start"].max())


def test_invalid_horizon_rejected():
    data = make_weekly()
    with pytest.raises(ForecastOutputError):
        build_site_total_forecasts(data, data["week_start"].max(), horizon=9)
