"""Checkpoint 4B fair hierarchy comparison tests."""

import numpy as np
import pandas as pd
import pytest

from src.hierarchy import HierarchyError
from src.hierarchy_eval import APPROACHES, compare_hierarchies
from datetime import timedelta

def example_weekly(weeks=28):
    records = []
    for i, week in enumerate(pd.date_range("2026-01-05", periods=weeks, freq="W-MON")):
        for site, values in [("SITE_001", [40, 20, 10]), ("SITE_002", [50, 30, 10])]:
            for (product, size), quantity in zip(
                [("period_pad", "regular"), ("period_pad", "overnight"),
                 ("period_tampon", "regular")], values
            ):
                records.append({
                    "site_id": site, "product": product, "size": size,
                    "week_start": week, "quantity": quantity + i % 2,
                    "is_imputed_zero": False,
                })
    return pd.DataFrame(records)


def test_three_approaches_common_evaluation_panel():
    data = example_weekly()
    outcome = compare_hierarchies(data, data["week_start"].max())
    assert outcome["summary"]["approach"].tolist() == list(APPROACHES)
    assert len(outcome["rows"]) == 4 * 4 * 6
    assert outcome["rows"]["fold"].nunique() == 4
    assert (outcome["summary"]["scored_rows"] == len(outcome["rows"])).all()
    assert (outcome["summary"]["wape_pct"] >= 0).all()
    assert np.isfinite(outcome["rows"][[f"{a}_units" for a in APPROACHES]].to_numpy()).all()


def test_same_named_sizes_from_different_products_are_not_mixed():
    data = example_weekly()
    out = compare_hierarchies(data, data["week_start"].max())["rows"]
    assert set(out.loc[out["size"] == "regular", "product"]) == {
        "period_pad", "period_tampon"
    }
    assert not out.duplicated(["fold", "week_start", "site_id", "product", "size"]).any()


def test_future_values_do_not_change_old_forecasts():
    data = example_weekly()
    last = data["week_start"].max()
    first = compare_hierarchies(data, last)["rows"]
    altered = data.copy()
    altered.loc[altered["week_start"] == last, "quantity"] = 100000
    second = compare_hierarchies(altered, last)["rows"]
    for method in APPROACHES:
        a = first.loc[first["fold"] == 1, f"{method}_units"].to_numpy()
        b = second.loc[second["fold"] == 1, f"{method}_units"].to_numpy()
        np.testing.assert_allclose(a, b)


def test_missing_actual_week_excluded_for_all_three():
    data = example_weekly()
    final = data["week_start"].max()
    target = final - timedelta(days=7)
    data = data.loc[~(
        data["week_start"].eq(target)
        & data["site_id"].eq("SITE_001")
        & data["product"].eq("period_tampon")
    )]
    out = compare_hierarchies(data, final)["rows"]
    week4 = out.loc[out["fold"].eq(4)]
    assert not ((week4["site_id"] == "SITE_001") &
                (week4["product"] == "period_tampon")).any()
    assert not out["actual_units"].isna().any()


def test_no_future_history_raises_no_fake_forecast():
    data = example_weekly(4)
    out = compare_hierarchies(data, data["week_start"].max())
    assert out["rows"].empty
    assert out["summary"]["wape_pct"].isna().all()


def test_duplicate_series_week_rejected():
    data = example_weekly()
    duplicate = pd.concat([data, data.iloc[[0]]], ignore_index=True)
    with pytest.raises(HierarchyError, match="Invalid canonical"):
        compare_hierarchies(duplicate, data["week_start"].max())
