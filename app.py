"""Public landing page for the ChiEAC supply planning application.

Keep this page lightweight: no forecasting, optimisation or file processing on
page load. The existing Streamlit pages own their analytical workflows.
"""

from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="Supply Bank Allocator | ChiEAC",
    page_icon="📦",
    layout="wide",
)

TEMPLATE_DIR = Path(__file__).resolve().parent / "src" / "templates"

st.title("Diaper & Period Supply Bank Allocator")
st.caption("Forecast distributions. See inventory risks. Allocate scarce supplies with equity in mind.")
st.markdown(
    "A free, open-source planning tool for diaper and period supply banks. "
    "Turn existing CSV or Excel records into reviewable forecasts, allocation plans, "
    "what-if scenarios, and an eight-week funder planning report."
)

st.info(
    "**Try it safely:** Open **Upload**, switch on **Demo Mode**, and click **Clean & Validate**. "
    "The demo uses synthetic data—not results from a real supply bank."
)

st.subheader("Start here")
a, b, c = st.columns(3, gap="medium")
with a:
    with st.container(border=True):
        st.markdown("### 1. Prepare data")
        st.write("Use Demo Mode, or bring distribution, on-hand inventory, and optional supply/survey files.")
        st.page_link("pages/1_Upload.py", label="Upload or try Demo Mode", icon="📤")
with b:
    with st.container(border=True):
        st.markdown("### 2. Plan supplies")
        st.write("Generate a four- to eight-week forecast, then review allocation and inventory risk.")
        st.page_link("pages/2_Forecast.py", label="Open Forecast", icon="📈")
with c:
    with st.container(border=True):
        st.markdown("### 3. Share a report")
        st.write("For a funder report, first generate an **8-week forecast AND 8-week allocation**.")
        st.page_link("pages/6_Report.py", label="Create an 8-week report", icon="📄")

st.subheader("What you can do")
left, right = st.columns(2, gap="large")
with left:
    st.markdown(
        "**Forecast** — estimate future distributions by partner, product and size. "
        "Historical fit, survey-based estimates and quality flags are kept distinct."
    )
    st.markdown(
        "**Allocate** — create equity-aware cycle plans, compare against a proportional "
        "baseline, and separate stock on hand from future confirmed arrivals."
    )
    st.page_link("pages/3_Allocate.py", label="Open Allocation", icon="📦")
with right:
    st.markdown(
        "**Alerts & Scenarios** — see weeks-of-supply and size mismatches; test changes "
        "to donations, demand mix, partners and hypothetical purchasing budgets."
    )
    st.markdown(
        "**Partner Survey** — add organisation-level information or import Google Forms "
        "CSV responses for cold-start and equity inputs."
    )
    st.page_link("pages/7_Survey.py", label="Open Partner Survey", icon="📝")

st.subheader("CSV starter templates")
st.caption(
    "Download the blank input templates. Upload provides column mapping, cleaning, and validation; "
    "optional data may improve planning but must never be invented."
)
for labels in (
    (("Distribution log", "distribution_log_template.csv"),
     ("Current inventory", "current_inventory_template.csv")),
    (("Incoming supply", "incoming_supply_template.csv"),
     ("Partner survey", "partner_survey_template.csv")),
):
    columns = st.columns(2)
    for column, (label, filename) in zip(columns, labels):
        path = TEMPLATE_DIR / filename
        with column:
            if path.is_file():
                st.download_button(
                    f"Download {label} CSV",
                    data=path.read_bytes(),
                    file_name=filename,
                    mime="text/csv",
                    width="stretch",
                )
            else:
                st.error(f"Missing template: {filename}. Please contact the project maintainer.")

st.subheader("Before using a planning result")
st.warning(
    "**Planning estimates are not measured community need.** Forecasts are based on recorded "
    "distributions or survey proxies. Allocation and purchasing scenarios are recommendations, "
    "not proof of deliveries, verified prices, or permission to place orders. "
    "Review flagged data and operational constraints before taking action."
)
st.markdown("**Privacy and use of uploaded files**")
st.caption(
    "Uploads are processed on the application server for your active session. "
    "This app does not intentionally write partner uploads to a permanent database. "
    "On public hosting, files are still transmitted to a third-party service. "
    "Do not upload individual client records, client names, personal addresses, medical details, "
    "immigration information or other sensitive data. Export any needed results before closing the session."
)
st.caption("Built by Khai Tran as part of the Chicago Education Advocacy Cooperative (ChiEAC) Fellowship.")
