from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------
# Global configuration
# ---------------------------------------------------------

SEED = 42
N_WEEKS = 78
N_SITES = 25
MESSY_ROW_RATE = 0.03

HISTORY_END_DATE = pd.Timestamp("2026-09-21")

DIAPER_SIZES = ["N", "1", "2", "3", "4", "5", "6", "7"]

BASE_DIAPER_MIX = {
    "N": 0.03,
    "1": 0.08,
    "2": 0.12,
    "3": 0.17,
    "4": 0.24,
    "5": 0.23,
    "6": 0.10,
    "7": 0.03,
}

DONATION_DIAPER_MIX = {
    "N": 0.22,
    "1": 0.24,
    "2": 0.20,
    "3": 0.14,
    "4": 0.09,
    "5": 0.06,
    "6": 0.04,
    "7": 0.01,
}

INCOMING_HORIZON_WEEKS = 52

PULLUP_SIZES = ["2T-3T", "3T-4T", "4T-5T"]

PULLUP_MIX = {
    "2T-3T": 0.30,
    "3T-4T": 0.40,
    "4T-5T": 0.30,
}

ADULT_INCONTINENCE_SIZES = ["S", "M", "L", "XL"]

ADULT_INCONTINENCE_MIX = {
    "S": 0.15,
    "M": 0.35,
    "L": 0.35,
    "XL": 0.15,
}

