"""Gate 6B - one-page public funder planning report. No implicit model reruns."""

import pandas as pd
import streamlit as st

from src.allocation_ui import input_signature
from src.forecast_ui import data_signature
from src.report import ReportError, build_report_data
from src.report_pdf import render_funder_pdf

st.set_page_config(page_title="Funder Report | Supply Bank Allocator", page_icon="📄", layout="wide")
st.title("Funder Report")
st.caption(
    "Generate a one-page eight-week planning report. Historical distribution, modeled allocations, "
    "provisional shortfall, and proposed funding requests are explicitly distinguished."
)


def _guide(message: str, destination: str, label: str):
    st.warning(message)
    st.page_link(destination, label=label)
    st.stop()


derived = st.session_state.get("derived_outputs")
cleaned = st.session_state.get("cleaned_results", {})
forecast_state = st.session_state.get("cp6_forecast_result")
saved_plan = st.session_state.get("g4_allocation_result")
if derived is None or "distribution_log" not in cleaned or "current_inventory" not in cleaned:
    _guide("Upload and validate distribution and current inventory data first.", "pages/1_Upload.py", "Go to Upload")
if not isinstance(forecast_state, dict):
    _guide("Generate an 8-week forecast before creating the funder report.", "pages/2_Forecast.py", "Go to Forecast")
if forecast_state.get("horizon") != 8:
    _guide("The saved forecast is not 8 weeks. Open Forecast, select 8 weeks, and click Generate forecast.",
           "pages/2_Forecast.py", "Generate an 8-week forecast")
if not isinstance(saved_plan, dict) or saved_plan.get("settings", {}).get("cycle_weeks") != 8:
    _guide("The report requires an existing 8-week allocation. Open Allocate, select an 8-week planning cycle, and optimize.",
           "pages/3_Allocate.py", "Generate an 8-week allocation")

try:
    forecast_signature = data_signature(derived.weekly_distribution, derived.site_master)
    if forecast_state.get("signature") != forecast_signature:
        raise ReportError("Forecast no longer matches the current upload and partner master.")
    fc = forecast_state["forecasts"]
    inventory = cleaned["current_inventory"].cleaning_result.dataframe
    arriving = cleaned.get("incoming_supply")
    incoming = arriving.cleaning_result.dataframe if arriving is not None else None
    current_signature = input_signature(fc, inventory, incoming, derived.site_master)
    raw_distribution = cleaned["distribution_log"].cleaning_result.dataframe
    preliminary = build_report_data(
        raw_distribution, derived.site_master, saved_plan,
        expected_signature=current_signature, prices=None,
    )
except (ReportError, ValueError, TypeError, KeyError, AttributeError) as exc:
    st.error(f"Report data needs review: {exc}")
    st.info("Review Upload, then generate a new eight-week Forecast and Allocate plan. No report was generated.")
    st.stop()

