"""Gate 5 counterfactual planning on copies of validated Gate 4 inputs.

Only Gate 4 prepares physical availability and solves integer allocations.
These are prospective planning assumptions, never updates to a warehouse
snapshot, a recorded forecast, or a confirmed operational commitment.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from math import isfinite
from time import perf_counter

import numpy as np
import pandas as pd

SKU = ["product", "size"]
CHILD = ["site_id", "product", "size"]
KEY = CHILD + ["week_start"]
KINDS = {"source_change", "pending_confirmed", "size_mix", "new_partner"}


class ScenarioError(ValueError):
    """The proposed counterfactual cannot be represented safely."""


def _required(table, fields, name):
    if not isinstance(table, pd.DataFrame) or not set(fields).issubset(table.columns):
        raise ScenarioError(f"{name} requires a cleaned table with {sorted(fields)}.")


def _period(baseline):
    try:
        period = baseline["prepared"]["period"]
        settings = baseline["settings"]
        if int(settings["cycle_weeks"]) != int(period["cycle_weeks"]):
            raise ScenarioError("Baseline cycle settings disagree with prepared inventory.")
        return period
    except (KeyError, TypeError, ValueError) as exc:
        raise ScenarioError("Run and retain a valid Gate 4 allocation baseline first.") from exc


def _eligible_in_cycle(frame, period, status):
    if frame is None:
        return pd.Series(dtype=bool)
    _required(frame, ["expected_date", "source", "product", "size", "quantity", "status"], "Incoming")
    date = pd.to_datetime(frame["expected_date"], errors="coerce")
    if date.isna().any():
        raise ScenarioError("Incoming dates must be valid before scenario selection.")
    return (
        frame["status"].eq(status)
        & date.gt(pd.Timestamp(period["inventory_as_of"]))
        & date.le(pd.Timestamp(period["cycle_end"]))
        & frame["size"].ne("unknown")
    )


def _rounded_units(units, multiplier):
    try:
        number = Decimal(str(units))
        result = int((number * multiplier).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, TypeError, ValueError, OverflowError) as exc:
        raise ScenarioError("Cannot adjust an invalid individual-unit quantity.") from exc
    if number != number.to_integral_value() or number < 0 or result < 0 or result > np.iinfo(np.int64).max:
        raise ScenarioError("Scenario incoming quantities must be nonnegative whole units.")
    return result


def change_source_supply(incoming, period, sources, change_pct):
    """Scale ONLY explicitly selected confirmed sources within the current cycle.

    Source names are staff-reviewed, not inferred to be 'donations' from
    free-text names. Per-record rounding is deterministic half-up.
    """
    _required(incoming, ["expected_date", "source", "product", "size", "quantity", "status"], "Incoming")
    if not isinstance(sources, (list, tuple, set)) or not sources or any(not isinstance(s, str) or not s.strip() for s in sources):
        raise ScenarioError("Select one or more explicitly identified incoming sources.")
    if isinstance(change_pct, (bool, np.bool_)) or not isinstance(change_pct, (int, float)) or not isfinite(change_pct) or not -50 <= change_pct <= 50:
        raise ScenarioError("Source change must be a finite percentage from -50 to +50.")
    scaled = incoming.copy(deep=True)
    mask = _eligible_in_cycle(scaled, period, "confirmed") & scaled["source"].isin(sources)
    if not mask.any():
        raise ScenarioError("No selected source has eligible confirmed units in this cycle.")
    multiplier = Decimal("1") + Decimal(str(change_pct)) / Decimal("100")
    before = scaled.loc[mask, "quantity"].tolist()
    after = [_rounded_units(q, multiplier) for q in before]
    scaled.loc[mask, "quantity"] = after
    delta = sum(after) - sum(int(q) for q in before)
    return scaled, {"eligible_rows": int(mask.sum()), "changed_inbound_units": int(delta), "selected_sources": sorted(set(sources))}


def assume_pending_confirmed(incoming, period):
    """Promote only eligible, known-size pending rows in a SCENARIO copy."""
    _required(incoming, ["expected_date", "source", "product", "size", "quantity", "status"], "Incoming")
    promoted = incoming.copy(deep=True)
    mask = _eligible_in_cycle(promoted, period, "pending")
    if not mask.any():
        raise ScenarioError("There are no eligible known-size pending arrivals in this cycle.")
    amounts = pd.to_numeric(promoted.loc[mask, "quantity"], errors="coerce")
    if amounts.isna().any() or not np.isfinite(amounts.to_numpy(dtype=float)).all() or amounts.lt(0).any() or not amounts.eq(np.floor(amounts)).all():
        raise ScenarioError("Pending arrivals have invalid individual-unit quantities.")
    promoted.loc[mask, "status"] = "confirmed"
    return promoted, {"assumed_confirmed_rows": int(mask.sum()), "assumed_inbound_units": int(amounts.sum())}


def shift_forecast_mix(forecasts, product, source_size, target_size, shift_pct, period):
    """Transfer a fraction of one size's point forecast within each site/week.

    Require both size rows for every affected site/week. Preserve each
    site-product-week total, never extrapolate a size or fake backtest error.
    """
    _required(forecasts, KEY + ["forecast_units", "requires_review"], "Forecast")
    if source_size == target_size or not all(isinstance(x, str) and x.strip() for x in (product, source_size, target_size)):
        raise ScenarioError("Choose two different canonical sizes within one product.")
    if isinstance(shift_pct, (bool, np.bool_)) or not isinstance(shift_pct, (int, float)) or not isfinite(shift_pct) or not 0 < shift_pct <= 50:
        raise ScenarioError("Size-mix shift must be greater than 0% and at most 50%.")
    result = forecasts.copy(deep=True)
    dates = pd.to_datetime(result["week_start"], errors="coerce")
    selected = dates.between(pd.Timestamp(period["cycle_start"]), pd.Timestamp(period["cycle_end"])) & result["product"].eq(product)
    source = selected & result["size"].eq(source_size)
    target = selected & result["size"].eq(target_size)
    if not source.any() or not target.any():
        raise ScenarioError("Both sizes need existing canonical forecasts within the selected cycle.")
    from_keys = set(map(tuple, result.loc[source, ["site_id", "week_start"]].itertuples(index=False, name=None)))
    to_keys = set(map(tuple, result.loc[target, ["site_id", "week_start"]].itertuples(index=False, name=None)))
    if from_keys != to_keys or result.loc[source | target, KEY].duplicated().any():
        raise ScenarioError("Size-mix transfer needs exactly one row for both sizes in every affected site/week.")
    before_total = float(pd.to_numeric(result.loc[selected, "forecast_units"]).sum())
    fraction = float(shift_pct) / 100
    values = pd.to_numeric(result.loc[source, "forecast_units"], errors="coerce")
    if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all() or values.lt(0).any():
        raise ScenarioError("Cannot shift negative or invalid forecast units.")
    move = result.loc[source, ["site_id", "week_start"]].copy()
    move["transfer_units"] = values.to_numpy(dtype=float) * fraction
    if move["transfer_units"].sum() <= 0:
        raise ScenarioError("Selected source-size forecast has no positive volume to transfer.")
    target_rows = result.loc[target, ["site_id", "week_start"]].merge(move, on=["site_id", "week_start"], validate="one_to_one", sort=False)
    if len(target_rows) != int(target.sum()):
        raise ScenarioError("Size-mix transfer cannot match target rows unambiguously.")
    increments = dict(zip(map(tuple, move[["site_id", "week_start"]].itertuples(index=False, name=None)), move["transfer_units"]))
    source_values = result.loc[source, "forecast_units"].to_numpy(dtype=float) * (1-fraction)
    target_values = result.loc[target, "forecast_units"].to_numpy(dtype=float) + [increments[(row.site_id, row.week_start)] for row in result.loc[target, ["site_id", "week_start"]].itertuples(index=False)]
    result.loc[source, "forecast_units"] = source_values
    result.loc[target, "forecast_units"] = target_values
    touched = source | target
    result.loc[touched, "requires_review"] = True
    if "quality_flags" in result:
        result.loc[touched, "quality_flags"] = result.loc[touched, "quality_flags"].fillna("").astype(str).map(lambda v: (v + ";" if v else "") + "scenario_size_mix_assumption")
    if "forecast_source" in result:
        result.loc[touched, "forecast_source"] = "scenario_adjusted_point_forecast"
    # Historical accuracy/bands refer to the pre-scenario forecast, not to a
    # hand-adjusted child mix. Clear their numeric claims for affected rows.
    for uncalibrated in ("wape_pct", "parent_wape_pct", "lower_units", "upper_units",
                         "parent_bias_pct", "parent_backtest_folds"):
        if uncalibrated in result:
            result.loc[touched, uncalibrated] = np.nan
    if "wape_reason" in result:
        result.loc[touched, "wape_reason"] = "scenario_shift_not_backtested"
    if "forecast_status" in result:
        result.loc[touched, "forecast_status"] = "provisional_scenario"
    if "method" in result:
        result.loc[touched, "method"] = "assumed_size_mix_shift"
    after_total = float(pd.to_numeric(result.loc[selected, "forecast_units"]).sum())
    if not np.isclose(before_total, after_total, rtol=1e-11, atol=1e-6) or (result["forecast_units"] < 0).any():
        raise ScenarioError("Size-mix transfer failed network demand conservation.")
    return result, {"transferred_expected_units": float(move["transfer_units"].sum()), "affected_site_weeks": len(from_keys), "demand_total_conserved": True,
                    "conservation_basis": "fractional_forecast_before_product_size_integer_rounding"}


def prospective_partner(forecasts, master, period, *, site_id=None, name=None, families=None, agency_type=None, acknowledged=False):
    """Generate transparent scenario-only needs from current peer forecasts.

    No retrospective survey date is asserted. An existing survey-only partner
    or a hypothetical survey-like profile can be evaluated prospectively, but
    the result is never represented as a leakage-safe backtested forecast.
    """
    _required(master, ["site_id", "site_name", "families_served_per_month", "agency_type"], "Site master")
    _required(forecasts, KEY + ["forecast_units", "requires_review"], "Forecast")
    if acknowledged is not True:
        raise ScenarioError("Acknowledge the provisional prospective survey assumption before solving.")
    fc = forecasts.copy(deep=True)
    sites = master.copy(deep=True)
    if site_id is not None:
        hits = sites.loc[sites["site_id"].astype(str).eq(str(site_id))]
        if len(hits) != 1 or str(site_id) in set(fc["site_id"].astype(str)):
            raise ScenarioError("Choose one survey-only partner not already included in the baseline forecast.")
        partner = hits.iloc[0]
        if bool(partner.get("has_distribution_history", False)):
            raise ScenarioError("A new-partner scenario cannot duplicate a partner with distribution history.")
        target_id, target_name = str(partner["site_id"]), str(partner["site_name"])
        families, agency_type = partner["families_served_per_month"], partner["agency_type"]
    else:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ScenarioError("Enter a prospective partner name (1–100 characters).")
        target_name = name.strip()
        if target_name.casefold() in set(sites["site_name"].astype(str).str.strip().str.casefold()):
            raise ScenarioError("This partner name already exists in the site master.")
        target_id = "scenario_" + sha256(target_name.casefold().encode("utf-8")).hexdigest()[:12]
        if target_id in set(sites["site_id"].astype(str)):
            raise ScenarioError("Prospective partner ID conflicts with an existing partner.")
        row = {c: pd.NA for c in sites.columns}
        row.update({"site_id": target_id, "site_name": target_name,
                    "families_served_per_month": families, "agency_type": agency_type,
                    "has_distribution_history": False, "has_survey_data": True})
        sites = pd.concat([sites, pd.DataFrame([row])], ignore_index=True)
    try:
        family_value = float(families)
    except (TypeError, ValueError) as exc:
        raise ScenarioError("Prospective monthly families must be a positive whole number.") from exc
    if not np.isfinite(family_value) or family_value <= 0 or family_value != int(family_value):
        raise ScenarioError("Prospective monthly families must be a positive whole number.")
    if not isinstance(agency_type, str) or not agency_type.strip():
        raise ScenarioError("Prospective partner requires a valid surveyed agency type.")
    dates = pd.to_datetime(fc["week_start"], errors="coerce")
    subset = fc.loc[dates.between(pd.Timestamp(period["cycle_start"]), pd.Timestamp(period["cycle_end"]))].copy()
    history_peers = sites.loc[sites["site_id"].astype(str).isin(subset["site_id"].astype(str))].copy()
    history_peers["peer_families"] = pd.to_numeric(history_peers["families_served_per_month"], errors="coerce")
    history_peers = history_peers.loc[history_peers["peer_families"].gt(0) & np.isfinite(history_peers["peer_families"])].copy()
    same_type = history_peers.loc[history_peers["agency_type"].eq(agency_type)]
    pool = same_type if len(same_type) >= 2 else history_peers
    if len(pool) < 2:
        raise ScenarioError("At least two forecast-covered survey peers with positive family counts are required.")
    peers = set(pool["site_id"].astype(str))
    source = subset.loc[subset["site_id"].astype(str).isin(peers)]
    denominators = float(pool["peer_families"].sum())
    by_week = source.groupby(["week_start", *SKU], as_index=False)["forecast_units"].sum()
    if by_week.empty or by_week["forecast_units"].le(0).all():
        raise ScenarioError("Peer forecasts contain no usable planning volume.")
    n_weeks = int(period["cycle_weeks"])
    if by_week["week_start"].nunique() != n_weeks:
        raise ScenarioError("Peer forecasts do not cover every week in the selected cycle.")
    rows = []
    for item in by_week.itertuples(index=False):
        row = {column: np.nan for column in fc.columns}
        row.update({"site_id": target_id, "product": item.product, "size": item.size,
                    "week_start": item.week_start,
                    "forecast_units": float(item.forecast_units) * family_value / denominators,
                    "requires_review": True})
        for key, value in {"forecast_source": "prospective_scenario_peer_scaling",
                           "method": "scenario_peer_scaling", "forecast_status": "provisional_scenario",
                           "quality_flags": "prospective_unverified_survey_assumption;not_backtested",
                           "wape_reason": "not_historically_backtested"}.items():
            if key in row:
                row[key] = value
        if "origin_week" in row and "origin_week" in fc:
            row["origin_week"] = fc["origin_week"].iloc[0]
        rows.append(row)
    fc = pd.concat([fc, pd.DataFrame(rows, columns=fc.columns)], ignore_index=True)
    if fc[KEY].duplicated().any():
        raise ScenarioError("The prospective partner created duplicate forecast keys.")
    return fc, sites, {"new_partner_id": target_id, "new_partner_name": target_name,
                       "peer_sites": len(peers), "peer_method": "same_agency" if len(same_type) >= 2 else "network",
                       "assumed_cycle_need_units": float(sum(r["forecast_units"] for r in rows)),
                       "provenance": "provisional_prospective_scenario_not_backtested"}


def _retained_issues(issues, added_site_id):
    if not isinstance(issues, pd.DataFrame) or issues.empty or "site_id" not in issues:
        return issues
    return issues.loc[~issues["site_id"].astype(str).eq(str(added_site_id))].copy()


def _compare_wos(forecasts, baseline, scenario_forecasts, prepared):
    from src.alerts import build_inventory_alerts
    original = build_inventory_alerts(forecasts, baseline["prepared"])["alerts"]
    alternative = build_inventory_alerts(scenario_forecasts, prepared)["alerts"]
    keep = SKU + ["cycle_wos", "cycle_supply_gap_units"]
    joined = original[keep].rename(columns={
        "cycle_wos": "original_cycle_wos", "cycle_supply_gap_units": "original_cycle_gap_units"
    }).merge(alternative[keep].rename(columns={
        "cycle_wos": "scenario_cycle_wos", "cycle_supply_gap_units": "scenario_cycle_gap_units"
    }), on=SKU, how="outer", validate="one_to_one")
    return joined.sort_values(SKU).reset_index(drop=True)


def reconcile_scenario_demand(original_prepared: dict, scenario_prepared: dict, kind: str) -> dict:
    """Audit fractional demand versus Gate 4 integerized planning requirements.

    Week 4 rounds each network product/size total independently with the
    largest-remainder (Hamilton) allocator. Moving demand between sizes keeps
    the *fractional* forecast total constant but can change the total integer
    planning requirements by one unit. Never fudge the actual needs table to
    conceal this rounding effect.
    """
    original_needs = original_prepared.get("needs")
    scenario_needs = scenario_prepared.get("needs")
    for frame in (original_needs, scenario_needs):
        _required(frame, CHILD + ["forecast_units", "need_units"], "Prepared planning needs")
        if frame.empty or frame[CHILD].isna().any().any() or frame.duplicated(CHILD).any():
            raise ScenarioError("Invalid or duplicate scenario planning need keys.")
        for column in ("forecast_units", "need_units"):
            vals = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(vals).all() or (vals < 0).any():
                raise ScenarioError("Invalid scenario planning demand quantities.")
            if column == "need_units" and not np.equal(vals, np.floor(vals)).all():
                raise ScenarioError("Operational planning demand must be whole units.")
    old_expected = float(pd.to_numeric(original_needs["forecast_units"]).sum())
    new_expected = float(pd.to_numeric(scenario_needs["forecast_units"]).sum())
    old_rounded = int(pd.to_numeric(original_needs["need_units"]).sum())
    new_rounded = int(pd.to_numeric(scenario_needs["need_units"]).sum())
    expected_delta = new_expected - old_expected
    rounded_delta = new_rounded - old_rounded
    tolerance = max(1e-6, 1e-11 * max(abs(old_expected), abs(new_expected)))
    if kind in {"size_mix", "source_change", "pending_confirmed"}:
        if abs(expected_delta) > tolerance:
            raise ScenarioError("A fixed-network scenario unexpectedly changed total fractional demand.")
        if kind != "size_mix" and rounded_delta != 0:
            raise ScenarioError("A supply-only scenario unexpectedly changed integer planning demand.")
        # Size-mix changes exactly two network SKUs. Independently rounding
        # those two conserved totals can shift the combined integer count by 1.
        if kind == "size_mix" and abs(rounded_delta) > 1:
            raise ScenarioError("Size-mix integer demand drift exceeds the two-SKU rounding bound.")
    return {
        "original_expected_units": old_expected,
        "scenario_expected_units": new_expected,
        "expected_delta_units": expected_delta,
        "original_integer_need_units": old_rounded,
        "scenario_integer_need_units": new_rounded,
        "integer_need_delta_units": rounded_delta,
        "rounding_delta_units": rounded_delta - expected_delta,
        "rounding_policy": "Week 4 independently rounds network product-size totals using largest remainder",
    }


def run_counterfactual(forecasts, inventory, incoming, master, baseline, *, kind, params):
    """Single scenario run against an EXISTING actual Gate 4 plan.

    Returns original operational metrics, scenario-optimized metrics, and a
    separate scenario-specific proportional comparator. Never changes inputs.
    """
    if kind not in KINDS or not isinstance(params, dict):
        raise ScenarioError("Unknown scenario or invalid settings.")
    period = _period(baseline)
    from src.allocation_inputs import prepare_allocation_inputs, run_operational_allocation
    start = perf_counter()
    fc = forecasts.copy(deep=True)
    inv = inventory.copy(deep=True)
    inc = incoming.copy(deep=True) if incoming is not None else None
    sites = master.copy(deep=True)
    info = {}
    if kind == "source_change":
        inc, info = change_source_supply(inc, period, params.get("sources"), params.get("change_pct"))
    elif kind == "pending_confirmed":
        inc, info = assume_pending_confirmed(inc, period)
    elif kind == "size_mix":
        fc, info = shift_forecast_mix(fc, params.get("product"), params.get("from_size"), params.get("to_size"), params.get("shift_pct"), period)
    elif kind == "new_partner":
        fc, sites, info = prospective_partner(
            fc, sites, period, site_id=params.get("site_id"), name=params.get("name"),
            families=params.get("families"), agency_type=params.get("agency_type"),
            acknowledged=params.get("acknowledged", False),
        )
    settings = baseline["settings"]
    orig_caps = baseline["prepared"].get("capacities_units", {})
    prepared = prepare_allocation_inputs(
        fc, inv, inc, sites, cycle_weeks=int(settings["cycle_weeks"]),
        alpha=float(settings["alpha"]), beta=float(settings["beta"]),
        capacities_units=dict(orig_caps),
        forecast_issues=(
            baseline["prepared"].get("forecast_issues")
            if kind != "new_partner"
            else _retained_issues(baseline["prepared"].get("forecast_issues"), info["new_partner_id"])
        ),
    )
    demand_audit = reconcile_scenario_demand(baseline["prepared"], prepared, kind)
    solved = run_operational_allocation(
        prepared, fairness_floor=float(settings["fairness_floor"]),
        worst_shortfall_penalty_share=float(settings["penalty_share"]),
        protect_baseline_fill=bool(settings["protect_baseline_fill"]),
        time_limit_seconds=8,
    )
    before = baseline["solved"]["metrics"]
    after = solved["metrics"]
    from_baseline = baseline["solved"]["baseline_metrics"]
    scenario_proportional = solved["baseline_metrics"]
    coverage = _compare_wos(forecasts, baseline, fc, prepared)
    elapsed = perf_counter() - start
    rows = []
    fields = ["total_allocated_units", "total_unmet_units", "weighted_unmet_units", "worst_site_fill_rate"]
    for key in fields:
        original = float(before[key])
        alternative = float(after[key])
        rows.append({"metric": key, "original_plan": original, "scenario_optimized": alternative,
                     "change_from_original": alternative - original,
                     "scenario_proportional": float(scenario_proportional[key])})
    return {
        "kind": kind, "assumptions": info, "forecasts": fc, "prepared": prepared, "solved": solved,
        "comparison": pd.DataFrame(rows), "coverage": coverage, "demand_audit": demand_audit,
        "original_metrics": dict(before),
        "original_proportional_metrics": dict(from_baseline),
        "scenario_proportional_metrics": dict(scenario_proportional),
        "elapsed_seconds": elapsed,
        "is_synthetic_or_prospective": kind == "new_partner",
    }
