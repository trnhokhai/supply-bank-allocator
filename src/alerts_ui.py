"""Presentation-only helpers for the Inventory Alerts page.

Do not modify WOS, shortfall calculations, or upstream supply contracts here.
"""

import pandas as pd


def actionable_alert_rows(alerts: pd.DataFrame) -> pd.DataFrame:
    """Keep threshold warnings, unknown coverage, and positive cycle gaps.

    A three-week WOS threshold can be adequate even when a longer planning
    cycle lacks enough stock. Never hide that actionable planning shortfall.
    """
    attention = (
        alerts["on_hand_status"].isin(["short", "long"])
        | alerts["cycle_status"].isin(["short", "long"])
        | alerts["on_hand_wos"].isna()
        | alerts["cycle_supply_gap_units"].gt(0)
    )
    return alerts.loc[attention].copy()


def staff_action_queue(alerts: pd.DataFrame) -> pd.DataFrame:
    """Prioritize visible operator checks; never alter risk math or source rows.

    A review order is NOT a verified emergency severity or purchase instruction.
    """
    required = {"product", "size", "on_hand_status", "cycle_status", "on_hand_wos",
                "cycle_supply_gap_units", "forecast_requires_review"}
    if not isinstance(alerts, pd.DataFrame) or not required.issubset(alerts.columns):
        raise ValueError("Staff action queue requires a complete alert table.")
    rows = actionable_alert_rows(alerts).copy()
    columns = ["product", "size", "review_first", "why", "next_action",
               "cycle_supply_gap_units", "on_hand_wos"]
    if rows.empty:
        return pd.DataFrame(columns=columns)

    def describe(row):
        on_hand = str(row.on_hand_status)
        cycle = str(row.cycle_status)
        gap = float(row.cycle_supply_gap_units) if pd.notna(row.cycle_supply_gap_units) else 0.0
        coverage = (f"{float(row.on_hand_wos):.1f} weeks of current stock"
                    if pd.notna(row.on_hand_wos) else "unknown current coverage")
        gap_text = f"{int(gap):,} modeled units short for the selected cycle" if gap > 0 else "no modeled gap for the selected cycle"
        if on_hand in ("inventory_missing", "forecast_missing", "zero_forecast_review") or pd.isna(row.on_hand_wos):
            return (0, "Verify missing data", f"{coverage}; coverage cannot be assessed.",
                    "Verify stock records and forecast quality before relying on this size.")
        if on_hand == "short":
            return (1, "Check current stock", f"{coverage}; {gap_text}.",
                    "Confirm count, next distribution date and actual receipts; review replenishment if the gap remains.")
        if cycle == "short":
            return (1, "Check projected stock", f"{coverage}; projected coverage is below the selected threshold.",
                    "Verify inbound dates and stock before committing quantities.")
        if gap > 0:
            return (2, "Plan cycle gap", f"{coverage}; {gap_text}, even though the WOS alert may be adequate.",
                    "Check the forecast and receipts; plan a donation request if the gap remains.")
        if on_hand == "long" or cycle == "long":
            return (3, "Review potential excess", f"{coverage}; above a long-stock threshold.",
                    "Check partner size needs before reducing the next donation request.")
        return (4, "Monitor", f"{coverage}; no detected actionable gap.",
                "Continue checking forecasts and physical inventory.")

    details = [describe(row) for row in rows.itertuples(index=False)]
    rows["_priority"] = [x[0] for x in details]
    rows["review_first"] = [x[1] for x in details]
    rows["why"] = [x[2] for x in details]
    rows["next_action"] = [x[3] for x in details]
    rows["_gap_sort"] = pd.to_numeric(rows["cycle_supply_gap_units"], errors="coerce").fillna(0)
    rows = rows.sort_values(["_priority", "_gap_sort", "product", "size"],
                            ascending=[True, False, True, True], kind="stable")
    return rows[columns].reset_index(drop=True)
