from dataclasses import dataclass
from numbers import Integral, Real

import pandas as pd

from src.ingest import (
    assign_site_ids,
    normalize_product,
    normalize_site_name,
    normalize_size,
    parse_quantity_to_units,
)
from src.validate import (
    find_duplicate_issues,
    validate_table,
)


@dataclass(frozen=True)
class QualityEvent:
    """
    One user-facing data-quality event.

    Severity values currently used:
        correction
        warning
        error
    """

    severity: str
    code: str
    message: str
    count: int
    column: str | None = None


@dataclass(frozen=True)
class DataQualityReport:
    """
    Summary of what happened while cleaning one uploaded table.
    """

    input_rows: int
    output_rows: int
    corrected_rows: int
    dropped_rows: int
    events: tuple[QualityEvent, ...]

    @property
    def corrections(self):
        return tuple(
            event
            for event in self.events
            if event.severity == "correction"
        )

    @property
    def warnings(self):
        return tuple(
            event
            for event in self.events
            if event.severity == "warning"
        )

    @property
    def errors(self):
        return tuple(
            event
            for event in self.events
            if event.severity == "error"
        )


@dataclass(frozen=True)
class CleaningResult:
    """
    Clean canonical dataframe plus its data-quality report.
    """

    dataframe: pd.DataFrame
    report: DataQualityReport


def _text_was_corrected(
    raw_value,
    normalized_value,
):
    """
    Return True when text normalization materially changed
    the uploaded representation.
    """

    if pd.isna(raw_value):
        return True

    return str(raw_value) != str(
        normalized_value
    )


def _quantity_was_corrected(
    raw_value,
    parsed_value,
):
    """
    Determine whether parsing changed the user's quantity
    representation.

    Plain numeric values such as 300, 300.0, or "300" are
    treated as already semantically canonical.

    Explicit units, pack expressions, fractional formatting,
    and similar supported transformations count as corrections.
    """

    if isinstance(raw_value, bool):
        return True

    if isinstance(raw_value, Integral):
        return int(raw_value) != parsed_value

    if isinstance(raw_value, Real):
        numeric_value = float(raw_value)

        return not (
            numeric_value.is_integer()
            and int(numeric_value)
            == parsed_value
        )

    if isinstance(raw_value, str):
        text = raw_value.strip()

        return text != str(parsed_value)

    return True


def _add_correction_event(
    events,
    code,
    message,
    count,
    column,
):
    if count <= 0:
        return

    events.append(
        QualityEvent(
            severity="correction",
            code=code,
            message=message,
            count=count,
            column=column,
        )
    )


