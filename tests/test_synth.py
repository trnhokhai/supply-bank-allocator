import numpy as np
import pandas as pd

from src.synth import (
    HISTORY_END_DATE,
    N_WEEKS,
    SEED,
    generate_distribution_history,
    generate_partner_master,
    generate_partner_survey,
    generate_current_inventory,
    generate_incoming_supply,
    MESSY_ROW_RATE,
    inject_messy_distribution_rows,
    validate_synthetic_data,
    save_outputs,
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

    diaper_distribution = distribution.loc[
        distribution["product"] == "diaper"
    ]

    diaper_mix = (
        diaper_distribution
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

def test_distribution_contains_expected_products():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    expected_products = {
        "diaper",
        "wipes",
        "pull_up",
        "period_pad",
        "period_tampon",
        "period_liner",
        "period_cup",
        "adult_incontinence",
    }

    assert expected_products.issubset(
        set(distribution["product"].unique())
    )


def test_distribution_product_site_counts():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    pullup_sites = distribution.loc[
        distribution["product"] == "pull_up",
        "site_id",
    ].nunique()

    period_sites = distribution.loc[
        distribution["product"].str.startswith("period_"),
        "site_id",
    ].nunique()

    adult_sites = distribution.loc[
        distribution["product"] == "adult_incontinence",
        "site_id",
    ].nunique()

    assert pullup_sites == 8
    assert period_sites == 10
    assert adult_sites == 3


def test_product_size_vocabularies():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    pullup_sizes = set(
        distribution.loc[
            distribution["product"] == "pull_up",
            "size",
        ]
    )

    adult_sizes = set(
        distribution.loc[
            distribution["product"] == "adult_incontinence",
            "size",
        ]
    )

    wipe_sizes = set(
        distribution.loc[
            distribution["product"] == "wipes",
            "size",
        ]
    )

    assert pullup_sizes.issubset(
        {"2T-3T", "3T-4T", "4T-5T"}
    )

    assert adult_sizes.issubset(
        {"S", "M", "L", "XL"}
    )

    assert wipe_sizes == {"one_size"}


def test_period_cups_are_intermittent():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    distribution = generate_distribution_history(
        partners,
        rng,
    )

    period_sites = partners.loc[
        partners["has_period_products"],
        "site_id",
    ]

    cup_distribution = distribution.loc[
        distribution["product"] == "period_cup"
    ]

    total_possible_site_weeks = 0

    for site_id in period_sites:

        onboarding_week = int(
            partners.loc[
                partners["site_id"] == site_id,
                "onboarding_week",
            ].iloc[0]
        )

        active_weeks = N_WEEKS - onboarding_week

        if site_id == "SITE_008":
            active_weeks -= 6

        total_possible_site_weeks += active_weeks

    actual_cup_site_weeks = (
        cup_distribution[
            ["site_id", "date"]
        ]
        .drop_duplicates()
        .shape[0]
    )

    assert actual_cup_site_weeks < total_possible_site_weeks

def test_partner_survey_structure():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    survey = generate_partner_survey(
        partners,
        rng,
    )

    expected_columns = [
        "site_name",
        "zip_code",
        "agency_type",
        "families_served_per_month",
        "children_under_4_per_month",
        "menstruating_clients_per_month",
        "poverty_share_band",
        "priority_population_flags",
        "storage_capacity_cases",
        "distribution_frequency",
        "recent_stockout_sizes",
        "preferred_contact",
        "languages_spoken",
    ]

    assert len(survey) == 25
    assert list(survey.columns) == expected_columns
    assert survey["site_name"].nunique() == 25

    assert set(survey["site_name"]) == set(
        partners["site_name"]
    )


def test_partner_survey_allowed_values():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    survey = generate_partner_survey(
        partners,
        rng,
    )

    allowed_poverty_bands = {
        "under_25_percent",
        "25_to_50_percent",
        "50_to_75_percent",
        "over_75_percent",
    }

    allowed_frequencies = {
        "weekly",
        "biweekly",
        "monthly",
    }

    assert set(
        survey["poverty_share_band"]
    ).issubset(
        allowed_poverty_bands
    )

    assert set(
        survey["distribution_frequency"]
    ).issubset(
        allowed_frequencies
    )


def test_partner_survey_numeric_values():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)
    survey = generate_partner_survey(
        partners,
        rng,
    )

    assert (
        survey["families_served_per_month"] > 0
    ).all()

    assert (
        survey["children_under_4_per_month"] >= 0
    ).all()

    assert (
        survey["menstruating_clients_per_month"] >= 0
    ).all()

    assert (
        survey["storage_capacity_cases"] > 0
    ).all()

    assert (
        survey["zip_code"]
        .str.fullmatch(r"\d{5}")
        .all()
    )

def test_current_inventory_structure():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    expected_columns = [
        "as_of_date",
        "product",
        "size",
        "quantity_on_hand",
        "location",
    ]

    assert list(inventory.columns) == expected_columns

    assert (
        inventory["as_of_date"] == HISTORY_END_DATE
    ).all()

    assert (
        inventory["quantity_on_hand"] >= 0
    ).all()


def test_current_inventory_covers_demanded_products():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    demand_combinations = set(
        map(
            tuple,
            distribution[
                ["product", "size"]
            ]
            .drop_duplicates()
            .to_numpy(),
        )
    )

    inventory_combinations = set(
        map(
            tuple,
            inventory[
                ["product", "size"]
            ]
            .drop_duplicates()
            .to_numpy(),
        )
    )

    assert demand_combinations.issubset(
        inventory_combinations
    )


def test_diaper_inventory_has_long_and_short_sizes():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    recent_dates = sorted(
        distribution["date"].unique()
    )[-8:]

    recent_diaper = distribution.loc[
        distribution["date"].isin(recent_dates)
        & (distribution["product"] == "diaper")
    ]

    weekly_demand = (
        recent_diaper
        .groupby("size")["quantity"]
        .sum()
        / len(recent_dates)
    )

    diaper_inventory = (
        inventory.loc[
            inventory["product"] == "diaper"
        ]
        .groupby("size")["quantity_on_hand"]
        .sum()
    )

    weeks_of_supply = (
        diaper_inventory / weekly_demand
    )

    assert weeks_of_supply["N"] > 12
    assert weeks_of_supply["1"] > 12
    assert weeks_of_supply["2"] > 12

    assert weeks_of_supply["5"] < 3
    assert weeks_of_supply["6"] < 3

def test_incoming_supply_structure():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    expected_columns = [
        "expected_date",
        "source",
        "product",
        "size",
        "quantity",
        "status",
    ]

    assert list(incoming.columns) == expected_columns

    assert (
        incoming["expected_date"]
        > HISTORY_END_DATE
    ).all()

    assert (
        incoming["quantity"] > 0
    ).all()


def test_incoming_supply_has_both_statuses():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    assert set(incoming["status"]) == {
        "confirmed",
        "pending",
    }


def test_donation_diaper_mix_skews_small():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    donations = incoming.loc[
        incoming["source"].isin(
            [
                "Community Donations",
                "Spring Donation Drive",
                "Holiday Donation Drive",
            ]
        )
        & (
            incoming["product"]
            == "diaper"
        )
    ]

    donation_mix = (
        donations
        .groupby("size")["quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    top_three = set(
        donation_mix.head(3).index
    )

    assert top_three == {
        "N",
        "1",
        "2",
    }


def test_donation_seasonality_and_drives():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    sources = set(incoming["source"])

    assert "Spring Donation Drive" in sources
    assert "Holiday Donation Drive" in sources

    community_donations = incoming.loc[
        incoming["source"]
        == "Community Donations"
    ].copy()

    weekly_donations = (
        community_donations
        .groupby("expected_date")["quantity"]
        .sum()
    )

    summer_mask = (
        weekly_donations.index.month
        .isin([6, 7, 8])
    )

    summer_average = (
        weekly_donations.loc[
            summer_mask
        ].mean()
    )

    non_summer_average = (
        weekly_donations.loc[
            ~summer_mask
        ].mean()
    )

    assert summer_average < non_summer_average

def test_messy_distribution_preserves_row_count():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    clean_distribution = (
        generate_distribution_history(
            partners,
            rng,
        )
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            clean_distribution,
            rng,
        )
    )

    assert len(messy_distribution) == len(
        clean_distribution
    )


def test_messy_distribution_does_not_mutate_clean_data():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    clean_distribution = (
        generate_distribution_history(
            partners,
            rng,
        )
    )

    original_distribution = (
        clean_distribution.copy(deep=True)
    )

    inject_messy_distribution_rows(
        clean_distribution,
        rng,
    )

    pd.testing.assert_frame_equal(
        clean_distribution,
        original_distribution,
    )


def test_messy_distribution_rate_is_about_three_percent():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    clean_distribution = (
        generate_distribution_history(
            partners,
            rng,
        )
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            clean_distribution,
            rng,
        )
    )

    comparison_columns = [
        "product",
        "size",
        "quantity",
    ]

    changed_rows = (
        clean_distribution[
            comparison_columns
        ]
        .astype(str)
        .ne(
            messy_distribution[
                comparison_columns
            ].astype(str)
        )
        .any(axis=1)
        .sum()
    )

    actual_rate = (
        changed_rows
        / len(clean_distribution)
    )

    assert abs(
        actual_rate - MESSY_ROW_RATE
    ) < 0.005


