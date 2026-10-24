"""Gate 5 Alerts: physically counted stock versus projected cycle supply.

Uses the existing cleaned-upload and forecast contracts. No uploaded data is
persisted and no inbound delivery is represented as ready-to-pick inventory.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from src.alerts import AlertsError, build_inventory_alerts
from src.allocation_inputs import prepare_allocation_inputs
from src.allocation_ui import csv_download, input_signature
from src.forecast_ui import ForecastUIError, data_signature, validate_forecast_table

st.set_page_config(page_title="Alerts | Supply Bank Allocator", page_icon="⚠️", layout="wide")
st.title("Inventory Risk & Size-Mismatch Alerts")
st.caption(
    "On-hand risk is based on physically counted stock. Projected-cycle coverage also includes "
    "eligible confirmed incoming units, which may not be ready to pick today. "
    "Forecasts estimate previous distribution patterns, not independently verified community need."
)

derived = st.session_state.get("derived_outputs")
cleaned = st.session_state.get("cleaned_results", {})
forecast_state = st.session_state.get("cp6_forecast_result")
if derived is None or "current_inventory" not in cleaned:
    st.warning("Load and clean your Distribution Log and Current Inventory on Upload first.")
    st.page_link("pages/1_Upload.py", label="Go to Upload", icon="📤")
    st.stop()
if forecast_state is None:
    st.warning("Generate a forecast before reviewing inventory risk.")
    st.page_link("pages/2_Forecast.py", label="Go to Forecast", icon="📈")
    st.stop()

try:
    master = derived.site_master
    weekly = derived.weekly_distribution
    if forecast_state.get("signature") != data_signature(weekly, master):
        raise ForecastUIError("The forecast belongs to a different upload or site master.")
    forecasts = forecast_state["forecasts"]
    validate_forecast_table(forecasts)
    inventory = cleaned["current_inventory"].cleaning_result.dataframe
    incoming_record = cleaned.get("incoming_supply")
    inbound = incoming_record.cleaning_result.dataframe if incoming_record else None
    source_signature = input_signature(forecasts, inventory, inbound, master)
    max_weeks = min(int(forecast_state["horizon"]), 8)
except (ValueError, TypeError, KeyError, AttributeError, ForecastUIError) as exc:
    st.error(f"Inventory alert inputs need review: {exc}")
    st.stop()

st.subheader("1 · Coverage assumptions")
with st.form("g5_alert_controls"):
    left, middle, right = st.columns(3)
    cycle_weeks = left.slider(
        "Planning cycle (weeks)", 1, max_weeks, min(4, max_weeks),
        help="Confirmed arrivals are counted only after the inventory snapshot and within this cycle.",
    )
    short_weeks = middle.slider("Short below (weeks)", 0.0, 52.0, 3.0, step=0.5)
    long_weeks = right.slider("Long above (weeks)", 0.5, 52.0, 12.0, step=0.5)
    submitted = st.form_submit_button("Calculate alerts", type="primary", width="stretch")

current = st.session_state.get("g5_alert_result")
setting_key = (source_signature, cycle_weeks, short_weeks, long_weeks)
if submitted:
    try:
        prepared = prepare_allocation_inputs(
            forecasts, inventory, inbound, master, cycle_weeks=cycle_weeks,
            forecast_issues=forecast_state.get("issues"),
        )
        report = build_inventory_alerts(
            forecasts, prepared, short_weeks=short_weeks, long_weeks=long_weeks,
        )
        current = {"key": setting_key, "report": report}
        st.session_state["g5_alert_result"] = current
    except (AlertsError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        st.session_state.pop("g5_alert_result", None)
        st.error(f"Cannot calculate safe inventory alerts: {exc}")
        st.stop()
if current is None or current.get("key") != setting_key:
    st.info("Select thresholds and click **Calculate alerts**. Recalculate after changing the inputs.")
    st.stop()

report = current["report"]
alerts = report["alerts"]
period = report["period"]
summary = report["summary"]
st.caption(
    f"Inventory snapshot: **{pd.Timestamp(period['inventory_as_of']).date()}** · "
    f"Forecast cycle: **{pd.Timestamp(period['cycle_start']).date()}–{pd.Timestamp(period['cycle_end']).date()}** · "
    f"Short < {short_weeks:g} weeks, long > {long_weeks:g} weeks."
)

st.subheader("2 · Inventory coverage")
a, b, c, d, e = st.columns(5)
a.metric("Network on-hand short", summary["on_hand_short"])
b.metric("Network on-hand long", summary["on_hand_long"])
c.metric("Network cycle short", summary["cycle_short"])
d.metric("Network cycle long", summary["cycle_long"])
e.metric("Network cannot assess", summary["unassessable"])

st.info(
    "**Important:** On-hand WOS = current counted units ÷ mean weekly forecast. "
    "Projected-cycle WOS = (on-hand + eligible confirmed inbound) ÷ the same forecast. "
    "The second is the Project Brief's WOS definition; it does not imply that incoming stock "
    "is already available for picking. Thresholds apply independently to both measures."
)
if forecast_state.get("demo_optin"):
    st.warning("Synthetic retrospective survey assumption was enabled; this is not a field-validated forecast.")
if not report["warnings"].empty:
    with st.expander(f"Data-quality and operational cautions ({len(report['warnings'])})", expanded=True):
        st.dataframe(report["warnings"], width="stretch", hide_index=True)
        st.caption("Unknown-size arrivals, pending donations and unverified past receipts are excluded by the upstream supply contract.")

product_options = sorted(alerts["product"].unique().tolist())
product = st.selectbox("Product family", options=product_options)
selected = alerts.loc[alerts["product"].eq(product)].copy()
show_cols = [
    "product", "size", "on_hand_units", "confirmed_inbound_units",
    "mean_weekly_forecast_units", "on_hand_wos", "on_hand_status",
    "cycle_wos", "cycle_status", "cycle_supply_gap_units",
    "forecast_requires_review", "recommendation",
]
st.dataframe(
    selected[show_cols].rename(columns={
        "on_hand_units": "Counted on hand", "confirmed_inbound_units": "Confirmed inbound (cycle)",
        "mean_weekly_forecast_units": "Forecast units / week",
        "on_hand_wos": "On-hand WOS", "cycle_wos": "Projected-cycle WOS",
        "cycle_supply_gap_units": f"{cycle_weeks}-week forecast supply gap (units)",
    }),
    width="stretch", hide_index=True,
)
st.caption(
    "A missing inventory size is UNKNOWN, not a verified zero stock balance. "
    "Zero or missing forecasts have no interpretable WOS. Forecast-review flags require staff judgment."
)

st.subheader("3 · Inventory-vs-demand size mix")
mix = report["mismatch"]
subset = mix.loc[mix["product"].eq(product)].copy()
if subset.empty:
    st.warning("Size-mix comparison is unavailable: inventory/forecast size coverage is incomplete or the product total is zero.")
else:
    data = subset.melt(
        id_vars=["product", "size"], value_vars=["on_hand_mix_pct", "forecast_mix_pct"],
        var_name="source", value_name="share_percent",
    )
    data["source"] = data["source"].map({
        "on_hand_mix_pct": "Counted inventory", "forecast_mix_pct": "Forecast distribution",
    })
    chart = px.bar(
        data, x="size", y="share_percent", color="source", barmode="group",
        labels={"share_percent": "Share of product family (%)", "size": "Variant", "source": ""},
        title=f"{product}: on-hand inventory vs. projected distribution mix",
        category_orders={"size": ["N", "1", "2", "3", "4", "5", "6", "7"]} if product == "diaper" else None,
    )
    # The diaper vocabulary mixes 'N' with numeric-looking sizes. If Plotly
    # auto-detects a numeric axis, the N bar can disappear from the plot even
    # though its row exists in the mismatch table. Force a categorical axis.
    chart.update_xaxes(type="category")
    if product == "diaper":
        chart.update_xaxes(
            categoryorder="array",
            categoryarray=["N", "1", "2", "3", "4", "5", "6", "7"],
        )
    st.plotly_chart(chart, width="stretch")
    st.dataframe(
        subset.assign(abs_gap=lambda df: df["mismatch_index_pp"].abs())
        .sort_values("abs_gap", ascending=False)
        .drop(columns=["abs_gap"]),
        hide_index=True, width="stretch",
    )
    st.caption(
        "Mismatch index (percentage points) = size share of counted on-hand inventory "
        "minus size share of forecast distributions **within the same product family**. "
        "Positive = relatively more stock than projected mix; negative = relatively less."
    )

st.subheader("4 · Review recommended actions")
risks = selected.loc[
    selected["on_hand_status"].isin(["short", "long"]) |
    selected["cycle_status"].isin(["short", "long"]) |
    selected["on_hand_wos"].isna()
]
if risks.empty:
    st.success("No threshold breaches in this product family for the selected assumptions.")
else:
    for row in risks.itertuples(index=False):
        st.write(f"**{row.product} / {row.size}:** {row.recommendation}")

st.subheader("5 · Download and eight-week planning ask")
st.download_button(
    "Download all inventory alerts (CSV)", csv_download(alerts),
    file_name="inventory_alerts.csv", mime="text/csv",
)
st.download_button(
    "Download size-mismatch index (CSV)", csv_download(mix),
    file_name="size_mismatch.csv", mime="text/csv", disabled=mix.empty,
)
if cycle_weeks != 8:
    st.caption(
        "To calculate a specific eight-week supply gap for the future Funder Report, "
        "generate an **8-week** forecast in Forecast and select an eight-week cycle here. "
        "A shorter forecast is not silently extrapolated."
    )
else:
    asks = alerts.loc[
        alerts["cycle_supply_gap_units"].gt(0) & alerts["on_hand_wos"].notna(),
        ["product", "size", "cycle_supply_gap_units"],
    ].copy()
    if asks.empty:
        st.info("No measurable eight-week forecast supply gap in the assessed sizes.")
    else:
        asks["unit_cost_usd"] = np.nan
        st.caption(
            "Optional: enter **verified USD cost per individual unit** to estimate a purchasing ask. "
            "Blank is unknown, not $0. These are planning gaps, not independently measured unmet community need."
        )
        costs = st.data_editor(
            asks, key=f"g5_alert_costs_{source_signature[:12]}",
            num_rows="fixed", hide_index=True,
            disabled=["product", "size", "cycle_supply_gap_units"],
            column_config={
                "unit_cost_usd": st.column_config.NumberColumn("Unit cost (USD)", min_value=0.01, format="$%.2f"),
            }, width="stretch",
        )
        prices = pd.to_numeric(costs["unit_cost_usd"], errors="coerce")
        invalid = (costs["unit_cost_usd"].notna() & (~np.isfinite(prices) | prices.le(0))).any()
        if invalid:
            st.error("Cost assumptions must be positive finite USD per individual unit; clear invalid cells.")
        else:
            costs["estimated_cost_usd"] = costs["cycle_supply_gap_units"] * prices
            total = costs["estimated_cost_usd"].sum(min_count=1)
            st.metric("Estimated cost for priced gaps", "N/A" if pd.isna(total) else f"${total:,.2f}")
            st.download_button(
                "Download 8-week planning ask (CSV)", csv_download(costs),
                file_name="eight_week_supply_gap_ask.csv", mime="text/csv",
            )
            st.caption("Total excludes sizes without a valid entered unit cost. A future Funder Report must preserve this limitation.")

with st.expander("How was this calculated?"):
    st.markdown(
        "**Forecast denominator:** sum of future weekly unit estimates for each product/size "
        "divided by the number of weeks in the selected cycle. "
        "**Physical stock:** dated on-hand inventory, with duplicate/location checks already applied by Upload. "
        "**Cycle incoming:** only confirmed, identified sizes arriving after the snapshot "
        "and no later than the cycle end; no double counting earlier receipts. "
        "**Flags:** WOS < short threshold is short, WOS > long threshold is long; "
        "the exact boundary is adequate. "
        "**Supply gap:** positive forecast-cycle units minus eligible cycle supply, rounded up; "
        "this is not a forecast of unconstrained social need. "
        "Size mismatch compares inventory and forecast shares *within* product categories, "
        "not across unrelated product types."
    )
