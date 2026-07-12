"""Shared helpers for market-data immutable records."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.market import Price


def ensure_utc(moment: datetime, *, field: str) -> datetime:
    """Normalise a datetime to timezone-aware UTC."""
    _ = field  # kept for call-site symmetry with sibling helpers
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def ensure_price(value: Price | Decimal | int | str, *, field: str) -> Price:
    """Coerce raw input to a validated :class:`Price`."""
    _ = field  # kept for call-site symmetry with sibling helpers
    if isinstance(value, Price):
        return value
    return Price.of(value)


def ensure_non_negative_decimal(
    value: Decimal | int | str,
    *,
    field: str,
) -> Decimal:
    """Coerce to a finite non-negative Decimal (rejects float)."""
    if isinstance(value, float):
        raise ValidationError(
            f"{field} must not be constructed from float; use Decimal or str",
            details={"field": field},
        )
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    if not amount.is_finite():
        raise ValidationError(
            f"{field} must be a finite number",
            details={"field": field},
        )
    if amount < 0:
        raise ValidationError(
            f"{field} must be non-negative",
            details={"field": field, "value": str(amount)},
        )
    return amount
