"""Run in the full project environment: Gate 4 supply policy -> Gate 5 alerts."""

import pandas as pd
import pytest

# The patch is also tested standalone before delivery. This integration test
# runs when the full Week 1–4 project environment is present.
pytest.importorskip("src.allocation_inputs")
from src.allocation_inputs import prepare_allocation_inputs
from src.alerts import build_inventory_alerts


def test_confirmed_arrival_bridge_preserves_pending_unknown_and_cycle_boundaries():
    start = pd.Timestamp("2026-09-28")
    weeks = pd.date_range(start, periods=4, freq="W-MON")
    forecasts = pd.DataFrame([
        {"site_id": "A", "product": "diaper", "size": "5", "week_start": week,
         "origin_week": pd.Timestamp("2026-09-21"), "forecast_units": 100.0,
         "requires_review": False, "quality_flags": ""}
        for week in weeks
    ])
    inventory = pd.DataFrame([
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "5",
         "quantity_on_hand": 150, "location": "Warehouse"}
    ])
    inbound = pd.DataFrame([
        {"expected_date": "2026-09-20", "product": "diaper", "size": "5", "quantity": 1000, "status": "confirmed"},
        {"expected_date": "2026-10-10", "product": "diaper", "size": "5", "quantity": 150, "status": "confirmed"},
        {"expected_date": "2026-10-10", "product": "diaper", "size": "5", "quantity": 900, "status": "pending"},
        {"expected_date": "2026-10-10", "product": "diaper", "size": "unknown", "quantity": 900, "status": "confirmed"},
        {"expected_date": "2026-10-26", "product": "diaper", "size": "5", "quantity": 900, "status": "confirmed"},
    ])
    master = pd.DataFrame([{"site_id": "A", "site_name": "Partner A"}])
    prepared = prepare_allocation_inputs(forecasts, inventory, inbound, master, cycle_weeks=4)
    result = build_inventory_alerts(forecasts, prepared)
    row = result["alerts"].iloc[0]
    assert int(row["on_hand_units"]) == 150
    assert int(row["confirmed_inbound_units"]) == 150
    assert row["on_hand_wos"] == pytest.approx(1.5)
    assert row["cycle_wos"] == pytest.approx(3.0)
    assert row["on_hand_status"] == "short"
    assert row["cycle_status"] == "adequate"  # boundary not a shortage
    warning_codes = set(result["warnings"]["code"])
    assert "allocation_pending_excluded" in warning_codes
    assert "allocation_unresolved_size_excluded" in warning_codes
    assert "allocation_before_snapshot_excluded" in warning_codes
    assert "allocation_after_cycle_excluded" in warning_codes
