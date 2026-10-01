from dataclasses import dataclass

import pandas as pd
import pandera.pandas as pa
from pandera.errors import SchemaError, SchemaErrors

from src.ingest import (
    CANONICAL_PRODUCTS,
    CANONICAL_SIZES_BY_PRODUCT,
    normalize_site_name,
)


@dataclass(frozen=True)
class ValidationIssue:
    """
    Plain-language validation issue that can later be shown
    directly in the Streamlit data-quality experience.
    """

    severity: str
    code: str
    message: str
    count: int = 1


class TableValidationError(ValueError):
    """
    Raised when a canonical uploaded table contains
    blocking validation problems.
    """

    def __init__(
        self,
        message,
        failure_cases=None,
        issues=None,
    ):
        super().__init__(message)

        self.failure_cases = failure_cases

        self.issues = (
            list(issues)
            if issues is not None
            else []
        )


AGENCY_TYPES = {
    "shelter",
    "wic_clinic",
    "school",
    "pantry",
    "health_center",
    "faith_community",
    "other",
}


POVERTY_SHARE_BANDS = {
    "under_25_percent",
    "25_to_50_percent",
    "50_to_75_percent",
    "over_75_percent",
}


DISTRIBUTION_FREQUENCIES = {
    "weekly",
    "biweekly",
    "monthly",
}


INCOMING_STATUSES = {
    "confirmed",
    "pending",
}


REQUIRED_COLUMNS = {
    "distribution_log": {
        "date",
        "site_name",
        "product",
        "size",
        "quantity",
    },
    "current_inventory": {
        "as_of_date",
        "product",
        "size",
        "quantity_on_hand",
    },
    "incoming_supply": {
        "expected_date",
        "source",
        "product",
        "size",
        "quantity",
        "status",
    },
    "partner_survey": {
        "site_name",
        "zip_code",
        "agency_type",
        "families_served_per_month",
    },
}


def _nonblank(series):
    """
    Return True when every non-null value contains
    meaningful text after whitespace is removed.
    """

    return (
        series
        .dropna()
        .astype(str)
        .str.strip()
        .ne("")
        .all()
    )


def _whole_nonnegative(series):
    """
    Validate optional numeric values that may contain nulls.
    """

    values = pd.to_numeric(
        series.dropna(),
        errors="coerce",
    )

    if values.isna().any():
        return False

    return (
        values.ge(0)
        & values.mod(1).eq(0)
    ).all()


def _is_valid_product_size(
    product,
    size,
    allow_unknown=False,
):
    if (
        allow_unknown
        and str(size) == "unknown"
    ):
        return True

    if product not in CANONICAL_SIZES_BY_PRODUCT:
        return False

    return (
        str(size)
        in CANONICAL_SIZES_BY_PRODUCT[
            product
        ]
    )


def _valid_product_size_pairs(dataframe):
    return dataframe.apply(
        lambda row: _is_valid_product_size(
            row["product"],
            row["size"],
        ),
        axis=1,
    )


def _valid_incoming_product_size_pairs(
    dataframe,
):
    return dataframe.apply(
        lambda row: _is_valid_product_size(
            row["product"],
            row["size"],
            allow_unknown=True,
        ),
        axis=1,
    )


PRODUCT_SIZE_CHECK = pa.Check(
    _valid_product_size_pairs,
    error=(
        "Product and size must form "
        "a valid canonical pair."
    ),
)


INCOMING_PRODUCT_SIZE_CHECK = pa.Check(
    _valid_incoming_product_size_pairs,
    error=(
        "Incoming product and size must form "
        "a valid canonical pair, or size may "
        "be unknown."
    ),
)


DISTRIBUTION_SCHEMA = pa.DataFrameSchema(
    {
        "date": pa.Column(
            "datetime64[ns]",
            coerce=True,
        ),
        "site_id": pa.Column(
            object,
            required=False,
            nullable=True,
        ),
        "site_name": pa.Column(
            str,
            checks=pa.Check(_nonblank),
            coerce=True,
        ),
        "product": pa.Column(
            str,
            checks=pa.Check.isin(
                CANONICAL_PRODUCTS
            ),
            coerce=True,
        ),
        "size": pa.Column(
            str,
            coerce=True,
        ),
        "quantity": pa.Column(
            int,
            checks=pa.Check.ge(0),
            coerce=True,
        ),
        "households_served": pa.Column(
            float,
            checks=pa.Check(
                _whole_nonnegative
            ),
            required=False,
            nullable=True,
            coerce=True,
        ),
        "children_served": pa.Column(
            float,
            checks=pa.Check(
                _whole_nonnegative
            ),
            required=False,
            nullable=True,
            coerce=True,
        ),
    },
    checks=PRODUCT_SIZE_CHECK,
    strict=False,
)