def clean_distribution_log(
    dataframe,
):
    """
    Clean and validate a canonical-header distribution log.

    Header mapping is intentionally handled before this
    function. This function owns value normalization,
    site identity resolution, validation, and the
    data-quality report.

    No rows are silently dropped.
    """

    working = (
        dataframe
        .copy()
        .reset_index(drop=True)
    )

    input_rows = len(working)

    required_for_cleaning = {
        "site_name",
        "product",
        "size",
        "quantity",
    }

    missing_for_cleaning = (
        required_for_cleaning
        - set(working.columns)
    )

    if missing_for_cleaning:
        # validate_table already provides the friendly
        # missing-column error structure.
        validate_table(
            working,
            dataset_type="distribution_log",
        )

    events = []
    corrected_row_indices = set()

    # -------------------------------------------------
    # Site names
    # -------------------------------------------------

    normalized_site_names = []

    site_name_corrections = 0

    for row_index, raw_value in (
        working["site_name"].items()
    ):
        normalized_value = (
            normalize_site_name(
                raw_value
            )
        )

        normalized_site_names.append(
            normalized_value
        )

        if _text_was_corrected(
            raw_value,
            normalized_value,
        ):
            site_name_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["site_name"] = (
        normalized_site_names
    )

    _add_correction_event(
        events,
        code="site_name_normalized",
        message=(
            "Partner site names had whitespace "
            "normalized."
        ),
        count=site_name_corrections,
        column="site_name",
    )

    # -------------------------------------------------
    # Site IDs
    # -------------------------------------------------

    if "site_id" not in working.columns:
        missing_site_id_mask = pd.Series(
            True,
            index=working.index,
        )
    else:
        missing_site_id_mask = (
            working["site_id"].isna()
            | working["site_id"]
            .astype(str)
            .str.strip()
            .eq("")
        )

    working = assign_site_ids(
        working
    )

    assigned_site_id_count = int(
        missing_site_id_mask.sum()
    )

    if assigned_site_id_count:
        corrected_row_indices.update(
            working.index[
                missing_site_id_mask
            ].tolist()
        )

        _add_correction_event(
            events,
            code="site_id_assigned",
            message=(
                "Missing partner site IDs were "
                "resolved deterministically."
            ),
            count=assigned_site_id_count,
            column="site_id",
        )

    # -------------------------------------------------
    # Products
    # -------------------------------------------------

    normalized_products = []

    product_corrections = 0

    for row_index, raw_value in (
        working["product"].items()
    ):
        normalized_value = (
            normalize_product(
                raw_value
            )
        )

        normalized_products.append(
            normalized_value
        )

        if _text_was_corrected(
            raw_value,
            normalized_value,
        ):
            product_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["product"] = (
        normalized_products
    )

    _add_correction_event(
        events,
        code="product_normalized",
        message=(
            "Product labels were normalized to "
            "the canonical product vocabulary."
        ),
        count=product_corrections,
        column="product",
    )

    # -------------------------------------------------
    # Product-aware sizes
    # -------------------------------------------------

    normalized_sizes = []

    size_corrections = 0

    for row_index, (
        product,
        raw_size,
    ) in enumerate(
        zip(
            working["product"],
            working["size"],
        )
    ):
        normalized_size = normalize_size(
            product,
            raw_size,
        )

        normalized_sizes.append(
            normalized_size
        )

        if _text_was_corrected(
            raw_size,
            normalized_size,
        ):
            size_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["size"] = (
        normalized_sizes
    )

    _add_correction_event(
        events,
        code="size_normalized",
        message=(
            "Product sizes were normalized using "
            "product-specific size rules."
        ),
        count=size_corrections,
        column="size",
    )

    # -------------------------------------------------
    # Quantity → individual units
    # -------------------------------------------------

    parsed_quantities = []

    quantity_corrections = 0

    for row_index, raw_value in (
        working["quantity"].items()
    ):
        parsed_value = (
            parse_quantity_to_units(
                raw_value
            )
        )

        parsed_quantities.append(
            parsed_value
        )

        if _quantity_was_corrected(
            raw_value,
            parsed_value,
        ):
            quantity_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["quantity"] = (
        parsed_quantities
    )

    _add_correction_event(
        events,
        code="quantity_normalized",
        message=(
            "Quantity values were converted to "
            "individual whole units."
        ),
        count=quantity_corrections,
        column="quantity",
    )

    # -------------------------------------------------
    # Contract validation
    # -------------------------------------------------

    validated = validate_table(
        working,
        dataset_type="distribution_log",
    )

    # -------------------------------------------------
    # Non-blocking duplicate warnings
    # -------------------------------------------------

    duplicate_issues = (
        find_duplicate_issues(
            validated,
            dataset_type="distribution_log",
        )
    )

    for issue in duplicate_issues:
        if issue.severity != "warning":
            continue

        events.append(
            QualityEvent(
                severity="warning",
                code=issue.code,
                message=issue.message,
                count=issue.count,
            )
        )

    output_rows = len(validated)

    report = DataQualityReport(
        input_rows=input_rows,
        output_rows=output_rows,
        corrected_rows=len(
            corrected_row_indices
        ),
        dropped_rows=(
            input_rows
            - output_rows
        ),
        events=tuple(events),
    )

    return CleaningResult(
        dataframe=validated,
        report=report,
    )