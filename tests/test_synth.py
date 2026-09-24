import numpy as np

from src.synth import SEED, generate_partner_master


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