from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

from src.ingest import (
    HeaderMappingError,
    NormalizationError,
    QuantityParseError,
    apply_header_mapping,
    normalize_product,
    normalize_size,
    parse_quantity_to_units,
    suggest_header_mapping,
)


def test_parse_integer_quantity():
    assert parse_quantity_to_units(300) == 300


def test_parse_whole_float_quantity():
    assert parse_quantity_to_units(300.0) == 300


def test_parse_numeric_string_quantity():
    assert parse_quantity_to_units("300") == 300


def test_parse_units_string_quantity():
    assert parse_quantity_to_units("300 units") == 300


def test_parse_pack_quantity():
    assert parse_quantity_to_units("12 packs x 25 units") == 300


def test_parse_singular_pack_quantity():
    assert parse_quantity_to_units("1 pack x 25 units") == 25


def test_reject_fractional_quantity():
    with pytest.raises(QuantityParseError):
        parse_quantity_to_units(300.5)


def test_reject_negative_quantity():
    with pytest.raises(QuantityParseError):
        parse_quantity_to_units(-10)


def test_reject_pack_without_pack_size():
    with pytest.raises(QuantityParseError):
        parse_quantity_to_units("12 packs")


def test_reject_ambiguous_quantity_text():
    with pytest.raises(QuantityParseError):
        parse_quantity_to_units("about 300")

def test_messy_sample_quantities_match_clean_ground_truth():
    clean_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    )

    messy_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_messy.csv"
    )

    parsed_quantities = messy_df["quantity"].map(
        parse_quantity_to_units
    )

    expected_quantities = clean_df["quantity"].astype(int)

    pd.testing.assert_series_equal(
        parsed_quantities.reset_index(drop=True),
        expected_quantities.reset_index(drop=True),
        check_names=False,
    )

def test_normalize_product_variants():
    assert normalize_product("DIAPER") == "diaper"
    assert normalize_product(" diaper ") == "diaper"
    assert normalize_product("Period_Pad") == "period_pad"
    assert normalize_product("PULL_UP") == "pull_up"


def test_reject_unknown_product():
    with pytest.raises(NormalizationError):
        normalize_product("baby_supply")


def test_normalize_diaper_sizes():
    assert normalize_size("diaper", " newborn ") == "N"
    assert normalize_size("diaper", "N") == "N"
    assert normalize_size("diaper", "SIZE5") == "5"
    assert normalize_size("diaper", " 6 ") == "6"


def test_normalize_pull_up_sizes():
    assert normalize_size("pull_up", "2t-3t") == "2T-3T"
    assert normalize_size("pull_up", " 3T-4T ") == "3T-4T"


def test_normalize_period_product_sizes():
    assert normalize_size("period_pad", "REGULAR") == "regular"
    assert normalize_size("period_pad", " overnight ") == "overnight"
    assert normalize_size("period_tampon", "SUPER_PLUS") == "super_plus"


def test_normalize_adult_incontinence_sizes():
    assert normalize_size("adult_incontinence", " l ") == "L"
    assert normalize_size("adult_incontinence", "xl") == "XL"


def test_normalize_one_size_products():
    assert normalize_size("wipes", "ONE_SIZE") == "one_size"
    assert normalize_size("period_liner", " one_size ") == "one_size"
    assert normalize_size("period_cup", "one size") == "one_size"


def test_reject_size_not_valid_for_product():
    with pytest.raises(NormalizationError):
        normalize_size("diaper", "XL")

    with pytest.raises(NormalizationError):
        normalize_size("period_pad", "5")


def test_messy_sample_products_and_sizes_match_clean_ground_truth():
    clean_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    )

    messy_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_messy.csv"
    )

    normalized_products = messy_df["product"].map(
        normalize_product
    )

    normalized_sizes = pd.Series(
        [
            normalize_size(product, size)
            for product, size in zip(
                normalized_products,
                messy_df["size"],
            )
        ],
        index=messy_df.index,
    )

    pd.testing.assert_series_equal(
        normalized_products.reset_index(drop=True),
        clean_df["product"].reset_index(drop=True),
        check_names=False,
    )

    pd.testing.assert_series_equal(
        normalized_sizes.reset_index(drop=True),
        clean_df["size"].astype(str).reset_index(drop=True),
        check_names=False,
    )

