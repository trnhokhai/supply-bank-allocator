"""Gate 6D readiness checks; cloud deployment itself needs live validation."""

from pathlib import Path

import pytest

from src.report import ReportError
from src.report_pdf import DATA_CONTEXT_LABELS, render_funder_pdf
from test_report_pdf import pages, sample_report


ROOT = Path(__file__).resolve().parents[1]


def test_home_is_lightweight_and_links_to_actual_pages():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "st.set_page_config" in source
    assert "Demo Mode" in source
    assert "synthetic" in source.lower()
    assert "third-party service" in source
    assert "from src.forecast" not in source
    assert "from src.allocate" not in source
    for target in ("1_Upload", "2_Forecast", "3_Allocate", "6_Report", "7_Survey"):
        assert f"pages/{target}.py" in source


def test_home_downloads_existing_four_blank_csv_templates():
    # Run on the full local project (not a standalone ZIP extraction) so
    # missing templates block a deceptive public launch.
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for dataset in ("distribution_log", "current_inventory", "incoming_supply", "partner_survey"):
        filename = f"{dataset}_template.csv"
        assert filename in source
        assert (ROOT / "src" / "templates" / filename).is_file()


def test_report_page_discloses_origin_and_passes_it_to_pdf():
    source = (ROOT / "pages" / "6_Report.py").read_text(encoding="utf-8")
    assert 'resolve_report_context(cleaned, st.session_state.get("input_provenance"))' in source
    assert "Report data source (shown clearly inside the PDF)" not in source
    assert "data_context=data_context" in source
    assert '"data_context": data_context' in source
    assert "synthetic" in source.lower()


def test_rendered_pdf_differs_by_label_and_stays_one_page():
    a = render_funder_pdf(sample_report(), data_context="synthetic_demo")
    b = render_funder_pdf(sample_report(), data_context="user_supplied_unverified")
    assert a.startswith(b"%PDF") and b.startswith(b"%PDF")
    assert a != b
    assert pages(a) == 1
    assert pages(b) == 1
    assert "synthetic_demo" in DATA_CONTEXT_LABELS


def test_unrecognized_data_source_fails_closed():
    with pytest.raises(ReportError, match="data-source"):
        render_funder_pdf(sample_report(), data_context="field_verified")


def test_all_high_need_equity_stays_renderable():
    report = sample_report()
    report["planning"]["modeled_partners"] = 25
    report["equity"]["classified_high_need_partners"] = 25
    report["equity"]["unknown_classification_partners"] = 0
    report["equity"]["planned_high_need_share_of_all_allocations_pct"] = 100.0
    report["equity"]["classification_coverage_of_allocations_pct"] = 100.0
    assert render_funder_pdf(report, data_context="synthetic_demo").startswith(b"%PDF")


def test_new_app_and_report_source_compile():
    for filename in ("app.py", "src/report_pdf.py", "pages/6_Report.py"):
        compile((ROOT / filename).read_text(encoding="utf-8"), filename, "exec")
