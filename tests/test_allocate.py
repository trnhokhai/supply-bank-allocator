"""Focused Block 1 tests for Gate 4: run with python -m pytest -q tests/test_allocate.py."""

import pandas as pd
import pytest

from src.allocate import (
    AllocationError,
    forecast_cycle_needs,
    solve_allocation,
    survey_equity_weights,
)


def _needs():
    return pd.DataFrame({"site_id": ["A", "B"], "product": ["diaper", "diaper"],
                         "size": ["5", "5"], "need_units": [100, 100]})


def _stock(units):
    return pd.DataFrame({"product": ["diaper"], "size": ["5"], "available_units": [units]})


def test_weighted_optimizer_improves_weighted_need_but_may_reduce_worst_fill():
    result = solve_allocation(_needs(), _stock(160), equity_weights={"A": 2, "B": 1},
                              worst_shortfall_penalty_share=0)
    assert result["metrics"]["weighted_unmet_units"] < result["baseline_metrics"]["weighted_unmet_units"]
    assert result["metrics"]["total_allocated_units"] == 160
    assert result["metrics"]["worst_site_fill_rate"] < result["baseline_metrics"]["worst_site_fill_rate"]


def test_severe_shortage_fairness_is_adjusted_not_infeasible():
    result = solve_allocation(_needs(), _stock(80), equity_weights={"A": 2}, fairness_floor=0.6)
    assert result["metrics"]["total_allocated_units"] == 80
    assert result["fairness"].iloc[0]["floor_mode"] == "scarcity_or_integer_adjusted"
    assert result["allocation"]["allocated_units"].ge(result["allocation"]["fairness_min_units"]).all()


def test_no_inventory_creates_no_fictitious_supply():
    result = solve_allocation(_needs(), _stock(0))
    assert result["metrics"]["total_allocated_units"] == 0
    assert result["metrics"]["total_unmet_units"] == 200


def test_sufficient_stock_meets_every_need():
    result = solve_allocation(_needs(), _stock(300))
    assert result["metrics"]["total_allocated_units"] == 200
    assert result["metrics"]["total_unmet_units"] == 0


def test_capacity_applies_to_optimized_and_baseline():
    result = solve_allocation(_needs(), _stock(160), capacities_units={"A": 65})
    for key in ("allocation", "proportional_baseline"):
        plan = result[key]
        assert int(plan.loc[plan.site_id.eq("A"), "allocated_units"].sum()) <= 65
    assert result["baseline_type"] == "capacity_aware_proportional"


def test_infeasible_site_capacity_fails_safely():
    with pytest.raises(AllocationError, match="capacity"):
        solve_allocation(_needs(), _stock(160), capacities_units={"A": 10})


def test_invalid_supply_fails_instead_of_silently_rounding():
    with pytest.raises(AllocationError, match="nonnegative whole"):
        solve_allocation(_needs(), _stock(10.5))


def test_equal_weights_without_survey():
    master = pd.DataFrame({"site_id": ["A", "B"], "poverty_share_band": [None, None]})
    assert survey_equity_weights(master) == {"A": 1.0, "B": 1.0}


def test_survey_weights_are_monotonic_in_poverty_score_and_flags():
    master = pd.DataFrame({"site_id": ["A", "B"],
                           "poverty_share_band": ["under_25_percent", "over_75_percent"],
                           "priority_population_flags": ["students", "students;teen_parents"]})
    weights = survey_equity_weights(master)
    assert weights["B"] > weights["A"] >= 1


def test_integerize_forecast_preserves_rounded_sku_network_total():
    weeks = pd.to_datetime(["2026-09-28", "2026-10-05"])
    f = pd.DataFrame({"site_id": ["A", "B", "A", "B"],
                      "product": ["diaper"]*4, "size": ["5"]*4,
                      "week_start": [weeks[0], weeks[0], weeks[1], weeks[1]],
                      "forecast_units": [1.4, 1.4, 1.4, 1.4],
                      "requires_review": [False]*4})
    result = forecast_cycle_needs(f, 2)
    assert result["need_units"].sum() == 6
    assert result["need_units"].map(lambda x: isinstance(x, int)).all() or result["need_units"].dtype.kind == "i"


def test_integerize_preserves_review_flags():
    w = pd.Timestamp("2026-09-28")
    f = pd.DataFrame({"site_id": ["A"], "product": ["diaper"], "size": ["5"],
                      "week_start": [w], "forecast_units": [12.3], "requires_review": [True]})
    assert bool(forecast_cycle_needs(f, 1).iloc[0]["requires_review"])


def test_same_input_produces_same_allocation():
    args = (_needs(), _stock(160))
    first = solve_allocation(*args, equity_weights={"A": 2})
    second = solve_allocation(*args, equity_weights={"A": 2})
    pd.testing.assert_frame_equal(first["allocation"], second["allocation"])


def test_maximum_shortfall_penalty_can_shift_the_fairness_tradeoff():
    """Benjamin's maximum-shortfall term must actually affect the solution."""
    weights = {"A": 1.05, "B": 1.0}
    weighted_only = solve_allocation(_needs(), _stock(160), equity_weights=weights,
                                      worst_shortfall_penalty_share=0.0)
    balanced = solve_allocation(_needs(), _stock(160), equity_weights=weights,
                                 worst_shortfall_penalty_share=0.04)
    assert balanced["metrics"]["worst_site_fill_rate"] > weighted_only["metrics"]["worst_site_fill_rate"]
    assert balanced["metrics"]["weighted_unmet_units"] >= weighted_only["metrics"]["weighted_unmet_units"]
