import streamlit as st

from src.file_io import (
    FileReadError,
    load_demo_inputs,
    read_table,
)

from src.ingest import (
    CANONICAL_COLUMNS,
    suggest_header_mapping,
)

from src.workflow import (
    prepare_input,
)

st.set_page_config(
    page_title="Upload | Supply Bank Allocator",
    page_icon="📤",
    layout="wide",
)


DATASET_CONFIG = {
    "distribution_log": {
        "label": "Distribution Log",
        "help": (
            "Historical distributions by partner, "
            "product, and size."
        ),
    },
    "current_inventory": {
        "label": "Current Inventory",
        "help": (
            "Current on-hand inventory by product "
            "and size."
        ),
    },
    "incoming_supply": {
        "label": "Incoming Supply",
        "help": (
            "Expected donations and purchases. "
            "Recommended when available."
        ),
    },
    "partner_survey": {
        "label": "Partner Survey",
        "help": (
            "Optional partner-level context used later "
            "for equity and cold-start planning."
        ),
    },
}


def show_raw_preview(
    dataset_type,
    dataframe,
):
    """
    Show a compact preview of one raw input before any
    header mapping or cleaning occurs.
    """

    config = DATASET_CONFIG[
        dataset_type
    ]

    st.markdown(
        f"#### {config['label']}"
    )

    st.caption(
        config["help"]
    )

    metric_columns = st.columns(2)

    metric_columns[0].metric(
        "Rows",
        f"{len(dataframe):,}",
    )

    metric_columns[1].metric(
        "Columns",
        len(dataframe.columns),
    )

    with st.expander(
        "Preview raw data",
        expanded=False,
    ):
        st.dataframe(
            dataframe.head(10),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Detected columns: "
        + ", ".join(
            str(column)
            for column
            in dataframe.columns
        )
    )

def show_header_mapping(
    dataset_type,
    dataframe,
):
    """
    Show suggested header mappings and allow the user
    to review or change each mapped target.
    """

    config = DATASET_CONFIG[
        dataset_type
    ]

    st.markdown(
        f"### Map Columns — {config['label']}"
    )

    suggestions = (
        suggest_header_mapping(
            dataframe.columns.tolist(),
            dataset_type=dataset_type,
        )
    )

    canonical_options = (
        [
            "— Unmapped —",
        ]
        + CANONICAL_COLUMNS[
            dataset_type
        ]
    )

    reviewed_mapping = {}

    for raw_column in dataframe.columns:
        suggested_target = (
            suggestions.get(
                raw_column
            )
        )

        if suggested_target is None:
            default_index = 0

        else:
            default_index = (
                canonical_options.index(
                    suggested_target
                )
            )

        selected = st.selectbox(
            f"{raw_column}",
            options=canonical_options,
            index=default_index,
            key=(
                f"mapping_"
                f"{dataset_type}_"
                f"{raw_column}"
            ),
        )

        reviewed_mapping[
            raw_column
        ] = (
            None
            if selected
            == "— Unmapped —"
            else selected
        )

    return reviewed_mapping

st.title("Upload Data")

st.write(
    "Load operational files for cleaning and validation. "
    "Nothing uploaded here is written to a database."
)


demo_mode = st.toggle(
    "Demo Mode",
    value=False,
    help=(
        "Load the project's synthetic datasets "
        "instead of uploading files."
    ),
)


raw_inputs = {}


# ---------------------------------------------------------
# Demo Mode
# ---------------------------------------------------------

if demo_mode:
    try:
        raw_inputs = (
            load_demo_inputs()
        )

        st.success(
            "Demo Mode loaded all four synthetic inputs."
        )

        st.info(
            "The demo Distribution Log is deliberately messy. "
            "Later in this Upload workflow, the app will "
            "demonstrate the automatic corrections and "
            "Data Quality Report."
        )

    except FileReadError as exc:
        st.error(
            str(exc)
        )


# ---------------------------------------------------------
# User Upload Mode
# ---------------------------------------------------------

else:
    st.markdown(
        "### Choose files"
    )

    st.caption(
        "Supported formats: CSV and XLSX."
    )

    distribution_file = (
        st.file_uploader(
            "Distribution Log",
            type=[
                "csv",
                "xlsx",
            ],
            key="distribution_log_upload",
        )
    )

    inventory_file = (
        st.file_uploader(
            "Current Inventory",
            type=[
                "csv",
                "xlsx",
            ],
            key="current_inventory_upload",
        )
    )

    incoming_file = (
        st.file_uploader(
            "Incoming Supply",
            type=[
                "csv",
                "xlsx",
            ],
            key="incoming_supply_upload",
        )
    )

    survey_file = (
        st.file_uploader(
            "Partner Survey",
            type=[
                "csv",
                "xlsx",
            ],
            key="partner_survey_upload",
        )
    )

    uploaded_files = {
        "distribution_log": (
            distribution_file
        ),
        "current_inventory": (
            inventory_file
        ),
        "incoming_supply": (
            incoming_file
        ),
        "partner_survey": (
            survey_file
        ),
    }

    for (
        dataset_type,
        uploaded_file,
    ) in uploaded_files.items():

        if uploaded_file is None:
            continue

        try:
            raw_inputs[
                dataset_type
            ] = read_table(
                uploaded_file
            )

        except FileReadError as exc:
            st.error(
                f"{DATASET_CONFIG[dataset_type]['label']}: "
                f"{exc}"
            )


