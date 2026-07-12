"""MT5 market-data domain events (Sprint 2).

``TickReceived`` already exists in ``app.domain.events.market`` and is
re-exported here. ``CandleReceived`` and ``MarketDataUpdated`` are new.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from app.domain.events.base import DomainEvent
from app.domain.events.market import TickReceived
from app.domain.market_data.candle import Candle

__all__ = [
    "CandleReceived",
    "MarketDataUpdated",
    "TickReceived",
]


@dataclass(frozen=True, kw_only=True, slots=True)
class CandleReceived(DomainEvent):
    """Emitted when candle/rate bars are retrieved from MT5."""

    event_type: ClassVar[str] = "market.candle_received"
    candle: Candle
    source: str = "mt5"

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload["candle"] = self.candle.to_dict()
        payload["source"] = self.source
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketDataUpdated(DomainEvent):
    """Emitted when MT5 market-data state changes for a symbol."""

    event_type: ClassVar[str] = "market.data_updated"
    symbol: str
    kind: str  # tick | candle | symbol
    timeframe: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "symbol": self.symbol,
                "kind": self.kind,
                "timeframe": self.timeframe,
                "detail": self.detail,
            }
        )
        return payload