def test_messy_distribution_contains_planted_issues():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    clean_distribution = (
        generate_distribution_history(
            partners,
            rng,
        )
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            clean_distribution,
            rng,
        )
    )

    quantity_strings = (
        messy_distribution["quantity"]
        .astype(str)
    )

    has_pack_quantity = (
        quantity_strings
        .str.contains(
            "packs x",
            regex=False,
        )
        .any()
    )

    product_changed = (
        clean_distribution["product"]
        .astype(str)
        .ne(
            messy_distribution["product"]
            .astype(str)
        )
        .any()
    )

    size_changed = (
        clean_distribution["size"]
        .astype(str)
        .ne(
            messy_distribution["size"]
            .astype(str)
        )
        .any()
    )

    assert has_pack_quantity
    assert product_changed
    assert size_changed

def test_full_synthetic_validation_passes():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    survey = generate_partner_survey(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            distribution,
            rng,
        )
    )

    summary = validate_synthetic_data(
        partners,
        distribution,
        messy_distribution,
        inventory,
        incoming,
        survey,
    )

    assert summary["partner_sites"] == 25
    assert summary["historical_weeks"] == 78


def test_validation_summary_contains_business_checks():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    survey = generate_partner_survey(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            distribution,
            rng,
        )
    )

    summary = validate_synthetic_data(
        partners,
        distribution,
        messy_distribution,
        inventory,
        incoming,
        survey,
    )

    assert set(
        summary["top_diaper_sizes"]
    ) == {"4", "5"}

    assert set(
        summary["top_donation_sizes"]
    ) == {"N", "1", "2"}

    assert (
        summary["messy_row_rate"]
        > 0
    )

    assert (
        summary["diaper_weeks_of_supply"]["5"]
        < 3
    )

    assert (
        summary["diaper_weeks_of_supply"]["6"]
        < 3
    )

