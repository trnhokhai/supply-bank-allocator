from pathlib import Path
from zipfile import BadZipFile

import pandas as pd


class FileReadError(ValueError):
    """Raised when an uploaded table cannot be read safely."""


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


DEMO_FILES = {
    "distribution_log": (
        SAMPLE_DIR
        / "distribution_log_messy.csv"
    ),
    "current_inventory": (
        SAMPLE_DIR
        / "current_inventory.csv"
    ),
    "incoming_supply": (
        SAMPLE_DIR
        / "incoming_supply.csv"
    ),
    "partner_survey": (
        SAMPLE_DIR
        / "partner_survey.csv"
    ),
}


SUPPORTED_EXTENSIONS = {
    ".csv",
    ".xlsx",
}


def _resolve_filename(
    source,
    filename=None,
):
    """
    Resolve the user-facing filename from either a local path
    or an uploaded file-like object.
    """

    if filename is not None:
        return str(filename)

    if isinstance(
        source,
        (
            str,
            Path,
        ),
    ):
        return str(source)

    source_name = getattr(
        source,
        "name",
        None,
    )

    if source_name:
        return str(source_name)

    raise FileReadError(
        "Could not determine the uploaded file type. "
        "Provide a CSV or XLSX filename."
    )


def _rewind_if_possible(source):
    """
    Reset file-like uploads before reading.

    Streamlit UploadedFile objects behave like in-memory
    file streams and may already have been read elsewhere.
    """

    seek = getattr(
        source,
        "seek",
        None,
    )

    if callable(seek):
        seek(0)


def read_table(
    source,
    filename=None,
):
    """
    Read a CSV or XLSX table from either:

    - a local filesystem path; or
    - a file-like uploaded object.

    This function performs file parsing only.

    Header mapping, normalization, validation, and cleaning
    remain separate downstream responsibilities.
    """

    resolved_filename = (
        _resolve_filename(
            source,
            filename=filename,
        )
    )

    extension = (
        Path(
            resolved_filename
        )
        .suffix
        .lower()
    )

    if extension not in SUPPORTED_EXTENSIONS:
        raise FileReadError(
            "Unsupported file type. "
            "Please upload a .csv or .xlsx file."
        )

    try:
        _rewind_if_possible(
            source
        )

        if extension == ".csv":
            dataframe = pd.read_csv(
                source
            )

        else:
            dataframe = pd.read_excel(
                source,
                engine="openpyxl",
            )

    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        BadZipFile,
        ValueError,
        OSError,
    ) as exc:
        raise FileReadError(
            f"Could not read {Path(resolved_filename).name!r}. "
            "Confirm that the file is a valid CSV or XLSX "
            "table and try again."
        ) from exc

    if len(dataframe.columns) == 0:
        raise FileReadError(
            "The uploaded file does not contain "
            "any readable columns."
        )

    return dataframe


def load_demo_inputs():
    """
    Load all four synthetic inputs used by Demo Mode.

    The deliberately messy distribution file is used so
    the upload experience can demonstrate automatic
    corrections and the data-quality report.
    """

    demo_inputs = {}

    for (
        dataset_type,
        file_path,
    ) in DEMO_FILES.items():
        try:
            demo_inputs[
                dataset_type
            ] = read_table(
                file_path
            )

        except FileReadError as exc:
            raise FileReadError(
                "Demo Mode could not load "
                f"{dataset_type!r}: {exc}"
            ) from exc

    return demo_inputs