"""Spread — difference between ask and bid.

Why it exists
-------------
Spread is a first-class market observation used for monitoring liquidity
conditions. It can be derived from a Quote or recorded directly. Immutable.
Does not imply trading or execution decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import (
    ensure_non_negative_decimal,
    ensure_price,
    ensure_utc,
)
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price

if TYPE_CHECKING:
    from app.domain.market_data.quote import Quote


@dataclass(frozen=True, kw_only=True, slots=True)
class Spread:
    """Immutable spread observation for a single symbol."""

    symbol_code: SymbolCode
    bid: Price
    ask: Price
    value: Decimal
    timestamp: datetime
    id: UUID = field(default_factory=uuid4)
    symbol_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", ensure_utc(self.timestamp, field="timestamp")
        )
        object.__setattr__(
            self,
            "value",
            ensure_non_negative_decimal(self.value, field="value"),
        )
        require(
            isinstance(self.symbol_code, SymbolCode), "symbol_code must be a SymbolCode"
        )
        require(self.ask.value >= self.bid.value, "ask must be >= bid")
        expected = self.ask.value - self.bid.value
        require(
            self.value == expected,
            "spread value must equal ask - bid",
            value=str(self.value),
            expected=str(expected),
        )

    @classmethod
    def create(
        cls,
        *,
        symbol_code: str | SymbolCode,
        bid: Price | Decimal | int | str,
        ask: Price | Decimal | int | str,
        timestamp: datetime | None = None,
        symbol_id: UUID | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: build a spread from bid/ask prices."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        bid_p = ensure_price(bid, field="bid")
        ask_p = ensure_price(ask, field="ask")
        kwargs: dict[str, object] = {
            "symbol_code": code,
            "bid": bid_p,
            "ask": ask_p,
            "value": ask_p.value - bid_p.value,
            "timestamp": timestamp or datetime.now(UTC),
            "symbol_id": symbol_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    @classmethod
    def from_quote(cls, quote: Quote) -> Self:
        """Factory: derive a spread from an existing quote."""
        return cls.create(
            symbol_code=quote.symbol_code,
            bid=quote.bid,
            ask=quote.ask,
            timestamp=quote.timestamp,
            symbol_id=quote.symbol_id,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "symbol_id": str(self.symbol_id) if self.symbol_id else None,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "value": str(self.value),
            "timestamp": self.timestamp.isoformat(),
        }
