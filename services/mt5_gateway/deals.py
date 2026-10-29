"""Deal-history field formatting.

A missing commission is not evidence of a zero tariff. A numeric zero is
preserved so callers can tell the two cases apart.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

_MISSING = object()


def deal_commission_text(deal: Any) -> str | None:
    """Return the broker commission text, or None when the field is absent."""
    raw = getattr(deal, "commission", _MISSING)
    if raw is _MISSING or raw is None:
        return None
    return str(raw)


def parse_reported_commission(value: Any) -> Decimal | None:
    """Parse a gateway commission field. Blank and null stay unknown."""
    if value is None or value == "":
        return None
    return Decimal(str(value))
