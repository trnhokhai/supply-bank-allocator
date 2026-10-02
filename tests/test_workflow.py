from pathlib import Path

import pandas as pd
import pytest

from src.ingest import (
    suggest_header_mapping,
)
from src.workflow import (
    WorkflowError,
    build_derived_outputs,
    prepare_input,
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


def test_alternate_headers_flow_through_cleaning():
    alternate = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_alternate_headers.csv"
    )

    clean = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    mapping = suggest_header_mapping(
        alternate.columns,
        dataset_type="distribution_log",
    )

    result = prepare_input(
        alternate,
        mapping,
        dataset_type="distribution_log",
    )

    expected_mapping = (
        suggest_header_mapping(
            clean.columns,
            dataset_type="distribution_log",
        )
    )

    expected = prepare_input(
        clean,
        expected_mapping,
        dataset_type="distribution_log",
    )

    pd.testing.assert_frame_equal(
        result.cleaning_result.dataframe
        .reset_index(drop=True),
        expected.cleaning_result.dataframe
        .reset_index(drop=True),
    )


def test_messy_distribution_produces_corrections():
    dataframe = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    )

    mapping = suggest_header_mapping(
        dataframe.columns,
        dataset_type="distribution_log",
    )

    result = prepare_input(
        dataframe,
        mapping,
        dataset_type="distribution_log",
    )

    assert (
        result.cleaning_result
        .report
        .corrected_rows
        > 0
    )


def test_missing_required_mapping_has_friendly_error():
    dataframe = pd.DataFrame(
        {
            "Partner": [
                "Site A",
            ],
            "Product": [
                "diaper",
            ],
            "Size": [
                "4",
            ],
        }
    )

    mapping = suggest_header_mapping(
        dataframe.columns,
        dataset_type="distribution_log",
    )

    with pytest.raises(
        WorkflowError,
        match="quantity",
    ):
        prepare_input(
            dataframe,
            mapping,
            dataset_type="distribution_log",
        )


def test_inventory_flows_through_workflow():
    dataframe = pd.read_csv(
        SAMPLE_DIR
        / "current_inventory.csv"
    )

    mapping = suggest_header_mapping(
        dataframe.columns,
        dataset_type="current_inventory",
    )

    result = prepare_input(
        dataframe,
        mapping,
        dataset_type="current_inventory",
    )

    assert (
        len(
            result.cleaning_result.dataframe
        )
        == len(dataframe)
    )


def test_unknown_dataset_type_is_rejected():
    dataframe = pd.DataFrame(
        {
            "example": [1],
        }
    )

    with pytest.raises(
        WorkflowError
    ):
        prepare_input(
            dataframe,
            {"example": None},
            dataset_type="unknown",
        )

def test_build_derived_outputs_from_demo_inputs():
    distribution = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    survey = pd.read_csv(
        SAMPLE_DIR
        / "partner_survey.csv"
    )

    distribution_mapping = (
        suggest_header_mapping(
            distribution.columns,
            dataset_type="distribution_log",
        )
    )

    survey_mapping = (
        suggest_header_mapping(
            survey.columns,
            dataset_type="partner_survey",
        )
    )

    prepared = {
        "distribution_log": prepare_input(
            distribution,
            distribution_mapping,
            dataset_type="distribution_log",
        ),
        "partner_survey": prepare_input(
            survey,
            survey_mapping,
            dataset_type="partner_survey",
        ),
    }

    outputs = build_derived_outputs(
        prepared
    )

    assert not (
        outputs.weekly_distribution.empty
    )

    assert len(
        outputs.site_master
    ) == 25

    assert (
        outputs.site_master[
            "site_id"
        ]
        .nunique()
        == 25
    )

    site_008 = (
        outputs.inactive_spans.loc[
            outputs.inactive_spans[
                "site_id"
            ]
            .eq("SITE_008")
        ]
    )

    assert len(site_008) == 1

    assert (
        int(
            site_008.iloc[
                0
            ]["weeks_inactive"]
        )
        == 6
    )


def test_build_derived_outputs_without_survey():
    distribution = pd.read_csv(
        SAMPLE_DIR
        / "distribution_log_clean.csv"
    )

    mapping = suggest_header_mapping(
        distribution.columns,
        dataset_type="distribution_log",
    )

    prepared = {
        "distribution_log": prepare_input(
            distribution,
            mapping,
            dataset_type="distribution_log",
        ),
    }

    outputs = build_derived_outputs(
        prepared
    )

    assert len(
        outputs.site_master
    ) == 25

    assert not (
        outputs.site_master[
            "has_survey_data"
        ]
        .any()
    )


def test_derived_outputs_require_distribution():
    with pytest.raises(
        WorkflowError,
        match="Distribution Log",
    ):
        build_derived_outputs(
            {}
        )