"""Independent adversarial checks for Gate 5 purchasing benchmark claims.

Synthetic, small, deterministic fixtures only. The full 4/8-week Demo Mode
outcomes must still be tested in the user's local Streamlit venv.
"""
import copy
import pandas as pd
import pytest

from src.purchasing import (
    optimize_budgeted_purchases, _shortest_only, _validate,
)


def _case(one_shortage=False):
    # Size 5 is SHORTER in projected WOS (0 weeks), but a $2 budget buys
    # far more physical units of shortage size 4 at $0.25 per unit.
    rows = [
        ("A", "diaper", "5", 1), ("B", "diaper", "5", 1),
        ("A", "diaper", "4", 6), ("B", "diaper", "4", 6),
    ]
    need = pd.DataFrame(rows, columns=["site_id", "product", "size", "need_units"])
    floors = need[["site_id", "product", "size"]].copy()
    floors["fairness_min_units"] = 0
    stock = pd.DataFrame([
        ("diaper", "5", 0), ("diaper", "4", 12 if one_shortage else 4),
    ], columns=["product", "size", "available_units"])
    prepared = {"needs": need, "supply": stock,
                "equity_weights": {"A": 2., "B": 1.},
                "capacities_units": {}, "period": {"cycle_weeks": 4}}
    original = {"allocation": floors, "metrics": {"maximum_shortfall_rate": 1.}}
    quotes = pd.DataFrame([
        ("diaper", "5", 1.00, 2, "scenario_assumption"),
        ("diaper", "4", 0.25, 8, "scenario_assumption"),
    ], columns=["product", "size", "unit_cost_usd", "max_purchase_units", "price_basis"])
    return prepared, original, quotes


def test_multi_shortage_joint_buys_more_physical_units_than_shortest_only():
    prep, baseline, quotes = _case()
    before = copy.deepcopy(prep)
    sol = optimize_budgeted_purchases(prep, baseline, quotes, 2.00,
                                      penalty_share=0, protect_original_fill=False)
    *_, priced, budget_cents = _validate(prep, baseline, quotes, 2.00)
    one = _shortest_only(prep, priced, budget_cents)
    assert one.loc[one["size"].eq("5"), "purchase_units"].iloc[0] == 2
    assert one.loc[one["size"].eq("4"), "purchase_units"].iloc[0] == 0
    purchased = sol["purchases"].set_index("size")["purchase_units"].to_dict()
    assert purchased["4"] == 8 and purchased["5"] == 0
    assert sol["spent_cents"] == 200
    assert int(sol["purchases"].purchase_units.sum()) == 8
    assert int(one.purchase_units.sum()) == 2
    assert (sol["joint_allocation_candidate"].allocated_units
            + sol["joint_allocation_candidate"].unmet_units
            == sol["joint_allocation_candidate"].need_units).all()
    pd.testing.assert_frame_equal(prep["supply"], before["supply"])


def test_one_shortage_provides_no_forced_win():
    prep, baseline, quotes = _case(one_shortage=True)
    sol = optimize_budgeted_purchases(prep, baseline, quotes, 2.00,
                                      penalty_share=0, protect_original_fill=False)
    *_, priced, cents = _validate(prep, baseline, quotes, 2.00)
    one = _shortest_only(prep, priced, cents)
    assert sol["spent_cents"] == int(one.purchase_cost_cents.sum())
    assert int(sol["purchases"].purchase_units.sum()) == int(one.purchase_units.sum()) == 2
    assert sol["purchases"].set_index("size").loc["5", "purchase_units"] == 2


def test_more_budget_than_needed_does_not_purchase_surplus():
    prep, baseline, quotes = _case(one_shortage=True)
    sol = optimize_budgeted_purchases(prep, baseline, quotes, 100.,
                                      penalty_share=0, protect_original_fill=False)
    assert sol["spent_cents"] == 200
    assert sol["remaining_cents"] == 9800
    assert int(sol["purchases"].purchase_units.sum()) == 2


def test_neither_unpriced_sku_nor_zero_cost_can_enter_model():
    prep, baseline, quotes = _case()
    partial = quotes[quotes["size"].eq("5")].copy()
    sol = optimize_budgeted_purchases(prep, baseline, partial, 2.,
                                      penalty_share=0, protect_original_fill=False)
    assert sol["unpriced_skus_with_gap"] == 1
    assert sol["purchases"].set_index("size").loc["5", "purchase_units"] == 2


