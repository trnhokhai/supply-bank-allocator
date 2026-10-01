from pathlib import Path

import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = PROJECT_ROOT / "data" / "sample"

from src.ingest import QuantityParseError, parse_quantity_to_units


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