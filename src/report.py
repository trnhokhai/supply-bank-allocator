"""Gate 6A: provenance-safe, read-only data contract for an eight-week funder report.

Consumes the existing signature-checked Gate 4 *eight-week* saved plan. Does not
fit forecasts, solve allocations, mutate caller data, or generate a PDF.

Financial numbers are SKU-level potential supply-gap asks, NOT purchase orders.
Distribution history is NOT independently established community need.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd


class ReportError(ValueError):
    """Unsafe, incomplete, or incompatible report inputs."""


SKU = ["product", "size"]
CHILD = ["site_id", *SKU]
HIGH_POVERTY_BANDS = {"50_to_75_percent", "over_75_percent"}
LOW_POVERTY_BANDS = {"under_25_percent", "25_to_50_percent"}
PRICE_BASES = {"verified_quote", "scenario_assumption"}


def _table(frame, required, name, key=None):
    if not isinstance(frame, pd.DataFrame):
        raise ReportError(f"{name} must be a pandas DataFrame.")
    absent = set(required) - set(frame.columns)
    if absent:
        raise ReportError(f"{name} is missing: {sorted(absent)}.")
    out = frame.copy(deep=True)
    if key:
        if out[key].isna().any().any() or out.duplicated(key).any():
            raise ReportError(f"{name} has duplicate or missing identifying keys.")
        for field in key:
            if out[field].astype(str).str.strip().eq("").any():
                raise ReportError(f"{name} has empty identifying keys.")
    return out


def _whole(frame, field, label, *, nullable=False):
    values = pd.to_numeric(frame[field], errors="coerce")
    if nullable:
        invalid = frame[field].notna() & values.isna()
    else:
        invalid = values.isna()
    valid = values.dropna().to_numpy(dtype=float)
    if (invalid.any() or not np.isfinite(valid).all()
            or (valid < 0).any() or (valid % 1 != 0).any()):
        raise ReportError(f"{label} must contain nonnegative integer units (or null where allowed).")
    return values


def _money_cents(value):
    if isinstance(value, (bool, np.bool_)):
        raise ReportError("Unit price must be positive USD per individual unit.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ReportError("Unit price must be positive USD per individual unit.") from exc
    if (not amount.is_finite() or amount <= 0 or amount > Decimal("1000000000")
            or amount * 100 != (amount * 100).to_integral_value()):
        raise ReportError("Unit price must be positive USD with at most two decimal places.")
    return int(amount * 100)


def _period(saved_plan):
    try:
        prepared = saved_plan["prepared"]
        period = prepared["period"]
        settings = saved_plan["settings"]
        start = pd.Timestamp(period["cycle_start"])
        end = pd.Timestamp(period["cycle_end"])
        snapshot = pd.Timestamp(period["inventory_as_of"])
        weeks = period["cycle_weeks"]
    except (KeyError, ValueError, TypeError, OverflowError) as exc:
        raise ReportError("Saved allocation lacks a valid planning period.") from exc
    if (type(weeks) is not int or weeks != 8 or settings.get("cycle_weeks") != 8
            or any(pd.isna(v) or v.tzinfo is not None or v != v.normalize()
                   for v in (start, end, snapshot))
            or start.weekday() != 0 or end != start + timedelta(days=55)
            or snapshot > start):
        raise ReportError("Funder report needs a valid, saved 8-week allocation. Run Forecast (8 weeks) and Allocate (8 weeks) first.")
    return start, end, snapshot


def _high_need(row):
    """Known high/known lower/unknown. Missing optional flags are not 'no flags'."""
    has_survey = row.get("has_survey_data")
    if pd.isna(has_survey) or not bool(has_survey):
        return "unknown"
    poverty = row.get("poverty_share_band")
    flags = row.get("priority_population_flags")
    known_flags = isinstance(flags, str)
    has_priority = known_flags and bool(flags.strip().strip(";"))
    if poverty in HIGH_POVERTY_BANDS or has_priority:
        return "high"
    if poverty in LOW_POVERTY_BANDS and known_flags:
        return "lower"
    return "unknown"


def _historical(distribution, start):
    log = _table(distribution, ["date", "site_id", "quantity"], "Cleaned distribution log")
    dates = pd.to_datetime(log["date"], errors="coerce")
    if dates.isna().any() or dates.dt.tz is not None or not dates.eq(dates.dt.normalize()).all():
        raise ReportError("Distribution log has invalid calendar dates.")
    log["date"] = dates
    log["quantity"] = _whole(log, "quantity", "Historical distribution quantities")
    if log.empty:
        raise ReportError("Distribution history is empty.")
    origin = start - timedelta(days=7)
    max_date = log["date"].max()
    if not origin <= max_date <= origin + timedelta(days=6):
        raise ReportError("Last distribution ISO week differs from the saved forecast origin. Refresh Forecast and Allocate.")
    historical_start = origin - timedelta(days=49)
    historical_end = origin + timedelta(days=6)
    window = log.loc[log["date"].between(historical_start, historical_end)].copy()
    observed = {
        "window_start": historical_start,
        "window_end": historical_end,
        "last_recorded_date": max_date,
        "units_distributed": int(window["quantity"].sum()),
        "partners_with_distributions": int(window["site_id"].nunique()),
        "record_count": int(len(window)),
        "is_last_iso_week_potentially_partial": bool(max_date < historical_end),
    }
    for field, output in (("households_served", "household_service_count"),
                          ("children_served", "child_service_count")):
        if field not in window:
            observed[f"reported_{output}_sum"] = None
            observed[f"{output}_rows"] = 0
            continue
        nums = _whole(window, field, field, nullable=True)
        count = int(nums.notna().sum())
        observed[f"reported_{output}_sum"] = int(nums.sum()) if count else None
        observed[f"{output}_rows"] = count
    return observed


def _validated_plan(saved_plan):
    prepared, solved = saved_plan["prepared"], saved_plan["solved"]
    needs = _table(prepared["needs"], CHILD + ["need_units", "requires_review"],
                   "Prepared needs", CHILD)
    allocation = _table(solved["allocation"],
                        CHILD + ["need_units", "allocated_units", "unmet_units", "equity_weight"],
                        "Saved allocation", CHILD)
    supply = _table(prepared["supply"], SKU + ["available_units"], "Cycle supply", SKU)
    on_hand = _table(prepared["on_hand"], SKU + ["on_hand_units"], "Inventory snapshot", SKU)
    inbound = _table(prepared["confirmed_inbound"], SKU + ["confirmed_inbound_units"],
                     "Confirmed inbound", SKU)
    for frame, field in ((needs, "need_units"), (allocation, "need_units"),
                         (allocation, "allocated_units"), (allocation, "unmet_units"),
                         (supply, "available_units"), (on_hand, "on_hand_units"),
                         (inbound, "confirmed_inbound_units")):
        frame[field] = _whole(frame, field, field).astype("int64")
    if needs.empty or allocation.empty:
        raise ReportError("Cannot report an empty allocation.")
    if needs["requires_review"].isna().any() or not needs["requires_review"].isin([True, False]).all():
        raise ReportError("Forecast review flags are invalid.")
    check = needs[CHILD + ["need_units"]].merge(
        allocation[CHILD + ["need_units", "allocated_units", "unmet_units"]],
        on=CHILD, how="outer", validate="one_to_one", indicator=True,
        suffixes=("_prepared", "_allocated"),
    )
    if (check["_merge"] != "both").any() or not check["need_units_prepared"].eq(check["need_units_allocated"]).all():
        raise ReportError("Saved plan needs do not reconcile with allocation rows.")
    if not check["allocated_units"].add(check["unmet_units"]).eq(check["need_units_prepared"]).all():
        raise ReportError("Saved allocation units + unmet units do not equal need.")
    stock = supply.merge(on_hand, on=SKU, how="outer", validate="one_to_one").merge(
        inbound, on=SKU, how="outer", validate="one_to_one")
    for col in ("available_units", "on_hand_units", "confirmed_inbound_units"):
        stock[col] = stock[col].fillna(0)
    if not stock["available_units"].eq(stock["on_hand_units"] + stock["confirmed_inbound_units"]).all():
        raise ReportError("Saved supply is inconsistent with on-hand plus confirmed inbound.")
    use = allocation.groupby(SKU, as_index=False)["allocated_units"].sum()
    matched = use.merge(stock[SKU + ["available_units"]], on=SKU, how="left", validate="one_to_one")
    if (matched["allocated_units"] > matched["available_units"].fillna(0)).any():
        raise ReportError("Saved allocation exceeds confirmed cycle supply.")
    weights = pd.to_numeric(allocation["equity_weight"], errors="coerce")
    if (weights.isna().any() or not np.isfinite(weights.to_numpy(dtype=float)).all()
            or weights.lt(1).any()
            or allocation.assign(_weight=weights).groupby("site_id")["_weight"].nunique().gt(1).any()):
        raise ReportError("Saved allocation has invalid or inconsistent equity weights.")
    expected_weights = prepared.get("equity_weights")
    if expected_weights is not None:
        for site, observed_weight in allocation.assign(_weight=weights).groupby("site_id")["_weight"].first().items():
            try:
                correct_weight = float(expected_weights[site])
            except (KeyError, ValueError, TypeError) as exc:
                raise ReportError("Saved equity-weight metadata is incomplete.") from exc
            if not np.isfinite(correct_weight) or abs(correct_weight - observed_weight) > 1e-9:
                raise ReportError("Saved allocation equity weights do not match prepared inputs.")
    metrics = solved.get("metrics", {})
    expected = {"total_allocated_units": int(allocation["allocated_units"].sum()),
                "total_unmet_units": int(allocation["unmet_units"].sum())}
    if any(metrics.get(key) != value for key, value in expected.items()):
        raise ReportError("Saved plan metrics do not reconcile with its allocations.")
    return needs, allocation, supply, on_hand


def _ask(needs, allocation, supply, on_hand, prices):
    total_need = needs.groupby(SKU, as_index=False)["need_units"].sum()
    unmet = allocation.groupby(SKU, as_index=False)["unmet_units"].sum()
    gap = total_need.merge(unmet, on=SKU, validate="one_to_one").merge(
        supply, on=SKU, how="left", validate="one_to_one")
    gap = gap.merge(on_hand[SKU].assign(snapshot_row_present=True), on=SKU,
                    how="left", validate="one_to_one")
    # A missing inventory SKU is UNMEASURED, never a certified zero.
    if (gap["need_units"].gt(0) & gap["snapshot_row_present"].isna()).any():
        raise ReportError("A forecast product/size has no verified inventory snapshot row. Review inventory before reporting a funding ask.")
    gap["available_units"] = gap["available_units"].fillna(0)
    gap["supply_gap_units"] = (gap["need_units"] - gap["available_units"]).clip(lower=0).astype("int64")
    gap["unit_cost_usd"] = pd.Series([None] * len(gap), dtype="object")
    gap["price_basis"] = pd.Series([None] * len(gap), dtype="object")
    gap["estimated_cost_usd"] = pd.Series([None] * len(gap), dtype="object")
    if prices is not None:
        quotes = _table(prices, SKU + ["unit_cost_usd", "price_basis"], "Unit price assumptions", SKU)
        listed_skus = set(map(tuple, gap[SKU].itertuples(index=False, name=None)))
        if any(tuple(x) not in listed_skus for x in quotes[SKU].itertuples(index=False, name=None)):
            raise ReportError("A price was provided for a product/size outside the current forecast.")
        for q in quotes.itertuples(index=False):
            if pd.isna(q.unit_cost_usd):
                continue
            if q.price_basis not in PRICE_BASES:
                raise ReportError("Every entered price must identify verified_quote or scenario_assumption.")
            cents = _money_cents(q.unit_cost_usd)
            match = gap["product"].eq(q.product) & gap["size"].eq(q.size)
            ix = gap.index[match][0]
            gap.at[ix, "unit_cost_usd"] = cents / 100
            gap.at[ix, "price_basis"] = q.price_basis
            gap.at[ix, "estimated_cost_usd"] = int(gap.at[ix, "supply_gap_units"]) * cents / 100
    requested = gap.loc[gap["supply_gap_units"].gt(0)].copy()
    priced = requested.loc[requested["estimated_cost_usd"].notna()]
    all_priced = bool(len(priced) == len(requested))
    pricing = {
        "sku_gaps": int(len(requested)),
        "priced_sku_gaps": int(len(priced)),
        "partially_costed_usd": round(float(priced["estimated_cost_usd"].sum()), 2),
        "fully_costed_ask_usd": round(float(priced["estimated_cost_usd"].sum()), 2) if all_priced else None,
        "all_prices_verified_quotes": bool(all_priced and priced["price_basis"].eq("verified_quote").all()),
    }
    return gap.sort_values(SKU).reset_index(drop=True), requested.sort_values(SKU).reset_index(drop=True), pricing


def build_report_data(distribution_log: pd.DataFrame, site_master: pd.DataFrame,
                      saved_plan: dict, *, expected_signature: str,
                      prices: pd.DataFrame | None = None) -> dict:
    """Build auditable report content from the *existing* eight-week operational plan.

    expected_signature must be recomputed by Report UI using the current
    forecast, inventory, inbound and site master via allocation_ui.input_signature.
    """
    if not isinstance(saved_plan, dict):
        raise ReportError("No saved allocation plan. Run an eight-week allocation first.")
    if (not isinstance(expected_signature, str) or not expected_signature
            or saved_plan.get("signature") != expected_signature):
        raise ReportError("Saved allocation is stale relative to current inputs.")
    start, end, snapshot = _period(saved_plan)
    needs, allocation, supply, on_hand = _validated_plan(saved_plan)
    master = _table(site_master, ["site_id", "has_survey_data",
                                  "poverty_share_band", "priority_population_flags"],
                    "Site master", ["site_id"])
    if not set(allocation["site_id"]).issubset(set(master["site_id"])):
        raise ReportError("Allocation includes unknown partner sites.")
    observed = _historical(distribution_log, start)
    historical_ids = set(distribution_log["site_id"].dropna().astype(str))
    if not historical_ids.issubset(set(master["site_id"].astype(str))):
        raise ReportError("Historical partner IDs are inconsistent with the current site master.")
    gap_by_sku, ask_by_sku, pricing = _ask(needs, allocation, supply, on_hand, prices)
    classified = master[["site_id", "has_survey_data", "poverty_share_band",
                         "priority_population_flags"]].copy()
    classified["classification"] = classified.apply(_high_need, axis=1)
    by_site = allocation.groupby("site_id", as_index=False).agg(
        allocated_units=("allocated_units", "sum"),
        unmet_units=("unmet_units", "sum"), need_units=("need_units", "sum"))
    by_site = by_site.merge(classified[["site_id", "classification"]],
                            on="site_id", how="left", validate="one_to_one")
    total_allocated = int(by_site["allocated_units"].sum())
    known_high = int(by_site.loc[by_site["classification"].eq("high"), "allocated_units"].sum())
    known_any = int(by_site.loc[by_site["classification"].isin(["high", "lower"]), "allocated_units"].sum())
    equity = {
        "definition": "High-need = survey poverty band >=50% OR >=1 priority-population flag; missing values are unknown.",
        "planned_high_need_share_of_all_allocations_pct":
            (100 * known_high / total_allocated if total_allocated and known_any else None),
        "classification_coverage_of_allocations_pct":
            (100 * known_any / total_allocated if total_allocated else None),
        "classified_high_need_partners": int(by_site["classification"].eq("high").sum()),
        "unknown_classification_partners": int(by_site["classification"].eq("unknown").sum()),
    }
    issues = saved_plan["prepared"].get("forecast_issues")
    unresolved = int(issues["site_id"].nunique()) if isinstance(issues, pd.DataFrame) and "site_id" in issues else 0
    flags = []
    if observed["is_last_iso_week_potentially_partial"]:
        flags.append("Last observed ISO week may be partial; only logged distributions counted.")
    if observed["reported_household_service_count_sum"] is not None:
        flags.append("Household service-count fields are not deduplicated or certified unique families.")
        if observed["household_service_count_rows"] < observed["record_count"]:
            flags.append("Household service-count fields are missing on some distribution records.")
    if observed["reported_child_service_count_sum"] is not None:
        flags.append("Child service-count fields are not deduplicated or certified unique children.")
        if observed["child_service_count_rows"] < observed["record_count"]:
            flags.append("Child service-count fields are missing on some distribution records.")
    if needs["requires_review"].any():
        flags.append("Some forecasts are provisional or flagged for review.")
    if unresolved:
        flags.append(f"{unresolved} site(s) have unresolved forecasts; network coverage is incomplete.")
    if len(ask_by_sku) != pricing["priced_sku_gaps"]:
        flags.append("The funding ask contains SKUs with no unit prices; total dollars are unavailable.")
    if pricing["priced_sku_gaps"] and not pricing["all_prices_verified_quotes"]:
        flags.append("Some prices are scenario assumptions, not verified supplier quotations.")
    if equity["classification_coverage_of_allocations_pct"] is None or equity["classification_coverage_of_allocations_pct"] < 100:
        flags.append("High-need partner classification is incomplete; unknown partners remain in the denominator.")
    prep_warnings = saved_plan["prepared"].get("warnings")
    if isinstance(prep_warnings, pd.DataFrame) and "message" in prep_warnings:
        flags.extend(str(message) for message in prep_warnings["message"].dropna())
    return {
        "periods": {"historical_start": observed["window_start"],
                    "historical_end": observed["window_end"],
                    "historical_last_recorded": observed["last_recorded_date"],
                    "forecast_start": start, "forecast_end": end, "forecast_weeks": 8,
                    "inventory_as_of": snapshot},
        "observed": observed,
        "planning": {"need_units": int(allocation["need_units"].sum()),
                     "allocated_units": total_allocated,
                     "modeled_unmet_units": int(allocation["unmet_units"].sum()),
                     "modeled_partners": int(by_site["site_id"].nunique()),
                     "review_flagged_sku_site_rows": int(needs["requires_review"].sum()),
                     "unresolved_forecast_sites": unresolved,
                     "supply_gap_units": int(gap_by_sku["supply_gap_units"].sum())},
        "equity": equity,
        "gap_by_sku": gap_by_sku,
        "ask_by_sku": ask_by_sku,
        "pricing": pricing,
        "warnings": flags,
        "labels": {"modeled_unmet": "Modeled 8-week distribution-proxy shortfall (NOT measured community need)",
                   "equity": "Share of modeled allocations to classified high-need partners (NOT actual distribution)",
                   "ask": "Potential SKU supply-gap ask (NOT an approved purchase order)"},
    }
