"""Gate 5 what-if scenarios: compare against the user's actual Gate 4 plan.

Pure hypothetical planning. Never overwrites a confirmed forecast, physical
stock count, or allocatable ready-now pick list.
"""

import pandas as pd
import streamlit as st

from src.allocation_ui import csv_download, input_signature
from src.forecast_ui import data_signature, validate_forecast_table
from src.scenarios import ScenarioError, run_counterfactual

def _has_current_demand_audit(payload: object) -> bool:
    """Only display results produced under the current scenario schema.

    Streamlit can retain an old scenario in session_state (or import a previously
    loaded Python module) after the page code is updated. Such results did not
    include demand reconciliation. Never silently invent or omit its audit.
    """
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("demand_audit"), dict)
        and {"expected_delta_units", "integer_need_delta_units"}.issubset(payload["demand_audit"])
    )


st.set_page_config(page_title="Scenarios | Supply Bank Allocator", page_icon="🔀", layout="wide")
st.title("What-if Supply & Allocation Scenarios")
st.caption(
    "Start with the operational plan you approved on Allocate. Each scenario creates in-memory copies, "
    "re-solves the SAME fairness objective, and compares to that original plan. "
    "Hypothetical stock and purchases are never physical pick authorization."
)

original = st.session_state.get("g4_allocation_result")
derived = st.session_state.get("derived_outputs")
cleaned = st.session_state.get("cleaned_results", {})
forecast_state = st.session_state.get("cp6_forecast_result")
if original is None:
    st.warning("First generate a forecast and click **Optimize allocation** in Allocate. That result is the immutable scenario baseline.")
    st.page_link("pages/3_Allocate.py", label="Go to Allocate", icon="📦")
    st.stop()
if derived is None or forecast_state is None or "current_inventory" not in cleaned:
    st.warning("Original uploads, a validated inventory count, and a current forecast are required.")
    st.stop()

try:
    master = derived.site_master
    forecasts = forecast_state["forecasts"]
    validate_forecast_table(forecasts)
    if forecast_state.get("signature") != data_signature(derived.weekly_distribution, master):
        raise ScenarioError("Forecast belongs to an earlier data upload.")
    inventory = cleaned["current_inventory"].cleaning_result.dataframe
    rec = cleaned.get("incoming_supply")
    inbound = rec.cleaning_result.dataframe if rec is not None else None
    signature = input_signature(forecasts, inventory, inbound, master)
    if original.get("signature") != signature:
        raise ScenarioError("Allocation plan is stale relative to the forecast, inventory, or incoming supply. Re-optimize Allocate first.")
    period = original["prepared"]["period"]
    settings = original["settings"]
    if settings["cycle_weeks"] != period["cycle_weeks"]:
        raise ScenarioError("The saved allocation cycle is inconsistent; regenerate the baseline.")
except (ValueError, KeyError, TypeError, AttributeError, ScenarioError) as exc:
    st.error(f"Cannot trust the scenario baseline: {exc}")
    st.stop()

st.subheader("1 · Original operational baseline")
c1, c2, c3, c4 = st.columns(4)
original_metrics = original["solved"]["metrics"]
c1.metric("Cycle", f"{period['cycle_weeks']} weeks")
c2.metric("Allocated", f"{original_metrics['total_allocated_units']:,} units")
c3.metric("Unmet planning units", f"{original_metrics['total_unmet_units']:,}")
c4.metric("Worst partner fill", f"{100*original_metrics['worst_site_fill_rate']:.2f}%")
st.caption(
    f"Baseline cycle: {pd.Timestamp(period['cycle_start']).date()} – {pd.Timestamp(period['cycle_end']).date()} · "
    f"Fairness minimum: {settings['fairness_floor']:.0%} · "
    f"Worst-partner baseline protection: {'ON' if settings['protect_baseline_fill'] else 'OFF'} · "
    "Original allocations are not modified."
)

