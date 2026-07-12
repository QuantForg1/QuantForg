"""Symbol aggregate — tradable instrument metadata.

Why this entity exists
----------------------
Orders, positions, trades, and signals all reference a Symbol. This
aggregate holds instrument identity (code), asset class, quote currencies,
pip size, and digits. It is market *catalogue* data — not price feeds,
indicators, or charting logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.symbol import SymbolAssetClass, SymbolStatus
from app.domain.value_objects.identity import PersonName, PipSize, SymbolCode
from app.domain.value_objects.money import CurrencyCode


@dataclass(eq=False, kw_only=True)
class Symbol(Entity):
    """Rich domain model for a tradable symbol."""

    code: SymbolCode
    name: PersonName
    asset_class: SymbolAssetClass = SymbolAssetClass.FOREX
    status: SymbolStatus = SymbolStatus.ACTIVE
    base_currency: CurrencyCode = None  # type: ignore[assignment]
    quote_currency: CurrencyCode = None  # type: ignore[assignment]
    digits: int = 5
    pip_size: PipSize = None  # type: ignore[assignment]
    broker_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.base_currency is None:
            self.base_currency = CurrencyCode(value="EUR")
        if self.quote_currency is None:
            self.quote_currency = CurrencyCode(value="USD")
        if self.pip_size is None:
            self.pip_size = PipSize.of("0.0001")
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(
            0 <= self.digits <= 8, "digits must be between 0 and 8", digits=self.digits
        )
        require(
            self.base_currency != self.quote_currency,
            "base_currency and quote_currency must differ",
            base=self.base_currency.value,
            quote=self.quote_currency.value,
        )

    @classmethod
    def create(
        cls,
        *,
        code: str | SymbolCode,
        name: str | PersonName,
        asset_class: SymbolAssetClass = SymbolAssetClass.FOREX,
        base_currency: str = "EUR",
        quote_currency: str = "USD",
        digits: int = 5,
        pip_size: str | PipSize = "0.0001",
        broker_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create an ACTIVE symbol catalogue entry."""
        code_vo = code if isinstance(code, SymbolCode) else SymbolCode(value=code)
        name_vo = name if isinstance(name, PersonName) else PersonName(value=name)
        pip_vo = pip_size if isinstance(pip_size, PipSize) else PipSize.of(pip_size)
        kwargs: dict[str, object] = {
            "code": code_vo,
            "name": name_vo,
            "asset_class": asset_class,
            "status": SymbolStatus.ACTIVE,
            "base_currency": CurrencyCode(value=base_currency),
            "quote_currency": CurrencyCode(value=quote_currency),
            "digits": digits,
            "pip_size": pip_vo,
            "broker_id": broker_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def suspend(self) -> None:
        """Suspend trading on this symbol."""
        require_state(
            self.status == SymbolStatus.ACTIVE,
            "Only active symbols can be suspended",
            status=self.status.value,
        )
        self.status = SymbolStatus.SUSPENDED
        self.touch()

    def activate(self) -> None:
        """Re-activate a suspended symbol."""
        require_state(
            self.status == SymbolStatus.SUSPENDED,
            "Only suspended symbols can be activated",
            status=self.status.value,
        )
        self.status = SymbolStatus.ACTIVE
        self.touch()

    def delist(self) -> None:
        """Permanently delist the symbol."""
        require_state(
            self.status != SymbolStatus.DELISTED,
            "Symbol is already delisted",
            status=self.status.value,
        )
        self.status = SymbolStatus.DELISTED
        self.touch()

    @property
    def is_tradable(self) -> bool:
        return self.status == SymbolStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "code": str(self.code),
                "name": str(self.name),
                "asset_class": self.asset_class.value,
                "status": self.status.value,
                "base_currency": self.base_currency.value,
                "quote_currency": self.quote_currency.value,
                "digits": self.digits,
                "pip_size": str(self.pip_size),
                "broker_id": str(self.broker_id) if self.broker_id else None,
            }
        )
        return base
