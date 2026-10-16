"""Presentation-only helpers for Gate 4 allocation results.

Never solve, modify demand, or manufacture a successful benchmark in this file.
Kept separate from Streamlit so totals, comparisons, exports, and input
fingerprinting can be verified without an interactive browser session.
"""

from __future__ import annotations

from hashlib import sha256

import numpy as np
import pandas as pd

from src.allocate import AllocationError


def input_signature(*tables: pd.DataFrame | None) -> str:
    """Fingerprint the actual session inputs; invalidate plans after uploads change."""
    digest = sha256()
    for table in tables:
        if table is None:
            digest.update(b"<not-provided>")
        elif isinstance(table, pd.DataFrame):
            digest.update(str(list(table.columns)).encode("utf-8"))
            digest.update(table.to_json(
                orient="split", date_format="iso", default_handler=str
            ).encode("utf-8"))
        else:
            raise AllocationError("Allocation fingerprint expects data tables.")
        digest.update(b"\n")
    return digest.hexdigest()


def verified_capacity_overrides(edited: pd.DataFrame, allowed_sites: set[str]) -> dict[str, int]:
    """Only user-entered, verified individual-unit caps; missing means no cap."""
    if not isinstance(edited, pd.DataFrame) or not {"site_id", "capacity_units"}.issubset(edited.columns):
        raise AllocationError("Unit-capacity editor is missing required columns.")
    if edited["site_id"].isna().any() or edited["site_id"].astype(str).duplicated().any():
        raise AllocationError("Unit capacity table has invalid or duplicate partner IDs.")
    if not set(edited["site_id"].astype(str)).issubset(allowed_sites):
        raise AllocationError("Capacity specified for a partner outside the site master.")
    caps = {}
    for row in edited.itertuples(index=False):
        raw = getattr(row, "capacity_units")
        if pd.isna(raw) or (isinstance(raw, str) and raw.strip() == ""):
            continue
        if isinstance(raw, (bool, np.bool_)):
            raise AllocationError("Capacity must be a nonnegative whole number of individual units.")
        try:
            qty = float(raw)
        except (TypeError, ValueError) as exc:
            raise AllocationError("Capacity must be a nonnegative whole number of individual units.") from exc
        if not np.isfinite(qty) or qty < 0 or not qty.is_integer():
            raise AllocationError("Capacity must be a nonnegative whole number of individual units.")
        caps[str(row.site_id)] = int(qty)
    return caps


def partner_summary(allocation: pd.DataFrame) -> pd.DataFrame:
    """One row per partner with denominators explicit (not average of SKU rates)."""
    needed = {"site_id", "site_name", "need_units", "allocated_units", "unmet_units",
              "ready_now_units", "awaiting_inbound_units", "equity_weight"}
    if not isinstance(allocation, pd.DataFrame) or not needed.issubset(allocation.columns):
        raise AllocationError("Allocation output is missing partner-summary fields.")
    if allocation.empty:
        return pd.DataFrame(columns=["site_id", "site_name", "need_units", "allocated_units", "unmet_units",
                                     "ready_now_units", "awaiting_inbound_units", "equity_weight", "fill_rate_pct"])
    if allocation["site_id"].isna().any() or allocation["site_name"].isna().any():
        raise AllocationError("Allocation contains an unidentified partner.")
    for site, sub in allocation.groupby("site_id"):
        if sub["site_name"].nunique() != 1 or sub["equity_weight"].nunique() != 1:
            raise AllocationError(f"Conflicting name or equity weight for {site}.")
    numeric = ["need_units", "allocated_units", "unmet_units", "ready_now_units", "awaiting_inbound_units"]
    amounts = allocation[numeric].apply(pd.to_numeric, errors="coerce")
    if amounts.isna().any().any() or (~np.isfinite(amounts.to_numpy(dtype=float))).any() or (amounts < 0).any().any():
        raise AllocationError("Allocation contains invalid unit quantities.")
    if not (amounts["allocated_units"] + amounts["unmet_units"]).eq(amounts["need_units"]).all():
        raise AllocationError("Allocation need reconciliation failed.")
    if not (amounts["ready_now_units"] + amounts["awaiting_inbound_units"]).eq(amounts["allocated_units"]).all():
        raise AllocationError("Ready-now allocation reconciliation failed.")
    result = (allocation.groupby(["site_id", "site_name"], as_index=False)
              .agg(need_units=("need_units", "sum"), allocated_units=("allocated_units", "sum"),
                   unmet_units=("unmet_units", "sum"), ready_now_units=("ready_now_units", "sum"),
                   awaiting_inbound_units=("awaiting_inbound_units", "sum"),
                   equity_weight=("equity_weight", "first")))
    result["fill_rate_pct"] = 100 * result["allocated_units"].div(
        result["need_units"].replace(0, np.nan)
    )
    return result.sort_values(["fill_rate_pct", "site_name"], na_position="last").reset_index(drop=True)


def comparison_summary(result: dict) -> dict:
    """Improvement means baseline weighted unmet MINUS optimized weighted unmet."""
    try:
        now = result["metrics"]
        base = result["baseline_metrics"]
        weighted_now = float(now["weighted_unmet_units"])
        weighted_base = float(base["weighted_unmet_units"])
        worst_now = float(now["worst_site_fill_rate"])
        worst_base = float(base["worst_site_fill_rate"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AllocationError("Missing allocation baseline metrics.") from exc
    if not all(np.isfinite(x) for x in (weighted_now, weighted_base, worst_now, worst_base)):
        raise AllocationError("Comparison has invalid non-finite metrics.")
    return {
        "optimized_weighted_unmet": weighted_now,
        "baseline_weighted_unmet": weighted_base,
        "weighted_units_improved": weighted_base - weighted_now,
        "weighted_improvement_pct": (100 * (weighted_base - weighted_now) / weighted_base
                                     if weighted_base > 0 else None),
        "optimized_worst_fill_pct": 100 * worst_now,
        "baseline_worst_fill_pct": 100 * worst_base,
        "worst_fill_delta_pp": 100 * (worst_now - worst_base),
    }


def csv_download(data: pd.DataFrame) -> bytes:
    """Excel-safe UTF-8 CSV without writing private uploaded data to disk."""
    if not isinstance(data, pd.DataFrame):
        raise AllocationError("Download requires a table.")
    out = data.copy()
    for column in out.select_dtypes(include=["object", "string"]).columns:
        out[column] = out[column].map(
            lambda value: "'" + value if isinstance(value, str)
            and value.lstrip().startswith(("=", "+", "-", "@")) else value
        )
    return out.to_csv(index=False, na_rep="N/A").encode("utf-8-sig")
