"""Run only on the project's full Windows venv with Week 4 dependencies."""
import copy

import pandas as pd
import pytest

pytest.importorskip("pulp")
from src.allocation_inputs import run_operational_allocation
from src.purchasing import evaluate_purchase_scenario


def test_joint_and_shortest_use_actual_gate4_backend_and_preserve_stock():
    keys=[("A","diaper","5",6),("B","diaper","5",6),
          ("A","diaper","2",6),("B","diaper","2",6)]
    needs=pd.DataFrame(keys,columns=["site_id","product","size","need_units"])
    supply=pd.DataFrame([("diaper","5",8),("diaper","2",8)],columns=["product","size","available_units"])
    on_hand=pd.DataFrame([("diaper","5",5),("diaper","2",5)],columns=["product","size","on_hand_units"])
    prepared={"needs":needs,"supply":supply,"on_hand":on_hand,
              "confirmed_inbound":pd.DataFrame(columns=["product","size","confirmed_inbound_units"]),
              "equity_weights":{"A":2.0,"B":1.0},
              "capacities_units":{},"site_names":{"A":"Partner A","B":"Partner B"},
              "warnings":pd.DataFrame(columns=["code","message","count"]),
              "review_rows":pd.DataFrame(),"forecast_issues":pd.DataFrame(),
              "period":{"cycle_start":pd.Timestamp("2026-09-28"),"cycle_end":pd.Timestamp("2026-10-25"),
                        "inventory_as_of":pd.Timestamp("2026-09-21"),"cycle_weeks":4}}
    settings={"fairness_floor":0.6,"penalty_share":0.01,"protect_baseline_fill":True}
    solved=run_operational_allocation(prepared, fairness_floor=settings["fairness_floor"],
       worst_shortfall_penalty_share=settings["penalty_share"],protect_baseline_fill=True)
    baseline={"prepared":prepared,"solved":solved,"settings":settings}
    before=copy.deepcopy(baseline)
    quotes=pd.DataFrame([("diaper","5",1.00,4,"scenario_assumption"),
                         ("diaper","2",3.00,4,"scenario_assumption")],
      columns=["product","size","unit_cost_usd","max_purchase_units","price_basis"])
    out=evaluate_purchase_scenario(baseline,quotes,4,time_limit_seconds=6)
    assert out["joint_model"]["spent_cents"]<=400
    assert out["joint_evaluated"]["solver_backend"]=="scipy_highs"
    assert out["shortest_evaluated"]["solver_backend"]=="scipy_highs"
    for key in ["joint_evaluated","shortest_evaluated"]:
        plan=out[key]["allocation"]
        assert (plan.ready_now_units<=plan.allocated_units).all()
        assert (plan.ready_now_units>=0).all()
        assert (plan.awaiting_inbound_units>=0).all()
        assert (plan.ready_now_units+plan.awaiting_inbound_units==plan.allocated_units).all()
        assert plan.ready_now_units.sum()<=on_hand.on_hand_units.sum()
        # Hypothetical purchases NEVER become counted/ready stock, even if
        # aggregate stock across different SKUs would otherwise mask leakage.
        actual=on_hand.set_index(["product","size"]).on_hand_units.to_dict()
        for sku,group in plan.groupby(["product","size"]):
            assert int(group.ready_now_units.sum())<=int(actual.get(tuple(sku),0))
    pd.testing.assert_frame_equal(baseline["prepared"]["supply"],before["prepared"]["supply"])
    pd.testing.assert_frame_equal(baseline["prepared"]["on_hand"],before["prepared"]["on_hand"])
    assert out["status"]=="HYPOTHETICAL_PLAN_NOT_PURCHASE_OR_PICK_AUTHORIZATION"
