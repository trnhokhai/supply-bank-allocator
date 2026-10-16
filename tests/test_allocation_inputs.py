"""Operational allocation adapter: canonical dates, availability, provenance, and pick safety."""

import pandas as pd
import pytest

from src.allocate import AllocationError
from src.allocation_inputs import (
    prepare_allocation_inputs,
    run_operational_allocation,
)


def _tables(weeks=4):
    dates = pd.date_range("2026-09-28", periods=weeks, freq="W-MON")
    forecasts = pd.DataFrame([
        {"site_id": s, "product": "diaper", "size": "5", "week_start": date,
         "origin_week": pd.Timestamp("2026-09-21"), "forecast_units": 10.0,
         "requires_review": False, "quality_flags": "",
         "forecast_source": "site_total_historical", "method": "naive",
         "wape_pct": 12.3, "wape_reason": "observed_panel"}
        for date in dates for s in ("A", "B")
    ])
    inventory = pd.DataFrame([
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "5",
         "quantity_on_hand": 30, "location": "Main"},
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "5",
         "quantity_on_hand": 10, "location": "Secondary"},
    ])
    inbound = pd.DataFrame([
        {"expected_date": "2026-10-02", "product": "diaper", "size": "5",
         "quantity": 20, "status": "confirmed"}
    ])
    master = pd.DataFrame([
        {"site_id": "A", "site_name": "Alpha Pantry", "poverty_share_band": "over_75_percent",
         "priority_population_flags": "students", "storage_capacity_cases": 5},
        {"site_id": "B", "site_name": "Beta Clinic", "poverty_share_band": None,
         "priority_population_flags": None, "storage_capacity_cases": None},
    ])
    return forecasts, inventory, inbound, master


def _prepared(*args, **kwargs):
    return prepare_allocation_inputs(*args, **kwargs)


def test_on_hand_and_only_confirmed_in_cycle_arrivals_count():
    p = _prepared(*_tables())
    assert p["supply"].iloc[0]["available_units"] == 60
    assert p["on_hand"].iloc[0]["on_hand_units"] == 40
    assert p["confirmed_inbound"].iloc[0]["confirmed_inbound_units"] == 20
    assert p["needs"]["need_units"].sum() == 80
    assert p["equity_weights"]["A"] > p["equity_weights"]["B"] == 1.0
    assert p["period"]["cycle_start"] == pd.Timestamp("2026-09-28")
    assert p["period"]["cycle_end"] == pd.Timestamp("2026-10-25")
    assert "cycle_timing" in set(p["warnings"]["code"])


def test_pending_unknown_old_and_late_not_added_or_silently_reassigned():
    f, inv, donor, master = _tables()
    extras = pd.DataFrame([
        {"expected_date": "2026-10-02", "product": "diaper", "size": "5", "quantity": 100, "status": "pending"},
        {"expected_date": "2026-10-05", "product": "diaper", "size": "unknown", "quantity": 200, "status": "confirmed"},
        {"expected_date": "2026-09-21", "product": "diaper", "size": "5", "quantity": 300, "status": "confirmed"},
        {"expected_date": "2026-11-01", "product": "diaper", "size": "5", "quantity": 400, "status": "confirmed"},
    ])
    p = _prepared(f, inv, pd.concat([donor, extras]), master)
    assert int(p["supply"]["available_units"].sum()) == 60
    assert {"pending_excluded", "unresolved_size_excluded", "before_snapshot_excluded", "after_cycle_excluded"}.issubset(set(p["warnings"]["code"]))


def test_no_incoming_is_optional_and_does_not_create_supply():
    f, inv, _, master = _tables()
    p = _prepared(f, inv, None, master)
    assert int(p["supply"]["available_units"].sum()) == 40
    assert "incoming_not_provided" in set(p["warnings"]["code"])


def test_mixed_inventory_snapshot_dates_rejected():
    f, inv, donor, master = _tables()
    inv.loc[0, "as_of_date"] = "2026-09-20"
    with pytest.raises(AllocationError, match="mixed snapshot dates"):
        _prepared(f, inv, donor, master)


def test_inventory_snapshot_after_cycle_rejected():
    f, inv, donor, master = _tables()
    inv["as_of_date"] = "2026-09-29"
    with pytest.raises(AllocationError, match="after the allocation cycle"):
        _prepared(f, inv, donor, master)


def test_forecast_child_missing_one_week_is_not_underestimated():
    f, inv, donor, master = _tables()
    f = f.loc[~(f["site_id"].eq("A") & f["week_start"].eq(pd.Timestamp("2026-10-05")))]
    with pytest.raises(AllocationError, match="missing a cycle week"):
        _prepared(f, inv, donor, master)


