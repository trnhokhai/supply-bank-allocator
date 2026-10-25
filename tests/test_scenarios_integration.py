"""True Gate 4 + Alerts integration; run inside complete repo with pinned .venv."""

import ast
from pathlib import Path

import pandas as pd
import pytest

from src.scenarios import run_counterfactual

# Do not fake the optimizer. A missing dependency outside the Windows project
# makes this integration test unavailable, not 'passed'.
pytest.importorskip("pulp")
from src.allocation_inputs import prepare_allocation_inputs, run_operational_allocation
from src.allocation_ui import input_signature


def _inputs():
    weeks = pd.date_range("2026-09-28", periods=4, freq="W-MON")
    forecasts = pd.DataFrame([
        {"site_id": site, "product": "diaper", "size": size,
         "week_start": week, "origin_week": pd.Timestamp("2026-09-21"),
         "forecast_units": float(quantity), "requires_review": False, "quality_flags": ""}
        for site, values in (("A", {"1": 20, "5": 10}), ("B", {"1": 12, "5": 24}))
        for week in weeks for size, quantity in values.items()
    ])
    stock = pd.DataFrame([
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "1", "quantity_on_hand": 50, "location": "Main"},
        {"as_of_date": "2026-09-21", "product": "diaper", "size": "5", "quantity_on_hand": 30, "location": "Main"},
    ])
    incoming = pd.DataFrame([
        {"expected_date": "2026-10-02", "source": "Donation A", "product": "diaper", "size": "1", "quantity": 30, "status": "confirmed"},
        {"expected_date": "2026-10-03", "source": "Donation A", "product": "diaper", "size": "5", "quantity": 12, "status": "pending"},
    ])
    site_master = pd.DataFrame([
        {"site_id": "A", "site_name": "Alpha", "families_served_per_month": 100,
         "agency_type": "school", "has_distribution_history": True, "has_survey_data": True,
         "poverty_share_band": "under_25_percent", "priority_population_flags": ""},
        {"site_id": "B", "site_name": "Beta", "families_served_per_month": 120,
         "agency_type": "school", "has_distribution_history": True, "has_survey_data": True,
         "poverty_share_band": "over_75_percent", "priority_population_flags": "students"},
    ])
    return forecasts, stock, incoming, site_master


def _baseline(fr, stock, incoming, master):
    prepared = prepare_allocation_inputs(fr, stock, incoming, master, cycle_weeks=4)
    solved = run_operational_allocation(prepared, protect_baseline_fill=True)
    settings = {"cycle_weeks": 4, "alpha": .5, "beta": .25,
                "fairness_floor": .6, "penalty_share": .01, "protect_baseline_fill": True}
    return {"prepared": prepared, "solved": solved, "settings": settings,
            "signature": input_signature(fr, stock, incoming, master)}


@pytest.mark.parametrize("kind,params", [
    ("source_change", {"sources": ["Donation A"], "change_pct": -50}),
    ("pending_confirmed", {}),
    ("size_mix", {"product": "diaper", "from_size": "1", "to_size": "5", "shift_pct": 25}),
    ("new_partner", {"name": "Third Pantry", "families": 60, "agency_type": "school", "acknowledged": True}),
])
def test_reuses_real_allocation_backend_and_preserves_baseline(kind, params):
    forecasts, stock, incoming, master = _inputs()
    fc_original, stock_original, incoming_original, master_original = [t.copy(deep=True) for t in (forecasts, stock, incoming, master)]
    baseline = _baseline(forecasts, stock, incoming, master)
    before = baseline["solved"]["allocation"].copy(deep=True)
    result = run_counterfactual(forecasts, stock, incoming, master, baseline, kind=kind, params=params)
    assert set(result["comparison"]["metric"]) == {
        "total_allocated_units", "total_unmet_units", "weighted_unmet_units", "worst_site_fill_rate"
    }
    assert set(result["coverage"].columns) == {
        "product", "size", "original_cycle_wos", "original_cycle_gap_units",
        "scenario_cycle_wos", "scenario_cycle_gap_units",
    }
    audit = result["demand_audit"]
    assert int(result["prepared"]["needs"]["need_units"].sum()) == audit["scenario_integer_need_units"]
    assert int(baseline["prepared"]["needs"]["need_units"].sum()) == audit["original_integer_need_units"]
    if kind in {"source_change", "pending_confirmed", "size_mix"}:
        assert audit["expected_delta_units"] == pytest.approx(0, abs=1e-6)
        assert abs(audit["integer_need_delta_units"]) <= (1 if kind == "size_mix" else 0)
    assert result["solved"]["baseline_fill_protection"] is True
    assert result["solved"]["metrics"]["worst_site_fill_rate"] + 1e-6 >= result["solved"]["baseline_metrics"]["worst_site_fill_rate"]
    plan = result["solved"]["allocation"]
    assert (plan["allocated_units"] >= 0).all()
    assert (plan["allocated_units"] + plan["unmet_units"] == plan["need_units"]).all()
    pd.testing.assert_frame_equal(forecasts, fc_original)
    pd.testing.assert_frame_equal(stock, stock_original)
    pd.testing.assert_frame_equal(incoming, incoming_original)
    pd.testing.assert_frame_equal(master, master_original)
    pd.testing.assert_frame_equal(before, baseline["solved"]["allocation"])
    # Physical on-hand stock remains the exact same data in every scenario.
    pd.testing.assert_frame_equal(baseline["prepared"]["on_hand"], result["prepared"]["on_hand"])


def test_no_incompatible_keyword_in_scenario_page():
    root = Path(__file__).resolve().parents[1]
    source = (root / "pages" / "5_Scenarios.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    calls = [x for x in ast.walk(tree) if isinstance(x, ast.Call)
             and isinstance(x.func, ast.Name) and x.func.id == "run_counterfactual"]
    assert len(calls) == 1
    assert not any(k.arg is None for k in calls[0].keywords)
    assert {k.arg for k in calls[0].keywords} == {"kind", "params"}
