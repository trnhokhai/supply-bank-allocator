"""CP8.1 display-only regression tests; no forecast or optimization changes."""

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.forecast_history_view import ForecastHistoryViewError, build_historical_window


def sample_history():
    return pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": "4", "week_start": "2026-08-31", "quantity": 12, "is_imputed_zero": False},
        {"site_id": "A", "product": "diaper", "size": "4", "week_start": "2026-09-07", "quantity": 0, "is_imputed_zero": True},
        # 2026-09-14 has no row (entire site may have been inactive)
        {"site_id": "A", "product": "diaper", "size": "4", "week_start": "2026-09-21", "quantity": 18, "is_imputed_zero": False},
        {"site_id": "B", "product": "diaper", "size": "4", "week_start": "2026-09-14", "quantity": 999, "is_imputed_zero": False},
        {"site_id": "A", "product": "diaper", "size": "5", "week_start": "2026-09-14", "quantity": 777, "is_imputed_zero": False},
        {"site_id": "A", "product": "diaper", "size": "4", "week_start": "2026-09-28", "quantity": 4000, "is_imputed_zero": False},
    ])


def view(hist=None, **changes):
    args = {"site_id": "A", "product": "diaper", "size": "4", "origin_week": "2026-09-21", "lookback_weeks": 4}
    args.update(changes)
    return build_historical_window(sample_history() if hist is None else hist, **args)


def test_four_calendar_weeks_exactly():
    output = view()
    assert output["week_start"].dt.strftime("%Y-%m-%d").tolist() == ["2026-08-31", "2026-09-07", "2026-09-14", "2026-09-21"]
    assert output["has_record"].tolist() == [True, True, False, True]


def test_missing_site_week_stays_missing_not_zero():
    output = view()
    assert pd.isna(output.loc[2, "actual_units"])
    assert not output.loc[2, "is_imputed_zero"]


def test_imputed_zero_is_visible_and_explicitly_flagged():
    output = view()
    assert output.loc[1, "actual_units"] == 0.0
    assert output.loc[1, "is_imputed_zero"]
    assert not output.loc[0, "is_imputed_zero"]


def test_no_future_data_leaks_into_display():
    output = view()
    assert 4000 not in output["actual_units"].tolist()
    assert output["week_start"].max() == pd.Timestamp("2026-09-21")


def test_other_partner_and_size_never_enter_plot():
    output = view()
    assert 999 not in output["actual_units"].tolist()
    assert 777 not in output["actual_units"].tolist()


def test_does_not_mutate_source_dataframe():
    original = sample_history()
    copy = original.copy(deep=True)
    view(original)
    assert_frame_equal(original, copy)


def test_missing_series_returns_missing_calendar_not_fake_zeros():
    output = view(site_id="NO_SITE")
    assert output["actual_units"].isna().all()
    assert not output["has_record"].any()


def test_twentysix_weeks_has_exact_calendar_length():
    output = view(lookback_weeks=26)
    assert len(output) == 26
    assert output["week_start"].iloc[-1] == pd.Timestamp("2026-09-21")


@pytest.mark.parametrize("bad_weeks", [0, -1, 105, 3.5, "26", True])
def test_invalid_history_window_rejected(bad_weeks):
    with pytest.raises(ForecastHistoryViewError):
        view(lookback_weeks=bad_weeks)


@pytest.mark.parametrize("bad_origin", ["2026-09-22", "not-a-date", None])
def test_invalid_origin_rejected(bad_origin):
    with pytest.raises(ForecastHistoryViewError):
        view(origin_week=bad_origin)


def test_duplicate_history_is_rejected():
    base = sample_history()
    duplicate = pd.concat([base, base.iloc[[0]]], ignore_index=True)
    with pytest.raises(ForecastHistoryViewError, match="unique"):
        view(duplicate)


def test_bad_quantity_is_rejected():
    base = sample_history()
    base.loc[0, "quantity"] = -4
    with pytest.raises(ForecastHistoryViewError, match="nonnegative"):
        view(base)


def test_bad_imputation_flag_is_rejected():
    base = sample_history()
    base["is_imputed_zero"] = base["is_imputed_zero"].astype(object)
    base.loc[0, "is_imputed_zero"] = "unknown"
    with pytest.raises(ForecastHistoryViewError, match="Boolean"):
        view(base)


def test_no_invalid_fallthrough_when_history_is_empty():
    empty = sample_history().iloc[0:0].copy()
    output = view(empty)
    assert len(output) == 4
    assert output["actual_units"].isna().all()

def test_history_window_no_numpy_generic_timedelta_warning():
    """Regression: CP8.1 chart helper must not emit the NumPy generic timedelta deprecation."""
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error", category=DeprecationWarning,
            message=r"The 'generic' unit for NumPy timedelta is deprecated.*",
        )
        timeline = view(lookback_weeks=26)
    assert len(timeline) == 26
