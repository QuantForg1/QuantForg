"""Tick — single market price observation at a point in time.

Why it exists
-------------
A Tick is the finest-grained market-data atom: one price (and optional
volume) for one symbol at one UTC instant. Multiple symbols are supported
via ``symbol_code``. Ticks are immutable once recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import (
    ensure_non_negative_decimal,
    ensure_price,
    ensure_utc,
)
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, kw_only=True, slots=True)
class Tick:
    """Immutable tick observation for a single symbol."""

    symbol_code: SymbolCode
    price: Price
    timestamp: datetime
    id: UUID = field(default_factory=uuid4)
    symbol_id: UUID | None = None
    volume: Decimal | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", ensure_utc(self.timestamp, field="timestamp")
        )
        require(
            isinstance(self.symbol_code, SymbolCode),
            "symbol_code must be a SymbolCode",
        )
        require(isinstance(self.price, Price), "price must be a Price")
        if self.volume is not None:
            object.__setattr__(
                self,
                "volume",
                ensure_non_negative_decimal(self.volume, field="volume"),
            )

    @classmethod
    def create(
        cls,
        *,
        symbol_code: str | SymbolCode,
        price: Price | Decimal | int | str,
        timestamp: datetime | None = None,
        volume: Decimal | int | str | None = None,
        symbol_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: build a validated tick observation."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        vol = (
            None
            if volume is None
            else ensure_non_negative_decimal(volume, field="volume")
        )
        kwargs: dict[str, object] = {
            "symbol_code": code,
            "price": ensure_price(price, field="price"),
            "timestamp": timestamp or datetime.now(UTC),
            "volume": vol,
            "symbol_id": symbol_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "symbol_id": str(self.symbol_id) if self.symbol_id else None,
            "price": str(self.price),
            "volume": str(self.volume) if self.volume is not None else None,
            "timestamp": self.timestamp.isoformat(),
        }
