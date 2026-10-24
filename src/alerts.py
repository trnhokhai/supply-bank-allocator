"""Gate 5 inventory risk: explainable on-hand and cycle-supply coverage.

Consumes Gate 4's prepared (validated) supply contract.  No physical stock is
created here: confirmed inbound is included only in projected cycle coverage.
Weeks of supply forecasts distributions, not unconstrained community demand.
"""

from __future__ import annotations

from datetime import timedelta
from math import isfinite

import numpy as np
import pandas as pd

SKU = ["product", "size"]
REQUIRED_FORECAST = ["site_id"] + SKU + ["week_start", "forecast_units", "requires_review"]
ALERT_COLUMNS = SKU + [
    "on_hand_units", "confirmed_inbound_units", "projected_cycle_units",
    "mean_weekly_forecast_units", "on_hand_wos", "cycle_wos",
    "on_hand_status", "cycle_status", "forecast_requires_review",
    "inventory_row_present", "forecast_row_present", "gap_to_short_threshold_units",
    "cycle_supply_gap_units",
    "recommendation",
]
MIX_COLUMNS = SKU + ["on_hand_mix_pct", "forecast_mix_pct", "mismatch_index_pp"]


class AlertsError(ValueError):
    """Unsafe input, mismatched planning periods or invalid thresholds."""


def _table(value, columns, label):
    if not isinstance(value, pd.DataFrame):
        raise AlertsError(f"{label} must be a cleaned pandas table.")
    absent = set(columns) - set(value.columns)
    if absent:
        raise AlertsError(f"{label} is missing columns: {sorted(absent)}.")
    if value[SKU].isna().any().any() or (value[SKU].astype(str).apply(lambda c: c.str.strip().eq(""))).any().any():
        raise AlertsError(f"{label} contains missing product/size identifiers.")
    return value.copy()


def _quantities(frame, column, label, whole):
    values = pd.to_numeric(frame[column], errors="coerce")
    numbers = values.to_numpy(dtype=float)
    if not np.isfinite(numbers).all() or (numbers < 0).any():
        raise AlertsError(f"{label} must contain nonnegative finite units.")
    if whole and (not np.equal(numbers, np.floor(numbers)).all() or (numbers > np.iinfo(np.int64).max).any()):
        raise AlertsError(f"{label} must contain nonnegative whole units.")
    return values


def _status(wos, present_inventory, present_forecast, demand, short_weeks, long_weeks):
    if not present_inventory:
        return "inventory_missing"
    if not present_forecast:
        return "forecast_missing"
    if demand <= 0:
        return "zero_forecast_review"
    if wos < short_weeks:
        return "short"
    if wos > long_weeks:
        return "long"
    return "adequate"


def _recommendation(row):
    product, size = row["product"], row["size"]
    label = f"{product} / {size}"
    on_hand = row["on_hand_status"]
    cycle = row["cycle_status"]
    if on_hand == "inventory_missing":
        return f"Verify a physical inventory count for {label} before treating missing rows as zero stock."
    if on_hand in {"forecast_missing", "zero_forecast_review"}:
        return f"Review distribution history and forecast coverage for {label} before calculating stock risk."
    # An otherwise 'adequate' WOS can still fall short of a longer selected
    # planning cycle. The threshold alert and full-cycle planning gap answer
    # different business questions; never hide the latter.
    full_cycle_gap = int(row["cycle_supply_gap_units"]) if pd.notna(row["cycle_supply_gap_units"]) else 0
    if full_cycle_gap > 0 and cycle != "short":
        return (
            f"{label} has an estimated {full_cycle_gap:,}-unit supply gap for the full "
            f"{int(row['cycle_weeks'])}-week planning cycle even after eligible confirmed inbound. "
            "Verify forecast assumptions and receipt dates; prioritize additional donations "
            "or purchasing before making commitments."
        )
    if on_hand == "short" and cycle == "adequate":
        return f"{label} is short on hand; confirm inbound receipt dates before promising these units."
    if on_hand == "short" and cycle == "long":
        return f"{label} is short today but long after expected receipts; verify arrivals before further purchasing."
    if cycle == "short":
        gap = int(row["gap_to_short_threshold_units"])
        return f"Prioritize {label} in the next drive or purchase review; at least {gap:,} additional units reach the {row['short_weeks']:g}-week minimum at the estimated run rate."
    if on_hand == "long" and cycle == "long":
        return f"Reduce {label} in the next donation ask; verify partner size needs before pursuing a transfer."
    if cycle == "long":
        return f"Projected coverage for {label} is long; review scheduled receipts and reduce future requests if confirmed."
    if on_hand == "short":
        return f"{label} is short in current stock; prioritize receiving the confirmed inbound before distribution."
    if on_hand == "long":
        return f"Review excess on-hand {label} against actual partner demand before asking donors for more."
    return f"Continue monitoring {label} against upcoming distributions and confirmed receipt dates."


