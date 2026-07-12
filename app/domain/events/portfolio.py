"""Portfolio synchronization domain events — read-only facts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class PortfolioSynchronized(DomainEvent):
    """Emitted when a full portfolio sync completes."""

    event_type: ClassVar[str] = "portfolio.synchronized"
    user_id: UUID
    sync_id: UUID
    login: int
    position_count: int
    pending_order_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "sync_id": str(self.sync_id),
                "login": self.login,
                "position_count": self.position_count,
                "pending_order_count": self.pending_order_count,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PositionOpenedDetected(DomainEvent):
    """Emitted when a previously unseen open position appears."""

    event_type: ClassVar[str] = "portfolio.position_opened_detected"
    user_id: UUID
    ticket: int
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "ticket": self.ticket,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PositionClosedDetected(DomainEvent):
    """Emitted when a previously open position is no longer present."""

    event_type: ClassVar[str] = "portfolio.position_closed_detected"
    user_id: UUID
    ticket: int
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "ticket": self.ticket,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class PendingOrderDetected(DomainEvent):
    """Emitted when a new pending order is observed."""

    event_type: ClassVar[str] = "portfolio.pending_order_detected"
    user_id: UUID
    ticket: int
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "ticket": self.ticket,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountUpdated(DomainEvent):
    """Emitted when account balance/equity snapshot changes."""

    event_type: ClassVar[str] = "portfolio.account_updated"
    user_id: UUID
    login: int
    equity: str
    balance: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "login": self.login,
                "equity": self.equity,
                "balance": self.balance,
            }
        )
        return payload
