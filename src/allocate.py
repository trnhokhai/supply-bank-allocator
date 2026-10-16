"""Gate 4 allocation core.

Integer LP minimizes equity-weighted planning unmet units plus a scaled
maximum-site-shortfall penalty. No incoming-supply timing, survey, or storage
*case* conversion is guessed here; callers must supply trusted unit quantities.
"""

from __future__ import annotations

from time import perf_counter
from numbers import Integral

import numpy as np
import pandas as pd
import pulp


KEY = ["site_id", "product", "size"]
SKU = ["product", "size"]


class AllocationError(ValueError):
    """An allocation cannot be modeled or safely reported."""


def _whole_number(value, label: str) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise AllocationError(f"{label} must be a nonnegative whole number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise AllocationError(f"{label} must be a nonnegative whole number.") from exc
    if not np.isfinite(number) or number < 0 or not number.is_integer():
        raise AllocationError(f"{label} must be a nonnegative whole number.")
    return int(number)


def _check_table(df: pd.DataFrame, keys: list[str], value: str, name: str) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame):
        raise AllocationError(f"{name} must be a pandas DataFrame.")
    required = set(keys + [value])
    if not required.issubset(df.columns):
        raise AllocationError(f"{name} is missing {sorted(required - set(df.columns))}.")
    if df[keys].isna().any().any() or df.duplicated(keys).any():
        raise AllocationError(f"{name} has missing or duplicate planning keys.")
    result = df[keys + [value]].copy()
    for col in keys:
        if result[col].astype(str).str.strip().eq("").any():
            raise AllocationError(f"{name} has blank {col} identifiers.")
        result[col] = result[col].astype(str)
    result[value] = [_whole_number(x, f"{name}.{value}") for x in result[value]]
    return result.sort_values(keys).reset_index(drop=True)


def _integer_hamilton(values: pd.Series, total: int, labels: pd.Series) -> pd.Series:
    """Integerize nonnegative quotas to a fixed aggregate, with stable ties."""
    arr = values.to_numpy(dtype=float)
    if not np.isfinite(arr).all() or (arr < 0).any():
        raise AllocationError("Forecast units must be finite and nonnegative.")
    lower = np.floor(arr).astype(np.int64)
    remainder = total - int(lower.sum())
    if remainder < 0 or remainder > len(arr):
        raise AllocationError("Inconsistent forecast rounding target.")
    order = sorted(range(len(arr)), key=lambda i: (-(arr[i] - lower[i]), str(labels.iloc[i])))
    for i in order[:remainder]:
        lower[i] += 1
    return pd.Series(lower, index=values.index, dtype="int64")


def forecast_cycle_needs(forecasts: pd.DataFrame, cycle_weeks: int = 4) -> pd.DataFrame:
    """Convert future weekly forecast quantities into integer site/SKU cycle need.

    Preserves the rounded *network SKU total* using largest-remainder rounding.
    Uncertain/review-marked forecasts are returned with their review status.
    """
    required = set(KEY + ["week_start", "forecast_units", "requires_review"])
    if not isinstance(forecasts, pd.DataFrame) or not required.issubset(forecasts.columns):
        raise AllocationError("A canonical Week 3 forecast table is required.")
    if type(cycle_weeks) is not int or not 1 <= cycle_weeks <= 8:
        raise AllocationError("Cycle must contain between 1 and 8 whole weeks.")
    if forecasts.empty or forecasts[KEY + ["week_start"]].isna().any().any():
        raise AllocationError("Forecast table is empty or has missing keys.")
    df = forecasts.copy()
    df["week_start"] = pd.to_datetime(df["week_start"], errors="coerce")
    if df["week_start"].isna().any() or df.duplicated(KEY + ["week_start"]).any():
        raise AllocationError("Forecast keys or week dates are invalid.")
    if df["requires_review"].isna().any():
        raise AllocationError("Unknown forecast review status must be resolved.")
    weeks = sorted(pd.Timestamp(value) for value in df["week_start"].unique())
    if len(weeks) < cycle_weeks:
        raise AllocationError("Forecast horizon is shorter than the allocation cycle.")
    selected = weeks[:cycle_weeks]
    if any((selected[j] - selected[j-1]).days != 7 for j in range(1, len(selected))):
        raise AllocationError("Forecast cycle contains a missing calendar week.")
    df = df[df["week_start"].isin(selected)].copy()
    nums = pd.to_numeric(df["forecast_units"], errors="coerce")
    if nums.isna().any() or not np.isfinite(nums.to_numpy(dtype=float)).all() or nums.lt(0).any():
        raise AllocationError("Forecast contains invalid unit quantities.")
    df["forecast_units"] = nums
    if not df["requires_review"].map(lambda x: isinstance(x, (bool, np.bool_))).all():
        raise AllocationError("Forecast review status must be Boolean.")
    grouped = df.groupby(KEY, as_index=False).agg(
        forecast_units=("forecast_units", "sum"),
        requires_review=("requires_review", "max"),
    )
    grouped["need_units"] = 0
    for _, index in grouped.groupby(SKU, sort=False).groups.items():
        subset = grouped.loc[index]
        total = int(np.floor(float(subset["forecast_units"].sum()) + 0.5))
        grouped.loc[index, "need_units"] = _integer_hamilton(
            subset["forecast_units"], total, subset["site_id"]
        )
    return grouped[KEY + ["need_units", "forecast_units", "requires_review"]].sort_values(KEY).reset_index(drop=True)


