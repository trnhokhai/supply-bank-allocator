"""Gate 6C: survey intake adapters for the existing Week 2 data contract.

This module does NOT create an alternate data-cleaning or site-identity system.
It produces a complete, validated replacement snapshot for Streamlit to apply
atomically after the user presses Save/Import.
"""

from __future__ import annotations

import re

import pandas as pd

from src.ingest import (CANONICAL_COLUMNS, apply_header_mapping,
                        normalize_site_name, suggest_header_mapping)
from src.workflow import build_derived_outputs, prepare_input


class SurveyIntakeError(ValueError):
    """Survey input cannot safely be added to the active planning session."""


SURVEY_COLUMNS = tuple(CANONICAL_COLUMNS["partner_survey"])
INVALIDATE_AFTER_SURVEY_CHANGE = (
    "cp6_forecast_result",
    "cp7_accuracy_result",
    "g4_allocation_result",
    "g5_alert_result",
    "g5_scenario_result",
    "g5_purchase_result",
    "g6_report_pdf",
)


# Use literal wording already documented in partner_survey_spec.md. No guessing
# when a Google Form changes the question text; users can review mapping in UI.
GOOGLE_FORM_QUESTIONS = {
    "partner agency name": "site_name",
    "zip code": "zip_code",
    "type of agency": "agency_type",
    "approximately how many families does your organization serve per month": "families_served_per_month",
    "approximately how many children under age 4 does your organization serve per month": "children_under_4_per_month",
    "approximately how many menstruating clients does your organization serve per month": "menstruating_clients_per_month",
    "approximately what share of your clients are below the federal poverty line": "poverty_share_band",
    "which priority populations does your organization serve": "priority_population_flags",
    "approximately how much storage capacity is available for these supplies": "storage_capacity_cases",
    "how often does your organization typically distribute supplies": "distribution_frequency",
    "which product sizes has your organization run out of during the last 90 days": "recent_stockout_sizes",
    "preferred contact": "preferred_contact",
    "what languages are commonly spoken by the clients your organization serves": "languages_spoken",
}


def _question_token(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).split())


def suggest_google_form_mapping(headers) -> dict:
    """Non-ambiguous suggestions; a human still confirms each Google column."""
    raw_headers = list(headers)
    mapping = suggest_header_mapping(raw_headers, "partner_survey")
    used = {v for v in mapping.values() if v is not None}
    for header in raw_headers:
        if mapping.get(header) is not None:
            continue
        candidate = GOOGLE_FORM_QUESTIONS.get(_question_token(header))
        if candidate is not None and candidate not in used:
            mapping[header] = candidate
            used.add(candidate)
    return mapping


def read_google_form_csv(source) -> pd.DataFrame:
    """Read Google CSV as strings, preserving ZIP codes such as '02108'."""
    if source is None:
        raise SurveyIntakeError("Choose a Google Forms CSV export first.")
    try:
        if hasattr(source, "seek"):
            source.seek(0)
        frame = pd.read_csv(source, dtype=str, keep_default_na=False,
                            encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, pd.errors.ParserError,
            UnicodeError, OSError, ValueError, TypeError) as exc:
        raise SurveyIntakeError("The survey CSV could not be read. Export it from Google Forms and try again.") from exc
    if frame.empty or not len(frame.columns):
        raise SurveyIntakeError("The survey CSV has no response rows.")
    return frame


POVERTY_LABELS = {
    "under 25": "under_25_percent",
    "under 25 percent": "under_25_percent",
    "25 to 50": "25_to_50_percent",
    "25 to 50 percent": "25_to_50_percent",
    "50 to 75": "50_to_75_percent",
    "50 to 75 percent": "50_to_75_percent",
    "over 75": "over_75_percent",
    "over 75 percent": "over_75_percent",
}
AGENCY_LABELS = {"food pantry": "pantry"}
FLAG_LABELS = {
    "emergency shelter": "emergency_shelter",
    "domestic violence program": "domestic_violence_program",
    "teen parents": "teen_parents",
    "refugee or newly arrived families": "refugee_or_newly_arrived_families",
    "students": "students",
    "families with a child with a disability": "families_with_child_with_disability",
}


def normalize_survey_display_values(mapped: pd.DataFrame) -> pd.DataFrame:
    """Interpret documented Google Forms display labels before canonical cleaning.

    Unknown values remain unchanged and fail existing validation rather than
    being silently guessed. Form checkbox answers use comma-separated lists.
    """
    result = mapped.copy()
    optional = set(SURVEY_COLUMNS) - {
        "site_name", "zip_code", "agency_type", "families_served_per_month"
    }
    for field in optional.intersection(result.columns):
        result[field] = result[field].map(
            lambda v: None if v is None or (isinstance(v, str) and not v.strip()) else v
        )
    if "poverty_share_band" in result:
        result["poverty_share_band"] = result["poverty_share_band"].map(
            lambda v: POVERTY_LABELS.get(_question_token(v), v) if pd.notna(v) else v
        )
    if "agency_type" in result:
        result["agency_type"] = result["agency_type"].map(
            lambda v: AGENCY_LABELS.get(_question_token(v), v) if pd.notna(v) else v
        )
    if "priority_population_flags" in result:
        def normalize_flags(v):
            if pd.isna(v):
                return v
            names = [p.strip() for p in re.split(r"[;,]", str(v)) if p.strip()]
            return ";".join(FLAG_LABELS.get(_question_token(p), p) for p in names)
        result["priority_population_flags"] = result["priority_population_flags"].map(normalize_flags)
    if "recent_stockout_sizes" in result:
        result["recent_stockout_sizes"] = result["recent_stockout_sizes"].map(
            lambda v: ";".join(x.strip() for x in re.split(r"[;,]", str(v)) if x.strip())
            if pd.notna(v) else v
        )
    return result