CURRENT_INVENTORY_SCHEMA = (
    pa.DataFrameSchema(
        {
            "as_of_date": pa.Column(
                "datetime64[ns]",
                coerce=True,
            ),
            "product": pa.Column(
                str,
                checks=pa.Check.isin(
                    CANONICAL_PRODUCTS
                ),
                coerce=True,
            ),
            "size": pa.Column(
                str,
                coerce=True,
            ),
            "quantity_on_hand": pa.Column(
                int,
                checks=pa.Check.ge(0),
                coerce=True,
            ),
            "location": pa.Column(
                object,
                required=False,
                nullable=True,
            ),
        },
        checks=PRODUCT_SIZE_CHECK,
        strict=False,
    )
)


INCOMING_SUPPLY_SCHEMA = (
    pa.DataFrameSchema(
        {
            "expected_date": pa.Column(
                "datetime64[ns]",
                coerce=True,
            ),
            "source": pa.Column(
                str,
                checks=pa.Check(_nonblank),
                coerce=True,
            ),
            "product": pa.Column(
                str,
                checks=pa.Check.isin(
                    CANONICAL_PRODUCTS
                ),
                coerce=True,
            ),
            "size": pa.Column(
                str,
                coerce=True,
            ),
            "quantity": pa.Column(
                int,
                checks=pa.Check.ge(0),
                coerce=True,
            ),
            "status": pa.Column(
                str,
                checks=pa.Check.isin(
                    INCOMING_STATUSES
                ),
                coerce=True,
            ),
        },
        checks=INCOMING_PRODUCT_SIZE_CHECK,
        strict=False,
    )
)


PARTNER_SURVEY_SCHEMA = (
    pa.DataFrameSchema(
        {
            "site_name": pa.Column(
                str,
                checks=pa.Check(_nonblank),
                coerce=True,
            ),
            "zip_code": pa.Column(
                str,
                checks=pa.Check(_nonblank),
                coerce=True,
            ),
            "agency_type": pa.Column(
                str,
                checks=pa.Check.isin(
                    AGENCY_TYPES
                ),
                coerce=True,
            ),
            "families_served_per_month": (
                pa.Column(
                    int,
                    checks=pa.Check.ge(0),
                    coerce=True,
                )
            ),
            "children_under_4_per_month": (
                pa.Column(
                    float,
                    checks=pa.Check(
                        _whole_nonnegative
                    ),
                    required=False,
                    nullable=True,
                    coerce=True,
                )
            ),
            "menstruating_clients_per_month": (
                pa.Column(
                    float,
                    checks=pa.Check(
                        _whole_nonnegative
                    ),
                    required=False,
                    nullable=True,
                    coerce=True,
                )
            ),
            "poverty_share_band": pa.Column(
                str,
                checks=pa.Check.isin(
                    POVERTY_SHARE_BANDS
                ),
                required=False,
                nullable=True,
                coerce=True,
            ),
            "priority_population_flags": (
                pa.Column(
                    object,
                    required=False,
                    nullable=True,
                )
            ),
            "storage_capacity_cases": (
                pa.Column(
                    float,
                    checks=pa.Check(
                        _whole_nonnegative
                    ),
                    required=False,
                    nullable=True,
                    coerce=True,
                )
            ),
            "distribution_frequency": (
                pa.Column(
                    str,
                    checks=pa.Check.isin(
                        DISTRIBUTION_FREQUENCIES
                    ),
                    required=False,
                    nullable=True,
                    coerce=True,
                )
            ),
            "recent_stockout_sizes": (
                pa.Column(
                    object,
                    required=False,
                    nullable=True,
                )
            ),
            "preferred_contact": pa.Column(
                object,
                required=False,
                nullable=True,
            ),
            "languages_spoken": pa.Column(
                object,
                required=False,
                nullable=True,
            ),
        },
        strict=False,
    )
)


SCHEMAS = {
    "distribution_log": (
        DISTRIBUTION_SCHEMA
    ),
    "current_inventory": (
        CURRENT_INVENTORY_SCHEMA
    ),
    "incoming_supply": (
        INCOMING_SUPPLY_SCHEMA
    ),
    "partner_survey": (
        PARTNER_SURVEY_SCHEMA
    ),
}


