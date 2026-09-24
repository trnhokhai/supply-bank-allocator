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


# ---------------------------------------------------------
# 2. Historical distributions
# ---------------------------------------------------------

def generate_distribution_history(partners, rng):
    """
    Generate 78 weeks of clean historical distribution data.

    The distribution history should reflect:
    - partner demand scale
    - agency-specific diaper size mix
    - product coverage
    - weekly variability
    - intermittent demand
    - two mid-series partner starts
    - one six-week activity gap
    """
    pass


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