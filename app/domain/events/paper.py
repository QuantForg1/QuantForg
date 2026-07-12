"""Paper Trading domain events — simulation facts only, never live fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class PaperTradeOpened(DomainEvent):
    """Emitted when a paper position is opened from a fill."""

    event_type: ClassVar[str] = "paper.trade_opened"
    user_id: UUID
    position_id: UUID
    order_id: UUID
    symbol: str
    side: str
    volume: str
    entry_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "position_id": str(self.position_id),
                "order_id": str(self.order_id),
                "symbol": self.symbol,
                "side": self.side,
                "volume": self.volume,
                "entry_price": self.entry_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PaperTradeClosed(DomainEvent):
    """Emitted when a paper position (or partial) is closed."""

    event_type: ClassVar[str] = "paper.trade_closed"
    user_id: UUID
    position_id: UUID
    symbol: str
    volume: str
    pnl: str
    fully_closed: bool

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "position_id": str(self.position_id),
                "symbol": self.symbol,
                "volume": self.volume,
                "pnl": self.pnl,
                "fully_closed": self.fully_closed,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PaperOrderFilled(DomainEvent):
    """Emitted when the virtual broker fills a paper order."""

    event_type: ClassVar[str] = "paper.order_filled"
    user_id: UUID
    order_id: UUID
    symbol: str
    fill_price: str
    filled_volume: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "order_id": str(self.order_id),
                "symbol": self.symbol,
                "fill_price": self.fill_price,
                "filled_volume": self.filled_volume,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PaperOrderRejected(DomainEvent):
    """Emitted when the virtual broker rejects a paper order."""

    event_type: ClassVar[str] = "paper.order_rejected"
    user_id: UUID
    order_id: UUID
    symbol: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "order_id": str(self.order_id),
                "symbol": self.symbol,
                "reason": self.reason,
            }
        )
        return payload
