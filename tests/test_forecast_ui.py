"""CP6 Forecast page pure-helper tests. Run with pytest from repo root."""

from io import BytesIO

import pandas as pd
import pytest

from src.forecast_ui import (
    ForecastUIError,
    backtest_method_table,
    data_signature,
    export_forecasts,
    filter_forecasts,
    network_rollup,
    summary,
    validate_forecast_table,
)


def sample():
    rows = []
    for site, product, size, qty in [
        ("S1", "diaper", "5", 10.5),
        ("S1", "period_pad", "regular", 20.0),
        ("S2", "period_tampon", "regular", 5.0),
    ]:
        for date in ["2026-09-28", "2026-10-05"]:
            rows.append({
                "site_id": site, "product": product, "size": size,
                "week_start": pd.Timestamp(date), "forecast_units": qty,
                "method": "naive", "wape_pct": float("nan"),
                "wape_reason": "child_level_backtesting_pending",
                "parent_wape_pct": 12.0, "lower_units": qty * 0.8,
                "upper_units": qty * 1.2, "quality_flags": "",
                "requires_review": False, "forecast_source": "site_total_historical",
            })
    return pd.DataFrame(rows)


def test_exact_canonical_filter_avoids_mix_of_regular_sizes():
    rows = filter_forecasts(sample(), variants=[("period_pad", "regular")])
    assert len(rows) == 2
    assert rows["product"].eq("period_pad").all()


def test_site_filter_and_product_filter_combined():
    rows = filter_forecasts(sample(), sites=["S1"], products=["diaper"])
    assert len(rows) == 2
    assert rows["site_id"].eq("S1").all()


def test_empty_filters_include_all():
    assert len(filter_forecasts(sample())) == 6


def test_rollup_sums_units_without_inventing_intervals():
    result = network_rollup(sample())
    assert len(result) == 6
    assert result["forecast_units"].sum() == pytest.approx(71.0)
    assert "lower_units" not in result.columns


def test_parent_wape_never_copied_to_child_wape():
    rows = sample()
    report = backtest_method_table(rows)
    assert len(report) == 2
    assert set(report["parent_wape_pct"]) == {12.0}
    assert rows["wape_pct"].isna().all()


def test_summary_flags_and_range_counts():
    rows = sample()
    rows.loc[0, "requires_review"] = True
    rows.loc[0, ["lower_units", "upper_units"]] = float("nan")
    m = summary(rows)
    assert m == {"rows": 6, "sites": 2, "variants": 3,
                 "review_rows": 1, "range_rows": 5}


def test_reject_duplicate_forecast_keys():
    x = sample()
    x = pd.concat([x, x.iloc[[0]]], ignore_index=True)
    with pytest.raises(ForecastUIError, match="Duplicate"):
        validate_forecast_table(x)


def test_csv_and_xlsx_exports_readable_and_preserve_na():
    rows = sample()
    csv_data = export_forecasts(rows, "csv")
    xlsx_data = export_forecasts(rows, "xlsx")
    assert csv_data.startswith(b"\xef\xbb\xbf")
    assert len(xlsx_data) > 1000
    assert len(pd.read_csv(BytesIO(csv_data))) == 6
    assert len(pd.read_excel(BytesIO(xlsx_data))) == 6


def test_export_formula_injection_escaped():
    rows = sample()
    rows.loc[0, "site_id"] = "=SUM(A1:A3)"
    data = export_forecasts(rows, "csv").decode("utf-8-sig")
    assert "'=SUM(A1:A3)" in data
    wb = pd.read_excel(BytesIO(export_forecasts(rows, "xlsx")), dtype=str)
    assert wb.loc[0, "site_id"].startswith("'")


def test_signature_detects_new_uploaded_data():
    x = sample()
    master = pd.DataFrame({"site_id": ["S1", "S2"]})
    old = data_signature(x, master)
    changed = x.copy()
    changed.loc[0, "forecast_units"] = 999
    assert data_signature(changed, master) != old
    assert data_signature(x, master) == old
