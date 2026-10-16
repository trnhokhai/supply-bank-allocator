"""Certified HiGHS MILP backend for the Gate 4 supply bank allocator.

The original PuLP/CBC formulation is retained in src.allocate as a reference.
SciPy HiGHS is used for fast operational solves; this function implements the
same integer feasible set, equity-weighted unmet objective and maximum-site-
shortfall penalty. Baseline protection is optional and explicitly disclosed.

Only certified, integer, independently checked solutions are accepted.
"""

from __future__ import annotations

from time import perf_counter

import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix


def solve_highs(
    demand: pd.DataFrame,
    available: dict[tuple[str, str], int],
    floors: dict[tuple[str, str, str], int],
    weights: dict[str, float],
    capacities: dict[str, int],
    *,
    penalty_share: float,
    baseline_worst_shortfall: float | None,
    time_limit_seconds: int,
    mip_rel_gap: float = 1e-5,
) -> dict:
    """Return certified site/SKU allocations, measured runtime and MIP gap.

    Variables: integer unmet[i] for each site/SKU, continuous z in [0, 1].
    Constraints: unmet <= need - floor; SKU unmet >= need - supply;
    site unmet <= z * site need; optional storage cap as unmet >= need - cap.
    Optional guard: z <= baseline max shortfall, protecting the *same*
    actual worst-site metric used in the report. No cherry-picked score.
    """
    records = list(demand[["site_id", "product", "size", "need_units"]].itertuples(index=False, name=None))
    if not records:
        raise ValueError("No demand rows for HiGHS optimizer.")
    keys = [tuple(row[:3]) for row in records]
    amounts = np.asarray([int(row[3]) for row in records], dtype=np.int64)
    count = len(keys)
    sites = sorted({key[0] for key in keys})
    skus = sorted({key[1:] for key in keys})
    sites_index = {site: i for i, site in enumerate(sites)}
    skus_index = {sku: i for i, sku in enumerate(skus)}

    site_need = {site: 0 for site in sites}
    sku_need = {sku: 0 for sku in skus}
    unmet_ub = np.zeros(count, dtype=np.float64)
    equity = np.zeros(count, dtype=np.float64)
    sparse_rows: list[int] = []
    sparse_cols: list[int] = []
    sparse_values: list[float] = []
    for i, key in enumerate(keys):
        site, product, size = key
        sku = (product, size)
        site_need[site] += int(amounts[i])
        sku_need[sku] += int(amounts[i])
        unmet_ub[i] = int(amounts[i]) - int(floors[key])
        equity[i] = float(weights[site])
        for constraint_row in (skus_index[sku], len(skus) + sites_index[site]):
            sparse_rows.append(constraint_row)
            sparse_cols.append(i)
            sparse_values.append(1.0)
    if (unmet_ub < 0).any() or not np.isfinite(equity).all() or (equity < 1).any():
        raise ValueError("Invalid fairness or equity inputs to HiGHS.")

    # SKU: sum(unmet) >= total SKU need - available SKU supply.
    lower = [float(max(0, sku_need[sku] - available.get(sku, 0))) for sku in skus]
    upper = [np.inf] * len(skus)
    # Site: sum(unmet) - z * site_need <= 0.
    for site in sites:
        row = len(skus) + sites_index[site]
        sparse_rows.append(row)
        sparse_cols.append(count)
        sparse_values.append(-float(site_need[site]))
        lower.append(-np.inf)
        upper.append(0.0)

    # Shared storage capacity: sum(allocated) <= cap, equivalent to
    # sum(unmet) >= site total need - cap. This applies across all SKUs.
    for site in sorted(capacities):
        if site not in site_need:
            raise ValueError(f"Unknown storage-capacity site: {site}.")
        row = len(lower)
        for i, key in enumerate(keys):
            if key[0] == site:
                sparse_rows.append(row)
                sparse_cols.append(i)
                sparse_values.append(1.0)
        lower.append(float(max(0, site_need[site] - capacities[site])))
        upper.append(np.inf)

    matrix = coo_matrix(
        (sparse_values, (sparse_rows, sparse_cols)),
        shape=(len(lower), count + 1),
    ).tocsr()
    z_ub = 1.0 if baseline_worst_shortfall is None else min(1.0, float(baseline_worst_shortfall) + 1e-9)
    objective = np.r_[equity, float(penalty_share) * int(amounts.sum())]

    started = perf_counter()
    result = milp(
        objective,
        integrality=np.r_[np.ones(count, dtype=np.int32), 0],
        bounds=Bounds(np.zeros(count + 1), np.r_[unmet_ub, z_ub]),
        constraints=LinearConstraint(matrix, np.asarray(lower), np.asarray(upper)),
        options={"time_limit": float(time_limit_seconds), "mip_rel_gap": float(mip_rel_gap)},
    )
    elapsed = perf_counter() - started
    if result.status != 0 or result.x is None:
        raise RuntimeError(f"HiGHS did not certify a solution within {time_limit_seconds}s: {result.message}")
    gap = getattr(result, "mip_gap", None)
    if gap is None or not np.isfinite(gap) or gap > mip_rel_gap + 1e-8:
        raise RuntimeError("HiGHS returned a solution without the required MIP gap certificate.")

    unmet_float = np.asarray(result.x[:count], dtype=float)
    if (not np.isfinite(unmet_float).all()
            or np.max(np.abs(unmet_float - np.rint(unmet_float))) > 1e-5):
        raise RuntimeError("HiGHS returned fractional or invalid unmet quantities.")
    unmet = np.rint(unmet_float).astype(np.int64)
    allocated = amounts - unmet
    if (allocated < 0).any() or (allocated > amounts).any() or (unmet < 0).any():
        raise RuntimeError("HiGHS solution has invalid material balances.")
    if (unmet > unmet_ub).any():
        raise RuntimeError("HiGHS solution violates a fairness minimum.")

    actual_sku_allocations = {sku: 0 for sku in skus}
    actual_site_allocations = {site: 0 for site in sites}
    actual_site_unmet = {site: 0 for site in sites}
    for i, key in enumerate(keys):
        actual_sku_allocations[key[1:]] += int(allocated[i])
        actual_site_allocations[key[0]] += int(allocated[i])
        actual_site_unmet[key[0]] += int(unmet[i])
    if any(actual_sku_allocations[sku] > available.get(sku, 0) for sku in skus):
        raise RuntimeError("HiGHS solution exceeds available SKU supply.")
    if any(actual_site_allocations[s] > cap for s, cap in capacities.items()):
        raise RuntimeError("HiGHS solution exceeds a verified storage capacity.")
    worst = max((actual_site_unmet[s] / site_need[s]
                 for s in sites if site_need[s] > 0), default=0.0)
    if float(result.x[-1]) + 1e-6 < worst:
        raise RuntimeError("HiGHS maximum-shortfall variable understates actual worst-site shortfall.")
    if baseline_worst_shortfall is not None and worst > baseline_worst_shortfall + 1e-6:
        raise RuntimeError("Protected HiGHS solution underperforms the baseline worst-site fill.")

    return {
        "allocation": {key: int(allocated[i]) for i, key in enumerate(keys)},
        "solver_seconds": elapsed,
        "mip_relative_gap": float(gap),
        "solver_backend": "scipy_highs",
    }
