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
    """
    pass


# ---------------------------------------------------------
# 4. Current inventory
# ---------------------------------------------------------

def generate_current_inventory(distribution_df, rng):
    """
    Generate the current inventory snapshot.

    Inventory will intentionally create:
    - long positions in N, 1, and 2
    - short positions in 5 and 6
    """
    pass


# ---------------------------------------------------------
# 5. Incoming donations and purchases
# ---------------------------------------------------------

def generate_incoming_supply(rng):
    """
    Generate future inbound supply.

    Donation behavior should include:
    - bias toward N, 1, and 2
    - confirmed and pending records
    - spring and holiday donation-drive effects
    - summer donation trough
    """
    pass


# ---------------------------------------------------------
# 6. Deliberately messy validation data
# ---------------------------------------------------------

def inject_messy_distribution_rows(distribution_df, rng):
    """
    Create a validation version of the distribution log
    with approximately 3% planted data-quality issues.

    Examples:
    - SIZE5
    - size 5
    - trailing whitespace
    - pack quantities
    """
    pass


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