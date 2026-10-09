"""CP7B: verify provenance-aware attachment of historical child WAPE."""
import pandas as pd
import pytest
from src.gate3_reporting import attach_child_wape, Gate3ReportingError


def forecasts():
    return pd.DataFrame([
        {"site_id":"SITE_001","product":"diaper","size":"5","week_start":"2026-09-28","method":"naive","wape_pct":None,"wape_reason":"child_level_backtesting_pending","forecast_units":120.,"parent_wape_pct":14.,"quality_flags":""},
        {"site_id":"SITE_001","product":"diaper","size":"5","week_start":"2026-10-05","method":"naive","wape_pct":None,"wape_reason":"child_level_backtesting_pending","forecast_units":120.,"parent_wape_pct":14.,"quality_flags":""},
        {"site_id":"SITE_002","product":"period_cup","size":"one_size","week_start":"2026-09-28","method":"survey_based","wape_pct":None,"wape_reason":"survey_based","forecast_units":4.,"parent_wape_pct":None,"quality_flags":"undated_survey_retrospective_demo"},
        {"site_id":"SITE_003","product":"period_cup","size":"one_size","week_start":"2026-09-28","method":"naive","wape_pct":None,"wape_reason":"child_level_backtesting_pending","forecast_units":0.,"parent_wape_pct":None,"quality_flags":"trailing_child_history_gap"},
    ])


def report():
    return pd.DataFrame([
        {"site_id":"SITE_001","product":"diaper","size":"5","wape_pct":16.5,"wape_reason":"","evaluated_folds":4,"methods_used":"naive;ses"},
        {"site_id":"SITE_002","product":"period_cup","size":"one_size","wape_pct":70.,"wape_reason":"","evaluated_folds":2,"methods_used":"ma4"},
        {"site_id":"SITE_003","product":"period_cup","size":"one_size","wape_pct":None,"wape_reason":"no_complete_four_week_fold","evaluated_folds":0,"methods_used":"naive"},
    ])


def test_repeated_future_rows_get_historical_pipeline_metric():
    out = attach_child_wape(forecasts(),report())
    assert out.loc[0,"wape_pct"] == out.loc[1,"wape_pct"] == 16.5


def test_survey_never_receives_retrospective_historical_wape():
    out = attach_child_wape(forecasts(),report())
    assert pd.isna(out.loc[2,"wape_pct"])
    assert out.loc[2,"wape_reason"] == "survey_based_no_historical_accuracy"


def test_unbacktestable_series_is_na_with_reason():
    out=attach_child_wape(forecasts(),report())
    assert pd.isna(out.loc[3,"wape_pct"])
    assert out.loc[3,"wape_reason"] == "no_complete_four_week_fold"


def test_point_forecast_and_parent_metric_are_unchanged():
    old=forecasts();new=attach_child_wape(old,report())
    assert new["forecast_units"].tolist()==old["forecast_units"].tolist()
    assert new["parent_wape_pct"].fillna(-1).tolist()==old["parent_wape_pct"].fillna(-1).tolist()
    assert new["quality_flags"].tolist()==old["quality_flags"].tolist()


def test_explanatory_method_list_is_kept_distinct():
    new=attach_child_wape(forecasts(),report())
    assert new.loc[0,"method"] == "naive"
    assert new.loc[0,"audit_methods_used"] == "naive;ses"
    assert "not_current_model" in new.loc[0,"accuracy_evaluation"]


def test_missing_report_series_stays_na():
    out=attach_child_wape(forecasts(),report().iloc[:1])
    assert pd.isna(out.loc[3,"wape_pct"])
    assert out.loc[3,"wape_reason"] == "no_matching_historical_audit"


def test_duplicate_report_keys_rejected():
    r=report();r=pd.concat([r,r.iloc[[0]]],ignore_index=True)
    with pytest.raises(Gate3ReportingError,match="Duplicate"):
        attach_child_wape(forecasts(),r)


def test_negative_audit_error_rejected():
    r=report();r.loc[0,"wape_pct"]=-1
    with pytest.raises(Gate3ReportingError,match="Invalid"):
        attach_child_wape(forecasts(),r)


def test_no_mutation_of_inputs():
    a=forecasts();r=report();_ = attach_child_wape(a,r)
    assert a["wape_pct"].isna().all()
    assert "audit_child_wape_pct" not in r.columns


def test_missing_column_rejected():
    with pytest.raises(Gate3ReportingError,match="Missing"):
        attach_child_wape(forecasts().drop(columns="method"),report())
