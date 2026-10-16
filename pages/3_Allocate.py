"""Gate 4 Allocation: explainable one-cycle plans and stock-on-hand pick drafts.

Depends on verified Week 2 cleaned tables and the current Week 3 forecast
stored in the Streamlit session. Does not write uploaded data to disk.
"""

from time import perf_counter

import pandas as pd
import streamlit as st

from src.allocate import AllocationError
from src.allocation_inputs import prepare_allocation_inputs, run_operational_allocation
from src.allocation_ui import (
    comparison_summary,
    csv_download,
    input_signature,
    partner_summary,
    verified_capacity_overrides,
)
from src.forecast_ui import ForecastUIError, data_signature, validate_forecast_table

st.set_page_config(page_title="Allocation | Supply Bank Allocator", page_icon="📦", layout="wide")
st.title("Allocate Essential Supplies")
st.caption(
    "Equity-aware cycle plan, proportional comparison, and a stock-on-hand pick suggestion. "
    "Forecasts estimate historical distribution patterns, NOT measured unconstrained community need."
)

# Each page is session-only: require current, cleaned inputs and the user's
# actual latest forecast instead of rerunning a second model behind their back.
derived = st.session_state.get("derived_outputs")
cleaned = st.session_state.get("cleaned_results", {})
forecast_state = st.session_state.get("cp6_forecast_result")
if derived is None:
    st.warning("First open Upload, load your files or Demo Mode, and click Clean & Validate.")
    st.page_link("pages/1_Upload.py", label="Go to Upload", icon="📤")
    st.stop()
if "current_inventory" not in cleaned:
    st.warning("Current Inventory is required for allocation. Upload and validate an inventory snapshot.")
    st.page_link("pages/1_Upload.py", label="Go to Upload", icon="📤")
    st.stop()
if forecast_state is None:
    st.warning("Generate a forecast first, then return here. Allocation uses that SAME forecast output.")
    st.page_link("pages/2_Forecast.py", label="Go to Forecast", icon="📈")
    st.stop()

try:
    weekly = derived.weekly_distribution
    master = derived.site_master
    expected_signature = data_signature(weekly, master)
    if forecast_state.get("signature") != expected_signature:
        raise ForecastUIError("The saved forecast belongs to an earlier upload or site master.")
    forecasts = forecast_state["forecasts"]
    validate_forecast_table(forecasts)
    if forecasts.empty:
        raise ForecastUIError("The forecast contains no allocatable series.")
    inventory = cleaned["current_inventory"].cleaning_result.dataframe
    incoming_record = cleaned.get("incoming_supply")
    inbound = incoming_record.cleaning_result.dataframe if incoming_record is not None else None
    signature = input_signature(forecasts, inventory, inbound, master)
except (ValueError, TypeError, KeyError, AttributeError, ForecastUIError) as exc:
    st.error(f"Allocation inputs must be reviewed: {exc}")
    st.page_link("pages/2_Forecast.py", label="Regenerate forecast", icon="📈")
    st.stop()

# Invalidate old plans even when only inventory or incoming supply was replaced.
previous = st.session_state.get("g4_allocation_result")
if previous is not None and previous.get("signature") != signature:
    st.session_state.pop("g4_allocation_result", None)
    previous = None

horizon = int(forecast_state["horizon"])
max_cycle = min(horizon, 8)
origin = pd.Timestamp(forecast_state["origin"])
st.caption(
    f"Forecast origin: **{origin.date()}** · Available forecast horizon: **{horizon} weeks** · "
    "Data remains in this app session."
)
if forecast_state.get("demo_optin"):
    st.warning("Retrospective synthetic demo mode: undated survey inputs were explicitly allowed. This is NOT real-world validation.")

st.subheader("1 · Planning settings")
with st.form("g4_allocation_controls", clear_on_submit=False):
    c1, c2, c3 = st.columns(3)
    cycle_weeks = c1.slider("Planning cycle (weeks)", min_value=1,
                            max_value=max_cycle, value=min(4, max_cycle), step=1,
                            help="Choose the first N consecutive weeks of the displayed forecast.")
    alpha = c2.slider("Poverty-share weight (alpha)", min_value=0.0, max_value=2.0,
                      value=0.5, step=0.05)
    beta = c3.slider("Priority-population weight (beta)", min_value=0.0, max_value=1.0,
                     value=0.25, step=0.05)
    d1, d2 = st.columns(2)
    fairness = d1.slider("Requested minimum fill (fairness floor)",
                         min_value=0.0, max_value=1.0, value=0.60, step=0.05,
                         help="May be adjusted downward for SKU-level shortages or indivisible units; adjustments are reported.")
    penalty = d2.slider("Maximum-site-shortfall penalty (share of network need)",
                        min_value=0.0, max_value=0.20, value=0.01, step=0.01,
                        help="Adds share × total planning need × worst-site shortfall rate to weighted unmet need. Not a hard guarantee.")

    with st.expander("Optional: verified storage capacity limits (individual units)"):
        st.caption("Do NOT enter survey storage capacity in cases here. Only use a verified total individual-unit cap "
                   "for each partner for the whole planning cycle. Leave blank when unknown.")
        cap_enabled = st.checkbox("Apply verified individual-unit storage capacities", value=False)
        cap_editor = None
        if cap_enabled:
            cap_editor = master[["site_id", "site_name"]].copy()
            cap_editor["capacity_units"] = pd.Series([float("nan")] * len(cap_editor), dtype="float64")
            cap_editor = st.data_editor(
                cap_editor, hide_index=True, num_rows="fixed", key="g4_capacity_editor",
                disabled=["site_id", "site_name"],
                column_config={
                    "site_id": st.column_config.TextColumn("Partner ID"),
                    "site_name": st.column_config.TextColumn("Partner"),
                    "capacity_units": st.column_config.NumberColumn(
                        "Verified unit capacity", min_value=0, step=1,
                        help="Individual units across all product-size combinations during this cycle.",
                    ),
                }, width="stretch",
            )
    submitted = st.form_submit_button("Optimize allocation", type="primary", width="stretch")

