"""Vietnamese number formatting shared by the report screens and exports."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

DISPLAY_QUANTUM = Decimal("0.01")
EMPTY_VALUE = "—"


def format_vi_number(value) -> str:
    """Return ``1.234`` or ``1.200,5`` for a report value.

    Values are displayed with at most two decimal places. Trailing zeros are
    dropped. ``None`` is rendered as a dash so table cells stay readable; the
    Excel writer never calls this helper for numeric cells.
    """
    if value is None or value == "":
        return EMPTY_VALUE

    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return EMPTY_VALUE

    if not number.is_finite():
        return EMPTY_VALUE

    number = number.quantize(DISPLAY_QUANTUM, rounding=ROUND_HALF_UP)
    negative = number < 0
    text = format(abs(number), "f")
    integer_part, _, fraction_part = text.partition(".")
    integer_part = f"{int(integer_part):,}".replace(",", ".")
    fraction_part = fraction_part.rstrip("0")
    result = integer_part
    if fraction_part:
        result = f"{result},{fraction_part}"
    return f"-{result}" if negative else result
