from dataclasses import dataclass

import pandas as pd

from src.clean import (
    CleaningResult,
    clean_current_inventory,
    clean_distribution_log,
    clean_incoming_supply,
    clean_partner_survey,
)
from src.ingest import (
    apply_header_mapping,
)
from src.validate import (
    REQUIRED_COLUMNS,
)

from src.aggregate import (
    aggregate_distribution_to_iso_weeks,
    find_inactive_spans,
)

from src.site_master import (
    build_site_master,
)

class WorkflowError(ValueError):
    """Raised when an upload cannot enter the cleaning pipeline safely."""


@dataclass(frozen=True)
class PreparedInput:
    """
    Result of header mapping plus dataset-specific cleaning.
    """

    mapped_dataframe: pd.DataFrame
    cleaning_result: CleaningResult


CLEANERS = {
    "distribution_log": clean_distribution_log,
    "current_inventory": clean_current_inventory,
    "incoming_supply": clean_incoming_supply,
    "partner_survey": clean_partner_survey,
}


def prepare_input(
    dataframe,
    mapping,
    dataset_type,
):
    """
    Apply reviewed header mapping and run the appropriate
    cleaning/validation pipeline.
    """

    if dataset_type not in CLEANERS:
        raise WorkflowError(
            f"Unknown dataset type: {dataset_type!r}."
        )

    mapped = apply_header_mapping(
        dataframe,
        mapping,
        dataset_type=dataset_type,
    )

    missing_required = (
        REQUIRED_COLUMNS[dataset_type]
        - set(mapped.columns)
    )

    if missing_required:
        missing_text = ", ".join(
            sorted(missing_required)
        )

        raise WorkflowError(
            "Map all required columns before cleaning. "
            f"Still missing: {missing_text}."
        )

    cleaner = CLEANERS[
        dataset_type
    ]

    cleaning_result = cleaner(
        mapped
    )

    return PreparedInput(
        mapped_dataframe=mapped,
        cleaning_result=cleaning_result,
    )

@dataclass(frozen=True)
class DerivedOutputs:
    """
    Trusted analytical-preparation tables created only
    after uploaded inputs have been cleaned and validated.
    """

    weekly_distribution: pd.DataFrame
    inactive_spans: pd.DataFrame
    site_master: pd.DataFrame


def build_derived_outputs(
    prepared_inputs,
):
    """
    Build Week 2 derived tables from cleaned inputs.

    Distribution history is required.

    Partner survey is optional. When present, it enriches
    the site master. When absent, the site master is still
    created from distribution history.
    """

    if (
        "distribution_log"
        not in prepared_inputs
    ):
        raise WorkflowError(
            "A cleaned Distribution Log is required "
            "to build derived planning tables."
        )

    distribution = (
        prepared_inputs[
            "distribution_log"
        ]
        .cleaning_result
        .dataframe
    )

    survey = None

    if (
        "partner_survey"
        in prepared_inputs
    ):
        survey = (
            prepared_inputs[
                "partner_survey"
            ]
            .cleaning_result
            .dataframe
        )

    weekly_distribution = (
        aggregate_distribution_to_iso_weeks(
            distribution
        )
    )

    inactive_spans = (
        find_inactive_spans(
            distribution
        )
    )

    site_master = build_site_master(
        distribution,
        survey_df=survey,
    )

    return DerivedOutputs(
        weekly_distribution=weekly_distribution,
        inactive_spans=inactive_spans,
        site_master=site_master,
    )