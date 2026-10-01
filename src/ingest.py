import re
from difflib import SequenceMatcher
from numbers import Integral, Real


class QuantityParseError(ValueError):
    """Raised when a quantity cannot be safely converted to individual units."""

class NormalizationError(ValueError):
    """Raised when a product or size cannot be safely normalized."""

class HeaderMappingError(ValueError):
    """Raised when header mapping cannot be configured safely."""


CANONICAL_COLUMNS = {
    "distribution_log": [
        "date",
        "site_id",
        "site_name",
        "product",
        "size",
        "quantity",
        "households_served",
        "children_served",
    ],
    "current_inventory": [
        "as_of_date",
        "product",
        "size",
        "quantity_on_hand",
        "location",
    ],
    "incoming_supply": [
        "expected_date",
        "source",
        "product",
        "size",
        "quantity",
        "status",
    ],
    "partner_survey": [
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


HEADER_ALIASES = {
    "distribution_log": {
        "date": {
            "distribution date",
            "distribution_date",
            "dist date",
        },
        "site_id": {
            "site id",
            "partner id",
            "agency id",
        },
        "site_name": {
            "site name",
            "partner",
            "partner name",
            "agency",
            "agency name",
        },
        "product": {
            "product category",
            "product type",
            "item",
        },
        "size": {
            "product size",
            "product variant",
            "variant",
        },
        "quantity": {
            "qty",
            "units",
            "units distributed",
            "distributed quantity",
        },
        "households_served": {
            "households",
            "households served",
        },
        "children_served": {
            "children",
            "children served",
        },
    },
    "current_inventory": {
        "as_of_date": {
            "as of date",
            "inventory date",
            "count date",
            "snapshot date",
        },
        "product": {
            "product category",
            "product type",
            "item",
        },
        "size": {
            "product size",
            "variant",
        },
        "quantity_on_hand": {
            "quantity on hand",
            "qty on hand",
            "on hand",
            "inventory quantity",
        },
        "location": {
            "warehouse",
            "storage location",
        },
    },
    "incoming_supply": {
        "expected_date": {
            "expected date",
            "arrival date",
            "expected arrival",
        },
        "source": {
            "donor",
            "vendor",
            "supply source",
        },
        "product": {
            "product category",
            "product type",
            "item",
        },
        "size": {
            "product size",
            "variant",
        },
        "quantity": {
            "qty",
            "units",
            "expected quantity",
        },
        "status": {
            "supply status",
        },
    },
    "partner_survey": {
        "site_name": {
            "site name",
            "partner",
            "partner name",
            "partner agency name",
            "agency name",
        },
        "zip_code": {
            "zip",
            "zip code",
            "postal code",
        },
        "agency_type": {
            "agency type",
            "organization type",
            "partner type",
        },
        "families_served_per_month": {
            "families served per month",
            "monthly families served",
        },
        "children_under_4_per_month": {
            "children under 4 per month",
            "children under four per month",
        },
        "menstruating_clients_per_month": {
            "menstruating clients per month",
        },
        "poverty_share_band": {
            "poverty share band",
            "poverty band",
        },
        "priority_population_flags": {
            "priority population flags",
            "priority populations",
        },
        "storage_capacity_cases": {
            "storage capacity cases",
            "storage capacity",
        },
        "distribution_frequency": {
            "distribution frequency",
        },
        "recent_stockout_sizes": {
            "recent stockout sizes",
            "stockout sizes",
        },
        "preferred_contact": {
            "preferred contact",
            "contact",
        },
        "languages_spoken": {
            "languages spoken",
            "languages",
        },
    },
}

def _normalize_header_name(value):
    """
    Convert a raw header into a comparable text token.

    This function is used only for matching header names.
    It does not rename dataframe columns by itself.
    """

    text = str(value).strip().lower()

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text,
    )

    return " ".join(text.split())


def suggest_header_mapping(
    headers,
    dataset_type,
    fuzzy_cutoff=0.78,
):
    """
    Suggest canonical column mappings for uploaded headers.

    Matching order:
    1. canonical or known alias match;
    2. fuzzy suggestion for minor spelling differences;
    3. leave unresolved headers unmapped.

    A canonical target is suggested at most once.
    """

    if dataset_type not in CANONICAL_COLUMNS:
        raise HeaderMappingError(
            f"Unknown dataset type: {dataset_type!r}."
        )

    canonical_columns = CANONICAL_COLUMNS[
        dataset_type
    ]

    aliases = HEADER_ALIASES.get(
        dataset_type,
        {}
    )

    candidate_names = {}

    for canonical_column in canonical_columns:
        names = {
            canonical_column,
            canonical_column.replace("_", " "),
        }

        names.update(
            aliases.get(
                canonical_column,
                set(),
            )
        )

        candidate_names[canonical_column] = {
            _normalize_header_name(name)
            for name in names
        }

    mapping = {}
    used_targets = set()
    unresolved_headers = []

    # -----------------------------------------------------
    # Pass 1: exact canonical / alias matching
    # -----------------------------------------------------

    for raw_header in headers:
        normalized_header = _normalize_header_name(
            raw_header
        )

        matched_target = None

        for canonical_column, names in (
            candidate_names.items()
        ):
            if normalized_header in names:
                matched_target = canonical_column
                break

        if (
            matched_target is not None
            and matched_target not in used_targets
        ):
            mapping[raw_header] = matched_target
            used_targets.add(matched_target)
        else:
            mapping[raw_header] = None
            unresolved_headers.append(raw_header)

    # -----------------------------------------------------
    # Pass 2: fuzzy suggestions for unresolved headers
    # -----------------------------------------------------

    for raw_header in unresolved_headers:
        normalized_header = _normalize_header_name(
            raw_header
        )

        best_target = None
        best_score = 0.0

        for canonical_column, names in (
            candidate_names.items()
        ):
            if canonical_column in used_targets:
                continue

            score = max(
                SequenceMatcher(
                    None,
                    normalized_header,
                    candidate_name,
                ).ratio()
                for candidate_name in names
            )

            if score > best_score:
                best_score = score
                best_target = canonical_column

        if (
            best_target is not None
            and best_score >= fuzzy_cutoff
        ):
            mapping[raw_header] = best_target
            used_targets.add(best_target)

    return mapping

def apply_header_mapping(
    dataframe,
    mapping,
    dataset_type,
):
    """
    Apply a reviewed header mapping to a dataframe.

    Mapped columns are renamed to canonical names.
    Unmapped columns are preserved so that user data is not
    silently discarded.

    Duplicate or invalid canonical targets are rejected.
    """

    if dataset_type not in CANONICAL_COLUMNS:
        raise HeaderMappingError(
            f"Unknown dataset type: {dataset_type!r}."
        )

    dataframe_columns = set(dataframe.columns)

    unknown_source_columns = [
        source
        for source in mapping
        if source not in dataframe_columns
    ]

    if unknown_source_columns:
        raise HeaderMappingError(
            "Header mapping contains columns that are not "
            f"present in the uploaded file: "
            f"{unknown_source_columns}."
        )

    allowed_targets = set(
        CANONICAL_COLUMNS[dataset_type]
    )

    mapped_targets = [
        target
        for target in mapping.values()
        if target is not None
    ]

    invalid_targets = [
        target
        for target in mapped_targets
        if target not in allowed_targets
    ]

    if invalid_targets:
        raise HeaderMappingError(
            "Header mapping contains invalid canonical "
            f"columns: {invalid_targets}."
        )

    if len(mapped_targets) != len(
        set(mapped_targets)
    ):
        raise HeaderMappingError(
            "Multiple uploaded columns cannot map to the "
            "same canonical column."
        )

    rename_map = {
        source: target
        for source, target in mapping.items()
        if target is not None
    }

    return dataframe.rename(
        columns=rename_map
    ).copy()

CANONICAL_PRODUCTS = {
    "diaper",
    "pull_up",
    "wipes",
    "period_pad",
    "period_tampon",
    "period_liner",
    "period_cup",
    "adult_incontinence",
}


CANONICAL_SIZES_BY_PRODUCT = {
    "diaper": {
        "N",
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
    },
    "pull_up": {
        "2T-3T",
        "3T-4T",
        "4T-5T",
    },
    "wipes": {
        "one_size",
    },
    "period_pad": {
        "regular",
        "super",
        "overnight",
    },
    "period_tampon": {
        "regular",
        "super",
        "super_plus",
    },
    "period_liner": {
        "one_size",
    },
    "period_cup": {
        "one_size",
    },
    "adult_incontinence": {
        "S",
        "M",
        "L",
        "XL",
    },
}


def normalize_product(value):
    """
    Normalize a raw product value to the canonical product vocabulary.

    Obvious formatting differences such as capitalization,
    whitespace, spaces, and hyphens are corrected.

    Unknown product categories are rejected rather than guessed.
    """

    if not isinstance(value, str):
        raise NormalizationError(
            "Product must be provided as text."
        )

    normalized = (
        value
        .strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    normalized = re.sub(
        r"_+",
        "_",
        normalized,
    )

    if normalized not in CANONICAL_PRODUCTS:
        raise NormalizationError(
            f"Unknown product category: {value!r}."
        )

    return normalized


def normalize_size(product, value):
    """
    Normalize a raw size using the canonical vocabulary
    for the specified product.

    Size validation is product-specific because the same raw
    label can have different meanings across product categories.
    """

    canonical_product = normalize_product(product)

    if not isinstance(value, str):
        value = str(value)

    raw_size = value.strip()

    if not raw_size:
        raise NormalizationError(
            "Size cannot be blank."
        )

    if canonical_product == "diaper":
        compact = (
            raw_size
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

        diaper_aliases = {
            "n": "N",
            "nb": "N",
            "newborn": "N",
            "sizen": "N",
            "size1": "1",
            "size2": "2",
            "size3": "3",
            "size4": "4",
            "size5": "5",
            "size6": "6",
            "size7": "7",
            "1": "1",
            "2": "2",
            "3": "3",
            "4": "4",
            "5": "5",
            "6": "6",
            "7": "7",
        }

        normalized_size = diaper_aliases.get(
            compact
        )

    elif canonical_product == "pull_up":
        normalized_size = raw_size.upper()

    elif canonical_product == "adult_incontinence":
        normalized_size = raw_size.upper()

    else:
        normalized_size = (
            raw_size
            .lower()
            .replace("-", "_")
            .replace(" ", "_")
        )

        normalized_size = re.sub(
            r"_+",
            "_",
            normalized_size,
        )

    allowed_sizes = CANONICAL_SIZES_BY_PRODUCT[
        canonical_product
    ]

    if normalized_size not in allowed_sizes:
        raise NormalizationError(
            f"Size {value!r} is not valid for "
            f"product {canonical_product!r}."
        )

    return normalized_size

def parse_quantity_to_units(value):
    """
    Convert a raw quantity value into a non-negative whole number
    of individual units.

    Accepted examples:
        300
        300.0
        "300"
        "300 units"
        "12 packs x 25 units"
        "1 pack x 25 units"

    Ambiguous, negative, or fractional quantities are rejected.
    """

    if isinstance(value, bool):
        raise QuantityParseError(
            "Boolean values are not valid quantities."
        )

    if isinstance(value, Integral):
        quantity = int(value)

        if quantity < 0:
            raise QuantityParseError(
                "Quantity cannot be negative."
            )

        return quantity

    if isinstance(value, Real):
        numeric_value = float(value)

        if numeric_value < 0:
            raise QuantityParseError(
                "Quantity cannot be negative."
            )

        if not numeric_value.is_integer():
            raise QuantityParseError(
                "Quantity must be a whole number of units."
            )

        return int(numeric_value)

    if not isinstance(value, str):
        raise QuantityParseError(
            "Quantity must be numeric or a supported quantity string."
        )

    text = value.strip().lower()

    if not text:
        raise QuantityParseError(
            "Quantity cannot be blank."
        )

    pack_match = re.fullmatch(
        r"(\d+)\s+packs?\s*x\s*(\d+)\s+units?",
        text,
    )

    if pack_match:
        pack_count = int(pack_match.group(1))
        units_per_pack = int(pack_match.group(2))

        return pack_count * units_per_pack

    unit_match = re.fullmatch(
        r"([+-]?\d+(?:\.\d+)?)\s*units?",
        text,
    )

    if unit_match:
        numeric_value = float(unit_match.group(1))

        if numeric_value < 0:
            raise QuantityParseError(
                "Quantity cannot be negative."
            )

        if not numeric_value.is_integer():
            raise QuantityParseError(
                "Quantity must be a whole number of units."
            )

        return int(numeric_value)

    numeric_match = re.fullmatch(
        r"[+-]?\d+(?:\.\d+)?",
        text,
    )

    if numeric_match:
        numeric_value = float(text)

        if numeric_value < 0:
            raise QuantityParseError(
                "Quantity cannot be negative."
            )

        if not numeric_value.is_integer():
            raise QuantityParseError(
                "Quantity must be a whole number of units."
            )

        return int(numeric_value)

    raise QuantityParseError(
        "Quantity format is ambiguous or unsupported."
    )