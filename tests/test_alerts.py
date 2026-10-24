"""Gate 5 Block 1: alerts math and operational safety; no synthetic score-fitting."""
import pandas as pd
import pytest

from src.alerts import AlertsError, build_inventory_alerts


def inputs(*, with_missing=False, with_zero=False):
    dates = pd.date_range("2026-09-28", periods=4, freq="W-MON")
    rates = {"N": 100., "1": 100., "2": 100., "3": 100., "4": 100., "5": 100., "6": 100.}
    if with_zero:
        rates["6"] = 0.
    forecasts = pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": size, "week_start": date,
         "forecast_units": units, "requires_review": size == "6"}
        for size, units in rates.items() for date in dates
    ])
    quantities = {"N": 1600, "1": 1500, "2": 1300, "3": 700, "4": 400, "5": 180, "6": 220}
    if with_missing:
        del quantities["6"]
    on_hand = pd.DataFrame([
        {"product": "diaper", "size": size, "on_hand_units": amount}
        for size, amount in quantities.items()
    ])
    inbound = pd.DataFrame([
        {"product": "diaper", "size": "5", "confirmed_inbound_units": 300},
        {"product": "diaper", "size": "6", "confirmed_inbound_units": 200},
    ])
    prepared = {
        "on_hand": on_hand,
        "confirmed_inbound": inbound,
        "period": {"cycle_start": pd.Timestamp("2026-09-28"),
                   "cycle_end": pd.Timestamp("2026-10-25"), "cycle_weeks": 4,
                   "inventory_as_of": pd.Timestamp("2026-09-21")},
        "warnings": pd.DataFrame([{"code": "cycle_timing", "message": "Do not pick inbound before receipt", "count": 1}]),
    }
    return forecasts, prepared


def look(result, size):
    return result["alerts"].set_index("size").loc[size]


def test_planted_long_and_short_size_flags_are_on_hand_only():
    fc, prepared = inputs()
    out = build_inventory_alerts(fc, prepared)
    assert {"N", "1", "2"}.issubset(set(out["alerts"].query("on_hand_status == 'long'")["size"]))
    assert {"5", "6"}.issubset(set(out["alerts"].query("on_hand_status == 'short'")["size"]))
    assert look(out, "5")["on_hand_wos"] == pytest.approx(1.8)
    assert look(out, "5")["cycle_wos"] == pytest.approx(4.8)
    assert look(out, "5")["cycle_status"] == "adequate"
    assert out["summary"]["on_hand_short"] == 2
    assert out["summary"]["cycle_short"] == 0
    assert "before promising" in look(out, "5")["recommendation"]


def test_threshold_boundary_is_strict():
    fc, prepared = inputs()
    prepared["on_hand"].loc[lambda d: d["size"] == "3", "on_hand_units"] = 300
    prepared["on_hand"].loc[lambda d: d["size"] == "N", "on_hand_units"] = 1200
    out = build_inventory_alerts(fc, prepared)
    assert look(out, "3")["on_hand_status"] == "adequate"  # exactly 3
    assert look(out, "N")["on_hand_status"] == "adequate"  # exactly 12
    change = build_inventory_alerts(fc, prepared, short_weeks=4, long_weeks=11)
    assert look(change, "3")["on_hand_status"] == "short"
    assert look(change, "N")["on_hand_status"] == "long"


def test_missing_inventory_does_not_mean_zero_confirmed_stock():
    fc, prepared = inputs(with_missing=True)
    out = build_inventory_alerts(fc, prepared)
    assert look(out, "6")["on_hand_status"] == "inventory_missing"
    assert pd.isna(look(out, "6")["cycle_wos"])
    assert "physical inventory count" in look(out, "6")["recommendation"]
    assert "diaper" not in set(out["mismatch"]["product"])


def test_zero_demand_is_unassessable_not_infinite_coverage():
    fc, prepared = inputs(with_zero=True)
    out = build_inventory_alerts(fc, prepared)
    assert look(out, "6")["on_hand_status"] == "zero_forecast_review"
    assert pd.isna(look(out, "6")["on_hand_wos"])
    assert pd.isna(look(out, "6")["cycle_wos"])
    assert out["summary"]["unassessable"] == 1


def test_missing_forecast_stock_is_reviewed_not_long():
    fc, prepared = inputs()
    prepared["on_hand"] = pd.concat([
        prepared["on_hand"], pd.DataFrame([{"product": "period_pad", "size": "regular", "on_hand_units": 5000}])
    ], ignore_index=True)
    out = build_inventory_alerts(fc, prepared)
    row = out["alerts"].loc[out["alerts"]["product"] == "period_pad"].iloc[0]
    assert row["on_hand_status"] == "forecast_missing"
    assert pd.isna(row["on_hand_wos"])
    assert set(out["mismatch"]["product"]) == {"diaper"}


def test_mix_index_is_within_product_and_conserves_shares():
    fc, prepared = inputs()
    out = build_inventory_alerts(fc, prepared)
    mix = out["mismatch"]
    assert mix["on_hand_mix_pct"].sum() == pytest.approx(100)
    assert mix["forecast_mix_pct"].sum() == pytest.approx(100)
    assert mix["mismatch_index_pp"].sum() == pytest.approx(0)
    assert mix.loc[mix["size"] == "N", "mismatch_index_pp"].iloc[0] > 0
    assert mix.loc[mix["size"] == "5", "mismatch_index_pp"].iloc[0] < 0


def test_safe_gap_is_in_whole_units():
    fc, prepared = inputs()
    prepared["confirmed_inbound"] = prepared["confirmed_inbound"].iloc[0:0]
    out = build_inventory_alerts(fc, prepared)
    assert look(out, "5")["gap_to_short_threshold_units"] == 120
    assert "120 additional" in look(out, "5")["recommendation"]


