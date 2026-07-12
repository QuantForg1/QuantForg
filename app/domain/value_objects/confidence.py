"""Confidence score value object for signals."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject


class Confidence(ValueObject):
    """Signal confidence in the inclusive range 0.0-1.0.

    Why it exists
    -------------
    Signals may carry a confidence score. Constraining the range keeps
    downstream consumers from misinterpreting unbounded scores. This is
    metadata only — not a prediction engine.
    """

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        if isinstance(raw, float):
            # Allow float only for confidence via Decimal conversion of str
            # to avoid binary float surprises — require str/Decimal/int.
            raise ValidationError(
                "Confidence must not be constructed from float; use Decimal or str",
                details={"field": "confidence"},
            )
        value = Decimal(str(raw))
        if not value.is_finite() or value < 0 or value > 1:
            raise ValidationError(
                "Confidence must be between 0 and 1 inclusive",
                details={"field": "confidence", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)
