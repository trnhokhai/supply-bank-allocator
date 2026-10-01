from pathlib import Path

import pandas as pd

from src.clean import (
    clean_current_inventory,
    clean_distribution_log,
    clean_incoming_supply,
    clean_partner_survey,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

SAMPLE_DIR = (
    PROJECT_ROOT
    / "data"
    / "sample"
)


def test_clean_distribution_file_is_stable():
    clean_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    result = clean_distribution_log(
        clean_df
    )

    assert result.report.input_rows == len(
        clean_df
    )

    assert result.report.output_rows == len(
        clean_df
    )

    assert result.report.dropped_rows == 0

    assert (
        result.report.corrected_rows
        == 0
    )


def test_messy_distribution_cleans_to_ground_truth():
    clean_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    messy_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    )

    expected = clean_distribution_log(
        clean_df
    ).dataframe

    actual = clean_distribution_log(
        messy_df
    ).dataframe

    pd.testing.assert_frame_equal(
        actual.reset_index(drop=True),
        expected.reset_index(drop=True),
    )


def test_quality_report_counts_all_planted_dirty_rows():
    clean_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    messy_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    )

    dirty_row_mask = (
        messy_df["product"]
        .astype(str)
        .ne(
            clean_df["product"]
            .astype(str)
        )
        |
        messy_df["size"]
        .astype(str)
        .ne(
            clean_df["size"]
            .astype(str)
        )
        |
        messy_df["quantity"]
        .astype(str)
        .ne(
            clean_df["quantity"]
            .astype(str)
        )
    )

    result = clean_distribution_log(
        messy_df
    )

    assert (
        result.report.corrected_rows
        == int(dirty_row_mask.sum())
    )

    assert result.report.dropped_rows == 0


def test_quality_report_explains_messy_corrections():
    messy_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    )

    result = clean_distribution_log(
        messy_df
    )

    correction_codes = {
        event.code
        for event
        in result.report.corrections
    }

    assert {
        "product_normalized",
        "size_normalized",
        "quantity_normalized",
    }.issubset(
        correction_codes
    )

    assert all(
        event.count > 0
        for event
        in result.report.corrections
    )


def test_cleaning_never_silently_drops_distribution_rows():
    messy_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    )

    result = clean_distribution_log(
        messy_df
    )

    assert len(result.dataframe) == len(
        messy_df
    )

    assert result.report.dropped_rows == 0


def test_distribution_duplicate_warning_reaches_quality_report():
    clean_df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    ).head(1)

    duplicate_df = pd.concat(
        [
            clean_df,
            clean_df,
        ],
        ignore_index=True,
    )

    result = clean_distribution_log(
        duplicate_df
    )

    warning_codes = {
        event.code
        for event
        in result.report.warnings
    }

    assert (
        "exact_duplicate_rows"
        in warning_codes
    )

    assert len(result.dataframe) == 2

def test_clean_current_inventory_is_stable():
    df = pd.read_csv(
        SAMPLE_DIR
        / "current_inventory.csv"
    )

    result = clean_current_inventory(
        df
    )

    assert len(result.dataframe) == len(
        df
    )

    assert result.report.dropped_rows == 0
    assert result.report.corrected_rows == 0


def test_inventory_normalizes_product_size_and_quantity():
    df = pd.read_csv(
        SAMPLE_DIR
        / "current_inventory.csv"
    ).head(1).copy()
    df["quantity_on_hand"] = (
    df["quantity_on_hand"]
    .astype(object)
    )
    df.loc[0, "product"] = " ADULT INCONTINENCE "
    df.loc[0, "size"] = " l "
    df.loc[
        0,
        "quantity_on_hand",
    ] = "12 packs x 25 units"

    result = clean_current_inventory(
        df
    )

    assert (
        result.dataframe.loc[
            0,
            "product",
        ]
        == "adult_incontinence"
    )

    assert (
        result.dataframe.loc[
            0,
            "size",
        ]
        == "L"
    )

    assert (
        result.dataframe.loc[
            0,
            "quantity_on_hand",
        ]
        == 300
    )

    assert result.report.corrected_rows == 1


