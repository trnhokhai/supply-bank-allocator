"""Week 7 CP7.1: provenance integrity, rendered PDF and wiring regression."""

from pathlib import Path

import pytest

from src.provenance import (
    ORIGIN_DEMO,
    ORIGIN_MIXED,
    ORIGIN_UNKNOWN,
    ORIGIN_UPLOADED,
    resolve_report_context,
    survey_source_after_change,
)
from src.report_pdf import DATA_CONTEXT_LABELS, render_funder_pdf
from test_report_pdf import pages, sample_report

ROOT = Path(__file__).resolve().parents[1]


def test_all_demo_and_all_uploaded_have_distinct_conservative_labels():
    cleaned = {"distribution_log": object(), "current_inventory": object()}
    assert resolve_report_context(cleaned, {k: ORIGIN_DEMO for k in cleaned}) == ORIGIN_DEMO
    assert resolve_report_context(cleaned, {k: ORIGIN_UPLOADED for k in cleaned}) == ORIGIN_UPLOADED


def test_mixed_uploaded_and_demo_and_explicitly_mixed_survey():
    cleaned = {"distribution_log": 1, "current_inventory": 2, "partner_survey": 3}
    assert resolve_report_context(cleaned, {
        "distribution_log": ORIGIN_DEMO,
        "current_inventory": ORIGIN_DEMO,
        "partner_survey": ORIGIN_UPLOADED,
    }) == ORIGIN_MIXED
    assert resolve_report_context(cleaned, {k: ORIGIN_MIXED for k in cleaned}) == ORIGIN_MIXED


def test_missing_unrecognized_or_unknown_provenance_fails_conservatively():
    cleaned = {"distribution_log": 1, "current_inventory": 2}
    assert resolve_report_context(cleaned, None) == ORIGIN_UNKNOWN
    assert resolve_report_context(cleaned, {}) == ORIGIN_UNKNOWN
    assert resolve_report_context({}, {}) == ORIGIN_UNKNOWN
    assert resolve_report_context(cleaned, {"distribution_log": ORIGIN_DEMO}) == ORIGIN_UNKNOWN
    assert resolve_report_context(cleaned, {
        "distribution_log": ORIGIN_DEMO, "current_inventory": "verified_real_world"
    }) == ORIGIN_UNKNOWN
    assert resolve_report_context(cleaned, {
        "distribution_log": ORIGIN_UNKNOWN, "current_inventory": ORIGIN_UPLOADED
    }) == ORIGIN_UNKNOWN
    assert resolve_report_context(cleaned, {
        "distribution_log": [], "current_inventory": ORIGIN_UPLOADED
    }) == ORIGIN_UNKNOWN


def test_survey_upsert_and_replace_keep_correct_record_lineage():
    assert survey_source_after_change(ORIGIN_DEMO, mode="upsert", retained_rows=20) == ORIGIN_MIXED
    assert survey_source_after_change(ORIGIN_DEMO, mode="replace", retained_rows=0) == ORIGIN_UPLOADED
    assert survey_source_after_change(ORIGIN_DEMO, mode="upsert", retained_rows=0) == ORIGIN_UPLOADED
    assert survey_source_after_change(ORIGIN_UPLOADED, mode="upsert", retained_rows=3) == ORIGIN_UPLOADED
    assert survey_source_after_change(None, mode="upsert", retained_rows=2) == ORIGIN_UNKNOWN
    assert survey_source_after_change(ORIGIN_MIXED, mode="upsert", retained_rows=4) == ORIGIN_MIXED


@pytest.mark.parametrize("mode,retained", [("append", 1), ("upsert", -1), ("upsert", 1.5), ("upsert", True)])
def test_invalid_survey_update_fails_closed(mode, retained):
    with pytest.raises(ValueError):
        survey_source_after_change(ORIGIN_DEMO, mode=mode, retained_rows=retained)


@pytest.mark.parametrize("label", [ORIGIN_DEMO, ORIGIN_UPLOADED, ORIGIN_MIXED, ORIGIN_UNKNOWN])
def test_pdf_renders_one_page_with_every_approved_source_label(label):
    assert label in DATA_CONTEXT_LABELS
    payload = render_funder_pdf(sample_report(), data_context=label)
    assert payload.startswith(b"%PDF")
    assert pages(payload) == 1


def test_report_page_uses_computed_source_not_a_user_selectable_radio():
    text = (ROOT / "pages" / "6_Report.py").read_text(encoding="utf-8")
    assert "resolve_report_context(cleaned, st.session_state.get(\"input_provenance\"))" in text
    assert "Report data source (shown clearly inside the PDF)" not in text
    assert "output.get(\"data_context\") != data_context" in text


def test_upload_and_survey_recompute_provenance_and_invalidate_old_results():
    upload = (ROOT / "pages" / "1_Upload.py").read_text(encoding="utf-8")
    survey = (ROOT / "pages" / "7_Survey.py").read_text(encoding="utf-8")
    assert 'st.session_state["input_provenance"]' in upload
    assert 'for key in INVALIDATE_AFTER_SURVEY_CHANGE:' in upload
    assert 'st.session_state["input_provenance"] = updated_provenance' in survey
    assert 'survey_source_after_change(' in survey
