
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

from src.forecast import (
    eligible_smoothing,
    smoothing_forecast,
)

from src.forecast import (
    eligible_intermittent,
    intermittent_forecast,
)

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


# ---------------------------------------------------------
# Checkpoint 3B.1 tests
# ---------------------------------------------------------

def test_ses_constant_demand():
    series = make_weekly([100] * 16)

    result = smoothing_forecast(series, "ses", 4)

    assert len(result) == 4
    np.testing.assert_allclose(result, [100] * 4, atol=1)


def test_damped_holt_positive_trend():
    series = make_weekly(
        [100 + 10 * i for i in range(20)]
    )

    result = smoothing_forecast(
        series, "damped_holt", 4
    )

    assert len(result) == 4
    assert np.isfinite(result).all()
    assert (result >= 0).all()
    assert result[0] > 100


def test_smoothing_method_eligibility():
    assert eligible_smoothing(
        make_weekly([100] * 7)
    ) == []

    assert eligible_smoothing(
        make_weekly([100] * 8)
    ) == ["ses"]

    assert eligible_smoothing(
        make_weekly([100] * 12)
    ) == ["ses", "damped_holt"]


def test_smoothing_does_not_cross_inactive_gap():
    series = make_weekly([100] * 20)

    # Removing week 13 leaves only 7 recent
    # consecutive weeks in this history.
    series = series.drop(index=12)

    assert eligible_smoothing(series) == []

    with pytest.raises(ForecastError):
        smoothing_forecast(series, "ses", 4)


def test_old_history_before_gap_cannot_affect_forecast():
    series = make_weekly([100] * 24)
    series = series.drop(index=10)

    altered = series.copy()
    altered.loc[
        altered.index < 10, "quantity"
    ] = 10000

    original_result = smoothing_forecast(
        series, "ses", 4
    )

    altered_result = smoothing_forecast(
        altered, "ses", 4
    )

    np.testing.assert_allclose(
        original_result, altered_result
    )


def test_smoothing_keeps_valid_imputed_zero():
    series = make_weekly([100] * 16)

    series.loc[12, "quantity"] = 0
    series.loc[12, "is_imputed_zero"] = True

    result = smoothing_forecast(
        series, "ses", 4
    )

    assert len(result) == 4
    assert np.isfinite(result).all()
    assert (result >= 0).all()


def test_smoothing_invalid_horizon():
    series = make_weekly([100] * 16)

    with pytest.raises(ForecastError):
        smoothing_forecast(series, "ses", 9)


# ---------------------------------------------------------
# Checkpoint 3B.2 tests
# ---------------------------------------------------------

def intermittent_sample():
    return make_weekly([0, 25, 0, 0] * 6)


def test_intermittent_methods_eligible():
    series = intermittent_sample()

    assert eligible_intermittent(series) == [
        "croston", "tsb"
    ]


def test_regular_distribution_not_intermittent():
    series = make_weekly([100] * 24)

    assert eligible_intermittent(series) == []


def test_single_positive_observation_insufficient():
    series = make_weekly([0] * 23 + [25])

    assert eligible_intermittent(series) == []


def test_croston_forecast_valid():
    result = intermittent_forecast(
        intermittent_sample(), "croston", 4
    )

    assert len(result) == 4
    assert np.isfinite(result).all()
    assert (result >= 0).all()


def test_tsb_forecast_valid():
    result = intermittent_forecast(
        intermittent_sample(), "tsb", 4
    )

    assert len(result) == 4
    assert np.isfinite(result).all()
    assert (result >= 0).all()


def test_inactive_gap_breaks_eligibility():
    series = make_weekly([0, 25, 0, 0] * 5)

    # Only 9 recent consecutive weeks remain.
    series = series.drop(index=10)

    assert eligible_intermittent(series) == []

    with pytest.raises(ForecastError):
        intermittent_forecast(series, "tsb", 4)


def test_old_pre_gap_values_do_not_affect_tsb():
    series = make_weekly([0, 25, 0, 0] * 7)
    series = series.drop(index=10)

    changed = series.copy()
    changed.loc[
        changed.index < 10, "quantity"
    ] = 10000

    original_result = intermittent_forecast(
        series, "tsb", 4
    )

    changed_result = intermittent_forecast(
        changed, "tsb", 4
    )

    np.testing.assert_allclose(
        original_result,
        changed_result,
    )


def test_intermittent_invalid_horizon():
    with pytest.raises(ForecastError):
        intermittent_forecast(
            intermittent_sample(), "croston", 9
        )