def test_saved_fairness_minima_nontrivial():
    prep, baseline, quotes = _case()
    # Saved applied fair minimums must be respected, not silently replaced by zero.
    baseline["allocation"].loc[
        baseline["allocation"]["site_id"].eq("A")
        & baseline["allocation"]["size"].eq("4"), "fairness_min_units"] = 4
    sol = optimize_budgeted_purchases(prep, baseline, quotes, 2.,
                                      penalty_share=0, protect_original_fill=False)
    p = sol["joint_allocation_candidate"]
    assert (p.allocated_units >= p.fairness_min_units).all()

from src.purchasing import assess_purchase_benchmark, PurchasingError


def _summary(spend, physical, weighted):
    return {"spent_usd": spend, "physical_unmet_reduction_units": physical,
            "equity_weighted_unmet_reduction_units": weighted}


def test_actual_eight_week_flat_price_audit_is_physical_tie_and_weighted_loss():
    # Exact values from user's 8-week Streamlit synthetic validation screenshot.
    optimized = _summary(3000., 15000., 23429.)
    shortest = _summary(183.4, 917., 1569.4375)
    quotes = pd.DataFrame({"unit_cost_usd": [0.20] * 13})
    audit = assess_purchase_benchmark(optimized, shortest, quotes, 3000., 1.57)
    assert audit["uniform_cost_full_effectiveness_tie"]
    assert audit["optimized_physical_per_usd"] == pytest.approx(5.)
    assert audit["shortest_physical_per_usd"] == pytest.approx(5.)
    assert audit["optimized_weighted_per_usd"] == pytest.approx(23429/3000)
    assert not audit["gate5_physical_per_dollar_superior"]
    assert not audit["equity_weighted_per_dollar_superior"]
    assert audit["runtime_under_15_seconds"]
    assert not audit["gate5_per_dollar_and_speed_observed"]
    assert audit["spend_difference_usd"] == pytest.approx(2816.6)


def test_brief_physical_benchmark_is_distinct_from_weighted_equity_diagnostic():
    # Expensive shortest SKU versus affordable alternative; weighted efficiency
    # can be worse even when the Brief's PHYSICAL per-dollar gate is better.
    a = assess_purchase_benchmark(
        _summary(200., 400., 350.), _summary(200., 200., 400.),
        pd.DataFrame({"unit_cost_usd": [0.50, 1.00]}), 200., 2.)
    assert a["gate5_physical_per_dollar_superior"]
    assert not a["equity_weighted_per_dollar_superior"]
    assert a["gate5_per_dollar_and_speed_observed"]
    assert not a["uniform_cost_full_effectiveness_tie"]


def test_spend_zero_or_slow_solution_does_not_create_gate5_pass():
    costs = pd.DataFrame({"unit_cost_usd": [0.25, 1.00]})
    empty = assess_purchase_benchmark(_summary(0., 0., 0.),
                                      _summary(2., 1., 2.), costs, 5., 1.)
    assert not empty["physical_ratio_comparable"]
    assert not empty["gate5_per_dollar_and_speed_observed"]
    slow = assess_purchase_benchmark(_summary(4., 8., 8.),
                                     _summary(1., 1., 2.), costs, 5., 15.)
    assert slow["gate5_physical_per_dollar_superior"]
    assert not slow["gate5_per_dollar_and_speed_observed"]


def test_budget_audit_rejects_invalid_spend():
    with pytest.raises(PurchasingError, match="exceeds the scenario budget"):
        assess_purchase_benchmark(_summary(25., 50., 50.),
                                  _summary(1., 1., 1.),
                                  pd.DataFrame({"unit_cost_usd": [0.5]}), 20., 1.)


def test_negative_reductions_cannot_be_called_gate_improvement():
    a = assess_purchase_benchmark(
        _summary(10., -1., -2.), _summary(10., -5., -8.),
        pd.DataFrame({"unit_cost_usd": [1.0]}), 10., 1.)
    assert not a["gate5_physical_per_dollar_superior"]
    assert not a["equity_weighted_per_dollar_superior"]
    assert not a["gate5_per_dollar_and_speed_observed"]