def test_clean_incoming_supply_is_stable():
    df = pd.read_csv(
        SAMPLE_DIR
        / "incoming_supply.csv"
    )

    result = clean_incoming_supply(
        df
    )

    assert len(result.dataframe) == len(
        df
    )

    assert result.report.dropped_rows == 0
    assert result.report.corrected_rows == 0


def test_incoming_supply_normalizes_supported_variants():
    df = pd.read_csv(
        SAMPLE_DIR
        / "incoming_supply.csv"
    ).head(1).copy()
    df["quantity"] = (
    df["quantity"]
    .astype(object)
    )
    df.loc[0, "source"] = (
        "  Community   Donations "
    )
    df.loc[0, "product"] = " DIAPER "
    df.loc[0, "size"] = " newborn "
    df.loc[0, "quantity"] = "300 units"
    df.loc[0, "status"] = " Confirmed "

    result = clean_incoming_supply(
        df
    )

    row = result.dataframe.iloc[0]

    assert row["source"] == (
        "Community Donations"
    )
    assert row["product"] == "diaper"
    assert row["size"] == "N"
    assert row["quantity"] == 300
    assert row["status"] == "confirmed"

    assert result.report.corrected_rows == 1


def test_incoming_supply_preserves_unknown_size():
    df = pd.read_csv(
        SAMPLE_DIR
        / "incoming_supply.csv"
    ).head(1).copy()

    df.loc[0, "size"] = " UNKNOWN "

    result = clean_incoming_supply(
        df
    )

    assert (
        result.dataframe.loc[
            0,
            "size",
        ]
        == "unknown"
    )


def test_clean_partner_survey_generates_site_ids():
    df = pd.read_csv(
        SAMPLE_DIR
        / "partner_survey.csv"
    )

    result = clean_partner_survey(
        df
    )

    assert len(result.dataframe) == 25

    assert (
        result.dataframe["site_id"]
        .notna()
        .all()
    )

    assert (
        result.dataframe["site_id"]
        .nunique()
        == 25
    )


def test_partner_survey_normalizes_recent_stockouts():
    df = pd.read_csv(
        SAMPLE_DIR
        / "partner_survey.csv"
    ).copy()

    result = clean_partner_survey(
        df
    )

    original_non_none = (
        df["recent_stockout_sizes"]
        .astype(str)
        .str.casefold()
        .ne("none")
        .sum()
    )

    normalized_values = (
        result.dataframe[
            "recent_stockout_sizes"
        ]
    )

    normalized_non_none = (
        normalized_values[
            normalized_values
            .astype(str)
            .str.casefold()
            .ne("none")
        ]
    )

    assert len(
        normalized_non_none
    ) == original_non_none

    assert all(
        ":" in value
        for value in normalized_non_none
    )


def test_partner_survey_accepts_explicit_product_stockouts():
    df = pd.read_csv(
        SAMPLE_DIR
        / "partner_survey.csv"
    ).head(1).copy()

    df.loc[
        0,
        "recent_stockout_sizes",
    ] = (
        "diaper:SIZE5;"
        "period_pad:OVERNIGHT"
    )

    result = clean_partner_survey(
        df
    )

    assert (
        result.dataframe.loc[
            0,
            "recent_stockout_sizes",
        ]
        == (
            "diaper:5;"
            "period_pad:overnight"
        )
    )


def test_all_four_cleaners_preserve_row_counts():
    datasets = [
        (
            "distribution_log_clean.csv",
            clean_distribution_log,
        ),
        (
            "current_inventory.csv",
            clean_current_inventory,
        ),
        (
            "incoming_supply.csv",
            clean_incoming_supply,
        ),
        (
            "partner_survey.csv",
            clean_partner_survey,
        ),
    ]

    for filename, cleaner in datasets:
        df = pd.read_csv(
            SAMPLE_DIR / filename
        )

        result = cleaner(df)

        assert len(
            result.dataframe
        ) == len(df)

        assert (
            result.report.dropped_rows
            == 0
        )