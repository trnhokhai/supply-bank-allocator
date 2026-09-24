from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "src" / "templates"


EXPECTED_COLUMNS = {
    "distribution_log_template": [
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
        "households_served",
        "children_served",
    ],
    "current_inventory_template": [
        "as_of_date",
        "product",
        "size",
        "quantity_on_hand",
        "location",
    ],
    "incoming_supply_template": [
        "expected_date",
        "source",
        "product",
        "size",
        "quantity",
        "status",
    ],
    "partner_survey_template": [
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
    ],
}


def test_all_template_files_exist():
    for template_name in EXPECTED_COLUMNS:
        assert (TEMPLATE_DIR / f"{template_name}.csv").exists()
        assert (TEMPLATE_DIR / f"{template_name}.xlsx").exists()


def test_csv_template_headers():
    for template_name, expected_columns in EXPECTED_COLUMNS.items():
        df = pd.read_csv(TEMPLATE_DIR / f"{template_name}.csv")
        assert list(df.columns) == expected_columns


def test_xlsx_template_headers():
    for template_name, expected_columns in EXPECTED_COLUMNS.items():
        df = pd.read_excel(TEMPLATE_DIR / f"{template_name}.xlsx")
        assert list(df.columns) == expected_columns