import re
from numbers import Integral, Real


class QuantityParseError(ValueError):
    """Raised when a quantity cannot be safely converted to individual units."""

class NormalizationError(ValueError):
    """Raised when a product or size cannot be safely normalized."""


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