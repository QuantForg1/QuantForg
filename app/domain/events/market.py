"""Market-data domain events.

These events announce that market observations were produced or stored.
They do not trigger trade execution, indicator calculation, or strategy
logic — consumers decide what to do with them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent
from app.domain.market_data.candle import Candle
from app.domain.market_data.quote import Quote
from app.domain.market_data.snapshot import MarketSnapshot
from app.domain.market_data.spread import Spread
from app.domain.market_data.tick import Tick


@dataclass(frozen=True, kw_only=True, slots=True)
class TickReceived(DomainEvent):
    """Emitted when a new tick observation is accepted by the system.

    Why it exists
    -------------
    Notifies subscribers that a fresh last-traded / last-quoted price point
    is available for a symbol — without coupling producers to storage or UI.
    """

    event_type: ClassVar[str] = "market.tick_received"
    tick: Tick

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["tick"] = self.tick.to_dict()
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class QuoteUpdated(DomainEvent):
    """Emitted when a bid/ask quote is updated for a symbol."""

    event_type: ClassVar[str] = "market.quote_updated"
    quote: Quote

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["quote"] = self.quote.to_dict()
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class CandleClosed(DomainEvent):
    """Emitted when a candle period completes (bar close).

    Why it exists
    -------------
    Closed candles are immutable historical bars. Downstream analytics may
    subscribe later — this sprint only announces the fact.
    """

    event_type: ClassVar[str] = "market.candle_closed"
    candle: Candle

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["candle"] = self.candle.to_dict()
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class SpreadObserved(DomainEvent):
    """Emitted when a spread observation is recorded for a symbol."""

    event_type: ClassVar[str] = "market.spread_observed"
    spread: Spread

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["spread"] = self.spread.to_dict()
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketSnapshotCaptured(DomainEvent):
    """Emitted when a multi-field market snapshot is captured.

    Why it exists
    -------------
    Snapshots aggregate tick/quote/candle state for one or more symbols at
    a point in time — useful for auditing and later UI, without executing
    trades.
    """

    event_type: ClassVar[str] = "market.snapshot_captured"
    snapshot: MarketSnapshot

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["snapshot"] = self.snapshot.to_dict()
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketDataStored(DomainEvent):
    """Emitted after a market-data record is successfully stored via a port.

    Why it exists
    -------------
    Separates "observation accepted" from "observation persisted" so
    storage adapters can confirm durability independently of providers.
    """

    event_type: ClassVar[str] = "market.data_stored"
    record_type: str
    record_id: UUID
    symbol_code: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "record_type": self.record_type,
                "record_id": str(self.record_id),
                "symbol_code": self.symbol_code,
            }
        )
        return payload
