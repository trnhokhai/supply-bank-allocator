from io import BytesIO
from pathlib import Path
import time

import pandas as pd
import pytest

from src.file_io import (
    FileReadError,
    load_demo_inputs,
    read_table,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

SAMPLE_DIR = (
    PROJECT_ROOT
    / "data"
    / "sample"
)


def test_read_csv_from_path():
    dataframe = read_table(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    assert not dataframe.empty

    assert {
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
    }.issubset(
        dataframe.columns
    )


def test_read_xlsx_from_path():
    dataframe = read_table(
        SAMPLE_DIR
        / "distribution_log_clean.xlsx"
    )

    assert not dataframe.empty

    assert {
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
    }.issubset(
        dataframe.columns
    )


def test_read_uploaded_csv_file_like_object():
    uploaded = BytesIO(
        (
            "date,site_name,product,size,quantity\n"
            "2026-01-05,Site A,diaper,4,100\n"
        ).encode("utf-8")
    )

    dataframe = read_table(
        uploaded,
        filename="uploaded_distribution.csv",
    )

    assert len(dataframe) == 1

    assert (
        dataframe.loc[
            0,
            "site_name",
        ]
        == "Site A"
    )


def test_read_uploaded_xlsx_file_like_object():
    source_dataframe = pd.DataFrame(
        {
            "product": [
                "diaper",
            ],
            "size": [
                "4",
            ],
            "quantity_on_hand": [
                100,
            ],
        }
    )

    uploaded = BytesIO()

    source_dataframe.to_excel(
        uploaded,
        index=False,
        engine="openpyxl",
    )

    dataframe = read_table(
        uploaded,
        filename="inventory.xlsx",
    )

    assert len(dataframe) == 1

    assert (
        dataframe.loc[
            0,
            "quantity_on_hand",
        ]
        == 100
    )


def test_unsupported_file_type_is_rejected():
    uploaded = BytesIO(
        b"not relevant"
    )

    with pytest.raises(
        FileReadError,
        match="Unsupported file type",
    ):
        read_table(
            uploaded,
            filename="data.txt",
        )


def test_malformed_xlsx_has_friendly_error():
    uploaded = BytesIO(
        b"this is not really an xlsx workbook"
    )

    with pytest.raises(
        FileReadError,
        match="Could not read",
    ):
        read_table(
            uploaded,
            filename="broken.xlsx",
        )


def test_demo_mode_loads_all_four_inputs():
    demo = load_demo_inputs()

    assert set(
        demo
    ) == {
        "distribution_log",
        "current_inventory",
        "incoming_supply",
        "partner_survey",
    }

    assert all(
        not dataframe.empty
        for dataframe in demo.values()
    )


def test_demo_mode_uses_messy_distribution_sample():
    demo = load_demo_inputs()

    clean_distribution = (
        pd.read_csv(
            SAMPLE_DIR
            / "distribution_log_clean.csv"
        )
    )

    demo_distribution = (
        demo[
            "distribution_log"
        ]
    )

    assert (
        len(demo_distribution)
        == len(clean_distribution)
    )

    assert not (
        demo_distribution
        .equals(
            clean_distribution
        )
    )


def test_demo_mode_loads_under_five_seconds():
    start = time.perf_counter()

    demo = load_demo_inputs()

    elapsed = (
        time.perf_counter()
        - start
    )

    assert len(demo) == 4

    assert elapsed < 5.0