def test_exact_canonical_distribution_headers_map_to_themselves():
    headers = [
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
        "households_served",
        "children_served",
    ]

    mapping = suggest_header_mapping(
        headers,
        dataset_type="distribution_log",
    )

    assert mapping == {
        header: header
        for header in headers
    }


def test_alternate_distribution_headers_map_automatically():
    alternate_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_alternate_headers.csv",
        nrows=0,
    )

    mapping = suggest_header_mapping(
        alternate_df.columns.tolist(),
        dataset_type="distribution_log",
    )

    assert mapping == {
        "Distribution Date": "date",
        "Site ID": "site_id",
        "Partner": "site_name",
        "Product Category": "product",
        "Product Size": "size",
        "Qty": "quantity",
        "Households": "households_served",
        "Children": "children_served",
    }


def test_fuzzy_header_mapping_handles_minor_typos():
    mapping = suggest_header_mapping(
        [
            "Distribtion Date",
            "Quantty",
        ],
        dataset_type="distribution_log",
    )

    assert mapping["Distribtion Date"] == "date"
    assert mapping["Quantty"] == "quantity"


def test_unknown_header_remains_unmapped():
    mapping = suggest_header_mapping(
        [
            "Mystery Column",
        ],
        dataset_type="distribution_log",
    )

    assert mapping["Mystery Column"] is None


def test_header_mapping_does_not_assign_same_target_twice():
    mapping = suggest_header_mapping(
        [
            "Partner",
            "Site Name",
        ],
        dataset_type="distribution_log",
    )

    mapped_targets = [
        target
        for target in mapping.values()
        if target is not None
    ]

    assert mapped_targets.count("site_name") == 1


def test_reject_unknown_dataset_type():
    with pytest.raises(HeaderMappingError):
        suggest_header_mapping(
            ["date"],
            dataset_type="unknown_dataset",
        )

def test_apply_alternate_header_mapping_restores_canonical_distribution_table():
    clean_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_clean.csv"
    )

    alternate_df = pd.read_csv(
        SAMPLE_DIR / "distribution_log_alternate_headers.csv"
    )

    mapping = suggest_header_mapping(
        alternate_df.columns.tolist(),
        dataset_type="distribution_log",
    )

    mapped_df = apply_header_mapping(
        alternate_df,
        mapping,
        dataset_type="distribution_log",
    )

    assert list(mapped_df.columns) == list(clean_df.columns)

    pd.testing.assert_frame_equal(
        mapped_df.reset_index(drop=True),
        clean_df.reset_index(drop=True),
    )


def test_apply_header_mapping_preserves_unmapped_extra_columns():
    df = pd.DataFrame(
        {
            "Distribution Date": ["2026-01-01"],
            "Qty": [100],
            "Notes": ["Emergency distribution"],
        }
    )

    mapping = {
        "Distribution Date": "date",
        "Qty": "quantity",
        "Notes": None,
    }

    mapped_df = apply_header_mapping(
        df,
        mapping,
        dataset_type="distribution_log",
    )

    assert list(mapped_df.columns) == [
        "date",
        "quantity",
        "Notes",
    ]


def test_apply_header_mapping_rejects_duplicate_targets():
    df = pd.DataFrame(
        {
            "Partner": ["Site A"],
            "Site Name": ["Site A"],
        }
    )

    mapping = {
        "Partner": "site_name",
        "Site Name": "site_name",
    }

    with pytest.raises(HeaderMappingError):
        apply_header_mapping(
            df,
            mapping,
            dataset_type="distribution_log",
        )


def test_apply_header_mapping_rejects_invalid_target():
    df = pd.DataFrame(
        {
            "Qty": [100],
        }
    )

    mapping = {
        "Qty": "made_up_column",
    }

    with pytest.raises(HeaderMappingError):
        apply_header_mapping(
            df,
            mapping,
            dataset_type="distribution_log",
        )