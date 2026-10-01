import re
from numbers import Integral, Real


class QuantityParseError(ValueError):
    """Raised when a quantity cannot be safely converted to individual units."""


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