st.subheader("2 · Choose one change")
kind_labels = {
    "source_change": "Confirmed donation source ±50%",
    "pending_confirmed": "What if pending arrivals become confirmed?",
    "size_mix": "Demand size-mix shift",
    "new_partner": "Prospective new partner",
}
kind = st.selectbox("Scenario", list(kind_labels), format_func=lambda x: kind_labels[x])

# Streamlit forms batch widget values until the form is submitted.  A product
# selector inside this form would leave the dependent size dropdowns showing
# the PREVIOUS product's sizes (e.g. L/M/S/XL while 'diaper' is selected).
# Keep the product selection OUTSIDE the form so changing it triggers a rerun
# before the size controls are built.
size_mix_product = None
if kind == "size_mix":
    size_mix_products = sorted(forecasts["product"].astype(str).unique().tolist())
    size_mix_product = st.selectbox(
        "Product family", size_mix_products, key="g5_size_mix_product",
    )

params = {}
with st.form("gate5_scenario_controls", clear_on_submit=False):
    if kind == "source_change":
        if inbound is None:
            st.warning("No incoming supply file is present. This scenario needs eligible confirmed arrivals.")
            candidates = []
        else:
            dates = pd.to_datetime(inbound["expected_date"], errors="coerce")
            active = inbound.loc[
                inbound["status"].eq("confirmed") & inbound["size"].ne("unknown")
                & dates.gt(pd.Timestamp(period["inventory_as_of"]))
                & dates.le(pd.Timestamp(period["cycle_end"]))
            ]
            candidates = sorted(active["source"].dropna().astype(str).unique().tolist())
        params["sources"] = st.multiselect("Select confirmed donation sources to change", candidates)
        params["change_pct"] = st.slider("Donation volume change (%)", -50, 50, -20, step=5)
        verified = st.checkbox("I verified these source names refer to donations, not purchased stock", value=False)
    elif kind == "pending_confirmed":
        st.info("Assume all eligible pending, known-size arrivals are confirmed at their recorded dates. Late and unknown-size shipments remain excluded. This is NOT a receiving event.")
    elif kind == "size_mix":
        params["product"] = size_mix_product
        variants = sorted(forecasts.loc[forecasts["product"].eq(size_mix_product), "size"].astype(str).unique().tolist())
        params["from_size"] = st.selectbox("Move demand FROM size", variants)
        params["to_size"] = st.selectbox("Move demand TO size", variants, index=min(1, len(variants)-1))
        params["shift_pct"] = st.slider("Transfer percentage of source-size forecast", 5, 50, 20, step=5)
        st.caption("Conserves forecast units within each affected site/week. This is an assumed mix shift, not a new historical model fit.")
    else:
        candidates = master.loc[
            master.get("has_distribution_history", pd.Series(True, index=master.index)).eq(False)
            & ~master["site_id"].astype(str).isin(forecasts["site_id"].astype(str))
        ]
        options = ["__hypothetical__"] + candidates["site_id"].astype(str).tolist()
        selected = st.selectbox("Survey-only partner or hypothetical profile", options,
                                format_func=lambda s: "New hypothetical survey profile" if s == "__hypothetical__" else f"{master.loc[master.site_id.astype(str).eq(s), 'site_name'].iloc[0]} ({s})")
        if selected == "__hypothetical__":
            params["name"] = st.text_input("Hypothetical partner name", "Scenario Partner")
            params["families"] = st.number_input("Families served per month (assumed)", min_value=1, value=100, step=1)
            params["agency_type"] = st.selectbox("Agency type", ["shelter", "wic_clinic", "school", "pantry", "health_center", "faith_community", "other"])
        else:
            params["site_id"] = selected
        params["acknowledged"] = st.checkbox(
            "I understand this uses current peer forecasts and prospective survey assumptions; it is NOT a backtested new-partner forecast.", value=False
        )
    submitted = st.form_submit_button("Run what-if scenario", type="primary", width="stretch")

