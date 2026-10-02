from pathlib import Path

import pandas as pd

from src.aggregate import (
    aggregate_distribution_to_iso_weeks,
    build_site_activity_calendar,
    find_inactive_spans,
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


def test_weekly_aggregation_preserves_total_quantity():
    df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    assert (
        weekly["quantity"].sum()
        == df["quantity"].sum()
    )

    assert (
        weekly["week_start"]
        .dt
        .weekday
        .eq(0)
        .all()
    )


def test_weekly_output_has_unique_canonical_grain():
    df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    duplicate_mask = weekly.duplicated(
        subset=[
            "week_start",
            "site_id",
            "product",
            "size",
        ]
    )

    assert not duplicate_mask.any()


def test_site_008_has_six_week_inactive_span():
    df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    spans = find_inactive_spans(
        df
    )

    site_008 = spans.loc[
        spans["site_id"]
        .eq("SITE_008")
    ]

    assert len(site_008) == 1

    assert (
        int(
            site_008.iloc[
                0
            ]["weeks_inactive"]
        )
        == 6
    )


def test_late_onboarding_is_not_an_inactive_gap():
    df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    calendar = (
        build_site_activity_calendar(
            df
        )
    )

    site_024 = calendar.loc[
        calendar["site_id"]
        .eq("SITE_024")
    ]

    site_025 = calendar.loc[
        calendar["site_id"]
        .eq("SITE_025")
    ]

    assert (
        site_024.iloc[:30][
            "activity_state"
        ]
        .eq("pre_observation")
        .all()
    )

    assert (
        site_025.iloc[:50][
            "activity_state"
        ]
        .eq("pre_observation")
        .all()
    )

    spans = find_inactive_spans(
        df
    )

    assert not (
        spans["site_id"]
        .isin(
            [
                "SITE_024",
                "SITE_025",
            ]
        )
        .any()
    )


def test_inactive_site_gap_is_not_zero_filled():
    df = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    dates = sorted(
        pd.to_datetime(
            df["date"]
        ).unique()
    )

    expected_gap_weeks = set(
        pd.to_datetime(
            dates[35:41]
        )
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    site_008_weeks = set(
        weekly.loc[
            weekly["site_id"]
            .eq("SITE_008"),
            "week_start",
        ]
    )

    assert expected_gap_weeks.isdisjoint(
        site_008_weeks
    )


def test_missing_series_week_is_zero_filled_when_site_is_active():
    df = pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "4",
                "quantity": 10,
            },
            {
                "date": "2026-01-05",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "5",
                "quantity": 20,
            },
            {
                "date": "2026-01-12",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "4",
                "quantity": 11,
            },
            {
                "date": "2026-01-12",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "wipes",
                "size": "one_size",
                "quantity": 5,
            },
            {
                "date": "2026-01-19",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "4",
                "quantity": 12,
            },
            {
                "date": "2026-01-19",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "5",
                "quantity": 22,
            },
        ]
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    imputed_row = weekly.loc[
        (
            weekly["site_id"]
            .eq("SITE_A")
        )
        & (
            weekly["product"]
            .eq("diaper")
        )
        & (
            weekly["size"]
            .eq("5")
        )
        & (
            weekly["week_start"]
            .eq(
                pd.Timestamp(
                    "2026-01-12"
                )
            )
        )
    ]

    assert len(imputed_row) == 1
    assert imputed_row.iloc[0]["quantity"] == 0

    assert bool(
        imputed_row.iloc[
            0
        ]["is_imputed_zero"]
    )


def test_full_site_gap_is_not_imputed_as_zero():
    df = pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "5",
                "quantity": 20,
            },
            {
                "date": "2026-01-19",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "5",
                "quantity": 22,
            },
        ]
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    missing_week = weekly.loc[
        weekly["week_start"]
        .eq(
            pd.Timestamp(
                "2026-01-12"
            )
        )
    ]

    assert missing_week.empty


def test_multiple_records_in_same_iso_week_are_summed():
    df = pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "4",
                "quantity": 10,
            },
            {
                "date": "2026-01-07",
                "site_id": "SITE_A",
                "site_name": "Site A",
                "product": "diaper",
                "size": "4",
                "quantity": 15,
            },
        ]
    )

    weekly = (
        aggregate_distribution_to_iso_weeks(
            df
        )
    )

    assert len(weekly) == 1

    assert (
        weekly.iloc[0]["quantity"]
        == 25
    )

    assert (
        weekly.iloc[0]["week_start"]
        == pd.Timestamp(
            "2026-01-05"
        )
    )