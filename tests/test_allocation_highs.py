"""Gate 4: certified HiGHS and baseline-protected production regression tests.

Run alongside existing tests: python -m pytest -q tests/test_allocation_highs.py
"""

import pandas as pd
import pytest

from src.allocate import AllocationError, solve_allocation
from src.allocation_inputs import prepare_allocation_inputs, run_operational_allocation


def need_table():
    return pd.DataFrame({
        "site_id": ["A", "B"], "product": ["diaper", "diaper"],
        "size": ["5", "5"], "need_units": [100, 100],
    })


def stock_table(quantity=160):
    return pd.DataFrame({"product": ["diaper"], "size": ["5"], "available_units": [quantity]})


def check_physical_constraints(result, available):
    for label in ("allocation", "proportional_baseline"):
        rows = result[label]
        assert (rows["allocated_units"] + rows["unmet_units"] == rows["need_units"]).all(), label
        assert (rows["allocated_units"] >= rows["fairness_min_units"]).all(), label
        assert (rows["allocated_units"] >= 0).all(), label
        assert (rows["allocated_units"] <= rows["need_units"]).all(), label
        assert rows["allocated_units"].sum() <= available, label


def test_guarded_highs_protects_baseline_worst_fill():
    result = solve_allocation(need_table(), stock_table(), equity_weights={"A": 2.0, "B": 1.0},
                              worst_shortfall_penalty_share=0.01,
                              protect_baseline_fill=True, solver="highs")
    assert result["solver_backend"] == "scipy_highs"
    assert result["baseline_fill_protection"] is True
    assert 0 <= result["certified_mip_gap"] <= 1e-5 + 1e-8
    assert result["metrics"]["worst_site_fill_rate"] >= result["baseline_metrics"]["worst_site_fill_rate"] - 1e-6
    check_physical_constraints(result, 160)


def test_soft_only_option_preserves_benjamin_tradeoff():
    result = solve_allocation(need_table(), stock_table(), equity_weights={"A": 2.0, "B": 1.0},
                              worst_shortfall_penalty_share=0.0,
                              protect_baseline_fill=False, solver="highs")
    assert result["metrics"]["weighted_unmet_units"] < result["baseline_metrics"]["weighted_unmet_units"]
    assert result["metrics"]["worst_site_fill_rate"] < result["baseline_metrics"]["worst_site_fill_rate"]


def test_increasing_shortfall_penalty_can_improve_worst_site_fill():
    options = {"equity_weights": {"A": 1.05, "B": 1.0}, "solver": "highs"}
    low = solve_allocation(need_table(), stock_table(), worst_shortfall_penalty_share=0.0, **options)
    high = solve_allocation(need_table(), stock_table(), worst_shortfall_penalty_share=0.04, **options)
    assert high["metrics"]["worst_site_fill_rate"] > low["metrics"]["worst_site_fill_rate"]
    assert high["metrics"]["weighted_unmet_units"] >= low["metrics"]["weighted_unmet_units"]


def test_protected_capacity_and_supply_consistent():
    result = solve_allocation(need_table(), stock_table(), equity_weights={"A": 2.0},
                              capacities_units={"A": 65}, protect_baseline_fill=True,
                              solver="highs")
    for label in ("allocation", "proportional_baseline"):
        frame = result[label]
        assert int(frame.loc[frame.site_id.eq("A"), "allocated_units"].sum()) <= 65
    check_physical_constraints(result, 160)


def test_zero_stock_and_abundant_stock():
    for stock in (0, 400):
        result = solve_allocation(need_table(), stock_table(stock), protect_baseline_fill=True)
        assert result["metrics"]["total_allocated_units"] == min(stock, 200)
        check_physical_constraints(result, stock)


def test_solver_backend_rejects_invalid_requests():
    with pytest.raises(AllocationError, match="Unknown solver"):
        solve_allocation(need_table(), stock_table(), solver="made_up")
    with pytest.raises(AllocationError, match="Baseline fill protection"):
        solve_allocation(need_table(), stock_table(), protect_baseline_fill=1)
    with pytest.raises(AllocationError, match="MIP gap"):
        solve_allocation(need_table(), stock_table(), mip_rel_gap=1.0)


def test_pulp_reference_matches_highs_objective_on_small_case():
    # CBC is retained as a reference implementation. This small problem has
    # simple integer optima; compare actual objective values, not variable tie-breaks.
    opts = {"equity_weights": {"A": 1.2, "B": 1.0},
            "protect_baseline_fill": True, "worst_shortfall_penalty_share": 0.01}
    highs = solve_allocation(need_table(), stock_table(), solver="highs", **opts)
    cbc = solve_allocation(need_table(), stock_table(), solver="cbc", **opts)
    assert highs["metrics"]["penalized_objective"] == pytest.approx(
        cbc["metrics"]["penalized_objective"], abs=1e-6)
    check_physical_constraints(highs, 160)
    check_physical_constraints(cbc, 160)


def test_operational_wrapper_defaults_to_protected_highs():
    weeks = pd.date_range("2026-09-28", periods=4, freq="W-MON")
    forecasts = pd.DataFrame([
        {"site_id": site, "product": "diaper", "size": "5", "week_start": date,
         "origin_week": pd.Timestamp("2026-09-21"), "forecast_units": 25.0,
         "requires_review": False, "quality_flags": ""}
        for date in weeks for site in ("A", "B")
    ])
    inventory = pd.DataFrame([{"as_of_date": "2026-09-21", "product": "diaper", "size": "5",
                               "quantity_on_hand": 120, "location": "Main"}])
    master = pd.DataFrame([{"site_id": "A", "site_name": "A Agency"},
                           {"site_id": "B", "site_name": "B Agency"}])
    prepared = prepare_allocation_inputs(forecasts, inventory, None, master)
    result = run_operational_allocation(prepared)
    assert result["baseline_fill_protection"] is True
    assert result["solver_backend"] == "scipy_highs"
    assert result["metrics"]["worst_site_fill_rate"] + 1e-6 >= result["baseline_metrics"]["worst_site_fill_rate"]
    assert result["operational_summary"]["ready_now_units"] <= 120
    assert result["operational_summary"]["awaiting_inbound_units"] == 0