def _friendly_validation_issues(
    dataframe,
    dataset_type,
):
    """
    Detect common user-facing validation problems before
    Pandera produces technical schema errors.
    """

    issues = []

    date_columns = {
        "distribution_log": "date",
        "current_inventory": "as_of_date",
        "incoming_supply": "expected_date",
    }

    date_column = date_columns.get(
        dataset_type
    )

    if (
        date_column is not None
        and date_column in dataframe.columns
    ):
        parsed_dates = pd.to_datetime(
            dataframe[date_column],
            errors="coerce",
        )

        invalid_count = int(
            parsed_dates.isna().sum()
        )

        if invalid_count:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_date",
                    message=(
                        f"{date_column} contains "
                        f"{invalid_count} invalid or "
                        "missing date value(s)."
                    ),
                    count=invalid_count,
                )
            )

    quantity_columns = {
        "distribution_log": "quantity",
        "current_inventory": (
            "quantity_on_hand"
        ),
        "incoming_supply": "quantity",
        "partner_survey": (
            "families_served_per_month"
        ),
    }

    quantity_column = quantity_columns.get(
        dataset_type
    )

    if (
        quantity_column is not None
        and quantity_column in dataframe.columns
    ):
        raw_values = dataframe[
            quantity_column
        ]

        numeric_values = pd.to_numeric(
            raw_values,
            errors="coerce",
        )

        invalid_numeric = (
            raw_values.notna()
            & numeric_values.isna()
        )

        if invalid_numeric.any():
            count = int(
                invalid_numeric.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_numeric_value",
                    message=(
                        f"{quantity_column} contains "
                        f"{count} value(s) that are "
                        "not valid numbers."
                    ),
                    count=count,
                )
            )

        negative_values = (
            numeric_values.notna()
            & numeric_values.lt(0)
        )

        if negative_values.any():
            count = int(
                negative_values.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="negative_quantity",
                    message=(
                        f"{quantity_column} must contain "
                        "non-negative values. "
                        f"Found {count} invalid row(s)."
                    ),
                    count=count,
                )
            )

        fractional_values = (
            numeric_values.notna()
            & numeric_values.mod(1).ne(0)
        )

        if fractional_values.any():
            count = int(
                fractional_values.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="fractional_quantity",
                    message=(
                        f"{quantity_column} must contain "
                        "whole individual units. "
                        f"Found {count} fractional value(s)."
                    ),
                    count=count,
                )
            )

    if "product" in dataframe.columns:
        invalid_products = (
            ~dataframe["product"].isin(
                CANONICAL_PRODUCTS
            )
        )

        if invalid_products.any():
            count = int(
                invalid_products.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="unknown_product",
                    message=(
                        f"Found {count} unknown product "
                        "value(s). Use a supported "
                        "canonical product category."
                    ),
                    count=count,
                )
            )

    if (
        "product" in dataframe.columns
        and "size" in dataframe.columns
    ):
        allow_unknown = (
            dataset_type
            == "incoming_supply"
        )

        valid_pairs = dataframe.apply(
            lambda row: _is_valid_product_size(
                row["product"],
                row["size"],
                allow_unknown=allow_unknown,
            ),
            axis=1,
        )

        invalid_pairs = ~valid_pairs

        if invalid_pairs.any():
            count = int(
                invalid_pairs.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_product_size",
                    message=(
                        f"Found {count} product-size "
                        "combination(s) that are not "
                        "valid for the selected product."
                    ),
                    count=count,
                )
            )

    if (
        dataset_type == "incoming_supply"
        and "status" in dataframe.columns
    ):
        invalid_status = (
            ~dataframe["status"].isin(
                INCOMING_STATUSES
            )
        )

        if invalid_status.any():
            count = int(
                invalid_status.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_status",
                    message=(
                        "Incoming supply status must be "
                        "'confirmed' or 'pending'. "
                        f"Found {count} invalid row(s)."
                    ),
                    count=count,
                )
            )

    if (
        dataset_type == "partner_survey"
        and "agency_type" in dataframe.columns
    ):
        invalid_agency = (
            ~dataframe["agency_type"].isin(
                AGENCY_TYPES
            )
        )

        if invalid_agency.any():
            count = int(
                invalid_agency.sum()
            )

            issues.append(
                ValidationIssue(
                    severity="error",
                    code="invalid_agency_type",
                    message=(
                        f"Found {count} unsupported "
                        "agency type value(s)."
                    ),
                    count=count,
                )
            )

    return issues


