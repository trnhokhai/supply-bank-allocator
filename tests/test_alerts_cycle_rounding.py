"""CP8.3A: Alerts SKU gaps reconcile with integer allocation/report demand."""

import pandas as pd
import pytest

from src.allocate import forecast_cycle_needs
from src.alerts import build_inventory_alerts


def test_fractional_forecast_gap_uses_shared_integer_cycle_need_and_preserves_wos():
    weeks = pd.date_range("2026-09-28", periods=4, freq="W-MON")
    forecast = pd.DataFrame([
        {"site_id": site, "product": "diaper", "size": "4",
         "week_start": week, "forecast_units": 100.05, "requires_review": False}
        for site in ("A", "B") for week in weeks
    ])
    prepared = {
        "on_hand": pd.DataFrame([
            {"product": "diaper", "size": "4", "on_hand_units": 799}
        ]),
        "confirmed_inbound": pd.DataFrame(columns=[
            "product", "size", "confirmed_inbound_units"
        ]),
        "period": {"cycle_start": pd.Timestamp("2026-09-28"), "cycle_end": pd.Timestamp("2026-10-25"),
                   "cycle_weeks": 4, "inventory_as_of": pd.Timestamp("2026-09-21")},
        "warnings": pd.DataFrame(columns=["code", "message", "count"]),
    }
    plan_need = forecast_cycle_needs(forecast, cycle_weeks=4)
    assert float(forecast["forecast_units"].sum()) == pytest.approx(800.4)
    assert int(plan_need["need_units"].sum()) == 800

    out = build_inventory_alerts(forecast, prepared)
    row = out["alerts"].iloc[0]
    assert row["on_hand_status"] == "adequate"
    assert row["cycle_status"] == "adequate"
    assert row["on_hand_wos"] == pytest.approx(799 / 200.1)
    assert row["cycle_wos"] == pytest.approx(799 / 200.1)
    # Old Alerts ceil(800.4 - 799) gave 2, while the saved plan gave 1.
    assert row["cycle_supply_gap_units"] == 1
    assert row["cycle_supply_gap_units"] == max(0, int(plan_need["need_units"].sum()) - 799)
    assert "1-unit supply gap" in row["recommendation"]
