from pathlib import Path

import pandas as pd
import pytest

from src.clean import (
    clean_distribution_log,
    clean_partner_survey,
)
from src.site_master import (
    SiteMasterError,
    build_site_master,
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


def _load_clean_distribution():
    raw = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    return clean_distribution_log(
        raw
    ).dataframe


def _load_clean_survey():
    raw = pd.read_csv(
        SAMPLE_DIR
        / "partner_survey.csv"
    )

    return clean_partner_survey(
        raw
    ).dataframe


def test_synthetic_site_master_has_25_sites():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    master = build_site_master(
        distribution,
        survey,
    )

    assert len(master) == 25

    assert (
        master["site_id"]
        .nunique()
        == 25
    )

    assert set(
        master["site_id"]
    ) == {
        f"SITE_{number:03d}"
        for number in range(
            1,
            26,
        )
    }


def test_distribution_ids_override_survey_generated_ids():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    survey_site_id = (
        survey.loc[
            survey["site_name"]
            .eq("Partner Site 01"),
            "site_id",
        ]
        .iloc[0]
    )

    assert survey_site_id.startswith(
        "AUTO_"
    )

    master = build_site_master(
        distribution,
        survey,
    )

    master_site_id = (
        master.loc[
            master["site_name"]
            .eq("Partner Site 01"),
            "site_id",
        ]
        .iloc[0]
    )

    assert master_site_id == "SITE_001"


def test_all_synthetic_sites_have_history_and_survey():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    master = build_site_master(
        distribution,
        survey,
    )

    assert (
        master[
            "has_distribution_history"
        ]
        .all()
    )

    assert (
        master[
            "has_survey_data"
        ]
        .all()
    )

    assert (
        master["agency_type"]
        .notna()
        .all()
    )


def test_site_master_works_without_survey():
    distribution = (
        _load_clean_distribution()
    )

    master = build_site_master(
        distribution,
        survey_df=None,
    )

    assert len(master) == 25

    assert (
        master[
            "has_distribution_history"
        ]
        .all()
    )

    assert not (
        master[
            "has_survey_data"
        ]
        .any()
    )


def test_survey_only_partner_is_added_for_cold_start():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    new_partner = (
        survey
        .head(1)
        .copy()
    )

    new_partner.loc[
        new_partner.index[0],
        "site_name",
    ] = "New Community Partner"

    new_partner.loc[
        new_partner.index[0],
        "site_id",
    ] = "IGNORED_SURVEY_ID"

    new_partner.loc[
        new_partner.index[0],
        "zip_code",
    ] = "60699"

    survey_with_new_partner = (
        pd.concat(
            [
                survey,
                new_partner,
            ],
            ignore_index=True,
        )
    )

    master = build_site_master(
        distribution,
        survey_with_new_partner,
    )

    assert len(master) == 26

    new_site = master.loc[
        master["site_name"]
        .eq("New Community Partner")
    ]

    assert len(new_site) == 1

    row = new_site.iloc[0]

    assert row["site_id"].startswith(
        "AUTO_NEW_COMMUNITY_PARTNER"
    )

    assert not bool(
        row["has_distribution_history"]
    )

    assert bool(
        row["has_survey_data"]
    )

    assert pd.isna(
        row[
            "first_distribution_date"
        ]
    )


def test_survey_name_matching_is_case_and_whitespace_insensitive():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    survey.loc[
        survey["site_name"]
        .eq("Partner Site 01"),
        "site_name",
    ] = "  partner   SITE 01 "

    master = build_site_master(
        distribution,
        survey,
    )

    assert len(master) == 25

    site = master.loc[
        master["site_id"]
        .eq("SITE_001")
    ]

    assert len(site) == 1

    assert bool(
        site.iloc[0][
            "has_survey_data"
        ]
    )


def test_site_master_contains_history_summary():
    distribution = (
        _load_clean_distribution()
    )

    survey = _load_clean_survey()

    master = build_site_master(
        distribution,
        survey,
    )

    site_024 = master.loc[
        master["site_id"]
        .eq("SITE_024")
    ].iloc[0]

    site_001 = master.loc[
        master["site_id"]
        .eq("SITE_001")
    ].iloc[0]

    assert (
        site_024[
            "first_distribution_date"
        ]
        > site_001[
            "first_distribution_date"
        ]
    )

    assert (
        site_024[
            "observed_distribution_weeks"
        ]
        < site_001[
            "observed_distribution_weeks"
        ]
    )


def test_conflicting_distribution_identity_is_rejected():
    distribution = pd.DataFrame(
        [
            {
                "date": "2026-01-05",
                "site_id": "SITE_A",
                "site_name": "Same Partner",
            },
            {
                "date": "2026-01-12",
                "site_id": "SITE_B",
                "site_name": " same   partner ",
            },
        ]
    )

    with pytest.raises(
        SiteMasterError
    ):
        build_site_master(
            distribution
        )