"""Gate 6C partner intake: canonical Streamlit form + Google Forms CSV."""

import pandas as pd
import streamlit as st

from src.survey_session import (
    INVALIDATE_AFTER_SURVEY_CHANGE, SURVEY_COLUMNS, SurveyIntakeError,
    canonical_survey_csv, prepare_survey_change, read_google_form_csv,
    suggest_google_form_mapping, survey_record,
)

st.set_page_config(page_title="Partner Survey | Supply Bank Allocator", page_icon="📝", layout="wide")
st.title("Partner Intake Survey")
st.caption(
    "Add or update partner-level information for cold-start planning and equity weighting. "
    "Survey answers are organizational estimates, not verified household service counts."
)
st.info("Please do not enter individual client records, names, addresses, health details, or immigration information.")

cleaned = st.session_state.get("cleaned_results", {})
if "distribution_log" not in cleaned or st.session_state.get("derived_outputs") is None:
    st.warning("First load Demo Mode or a Distribution Log, then click Clean & Validate on Upload.")
    st.page_link("pages/1_Upload.py", label="Go to Upload", icon="📤")
    st.stop()


def apply_change(frame: pd.DataFrame, mapping: dict, mode: str) -> None:
    """One transaction: compute first, then publish a fully reconciled state."""
    staged = prepare_survey_change(st.session_state["cleaned_results"], frame, mapping, mode=mode)
    st.session_state["cleaned_results"] = staged["cleaned_results"]
    st.session_state["derived_outputs"] = staged["derived_outputs"]
    errors = dict(st.session_state.get("processing_errors", {}))
    errors.pop("partner_survey", None)
    st.session_state["processing_errors"] = errors
    st.session_state["derived_error"] = None
    for key in INVALIDATE_AFTER_SURVEY_CHANGE:
        st.session_state.pop(key, None)
    st.success(
        f"Survey saved: {staged['incoming_rows']} new/updated record(s), "
        f"{staged['survey_rows']} partner survey(s) in this session. "
        "Regenerate Forecast and Allocate before using their results or the Funder Report."
    )
    st.page_link("pages/2_Forecast.py", label="Go to Forecast", icon="📈")

existing = cleaned.get("partner_survey")
if existing is not None:
    current_survey = existing.cleaning_result.dataframe
    st.caption(f"Current validated partner survey records: {len(current_survey):,} (current session only).")
    with st.expander("Review current partner survey", expanded=False):
        st.dataframe(current_survey[[c for c in SURVEY_COLUMNS if c in current_survey]],
                     hide_index=True, width="stretch")
    st.download_button(
        "Download current partner survey (CSV)",
        data=canonical_survey_csv(cleaned),
        file_name="partner_survey_session.csv", mime="text/csv",
    )
else:
    st.caption("No partner survey has been provided yet. Equal equity weights apply until survey data is supplied.")

st.warning(
    "Survey edits are session-only. Re-running Clean & Validate on Upload will use that page's "
    "selected file(s) and may replace these edits. Export the CSV if you need to reuse them."
)

form_tab, csv_tab = st.tabs(["Complete a partner survey", "Import Google Forms CSV"])

AGENCIES = {
    "shelter": "Shelter", "wic_clinic": "WIC clinic", "school": "School",
    "pantry": "Food pantry", "health_center": "Health center",
    "faith_community": "Faith community", "other": "Other",
}
POVERTY = {
    "under_25_percent": "Under 25%", "25_to_50_percent": "25%–50%",
    "50_to_75_percent": "50%–75%", "over_75_percent": "Over 75%",
}
FLAGS = {
    "emergency_shelter": "Emergency shelter",
    "domestic_violence_program": "Domestic violence program",
    "teen_parents": "Teen parents",
    "refugee_or_newly_arrived_families": "Refugee/newly arrived families",
    "students": "Students",
    "families_with_child_with_disability": "Families with a child with a disability",
}
STOCKOUTS = ([f"diaper:{x}" for x in ("N", "1", "2", "3", "4", "5", "6", "7")]
             + [f"pull_up:{x}" for x in ("2T-3T", "3T-4T", "4T-5T")]
             + [f"adult_incontinence:{x}" for x in ("S", "M", "L", "XL")]
             + [f"period_pad:{x}" for x in ("regular", "super", "overnight")]
             + [f"period_tampon:{x}" for x in ("regular", "super", "super_plus")]
             + ["period_liner:one_size", "period_cup:one_size"])

