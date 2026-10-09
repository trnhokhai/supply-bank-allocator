import numpy as np
import pandas as pd
import pytest
from src.hierarchy import (
    HierarchyError,
    historical_size_mix,
    disaggregate_parent_forecasts,
)


def sample_weekly():
    rows = []
    for week in ["2026-01-05", "2026-01-12"]:
        for product, size, quantity in [
            ("period_pad", "regular", 60),
            ("period_tampon", "regular", 30),
            ("period_pad", "overnight", 10),
        ]:
            rows.append({
                "site_id": "SITE_001",
                "product": product,
                "size": size,
                "week_start": week,
                "quantity": quantity,
                "is_imputed_zero": False,
            })
    return pd.DataFrame(rows)


def test_site_total_mix_preserves_product_identity():
    mix = historical_size_mix(sample_weekly(), "2026-01-12", "site_total")
    assert len(mix) == 3
    regular = mix.loc[mix["size"].eq("regular")]
    assert set(regular["product"]) == {"period_pad", "period_tampon"}
    assert mix["weight"].sum() == pytest.approx(1)
    pad_regular = mix.loc[
        mix["product"].eq("period_pad") & mix["size"].eq("regular"),
        "weight",
    ].iloc[0]
    assert pad_regular == pytest.approx(0.6)


def test_site_product_mix_and_disaggregation_conserve_units():
    mix = historical_size_mix(sample_weekly(), "2026-01-12", "site_product")
    parents = pd.DataFrame([
        dict(site_id="SITE_001", product="period_pad", week_start="2026-01-19", forecast_units=70),
        dict(site_id="SITE_001", product="period_tampon", week_start="2026-01-19", forecast_units=30),
    ])
    out = disaggregate_parent_forecasts(parents, mix, "site_product")
    assert out["forecast_units"].sum() == pytest.approx(100)
    pad = out.loc[out["product"].eq("period_pad")]
    assert pad["forecast_units"].sum() == pytest.approx(70)
    assert set(out["size"]) == {"regular", "overnight"}


def test_site_total_disaggregation_conserves_units():
    mix = historical_size_mix(sample_weekly(), "2026-01-12", "site_total")
    parents = pd.DataFrame([
        dict(site_id="SITE_001", week_start="2026-01-19", forecast_units=137.5),
        dict(site_id="SITE_001", week_start="2026-01-26", forecast_units=88.5),
    ])
    out = disaggregate_parent_forecasts(parents, mix, "site_total")
    actual = out.groupby("week_start")["forecast_units"].sum().sort_index()
    assert actual.tolist() == pytest.approx([137.5, 88.5])


def test_future_does_not_leak_into_historical_mix():
    base = sample_weekly()
    future = base.iloc[[0]].copy()
    future["week_start"] = "2026-01-19"
    future["quantity"] = 100000
    augmented = pd.concat([base, future], ignore_index=True)
    old = historical_size_mix(base, "2026-01-12", "site_total")
    new = historical_size_mix(augmented, "2026-01-12", "site_total")
    pd.testing.assert_frame_equal(old, new)


def test_no_recent_distribution_uses_labeled_historical_mix():
    mix = historical_size_mix(sample_weekly(), "2026-03-02", "site_product", lookback_weeks=2)
    assert mix["mix_source"].eq("full_history_fallback").all()
    assert mix.groupby(["site_id", "product"])["weight"].sum().eq(1.0).all()


def test_cannot_invent_mix_from_all_zero_history():
    data = sample_weekly()
    data["quantity"] = 0
    data["is_imputed_zero"] = True
    with pytest.raises(HierarchyError, match="no positive"):
        historical_size_mix(data, "2026-01-12", "site_total")


def test_disaggregation_rejects_unknown_site():
    mix = historical_size_mix(sample_weekly(), "2026-01-12", "site_total")
    unknown = pd.DataFrame([dict(site_id="SITE_999", week_start="2026-01-19", forecast_units=10)])
    with pytest.raises(HierarchyError, match="No size mix"):
        disaggregate_parent_forecasts(unknown, mix, "site_total")
