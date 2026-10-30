"""Gate 6C focused integration tests; run against repository's REAL Week 2 code."""

from io import BytesIO

import pandas as pd
import pytest

from src.survey_session import (
    INVALIDATE_AFTER_SURVEY_CHANGE,
    SurveyIntakeError,
    canonical_survey_csv,
    normalize_survey_display_values,
    prepare_survey_change,
    read_google_form_csv,
    suggest_google_form_mapping,
    survey_record,
)
from src.workflow import prepare_input


def _core_cleaned():
    # Synthetic and purpose-built: no client data or real practitioner claims.
    history = pd.DataFrame({
        "date": pd.date_range("2026-07-06", periods=12, freq="W-MON"),
        "site_id": ["SITE_001"] * 12,
        "site_name": ["Community Pantry"] * 12,
        "product": ["diaper"] * 12,
        "size": ["4"] * 12,
        "quantity": [100] * 12,
    })
    prepared = prepare_input(history, {c: c for c in history.columns}, "distribution_log")
    return {"distribution_log": prepared}


def _survey(name, *, zip_code="02108", families=15, **more):
    return survey_record(
        site_name=name, zip_code=zip_code, agency_type="pantry",
        families_served_per_month=families, **more
    )


def _run(cleaned, survey, mode="upsert"):
    return prepare_survey_change(
        cleaned, survey, {c: c for c in survey.columns}, mode=mode
    )


def test_google_form_question_mapping_preserves_contract():
    columns = [
        "Timestamp", "Partner agency name", "ZIP code", "Type of agency",
        "Approximately how many families does your organization serve per month?",
        "Approximately what share of your clients are below the federal poverty line?",
    ]
    mapped = suggest_google_form_mapping(columns)
    assert mapped["Timestamp"] is None
    assert mapped["Partner agency name"] == "site_name"
    assert mapped["ZIP code"] == "zip_code"
    assert mapped["Type of agency"] == "agency_type"
    assert mapped[columns[4]] == "families_served_per_month"
    assert mapped[columns[5]] == "poverty_share_band"


def test_google_form_csv_preserves_leading_zero_zip():
    content = "Partner agency name,ZIP code\nEast Side Center,02108\n"
    raw = read_google_form_csv(BytesIO(content.encode("utf-8-sig")))
    assert raw.iloc[0]["ZIP code"] == "02108"


def test_google_display_values_normalize_without_guessing():
    raw = pd.DataFrame([{
        "poverty_share_band": "25% to 50%", "agency_type": "Food pantry",
        "priority_population_flags": "Students, Teen parents",
        "recent_stockout_sizes": "diaper:4, period_pad:regular",
        "children_under_4_per_month": "",
    }])
    result = normalize_survey_display_values(raw)
    assert result.loc[0, "poverty_share_band"] == "25_to_50_percent"
    assert result.loc[0, "agency_type"] == "pantry"
    assert result.loc[0, "priority_population_flags"] == "students;teen_parents"
    assert result.loc[0, "recent_stockout_sizes"] == "diaper:4;period_pad:regular"
    assert pd.isna(result.loc[0, "children_under_4_per_month"])


def test_new_survey_record_reconciles_to_existing_site_id():
    original = _core_cleaned()
    result = _run(original, _survey("Community Pantry", families=85))
    master = result["derived_outputs"].site_master
    assert len(master) == 1
    assert master.iloc[0]["site_id"] == "SITE_001"
    assert int(master.iloc[0]["families_served_per_month"]) == 85
    assert "partner_survey" not in original  # transactional: no mutation


def test_survey_only_new_partner_available_to_cold_start():
    result = _run(_core_cleaned(), _survey("New Shelter"))
    master = result["derived_outputs"].site_master
    row = master.loc[master["site_name"].eq("New Shelter")].iloc[0]
    assert row["site_id"].startswith("AUTO_")
    assert not bool(row["has_distribution_history"])
    assert bool(row["has_survey_data"])


def test_upsert_updates_matching_partner_and_retains_others():
    first = _run(_core_cleaned(), pd.concat([
        _survey("Community Pantry", families=7),
        _survey("New Shelter", families=4),
    ], ignore_index=True))
    updated = _run(first["cleaned_results"], _survey(" community   pantry ", families=88))
    saved = updated["cleaned_results"]["partner_survey"].cleaning_result.dataframe
    assert len(saved) == 2
    assert int(saved.loc[saved.site_name.str.casefold().eq("community pantry"),
                         "families_served_per_month"].iloc[0]) == 88
    assert "New Shelter" in saved.site_name.tolist()


def test_replace_explicitly_discards_old_records():
    first = _run(_core_cleaned(), _survey("Old Site"))
    result = _run(first["cleaned_results"], _survey("New Site"), mode="replace")
    saved = result["cleaned_results"]["partner_survey"].cleaning_result.dataframe
    assert saved.site_name.tolist() == ["New Site"]


def test_invalid_import_has_no_partial_state_change():
    original = _run(_core_cleaned(), _survey("Community Pantry"))["cleaned_results"]
    previous = original["partner_survey"]
    with pytest.raises(SurveyIntakeError):
        _run(original, _survey("New Site", zip_code=""))
    assert original["partner_survey"] is previous


def test_duplicate_rows_rejected_not_silently_dropped():
    two = pd.concat([_survey("Shelter A"), _survey(" shelter a ")], ignore_index=True)
    with pytest.raises(SurveyIntakeError):
        _run(_core_cleaned(), two)


def test_google_csv_integration_to_site_master():
    csv = ("Timestamp,Partner agency name,ZIP code,Type of agency,"
           "Approximately how many families does your organization serve per month?,"
           "Approximately what share of your clients are below the federal poverty line?\n"
           "2026/10/30,New Shelter,02108,WIC clinic,27,Over 75%\n")
    raw = read_google_form_csv(BytesIO(csv.encode("utf-8")))
    result = prepare_survey_change(_core_cleaned(), raw,
                                   suggest_google_form_mapping(raw.columns))
    site = result["derived_outputs"].site_master
    new = site.loc[site.site_name.eq("New Shelter")].iloc[0]
    assert new.zip_code == "02108"
    assert new.agency_type == "wic_clinic"
    assert new.poverty_share_band == "over_75_percent"


def test_export_is_canonical_and_has_no_client_level_fields():
    result = _run(_core_cleaned(), _survey("Community Pantry"))
    csv = canonical_survey_csv(result["cleaned_results"]).decode("utf-8-sig")
    assert "site_name" in csv.splitlines()[0]
    assert "preferred_contact" in csv.splitlines()[0]
    assert "site_id" not in csv.splitlines()[0]


def test_invalidation_covers_forecast_allocation_scenario_and_report():
    for name in ("cp6_forecast_result", "g4_allocation_result", "g5_scenario_result",
                 "g5_purchase_result", "g6_report_pdf"):
        assert name in INVALIDATE_AFTER_SURVEY_CHANGE
