from pathlib import Path

import pandas as pd
import pytest

from src.validate import (
    TableValidationError,
    find_duplicate_issues,
    validate_table,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"


def test_clean_distribution_log_validates():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    )

    result = validate_table(
        df,
        dataset_type="distribution_log",
    )

    assert len(result) == len(df)


def test_current_inventory_validates():
    df = pd.read_csv(
        SAMPLE_DIR / "current_inventory.csv"
    )

    result = validate_table(
        df,
        dataset_type="current_inventory",
    )

    assert len(result) == len(df)


def test_incoming_supply_validates():
    df = pd.read_csv(
        SAMPLE_DIR / "incoming_supply.csv"
    )

    result = validate_table(
        df,
        dataset_type="incoming_supply",
    )

    assert len(result) == len(df)


def test_partner_survey_validates():
    df = pd.read_csv(
        SAMPLE_DIR / "partner_survey.csv"
    )

    result = validate_table(
        df,
        dataset_type="partner_survey",
    )

    assert len(result) == len(df)


def test_partner_survey_optional_enrichment_fields_may_be_absent():
    df = pd.read_csv(
        SAMPLE_DIR / "partner_survey.csv"
    )[
        [
            "site_name",
            "zip_code",
            "agency_type",
            "families_served_per_month",
        ]
    ]

    result = validate_table(
        df,
        dataset_type="partner_survey",
    )

    assert len(result) == len(df)


def test_missing_required_column_is_rejected():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).drop(columns=["quantity"])

    with pytest.raises(
        TableValidationError,
        match="Missing required",
    ):
        validate_table(
            df,
            dataset_type="distribution_log",
        )


def test_negative_distribution_quantity_is_rejected():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).head(5).copy()

    df.loc[0, "quantity"] = -100

    with pytest.raises(TableValidationError):
        validate_table(
            df,
            dataset_type="distribution_log",
        )


def test_invalid_incoming_status_is_rejected():
    df = pd.read_csv(
        SAMPLE_DIR / "incoming_supply.csv"
    ).head(5).copy()

    df.loc[0, "status"] = "arrived"

    with pytest.raises(TableValidationError):
        validate_table(
            df,
            dataset_type="incoming_supply",
        )


def test_invalid_product_size_pair_is_rejected():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).head(5).copy()

    df.loc[0, "product"] = "diaper"
    df.loc[0, "size"] = "XL"

    with pytest.raises(TableValidationError):
        validate_table(
            df,
            dataset_type="distribution_log",
        )

def test_incoming_supply_allows_unknown_size():
    df = pd.read_csv(
        SAMPLE_DIR / "incoming_supply.csv"
    ).head(1).copy()

    df.loc[0, "size"] = "unknown"

    result = validate_table(
        df,
        dataset_type="incoming_supply",
    )

    assert result.loc[0, "size"] == "unknown"


def test_distribution_exact_duplicates_are_warning_only():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).head(1)

    duplicate_df = pd.concat(
        [df, df],
        ignore_index=True,
    )

    issues = find_duplicate_issues(
        duplicate_df,
        dataset_type="distribution_log",
    )

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].code == "exact_duplicate_rows"
    assert issues[0].count == 2

    result = validate_table(
        duplicate_df,
        dataset_type="distribution_log",
    )

    assert len(result) == 2


def test_incoming_supply_exact_duplicates_are_warning_only():
    df = pd.read_csv(
        SAMPLE_DIR / "incoming_supply.csv"
    ).head(1)

    duplicate_df = pd.concat(
        [df, df],
        ignore_index=True,
    )

    issues = find_duplicate_issues(
        duplicate_df,
        dataset_type="incoming_supply",
    )

    assert len(issues) == 1
    assert issues[0].severity == "warning"
    assert issues[0].code == "exact_duplicate_rows"
    assert issues[0].count == 2

    result = validate_table(
        duplicate_df,
        dataset_type="incoming_supply",
    )

    assert len(result) == 2


def test_current_inventory_duplicate_snapshot_key_is_blocking():
    df = pd.read_csv(
        SAMPLE_DIR / "current_inventory.csv"
    ).head(1)

    duplicate_df = pd.concat(
        [df, df],
        ignore_index=True,
    )

    with pytest.raises(
        TableValidationError
    ) as exc_info:
        validate_table(
            duplicate_df,
            dataset_type="current_inventory",
        )

    assert any(
        issue.code == "duplicate_inventory_key"
        and issue.severity == "error"
        for issue in exc_info.value.issues
    )


def test_partner_survey_duplicate_normalized_site_is_blocking():
    df = pd.read_csv(
        SAMPLE_DIR / "partner_survey.csv"
    ).head(1)

    duplicate = df.copy()

    duplicate.loc[
        duplicate.index[0],
        "site_name",
    ] = (
        "  "
        + str(df.iloc[0]["site_name"])
        + "   "
    )

    duplicate_df = pd.concat(
        [df, duplicate],
        ignore_index=True,
    )

    with pytest.raises(
        TableValidationError
    ) as exc_info:
        validate_table(
            duplicate_df,
            dataset_type="partner_survey",
        )

    assert any(
        issue.code == "duplicate_partner_site"
        and issue.severity == "error"
        for issue in exc_info.value.issues
    )


def test_negative_quantity_has_friendly_issue():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).head(3).copy()

    df.loc[0, "quantity"] = -50

    with pytest.raises(
        TableValidationError
    ) as exc_info:
        validate_table(
            df,
            dataset_type="distribution_log",
        )

    messages = " ".join(
        issue.message
        for issue in exc_info.value.issues
    ).lower()

    assert "non-negative" in messages


def test_invalid_status_has_friendly_issue():
    df = pd.read_csv(
        SAMPLE_DIR / "incoming_supply.csv"
    ).head(3).copy()

    df.loc[0, "status"] = "arrived"

    with pytest.raises(
        TableValidationError
    ) as exc_info:
        validate_table(
            df,
            dataset_type="incoming_supply",
        )

    messages = " ".join(
        issue.message
        for issue in exc_info.value.issues
    ).lower()

    assert "confirmed" in messages
    assert "pending" in messages


def test_invalid_product_size_has_friendly_issue():
    df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    ).head(3).copy()

    df.loc[0, "product"] = "diaper"
    df.loc[0, "size"] = "XL"

    with pytest.raises(
        TableValidationError
    ) as exc_info:
        validate_table(
            df,
            dataset_type="distribution_log",
        )

    messages = " ".join(
        issue.message
        for issue in exc_info.value.issues
    ).lower()

    assert "product" in messages
    assert "size" in messages