period = preliminary["periods"]
st.info(
    f"Observed distribution: **{period['historical_start']:%b %d, %Y} - {period['historical_end']:%b %d, %Y}**. "
    f"Modeled planning: **{period['forecast_start']:%b %d, %Y} - {period['forecast_end']:%b %d, %Y}**. "
    "The report is based on the saved original allocation, not hypothetical Scenarios or purchases."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Observed units distributed", f"{preliminary['observed']['units_distributed']:,}")
c2.metric("Observed partners", f"{preliminary['observed']['partners_with_distributions']:,}")
c3.metric("Modeled unmet units", f"{preliminary['planning']['modeled_unmet_units']:,}")
c4.metric("Potential SKU supply gap", f"{preliminary['planning']['supply_gap_units']:,}")

with st.expander("What these numbers mean", expanded=True):
    st.write(
        "**Observed distributions** are logged historical units, not all community demand. "
        "**Modeled unmet units** are forecast-based allocation shortfalls, not independently measured unmet need. "
        "**SKU supply gaps** compare the eight-week forecast with on-hand plus eligible confirmed inbound, "
        "and can differ from modeled unmet when operational constraints apply. "
        "**High-need partner share** refers to modeled allocations, not deliveries already made. "
        "Survey family counts are estimates, not verified unique families served."
    )

st.subheader("Potential funding request")
base = preliminary["ask_by_sku"].copy()
if base.empty:
    st.success("This model currently shows no positive eight-week product-size supply gap. A zero-unit ask will appear in the PDF.")
else:
    st.caption(
        "Enter a USD price **per individual unit** only when you have a stated assumption or an actual quote. "
        "Leave unknown prices blank. A total dollar ask is unavailable until every positive-gap SKU is priced. "
        "The complete table is downloadable even when the one-page PDF groups smaller gaps."
    )

with st.form("g6_report_form"):
    bank_name = st.text_input("Bank name (optional; defaults to Supply Bank)", value="Supply Bank", max_chars=120)
    logo_file = st.file_uploader("Optional logo (PNG/JPEG, up to 2 MB)", type=["png", "jpg", "jpeg"])
    if not base.empty:
        editable = base[["product", "size", "supply_gap_units"]].copy()
        editable["unit_cost_usd"] = pd.Series([float("nan")] * len(editable), dtype="float64")
        editable["price_basis"] = "scenario_assumption"
        edited = st.data_editor(
            editable, hide_index=True, num_rows="fixed", width="stretch",
            disabled=["product", "size", "supply_gap_units"],
            column_config={
                "product": st.column_config.TextColumn("Product"),
                "size": st.column_config.TextColumn("Size"),
                "supply_gap_units": st.column_config.NumberColumn("Potential missing units", format="%d"),
                "unit_cost_usd": st.column_config.NumberColumn(
                    "USD / individual unit", min_value=0.01, step=0.01, format="$%.2f", required=False,
                ),
                "price_basis": st.column_config.SelectboxColumn(
                    "Price evidence", options=["scenario_assumption", "verified_quote"], required=True,
                ),
            },
        )
    else:
        edited = None
    create = st.form_submit_button("Generate one-page PDF", type="primary", width="stretch")

if create:
    try:
        prices = None
        if edited is not None:
            given = edited.loc[edited["unit_cost_usd"].notna(),
                               ["product", "size", "unit_cost_usd", "price_basis"]].copy()
            if not given.empty:
                prices = given
        report = build_report_data(
            raw_distribution, derived.site_master, saved_plan,
            expected_signature=current_signature, prices=prices,
        )
        logo_bytes = logo_file.getvalue() if logo_file is not None else None
        payload = render_funder_pdf(report, bank_name=bank_name.strip() or "Supply Bank", logo=logo_bytes)
        detail = report["ask_by_sku"].to_csv(index=False, na_rep="Not priced").encode("utf-8-sig")
        st.session_state["g6_report_pdf"] = {
            "signature": current_signature,
            "plan_object_id": id(saved_plan),
            "pdf": payload,
            "full_ask_csv": detail,
            "warnings": report["warnings"],
            "pricing": report["pricing"],
        }
    except (ReportError, ValueError, TypeError, KeyError, RuntimeError, OSError) as exc:
        st.session_state.pop("g6_report_pdf", None)
        st.error(f"Unable to create a reliable PDF report: {exc}")
        st.stop()

output = st.session_state.get("g6_report_pdf")
if output and (output.get("signature") != current_signature or output.get("plan_object_id") != id(saved_plan)):
    st.session_state.pop("g6_report_pdf", None)
    output = None
if output:
    st.caption("The files below reflect the LAST successful Generate action. Unsubmitted edits do not change them.")
    st.success("Your one-page, eight-week report is ready.")
    p = output["pricing"]
    if p["fully_costed_ask_usd"] is None:
        st.warning("Some product-size prices are missing: total funding dollars are intentionally unavailable.")
    elif not p["all_prices_verified_quotes"] and p["sku_gaps"]:
        st.warning("Report pricing includes scenario assumptions; do not label these figures as supplier quotes.")
    d1, d2 = st.columns(2)
    d1.download_button("Download one-page PDF", data=output["pdf"], file_name="supply_bank_funder_report_8_weeks.pdf", mime="application/pdf", width="stretch")
    d2.download_button("Download full SKU funding ask (CSV)", data=output["full_ask_csv"], file_name="supply_bank_full_8_week_ask.csv", mime="text/csv", width="stretch")
    with st.expander("Quality and provenance cautions"):
        if output["warnings"]:
            for item in output["warnings"]:
                st.write("- " + str(item))
        else:
            st.write("No additional data-quality warnings were returned.")
