from pathlib import Path

import pandas as pd


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "src" / "templates"

TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# 1. Distribution Log
# ---------------------------------------------------------

distribution_log_columns = [
    "date",
    "site_id",
    "site_name",
    "product",
    "size",
    "quantity",
    "households_served",
    "children_served",
]


# ---------------------------------------------------------
# 2. Current Inventory
# ---------------------------------------------------------

current_inventory_columns = [
    "as_of_date",
    "product",
    "size",
    "quantity_on_hand",
    "location",
]


# ---------------------------------------------------------
# 3. Incoming Donations and Purchases
# ---------------------------------------------------------

incoming_supply_columns = [
    "expected_date",
    "source",
    "product",
    "size",
    "quantity",
    "status",
]


# ---------------------------------------------------------
# 4. Partner Intake Survey
# ---------------------------------------------------------

partner_survey_columns = [
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


# ---------------------------------------------------------
# Template definitions
# ---------------------------------------------------------

templates = {
    "distribution_log_template": distribution_log_columns,
    "current_inventory_template": current_inventory_columns,
    "incoming_supply_template": incoming_supply_columns,
    "partner_survey_template": partner_survey_columns,
}


# ---------------------------------------------------------
# Generate CSV and XLSX templates
# ---------------------------------------------------------

for template_name, columns in templates.items():

    df = pd.DataFrame(columns=columns)

    csv_path = TEMPLATE_DIR / f"{template_name}.csv"
    xlsx_path = TEMPLATE_DIR / f"{template_name}.xlsx"

    df.to_csv(csv_path, index=False)
    df.to_excel(xlsx_path, index=False)

    print(f"Created: {csv_path.name}")
    print(f"Created: {xlsx_path.name}")


print("\nAll templates created successfully.")