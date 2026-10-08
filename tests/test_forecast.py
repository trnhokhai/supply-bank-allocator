
import numpy as np
import pandas as pd
import pytest

from src.forecast import (
    ForecastError,
    baseline_forecast,
    eligible_baselines,
    prepare_forecast_series,
)

from src.forecast import backtest_baseline, summarize_backtest

from src.forecast import select_baseline_method

def make_weekly(quantities, weeks=None):
    if weeks is None:
        weeks = pd.date_range(
            "2026-01-05", periods=len(quantities), freq="W-MON"
        )

    return pd.DataFrame({
        "site_id": ["SITE_001"] * len(quantities),
        "product": ["diaper"] * len(quantities),
        "size": ["6"] * len(quantities),
        "week_start": weeks,
        "quantity": quantities,
        "is_imputed_zero": [
            value == 0 for value in quantities
        ],
    })


def test_naive():
    series = make_weekly([100, 120, 80, 140])
    result = baseline_forecast(series, "naive", 4)

    np.testing.assert_array_equal(result, [140] * 4)


def test_moving_average_4():
    series = make_weekly([100, 120, 80, 140])
    result = baseline_forecast(series, "ma4", 4)

    np.testing.assert_array_equal(result, [110] * 4)


def test_moving_average_8():
    series = make_weekly([10, 20, 30, 40, 50, 60, 70, 80])
    result = baseline_forecast(series, "ma8", 4)

    np.testing.assert_array_equal(result, [45] * 4)


def test_zero_distribution_is_preserved():
    series = make_weekly([100, 0, 120, 140])
    prepared = prepare_forecast_series(
        series, "SITE_001", "diaper", "6"
    )

    assert len(prepared) == 4
    assert prepared["quantity"].tolist() == [100, 0, 120, 140]
    assert prepared["is_imputed_zero"].sum() == 1


def test_inactive_gap_not_zero_filled():
    weeks = pd.to_datetime([
        "2026-01-05",
        "2026-01-12",
        "2026-03-02",
        "2026-03-09",
    ])

    series = make_weekly([100, 120, 130, 150], weeks)
    prepared = prepare_forecast_series(
        series, "SITE_001", "diaper", "6"
    )

    assert len(prepared) == 4
    assert prepared["quantity"].sum() == 500
    assert prepared["is_imputed_zero"].sum() == 0


def test_method_eligibility():
    assert eligible_baselines(make_weekly([1, 2])) == ["naive"]
    assert eligible_baselines(make_weekly([1, 2, 3, 4])) == [
        "naive", "ma4"
    ]
    assert len(eligible_baselines(make_weekly([1] * 8))) == 3


def test_invalid_horizon():
    with pytest.raises(ForecastError):
        baseline_forecast(make_weekly([100]), "naive", 9)


def test_negative_quantity_rejected():
    with pytest.raises(ForecastError):
        prepare_forecast_series(
            make_weekly([100, -1]),
            "SITE_001", "diaper", "6"
        )


def test_duplicate_week_rejected():
    weekly = make_weekly([100, 200])
    weekly.loc[1, "week_start"] = weekly.loc[0, "week_start"]

    with pytest.raises(ForecastError):
        prepare_forecast_series(
            weekly, "SITE_001", "diaper", "6"
        )


def test_backtest_four_folds_and_no_future_leakage():
    series = make_weekly(list(range(1, 25)))
    end_week = series["week_start"].max()

    rows = backtest_baseline(series, "naive", end_week)

    assert len(rows) == 16
    assert rows.groupby("fold").size().to_dict() == {
        1: 4, 2: 4, 3: 4, 4: 4
    }
    assert rows.loc[
        rows["fold"] == 1, "forecast_units"
    ].tolist() == [8.0] * 4

    assert rows.loc[
        rows["fold"] == 4, "forecast_units"
    ].tolist() == [20.0] * 4

    assert (rows["origin_week"] < rows["week_start"]).all()


