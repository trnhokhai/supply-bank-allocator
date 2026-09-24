import numpy as np
import pandas as pd

from src.synth import (
    HISTORY_END_DATE,
    N_WEEKS,
    SEED,
    generate_distribution_history,
    generate_partner_master,
)


def test_partner_master_structure():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    assert len(partners) == 25
    assert partners["site_id"].nunique() == 25
    assert partners["site_name"].nunique() == 25


def test_partner_agency_mix():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    counts = partners["agency_type"].value_counts().to_dict()

    expected_counts = {
        "pantry": 6,
        "shelter": 5,
        "wic_clinic": 4,
        "school": 4,
        "health_center": 3,
        "faith_community": 2,
        "other": 1,
    }

    assert counts == expected_counts


def test_special_onboarding_cases():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    site_24_week = partners.loc[
        partners["site_id"] == "SITE_024",
        "onboarding_week",
    ].iloc[0]

    site_25_week = partners.loc[
        partners["site_id"] == "SITE_025",
        "onboarding_week",
    ].iloc[0]

    assert site_24_week == 30
    assert site_25_week == 50


def test_product_coverage_counts():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    assert partners["has_period_products"].sum() == 10
    assert partners["has_pullups"].sum() == 8
    assert partners["has_adult_incontinence"].sum() == 3


def test_base_weekly_demand_matches_tier():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    tier_ranges = {
        "small": (400, 800),
        "medium": (800, 1500),
        "large": (1500, 2500),
    }

    for _, row in partners.iterrows():
        low, high = tier_ranges[row["demand_tier"]]

        assert low <= row["base_weekly_demand"] <= high

def test_distribution_history_has_78_weeks():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    assert distribution["date"].nunique() == N_WEEKS


def test_distribution_history_schema():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    expected_columns = [
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
        "households_served",
        "children_served",
    ]

    assert list(distribution.columns) == expected_columns


def test_diaper_size_mix_pattern():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    diaper_mix = (
        distribution
        .groupby("size")["quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    top_two = set(diaper_mix.head(2).index)
    bottom_two = set(diaper_mix.tail(2).index)

    assert top_two == {"4", "5"}
    assert bottom_two == {"N", "7"}


def test_mid_series_partner_start_dates():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    dates = pd.date_range(
        end=HISTORY_END_DATE,
        periods=N_WEEKS,
        freq="W-MON",
    )

    site_24_first_date = distribution.loc[
        distribution["site_id"] == "SITE_024",
        "date",
    ].min()

    site_25_first_date = distribution.loc[
        distribution["site_id"] == "SITE_025",
        "date",
    ].min()

    assert site_24_first_date == dates[30]
    assert site_25_first_date == dates[50]


def test_site_08_has_six_week_gap():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    dates = pd.date_range(
        end=HISTORY_END_DATE,
        periods=N_WEEKS,
        freq="W-MON",
    )

    gap_dates = set(dates[35:41])

    site_08_dates = set(
        distribution.loc[
            distribution["site_id"] == "SITE_008",
            "date",
        ]
    )

    assert gap_dates.isdisjoint(site_08_dates)