def survey_record(**values) -> pd.DataFrame:
    """A single canonical form record. Optional blanks remain unasserted."""
    data = {column: values.get(column, None) for column in SURVEY_COLUMNS}
    for name in ("priority_population_flags", "recent_stockout_sizes"):
        value = data[name]
        if isinstance(value, (list, tuple, set)):
            data[name] = ";".join(str(v) for v in value)
    return pd.DataFrame([data], columns=SURVEY_COLUMNS)


def _only_contract_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep canonical fields and preserve nullable object-typed survey columns.

    Concatenating an imported Google Form with existing survey records can
    infer float64 for optional, entirely empty text/list columns. Pandera's
    existing partner-survey contract requires object dtype for those fields;
    missing values stay missing (None), not the string "nan" or an empty list.
    """
    result = frame[[c for c in SURVEY_COLUMNS if c in frame.columns]].copy()
    for column in (
        "priority_population_flags",
        "recent_stockout_sizes",
        "preferred_contact",
        "languages_spoken",
    ):
        if column in result.columns:
            values = result[column].astype(object)
            result[column] = values.where(values.notna(), None)
    return result


def _names(frame: pd.DataFrame) -> pd.Series:
    if "site_name" not in frame.columns:
        raise SurveyIntakeError("Survey is missing a partner agency name.")
    return frame["site_name"].map(lambda x: normalize_site_name(x).casefold())


def prepare_survey_change(cleaned_results: dict, raw_survey: pd.DataFrame,
                          mapping: dict, *, mode: str = "upsert") -> dict:
    """Validate and stage new cleaned_results + derived_outputs without mutation.

    upsert: update partners matching normalized names, retain others.
    replace: replace the complete survey collection (explicit import choice).
    The existing distribution is required for site identity reconciliation.
    """
    if mode not in {"upsert", "replace"}:
        raise SurveyIntakeError("Survey mode must be upsert or replace.")
    if not isinstance(cleaned_results, dict) or "distribution_log" not in cleaned_results:
        raise SurveyIntakeError("Clean and validate a Distribution Log on Upload before saving survey data.")
    if not isinstance(raw_survey, pd.DataFrame) or raw_survey.empty:
        raise SurveyIntakeError("Provide at least one survey record.")

    try:
        mapped = apply_header_mapping(raw_survey, mapping, "partner_survey")
        normalized = normalize_survey_display_values(mapped)
        canonical = _only_contract_columns(normalized)
        incoming_prepared = prepare_input(
            canonical, {c: c for c in canonical.columns}, "partner_survey"
        )
        incoming = _only_contract_columns(incoming_prepared.cleaning_result.dataframe)
        previous_input = cleaned_results.get("partner_survey")
        previous = (_only_contract_columns(previous_input.cleaning_result.dataframe)
                    if previous_input is not None else pd.DataFrame(columns=SURVEY_COLUMNS))
        if mode == "replace":
            candidate = incoming
        else:
            current_keys = _names(previous) if not previous.empty else pd.Series([], dtype=str)
            new_keys = set(_names(incoming))
            retained = previous.loc[~current_keys.isin(new_keys)].copy()
            candidate = pd.concat([retained, incoming], ignore_index=True)
        # Revalidate the FULL survey to catch conflicts across old/new records.
        # Never carry generated site_id into a new record; the existing site
        # master determines reconciliation with historical distribution IDs.
        candidate = _only_contract_columns(candidate)
        canonical_mapping = {c: c for c in candidate.columns}
        combined_prepared = prepare_input(candidate, canonical_mapping, "partner_survey")
        staged = dict(cleaned_results)
        staged["partner_survey"] = combined_prepared
        derived = build_derived_outputs(staged)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise SurveyIntakeError(str(exc)) from exc

    return {
        "cleaned_results": staged,
        "derived_outputs": derived,
        "survey_rows": int(len(combined_prepared.cleaning_result.dataframe)),
        "incoming_rows": int(len(incoming)),
        "mode": mode,
    }


def canonical_survey_csv(prepared: dict) -> bytes:
    """Export current survey only; neutralize spreadsheet-formula text."""
    try:
        table = _only_contract_columns(prepared["partner_survey"].cleaning_result.dataframe)
    except (TypeError, KeyError, AttributeError) as exc:
        raise SurveyIntakeError("No validated partner survey is available.") from exc
    for column in table.select_dtypes(include=["object", "string"]).columns:
        table[column] = table[column].map(
            lambda v: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v
        )
    return table.to_csv(index=False, na_rep="").encode("utf-8-sig")