def survey_equity_weights(site_master: pd.DataFrame, alpha: float = 0.5, beta: float = 0.25) -> dict[str, float]:
    """Optional site-level survey enrichment; missing data yields weight 1."""
    for value, label in [(alpha, "alpha"), (beta, "beta")]:
        if not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
            raise AllocationError(f"{label} must be finite and nonnegative.")
    if not isinstance(site_master, pd.DataFrame) or "site_id" not in site_master:
        raise AllocationError("Site master must contain site_id.")
    if site_master["site_id"].isna().any() or site_master["site_id"].duplicated().any():
        raise AllocationError("Site master has duplicate or missing IDs.")
    scores = {
        "under_25_percent": 0.125,
        "25_to_50_percent": 0.375,
        "50_to_75_percent": 0.625,
        "over_75_percent": 0.875,
    }
    weights = {}
    for row in site_master.to_dict("records"):
        band = row.get("poverty_share_band")
        poverty = scores.get(band, 0.0) if pd.notna(band) else 0.0
        flags = row.get("priority_population_flags")
        flag_count = len(set(part.strip() for part in flags.split(";") if part.strip())) if isinstance(flags, str) else 0
        weights[str(row["site_id"])] = float(1 + alpha * poverty + beta * flag_count)
    return weights


def _lower_bounds(need: pd.DataFrame, supply: dict[tuple[str, str], int], fraction: float):
    """Feasibility-safe integer fair minimums with explicitly tracked relaxations."""
    mins: dict[tuple[str, str, str], int] = {}
    detail = []
    for sku, group in need.groupby(SKU, sort=True):
        sku = tuple(sku)
        total = int(group["need_units"].sum())
        available = min(supply.get(sku, 0), total)
        ratio = (available / total) if total else 1.0
        requested = fraction * group["need_units"].to_numpy(dtype=float)
        requested_ceil = np.ceil(requested - 1e-10).astype(int)
        if int(requested_ceil.sum()) <= available:
            floors = requested_ceil
            mode = "full_floor"
        else:
            # Scarcity-adjusted maximum uniformly feasible fractional floor.
            # Integer floors keep feasibility even when exact quotas cannot.
            scaled = np.minimum(fraction, ratio) * group["need_units"].to_numpy(dtype=float)
            floors = np.floor(scaled + 1e-10).astype(int)
            mode = "scarcity_or_integer_adjusted"
        for site, n in zip(group["site_id"], floors):
            mins[(str(site), sku[0], sku[1])] = int(n)
        detail.append({"product": sku[0], "size": sku[1], "supply_units": available,
                       "need_units": total, "floor_mode": mode,
                       "floor_fraction_achievable": min(fraction, ratio)})
    return mins, pd.DataFrame(detail)


def _base_model(need, supply, lower_bounds, capacities):
    model = pulp.LpProblem("supply_bank_allocation", pulp.LpMinimize)
    keys = [tuple(x) for x in need[KEY].itertuples(index=False, name=None)]
    n = {tuple(r[:3]): int(r[3]) for r in need[KEY + ["need_units"]].itertuples(index=False, name=None)}
    x = {key: pulp.LpVariable(f"alloc_{i}", lowBound=0, upBound=n[key], cat=pulp.LpInteger) for i, key in enumerate(keys)}
    u = {key: pulp.LpVariable(f"unmet_{i}", lowBound=0, cat=pulp.LpInteger) for i, key in enumerate(keys)}
    for key in keys:
        model += x[key] + u[key] == n[key]
        model += x[key] >= lower_bounds[key]
    by_sku = {}
    by_site = {}
    for key in keys:
        by_sku.setdefault(key[1:], []).append(key)
        by_site.setdefault(key[0], []).append(key)
    for sku, items in by_sku.items():
        model += pulp.lpSum(x[key] for key in items) <= supply.get(sku, 0)
    for site, cap in capacities.items():
        if site in by_site:
            model += pulp.lpSum(x[key] for key in by_site[site]) <= cap
    return model, keys, n, x, u, by_site