@pytest.mark.parametrize("short,long", [(3, 3), (12, 3), (-1, 12), (float("nan"), 12), (3, float("inf")), (True, 12)])
def test_invalid_thresholds_are_rejected(short, long):
    fc, prepared = inputs()
    with pytest.raises(AlertsError, match="Thresholds"):
        build_inventory_alerts(fc, prepared, short_weeks=short, long_weeks=long)


def test_duplicate_supply_and_incomplete_weeks_fail_closed():
    fc, prepared = inputs()
    dup = pd.concat([prepared["on_hand"], prepared["on_hand"].iloc[[0]]], ignore_index=True)
    prepared["on_hand"] = dup
    with pytest.raises(AlertsError, match="Duplicate"):
        build_inventory_alerts(fc, prepared)
    fc, prepared = inputs()
    fc = fc.iloc[1:]
    with pytest.raises(AlertsError, match="omit cycle weeks"):
        build_inventory_alerts(fc, prepared)


def test_inputs_not_modified_and_upstream_supply_warnings_preserved():
    fc, prepared = inputs()
    original = fc.copy(deep=True)
    stock = prepared["on_hand"].copy(deep=True)
    inbound = prepared["confirmed_inbound"].copy(deep=True)
    a = build_inventory_alerts(fc, prepared)
    b = build_inventory_alerts(fc, prepared)
    pd.testing.assert_frame_equal(fc, original)
    pd.testing.assert_frame_equal(prepared["on_hand"], stock)
    pd.testing.assert_frame_equal(prepared["confirmed_inbound"], inbound)
    pd.testing.assert_frame_equal(a["alerts"], b["alerts"])
    assert "allocation_cycle_timing" in set(a["warnings"]["code"])
    assert "forecast_quality" in set(a["warnings"]["code"])


def test_total_units_overflow_is_rejected_instead_of_wrapping_negative():
    fc, prepared = inputs()
    prepared["on_hand"].loc[lambda d: d["size"] == "5", "on_hand_units"] = 2**63 - 1
    with pytest.raises(AlertsError, match="exceeds supported unit range"):
        build_inventory_alerts(fc, prepared)


def test_missing_site_identifiers_are_rejected():
    fc, prepared = inputs()
    fc.loc[0, "site_id"] = None
    with pytest.raises(AlertsError, match="site identifiers"):
        build_inventory_alerts(fc, prepared)


@pytest.mark.parametrize("bad_count", [3.5, "4", True, None])
def test_cycle_duration_must_be_an_integer_without_coercion(bad_count):
    fc, prepared = inputs()
    prepared["period"]["cycle_weeks"] = bad_count
    with pytest.raises(AlertsError, match="whole number"):
        build_inventory_alerts(fc, prepared)


@pytest.mark.parametrize("bad_start, bad_end", [
    ("2026-09-28T12:00:00", "2026-10-25"),
    ("2026-09-28", "2026-10-26"),
    ("2026-09-29", "2026-10-26"),
    ("2026-09-28T00:00:00+00:00", "2026-10-25T00:00:00+00:00"),
    (None, "2026-10-25"),
])
def test_prepared_cycle_rejects_invalid_calendar_dates(bad_start, bad_end):
    fc, prepared = inputs()
    prepared["period"]["cycle_start"] = bad_start
    prepared["period"]["cycle_end"] = bad_end
    with pytest.raises(AlertsError, match="consecutive ISO-week"):
        build_inventory_alerts(fc, prepared)


def test_cycle_calendar_arithmetic_emits_no_timedelta_deprecation_warning():
    import warnings
    fc, prepared = inputs()
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=".*generic.*timedelta.*", category=DeprecationWarning)
        out = build_inventory_alerts(fc, prepared)
    assert out["period"]["cycle_weeks"] == 4


def test_full_cycle_gap_is_actionable_even_when_three_week_threshold_is_met():
    fc, prepared = inputs()
    # On-hand = 180, confirmed inbound = 140, weekly forecast = 100:
    # cycle WOS 3.2 (adequate by the 3-week threshold), but a 4-week
    # planning cycle still needs another 80 units.
    prepared["confirmed_inbound"].loc[
        lambda d: d["size"] == "5", "confirmed_inbound_units"
    ] = 140
    result = build_inventory_alerts(fc, prepared)
    row = look(result, "5")
    assert row["on_hand_status"] == "short"
    assert row["cycle_status"] == "adequate"
    assert row["cycle_wos"] == pytest.approx(3.2)
    assert row["cycle_supply_gap_units"] == 80
    assert "80-unit supply gap" in row["recommendation"]
    assert "4-week planning cycle" in row["recommendation"]
    assert "confirmed inbound" in row["recommendation"]


def test_full_cycle_gap_recommendation_does_not_mutate_or_overstate_on_hand():
    fc, prepared = inputs()
    prepared["confirmed_inbound"].loc[
        lambda d: d["size"] == "5", "confirmed_inbound_units"
    ] = 140
    copy_on_hand = prepared["on_hand"].copy(deep=True)
    copy_inbound = prepared["confirmed_inbound"].copy(deep=True)
    result = build_inventory_alerts(fc, prepared)
    assert look(result, "5")["on_hand_units"] == 180
    assert look(result, "5")["confirmed_inbound_units"] == 140
    pd.testing.assert_frame_equal(prepared["on_hand"], copy_on_hand)
    pd.testing.assert_frame_equal(prepared["confirmed_inbound"], copy_inbound)
