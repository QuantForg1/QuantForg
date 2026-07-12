"""Currency and money value objects."""

from __future__ import annotations

from decimal import Decimal
from typing import Self

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject

_SUPPORTED_CURRENCIES = frozenset(
    {
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "AUD",
        "CAD",
        "NZD",
        "CNY",
        "HKD",
        "SGD",
        "BTC",
        "ETH",
        "USDT",
    }
)


class CurrencyCode(ValueObject):
    """ISO-like currency / asset code used for monetary amounts.

    Why it exists
    -------------
    Prevents free-form currency strings across Money, Symbol, and Account.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate_code(cls, raw: str) -> str:
        code = raw.strip().upper()
        if len(code) < 3 or len(code) > 10:
            raise ValidationError(
                "Currency code must be 3-10 characters",
                details={"field": "currency", "value": raw},
            )
        if not code.isalnum():
            raise ValidationError(
                "Currency code must be alphanumeric",
                details={"field": "currency", "value": raw},
            )
        return code

    @property
    def is_known(self) -> bool:
        """Return True when the code is in the known supported set."""
        return self.value in _SUPPORTED_CURRENCIES

    def __str__(self) -> str:
        return self.value


class Money(ValueObject):
    """Immutable monetary amount with currency.

    Why it exists
    -------------
    Financial quantities must never be bare floats. Money pairs an exact
    ``Decimal`` amount with a currency and forbids cross-currency arithmetic.
    """

    amount: Decimal
    currency: CurrencyCode

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, raw: object) -> Decimal:
        if isinstance(raw, Decimal):
            value = raw
        elif isinstance(raw, int | str):
            value = Decimal(str(raw))
        elif isinstance(raw, float):
            raise ValidationError(
                "Money amount must not be constructed from float; use Decimal or str",
                details={"field": "amount"},
            )
        else:
            raise ValidationError(
                "Money amount type is unsupported",
                details={"field": "amount", "type": type(raw).__name__},
            )
        if not value.is_finite():
            raise ValidationError(
                "Money amount must be a finite number",
                details={"field": "amount"},
            )
        return value

    @classmethod
    def of(cls, amount: Decimal | int | str, currency: str) -> Self:
        """Factory: construct Money from a raw amount and currency code."""
        return cls(amount=amount, currency=CurrencyCode(value=currency))  # type: ignore[arg-type]

    @classmethod
    def zero(cls, currency: str) -> Self:
        """Factory: zero balance in the given currency."""
        return cls.of(Decimal("0"), currency)

    def ensure_same_currency(self, other: Money) -> None:
        """Raise if ``other`` uses a different currency."""
        if self.currency != other.currency:
            raise ValidationError(
                "Currency mismatch",
                details={
                    "left": self.currency.value,
                    "right": other.currency.value,
                },
            )

    def add(self, other: Money) -> Money:
        """Return a new Money equal to this amount plus ``other``."""
        self.ensure_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: Money) -> Money:
        """Return a new Money equal to this amount minus ``other``."""
        self.ensure_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def is_negative(self) -> bool:
        return self.amount < 0

    def is_zero(self) -> bool:
        return self.amount == 0

    def __str__(self) -> str:
        return f"{self.amount} {self.currency.value}"
