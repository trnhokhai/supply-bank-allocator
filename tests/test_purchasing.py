import pandas as pd
import pytest
from src.purchasing import PurchasingError,optimize_budgeted_purchases,_cents,_whole,_shortest_only


def fixture():
    needs=pd.DataFrame([
        ("A","diaper","5",3),("B","diaper","5",3),
        ("A","diaper","2",3),("B","diaper","2",3)],
        columns=["site_id","product","size","need_units"])
    floors=needs[["site_id","product","size"]].copy()
    floors["fairness_min_units"]=0
    return ({"needs":needs,"supply":pd.DataFrame([("diaper","5",2),("diaper","2",1)],columns=["product","size","available_units"]),
             "equity_weights":{"A":2.0,"B":1.0},"capacities_units":{},"period":{"cycle_weeks":4}},
            {"allocation":floors,"metrics":{"maximum_shortfall_rate":1.0}},
            pd.DataFrame([("diaper","5",1.0,2,"scenario_assumption"),("diaper","2",2.0,3,"scenario_assumption")],
                         columns=["product","size","unit_cost_usd","max_purchase_units","price_basis"]))


def test_budget_and_integral():
    a,b,c=fixture()
    out=optimize_budgeted_purchases(a,b,c,2.0,penalty_share=0,protect_original_fill=False)
    purchases=out["purchases"]
    assert out["spent_cents"]==200
    assert int(purchases.loc[purchases["size"].eq("5"),"purchase_units"].iloc[0])==2
    assert int(purchases.loc[purchases["size"].eq("2"),"purchase_units"].iloc[0])==0
    assert (out["joint_allocation_candidate"].allocated_units>=0).all()
    assert out["certified_primary_mip_gap"]<=1e-5+1e-8


def test_budget_zero_no_purchases():
    a,b,c=fixture(); x=optimize_budgeted_purchases(a,b,c,0,penalty_share=0,protect_original_fill=False)
    assert x["spent_cents"]==0
    assert x["purchases"].purchase_units.sum()==0


@pytest.mark.parametrize("value",[-1,"NaN","inf",True,"2.001","0",None])
def test_invalid_cost(value):
    a,b,c=fixture();c["unit_cost_usd"]=c["unit_cost_usd"].astype(object);c.loc[0,"unit_cost_usd"]=value
    with pytest.raises(PurchasingError):optimize_budgeted_purchases(a,b,c,2)


@pytest.mark.parametrize("value",[-1,"NaN","inf",True,"1.001",None])
def test_invalid_budget(value):
    a,b,c=fixture()
    with pytest.raises(PurchasingError):optimize_budgeted_purchases(a,b,c,value)


def test_duplicate_quotes():
    a,b,c=fixture();c=pd.concat([c,c.iloc[[0]]],ignore_index=True)
    with pytest.raises(PurchasingError):optimize_budgeted_purchases(a,b,c,2)


def test_unknown_sku():
    a,b,c=fixture();c.loc[0,"size"]="unknown"
    with pytest.raises(PurchasingError):optimize_budgeted_purchases(a,b,c,2)


def test_zero_price_never_free():
    with pytest.raises(PurchasingError):_cents(0,"price")
    assert _cents(0,"budget",allow_zero=True)==0


def test_boolean_quantity_rejected():
    with pytest.raises(PurchasingError):_whole(True,"quantity")


def test_protect_original_worst_fill():
    a,b,c=fixture();b["metrics"]["maximum_shortfall_rate"]=.5
    with pytest.raises(PurchasingError):
        optimize_budgeted_purchases(a,b,c,0,protect_original_fill=True,penalty_share=0)


def test_floors_enforced():
    a,b,c=fixture();b["allocation"].loc[0,"fairness_min_units"]=2
    out=optimize_budgeted_purchases(a,b,c,2,protect_original_fill=False)
    plan=out["joint_allocation_candidate"]
    assert (plan.allocated_units>=plan.fairness_min_units).all()


def test_shortest_only_single_sku():
    a,b,c=fixture();_,_,_,_,prices,budget=__import__('src.purchasing',fromlist=['_validate'])._validate(a,b,c,2)
    s=_shortest_only(a,prices,budget)
    assert (s.purchase_units>0).sum()==1
    assert int(s.purchase_cost_cents.sum())<=budget


def test_input_immutable():
    a,b,c=fixture();a0=a["supply"].copy(deep=True);c0=c.copy(deep=True)
    optimize_budgeted_purchases(a,b,c,2,protect_original_fill=False)
    pd.testing.assert_frame_equal(a["supply"],a0)
    pd.testing.assert_frame_equal(c,c0)


def test_capacity_saturated_does_not_waste_budget():
    a,b,c=fixture()
    a["capacities_units"]={"A":0,"B":0}
    out=optimize_budgeted_purchases(a,b,c,100,protect_original_fill=False)
    assert out["spent_cents"]==0
    assert out["purchases"].purchase_units.sum()==0


def test_invalid_price_provenance_rejected():
    a,b,c=fixture();c.loc[0,"price_basis"]="maybe"
    with pytest.raises(PurchasingError):optimize_budgeted_purchases(a,b,c,2)


def test_original_baseline_metrics_unchanged():
    a,b,c=fixture();before=b["metrics"].copy()
    optimize_budgeted_purchases(a,b,c,2,protect_original_fill=False)
    assert b["metrics"]==before


def test_tiny_independent_bruteforce_objective_and_spend():
    """Exhaustive oracle for every integer allocation and priced purchase."""
    from itertools import product
    a,b,c=fixture()
    for budget in [0,1,2,3,4]:
        out=optimize_budgeted_purchases(a,b,c,budget,penalty_share=0,protect_original_fill=False)
        best=None
        for buy5,buy2 in product(range(3),range(4)):
            spent=buy5+2*buy2
            if spent>budget:continue
            for alloc5A,alloc5B,alloc2A,alloc2B in product(range(4),repeat=4):
                if alloc5A+alloc5B>2+buy5 or alloc2A+alloc2B>1+buy2:continue
                unmet_score=(2*(3-alloc5A)+3-alloc5B+2*(3-alloc2A)+3-alloc2B)
                point=(unmet_score,spent)
                if best is None or point<best:best=point
        assert round(out["objective_weighted_unmet"],7)==best[0]
        assert out["spent_cents"]==100*best[1]
