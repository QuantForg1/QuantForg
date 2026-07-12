"""Price and quantity value objects for market instruments."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject


def _to_decimal(raw: object, *, field: str) -> Decimal:
    if isinstance(raw, Decimal):
        value = raw
    elif isinstance(raw, int | str):
        value = Decimal(str(raw))
    elif isinstance(raw, float):
        raise ValidationError(
            f"{field} must not be constructed from float; use Decimal or str",
            details={"field": field},
        )
    else:
        raise ValidationError(
            f"{field} type is unsupported",
            details={"field": field, "type": type(raw).__name__},
        )
    if not value.is_finite():
        raise ValidationError(
            f"{field} must be a finite number",
            details={"field": field},
        )
    return value


class Price(ValueObject):
    """Non-negative market price expressed as an exact Decimal.

    Why it exists
    -------------
    Orders, positions, and trades all need a validated price. Centralising
    the rule prevents negative or non-finite prices from entering aggregates.
    """

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="price")
        if value < 0:
            raise ValidationError(
                "Price must be non-negative",
                details={"field": "price", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)


class Quantity(ValueObject):
    """Strictly positive tradeable quantity (lots / units).

    Why it exists
    -------------
    Volume on orders, positions, and trades must be > 0. This VO encodes
    that invariant once for the whole domain.
    """

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="quantity")
        if value <= 0:
            raise ValidationError(
                "Quantity must be strictly positive",
                details={"field": "quantity", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __add__(self, other: Quantity) -> Quantity:
        return Quantity(value=self.value + other.value)

    def __sub__(self, other: Quantity) -> Quantity:
        result = self.value - other.value
        if result <= 0:
            raise ValidationError(
                "Quantity subtraction must leave a strictly positive result",
                details={"left": str(self.value), "right": str(other.value)},
            )
        return Quantity(value=result)

    def __str__(self) -> str:
        return str(self.value)


class Percentage(ValueObject):
    """Percentage in the inclusive range 0-100.

    Why it exists
    -------------
    Risk limits (max risk per trade, max daily loss) are expressed as
    percentages. This VO rejects out-of-range values at the boundary.
    """

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="percentage")
        if value < 0 or value > 100:
            raise ValidationError(
                "Percentage must be between 0 and 100 inclusive",
                details={"field": "percentage", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def as_ratio(self) -> Decimal:
        """Return the percentage as a 0-1 ratio."""
        return self.value / Decimal("100")

    def __str__(self) -> str:
        return f"{self.value}%"