with form_tab:
    st.caption("A matching partner name updates the existing survey record. All answers for that partner are replaced.")
    with st.form("partner_intake_form", clear_on_submit=False):
        st.markdown("#### 1 · Partner information")
        site_name = st.text_input("Partner agency name *", max_chars=150)
        zip_code = st.text_input("ZIP code * (keep leading zeros)", max_chars=20)
        agency = st.selectbox("Type of agency *", list(AGENCIES), format_func=AGENCIES.get)

        st.markdown("#### 2 · Monthly service population")
        families = st.number_input("Approximate families served per month *", min_value=0, value=0, step=1)
        children = st.number_input("Children under 4 per month (optional)", min_value=0, value=None, step=1)
        menstruating = st.number_input("Menstruating clients per month (optional)", min_value=0, value=None, step=1)

        st.markdown("#### 3 · Community need")
        poverty = st.selectbox("Estimated share below poverty line (optional)",
                               list(POVERTY), index=None, placeholder="Not provided", format_func=POVERTY.get)
        flags = st.multiselect("Priority populations served (optional)",
                               list(FLAGS), format_func=FLAGS.get)

        st.markdown("#### 4 · Operations and supply")
        storage = st.number_input("Storage capacity, cases (optional)", min_value=0, value=None, step=1,
                                  help="Cases are not automatically converted into individual-unit allocation caps.")
        frequency = st.selectbox("Distribution frequency (optional)",
                                 ["weekly", "biweekly", "monthly"], index=None,
                                 placeholder="Not provided")
        stockouts = st.multiselect("Product sizes out of stock in the last 90 days (optional)", STOCKOUTS)

        st.markdown("#### 5 · Contact and communication")
        contact = st.text_input("Preferred organization contact (optional)", max_chars=160)
        languages = st.text_input("Languages commonly spoken (optional; separate with semicolons)", max_chars=200)
        submitted_form = st.form_submit_button("Save Partner Survey", type="primary")

    if submitted_form:
        if not site_name.strip() or not zip_code.strip():
            st.error("Enter a partner agency name and ZIP code before saving.")
        else:
            form_row = survey_record(
                site_name=site_name.strip(), zip_code=zip_code.strip(), agency_type=agency,
                families_served_per_month=int(families), children_under_4_per_month=children,
                menstruating_clients_per_month=menstruating, poverty_share_band=poverty,
                priority_population_flags=flags, storage_capacity_cases=storage,
                distribution_frequency=frequency, recent_stockout_sizes=stockouts,
                preferred_contact=contact or None, languages_spoken=languages or None,
            )
            try:
                apply_change(form_row, {c: c for c in form_row.columns}, "upsert")
            except SurveyIntakeError as exc:
                st.error(f"Survey could not be saved: {exc}")

with csv_tab:
    st.caption(
        "Upload a CSV exported from Google Forms. Question headings are matched to canonical fields; "
        "review every mapping before importing. Google timestamps and unrelated columns can remain unmapped."
    )
    uploaded = st.file_uploader("Google Forms CSV", type=["csv"], key="g6_google_form_csv")
    if uploaded is not None:
        try:
            raw = read_google_form_csv(uploaded)
        except SurveyIntakeError as exc:
            st.error(str(exc))
        else:
            st.caption(f"Read {len(raw):,} survey response rows and {len(raw.columns)} columns.")
            with st.expander("Preview raw Google Form responses", expanded=False):
                st.dataframe(raw.head(10), hide_index=True, width="stretch")
            suggestions = suggest_google_form_mapping(raw.columns)
            options = ["— Unmapped —", *SURVEY_COLUMNS]
            with st.form("g6_google_survey_mapping"):
                mappings = {}
                for i, header in enumerate(raw.columns):
                    recommended = suggestions.get(header)
                    selection = st.selectbox(
                        f"Column: {header}", options,
                        index=options.index(recommended) if recommended else 0,
                        key=f"g6_google_map_{i}_{header}",
                    )
                    mappings[header] = None if selection == "— Unmapped —" else selection
                mode = st.radio(
                    "Import behavior", ["upsert", "replace"], horizontal=True,
                    format_func=lambda x: "Update matching partners, keep others" if x == "upsert"
                    else "Replace all current survey records",
                )
                submitted_csv = st.form_submit_button("Validate & Import Google Forms CSV", type="primary")
            if submitted_csv:
                try:
                    apply_change(raw, mappings, mode)
                except SurveyIntakeError as exc:
                    st.error(f"Import could not be completed; existing survey is unchanged. Details: {exc}")