def test_forecast_origin_mismatch_rejected():
    f, inv, donor, master = _tables()
    f["origin_week"] = pd.Timestamp("2026-09-14")
    with pytest.raises(AllocationError, match="origin"):
        _prepared(f, inv, donor, master)


def test_forecast_site_missing_from_master_rejected():
    f, inv, donor, master = _tables()
    f.loc[f["site_id"].eq("A"), "site_id"] = "Z"
    with pytest.raises(AllocationError, match="not found"):
        _prepared(f, inv, donor, master)


def test_invalid_incoming_quantity_rejected():
    f, inv, donor, master = _tables()
    donor.loc[0, "quantity"] = 1.5
    with pytest.raises(AllocationError, match="nonnegative whole"):
        _prepared(f, inv, donor, master)


def test_missing_survey_fields_equal_weights_and_unmatched_partners_reported():
    f, inv, donor, master = _tables()
    master = master[["site_id", "site_name"]].copy()
    master.loc[len(master)] = ["C", "New Partner (unforecasted)"]
    p = _prepared(f, inv, donor, master)
    assert p["equity_weights"] == {"A": 1.0, "B": 1.0, "C": 1.0}
    assert "sites_not_forecast" in set(p["warnings"]["code"])


def test_review_flags_and_issues_visible():
    f, inv, donor, master = _tables()
    f.loc[f["site_id"].eq("A"), "requires_review"] = True
    f.loc[f["site_id"].eq("A"), "quality_flags"] = "zero_historical_mix_weight"
    issues = pd.DataFrame([{"site_id": "C", "reason": "missing_history"}])
    p = _prepared(f, inv, donor, master, forecast_issues=issues)
    assert p["review_rows"]["site_id"].tolist() == ["A"]
    assert "zero_historical_mix_weight" in p["review_rows"].iloc[0]["quality_flags"]
    assert {"forecast_review", "unresolved_forecasts"}.issubset(set(p["warnings"]["code"]))


def test_case_storage_capacity_is_not_guessed():
    p = _prepared(*_tables())
    assert p["capacities_units"] == {}
    assert "case_capacity_not_enforced" in set(p["warnings"]["code"])


def test_verified_explicit_unit_caps_forwarded():
    p = _prepared(*_tables(), capacities_units={"A": 35})
    assert p["capacities_units"] == {"A": 35}
    assert "case_capacity_not_enforced" not in set(p["warnings"]["code"])


def test_stale_snapshot_warns_but_does_not_fabricate_current_stock():
    f, inv, donor, master = _tables()
    inv["as_of_date"] = "2026-09-01"
    p = _prepared(f, inv, donor, master)
    assert "stale_inventory" in set(p["warnings"]["code"])
    assert int(p["on_hand"]["on_hand_units"].sum()) == 40


def test_run_operational_allocation_ready_now_never_exceeds_stock(monkeypatch):
    import src.allocation_inputs as module
    p = _prepared(*_tables())
    def fake_solver(needs, supply, **kwargs):
        return {"allocation": pd.DataFrame([
            {"site_id": "A", "product": "diaper", "size": "5", "allocated_units": 40},
            {"site_id": "B", "product": "diaper", "size": "5", "allocated_units": 20},
        ]), "metrics": {"total_allocated_units": 60}}
    monkeypatch.setattr(module, "solve_allocation", fake_solver)
    result = run_operational_allocation(p)
    assert result["operational_summary"] == {
        "allocated_cycle_units": 60,
        "ready_now_units": 40,
        "awaiting_inbound_units": 20,
    }
    assert int(result["ready_now_pick_list"]["ready_now_units"].sum()) == 40
    assert result["allocation"]["ready_now_units"].le(result["allocation"]["allocated_units"]).all()
    assert set(result["ready_now_pick_list"]["site_name"]) == {"Alpha Pantry", "Beta Clinic"}


def test_real_solver_end_to_end_does_not_pick_future_donations():
    p = _prepared(*_tables())
    result = run_operational_allocation(p)
    assert result["metrics"]["total_allocated_units"] == 60
    assert result["operational_summary"]["ready_now_units"] == 40
    assert result["operational_summary"]["awaiting_inbound_units"] == 20
    assert not result["allocation"]["ready_now_units"].gt(result["allocation"]["allocated_units"]).any()


def test_provenance_survives_weekly_to_cycle_conversion():
    p = _prepared(*_tables())
    assert set(p["needs"]["forecast_source"]) == {"site_total_historical"}
    assert set(p["needs"]["method"]) == {"naive"}
    assert set(p["needs"]["wape_pct"]) == {12.3}
