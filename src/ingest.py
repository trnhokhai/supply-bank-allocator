import hashlib
import re
import unicodedata
from difflib import SequenceMatcher
from numbers import Integral, Real

import pandas as pd


class QuantityParseError(ValueError):
    """Raised when a quantity cannot be safely converted to individual units."""

class NormalizationError(ValueError):
    """Raised when a product or size cannot be safely normalized."""

class HeaderMappingError(ValueError):
    """Raised when header mapping cannot be configured safely."""

class SiteIdentityError(ValueError):
    """Raised when partner site identity cannot be resolved safely."""

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

def normalize_site_name(value):
    """
    Normalize a partner site name without changing its
    business meaning.

    Leading/trailing whitespace is removed and repeated
    internal whitespace is collapsed.
    """

    if pd.isna(value):
        raise SiteIdentityError(
            "Site name cannot be missing."
        )

    if not isinstance(value, str):
        raise SiteIdentityError(
            "Site name must be provided as text."
        )

    normalized = " ".join(
        value.strip().split()
    )

    if not normalized:
        raise SiteIdentityError(
            "Site name cannot be blank."
        )

    return normalized


def _site_name_key(value):
    """
    Create a stable comparison key for site reconciliation.
    """

    return normalize_site_name(
        value
    ).casefold()


def _site_id_slug(site_name):
    """
    Create a readable deterministic slug for generated site IDs.
    """

    normalized_name = normalize_site_name(
        site_name
    )

    ascii_name = (
        unicodedata
        .normalize(
            "NFKD",
            normalized_name,
        )
        .encode(
            "ascii",
            "ignore",
        )
        .decode("ascii")
    )

    slug = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        ascii_name,
    )

    slug = slug.strip("_").upper()

    if slug:
        return f"AUTO_{slug}"

    fallback_hash = hashlib.sha1(
        _site_name_key(
            normalized_name
        ).encode("utf-8")
    ).hexdigest()[:8].upper()

    return f"AUTO_SITE_{fallback_hash}"


def _short_site_hash(site_key):
    """
    Return a short deterministic suffix for ID collisions.
    """

    return hashlib.sha1(
        site_key.encode("utf-8")
    ).hexdigest()[:8].upper()


def assign_site_ids(dataframe):
    """
    Normalize site names and assign one stable site ID per site.

    Existing site IDs are preserved.

    Missing IDs reuse an existing ID for the same normalized
    site name when available. Otherwise a readable AUTO_ ID is
    generated.

    Generated slug collisions receive deterministic hash
    suffixes rather than row-order-based numbering.
    """

    if "site_name" not in dataframe.columns:
        raise SiteIdentityError(
            "A site_name column is required "
            "to resolve site identity."
        )

    result = dataframe.copy()

    result["site_name"] = result[
        "site_name"
    ].map(normalize_site_name)

    if "site_id" not in result.columns:
        result["site_id"] = None

    site_keys = result[
        "site_name"
    ].map(_site_name_key)

    key_to_name = {}

    for site_key, site_name in zip(
        site_keys,
        result["site_name"],
    ):
        key_to_name.setdefault(
            site_key,
            site_name,
        )

    key_to_existing_id = {}
    existing_id_to_key = {}

    for site_key in site_keys.unique():
        matching_rows = result.loc[
            site_keys == site_key,
            "site_id",
        ]

        existing_ids = {
            str(value).strip()
            for value in matching_rows
            if (
                not pd.isna(value)
                and str(value).strip()
            )
        }

        if len(existing_ids) > 1:
            raise SiteIdentityError(
                "The same normalized site name has "
                "multiple different site IDs."
            )

        if existing_ids:
            existing_id = next(
                iter(existing_ids)
            )

            previous_key = (
                existing_id_to_key.get(
                    existing_id
                )
            )

            if (
                previous_key is not None
                and previous_key != site_key
            ):
                raise SiteIdentityError(
                    "The same site ID is assigned to "
                    "multiple different site names."
                )

            existing_id_to_key[
                existing_id
            ] = site_key

            key_to_existing_id[
                site_key
            ] = existing_id

    generated_keys = [
        site_key
        for site_key in key_to_name
        if site_key not in key_to_existing_id
    ]

    generated_bases = {
        site_key: _site_id_slug(
            key_to_name[site_key]
        )
        for site_key in generated_keys
    }

    base_counts = {}

    for base_id in generated_bases.values():
        base_counts[base_id] = (
            base_counts.get(
                base_id,
                0,
            )
            + 1
        )

    used_ids = set(
        existing_id_to_key
    )

    key_to_final_id = dict(
        key_to_existing_id
    )

    for site_key in generated_keys:
        base_id = generated_bases[
            site_key
        ]

        needs_suffix = (
            base_counts[base_id] > 1
            or base_id in used_ids
        )

        if needs_suffix:
            generated_id = (
                f"{base_id}_"
                f"{_short_site_hash(site_key)}"
            )
        else:
            generated_id = base_id

        if generated_id in used_ids:
            raise SiteIdentityError(
                "Generated site ID collision could "
                "not be resolved safely."
            )

        key_to_final_id[
            site_key
        ] = generated_id

        used_ids.add(
            generated_id
        )

    result["site_id"] = site_keys.map(
        key_to_final_id
    )

    return result

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