if submitted:
    if kind == "source_change" and not verified:
        st.error("Please verify selected donation sources before applying the scenario.")
        st.stop()
    try:
        with st.spinner("Creating counterfactual inputs and re-solving allocation..."):
            result = run_counterfactual(
                forecasts, inventory, inbound, master, original,
                kind=kind, params=params,
            )
        if not _has_current_demand_audit(result):
            raise ScenarioError(
                "Scenario engine returned an older result schema without demand reconciliation. "
                "Stop Streamlit (Ctrl+C), restart the app, and run this scenario again. "
                "Do not interpret this result as validated."
            )
        st.session_state["g5_scenario_result"] = {
            "baseline_id": id(original), "source_signature": signature,
            "kind": kind, "size_mix_product": size_mix_product,
            "submitted_params": dict(params), "result": result,
        }
    except (ScenarioError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        st.session_state.pop("g5_scenario_result", None)
        st.error(f"Could not create a safe scenario: {exc}")
        st.stop()

saved = st.session_state.get("g5_scenario_result")
if (saved is None or saved.get("baseline_id") != id(original)
        or saved.get("source_signature") != signature or saved.get("kind") != kind
        or (kind == "size_mix" and saved.get("size_mix_product") != size_mix_product)):
    st.info("Choose assumptions and click **Run what-if scenario**. The existing baseline is unchanged.")
    st.stop()

result = saved["result"]
if not _has_current_demand_audit(result):
    # Invalidate in-memory results produced before demand_audit was introduced.
    # Clear *only* the stale scenario; preserve Upload, Forecast and Allocate.
    st.session_state.pop("g5_scenario_result", None)
    st.warning(
        "This scenario result was produced by an older code version and has no demand "
        "reconciliation. It has been cleared. Click Run what-if scenario to recalculate "
        "under the current engine. If this warning recurs, fully restart Streamlit first."
    )
    st.stop()
st.subheader("3 · Compare outcomes")
st.caption("Results reflect the last completed Run action. Changing a control without running again does not update the scenario.")
elapsed = result["elapsed_seconds"]
if elapsed >= 15:
    st.warning(f"Scenario recomputation took {elapsed:.2f}s, at or above the Gate 5 <15s target. This run is NOT a performance pass.")
else:
    st.caption(f"Scenario calculation including input transformation, certified allocation solve and WOS comparison: **{elapsed:.2f}s** (<15s target on this run).")
st.caption(
    "Original operational plan = saved Allocate result. Scenario-optimized plan = re-solved after assumptions. "
    "Scenario proportional comparator = proportional allocation under the scenario's new constraints, "
    "not the original operational plan."
)
comparison = result["comparison"].copy()
comparison.loc[comparison["metric"].eq("worst_site_fill_rate"), ["original_plan", "scenario_optimized", "change_from_original", "scenario_proportional"]] *= 100
comparison.loc[comparison["metric"].eq("worst_site_fill_rate"), "metric"] = "worst_site_fill_rate_pct"
st.dataframe(comparison, width="stretch", hide_index=True)
if kind == "new_partner":
    st.warning("The network now has an additional hypothetical partner. Total need and the worst-fill denominator can change; raw deltas are not apples-to-apples impact estimates.")
st.markdown("#### Scenario assumptions actually applied")
# Render the settings that were ACTUALLY submitted, not current unsubmitted
# form widgets. Preserve original assumption keys unchanged for audit.
used = saved.get("submitted_params", {})
applied = result["assumptions"]
if kind == "source_change":
    details = [
        ("Change type", "Confirmed incoming donation volume"),
        ("Selected sources", ", ".join(applied["selected_sources"])),
        ("Volume adjustment", f"{used.get('change_pct', 0):+g}%"),
        ("Eligible incoming records", f"{applied['eligible_rows']:,}"),
        ("Change in cycle inbound", f"{applied['changed_inbound_units']:+,} units"),
    ]
elif kind == "pending_confirmed":
    details = [
        ("Change type", "Assume eligible pending deliveries become confirmed"),
        ("Pending arrivals included", f"{applied['assumed_confirmed_rows']:,}"),
        ("Assumed additional cycle inbound", f"+{applied['assumed_inbound_units']:,} units"),
        ("Availability", "Future inbound in this scenario; NOT received stock"),
    ]
elif kind == "size_mix":
    details = [
        ("Change type", "Prospective demand size-mix shift"),
        ("Product family", str(used.get("product", ""))),
        ("Size movement", f"{used.get('from_size', '')} → {used.get('to_size', '')}"),
        ("Source-size demand transferred", f"{used.get('shift_pct', 0):g}%"),
        ("Expected units transferred", f"{applied['transferred_expected_units']:,.2f}"),
        ("Affected site-weeks", f"{applied['affected_site_weeks']:,}"),
    ]
else:
    details = [
        ("Change type", "Prospective new partner (not backtested)"),
        ("Partner", applied["new_partner_name"]),
        ("Peer method", applied["peer_method"].replace("_", " ")),
        ("Number of peer sites", f"{applied['peer_sites']:,}"),
        ("Assumed expected cycle need", f"{applied['assumed_cycle_need_units']:,.2f} units"),
        ("Forecast status", "Provisional; requires review"),
    ]
st.dataframe(pd.DataFrame(details, columns=["Assumption", "Applied value"]),
             width="stretch", hide_index=True)
if kind == "size_mix":
    audit = result["demand_audit"]
    st.caption(
        f"Fractional forecast total conserved (Δ {audit['expected_delta_units']:+.6f} expected units). "
        f"After Week 4 product-size integer rounding, planning needs changed by "
        f"{audit['integer_need_delta_units']:+,} unit(s). "
        "This is an integer rounding adjustment, NOT newly forecast demand. "
        "The actual rounded needs, allocations and unmet units are reported without alteration."
    )
elif kind == "new_partner":
    audit = result["demand_audit"]
    st.caption(
        f"The added partner increases fractional forecast need by {audit['expected_delta_units']:,.2f} units "
        f"and rounded operational planning need by {audit['integer_need_delta_units']:,} units. "
        "The original network and scenario have different partner counts."
    )
with st.expander("Technical assumptions / audit JSON", expanded=False):
    st.json(applied)
    st.json({"demand_reconciliation": result["demand_audit"]})
st.markdown("#### Changes in projected weeks of supply")
st.dataframe(result["coverage"], width="stretch", hide_index=True)
st.caption("Coverage uses eligible confirmed cycle supply, not immediately pickable stock. Zero/missing forecasts may produce N/A WOS.")
if not result["solved"]["warnings"].empty:
    with st.expander("Scenario input and forecast warnings", expanded=False):
        st.dataframe(result["solved"]["warnings"], width="stretch", hide_index=True)
st.markdown("#### Scenario-optimized allocations (planning only)")
st.caption(
    "On-hand-backed planning units only indicate how much of the hypothetical allocation is supported "
    "by the dated counted-stock snapshot, NOT units reserved, received, approved for picking, or shipped. "
    "Future-inbound-backed planning units remain unavailable until actual verified receipt."
)
# Rename presentation columns only. Keep Gate 4 solver/output contracts intact.
scenario_allocation = result["solved"]["allocation"].rename(columns={
    "ready_now_units": "on_hand_backed_planning_units",
    "awaiting_inbound_units": "future_inbound_backed_planning_units",
}).copy()
st.dataframe(scenario_allocation, width="stretch", hide_index=True)
st.download_button("Download scenario comparison (CSV)", csv_download(result["comparison"]),
                   file_name="scenario_comparison.csv", mime="text/csv")
export_allocation = scenario_allocation.assign(plan_status="HYPOTHETICAL_NOT_PICK_AUTHORIZATION")
st.download_button("Download hypothetical allocation (CSV)", csv_download(export_allocation),
                   file_name="scenario_hypothetical_allocation_NOT_PICKLIST.csv", mime="text/csv")
st.warning("Scenario allocations are NOT approved shipping commitments. Hypothetical donations, pending arrivals, and scenario changes must not be treated as physical ready-to-pick stock.")