PERIOD_PRODUCT_CONFIG = {
    "period_pad": {
        "sizes": ["regular", "super", "overnight"],
        "mix": [0.50, 0.30, 0.20],
        "demand_share": 0.12,
        "active_probability": 0.95,
    },
    "period_tampon": {
        "sizes": ["regular", "super", "super_plus"],
        "mix": [0.55, 0.30, 0.15],
        "demand_share": 0.08,
        "active_probability": 0.90,
    },
    "period_liner": {
        "sizes": ["one_size"],
        "mix": [1.0],
        "demand_share": 0.04,
        "active_probability": 0.80,
    },
    "period_cup": {
        "sizes": ["one_size"],
        "mix": [1.0],
        "demand_share": 0.005,
        "active_probability": 0.30,
    },
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "sample"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# 1. Partner network
# ---------------------------------------------------------

def generate_partner_master(rng):
    """
    Create the 25 synthetic partner sites.

    Each partner will receive attributes such as:
    - site ID
    - site name
    - agency type
    - demand tier
    - base weekly demand
    - product coverage
    - onboarding week
    """

    agency_types = (
        ["pantry"] * 6
        + ["shelter"] * 5
        + ["wic_clinic"] * 4
        + ["school"] * 4
        + ["health_center"] * 3
        + ["faith_community"] * 2
        + ["other"] * 1
    )

    rng.shuffle(agency_types)

    demand_tiers = ["small", "medium", "large"]

    tier_ranges = {
        "small": (400, 800),
        "medium": (800, 1500),
        "large": (1500, 2500),
    }

    partners = []

    for i in range(N_SITES):
        site_number = i + 1
        agency_type = agency_types[i]

        demand_tier = rng.choice(
            demand_tiers,
            p=[0.36, 0.44, 0.20],
        )

        low, high = tier_ranges[demand_tier]

        base_weekly_demand = int(
            rng.integers(low, high + 1)
        )

        partners.append(
            {
                "site_id": f"SITE_{site_number:03d}",
                "site_name": f"Partner Site {site_number:02d}",
                "agency_type": agency_type,
                "demand_tier": demand_tier,
                "base_weekly_demand": base_weekly_demand,
                "onboarding_week": 0,
                "has_period_products": False,
                "has_pullups": False,
                "has_adult_incontinence": False,
            }
        )

    partner_df = pd.DataFrame(partners)

    # Special onboarding cases required by the project brief
    partner_df.loc[
        partner_df["site_id"] == "SITE_024",
        "onboarding_week",
    ] = 30

    partner_df.loc[
        partner_df["site_id"] == "SITE_025",
        "onboarding_week",
    ] = 50

        # -----------------------------------------------------
    # Agency-aware product coverage
    # -----------------------------------------------------

    def select_sites_by_weight(count, agency_weights):
        """
        Select partner sites without replacement using
        agency-type-informed probabilities.

        The weights are synthetic design assumptions used
        to create more realistic product coverage patterns.
        """

        weights = (
            partner_df["agency_type"]
            .map(agency_weights)
            .fillna(1.0)
            .astype(float)
            .to_numpy()
        )

        probabilities = weights / weights.sum()

        return rng.choice(
            partner_df.index.to_numpy(),
            size=count,
            replace=False,
            p=probabilities,
        )


    period_weights = {
        "school": 2.5,
        "shelter": 2.0,
        "health_center": 1.8,
        "pantry": 1.4,
        "wic_clinic": 1.2,
        "faith_community": 1.0,
        "other": 1.0,
    }

    pullup_weights = {
        "wic_clinic": 2.5,
        "shelter": 2.0,
        "pantry": 1.6,
        "health_center": 1.2,
        "school": 1.0,
        "faith_community": 1.0,
        "other": 1.0,
    }

    adult_incontinence_weights = {
        "health_center": 3.0,
        "pantry": 1.7,
        "faith_community": 1.5,
        "other": 1.3,
        "shelter": 1.0,
        "school": 0.5,
        "wic_clinic": 0.5,
    }

    period_sites = select_sites_by_weight(
        count=10,
        agency_weights=period_weights,
    )

    pullup_sites = select_sites_by_weight(
        count=8,
        agency_weights=pullup_weights,
    )

    adult_sites = select_sites_by_weight(
        count=3,
        agency_weights=adult_incontinence_weights,
    )

    partner_df.loc[
        period_sites,
        "has_period_products",
    ] = True

    partner_df.loc[
        pullup_sites,
        "has_pullups",
    ] = True

    partner_df.loc[
        adult_sites,
        "has_adult_incontinence",
    ] = True

    return partner_df

def get_diaper_size_mix(agency_type):
    """
    Return an agency-adjusted diaper size mix.

    The network baseline peaks at sizes 4 and 5.
    Agency-type multipliers create realistic variation
    while preserving the overall network pattern.
    """

    multipliers = {
        "N": 1.0,
        "1": 1.0,
        "2": 1.0,
        "3": 1.0,
        "4": 1.0,
        "5": 1.0,
        "6": 1.0,
        "7": 1.0,
    }

    if agency_type == "shelter":
        multipliers.update({
            "N": 0.75,
            "1": 0.80,
            "2": 0.90,
            "4": 1.10,
            "5": 1.20,
            "6": 1.20,
            "7": 1.10,
        })

    elif agency_type == "wic_clinic":
        multipliers.update({
            "N": 1.50,
            "1": 1.35,
            "2": 1.20,
            "4": 0.90,
            "5": 0.80,
            "6": 0.75,
            "7": 0.70,
        })

    elif agency_type == "school":
        multipliers.update({
            "N": 0.70,
            "1": 0.80,
            "2": 0.90,
            "3": 1.05,
            "4": 1.15,
            "5": 1.15,
            "6": 1.05,
        })

    adjusted_mix = np.array(
        [
            BASE_DIAPER_MIX[size] * multipliers[size]
            for size in DIAPER_SIZES
        ],
        dtype=float,
    )

    return adjusted_mix / adjusted_mix.sum()

# ---------------------------------------------------------
# 2. Historical distributions
# ---------------------------------------------------------

def generate_product_size_quantities(
    expected_quantity,
    sizes,
    mix,
    rng,
    active_probability=1.0,
    noise_rate=0.15,
):
    """
    Generate total weekly demand for a product and split it
    across the product's sizes or variants.

    Returns a list of (size, quantity) pairs.
    """

    if rng.random() > active_probability:
        return []

    expected_quantity = max(float(expected_quantity), 0.0)

    if expected_quantity == 0:
        return []

    total_quantity = int(
        round(
            rng.normal(
                loc=expected_quantity,
                scale=max(expected_quantity * noise_rate, 1.0),
            )
        )
    )

    total_quantity = max(total_quantity, 0)

    if total_quantity == 0:
        return []

    probabilities = np.array(
        mix,
        dtype=float,
    )

    probabilities = probabilities / probabilities.sum()

    size_quantities = rng.multinomial(
        total_quantity,
        probabilities,
    )

    return [
        (size, int(quantity))
        for size, quantity in zip(
            sizes,
            size_quantities,
        )
        if quantity > 0
    ]

def generate_distribution_history(partners, rng):
    """
    Generate clean weekly multi-product distribution history.

    The history includes:
    - 78 weeks
    - agency-specific diaper size mix
    - weekly demand variability
    - mild seasonality
    - two mid-series partner starts
    - one six-week inactivity gap

    Additional product categories will be added separately.
    """

    dates = pd.date_range(
        end=HISTORY_END_DATE,
        periods=N_WEEKS,
        freq="W-MON",
    )

    rows = []

    for _, partner in partners.iterrows():

        site_id = partner["site_id"]
        agency_type = partner["agency_type"]
        onboarding_week = int(partner["onboarding_week"])
        base_demand = int(partner["base_weekly_demand"])

        size_mix = get_diaper_size_mix(agency_type)

        for week_index, date in enumerate(dates):

            # Partner has not started operating yet
            if week_index < onboarding_week:
                continue

            # Required six-week inactive gap for Site 08
            if (
                site_id == "SITE_008"
                and 35 <= week_index <= 40
            ):
                continue

            # Mild demand seasonality
            seasonal_factor = 1.0

            if date.month in [6, 7, 8]:
                seasonal_factor *= 0.95

                if agency_type == "school":
                    seasonal_factor *= 0.80

            elif date.month in [11, 12]:
                seasonal_factor *= 1.05

            expected_weekly_demand = (
                base_demand * seasonal_factor
            )

            weekly_demand = int(
                round(
                    rng.normal(
                        loc=expected_weekly_demand,
                        scale=expected_weekly_demand * 0.12,
                    )
                )
            )

            weekly_demand = max(
                weekly_demand,
                0,
            )

            if weekly_demand == 0:
                continue

            size_quantities = rng.multinomial(
                weekly_demand,
                size_mix,
            )

                        # -------------------------------------------------
            # Diapers
            # -------------------------------------------------

            for size, quantity in zip(
                DIAPER_SIZES,
                size_quantities,
            ):

                if quantity == 0:
                    continue

                children_served = max(
                    1,
                    int(
                        round(
                            quantity
                            / rng.uniform(35, 55)
                        )
                    ),
                )

                households_served = max(
                    1,
                    int(
                        round(
                            children_served
                            / rng.uniform(1.1, 1.5)
                        )
                    ),
                )

                rows.append(
                    {
                        "date": date,
                        "site_id": site_id,
                        "site_name": partner["site_name"],
                        "product": "diaper",
                        "size": size,
                        "quantity": int(quantity),
                        "households_served": households_served,
                        "children_served": children_served,
                    }
                )

            # -------------------------------------------------
            # Wipes
            # -------------------------------------------------

            wipe_rows = generate_product_size_quantities(
                expected_quantity=expected_weekly_demand * 0.50,
                sizes=["one_size"],
                mix=[1.0],
                rng=rng,
                active_probability=0.95,
                noise_rate=0.15,
            )

            for size, quantity in wipe_rows:
                rows.append(
                    {
                        "date": date,
                        "site_id": site_id,
                        "site_name": partner["site_name"],
                        "product": "wipes",
                        "size": size,
                        "quantity": quantity,
                        "households_served": None,
                        "children_served": None,
                    }
                )

            # -------------------------------------------------
            # Pull-ups
            # -------------------------------------------------

            if partner["has_pullups"]:

                pullup_rows = generate_product_size_quantities(
                    expected_quantity=expected_weekly_demand * 0.20,
                    sizes=PULLUP_SIZES,
                    mix=[
                        PULLUP_MIX[size]
                        for size in PULLUP_SIZES
                    ],
                    rng=rng,
                    active_probability=0.90,
                    noise_rate=0.18,
                )

                for size, quantity in pullup_rows:
                    rows.append(
                        {
                            "date": date,
                            "site_id": site_id,
                            "site_name": partner["site_name"],
                            "product": "pull_up",
                            "size": size,
                            "quantity": quantity,
                            "households_served": None,
                            "children_served": None,
                        }
                    )

            # -------------------------------------------------
            # Period products
            # -------------------------------------------------

            if partner["has_period_products"]:

                for product, config in PERIOD_PRODUCT_CONFIG.items():

                    period_rows = generate_product_size_quantities(
                        expected_quantity=(
                            expected_weekly_demand
                            * config["demand_share"]
                        ),
                        sizes=config["sizes"],
                        mix=config["mix"],
                        rng=rng,
                        active_probability=(
                            config["active_probability"]
                        ),
                        noise_rate=0.20,
                    )

                    for size, quantity in period_rows:
                        rows.append(
                            {
                                "date": date,
                                "site_id": site_id,
                                "site_name": partner["site_name"],
                                "product": product,
                                "size": size,
                                "quantity": quantity,
                                "households_served": None,
                                "children_served": None,
                            }
                        )

            # -------------------------------------------------
            # Adult incontinence products
            # -------------------------------------------------

            if partner["has_adult_incontinence"]:

                adult_rows = generate_product_size_quantities(
                    expected_quantity=expected_weekly_demand * 0.12,
                    sizes=ADULT_INCONTINENCE_SIZES,
                    mix=[
                        ADULT_INCONTINENCE_MIX[size]
                        for size in ADULT_INCONTINENCE_SIZES
                    ],
                    rng=rng,
                    active_probability=0.85,
                    noise_rate=0.20,
                )

                for size, quantity in adult_rows:
                    rows.append(
                        {
                            "date": date,
                            "site_id": site_id,
                            "site_name": partner["site_name"],
                            "product": "adult_incontinence",
                            "size": size,
                            "quantity": quantity,
                            "households_served": None,
                            "children_served": None,
                        }
                    )

    distribution_df = pd.DataFrame(rows)

    return distribution_df


# ---------------------------------------------------------
# 3. Partner survey
# ---------------------------------------------------------

def generate_partner_survey(partners, rng):
    """
    Generate one completed synthetic intake-survey record
    for each partner site.

    Survey values are linked to partner operating profiles
    rather than generated independently at random.
    """

    children_share_by_agency = {
        "pantry": 0.45,
        "shelter": 0.55,
        "wic_clinic": 0.85,
        "school": 0.25,
        "health_center": 0.50,
        "faith_community": 0.35,
        "other": 0.40,
    }

    menstruating_share_by_agency = {
        "pantry": 0.60,
        "shelter": 0.70,
        "wic_clinic": 0.50,
        "school": 0.90,
        "health_center": 0.70,
        "faith_community": 0.55,
        "other": 0.60,
    }

    poverty_probabilities = {
        "pantry": [0.05, 0.15, 0.40, 0.40],
        "shelter": [0.00, 0.05, 0.25, 0.70],
        "wic_clinic": [0.00, 0.05, 0.35, 0.60],
        "school": [0.05, 0.25, 0.50, 0.20],
        "health_center": [0.05, 0.15, 0.40, 0.40],
        "faith_community": [0.05, 0.25, 0.40, 0.30],
        "other": [0.10, 0.25, 0.40, 0.25],
    }

    poverty_bands = [
        "under_25_percent",
        "25_to_50_percent",
        "50_to_75_percent",
        "over_75_percent",
    ]

    storage_ranges = {
        "small": (30, 70),
        "medium": (70, 150),
        "large": (150, 300),
    }

    distribution_frequency_probs = {
        "pantry": [0.50, 0.30, 0.20],
        "shelter": [0.70, 0.25, 0.05],
        "wic_clinic": [0.20, 0.50, 0.30],
        "school": [0.20, 0.45, 0.35],
        "health_center": [0.40, 0.40, 0.20],
        "faith_community": [0.25, 0.35, 0.40],
        "other": [0.30, 0.40, 0.30],
    }

    distribution_frequencies = [
        "weekly",
        "biweekly",
        "monthly",
    ]

    rows = []

    for _, partner in partners.iterrows():

        agency_type = partner["agency_type"]
        demand_tier = partner["demand_tier"]
        base_weekly_demand = int(
            partner["base_weekly_demand"]
        )

        site_number = int(
            partner["site_id"].split("_")[-1]
        )

        # Approximate monthly families served from
        # weekly product demand.
        units_per_family = rng.uniform(35, 55)

        families_served = max(
            10,
            int(
                round(
                    base_weekly_demand
                    * 4.33
                    / units_per_family
                )
            ),
        )

        children_share = (
            children_share_by_agency[agency_type]
            * rng.uniform(0.90, 1.10)
        )

        children_under_4 = max(
            0,
            int(
                round(
                    families_served
                    * children_share
                )
            ),
        )

        menstruating_share = (
            menstruating_share_by_agency[agency_type]
            * rng.uniform(0.85, 1.15)
        )

        if partner["has_period_products"]:
            menstruating_share *= 1.10

        menstruating_clients = max(
            0,
            int(
                round(
                    families_served
                    * menstruating_share
                )
            ),
        )

        poverty_share_band = rng.choice(
            poverty_bands,
            p=poverty_probabilities[agency_type],
        )

        # ---------------------------------------------
        # Priority-population flags
        # ---------------------------------------------

        priority_flags = []

        if agency_type == "shelter":
            priority_flags.append(
                "emergency_shelter"
            )

            if rng.random() < 0.30:
                priority_flags.append(
                    "domestic_violence_program"
                )

        if agency_type == "school":
            priority_flags.append(
                "students"
            )

        if (
            agency_type == "wic_clinic"
            and rng.random() < 0.30
        ):
            priority_flags.append(
                "teen_parents"
            )

        if (
            agency_type
            in {"pantry", "faith_community", "other"}
            and rng.random() < 0.25
        ):
            priority_flags.append(
                "refugee_or_newly_arrived_families"
            )

        if (
            agency_type
            in {"health_center", "wic_clinic"}
            and rng.random() < 0.20
        ):
            priority_flags.append(
                "families_with_child_with_disability"
            )

        if not priority_flags:
            priority_flags.append("none")

        # ---------------------------------------------
        # Storage capacity
        # ---------------------------------------------

        storage_low, storage_high = (
            storage_ranges[demand_tier]
        )

        storage_capacity_cases = int(
            rng.integers(
                storage_low,
                storage_high + 1,
            )
        )

        # ---------------------------------------------
        # Distribution frequency
        # ---------------------------------------------

        distribution_frequency = rng.choice(
            distribution_frequencies,
            p=distribution_frequency_probs[
                agency_type
            ],
        )

        # ---------------------------------------------
        # Recent stockouts
        # ---------------------------------------------

        if rng.random() < 0.75:

            stockout_count = int(
                rng.choice(
                    [1, 2],
                    p=[0.70, 0.30],
                )
            )

            stockout_sizes = rng.choice(
                ["4", "5", "6"],
                size=stockout_count,
                replace=False,
                p=[0.25, 0.50, 0.25],
            )

            recent_stockout_sizes = ";".join(
                stockout_sizes.tolist()
            )

        else:
            recent_stockout_sizes = "none"

        # ---------------------------------------------
        # Languages
        # ---------------------------------------------

        languages = ["English"]

        optional_languages = {
            "Spanish": 0.55,
            "Arabic": 0.12,
            "French": 0.10,
            "Vietnamese": 0.08,
        }

        for language, probability in (
            optional_languages.items()
        ):
            if rng.random() < probability:
                languages.append(language)

        rows.append(
            {
                "site_name": partner["site_name"],
                "zip_code": f"606{site_number:02d}",
                "agency_type": agency_type,
                "families_served_per_month": families_served,
                "children_under_4_per_month": children_under_4,
                "menstruating_clients_per_month": (
                    menstruating_clients
                ),
                "poverty_share_band": poverty_share_band,
                "priority_population_flags": ";".join(
                    priority_flags
                ),
                "storage_capacity_cases": (
                    storage_capacity_cases
                ),
                "distribution_frequency": (
                    distribution_frequency
                ),
                "recent_stockout_sizes": (
                    recent_stockout_sizes
                ),
                "preferred_contact": (
                    f"site{site_number:02d}@example.org"
                ),
                "languages_spoken": ";".join(
                    languages
                ),
            }
        )

    survey_df = pd.DataFrame(rows)

    return survey_df


# ---------------------------------------------------------
# 4. Current inventory
# ---------------------------------------------------------

def generate_current_inventory(distribution_df, rng):
    """
    Generate the current network inventory snapshot from
    recent simulated demand.

    Diaper inventory is intentionally designed to contain
    long and short size positions for later alert testing.
    """

    recent_dates = sorted(
        distribution_df["date"].unique()
    )[-8:]

    recent_distribution = distribution_df.loc[
        distribution_df["date"].isin(recent_dates)
    ]

    average_weekly_demand = (
        recent_distribution
        .groupby(["product", "size"])["quantity"]
        .sum()
        .div(len(recent_dates))
        .reset_index(name="avg_weekly_demand")
    )

    diaper_target_wos = {
        "N": 16.0,
        "1": 15.0,
        "2": 13.0,
        "3": 7.0,
        "4": 4.0,
        "5": 1.8,
        "6": 2.2,
        "7": 5.0,
    }

    other_product_target_wos = {
        "wipes": 6.0,
        "pull_up": 5.0,
        "period_pad": 5.0,
        "period_tampon": 5.0,
        "period_liner": 6.0,
        "period_cup": 8.0,
        "adult_incontinence": 5.0,
    }

    rows = []

    for _, record in average_weekly_demand.iterrows():

        product = record["product"]
        size = record["size"]
        weekly_demand = float(
            record["avg_weekly_demand"]
        )

        if product == "diaper":
            target_wos = diaper_target_wos[size]
        else:
            target_wos = other_product_target_wos[
                product
            ]

        # Small deterministic variation keeps inventory
        # from looking artificially exact.
        inventory_noise = rng.uniform(
            0.97,
            1.03,
        )

        quantity_on_hand = int(
            round(
                weekly_demand
                * target_wos
                * inventory_noise
            )
        )

        quantity_on_hand = max(
            quantity_on_hand,
            0,
        )

        rows.append(
            {
                "as_of_date": HISTORY_END_DATE,
                "product": product,
                "size": size,
                "quantity_on_hand": quantity_on_hand,
                "location": "Main Warehouse",
            }
        )

    inventory_df = pd.DataFrame(rows)

    return inventory_df


# ---------------------------------------------------------
# 5. Incoming donations and purchases
# ---------------------------------------------------------

def generate_incoming_supply(distribution_df, rng):
    """
    Generate 52 weeks of future synthetic inbound supply.

    The schedule includes:
    - diaper donations biased toward N, 1, and 2
    - one holiday donation drive
    - one spring donation drive
    - a summer donation trough
    - targeted diaper purchases
    - recurring purchases for other product categories
    - both confirmed and pending records
    """

    future_dates = pd.date_range(
        start=HISTORY_END_DATE + pd.DateOffset(weeks=1),
        periods=INCOMING_HORIZON_WEEKS,
        freq="W-MON",
    )

    recent_dates = sorted(
        distribution_df["date"].unique()
    )[-8:]

    recent_distribution = distribution_df.loc[
        distribution_df["date"].isin(recent_dates)
    ]

    average_weekly_demand = (
        recent_distribution
        .groupby(["product", "size"])["quantity"]
        .sum()
        .div(len(recent_dates))
        .reset_index(name="avg_weekly_demand")
    )

    diaper_demand = average_weekly_demand.loc[
        average_weekly_demand["product"] == "diaper"
    ]

    total_weekly_diaper_demand = (
        diaper_demand["avg_weekly_demand"].sum()
    )

    diaper_demand_by_size = (
        diaper_demand
        .set_index("size")["avg_weekly_demand"]
        .to_dict()
    )

    donation_probabilities = np.array(
        [
            DONATION_DIAPER_MIX[size]
            for size in DIAPER_SIZES
        ],
        dtype=float,
    )

    donation_probabilities = (
        donation_probabilities
        / donation_probabilities.sum()
    )

    # Donation volume intentionally covers only part of
    # network demand.
    base_weekly_donation = (
        total_weekly_diaper_demand * 0.45
    )

    spring_drive_date = next(
        date
        for date in future_dates
        if date.month == 4
    )

    holiday_drive_date = next(
        date
        for date in future_dates
        if date.month == 12
    )

    rows = []

    for week_index, date in enumerate(future_dates):

        seasonal_factor = 1.0
        drive_factor = 1.0
        source = "Community Donations"

        if date.month in [6, 7, 8]:
            seasonal_factor = 0.65

        if date == spring_drive_date:
            drive_factor = 2.0
            source = "Spring Donation Drive"

        elif date == holiday_drive_date:
            drive_factor = 2.3
            source = "Holiday Donation Drive"

        expected_donation = (
            base_weekly_donation
            * seasonal_factor
            * drive_factor
        )

        total_donation = int(
            round(
                rng.normal(
                    loc=expected_donation,
                    scale=max(
                        expected_donation * 0.10,
                        1.0,
                    ),
                )
            )
        )

        total_donation = max(
            total_donation,
            0,
        )

        donation_quantities = rng.multinomial(
            total_donation,
            donation_probabilities,
        )

        # Supply closer to the current date is more likely
        # to be confirmed.
        confirmed_probability = (
            0.85
            if week_index < 8
            else 0.60
        )

        for size, quantity in zip(
            DIAPER_SIZES,
            donation_quantities,
        ):

            if quantity == 0:
                continue

            status = rng.choice(
                ["confirmed", "pending"],
                p=[
                    confirmed_probability,
                    1 - confirmed_probability,
                ],
            )

            rows.append(
                {
                    "expected_date": date,
                    "source": source,
                    "product": "diaper",
                    "size": size,
                    "quantity": int(quantity),
                    "status": status,
                }
            )

        # -------------------------------------------------
        # Targeted diaper purchases every four weeks
        # -------------------------------------------------

        if week_index % 4 == 0:

            for size in ["4", "5", "6"]:

                weekly_size_demand = (
                    diaper_demand_by_size.get(
                        size,
                        0.0,
                    )
                )

                purchase_quantity = int(
                    round(
                        weekly_size_demand
                        * rng.uniform(
                            1.5,
                            2.0,
                        )
                    )
                )

                if purchase_quantity <= 0:
                    continue

                rows.append(
                    {
                        "expected_date": date,
                        "source": "Targeted Diaper Purchase",
                        "product": "diaper",
                        "size": size,
                        "quantity": purchase_quantity,
                        "status": rng.choice(
                            ["confirmed", "pending"],
                            p=[0.75, 0.25],
                        ),
                    }
                )

        # -------------------------------------------------
        # Other-product purchases every four weeks
        # -------------------------------------------------

        if week_index % 4 == 0:

            other_products = average_weekly_demand.loc[
                average_weekly_demand["product"]
                != "diaper"
            ]

            for _, record in other_products.iterrows():

                expected_quantity = (
                    float(
                        record["avg_weekly_demand"]
                    )
                    * rng.uniform(
                        1.5,
                        2.5,
                    )
                )

                quantity = int(
                    round(expected_quantity)
                )

                if quantity <= 0:
                    continue

                rows.append(
                    {
                        "expected_date": date,
                        "source": "Planned Purchase",
                        "product": record["product"],
                        "size": record["size"],
                        "quantity": quantity,
                        "status": rng.choice(
                            ["confirmed", "pending"],
                            p=[0.70, 0.30],
                        ),
                    }
                )

    incoming_supply_df = pd.DataFrame(rows)

    return incoming_supply_df


# ---------------------------------------------------------
# 6. Deliberately messy validation data
# ---------------------------------------------------------

def inject_messy_distribution_rows(distribution_df, rng):
    """
    Create a validation copy of the distribution log with
    approximately 3% deliberately planted data-quality issues.

    The clean source dataframe is never modified.

    Planted issues include:
    - non-standard size labels
    - inconsistent product capitalization / whitespace
    - pack-based quantity representations
    """

    messy_df = distribution_df.copy(deep=True)

    total_rows = len(messy_df)

    if total_rows == 0:
        return messy_df

    n_messy_rows = max(
        1,
        int(round(total_rows * MESSY_ROW_RATE)),
    )

    messy_indices = rng.choice(
        messy_df.index.to_numpy(),
        size=n_messy_rows,
        replace=False,
    )

    # Split the selected rows across three issue types.
    issue_groups = np.array_split(
        messy_indices,
        3,
    )

    size_indices = issue_groups[0]
    product_indices = issue_groups[1]
    quantity_indices = issue_groups[2]

    # Quantity must temporarily support both numeric values
    # and deliberately messy string representations.
    messy_df["quantity"] = (
        messy_df["quantity"].astype(object)
    )

    # -----------------------------------------------------
    # 1. Non-standard size labels
    # -----------------------------------------------------

    for row_index in size_indices:

        original_size = str(
            messy_df.at[row_index, "size"]
        )

        product = messy_df.at[
            row_index,
            "product",
        ]

        if product == "diaper":

            if original_size == "N":
                messy_size = " newborn "
            else:
                messy_size = (
                    f"SIZE{original_size}"
                )

        else:

            variation = int(
                rng.integers(0, 2)
            )

            if variation == 0:
                messy_size = (
                    original_size.upper()
                )
            else:
                messy_size = (
                    f" {original_size} "
                )

        messy_df.at[
            row_index,
            "size",
        ] = messy_size

    # -----------------------------------------------------
    # 2. Product capitalization / whitespace
    # -----------------------------------------------------

    for row_index in product_indices:

        original_product = str(
            messy_df.at[
                row_index,
                "product",
            ]
        )

        variation = int(
            rng.integers(0, 3)
        )

        if variation == 0:
            messy_product = (
                original_product.upper()
            )

        elif variation == 1:
            messy_product = (
                original_product.title()
            )

        else:
            messy_product = (
                f" {original_product} "
            )

        messy_df.at[
            row_index,
            "product",
        ] = messy_product

    # -----------------------------------------------------
    # 3. Pack-based quantity representations
    # -----------------------------------------------------

    candidate_pack_sizes = [
        10,
        20,
        25,
        50,
    ]

    for row_index in quantity_indices:

        original_quantity = int(
            messy_df.at[
                row_index,
                "quantity",
            ]
        )

        valid_pack_sizes = [
            pack_size
            for pack_size
            in candidate_pack_sizes
            if (
                original_quantity
                % pack_size
                == 0
            )
        ]

        if valid_pack_sizes:

            pack_size = int(
                rng.choice(
                    valid_pack_sizes
                )
            )

            number_of_packs = (
                original_quantity
                // pack_size
            )

        else:

            # Preserve the exact original quantity even
            # when it does not divide evenly into a
            # realistic standard pack size.
            pack_size = original_quantity
            number_of_packs = 1

        messy_quantity = (
            f"{number_of_packs} packs x "
            f"{pack_size} units"
        )

        messy_df.at[
            row_index,
            "quantity",
        ] = messy_quantity

    return messy_df


# ---------------------------------------------------------
# 7. Validation
# ---------------------------------------------------------

def validate_synthetic_data(
    partners,
    distribution_df,
    inventory_df,
    incoming_supply_df,
    survey_df,
):
    """
    Verify that the generated data satisfies the synthetic
    data specification before files are saved.
    """
    pass


# ---------------------------------------------------------
# 8. Save outputs
# ---------------------------------------------------------

def save_outputs(
    distribution_df,
    messy_distribution_df,
    inventory_df,
    incoming_supply_df,
    survey_df,
):
    """
    Save generated datasets to data/sample/.
    """
    pass


# ---------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------

def main():
    rng = np.random.default_rng(SEED)

    partners = generate_partner_master(rng)

    distribution_df = generate_distribution_history(
        partners,
        rng,
    )

    survey_df = generate_partner_survey(
        partners,
        rng,
    )

    inventory_df = generate_current_inventory(
        distribution_df,
        rng,
    )

    incoming_supply_df = generate_incoming_supply(
    distribution_df,
    rng,
)

    messy_distribution_df = inject_messy_distribution_rows(
        distribution_df,
        rng,
    )

    validate_synthetic_data(
        partners,
        distribution_df,
        inventory_df,
        incoming_supply_df,
        survey_df,
    )

    save_outputs(
        distribution_df,
        messy_distribution_df,
        inventory_df,
        incoming_supply_df,
        survey_df,
    )


if __name__ == "__main__":
    main()