def build_inventory_alerts(
    forecasts: pd.DataFrame,
    prepared: dict,
    *,
    short_weeks: float = 3.0,
    long_weeks: float = 12.0,
) -> dict:
    """Calculate SKU-level alert metrics over the *same* Gate 4 cycle.

    WOS = available units / mean weekly forecast units.
    Brief-compliant projected WOS counts on-hand plus only Gate 4 eligible
    confirmed inbound. The separate on-hand WOS describes physically counted
    inventory. No arrival-time assumption makes the cycle stock pickable now.

    Both metrics require a complete, positive forecast and an inventory record.
    Missing stock rows are not interpreted as verified physical zeros.
    """
    if (isinstance(short_weeks, bool) or isinstance(long_weeks, bool)
            or not all(isinstance(v, (int, float)) and isfinite(v) for v in (short_weeks, long_weeks))
            or not (0 <= short_weeks < long_weeks)):
        raise AlertsError("Thresholds must be finite with 0 <= short < long.")
    if not isinstance(prepared, dict) or "period" not in prepared:
        raise AlertsError("A Gate 4 prepared cycle is required.")
    period = prepared["period"]
    if not all(k in period for k in ("cycle_start", "cycle_end", "cycle_weeks", "inventory_as_of")):
        raise AlertsError("Prepared cycle is missing planning dates or duration.")
    raw_count = period["cycle_weeks"]
    if isinstance(raw_count, (bool, np.bool_)) or not isinstance(raw_count, (int, np.integer)):
        raise AlertsError("Prepared cycle duration must be a whole number of weeks.")
    count = int(raw_count)
    try:
        start = pd.Timestamp(period["cycle_start"])
        end = pd.Timestamp(period["cycle_end"])
    except (TypeError, ValueError, OverflowError) as exc:
        raise AlertsError("Invalid prepared cycle dates or duration.") from exc
    # Compare explicit calendar dates rather than NumPy's generic timedelta
    # arithmetic. This is stable across pandas/NumPy releases and enforces
    # the date-only, ISO-Monday cycle contract used by Gate 4.
    if (pd.isna(start) or pd.isna(end)
            or start.tzinfo is not None or end.tzinfo is not None
            or start != start.normalize() or end != end.normalize()
            or count < 1 or count > 8 or start.weekday() != 0
            or end.date() != start.date() + timedelta(days=7 * count - 1)):
        raise AlertsError("Prepared cycle is not a consecutive ISO-week interval.")

    fc = _table(forecasts, REQUIRED_FORECAST, "Forecast")
    dates = pd.to_datetime(fc["week_start"], errors="coerce")
    if dates.isna().any() or dates.dt.tz is not None or not dates.eq(dates.dt.normalize()).all():
        raise AlertsError("Forecast contains invalid dates.")
    fc["week_start"] = dates
    if fc["site_id"].isna().any() or fc["site_id"].astype(str).str.strip().eq("").any():
        raise AlertsError("Forecast site identifiers are missing.")
    if fc["requires_review"].isna().any() or not fc["requires_review"].isin([True, False]).all():
        raise AlertsError("Forecast review flags must be Boolean.")
    fc["forecast_units"] = _quantities(fc, "forecast_units", "Forecast", whole=False)
    if fc.duplicated(["site_id", *SKU, "week_start"]).any():
        raise AlertsError("Duplicate forecast keys could double count demand.")
    selected = fc.loc[fc["week_start"].between(start, end)].copy()
    expected = set(pd.date_range(start, periods=count, freq="W-MON"))
    if set(selected["week_start"].unique()) != expected or selected.empty:
        raise AlertsError("Forecast does not cover the selected cycle weeks.")
    if "site_id" in selected:
        sizes = selected.groupby(["site_id", *SKU])["week_start"].nunique()
        if sizes.ne(count).any():
            raise AlertsError("One or more site/product/size forecasts omit cycle weeks.")
    aggregated = selected.groupby(SKU, as_index=False).agg(
        forecast_cycle_units=("forecast_units", "sum"),
        forecast_requires_review=("requires_review", "any"),
        forecast_weeks=("week_start", "nunique"),
    )
    if aggregated["forecast_weeks"].ne(count).any():
        raise AlertsError("A product/size forecast is incomplete in the selected cycle.")
    aggregated["mean_weekly_forecast_units"] = aggregated["forecast_cycle_units"] / count

    inv = _table(prepared.get("on_hand"), SKU + ["on_hand_units"], "On-hand inventory")
    inc = _table(prepared.get("confirmed_inbound"), SKU + ["confirmed_inbound_units"], "Confirmed inbound")
    for frame, column, label in ((inv, "on_hand_units", "Inventory"), (inc, "confirmed_inbound_units", "Inbound")):
        frame[column] = _quantities(frame, column, label, whole=True).astype("Int64")
        if frame.duplicated(SKU).any():
            raise AlertsError(f"Duplicate {label} product/size keys would inflate stock.")

    inventory_keys = set(map(tuple, inv[SKU].itertuples(index=False, name=None)))
    forecast_keys = set(map(tuple, aggregated[SKU].itertuples(index=False, name=None)))
    all_keys = pd.concat([inv[SKU], inc[SKU], aggregated[SKU]]).drop_duplicates().reset_index(drop=True)
    result = all_keys.merge(inv, on=SKU, how="left", validate="one_to_one")
    result = result.merge(inc, on=SKU, how="left", validate="one_to_one")
    result = result.merge(aggregated, on=SKU, how="left", validate="one_to_one")
    result["inventory_row_present"] = [tuple(k) in inventory_keys for k in result[SKU].itertuples(index=False, name=None)]
    result["forecast_row_present"] = [tuple(k) in forecast_keys for k in result[SKU].itertuples(index=False, name=None)]
    result["on_hand_units"] = result["on_hand_units"].fillna(0).astype("int64")
    result["confirmed_inbound_units"] = result["confirmed_inbound_units"].fillna(0).astype("int64")
    max_units = np.iinfo(np.int64).max
    if (result["on_hand_units"] > max_units - result["confirmed_inbound_units"]).any():
        raise AlertsError("Combined on-hand and confirmed inbound exceeds supported unit range.")
    result["projected_cycle_units"] = result["on_hand_units"] + result["confirmed_inbound_units"]
    result["forecast_requires_review"] = result["forecast_requires_review"].map(
        lambda flag: True if pd.isna(flag) else bool(flag)
    ).astype(bool)
    positive = result["forecast_row_present"] & result["inventory_row_present"] & result["mean_weekly_forecast_units"].gt(0)
    result["on_hand_wos"] = np.where(positive, result["on_hand_units"] / result["mean_weekly_forecast_units"], np.nan)
    result["cycle_wos"] = np.where(positive, result["projected_cycle_units"] / result["mean_weekly_forecast_units"], np.nan)
    result["on_hand_status"] = [
        _status(row.on_hand_wos, row.inventory_row_present, row.forecast_row_present,
                row.mean_weekly_forecast_units, short_weeks, long_weeks)
        for row in result.itertuples(index=False)
    ]
    result["cycle_status"] = [
        _status(row.cycle_wos, row.inventory_row_present, row.forecast_row_present,
                row.mean_weekly_forecast_units, short_weeks, long_weeks)
        for row in result.itertuples(index=False)
    ]
    gap = (short_weeks * result["mean_weekly_forecast_units"] - result["projected_cycle_units"]).clip(lower=0)
    result["gap_to_short_threshold_units"] = np.where(positive, np.ceil(gap), np.nan)
    cycle_gap = (result["forecast_cycle_units"] - result["projected_cycle_units"]).clip(lower=0)
    result["cycle_supply_gap_units"] = np.where(positive, np.ceil(cycle_gap), np.nan)
    result["short_weeks"] = float(short_weeks)
    result["cycle_weeks"] = count  # Recommendation context only; not exported.
    result["recommendation"] = [_recommendation(row) for _, row in result.iterrows()]

    mix_parts = []
    for product, group in result.groupby("product", sort=True):
        # Suppress misleading percentages if any product variant is unmeasured.
        complete = group["inventory_row_present"].all() and group["forecast_row_present"].all()
        if not complete:
            continue
        stock_total = float(group["on_hand_units"].sum())
        forecast_total = float(group["forecast_cycle_units"].sum())
        if stock_total <= 0 or forecast_total <= 0:
            continue
        part = group[SKU].copy()
        part["on_hand_mix_pct"] = 100 * group["on_hand_units"] / stock_total
        part["forecast_mix_pct"] = 100 * group["forecast_cycle_units"] / forecast_total
        part["mismatch_index_pp"] = part["on_hand_mix_pct"] - part["forecast_mix_pct"]
        mix_parts.append(part)
    mix = (pd.concat(mix_parts, ignore_index=True) if mix_parts
           else pd.DataFrame(columns=MIX_COLUMNS))
    mix = mix.sort_values(SKU).reset_index(drop=True)
    result = result[ALERT_COLUMNS].sort_values(SKU).reset_index(drop=True)
    issues = []
    def warn(code, message, count_value):
        if count_value:
            issues.append({"code": code, "message": message, "count": int(count_value)})
    warn("missing_inventory_sku", "Forecast or inbound includes product sizes not present in the inventory snapshot; check stock completeness.", (~result["inventory_row_present"]).sum())
    warn("missing_forecast_sku", "Inventory or inbound includes product sizes without a demand forecast; stock risk is unknown, not zero.", (~result["forecast_row_present"]).sum())
    warn("zero_forecast_sku", "Zero forecast means WOS cannot be interpreted; review distribution history.", result["on_hand_status"].eq("zero_forecast_review").sum())
    warn("forecast_quality", "Some product-size forecasts have review flags; alerts are provisional.", result["forecast_requires_review"].sum())
    warn("mix_unavailable", "Inventory and forecast coverage is incomplete or all-zero for some products; their mix index is unavailable.", len(set(result["product"])) - mix["product"].nunique())
    original_warnings = prepared.get("warnings")
    if isinstance(original_warnings, pd.DataFrame) and not original_warnings.empty:
        for r in original_warnings.itertuples(index=False):
            issues.append({"code": f"allocation_{r.code}", "message": str(r.message), "count": int(r.count)})
    return {
        "alerts": result,
        "mismatch": mix,
        "warnings": pd.DataFrame(issues, columns=["code", "message", "count"]),
        "period": period,
        "thresholds": {"short_weeks": float(short_weeks), "long_weeks": float(long_weeks)},
        "summary": {
            "on_hand_short": int(result["on_hand_status"].eq("short").sum()),
            "on_hand_long": int(result["on_hand_status"].eq("long").sum()),
            "cycle_short": int(result["cycle_status"].eq("short").sum()),
            "cycle_long": int(result["cycle_status"].eq("long").sum()),
            "unassessable": int(result["on_hand_wos"].isna().sum()),
        },
    }
