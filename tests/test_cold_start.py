"""Checkpoint 5B: deterministic survey-based estimator unit tests."""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from src.cold_start import ColdStartError, build_survey_cold_start


def fixture_data(target_weeks=7):
    dates = pd.date_range("2026-01-05", periods=12, freq="W-MON")
    rows = []
    for date in dates:
        # Two WIC peers: both 8+ active weeks, known monthly family counts.
        for site, quantity in [("SITE_001", 100), ("SITE_002", 200)]:
            rows.append({"site_id": site, "product": "diaper", "size": "5",
                         "week_start": date, "quantity": quantity, "is_imputed_zero": False})
        # Other category must stay separate, not merge same size label.
        rows.append({"site_id": "SITE_002", "product": "period_pad", "size": "5",
                     "week_start": date, "quantity": 20, "is_imputed_zero": False})
    for date in dates[-target_weeks:]:
        rows.append({"site_id": "SITE_NEW", "product": "diaper", "size": "5",
                     "week_start": date, "quantity": 1, "is_imputed_zero": False})
    master = pd.DataFrame([
        {"site_id": "SITE_001", "site_name": "Peer 1", "families_served_per_month": 10,
         "agency_type": "wic_clinic", "has_survey_data": True},
        {"site_id": "SITE_002", "site_name": "Peer 2", "families_served_per_month": 20,
         "agency_type": "wic_clinic", "has_survey_data": True},
        {"site_id": "SITE_NEW", "site_name": "New", "families_served_per_month": 15,
         "agency_type": "wic_clinic", "has_survey_data": True},
    ])
    return pd.DataFrame(rows), master, dates[-1]


def run_demo(data, master, origin, **kwargs):
    return build_survey_cold_start(
        data, master, origin, ["SITE_NEW"],
        allow_undated_survey_for_demo=True, **kwargs,
    )


def test_seven_site_weeks_survey_based_and_units_conserved():
    data, master, origin = fixture_data()
    got = run_demo(data, master, origin)
    f = got["forecasts"]
    assert got["issues"].empty
    assert len(f) == 8  # Two canonical variants x four future weeks
    assert f["method"].eq("survey_based").all()
    assert f["wape_pct"].isna().all()
    assert f["parent_wape_pct"].isna().all()
    assert f["requires_review"].all()
    assert f["quality_flags"].str.contains("undated_survey_retrospective_demo").all()
    assert f["wape_reason"].eq("survey_based_no_leakage_safe_backtest").all()
    assert not f.duplicated(["site_id", "product", "size", "week_start"]).any()
    # ((100+200+20) units each peer-active week) / (10+20 family-weeks) = 10.666...
    expected_weekly = 15 * (320 / 30)
    np.testing.assert_allclose(f.groupby("week_start")["forecast_units"].sum(), expected_weekly)
    assert set(map(tuple, f[["product", "size"]].drop_duplicates().to_numpy())) == {
        ("diaper", "5"), ("period_pad", "5")
    }
    assert f["mix_source"].eq("agency_type_observed_mix").all()


def test_eight_observed_site_weeks_not_cold_start():
    data, master, origin = fixture_data(8)
    got = run_demo(data, master, origin)
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "historical_method_eligible"


def test_no_survey_timestamp_requires_explicit_demo_opt_in():
    data, master, origin = fixture_data()
    got = build_survey_cold_start(data, master, origin, ["SITE_NEW"])
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "survey_date_unverified"


def test_dated_survey_is_accepted_without_demo_opt_in():
    data, master, origin = fixture_data()
    master["survey_as_of_week"] = origin - timedelta(days=14)
    got = build_survey_cold_start(data, master, origin, ["SITE_NEW"])
    assert not got["forecasts"].empty
    assert got["forecasts"]["quality_flags"].str.contains("survey_dated_at_or_before_origin").all()


def test_future_survey_cannot_be_used_at_origin():
    data, master, origin = fixture_data()
    master["survey_as_of_week"] = origin - timedelta(days=7)
    master.loc[master["site_id"].eq("SITE_NEW"), "survey_as_of_week"] = origin + timedelta(days=7)
    got = build_survey_cold_start(data, master, origin, ["SITE_NEW"])
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "survey_not_yet_available"


def test_future_distributions_do_not_leak_into_calibration():
    data, master, origin = fixture_data()
    baseline = run_demo(data, master, origin)["forecasts"]
    future = data.loc[data["site_id"].eq("SITE_001")].iloc[-1:].copy()
    future["week_start"] = origin + timedelta(days=7)
    future["quantity"] = 10_000_000
    mutated = pd.concat([data, future], ignore_index=True)
    result = run_demo(mutated, master, origin)["forecasts"]
    pd.testing.assert_frame_equal(baseline, result)


def test_target_pre_eight_week_distributions_do_not_train_peer_rate():
    data, master, origin = fixture_data()
    expected = run_demo(data, master, origin)["forecasts"]
    shifted = data.copy()
    shifted.loc[shifted["site_id"].eq("SITE_NEW"), "quantity"] = 10000
    actual = run_demo(shifted, master, origin)["forecasts"]
    pd.testing.assert_frame_equal(expected, actual)


def test_missing_positive_family_count_returns_issue_not_zero_forecast():
    data, master, origin = fixture_data()
    master.loc[master["site_id"].eq("SITE_NEW"), "families_served_per_month"] = 0
    got = run_demo(data, master, origin)
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "missing_family_denominator"


def test_not_enough_calibration_peers_returns_issue():
    data, master, origin = fixture_data()
    master.loc[master["site_id"].eq("SITE_002"), "families_served_per_month"] = 0
    got = run_demo(data, master, origin)
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "insufficient_calibration_peers"


def test_duplicate_site_master_rejected():
    data, master, origin = fixture_data()
    duplicate = pd.concat([master, master.iloc[[0]]], ignore_index=True)
    with pytest.raises(ColdStartError, match="duplicated"):
        run_demo(data, duplicate, origin)


def test_inactive_target_is_not_silently_forecast():
    data, master, origin = fixture_data()
    data = data.loc[~((data["site_id"] == "SITE_NEW") & (data["week_start"] == origin))]
    got = run_demo(data, master, origin)
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "site_inactive_at_origin"


def test_unknown_site_issues_explicitly():
    data, master, origin = fixture_data()
    got = build_survey_cold_start(data, master, origin, ["UNKNOWN"])
    assert got["forecasts"].empty
    assert got["issues"].iloc[0]["reason"] == "unknown_site_id"