if submitted:
    start = perf_counter()
    try:
        capacities = (verified_capacity_overrides(cap_editor, set(master["site_id"].astype(str)))
                      if cap_enabled else {})
        prepared = prepare_allocation_inputs(
            forecasts, inventory, inbound, master, cycle_weeks=cycle_weeks,
            alpha=alpha, beta=beta, capacities_units=capacities,
            forecast_issues=forecast_state.get("issues"),
        )
        with st.spinner("Solving allocation and preparing stock-on-hand pick suggestions..."):
            solved = run_operational_allocation(
                prepared, fairness_floor=fairness,
                worst_shortfall_penalty_share=penalty, time_limit_seconds=8,
            )
        st.session_state["g4_allocation_result"] = {
            "signature": signature, "solved": solved, "prepared": prepared,
            "settings": {"cycle_weeks": cycle_weeks, "alpha": alpha, "beta": beta,
                         "fairness_floor": fairness, "penalty_share": penalty,
                         "verified_capacity_count": len(capacities)},
            "elapsed_total_seconds": perf_counter() - start,
        }
    except (AllocationError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        st.session_state.pop("g4_allocation_result", None)
        st.error(f"No safe allocation plan could be created: {exc}")
        st.info("Check inventory dates, forecast completeness, storage caps, and fairness constraints. "
                "The optimizer will not silently invent missing supply or return an infeasible plan.")
        st.stop()

state = st.session_state.get("g4_allocation_result")
if state is None:
    st.info("Choose planning settings and click **Optimize allocation** to calculate a plan.")
    st.stop()

solved = state["solved"]
prepared = state["prepared"]
settings = state["settings"]
period = solved["period"]
metrics = solved["metrics"]
ops = solved["operational_summary"]
comparison = comparison_summary(solved)

st.subheader("2 · Allocation results")
st.caption(
    f"Cycle: **{period['cycle_start'].date()} – {period['cycle_end'].date()}** "
    f"({settings['cycle_weeks']} weeks) · Inventory snapshot: **{period['inventory_as_of'].date()}** "
    f"· End-to-end run: **{state['elapsed_total_seconds']:.2f}s** "
    f"(including solver {solved['elapsed_seconds']:.2f}s)"
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Cycle allocated", f"{ops['allocated_cycle_units']:,} units")
c2.metric("Planning unmet", f"{metrics['total_unmet_units']:,} units")
c3.metric("Ready from on-hand", f"{ops['ready_now_units']:,} units")
c4.metric("Awaiting incoming", f"{ops['awaiting_inbound_units']:,} units")

warnings = solved["warnings"]
if not warnings.empty:
    st.warning(
        "**Planning cautions:** Review the flags below before treating the allocation as an operational commitment. "
        "A ready-now pick suggestion must be checked against physical stock and distribution arrangements."
    )
    with st.expander(f"Input and planning warnings ({len(warnings)})", expanded=True):
        st.dataframe(warnings, width="stretch", hide_index=True)
if not solved["forecast_issues"].empty:
    with st.expander("Partners with unresolved forecasts — not assumed to have zero demand"):
        st.dataframe(solved["forecast_issues"], width="stretch", hide_index=True)

st.markdown("#### Optimized vs. proportional baseline")
b1, b2, b3, b4 = st.columns(4)
b1.metric("Optimized weighted unmet", f"{comparison['optimized_weighted_unmet']:,.1f}",
          delta=f"{comparison['weighted_units_improved']:+,.1f} weighted units improved")
b2.metric("Baseline weighted unmet", f"{comparison['baseline_weighted_unmet']:,.1f}")
b3.metric("Optimized worst-site fill", f"{comparison['optimized_worst_fill_pct']:.1f}%",
          delta=f"{comparison['worst_fill_delta_pp']:+.2f} percentage points")
b4.metric("Baseline worst-site fill", f"{comparison['baseline_worst_fill_pct']:.1f}%")
if comparison["weighted_units_improved"] <= 0:
    st.info("This run did not improve weighted planning unmet units versus the constrained proportional baseline.")
if comparison["worst_fill_delta_pp"] < -1e-7:
    st.warning("Trade-off: worst-partner fill rate DECREASED versus the baseline. "
               "The maximum-shortfall penalty is a soft objective, not a guaranteed floor.")
elif comparison["worst_fill_delta_pp"] > 1e-7:
    st.success("The worst-partner fill rate increased versus the proportional baseline in this run.")
else:
    st.caption("Worst-partner fill rate is unchanged versus the proportional baseline.")

gain_pct = comparison["weighted_improvement_pct"]
if gain_pct is not None:
    st.caption(f"Relative reduction in weighted planning unmet: **{gain_pct:+.2f}%** "
               "versus the proportional baseline (negative means deterioration).")
else:
    st.caption("Relative weighted improvement: N/A (baseline weighted unmet is zero).")

st.caption("Baseline type: " + solved["baseline_type"].replace("_", " ") +
           ". Weighted units are an equity-weighted planning score, not physical units of unmet community demand.")

with st.expander("How was this calculated?", expanded=False):
    st.markdown(
        "**Planning need:** weekly Week 3 point forecasts are aggregated over the selected cycle "
        "and rounded to whole units while preserving each network product-size total. Historical distributions "
        "may understate unconstrained need.\n\n"
        "**Supply:** on-hand stock plus confirmed, size-identified arrivals dated after the inventory snapshot "
        "and no later than the cycle end. Pending, unknown-size, and late deliveries are not used.\n\n"
        "**Equity:** partner weight = 1 + alpha × poverty-score + beta × number of priority flags. "
        "Missing survey evidence defaults to weight 1.\n\n"
        "**Objective:** minimize weighted planning unmet units plus "
        "(penalty share × total planning need × maximum partner shortfall rate). "
        "The fairness minimum is relaxed for scarce individual sizes or integer rounding as needed.\n\n"
        "**Comparison:** the proportional baseline uses the same demand, verified inventory, minimums, "
        "and any verified storage caps. Improvements are not guaranteed."
    )

fair = solved["fairness"]
with st.expander("Fairness minimums actually applied"):
    st.caption("Scarcity-adjusted and integer-adjusted minimums can be lower than the requested floor.")
    st.dataframe(fair, width="stretch", hide_index=True)
    st.caption("A partner's combined fill rate can differ from an individual size-level floor.")

with st.expander("Inventory and confirmed supply actually considered"):
    source = (prepared["supply"]
              .merge(prepared["on_hand"], on=["product", "size"], how="left")
              .merge(prepared["confirmed_inbound"], on=["product", "size"], how="left"))
    st.dataframe(source, width="stretch", hide_index=True)
    st.caption("Available for the cycle is NOT necessarily available for immediate picking. "
               "Stock counted after the snapshot date is not silently included twice.")

st.markdown("#### By partner")
by_site = partner_summary(solved["allocation"])
st.dataframe(by_site, width="stretch", hide_index=True,
             column_config={"fill_rate_pct": st.column_config.NumberColumn("Fill rate (%)", format="%.1f%%")})

st.markdown("#### Allocation by product and size")
allocation = solved["allocation"]
show_columns = [
    "site_name", "site_id", "product", "size", "need_units", "allocated_units",
    "unmet_units", "fairness_min_units", "equity_weight", "ready_now_units",
    "awaiting_inbound_units", "requires_review", "quality_flags", "forecast_source", "method",
]
st.dataframe(allocation[[c for c in show_columns if c in allocation.columns]],
             width="stretch", hide_index=True)

st.subheader("3 · Download planning outputs")
left, middle, right = st.columns(3)
left.download_button(
    "Allocation plan (CSV)", csv_download(allocation),
    file_name="allocation_cycle_plan.csv", mime="text/csv", width="stretch",
)
middle.download_button(
    "Partner summary (CSV)", csv_download(by_site),
    file_name="allocation_partner_summary.csv", mime="text/csv", width="stretch",
)
pick = solved["ready_now_pick_list"]
right.download_button(
    "All-partner pick draft (CSV)", csv_download(pick),
    file_name="ready_now_pick_draft.csv", mime="text/csv", width="stretch",
    disabled=pick.empty,
)
st.caption("The ready-now file is a draft based on the recorded inventory snapshot; "
           "it must be verified before staff physically pick or ship products. "
           "Confirmed future arrivals appear only in the cycle plan until received.")

partner_options = sorted(pick["site_id"].astype(str).unique().tolist()) if not pick.empty else []
if partner_options:
    chosen_partner = st.selectbox(
        "Download an individual partner pick draft",
        options=partner_options,
        format_func=lambda site: f"{prepared['site_names'].get(site, site)} ({site})",
    )
    st.download_button(
        "Download selected partner pick draft (CSV)",
        csv_download(pick.loc[pick["site_id"].eq(chosen_partner)]),
        file_name="ready_now_pick_" + "".join(
            char if char.isalnum() or char in "-_" else "_" for char in chosen_partner
        ) + ".csv",
        mime="text/csv",
    )
else:
    st.info("No stock-on-hand pick rows are available in this plan.")

st.caption("Gate 4 planning results require independent manual review. Results are not field-validated; "
           "solver success alone is not proof of equitable impact.")
