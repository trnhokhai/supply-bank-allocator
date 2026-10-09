"""CP5D contract, safety, and empirical-range tests."""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import src.prediction_bands as bands
from src.prediction_bands import PlausibleRangeError, add_empirical_plausible_ranges


def sample(horizon=4):
    weeks = pd.date_range("2026-01-05", periods=28, freq="W-MON")
    history = []
    for week in weeks:
        for product, size, amount in [("diaper", "5", 60), ("period_pad", "regular", 40)]:
            history.append({"site_id": "SITE_001", "product": product,
                            "size": size, "week_start": week,
                            "quantity": amount, "is_imputed_zero": False})
    rows = []
    for week in pd.date_range(weeks[-1] + timedelta(days=7), periods=horizon, freq="W-MON"):
        for product, size, point in [("diaper", "5", 70), ("period_pad", "regular", 50)]:
            rows.append({"site_id": "SITE_001", "product": product,
                         "size": size, "week_start": week, "origin_week": weeks[-1],
                         "forecast_units": point, "method": "naive",
                         "parent_wape_pct": 12.5, "wape_pct": np.nan,
                         "wape_reason": "child_level_backtesting_pending",
                         "quality_flags": ""})
    return pd.DataFrame(rows), pd.DataFrame(history), weeks[-1]


def fake_backtest(series, method, end_week, folds=4):
    end = pd.Timestamp(end_week)
    recs = []
    for fold in range(1, min(folds, 4) + 1):
        start = end - timedelta(days=7 * (4 * (5 - fold) - 1))
        origin = start - timedelta(days=7)
        for w in pd.date_range(start, periods=4, freq="W-MON"):
            recs.append({"fold": fold, "origin_week": origin,
                         "week_start": w, "forecast_units": 120.0})
    return pd.DataFrame(recs)


def test_nominal_range_is_nonnegative_contains_point_and_has_evidence(monkeypatch):
    monkeypatch.setattr(bands, "backtest_forecast", fake_backtest)
    f, w, origin = sample()
    result = add_empirical_plausible_ranges(f, w, origin)
    out = result["forecasts"]
    assert result["coverage"]["range_rows"] == 8
    assert out["range_valid_folds"].eq(4).all()
    assert out["range_residual_rows"].eq(16).all()
    assert (out["lower_units"] >= 0).all()
    assert (out["lower_units"] <= out["forecast_units"]).all()
    assert (out["upper_units"] >= out["forecast_units"]).all()
    assert out["range_label"].str.contains("80% plausible").all()


def test_original_forecasts_and_accuracy_are_not_rewritten(monkeypatch):
    monkeypatch.setattr(bands, "backtest_forecast", fake_backtest)
    f, w, origin = sample()
    res = add_empirical_plausible_ranges(f, w, origin)["forecasts"]
    np.testing.assert_allclose(f["forecast_units"], res["forecast_units"])
    np.testing.assert_allclose(f["parent_wape_pct"], res["parent_wape_pct"])
    assert res["wape_pct"].isna().all()
    assert res["wape_reason"].eq("child_level_backtesting_pending").all()


def test_survey_forecast_keeps_range_na_and_reason(monkeypatch):
    f, w, origin = sample()
    f["method"] = "survey_based"
    f["parent_wape_pct"] = np.nan
    def should_not_backtest(*args, **kwargs):
        raise AssertionError("Cold-start must not pretend to have historical residuals")
    monkeypatch.setattr(bands, "backtest_forecast", should_not_backtest)
    out = add_empirical_plausible_ranges(f, w, origin)["forecasts"]
    assert out["lower_units"].isna().all()
    assert out["upper_units"].isna().all()
    assert out["range_reason"].eq("survey_based_no_independent_residuals").all()


def test_trailing_history_and_zero_weights_never_receive_fake_range(monkeypatch):
    monkeypatch.setattr(bands, "backtest_forecast", fake_backtest)
    f, w, origin = sample()
    f.loc[f["product"] == "period_pad", "quality_flags"] = "trailing_child_history_gap;zero_historical_mix_weight"
    out = add_empirical_plausible_ranges(f, w, origin)["forecasts"]
    stale = out.loc[out["product"] == "period_pad"]
    healthy = out.loc[out["product"] == "diaper"]
    assert stale["lower_units"].isna().all()
    assert stale["range_reason"].eq("stale_or_zero_weight_child_requires_review").all()
    assert healthy["lower_units"].notna().all()


def test_no_future_leakage_even_if_future_quantities_large(monkeypatch):
    monkeypatch.setattr(bands, "backtest_forecast", fake_backtest)
    f, w, origin = sample()
    extra = w.iloc[[-1]].copy()
    extra["week_start"] = origin + timedelta(days=7)
    extra["quantity"] = 999999
    a = add_empirical_plausible_ranges(f, w, origin)["forecasts"]
    b = add_empirical_plausible_ranges(f, pd.concat([w, extra]), origin)["forecasts"]
    pd.testing.assert_frame_equal(a, b)


def test_insufficient_two_folds_returns_na_not_fabricated(monkeypatch):
    def one_fold(*args, **kwargs):
        return fake_backtest(*args, **kwargs).query("fold == 1")
    monkeypatch.setattr(bands, "backtest_forecast", one_fold)
    f, w, origin = sample()
    out = add_empirical_plausible_ranges(f, w, origin)["forecasts"]
    assert out["lower_units"].isna().all()
    assert out["range_reason"].eq("insufficient_backtest_residual_evidence").all()
    assert out["range_valid_folds"].eq(1).all()


def test_5_to_8_week_range_only_widens_and_zero_floor(monkeypatch):
    monkeypatch.setattr(bands, "backtest_forecast", fake_backtest)
    f, w, origin = sample(horizon=8)
    out = add_empirical_plausible_ranges(f, w, origin, horizon=8)["forecasts"]
    d = out.loc[out["product"].eq("diaper")].sort_values("week_start")
    assert d["lower_units"].iloc[-1] <= d["lower_units"].iloc[3]
    assert d["upper_units"].iloc[-1] >= d["upper_units"].iloc[3]
    assert (d["lower_units"] >= 0).all()


def test_invalid_origin_and_duplicate_forecast_keys_rejected():
    f, w, origin = sample()
    with pytest.raises(PlausibleRangeError, match="Monday"):
        add_empirical_plausible_ranges(f, w, "2026-07-14")
    bad = pd.concat([f, f.iloc[[-1]]], ignore_index=True)
    with pytest.raises(PlausibleRangeError, match="Invalid canonical"):
        add_empirical_plausible_ranges(bad, w, origin)
