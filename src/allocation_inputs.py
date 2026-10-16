"""Gate 4 operational bridge: cleaned uploads + Week 3 forecasts -> allocation.

The core integer optimizer in src.allocate never guesses dates or case-pack
conversions. This module owns those business policies and distinguishes a
cycle commitment from a stock-on-hand pick suggestion. It does not schedule
shipments or claim historical distributions measure unconstrained need.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.allocate import (
    AllocationError,
    forecast_cycle_needs,
    solve_allocation,
    survey_equity_weights,
)

SKUS = ["product", "size"]
CHILD = ["site_id", "product", "size"]
WEEK_KEY = CHILD + ["week_start"]


def _require(frame, required, label):
    if not isinstance(frame, pd.DataFrame):
        raise AllocationError(f"{label} must be a cleaned pandas table.")
    missing = set(required) - set(frame.columns)
    if missing:
        raise AllocationError(f"{label} is missing columns: {sorted(missing)}.")


def _dates(values, label):
    dates = pd.to_datetime(values, errors="coerce")
    if dates.isna().any() or dates.dt.tz is not None:
        raise AllocationError(f"{label} contains invalid or timezone-aware dates.")
    # Preserve the original dates, but require dates rather than timestamps
    # with arbitrary hours because incoming availability is date-based.
    if not dates.eq(dates.dt.normalize()).all():
        raise AllocationError(f"{label} must contain calendar dates only.")
    return dates


def _units(frame, column, label):
    if frame.empty:
        return pd.Series(dtype="int64", index=frame.index)
    raw = frame[column]
    if raw.map(lambda x: isinstance(x, (bool, np.bool_))).any():
        raise AllocationError(f"{label} must contain nonnegative whole units.")
    numeric = pd.to_numeric(raw, errors="coerce")
    arr = numeric.to_numpy(dtype=float)
    if not np.isfinite(arr).all() or (arr < 0).any() or not np.equal(arr, np.floor(arr)).all():
        raise AllocationError(f"{label} must contain nonnegative whole units.")
    if (arr > np.iinfo(np.int64).max).any():
        raise AllocationError(f"{label} exceeds the supported unit range.")
    return numeric.astype("int64")


def _normalized_keys(frame, columns, label):
    for col in columns:
        if frame[col].isna().any() or frame[col].astype(str).str.strip().eq("").any():
            raise AllocationError(f"{label} has missing {col} identifiers.")
        frame[col] = frame[col].astype(str)


def _sku_sum(frame, quantity, output):
    if frame.empty:
        return pd.DataFrame(columns=SKUS + [output])
    return (frame.groupby(SKUS, as_index=False)[quantity]
            .sum().rename(columns={quantity: output})
            .sort_values(SKUS).reset_index(drop=True))


def prepare_allocation_inputs(
    forecasts: pd.DataFrame,
    current_inventory: pd.DataFrame,
    incoming_supply: pd.DataFrame | None,
    site_master: pd.DataFrame,
    *,
    cycle_weeks: int = 4,
    alpha: float = 0.5,
    beta: float = 0.25,
    capacities_units: dict[str, int] | None = None,
    forecast_issues: pd.DataFrame | None = None,
) -> dict:
    """Prepare an explainable single-cycle allocation input contract.

    Planning snapshot: one physical inventory count date. Future arrivals are
    additive ONLY when confirmed, date after snapshot and no later than cycle
    end, and their canonical size is known. A missing donation file means no
    verified incoming supply, not proof that no future donation will arrive.

    Allocation cycle is an aggregate planning horizon. Confirmed deliveries
    arriving late in the cycle DO NOT establish availability at earlier dates.
    """
    _require(forecasts, WEEK_KEY + ["forecast_units", "requires_review"], "Forecast")
    _require(current_inventory, ["as_of_date", *SKUS, "quantity_on_hand"], "Inventory")
    _require(site_master, ["site_id", "site_name"], "Site master")
    if forecasts.empty or current_inventory.empty:
        raise AllocationError("Forecast and inventory snapshot must be nonempty.")
    if type(cycle_weeks) is not int or not 1 <= cycle_weeks <= 8:
        raise AllocationError("Allocation cycle must be 1–8 whole weeks.")
    if incoming_supply is not None:
        _require(incoming_supply, ["expected_date", *SKUS, "quantity", "status"], "Incoming supply")

    fc = forecasts.copy()
    _normalized_keys(fc, CHILD, "Forecast")
    fc["week_start"] = _dates(fc["week_start"], "Forecast weeks")
    if fc["week_start"].dt.weekday.ne(0).any() or fc.duplicated(WEEK_KEY).any():
        raise AllocationError("Forecast must have unique ISO-Monday child/week keys.")
    all_weeks = sorted(pd.Timestamp(x) for x in fc["week_start"].unique())
    selected_weeks = all_weeks[:cycle_weeks]
    if len(selected_weeks) < cycle_weeks or any(
        (selected_weeks[i] - selected_weeks[i-1]).days != 7
        for i in range(1, len(selected_weeks))
    ):
        raise AllocationError("Forecast has an incomplete or nonconsecutive cycle.")
    start = pd.Timestamp(selected_weeks[0])
    end = pd.Timestamp(selected_weeks[-1]) + pd.Timedelta(days=6)
    cycle_forecast = fc.loc[fc["week_start"].isin(selected_weeks)].copy()
    coverage = cycle_forecast.groupby(CHILD)["week_start"].nunique()
    if coverage.lt(cycle_weeks).any():
        raise AllocationError("A partner/product/size forecast is missing a cycle week.")
    if "origin_week" in fc:
        origin_dates = _dates(fc["origin_week"], "Forecast origin")
        if origin_dates.nunique() != 1 or origin_dates.iloc[0] + pd.Timedelta(days=7) != start:
            raise AllocationError("Forecast origin does not align with the first future week.")

    inv = current_inventory.copy()
    _normalized_keys(inv, SKUS, "Inventory")
    inv["as_of_date"] = _dates(inv["as_of_date"], "Inventory snapshot")
    if inv["as_of_date"].nunique() != 1:
        raise AllocationError("Inventory contains mixed snapshot dates; reconcile counts first.")
    snapshot = pd.Timestamp(inv["as_of_date"].iloc[0])
    if snapshot > start:
        raise AllocationError("Inventory snapshot falls after the allocation cycle starts.")
    inv["quantity_on_hand"] = _units(inv, "quantity_on_hand", "Inventory quantity")
    if "location" in inv:
        key_cols = ["as_of_date", *SKUS, "location"]
        if inv.duplicated(key_cols).any():
            raise AllocationError("Duplicate inventory location/SKU snapshots need review.")
    else:
        if inv.duplicated(["as_of_date", *SKUS]).any():
            raise AllocationError("Duplicate inventory SKU rows need review.")
    on_hand = _sku_sum(inv, "quantity_on_hand", "on_hand_units")

    warnings = []
    def warn(code, message, count=1):
        warnings.append({"code": code, "message": message, "count": int(count)})

    if (start - snapshot).days > 14:
        warn("stale_inventory", "Inventory count is over 14 days older than the cycle start; verify quantities.")

    if incoming_supply is None:
        shipments = pd.DataFrame(columns=["expected_date", *SKUS, "quantity", "status"])
        warn("incoming_not_provided", "No Incoming Supply file: plan uses inventory on hand only.")
    else:
        shipments = incoming_supply.copy()
    if not shipments.empty:
        _normalized_keys(shipments, SKUS, "Incoming supply")
        shipments["expected_date"] = _dates(shipments["expected_date"], "Incoming supply dates")
        shipments["quantity"] = _units(shipments, "quantity", "Incoming quantity")
        if shipments["status"].isna().any() or not shipments["status"].isin({"confirmed", "pending"}).all():
            raise AllocationError("Incoming status must be confirmed or pending.")
        pending = shipments["status"].eq("pending")
        unknown = shipments["size"].eq("unknown")
        old = shipments["expected_date"].le(snapshot)
        late = shipments["expected_date"].gt(end)
        if pending.any():
            warn("pending_excluded", "Pending incoming supply is not available in the base plan.", pending.sum())
        if (unknown & ~pending).any():
            warn("unresolved_size_excluded", "Confirmed incoming supply with unknown size is excluded until physically identified.", (unknown & ~pending).sum())
        if ((~pending) & (~unknown) & old).any():
            warn("before_snapshot_excluded", "Confirmed deliveries on/before the snapshot may already be in on-hand stock and are not added again.", ((~pending) & (~unknown) & old).sum())
        if ((~pending) & (~unknown) & late).any():
            warn("after_cycle_excluded", "Confirmed deliveries after the cycle are not available to this plan.", ((~pending) & (~unknown) & late).sum())
        eligible = shipments.loc[(~pending) & (~unknown) & (~old) & (~late)].copy()
    else:
        eligible = shipments.copy()
    incoming = _sku_sum(eligible, "quantity", "confirmed_inbound_units")

    needs = forecast_cycle_needs(fc, cycle_weeks=cycle_weeks)
    # Keep Week 3 metadata alongside each aggregated planning need. These are
    # labels and quality diagnostics, never independently calibrated demand.
    metadata_fields = [
        "forecast_source", "method", "wape_pct", "wape_reason",
        "parent_wape_pct", "range_reason", "forecast_status",
    ]
    present = [column for column in metadata_fields if column in cycle_forecast]
    metadata = (
        cycle_forecast.groupby(CHILD, as_index=False)[present].first()
        if present else cycle_forecast[CHILD].drop_duplicates()
    )
    if "quality_flags" in cycle_forecast:
        flags = cycle_forecast.groupby(CHILD)["quality_flags"].agg(
            lambda series: ";".join(sorted(set(
                token.strip() for item in series.dropna().astype(str)
                for token in item.split(";") if token.strip()
            )))
        ).reset_index()
        metadata = metadata.merge(flags, on=CHILD, how="left", validate="one_to_one")
    needs = needs.merge(metadata, on=CHILD, how="left", validate="one_to_one")
    if not needs["site_id"].isin(site_master["site_id"].astype(str)).all():
        raise AllocationError("Forecast contains partner IDs not found in the site master.")
    stock = (on_hand.merge(incoming, on=SKUS, how="outer")
             .fillna({"on_hand_units": 0, "confirmed_inbound_units": 0}))
    stock["on_hand_units"] = stock["on_hand_units"].astype("int64")
    stock["confirmed_inbound_units"] = stock["confirmed_inbound_units"].astype("int64")
    stock["available_units"] = stock["on_hand_units"] + stock["confirmed_inbound_units"]
    supply = stock[SKUS + ["available_units"]].sort_values(SKUS).reset_index(drop=True)

    master = site_master.copy()
    _normalized_keys(master, ["site_id", "site_name"], "Site master")
    if master["site_id"].duplicated().any():
        raise AllocationError("Site master has duplicate partner IDs.")
    equity = survey_equity_weights(master, alpha=alpha, beta=beta)
    names = master.set_index("site_id")["site_name"].to_dict()
    missing_sites = sorted(set(master["site_id"]) - set(needs["site_id"]))
    if missing_sites:
        warn("sites_not_forecast", "Some known partners lack a forecast; their need has NOT been assumed zero.", len(missing_sites))
    if forecast_issues is not None and not forecast_issues.empty:
        _require(forecast_issues, ["site_id", "reason"], "Forecast issues")
        warn("unresolved_forecasts", "Review unresolved forecast issues before acting on the plan.", len(forecast_issues))
    review_rows = needs.loc[needs["requires_review"]].copy()
    if not review_rows.empty:
        warn("forecast_review", "Forecast-based planning needs include provisional or flagged series.", len(review_rows))
    if "storage_capacity_cases" in master:
        unresolved_cases = master.loc[
            master["site_id"].isin(needs["site_id"])
            & master["storage_capacity_cases"].notna()
            & ~master["site_id"].isin((capacities_units or {}).keys())
        ]
        if not unresolved_cases.empty:
            warn("case_capacity_not_enforced", "Survey storage capacity is in cases; no unit conversion is assumed. Supply explicit verified unit capacities to enforce it.", len(unresolved_cases))
    if len(eligible):
        warn("cycle_timing", "Cycle plan uses confirmed arrivals through cycle end; do not pick units until received.")
    return {
        "needs": needs,
        "supply": supply,
        "on_hand": on_hand,
        "confirmed_inbound": incoming,
        "eligible_incoming_rows": eligible.reset_index(drop=True),
        "equity_weights": equity,
        "capacities_units": capacities_units or {},
        "site_names": names,
        "review_rows": review_rows.reset_index(drop=True),
        "forecast_issues": forecast_issues.copy() if forecast_issues is not None else pd.DataFrame(),
        "warnings": pd.DataFrame(warnings, columns=["code", "message", "count"]),
        "period": {"cycle_start": start, "cycle_end": end,
                   "inventory_as_of": snapshot, "cycle_weeks": cycle_weeks},
    }


def _ready_now_split(allocation: pd.DataFrame, on_hand: pd.DataFrame) -> pd.DataFrame:
    """Apportion today's stock within the committed plan, never above it.

    This is a conservative, deterministic warehouse suggestion. It deliberately
    does not promise arrivals to a specific distribution date.
    """
    output = allocation.copy()
    output["ready_now_units"] = 0
    available = {(str(r.product), str(r.size)): int(r.on_hand_units)
                 for r in on_hand.itertuples(index=False)}
    for sku, subset in output.groupby(SKUS, sort=True):
        indices = list(subset.index)
        commitments = subset["allocated_units"].to_numpy(dtype=int)
        total = int(commitments.sum())
        immediately = min(total, available.get(tuple(sku), 0))
        if total == 0 or immediately == 0:
            continue
        targets = commitments.astype(float) * (immediately / total)
        integer = np.floor(targets).astype(int)
        left = immediately - int(integer.sum())
        priority = sorted(range(len(integer)), key=lambda i: (
            -(targets[i] - integer[i]), str(subset.iloc[i]["site_id"])
        ))
        for i in priority:
            if left == 0:
                break
            if integer[i] < commitments[i]:
                integer[i] += 1
                left -= 1
        if left:
            raise AllocationError("Could not produce a valid immediate pick list.")
        output.loc[indices, "ready_now_units"] = integer
    output["awaiting_inbound_units"] = output["allocated_units"] - output["ready_now_units"]
    return output


def run_operational_allocation(
    prepared: dict,
    *,
    fairness_floor: float = 0.6,
    worst_shortfall_penalty_share: float = 0.01,
    time_limit_seconds: int = 8,
) -> dict:
    """Solve the cycle plan, then derive a stock-on-hand-only pick suggestion."""
    result = solve_allocation(
        prepared["needs"], prepared["supply"],
        equity_weights=prepared["equity_weights"],
        capacities_units=prepared["capacities_units"],
        fairness_floor=fairness_floor,
        worst_shortfall_penalty_share=worst_shortfall_penalty_share,
        time_limit_seconds=time_limit_seconds,
    )
    planned = _ready_now_split(result["allocation"], prepared["on_hand"])
    provenance = prepared["needs"].drop(columns=["need_units", "forecast_units", "requires_review"], errors="ignore")
    additional = [column for column in provenance if column not in CHILD]
    if additional:
        planned = planned.merge(provenance[CHILD + additional], on=CHILD,
                                how="left", validate="one_to_one")
    planned.insert(1, "site_name", planned["site_id"].map(prepared["site_names"]))
    if planned["site_name"].isna().any():
        raise AllocationError("An allocated partner has no matching site name.")
    pick = planned.loc[planned["ready_now_units"].gt(0),
                       ["site_id", "site_name", "product", "size", "ready_now_units"]].copy()
    pick = pick.sort_values(["site_name", "product", "size", "site_id"]).reset_index(drop=True)
    return {
        **result,
        "allocation": planned,
        "ready_now_pick_list": pick,
        "operational_summary": {
            "allocated_cycle_units": int(planned["allocated_units"].sum()),
            "ready_now_units": int(planned["ready_now_units"].sum()),
            "awaiting_inbound_units": int(planned["awaiting_inbound_units"].sum()),
        },
        "warnings": prepared["warnings"],
        "review_rows": prepared["review_rows"],
        "forecast_issues": prepared["forecast_issues"],
        "period": prepared["period"],
    }
