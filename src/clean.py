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

def _normalize_simple_text(value, field_name):
    """
    Normalize ordinary text without changing its business meaning.
    """

    if pd.isna(value):
        raise ValueError(
            f"{field_name} cannot be missing."
        )

    normalized = " ".join(
        str(value).strip().split()
    )

    if not normalized:
        raise ValueError(
            f"{field_name} cannot be blank."
        )

    return normalized


def _normalize_category(value):
    """
    Normalize simple controlled-vocabulary labels.
    """

    text = _normalize_simple_text(
        value,
        "Category",
    )

    normalized = (
        text
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    while "__" in normalized:
        normalized = normalized.replace(
            "__",
            "_",
        )

    return normalized


def _normalize_semicolon_list(value):
    """
    Normalize semicolon-separated values while preserving order.
    """

    if pd.isna(value):
        return value

    text = str(value).strip()

    if not text:
        return text

    parts = [
        part.strip()
        for part in text.split(";")
        if part.strip()
    ]

    return ";".join(parts)


def _normalize_recent_stockouts(value):
    """
    Normalize partner-survey recent stockout entries.

    Preferred canonical format:
        product:size

    Legacy bare diaper sizes such as:
        4;5;6

    are safely interpreted as:
        diaper:4;diaper:5;diaper:6

    because those numeric size labels are unambiguous
    in the current controlled vocabulary.
    """

    if pd.isna(value):
        return value

    text = str(value).strip()

    if not text:
        return text

    if text.casefold() == "none":
        return "none"

    normalized_entries = []

    for raw_entry in text.split(";"):
        entry = raw_entry.strip()

        if not entry:
            continue

        if ":" in entry:
            product_text, size_text = (
                entry.split(
                    ":",
                    maxsplit=1,
                )
            )

            product = normalize_product(
                product_text
            )

            size = normalize_size(
                product,
                size_text,
            )

            normalized_entries.append(
                f"{product}:{size}"
            )

            continue

        bare_size = entry.strip()

        if bare_size in {
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
        }:
            normalized_entries.append(
                f"diaper:{bare_size}"
            )
            continue

        if bare_size.casefold() in {
            "n",
            "nb",
            "newborn",
        }:
            normalized_entries.append(
                "diaper:N"
            )
            continue

        raise ValueError(
            "Recent stockout size "
            f"{entry!r} is ambiguous. "
            "Use product:size format."
        )

    return ";".join(
        normalized_entries
    )

def clean_current_inventory(
    dataframe,
):
    """
    Clean and validate a current-inventory snapshot.

    Duplicate canonical inventory keys remain blocking
    because silently combining them could double-count stock.
    """

    working = (
        dataframe
        .copy()
        .reset_index(drop=True)
    )

    input_rows = len(working)
    events = []
    corrected_row_indices = set()

    normalized_products = []
    normalized_sizes = []
    parsed_quantities = []

    product_corrections = 0
    size_corrections = 0
    quantity_corrections = 0

    for row_index, raw_product in (
        working["product"].items()
    ):
        normalized_product = (
            normalize_product(
                raw_product
            )
        )

        normalized_products.append(
            normalized_product
        )

        if _text_was_corrected(
            raw_product,
            normalized_product,
        ):
            product_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["product"] = (
        normalized_products
    )

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

    working["size"] = normalized_sizes

    for row_index, raw_quantity in (
        working[
            "quantity_on_hand"
        ].items()
    ):
        parsed_quantity = (
            parse_quantity_to_units(
                raw_quantity
            )
        )

        parsed_quantities.append(
            parsed_quantity
        )

        if _quantity_was_corrected(
            raw_quantity,
            parsed_quantity,
        ):
            quantity_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working[
        "quantity_on_hand"
    ] = parsed_quantities

    if "location" in working.columns:
        normalized_locations = []

        location_corrections = 0

        for row_index, raw_location in (
            working["location"].items()
        ):
            if pd.isna(raw_location):
                normalized_locations.append(
                    raw_location
                )
                continue

            normalized_location = (
                " ".join(
                    str(
                        raw_location
                    ).strip().split()
                )
            )

            normalized_locations.append(
                normalized_location
            )

            if _text_was_corrected(
                raw_location,
                normalized_location,
            ):
                location_corrections += 1
                corrected_row_indices.add(
                    row_index
                )

        working["location"] = (
            normalized_locations
        )

        _add_correction_event(
            events,
            code="location_normalized",
            message=(
                "Inventory location labels had "
                "whitespace normalized."
            ),
            count=location_corrections,
            column="location",
        )

    _add_correction_event(
        events,
        code="product_normalized",
        message=(
            "Product labels were normalized."
        ),
        count=product_corrections,
        column="product",
    )

    _add_correction_event(
        events,
        code="size_normalized",
        message=(
            "Product sizes were normalized."
        ),
        count=size_corrections,
        column="size",
    )

    _add_correction_event(
        events,
        code="quantity_normalized",
        message=(
            "Inventory quantities were converted "
            "to individual whole units."
        ),
        count=quantity_corrections,
        column="quantity_on_hand",
    )

    validated = validate_table(
        working,
        dataset_type="current_inventory",
    )

    report = DataQualityReport(
        input_rows=input_rows,
        output_rows=len(validated),
        corrected_rows=len(
            corrected_row_indices
        ),
        dropped_rows=(
            input_rows
            - len(validated)
        ),
        events=tuple(events),
    )

    return CleaningResult(
        dataframe=validated,
        report=report,
    )

def clean_incoming_supply(
    dataframe,
):
    """
    Clean and validate expected incoming supply.

    Incoming supply may use size='unknown' when a donation
    source does not yet provide product-size detail.
    """

    working = (
        dataframe
        .copy()
        .reset_index(drop=True)
    )

    input_rows = len(working)
    events = []
    corrected_row_indices = set()

    normalized_products = []
    normalized_sizes = []
    normalized_sources = []
    normalized_statuses = []
    parsed_quantities = []

    product_corrections = 0
    size_corrections = 0
    source_corrections = 0
    status_corrections = 0
    quantity_corrections = 0

    for row_index, raw_source in (
        working["source"].items()
    ):
        normalized_source = (
            _normalize_simple_text(
                raw_source,
                "Source",
            )
        )

        normalized_sources.append(
            normalized_source
        )

        if _text_was_corrected(
            raw_source,
            normalized_source,
        ):
            source_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["source"] = (
        normalized_sources
    )

    for row_index, raw_product in (
        working["product"].items()
    ):
        normalized_product = (
            normalize_product(
                raw_product
            )
        )

        normalized_products.append(
            normalized_product
        )

        if _text_was_corrected(
            raw_product,
            normalized_product,
        ):
            product_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["product"] = (
        normalized_products
    )

    for row_index, (
        product,
        raw_size,
    ) in enumerate(
        zip(
            working["product"],
            working["size"],
        )
    ):
        raw_size_text = str(
            raw_size
        ).strip()

        if (
            raw_size_text.casefold()
            == "unknown"
        ):
            normalized_size = "unknown"
        else:
            normalized_size = (
                normalize_size(
                    product,
                    raw_size,
                )
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

    working["size"] = normalized_sizes

    for row_index, raw_quantity in (
        working["quantity"].items()
    ):
        parsed_quantity = (
            parse_quantity_to_units(
                raw_quantity
            )
        )

        parsed_quantities.append(
            parsed_quantity
        )

        if _quantity_was_corrected(
            raw_quantity,
            parsed_quantity,
        ):
            quantity_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["quantity"] = (
        parsed_quantities
    )

    for row_index, raw_status in (
        working["status"].items()
    ):
        normalized_status = (
            _normalize_category(
                raw_status
            )
        )

        normalized_statuses.append(
            normalized_status
        )

        if _text_was_corrected(
            raw_status,
            normalized_status,
        ):
            status_corrections += 1
            corrected_row_indices.add(
                row_index
            )

    working["status"] = (
        normalized_statuses
    )

    _add_correction_event(
        events,
        code="source_normalized",
        message=(
            "Incoming supply source labels had "
            "whitespace normalized."
        ),
        count=source_corrections,
        column="source",
    )

    _add_correction_event(
        events,
        code="product_normalized",
        message=(
            "Product labels were normalized."
        ),
        count=product_corrections,
        column="product",
    )

    _add_correction_event(
        events,
        code="size_normalized",
        message=(
            "Incoming product sizes were normalized."
        ),
        count=size_corrections,
        column="size",
    )

    _add_correction_event(
        events,
        code="quantity_normalized",
        message=(
            "Incoming quantities were converted "
            "to individual whole units."
        ),
        count=quantity_corrections,
        column="quantity",
    )

    _add_correction_event(
        events,
        code="status_normalized",
        message=(
            "Incoming supply statuses were "
            "normalized."
        ),
        count=status_corrections,
        column="status",
    )

    validated = validate_table(
        working,
        dataset_type="incoming_supply",
    )

    duplicate_issues = (
        find_duplicate_issues(
            validated,
            dataset_type="incoming_supply",
        )
    )

    for issue in duplicate_issues:
        if issue.severity == "warning":
            events.append(
                QualityEvent(
                    severity="warning",
                    code=issue.code,
                    message=issue.message,
                    count=issue.count,
                )
            )

    report = DataQualityReport(
        input_rows=input_rows,
        output_rows=len(validated),
        corrected_rows=len(
            corrected_row_indices
        ),
        dropped_rows=(
            input_rows
            - len(validated)
        ),
        events=tuple(events),
    )

    return CleaningResult(
        dataframe=validated,
        report=report,
    )

def clean_partner_survey(
    dataframe,
):
    """
    Clean and validate partner survey responses.

    Partner survey is optional, but when supplied it must
    contain one trusted current record per normalized partner.
    """

    working = (
        dataframe
        .copy()
        .reset_index(drop=True)
    )

    input_rows = len(working)
    events = []
    corrected_row_indices = set()

    # ---------------------------------------------
    # Site name
    # ---------------------------------------------

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

    # ---------------------------------------------
    # Controlled categorical fields
    # ---------------------------------------------

    categorical_columns = [
        "agency_type",
        "poverty_share_band",
        "distribution_frequency",
    ]

    for column in categorical_columns:
        if column not in working.columns:
            continue

        corrected_count = 0
        normalized_values = []

        for row_index, raw_value in (
            working[column].items()
        ):
            if pd.isna(raw_value):
                normalized_values.append(
                    raw_value
                )
                continue

            normalized_value = (
                _normalize_category(
                    raw_value
                )
            )

            normalized_values.append(
                normalized_value
            )

            if _text_was_corrected(
                raw_value,
                normalized_value,
            ):
                corrected_count += 1
                corrected_row_indices.add(
                    row_index
                )

        working[column] = (
            normalized_values
        )

        _add_correction_event(
            events,
            code=f"{column}_normalized",
            message=(
                f"{column} values were normalized."
            ),
            count=corrected_count,
            column=column,
        )

    # ---------------------------------------------
    # Semicolon-list fields
    # ---------------------------------------------

    list_columns = [
        "priority_population_flags",
        "languages_spoken",
    ]

    for column in list_columns:
        if column not in working.columns:
            continue

        corrected_count = 0
        normalized_values = []

        for row_index, raw_value in (
            working[column].items()
        ):
            normalized_value = (
                _normalize_semicolon_list(
                    raw_value
                )
            )

            normalized_values.append(
                normalized_value
            )

            if (
                not pd.isna(raw_value)
                and _text_was_corrected(
                    raw_value,
                    normalized_value,
                )
            ):
                corrected_count += 1
                corrected_row_indices.add(
                    row_index
                )

        working[column] = (
            normalized_values
        )

        _add_correction_event(
            events,
            code=f"{column}_normalized",
            message=(
                f"{column} formatting was "
                "normalized."
            ),
            count=corrected_count,
            column=column,
        )

    # ---------------------------------------------
    # Recent stockouts
    # ---------------------------------------------

    if (
        "recent_stockout_sizes"
        in working.columns
    ):
        normalized_stockouts = []
        stockout_corrections = 0

        for row_index, raw_value in (
            working[
                "recent_stockout_sizes"
            ].items()
        ):
            normalized_value = (
                _normalize_recent_stockouts(
                    raw_value
                )
            )

            normalized_stockouts.append(
                normalized_value
            )

            if (
                not pd.isna(raw_value)
                and _text_was_corrected(
                    raw_value,
                    normalized_value,
                )
            ):
                stockout_corrections += 1
                corrected_row_indices.add(
                    row_index
                )

        working[
            "recent_stockout_sizes"
        ] = normalized_stockouts

        _add_correction_event(
            events,
            code=(
                "recent_stockout_sizes_normalized"
            ),
            message=(
                "Recent stockout sizes were "
                "normalized to product:size format."
            ),
            count=stockout_corrections,
            column="recent_stockout_sizes",
        )

    # ---------------------------------------------
    # Validate before generated site IDs
    # ---------------------------------------------

    validated = validate_table(
        working,
        dataset_type="partner_survey",
    )

    # Survey itself does not require site_id from the user.
    # Generate one deterministically for later reconciliation
    # and site-master construction.
    identified = assign_site_ids(
        validated
    )

    report = DataQualityReport(
        input_rows=input_rows,
        output_rows=len(identified),
        corrected_rows=len(
            corrected_row_indices
        ),
        dropped_rows=(
            input_rows
            - len(identified)
        ),
        events=tuple(events),
    )

    return CleaningResult(
        dataframe=identified,
        report=report,
    )