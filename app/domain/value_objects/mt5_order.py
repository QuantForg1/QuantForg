"""MT5 order-validation value objects — never used for live order_send."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject
from app.domain.value_objects.market import _to_decimal


class LotSize(ValueObject):
    """Trade volume in lots (exact Decimal, must be > 0)."""

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="lot_size")
        if value <= 0:
            raise ValidationError(
                "LotSize must be strictly positive",
                details={"field": "lot_size", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)


class StopLoss(ValueObject):
    """Optional stop-loss price (non-negative when set)."""

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="stop_loss")
        if value < 0:
            raise ValidationError(
                "StopLoss must be non-negative",
                details={"field": "stop_loss", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)


class TakeProfit(ValueObject):
    """Optional take-profit price (non-negative when set)."""

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        value = _to_decimal(raw, field="take_profit")
        if value < 0:
            raise ValidationError(
                "TakeProfit must be non-negative",
                details={"field": "take_profit", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)


class Slippage(ValueObject):
    """Maximum acceptable slippage in points (>= 0)."""

    value: int

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> int:
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise ValidationError(
                "Slippage must be an integer",
                details={"field": "slippage", "value": repr(raw)},
            )
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Slippage must be an integer",
                details={"field": "slippage", "value": repr(raw)},
            ) from exc
        if value < 0:
            raise ValidationError(
                "Slippage must be non-negative",
                details={"field": "slippage", "value": value},
            )
        return value

    @classmethod
    def of(cls, value: int) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return str(self.value)


class MagicNumber(ValueObject):
    """Expert Advisor magic number (>= 0)."""

    value: int

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> int:
        if isinstance(raw, bool) or not isinstance(raw, (int, str)):
            raise ValidationError(
                "MagicNumber must be an integer",
                details={"field": "magic_number", "value": repr(raw)},
            )
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "MagicNumber must be an integer",
                details={"field": "magic_number", "value": repr(raw)},
            ) from exc
        if value < 0:
            raise ValidationError(
                "MagicNumber must be non-negative",
                details={"field": "magic_number", "value": value},
            )
        return value

    @classmethod
    def of(cls, value: int) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return str(self.value)
