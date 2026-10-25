"""Gate 5, Block 3: budget-limited hypothetical purchasing (no purchase authorization).

The purchase MILP jointly chooses integral quantities by SKU and integral unmet
planning units at each partner. It uses original Gate 4 fairness MINIMA and
weights, an optional protection against worsening the ORIGINAL worst-site fill,
and SciPy/HiGHS. Approved Gate 4 allocation is NEVER modified.

Purchased units are hypothetical future supply, never physical counted inventory,
and may only be used for scenario planning until received and verified.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from time import perf_counter

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

SKU = ["product", "size"]
KEY = ["site_id", "product", "size"]


class PurchasingError(ValueError):
    """Invalid purchasing plan, unsafe assumptions, or uncertified solve."""


def _whole(value, label):
    if isinstance(value, (bool, np.bool_)):
        raise PurchasingError(f"{label} must be a nonnegative whole number.")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PurchasingError(f"{label} must be a nonnegative whole number.") from exc
    if not d.is_finite() or d < 0 or d != d.to_integral_value() or d > 10**12:
        raise PurchasingError(f"{label} must be a nonnegative whole number <= 10^12.")
    return int(d)


def _cents(value, label, allow_zero=False):
    if isinstance(value, (bool, np.bool_)):
        raise PurchasingError(f"{label} must be USD dollars with at most two decimals.")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise PurchasingError(f"{label} must be USD dollars with at most two decimals.") from exc
    if (not d.is_finite() or d < 0 or (not allow_zero and d == 0)
            or d * 100 != (d * 100).to_integral_value() or d > 10**9):
        raise PurchasingError(f"{label} must be positive USD with at most two decimals (zero allowed only for budget).")
    return int(d * 100)


def _unique(frame, keys, label):
    if not isinstance(frame, pd.DataFrame) or not set(keys).issubset(frame.columns):
        raise PurchasingError(f"{label} must contain columns {keys}.")
    if frame[keys].isna().any().any() or frame.duplicated(keys).any():
        raise PurchasingError(f"{label} contains missing or duplicate identifiers.")
    if any(frame[k].astype(str).str.strip().eq("").any() for k in keys):
        raise PurchasingError(f"{label} has empty identifiers.")


def _validate(prepared, original, prices, budget_usd):
    try:
        needs = prepared["needs"][KEY + ["need_units"]].copy()
        supply = prepared["supply"][SKU + ["available_units"]].copy()
        original_allocation = original["allocation"][KEY + ["fairness_min_units"]].copy()
        weights = prepared["equity_weights"]
        capacities = prepared["capacities_units"]
    except (KeyError, TypeError) as exc:
        raise PurchasingError("A valid saved Gate 4 baseline and prepared inputs are required.") from exc
    for f, keys, label in [(needs, KEY, "Needs"), (supply, SKU, "Supply"),
                           (original_allocation, KEY, "Original fairness floors")]:
        _unique(f, keys, label)
        for k in keys:
            f[k] = f[k].astype(str)
    if needs.empty:
        raise PurchasingError("No planning needs found.")
    for f, field in [(needs, "need_units"), (supply, "available_units"),
                     (original_allocation, "fairness_min_units")]:
        f[field] = [_whole(v, field) for v in f[field]]
    if set(map(tuple, needs[KEY].to_numpy())) != set(map(tuple, original_allocation[KEY].to_numpy())):
        raise PurchasingError("Original fairness floors do not match current needs.")
    demand = needs.merge(original_allocation, on=KEY, validate="one_to_one").sort_values(KEY).reset_index(drop=True)
    if (demand["fairness_min_units"] > demand["need_units"]).any():
        raise PurchasingError("Original fairness floor exceeds a partner's planning need.")
    sites = set(demand.site_id)
    if not isinstance(weights, dict) or set(weights) < sites:
        raise PurchasingError("Missing saved equity weights.")
    weights = {s: float(weights[s]) for s in sites}
    if any(not np.isfinite(w) or w < 1 for w in weights.values()):
        raise PurchasingError("Equity weights must be finite and >= 1.")
    if not isinstance(capacities, dict):
        raise PurchasingError("Invalid capacity dictionary.")
    caps = {str(s): _whole(v, "Verified site capacity") for s, v in capacities.items()}
    if set(caps) - sites:
        raise PurchasingError("Unrecognized site capacity key.")
    _unique(prices, SKU, "Purchase quotations")
    if not {"unit_cost_usd", "price_basis"}.issubset(prices.columns) or prices.empty:
        raise PurchasingError("Provide an explicit USD unit cost and price_basis for every quoted SKU.")
    priced = prices.copy()
    if priced["price_basis"].isna().any() or not priced["price_basis"].isin({"verified_quote", "scenario_assumption"}).all():
        raise PurchasingError("price_basis must be verified_quote or scenario_assumption (never imply estimates are quotes).")
    for key in SKU:
        priced[key] = priced[key].astype(str)
    priced["unit_cost_cents"] = [_cents(x, "Unit cost") for x in priced.unit_cost_usd]
    priced["max_purchase_units"] = ([_whole(x, "Max purchasable units") for x in priced.max_purchase_units]
                                     if "max_purchase_units" in priced else [10**12] * len(priced))
    budget_cents = _cents(budget_usd, "Budget", allow_zero=True)
    supply_map = {tuple(x[:2]): int(x[2]) for x in supply.itertuples(index=False, name=None)}
    by_sku = demand.groupby(SKU, sort=True).need_units.sum().to_dict()
    if any(tuple(row) not in by_sku for row in priced[SKU].itertuples(index=False, name=None)):
        raise PurchasingError("A quoted SKU is not part of the forecast planning need.")
    priced["purchase_cap"] = [min(int(max_v), max(0, by_sku[(p, s)] - supply_map.get((p, s), 0)),
                                  budget_cents // int(cost))
                              for p,s,cost,max_v in priced[SKU + ["unit_cost_cents","max_purchase_units"]].itertuples(index=False,name=None)]
    return demand, supply_map, weights, caps, priced.sort_values(SKU).reset_index(drop=True), budget_cents


def optimize_budgeted_purchases(prepared: dict, original_solved: dict,
                                quotes: pd.DataFrame, budget_usd,
                                *, penalty_share: float = 0.01,
                                protect_original_fill: bool = True,
                                time_limit_seconds: int = 6,
                                mip_rel_gap: float = 1e-5) -> dict:
    """Certified joint MIP: purchase quantities, per-site unmet and worst shortfall.

    Original Gate 4 fairness MINIMA remain fixed (not falsely presented as
    dynamically recomputed fairness floors). Actual post-purchase allocation
    must be re-solved through Gate 4, which recomputes its own floors.
    """
    demand, available, weights, capacities, prices, budget = _validate(prepared, original_solved, quotes, budget_usd)
    if (not isinstance(time_limit_seconds, int) or isinstance(time_limit_seconds, bool)
            or time_limit_seconds <= 0 or not isinstance(protect_original_fill, bool)
            or isinstance(penalty_share, bool) or not np.isfinite(penalty_share)
            or penalty_share < 0 or penalty_share > 1
            or not 0 < mip_rel_gap <= 1e-3):
        raise PurchasingError("Invalid solver limits, penalty, protection or gap tolerance.")
    keys = [tuple(x) for x in demand[KEY].itertuples(index=False, name=None)]
    needs = demand.need_units.to_numpy(dtype=int)
    floors = demand.fairness_min_units.to_numpy(dtype=int)
    n = len(keys)
    purchases = [tuple(x) for x in prices[SKU].itertuples(index=False, name=None)]
    m = len(purchases)
    site_names = sorted(set(demand.site_id))
    sku_names = sorted({k[1:] for k in keys})
    by_sku = {sku: [i for i,k in enumerate(keys) if k[1:]==sku] for sku in sku_names}
    by_site = {site: [i for i,k in enumerate(keys) if k[0]==site] for site in site_names}
    purchase_index = {sku:n+j for j,sku in enumerate(purchases)}
    zidx=n+m
    rows,cols,data=[],[],[]
    lower,upper=[],[]
    def constraint(items, low=-np.inf, high=np.inf):
        r=len(lower)
        for i,v in items:
            if v:
                rows.append(r);cols.append(i);data.append(float(v))
        lower.append(float(low));upper.append(float(high))
    for sku,indices in by_sku.items():
        deficit = sum(int(needs[i]) for i in indices) - available.get(sku,0)
        terms = [(i,1) for i in indices]
        if sku in purchase_index: terms.append((purchase_index[sku],1))
        constraint(terms, low=max(0,deficit))
    for site,cap in capacities.items():
        deficit = sum(int(needs[i]) for i in by_site[site]) - cap
        constraint([(i,1) for i in by_site[site]], low=max(0,deficit))
    for site,indices in by_site.items():
        ntotal=sum(int(needs[i]) for i in indices)
        if ntotal: constraint([(i,1) for i in indices]+[(zidx,-ntotal)],high=0)
    cents = prices.unit_cost_cents.to_numpy(dtype=int)
    constraint([(n+j,int(cost)) for j,cost in enumerate(cents)],high=budget)
    weight_vector=np.array([weights[k[0]] for k in keys],dtype=float)
    total_need=int(sum(needs))
    # Lexicographic objective stage 1: EXACT Gate 4 equity + worst-shortfall score.
    # Stage 2: among objectively equivalent outcomes, minimize actual spend.
    objective=np.zeros(n+m+1,dtype=float)
    objective[:n]=weight_vector
    objective[zidx]=penalty_share*total_need
    upper_vars=np.r_[needs-floors,prices.purchase_cap.to_numpy(dtype=int),1.0]
    if protect_original_fill:
        worst=float(original_solved["metrics"]["maximum_shortfall_rate"])
        if not np.isfinite(worst) or not 0<=worst<=1:raise PurchasingError("Original worst-site rate missing or invalid.")
        upper_vars[zidx]=min(1.,worst+1e-9)
    matrix=coo_matrix((data,(rows,cols)),shape=(len(lower),n+m+1)).tocsr()
    variable_integrality=np.r_[np.ones(n+m,dtype=np.int32),0]
    bounds=Bounds(np.zeros(n+m+1),upper_vars)
    def certified_solve(c,mat,lo,hi,label):
        started=perf_counter()
        r=milp(c,integrality=variable_integrality,bounds=bounds,
                constraints=LinearConstraint(mat,np.asarray(lo),np.asarray(hi)),
                options={"time_limit":float(time_limit_seconds),"mip_rel_gap":float(mip_rel_gap)})
        elapsed=perf_counter()-started
        if r.status!=0 or r.x is None:
            raise PurchasingError(f"HiGHS did not certify {label} solution: {r.message}")
        g=getattr(r,"mip_gap",None)
        if g is None or not np.isfinite(g) or g>mip_rel_gap+1e-8:
            raise PurchasingError(f"HiGHS {label} solution lacks a valid gap certificate.")
        return r,elapsed,float(g)
    first,first_seconds,first_gap=certified_solve(objective,matrix,lower,upper,"primary equity")
    # The proven incumbent (not an assumed exact optimum) is a feasible anchor.
    primary_bound=float(objective@first.x)+1e-6
    # Adding one primary-objective constraint prevents cost minimization from
    # trading away material equity / worst-site performance.
    primary_row=coo_matrix(objective.reshape(1,-1)).tocsr()
    from scipy.sparse import vstack
    secondary_matrix=vstack([matrix,primary_row],format="csr")
    spend_objective=np.zeros(n+m+1,dtype=float)
    spend_objective[n:n+m]=cents/max(1,int(max(cents)))
    result,second_seconds,second_gap=certified_solve(spend_objective,secondary_matrix,
                                                     [*lower,-np.inf],[*upper,primary_bound],
                                                     "minimum-spend tie-break")
    if float(objective@result.x)>primary_bound+1e-5:
        raise PurchasingError("Purchasing cost minimization damaged the protected equity objective.")
    elapsed=first_seconds+second_seconds
    gap=first_gap
    x=result.x[:n+m]
    if not np.isfinite(x).all() or np.max(np.abs(x-np.rint(x)))>1e-5:
        raise PurchasingError("Fractional units returned in purchase or unmet plan.")
    integral=np.rint(x).astype(np.int64)
    unmet=integral[:n]
    purchased=integral[n:]
    spent=int(np.dot(cents,purchased))
    if spent>budget or np.any(purchased<0) or np.any(purchased>prices.purchase_cap.to_numpy(dtype=int)):
        raise PurchasingError("Purchase solver broke budget or purchase caps.")
    allocations=needs-unmet
    if (unmet<0).any() or (unmet>needs-floors).any():
        raise PurchasingError("Purchase solver violated original fairness lower bounds.")
    for sku,indices in by_sku.items():
        bought=int(purchased[purchase_index[sku]-n]) if sku in purchase_index else 0
        if int(sum(allocations[indices]))>available.get(sku,0)+bought:
            raise PurchasingError("Purchase solver allocated more than physical and hypothetical supply.")
    for site,indices in by_site.items():
        if site in capacities and int(sum(allocations[indices]))>capacities[site]:
            raise PurchasingError("Purchase solver violated site capacity.")
        site_need=int(sum(needs[indices]))
        if site_need and float(sum(unmet[indices])/site_need)>float(result.x[zidx])+1e-6:
            raise PurchasingError("Purchase solver understated worst-site shortfall.")
    detail=prices[SKU + ["unit_cost_cents", "price_basis"]].copy()
    detail["purchase_units"]=purchased
    detail["purchase_cost_cents"]=detail.unit_cost_cents*detail.purchase_units
    detail["unit_cost_usd"]=detail.unit_cost_cents/100
    detail["purchase_cost_usd"]=detail.purchase_cost_cents/100
    plan=demand[KEY+["need_units","fairness_min_units"]].copy()
    plan["allocated_units"]=allocations
    plan["unmet_units"]=unmet
    return {"purchases":detail, "joint_allocation_candidate":plan,
            "budget_cents":budget,"spent_cents":spent,"remaining_cents":budget-spent,
            "quote_coverage_skus":len(prices),"unpriced_skus_with_gap":int(sum(
                max(0,sum(int(needs[i]) for i in by_sku[sku])-available.get(sku,0))>0
                for sku in sku_names if sku not in purchase_index)),
            "certified_primary_mip_gap":float(gap),"certified_spend_mip_gap":float(second_gap),"solver_backend":"scipy_highs",
            "solver_seconds":elapsed,"equity_solver_seconds":first_seconds,"cost_solver_seconds":second_seconds,"fairness_floor_policy":"saved_gate4_original_lower_bounds",
            "protected_original_worst_fill":protect_original_fill,
            "objective_weighted_unmet":float(np.dot(weight_vector,unmet)),
            "objective_worst_shortfall_rate":float(max((sum(unmet[by_site[s]])/sum(needs[by_site[s]])
                  for s in site_names if sum(needs[by_site[s]])>0),default=0))}


def _shortest_only(prepared, prices, budget_cents):
    """Comparator: spend on one priced SKU with smallest PROJECTED-cycle WOS."""
    needs=prepared["needs"]
    supply={tuple(x[:2]):int(x[2]) for x in prepared["supply"][SKU+["available_units"]].itertuples(index=False,name=None)}
    weeks=int(prepared["period"]["cycle_weeks"])
    demand_total=needs.groupby(SKU).need_units.sum().to_dict()
    ranked=[]
    for row in prices.itertuples(index=False):
        sku=(row.product,row.size)
        demand=int(demand_total.get(sku,0))
        if row.purchase_cap>0 and demand>0:
            projected_wos=weeks*float(supply.get(sku,0))/demand
            ranked.append((projected_wos,sku))
    out=prices[SKU+["unit_cost_cents"]].copy()
    out["purchase_units"]=0
    if ranked:
        _,chosen=min(ranked)
        idx=next(i for i,sku in enumerate(zip(prices["product"],prices["size"])) if sku==chosen)
        out.loc[idx,"purchase_units"]=int(prices.loc[idx,"purchase_cap"])
    out["purchase_cost_cents"]=out.unit_cost_cents*out.purchase_units
    return out


def evaluate_purchase_scenario(baseline:dict, quotes:pd.DataFrame, budget_usd, **options)->dict:
    """Compare joint purchasing versus a one-size heuristic using identical Gate 4 solver.

    This is a hypothetical supply-only what-if; no edits to baseline/stock/picks.
    """
    from src.allocation_inputs import run_operational_allocation
    import copy
    prepared=baseline["prepared"]
    settings=baseline["settings"]
    original=baseline["solved"]
    joint=optimize_budgeted_purchases(prepared,original,quotes,budget_usd,
             penalty_share=float(settings["penalty_share"]),
             protect_original_fill=bool(settings["protect_baseline_fill"]),**options)
    # Rebuild the quote validation (and sorted cap list) for the comparator.
    _,_,_,_,price_table,budget=_validate(prepared,original,quotes,budget_usd)
    shortest=_shortest_only(prepared,price_table,budget)
    def rerun(rows):
        candidate=copy.deepcopy(prepared)
        new_supply=candidate["supply"].copy()
        by_sku={(str(p),str(s)):int(q) for p,s,q in rows[SKU+["purchase_units"]].itertuples(index=False,name=None)}
        for sku,q in by_sku.items():
            match=new_supply["product"].astype(str).eq(sku[0])&new_supply["size"].astype(str).eq(sku[1])
            if not bool(match.any()):
                new_supply.loc[len(new_supply)]=[sku[0],sku[1],q]
            else:
                new_supply.loc[match,"available_units"]+=q
        candidate["supply"]=new_supply
        return run_operational_allocation(candidate,
                fairness_floor=float(settings["fairness_floor"]),
                worst_shortfall_penalty_share=float(settings["penalty_share"]),
                protect_baseline_fill=bool(settings["protect_baseline_fill"]),
                time_limit_seconds=8)
    optimized=rerun(joint["purchases"])
    comparator=rerun(shortest)
    original_metrics=original["metrics"]
    def summary(solved,spent_cents):
        metrics=solved["metrics"]
        physical=int(original_metrics["total_unmet_units"])-int(metrics["total_unmet_units"])
        weighted=float(original_metrics["weighted_unmet_units"])-float(metrics["weighted_unmet_units"])
        dollars=spent_cents/100
        return {"spent_usd":dollars, "allocated_units":int(metrics["total_allocated_units"]),
                "unmet_units":int(metrics["total_unmet_units"]),
                "weighted_unmet_units":float(metrics["weighted_unmet_units"]),
                "worst_site_fill_pct":float(metrics["worst_site_fill_rate"])*100,
                "physical_unmet_reduction_units":physical,
                "equity_weighted_unmet_reduction_units":weighted,
                "physical_reduction_per_usd":physical/dollars if dollars else None,
                "weighted_reduction_per_usd":weighted/dollars if dollars else None}
    joint_spent=joint["spent_cents"]
    shortest_spent=int(shortest.purchase_cost_cents.sum())
    for solved in [optimized,comparator]:
        if int(solved["operational_summary"]["ready_now_units"])>int(prepared["on_hand"].on_hand_units.sum()):
            raise PurchasingError("Hypothetical units leaked into ready-now stock.")
    return {"original_metrics":dict(original_metrics),"joint_model":joint,
            "shortest_size_purchase":shortest,"joint_evaluated":optimized,
            "shortest_evaluated":comparator,
            "joint_summary":summary(optimized,joint_spent),
            "shortest_summary":summary(comparator,shortest_spent),
            "status":"HYPOTHETICAL_PLAN_NOT_PURCHASE_OR_PICK_AUTHORIZATION"}


def assess_purchase_benchmark(joint_summary: dict, shortest_summary: dict,
                              priced_quotes: pd.DataFrame, budget_usd,
                              elapsed_seconds: float, *, atol: float = 1e-8) -> dict:
    """Audit what the one-shortest-SKU test does and DOES NOT establish.

    Gate 5 Brief's specified test is PHYSICAL unmet units reduced per actual
    dollar, not total units or weighted units. Weighted efficiency is a separate
    equity diagnostic. Never infer victory from spending more of the budget.
    """
    j, s = joint_summary, shortest_summary
    metrics = ("spent_usd", "physical_unmet_reduction_units",
               "equity_weighted_unmet_reduction_units")
    for name, item in (("optimized", j), ("shortest-size-only", s)):
        if not isinstance(item, dict):
            raise PurchasingError(f"Missing {name} benchmark summary.")
        for field in metrics:
            v = item.get(field)
            if (not isinstance(v, (float, int, np.floating, np.integer))
                    or isinstance(v, (bool, np.bool_)) or not np.isfinite(v)):
                raise PurchasingError(f"Missing or invalid {name} {field}.")
        if item["spent_usd"] < 0:
            raise PurchasingError(f"{name} spending cannot be negative.")
        # Recompute ratios from source amounts: never trust preformatted UI values.
    budget_cents = _cents(budget_usd, "Budget", allow_zero=True)
    if any(round(float(item["spent_usd"])*100) > budget_cents
           for item in (j, s)):
        raise PurchasingError("Comparison spending exceeds the scenario budget.")
    if not np.isfinite(elapsed_seconds) or elapsed_seconds < 0:
        raise PurchasingError("Invalid end-to-end runtime.")
    def ratio(item, reduction):
        cost = float(item["spent_usd"])
        return float(item[reduction])/cost if cost > 0 else None
    jphysical=ratio(j,"physical_unmet_reduction_units")
    sphysical=ratio(s,"physical_unmet_reduction_units")
    jweighted=ratio(j,"equity_weighted_unmet_reduction_units")
    sweighted=ratio(s,"equity_weighted_unmet_reduction_units")
    compare_valid = jphysical is not None and sphysical is not None
    physical_win = compare_valid and jphysical > 0 and jphysical > sphysical + atol
    weighted_win = (jweighted is not None and sweighted is not None
                    and jweighted > 0 and jweighted > sweighted + atol)
    spend_difference = float(j["spent_usd"]) - float(s["spent_usd"])
    # A mathematical tie is unavoidable when all priced SKUs cost the same
    # and every purchased unit resolves exactly one otherwise-unmet unit.
    uniform_effective_case = False
    if isinstance(priced_quotes, pd.DataFrame) and "unit_cost_usd" in priced_quotes:
        costs = [_cents(v, "Unit cost") for v in priced_quotes.unit_cost_usd]
        if costs and len(set(costs)) == 1 and compare_valid:
            price_cents = costs[0]
            def fully_effective(item):
                return abs(float(item["physical_unmet_reduction_units"]) -
                           float(item["spent_usd"]) * 100 / price_cents) <= 1e-6
            uniform_effective_case = fully_effective(j) and fully_effective(s)
    return {
        "gate5_physical_per_dollar_superior": bool(physical_win),
        "equity_weighted_per_dollar_superior": bool(weighted_win),
        "runtime_under_15_seconds": bool(elapsed_seconds < 15),
        "physical_ratio_comparable": bool(compare_valid),
        "optimized_physical_per_usd": jphysical,
        "shortest_physical_per_usd": sphysical,
        "optimized_weighted_per_usd": jweighted,
        "shortest_weighted_per_usd": sweighted,
        "spend_difference_usd": spend_difference,
        "uniform_cost_full_effectiveness_tie": bool(uniform_effective_case),
        "gate5_per_dollar_and_speed_observed": bool(physical_win and elapsed_seconds < 15),
    }