def _solve(model, time_limit_seconds):
    status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_seconds, threads=1))
    if status != pulp.LpStatusOptimal:
        raise AllocationError(f"Allocation solver did not prove an optimal feasible plan: {pulp.LpStatus[status]}.")


def _hamilton_split(total: int, targets: np.ndarray, limits: np.ndarray, labels: list[str]) -> np.ndarray:
    """Integer fair/proportional apportionment without over-allocation."""
    allocated = np.minimum(np.floor(targets + 1e-10).astype(int), limits)
    if int(allocated.sum()) > total:
        raise AllocationError("Proportional baseline target inconsistent with supply.")
    remaining = total - int(allocated.sum())
    while remaining:
        eligible = np.flatnonzero(allocated < limits)
        if not len(eligible):
            raise AllocationError("Cannot fit proportional baseline into need caps.")
        i = sorted(eligible, key=lambda k: (-(targets[k] - allocated[k]), labels[k]))[0]
        allocated[i] += 1
        remaining -= 1
    return allocated


def _proportional_baseline(need, supply, floors, capacities, time_limit_seconds):
    """Direct per-SKU split unless capacities require a constrained comparator."""
    if not capacities:
        values = {}
        for sku, group in need.groupby(SKU, sort=True):
            sku = tuple(sku)
            total_need = int(group["need_units"].sum())
            total = min(supply.get(sku, 0), total_need)
            if total_need == 0:
                split = np.zeros(len(group), dtype=int)
            else:
                amounts = group["need_units"].to_numpy(dtype=int)
                lower = np.array([floors[(str(s), *sku)] for s in group["site_id"]], dtype=int)
                left = total - int(lower.sum())
                if left < 0:
                    raise AllocationError("Fairness minimums exceed SKU supply.")
                ideal = total * amounts / total_need
                residual_targets = np.maximum(ideal - lower, 0.0)
                if left:
                    if float(residual_targets.sum()) == 0:
                        residual_targets = np.maximum(amounts - lower, 0).astype(float)
                    residual_targets *= left / float(residual_targets.sum())
                    extra = _hamilton_split(left, residual_targets, amounts - lower,
                                            group["site_id"].astype(str).tolist())
                    split = lower + extra
                else:
                    split = lower
            for site, x in zip(group["site_id"], split):
                values[(str(site), *sku)] = int(x)
        return values

    # With optional per-site capacity, the exact independent SKU splits can
    # violate a shared total capacity. Compare instead with a *capacity-aware*
    # minimum-deviation-to-proportional solution subject to identical bounds.
    model, keys, n, x, u, _ = _base_model(need, supply, floors, capacities)
    total_need = sum(n.values())
    sums = need.groupby(SKU)["need_units"].sum().to_dict()
    targets = {}
    for key in keys:
        sku = key[1:]
        total = int(sums[sku])
        targets[key] = (n[key] * min(supply.get(sku, 0), total) / total) if total else 0.0
    dev = {key: pulp.LpVariable(f"deviation_{i}", lowBound=0)
           for i, key in enumerate(keys)}
    for key in keys:
        model += dev[key] >= x[key] - targets[key]
        model += dev[key] >= targets[key] - x[key]
    # Filling one more unit dominates any possible L1 target deviation change.
    model += (2 * total_need + 1) * pulp.lpSum(u.values()) + pulp.lpSum(dev.values())
    _solve(model, time_limit_seconds)
    return {key: int(round(pulp.value(x[key]))) for key in keys}


