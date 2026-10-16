"""Gate 4: model-size regression for exact compact MILP formulation."""

import pandas as pd
import pulp

from src.allocate import _base_model, solve_allocation


def test_one_integer_variable_per_site_sku():
    demand = pd.DataFrame({
        "site_id": ["A", "B", "C"],
        "product": ["diaper"] * 3,
        "size": ["5"] * 3,
        "need_units": [100, 80, 50],
    })
    supply = {("diaper", "5"): 160}
    floors = {(site, "diaper", "5"): 20 for site in demand["site_id"]}
    model, keys, needs, allocation, unmet, by_site = _base_model(
        demand, supply, floors, {}
    )
    model += pulp.lpSum(unmet.values())
    assert len(model.variables()) == len(keys)
    assert all(isinstance(allocation[key], pulp.LpVariable) for key in keys)
    assert all(not isinstance(unmet[key], pulp.LpVariable) for key in keys)
    assert all(allocation[key].lowBound == floors[key] for key in keys)
    assert all(str(needs[key] - allocation[key]) == str(unmet[key]) for key in keys)


def test_compact_solver_still_respects_material_balance_and_baseline():
    needs = pd.DataFrame({
        "site_id": ["A", "B"], "product": ["diaper"] * 2,
        "size": ["5"] * 2, "need_units": [100, 100],
    })
    supply = pd.DataFrame({
        "product": ["diaper"], "size": ["5"], "available_units": [160],
    })
    result = solve_allocation(needs, supply, equity_weights={"A": 2.0, "B": 1.0})
    for name in ("allocation", "proportional_baseline"):
        plan = result[name]
        assert (plan["allocated_units"] + plan["unmet_units"] == plan["need_units"]).all()
        assert plan["allocated_units"].sum() <= 160
        assert (plan["allocated_units"] >= plan["fairness_min_units"]).all()
