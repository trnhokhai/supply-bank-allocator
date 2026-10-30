"""Gate 6B: PDF rendering smoke/contract checks with no Cloud browser requirements."""

from datetime import date
from io import BytesIO

import pandas as pd
import pytest

from src.report import ReportError
from src.report_pdf import render_funder_pdf


def sample_report(*, sizes=3, priced=False):
    rows = []
    for i in range(sizes):
        qty = 25 * (i+1)
        is_priced = priced or i == 0
        rows.append({"product": "diaper" if i%2==0 else "period_pad",
                     "size": str(i+1), "supply_gap_units": qty,
                     "unit_cost_usd": 0.25 if is_priced else None,
                     "price_basis": "verified_quote" if is_priced else None,
                     "estimated_cost_usd": qty*0.25 if is_priced else None})
    ask = pd.DataFrame(rows)
    gap = int(ask.supply_gap_units.sum())
    priced_amt = float(sum(row["estimated_cost_usd"] or 0 for row in rows))
    return {
        "periods": {"historical_start": pd.Timestamp("2026-09-07"),
                    "historical_end": pd.Timestamp("2026-11-01"),
                    "forecast_start": pd.Timestamp("2026-11-02"),
                    "forecast_end": pd.Timestamp("2026-12-27"),
                    "forecast_weeks": 8,
                    "inventory_as_of": pd.Timestamp("2026-10-26")},
        "observed": {"units_distributed": 124585, "partners_with_distributions": 25,
                     "record_count": 500,
                     "reported_household_service_count_sum": None,
                     "reported_child_service_count_sum": 482},
        "planning": {"need_units": 200000, "allocated_units": 200000-gap,
                     "modeled_unmet_units": gap, "supply_gap_units": gap,
                     "unresolved_forecast_sites": 0},
        "equity": {"planned_high_need_share_of_all_allocations_pct": 58.42,
                   "classification_coverage_of_allocations_pct": 83.22,
                   "classified_high_need_partners": 10},
        "pricing": {"fully_costed_ask_usd": priced_amt if priced else None,
                    "partially_costed_usd": priced_amt,
                    "all_prices_verified_quotes": bool(priced),
                    "sku_gaps": sizes, "priced_sku_gaps": sizes if priced else 1},
        "ask_by_sku": ask,
    }


def pages(pdf_bytes):
    # Count actual page dictionary markers (not /Pages root); no new PDF
    # parsing runtime dependency needed in the user's project tests.
    import re
    return len(re.findall(rb"/Type\s*/Page\b", pdf_bytes))


def test_tiny_report_renders_one_letter_page():
    data = render_funder_pdf(sample_report(), generated_on=date(2026,10,30))
    assert data.startswith(b"%PDF")
    assert pages(data) == 1
    assert len(data) > 2000


def test_25_site_style_large_report_still_one_page():
    data = render_funder_pdf(sample_report(sizes=24, priced=True), bank_name="Community Essentials Bank", generated_on=date(2026,10,30))
    assert pages(data) == 1
    assert len(data) > 2000


def test_incomplete_dollar_prices_still_generate_without_fake_zero():
    report = sample_report(sizes=6, priced=False)
    assert report["pricing"]["fully_costed_ask_usd"] is None
    assert pages(render_funder_pdf(report)) == 1


def test_empty_ask_has_valid_one_page_report():
    report = sample_report(sizes=3)
    report["ask_by_sku"] = report["ask_by_sku"].iloc[0:0].copy()
    report["planning"]["supply_gap_units"] = 0
    report["planning"]["modeled_unmet_units"] = 0
    report["planning"]["need_units"] = report["planning"]["allocated_units"]
    report["pricing"].update({"sku_gaps":0,"priced_sku_gaps":0, "fully_costed_ask_usd":0, "partially_costed_usd":0.0})
    assert pages(render_funder_pdf(report)) == 1


def test_bad_data_fails_closed():
    bad = sample_report()
    bad["periods"]["forecast_weeks"] = 4
    with pytest.raises(ReportError, match="eight"):
        render_funder_pdf(bad)
    bad = sample_report()
    bad["planning"]["modeled_unmet_units"] += 1
    with pytest.raises(ReportError, match="reconcile"):
        render_funder_pdf(bad)
    bad = sample_report()
    bad["planning"]["supply_gap_units"] += 1
    with pytest.raises(ReportError, match="reconcile"):
        render_funder_pdf(bad)


def test_logo_validation_without_extra_files():
    with pytest.raises(ReportError, match="PNG/JPEG"):
        render_funder_pdf(sample_report(), logo=b"invalid")
    with pytest.raises(ReportError, match="2 MB"):
        render_funder_pdf(sample_report(), logo=b"x"*2_000_001)


def test_user_bank_name_is_not_silently_corrupted():
    with pytest.raises(ReportError, match="unsupported"):
        render_funder_pdf(sample_report(), bank_name="Example 🧸")
    assert pages(render_funder_pdf(sample_report(), bank_name="Ngân hàng Phụ nữ")) == 1


def test_mini_png_logo_success():
    from PIL import Image
    image = Image.new("RGB", (120, 40), (255, 255, 255))
    stream = BytesIO()
    image.save(stream, "PNG")
    assert pages(render_funder_pdf(sample_report(), logo=stream.getvalue())) == 1