def test_save_outputs_creates_expected_files(
    tmp_path,
):
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    survey = generate_partner_survey(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            distribution,
            rng,
        )
    )

    saved_files = save_outputs(
        distribution,
        messy_distribution,
        inventory,
        incoming,
        survey,
        output_dir=tmp_path,
    )

    expected_file_names = {
        "distribution_log_clean.csv",
        "distribution_log_clean.xlsx",
        "distribution_log_messy.csv",
        "distribution_log_messy.xlsx",
        "current_inventory.csv",
        "current_inventory.xlsx",
        "incoming_supply.csv",
        "incoming_supply.xlsx",
        "partner_survey.csv",
        "partner_survey.xlsx",
        "distribution_log_alternate_headers.csv",
        "distribution_log_alternate_headers.xlsx",
    }

    actual_file_names = {
        path.name
        for path in saved_files
    }

    assert actual_file_names == (
        expected_file_names
    )

    assert all(
        path.exists()
        for path in saved_files
    )


def test_alternate_header_file_has_expected_headers(
    tmp_path,
):
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution = generate_distribution_history(
        partners,
        rng,
    )

    survey = generate_partner_survey(
        partners,
        rng,
    )

    inventory = generate_current_inventory(
        distribution,
        rng,
    )

    incoming = generate_incoming_supply(
        distribution,
        rng,
    )

    messy_distribution = (
        inject_messy_distribution_rows(
            distribution,
            rng,
        )
    )

    save_outputs(
        distribution,
        messy_distribution,
        inventory,
        incoming,
        survey,
        output_dir=tmp_path,
    )

    alternate_file = pd.read_csv(
        tmp_path
        / "distribution_log_alternate_headers.csv"
    )

    expected_columns = [
        "Distribution Date",
        "Site ID",
        "Partner",
        "Product Category",
        "Product Size",
        "Qty",
        "Households",
        "Children",
    ]

    assert list(
        alternate_file.columns
    ) == expected_columns