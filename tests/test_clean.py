from pathlib import Path

import pandas as pd

from src.clean import (
    clean_distribution_log,
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