def find_duplicate_issues(
    dataframe,
    dataset_type,
):
    """
    Detect duplicates according to the semantics of each
    canonical input.

    Distribution and incoming-supply exact duplicates are
    warnings and are preserved.

    Inventory duplicate snapshot keys and partner-survey
    duplicate sites are blocking errors.
    """

    if dataset_type not in SCHEMAS:
        raise TableValidationError(
            f"Unknown dataset type: "
            f"{dataset_type!r}."
        )

    issues = []

    if dataset_type in {
        "distribution_log",
        "incoming_supply",
    }:
        duplicate_mask = (
            dataframe.duplicated(
                keep=False
            )
        )

        count = int(
            duplicate_mask.sum()
        )

        if count:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="exact_duplicate_rows",
                    message=(
                        f"Found {count} exact duplicate "
                        "row(s). They were preserved "
                        "because identical visible "
                        "records may represent separate "
                        "valid transactions."
                    ),
                    count=count,
                )
            )

    elif dataset_type == "current_inventory":
        key_columns = [
            "as_of_date",
            "product",
            "size",
        ]

        if "location" in dataframe.columns:
            key_columns.append(
                "location"
            )

        duplicate_mask = (
            dataframe.duplicated(
                subset=key_columns,
                keep=False,
            )
        )

        count = int(
            duplicate_mask.sum()
        )

        if count:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_inventory_key",
                    message=(
                        f"Found {count} inventory row(s) "
                        "with the same snapshot date, "
                        "product, size, and location. "
                        "Resolve these rows before "
                        "continuing to avoid double-"
                        "counting inventory."
                    ),
                    count=count,
                )
            )

    elif dataset_type == "partner_survey":
        site_keys = dataframe[
            "site_name"
        ].map(
            lambda value: (
                normalize_site_name(
                    value
                ).casefold()
            )
        )

        duplicate_mask = (
            site_keys.duplicated(
                keep=False
            )
        )

        count = int(
            duplicate_mask.sum()
        )

        if count:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="duplicate_partner_site",
                    message=(
                        f"Found {count} partner-survey "
                        "row(s) representing duplicate "
                        "normalized site names. Keep "
                        "one current survey record per "
                        "partner."
                    ),
                    count=count,
                )
            )

    return issues


def validate_table(
    dataframe,
    dataset_type,
):
    """
    Validate a canonical dataframe using the appropriate
    Pandera schema.

    Header mapping and value normalization should occur
    before this function is called.
    """

    if dataset_type not in SCHEMAS:
        raise TableValidationError(
            f"Unknown dataset type: "
            f"{dataset_type!r}."
        )

    missing_columns = (
        REQUIRED_COLUMNS[dataset_type]
        - set(dataframe.columns)
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        issue = ValidationIssue(
            severity="error",
            code="missing_required_columns",
            message=(
                "Missing required column(s): "
                f"{missing_text}."
            ),
            count=len(missing_columns),
        )

        raise TableValidationError(
            issue.message,
            issues=[issue],
        )

    friendly_issues = (
        _friendly_validation_issues(
            dataframe,
            dataset_type,
        )
    )

    blocking_friendly_issues = [
        issue
        for issue in friendly_issues
        if issue.severity == "error"
    ]

    if blocking_friendly_issues:
        raise TableValidationError(
            f"{dataset_type} contains "
            "validation problems.",
            issues=blocking_friendly_issues,
        )

    try:
        validated = SCHEMAS[
            dataset_type
        ].validate(
            dataframe.copy(),
            lazy=True,
        )

    except (
        SchemaError,
        SchemaErrors,
    ) as exc:
        failure_cases = getattr(
            exc,
            "failure_cases",
            None,
        )

        fallback_issue = (
            ValidationIssue(
                severity="error",
                code="schema_validation",
                message=(
                    "The uploaded table contains "
                    "values that do not match the "
                    "required data contract."
                ),
            )
        )

        raise TableValidationError(
            f"{dataset_type} failed validation.",
            failure_cases=failure_cases,
            issues=[fallback_issue],
        ) from exc

    duplicate_issues = (
        find_duplicate_issues(
            validated,
            dataset_type,
        )
    )

    blocking_duplicate_issues = [
        issue
        for issue in duplicate_issues
        if issue.severity == "error"
    ]

    if blocking_duplicate_issues:
        raise TableValidationError(
            f"{dataset_type} contains "
            "blocking duplicate records.",
            issues=blocking_duplicate_issues,
        )

    return validated