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