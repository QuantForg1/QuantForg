"""Identity and naming value objects."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Self

from pydantic import field_validator

from app.domain.exceptions.base import ValidationError
from app.domain.value_objects.base import ValueObject

_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9._\-]{0,31}$")
_ACCOUNT_PATTERN = re.compile(r"^[A-Za-z0-9\-_]{3,64}$")
_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+([.-][A-Za-z0-9]+)?$")


class SymbolCode(ValueObject):
    """Canonical instrument code (e.g. ``EURUSD``, ``XAUUSD``).

    Why it exists
    -------------
    Symbol codes are referenced across Order, Position, Trade, and Signal.
    Normalising to uppercase and validating format keeps references consistent.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        code = raw.strip().upper()
        if not _SYMBOL_PATTERN.match(code):
            raise ValidationError(
                "Symbol code must be 1-32 chars of A-Z, 0-9, '.', '_', '-'",
                details={"field": "symbol_code", "value": raw},
            )
        return code

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class AccountNumber(ValueObject):
    """External broker account number / login identifier.

    Why it exists
    -------------
    Trading accounts are identified at the broker by an account number.
    This VO validates length and character set without assuming any broker API.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        number = raw.strip()
        if not _ACCOUNT_PATTERN.match(number):
            raise ValidationError(
                "Account number must be 3-64 alphanumeric characters "
                "(hyphen and underscore allowed)",
                details={"field": "account_number", "value": raw},
            )
        return number

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class PersonName(ValueObject):
    """Non-blank display name for a person or organisation.

    Why it exists
    -------------
    User display names and broker names share the same non-empty / max-length
    invariant. Centralising it avoids duplicated validation.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        name = raw.strip()
        if not name:
            raise ValidationError(
                "Name must not be blank",
                details={"field": "name"},
            )
        if len(name) > 255:
            raise ValidationError(
                "Name must be at most 255 characters",
                details={"field": "name"},
            )
        return name

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class EntitySlug(ValueObject):
    """URL-safe lowercase slug for catalogue entities.

    Why it exists
    -------------
    StrategyMetadata and similar catalogue records need a stable, human-readable
    key distinct from their UUID identity.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        slug = raw.strip().lower()
        if not _SLUG_PATTERN.match(slug):
            raise ValidationError(
                "Slug must be lowercase kebab-case (a-z, 0-9, hyphens)",
                details={"field": "slug", "value": raw},
            )
        if len(slug) > 64:
            raise ValidationError(
                "Slug must be at most 64 characters",
                details={"field": "slug"},
            )
        return slug

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class Leverage(ValueObject):
    """Account leverage expressed as a ratio numerator (e.g. 100 for 1:100).

    Why it exists
    -------------
    Trading accounts declare maximum leverage. The domain constrains it to a
    sensible positive integer range without implementing margin calculations.
    """

    value: int

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: int) -> int:
        if raw < 1 or raw > 2000:
            raise ValidationError(
                "Leverage must be between 1 and 2000",
                details={"field": "leverage", "value": raw},
            )
        return raw

    @classmethod
    def of(cls, value: int) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return f"1:{self.value}"


class VersionLabel(ValueObject):
    """Semantic-ish version label for catalogue metadata (e.g. ``1.0.0``).

    Why it exists
    -------------
    StrategyMetadata versions need a constrained string format without
    pulling in a full semver library at the domain boundary.
    """

    value: str

    @field_validator("value")
    @classmethod
    def _validate(cls, raw: str) -> str:
        label = raw.strip()
        if not _VERSION_PATTERN.match(label):
            raise ValidationError(
                "Version must look like MAJOR.MINOR.PATCH (optional pre-release)",
                details={"field": "version", "value": raw},
            )
        return label

    @classmethod
    def of(cls, value: str) -> Self:
        return cls(value=value)

    def __str__(self) -> str:
        return self.value


class PipSize(ValueObject):
    """Minimum price increment (pip / point size) for a symbol.

    Why it exists
    -------------
    Symbols declare their pip size as market metadata. The VO ensures it is
    strictly positive — it does not compute pip values or P&L.
    """

    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _validate(cls, raw: object) -> Decimal:
        if isinstance(raw, float):
            raise ValidationError(
                "Pip size must not be constructed from float",
                details={"field": "pip_size"},
            )
        value = Decimal(str(raw))
        if value <= 0:
            raise ValidationError(
                "Pip size must be strictly positive",
                details={"field": "pip_size", "value": str(value)},
            )
        return value

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        return cls(value=value)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return str(self.value)
