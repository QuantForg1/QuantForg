"""Quote — bid/ask price pair for a symbol.

Why it exists
-------------
A Quote captures the best available bid and ask at a UTC instant. It is the
basis for spread calculation and market snapshots. Quotes are immutable and
support multiple symbols via ``symbol_code``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Self
from uuid import UUID, uuid4

from app.domain.entities._guards import require
from app.domain.market_data._validation import ensure_price, ensure_utc
from app.domain.market_data.spread import Spread
from app.domain.value_objects.identity import SymbolCode
from app.domain.value_objects.market import Price


@dataclass(frozen=True, kw_only=True, slots=True)
class Quote:
    """Immutable bid/ask quote for a single symbol."""

    symbol_code: SymbolCode
    bid: Price
    ask: Price
    timestamp: datetime
    id: UUID = field(default_factory=uuid4)
    symbol_id: UUID | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "timestamp", ensure_utc(self.timestamp, field="timestamp")
        )
        require(
            isinstance(self.symbol_code, SymbolCode), "symbol_code must be a SymbolCode"
        )
        require(isinstance(self.bid, Price), "bid must be a Price")
        require(isinstance(self.ask, Price), "ask must be a Price")
        require(
            self.ask.value >= self.bid.value,
            "ask must be greater than or equal to bid",
            bid=str(self.bid),
            ask=str(self.ask),
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
        """Factory: build a validated quote."""
        code = (
            symbol_code
            if isinstance(symbol_code, SymbolCode)
            else SymbolCode(value=symbol_code)
        )
        kwargs: dict[str, object] = {
            "symbol_code": code,
            "bid": ensure_price(bid, field="bid"),
            "ask": ensure_price(ask, field="ask"),
            "timestamp": timestamp or datetime.now(UTC),
            "symbol_id": symbol_id,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    @property
    def mid(self) -> Price:
        """Mid price ``(bid + ask) / 2``."""
        mid = (self.bid.value + self.ask.value) / Decimal("2")
        return Price(value=mid)

    def to_spread(self) -> Spread:
        """Derive an immutable :class:`Spread` observation from this quote."""
        return Spread.from_quote(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol_code": str(self.symbol_code),
            "symbol_id": str(self.symbol_id) if self.symbol_id else None,
            "bid": str(self.bid),
            "ask": str(self.ask),
            "mid": str(self.mid),
            "timestamp": self.timestamp.isoformat(),
        }
