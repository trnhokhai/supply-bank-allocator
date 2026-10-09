"""CP5C routing tests: work with the repository's CP4C/CP5B modules."""
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

import src.forecast_pipeline as pipeline
from src.forecast_pipeline import ForecastPipelineError, build_unified_forecasts
from src.forecast_output import OUTPUT_COLUMNS


def fixtures():
    weeks = pd.date_range("2026-01-05", periods=12, freq="W-MON")
    rows = []
    for site, dates in [
        ("OLD", weeks),
        ("NEW", weeks[-7:]),
        ("INACTIVE", weeks[:3]),
    ]:
        for w in dates:
            rows.append({"site_id": site, "product": "diaper", "size": "5",
                         "week_start": w, "quantity": 10, "is_imputed_zero": False})
    master = pd.DataFrame({"site_id": ["OLD", "NEW", "INACTIVE", "ONLY"],
                           "site_name": ["Old", "New", "Inactive", "Only"],
                           "agency_type": ["pantry"] * 4,
                           "families_served_per_month": [30] * 4})
    return pd.DataFrame(rows), master, weeks[-1]


def sample_row(site_id, origin, method, units=10, parent_wape=np.nan):
    d = dict.fromkeys(OUTPUT_COLUMNS, np.nan)
    d.update({"site_id": site_id, "product": "diaper", "size": "5",
              "week_start": origin + timedelta(days=7), "forecast_units": units,
              "hierarchy": "site_total", "method": method,
              "method_level": "site_total", "forecast_source": "historical" if method != "survey_based" else "survey_based_peer_calibration",
              "origin_week": origin, "parent_wape_pct": parent_wape,
              "wape_pct": np.nan, "wape_reason": "child_level_backtesting_pending" if method != "survey_based" else "survey_based_no_leakage_safe_backtest",
              "quality_flags": "", "requires_review": method == "survey_based",
              "forecast_status": "provisional_cp5"})
    return d


def mocked(monkeypatch, origin, survey_winner=True):
    calls = []

    def historical(weekly, origin_week, horizon=4):
        calls.append(("historical", origin_week, horizon))
        return {"forecasts": pd.DataFrame([sample_row("OLD", origin, "naive", parent_wape=12.5)], columns=OUTPUT_COLUMNS),
                "issues": pd.DataFrame([
                    {"site_id": "NEW", "reason": "site_cold_start", "detail": "under8"},
                    {"site_id": "INACTIVE", "reason": "site_not_observed_at_origin", "detail": "inactive"},
                ])}

    def cold(weekly, site_master, origin_week, target_site_ids, horizon=4, allow_undated_survey_for_demo=False):
        calls.append(("cold", origin_week, tuple(target_site_ids), horizon, allow_undated_survey_for_demo))
        rows = [sample_row("NEW", origin, "survey_based", units=7)] if survey_winner else []
        issues = [{"site_id": "ONLY", "reason": "survey_date_unverified", "detail": "undated"}]
        if not survey_winner:
            issues.append({"site_id": "NEW", "reason": "survey_missing", "detail": "missing"})
        return {"forecasts": pd.DataFrame(rows, columns=OUTPUT_COLUMNS),
                "issues": pd.DataFrame(issues), "calibration": pd.DataFrame([{"site_id": "NEW"}])}

    monkeypatch.setattr(pipeline, "build_site_total_forecasts", historical)
    monkeypatch.setattr(pipeline, "build_survey_cold_start", cold)
    return calls


def test_unified_routes_only_current_cold_and_survey_only(monkeypatch):
    wk, master, origin = fixtures()
    calls = mocked(monkeypatch, origin)
    result = build_unified_forecasts(wk, master, origin, allow_undated_survey_for_demo=True)
    assert calls[1] == ("cold", origin, ("NEW", "ONLY"), 4, True)
    assert set(result["forecasts"]["site_id"]) == {"OLD", "NEW"}
    assert set(result["issues"]["site_id"]) == {"INACTIVE", "ONLY"}
    assert result["coverage"]["historical_sites"] == 1
    assert result["coverage"]["survey_sites"] == 1
    assert result["coverage"]["unresolved_sites"] == 2


def test_unavailable_survey_is_issue_not_silent_zero(monkeypatch):
    wk, master, origin = fixtures()
    mocked(monkeypatch, origin, survey_winner=False)
    result = build_unified_forecasts(wk, master, origin)
    assert set(result["forecasts"]["site_id"]) == {"OLD"}
    assert "survey_missing" in set(result["issues"]["reason"])
    assert "site_cold_start" not in set(result["issues"]["reason"])


def test_future_site_weeks_cannot_change_cold_start_routing(monkeypatch):
    wk, master, origin = fixtures()
    calls = mocked(monkeypatch, origin)
    future = wk.loc[wk["site_id"].eq("NEW")].iloc[-1:].copy()
    future["week_start"] = origin + timedelta(days=7)
    build_unified_forecasts(pd.concat([wk, future]), master, origin)
    assert calls[1][2] == ("NEW", "ONLY")


def test_eight_site_weeks_transition_avoids_survey(monkeypatch):
    wk, master, origin = fixtures()
    extra = wk.loc[wk["site_id"].eq("NEW")].iloc[[-1]].copy()
    extra["week_start"] = wk["week_start"].min()
    wk = pd.concat([wk, extra], ignore_index=True)
    calls = mocked(monkeypatch, origin)
    build_unified_forecasts(wk, master, origin)
    assert calls[1][2] == ("ONLY",)


def test_parent_wape_not_invented_as_child_wape(monkeypatch):
    wk, master, origin = fixtures()
    mocked(monkeypatch, origin)
    result = build_unified_forecasts(wk, master, origin)
    f = result["forecasts"]
    assert f.loc[f["site_id"].eq("OLD"), "parent_wape_pct"].iloc[0] == 12.5
    assert f["wape_pct"].isna().all()


def test_bad_origin_rejected():
    wk, master, _ = fixtures()
    with pytest.raises(ForecastPipelineError, match="Monday"):
        build_unified_forecasts(wk, master, "2026-03-24")


def test_duplicate_site_master_rejected():
    wk, master, origin = fixtures()
    master = pd.concat([master, master.iloc[[-1]]], ignore_index=True)
    with pytest.raises(ForecastPipelineError, match="duplicate"):
        build_unified_forecasts(wk, master, origin)


def test_invalid_or_duplicate_output_rejected(monkeypatch):
    wk, master, origin = fixtures()
    mocked(monkeypatch, origin)
    base = pipeline.build_site_total_forecasts

    def invalid(*args, **kwargs):
        d = base(*args, **kwargs)
        d["forecasts"] = pd.concat([d["forecasts"], d["forecasts"]], ignore_index=True)
        return d
    monkeypatch.setattr(pipeline, "build_site_total_forecasts", invalid)
    with pytest.raises(ForecastPipelineError, match="Duplicate"):
        build_unified_forecasts(wk, master, origin)


def test_negative_forecast_rejected(monkeypatch):
    wk, master, origin = fixtures()
    mocked(monkeypatch, origin)
    base = pipeline.build_site_total_forecasts

    def invalid(*args, **kwargs):
        d = base(*args, **kwargs)
        d["forecasts"].loc[:, "forecast_units"] = -1
        return d
    monkeypatch.setattr(pipeline, "build_site_total_forecasts", invalid)
    with pytest.raises(ForecastPipelineError, match="Invalid unified"):
        build_unified_forecasts(wk, master, origin)