def test_inactive_test_week_skips_fold():
    series = make_weekly(list(range(1, 25)))
    end_week = series["week_start"].max()

    # Remove week 22: missing activity, not zero demand.
    series = series.drop(index=21)

    rows = backtest_baseline(series, "naive", end_week)

    assert len(rows) == 12
    assert set(rows["fold"]) == {1, 2, 3}


def test_imputed_zero_is_valid_evaluation_actual():
    series = make_weekly([10] * 24)
    series.loc[21, "quantity"] = 0
    series.loc[21, "is_imputed_zero"] = True

    rows = backtest_baseline(
        series, "naive", series["week_start"].max()
    )

    assert len(rows) == 16
    assert rows["is_imputed_zero"].sum() == 1
    assert (rows["actual_units"] == 0).sum() == 1


def test_ma4_does_not_cross_recent_calendar_gap():
    series = make_weekly(list(range(1, 25)))
    end_week = series["week_start"].max()

    # Remove week 18.
    series = series.drop(index=17)

    rows = backtest_baseline(series, "ma4", end_week)

    assert set(rows["fold"]) == {1, 2}
    assert len(rows) == 8


def test_backtest_wape_and_signed_bias():
    rows = pd.DataFrame({
        "fold": [1, 1],
        "actual_units": [100, 100],
        "forecast_units": [90, 120],
    })

    metrics = summarize_backtest(rows, "naive")

    assert metrics["wape_pct"] == pytest.approx(15.0)
    assert metrics["bias_pct"] == pytest.approx(5.0)
    assert metrics["folds_evaluated"] == 1


def test_zero_actual_denominator_is_not_fake_accuracy():
    rows = pd.DataFrame({
        "fold": [1, 1],
        "actual_units": [0, 0],
        "forecast_units": [10, 20],
    })

    metrics = summarize_backtest(rows, "naive")

    assert metrics["wape_pct"] is None
    assert metrics["bias_pct"] is None
    assert "zero" in metrics["reason"]


def test_insufficient_history_reports_na():
    series = make_weekly([10, 20, 30, 40])

    rows = backtest_baseline(
        series, "naive", series["week_start"].max()
    )
    metrics = summarize_backtest(rows, "naive")

    assert rows.empty
    assert metrics["folds_evaluated"] == 0
    assert metrics["wape_pct"] is None
    assert metrics["reason"] is not None


def test_evaluation_end_must_be_monday():
    series = make_weekly([10] * 24)

    with pytest.raises(ForecastError):
        backtest_baseline(
            series, "naive", "2026-06-23"
        )


def test_selection_identical_folds():
    series = make_weekly([10] * 24)

    result = select_baseline_method(
        series, series["week_start"].max()
    )

    assert result["method"] == "naive"
    assert result["compared_folds"] == [1, 2, 3, 4]
    assert len(result["scores"]) == 3
    assert all(
        type(fold) is int
        for fold in result["compared_folds"]
    )


def test_selection_intersects_unequal_fold_coverage():
    series = make_weekly([10] * 24)

    # Week 6 missing: some early moving-average
    # training windows become ineligible.
    series = series.drop(index=5)

    result = select_baseline_method(
        series, series["week_start"].max()
    )

    assert result["compared_folds"] == [3, 4]
    assert all(
        score["folds_evaluated"] == 2
        for score in result["scores"]
    )


def test_zero_actual_selection_returns_na():
    series = make_weekly([0] * 24)

    result = select_baseline_method(
        series, series["week_start"].max()
    )

    assert result["method"] is None
    assert result["wape_pct"] is None
    assert result["reason"] is not None


def test_direct_ma4_rejects_calendar_gap():
    weeks = pd.to_datetime([
        "2026-01-05",
        "2026-01-12",
        "2026-01-26",
        "2026-02-02",
    ])

    series = make_weekly(
        [100, 120, 130, 140], weeks
    )

    with pytest.raises(ForecastError):
        baseline_forecast(series, "ma4", 4)