def solve_allocation(
    needs: pd.DataFrame,
    supply: pd.DataFrame,
    *,
    equity_weights: dict[str, float] | None = None,
    fairness_floor: float = 0.6,
    capacities_units: dict[str, int] | None = None,
    worst_shortfall_penalty_share: float = 0.01,
    time_limit_seconds: int = 8,
) -> dict:
    """Optimize a one-cycle plan and compare fairly against proportional split.

    Inputs have ALREADY been vetted for availability timing and unit semantics.
    The penalty is `share * network_need * max_site_shortfall_rate`; users can
    compare results with share=0 rather than presuming the penalty is harmless.
    """
    started = perf_counter()
    demand = _check_table(needs, KEY, "need_units", "Cycle needs")
    stock = _check_table(supply, SKU, "available_units", "Available supply")
    if demand.empty:
        raise AllocationError("No forecast planning rows were supplied.")
    for label, value in (("fairness floor", fairness_floor),
                         ("maximum-shortfall penalty", worst_shortfall_penalty_share)):
        if not isinstance(value, (int, float)) or not np.isfinite(value) or value < 0:
            raise AllocationError(f"Invalid {label}.")
    if fairness_floor > 1:
        raise AllocationError("Fairness floor cannot exceed 100%.")
    if type(time_limit_seconds) is not int or time_limit_seconds <= 0:
        raise AllocationError("Solver time limit must be a positive whole number.")
    weights = equity_weights or {}
    sites = set(demand["site_id"])
    weights = {site: float(weights.get(site, 1.0)) for site in sites}
    if any(not np.isfinite(w) or w < 1 for w in weights.values()):
        raise AllocationError("Equity weights must be finite numbers >= 1.")
    caps = {str(site): _whole_number(value, "capacity units")
            for site, value in (capacities_units or {}).items()}
    if set(caps) - sites:
        raise AllocationError("A capacity was supplied for an unknown site.")
    available = {tuple(row[:2]): int(row[2]) for row in stock.itertuples(index=False, name=None)}
    floors, fairness_info = _lower_bounds(demand, available, fairness_floor)
    for site, cap in caps.items():
        minimum = sum(qty for key, qty in floors.items() if key[0] == site)
        if minimum > cap:
            raise AllocationError(
                f"Partner {site} capacity ({cap}) cannot accommodate mandatory "
                f"fairness minimums ({minimum}); review capacity or fairness floor."
            )

    model, keys, n, x, u, by_site = _base_model(demand, available, floors, caps)
    z = pulp.LpVariable("maximum_site_shortfall_fraction", lowBound=0, upBound=1)
    for site, items in by_site.items():
        site_need = sum(n[key] for key in items)
        if site_need:
            model += pulp.lpSum(u[key] for key in items) <= z * site_need
    total_need = sum(n.values())
    penalty_coefficient = worst_shortfall_penalty_share * total_need
    model += pulp.lpSum(weights[key[0]] * u[key] for key in keys) + penalty_coefficient * z
    _solve(model, time_limit_seconds)
    optimized = {key: int(round(pulp.value(x[key]))) for key in keys}
    baseline = _proportional_baseline(demand, available, floors, caps, time_limit_seconds)

    def _result_rows(solution):
        rows = []
        for key in keys:
            allocated = solution[key]
            if allocated < floors[key] or allocated > n[key]:
                raise AllocationError("Solver output failed allocation checks.")
            rows.append({"site_id": key[0], "product": key[1], "size": key[2],
                         "need_units": n[key], "allocated_units": allocated,
                         "unmet_units": n[key] - allocated, "equity_weight": weights[key[0]],
                         "fairness_min_units": floors[key]})
        frame = pd.DataFrame(rows)
        for sku, group in frame.groupby(SKU):
            if int(group["allocated_units"].sum()) > available.get(tuple(sku), 0):
                raise AllocationError("Solution over-allocates available supply.")
        for site, cap in caps.items():
            if int(frame.loc[frame.site_id.eq(site), "allocated_units"].sum()) > cap:
                raise AllocationError("Solution exceeds partner storage capacity.")
        return frame

    def _metrics(frame):
        sites_frame = frame.groupby("site_id").agg(
            need=("need_units", "sum"), unmet=("unmet_units", "sum"),
            allocated=("allocated_units", "sum"),
        )
        nonzero = sites_frame["need"].gt(0)
        worst_shortfall = float((sites_frame.loc[nonzero, "unmet"] /
                                 sites_frame.loc[nonzero, "need"]).max()) if nonzero.any() else 0.0
        weighted = float((frame["unmet_units"] * frame["equity_weight"]).sum())
        return {"total_allocated_units": int(frame["allocated_units"].sum()),
                "total_unmet_units": int(frame["unmet_units"].sum()),
                "weighted_unmet_units": weighted,
                "worst_site_fill_rate": 1 - worst_shortfall,
                "maximum_shortfall_rate": worst_shortfall,
                "penalized_objective": weighted + penalty_coefficient * worst_shortfall}

    plan = _result_rows(optimized)
    proportional = _result_rows(baseline)
    m = _metrics(plan)
    b = _metrics(proportional)
    return {"allocation": plan, "proportional_baseline": proportional,
            "metrics": m, "baseline_metrics": b,
            "comparison": {"weighted_unmet_delta": m["weighted_unmet_units"] - b["weighted_unmet_units"],
                           "worst_site_fill_delta": m["worst_site_fill_rate"] - b["worst_site_fill_rate"]},
            "fairness": fairness_info, "objective_penalty_coefficient": penalty_coefficient,
            "elapsed_seconds": perf_counter() - started,
            "baseline_type": "capacity_aware_proportional" if caps else "proportional"}