# ---------------------------------------------------------
# Raw Input Summary
# ---------------------------------------------------------

if raw_inputs:
    st.divider()

    st.markdown(
        "### Raw Input Preview"
    )

    st.caption(
        "These tables have only been read from the files. "
        "No header mapping, cleaning, normalization, or "
        "validation has happened yet."
    )

    for dataset_type in (
        "distribution_log",
        "current_inventory",
        "incoming_supply",
        "partner_survey",
    ):
        dataframe = raw_inputs.get(
            dataset_type
        )

        if dataframe is None:
            continue

        with st.container(
            border=True
        ):
            show_raw_preview(
                dataset_type,
                dataframe,
            )

        st.divider()

    st.markdown(
        "## Review Header Mapping"
    )

    st.caption(
        "The app suggests canonical columns automatically. "
        "Review the selections before cleaning."
    )

    reviewed_mappings = {}

    for dataset_type in (
        "distribution_log",
        "current_inventory",
        "incoming_supply",
        "partner_survey",
    ):
        dataframe = raw_inputs.get(
            dataset_type
        )

        if dataframe is None:
            continue

        with st.expander(
            (
                "Map "
                + DATASET_CONFIG[
                    dataset_type
                ]["label"]
                + " columns"
            ),
            expanded=(
                dataset_type
                == "distribution_log"
            ),
        ):
            reviewed_mappings[
                dataset_type
            ] = show_header_mapping(
                dataset_type,
                dataframe,
            )

        st.divider()

    if st.button(
        "Clean & Validate",
        type="primary",
        use_container_width=True,
    ):
        cleaned_results = {}
        processing_errors = {}

        for (
            dataset_type,
            dataframe,
        ) in raw_inputs.items():
            try:
                cleaned_results[
                    dataset_type
                ] = prepare_input(
                    dataframe,
                    reviewed_mappings[
                        dataset_type
                    ],
                    dataset_type=dataset_type,
                )

            except ValueError as exc:
                processing_errors[
                    dataset_type
                ] = str(exc)

        st.session_state[
            "cleaned_results"
        ] = cleaned_results

        st.session_state[
            "processing_errors"
        ] = processing_errors

    cleaned_results = st.session_state.get(
        "cleaned_results",
        {},
    )

    processing_errors = st.session_state.get(
        "processing_errors",
        {},
    )

    if cleaned_results or processing_errors:
        st.divider()

        st.markdown(
            "## Cleaning Results"
        )

        for dataset_type in (
            "distribution_log",
            "current_inventory",
            "incoming_supply",
            "partner_survey",
        ):
            label = DATASET_CONFIG[
                dataset_type
            ]["label"]

            if dataset_type in processing_errors:
                st.error(
                    f"{label}: "
                    f"{processing_errors[dataset_type]}"
                )

                continue

            if dataset_type not in cleaned_results:
                continue

            result = cleaned_results[
                dataset_type
            ].cleaning_result

            report = result.report

            st.success(
                f"{label} cleaned and validated successfully."
            )

            metric_columns = st.columns(4)

            metric_columns[0].metric(
                "Rows uploaded",
                f"{report.input_rows:,}",
            )

            metric_columns[1].metric(
                "Rows cleaned",
                f"{report.output_rows:,}",
            )

            metric_columns[2].metric(
                "Rows corrected",
                f"{report.corrected_rows:,}",
            )

            metric_columns[3].metric(
                "Rows dropped",
                f"{report.dropped_rows:,}",
            )

            if report.events:
                with st.expander(
                    "Data Quality Details",
                    expanded=(
                        dataset_type
                        == "distribution_log"
                    ),
                ):
                    for event in report.events:
                        severity_label = {
                            "correction": "Corrected",
                            "warning": "Warning",
                            "error": "Error",
                        }.get(
                            event.severity,
                            event.severity.title(),
                        )

                        st.markdown(
                            f"**{severity_label}: "
                            f"{event.count:,} row(s)**"
                        )

                        if event.column:
                            st.caption(
                                f"Column: {event.column}"
                            )

                        st.write(
                            event.message
                        )

            else:
                st.caption(
                    "No automatic corrections or "
                    "data-quality warnings were needed."
                )

            with st.expander(
                "Preview cleaned data",
                expanded=False,
            ):
                st.dataframe(
                    result.dataframe.head(10),
                    use_container_width=True,
                    hide_index=True,
                )

else:
    st.info(
        "Upload at least one file, or turn on Demo Mode "
        "to load the synthetic example data."
    )