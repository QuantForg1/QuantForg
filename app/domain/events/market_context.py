"""Market-context domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketContextCreated(DomainEvent):
    """Emitted when a :class:`MarketContext` aggregate is first created.

    Why it exists
    -------------
    Notifies subscribers that a market-context record now exists for a market
    (and optional symbol) without coupling creators to consumers.
    """

    event_type: ClassVar[str] = "market_context.created"
    context_id: UUID
    market_code: str
    session: str
    market_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "context_id": str(self.context_id),
                "market_code": self.market_code,
                "session": self.session,
                "market_state": self.market_state,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketContextUpdated(DomainEvent):
    """Emitted when market-context fields are refreshed."""

    event_type: ClassVar[str] = "market_context.updated"
    context_id: UUID
    market_code: str
    session: str
    market_state: str
    liquidity_level: str
    volatility_level: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "context_id": str(self.context_id),
                "market_code": self.market_code,
                "session": self.session,
                "market_state": self.market_state,
                "liquidity_level": self.liquidity_level,
                "volatility_level": self.volatility_level,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class SessionChanged(DomainEvent):
    """Emitted when the resolved trading session changes."""

    event_type: ClassVar[str] = "market_context.session_changed"
    context_id: UUID
    market_code: str
    previous_session: str
    current_session: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "context_id": str(self.context_id),
                "market_code": self.market_code,
                "previous_session": self.previous_session,
                "current_session": self.current_session,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketOpened(DomainEvent):
    """Emitted when market state transitions into an open trading state."""

    event_type: ClassVar[str] = "market_context.opened"
    context_id: UUID
    market_code: str
    session: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "context_id": str(self.context_id),
                "market_code": self.market_code,
                "session": self.session,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MarketClosed(DomainEvent):
    """Emitted when market state transitions into a closed/holiday/weekend state."""

    event_type: ClassVar[str] = "market_context.closed"
    context_id: UUID
    market_code: str
    market_state: str
    session: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "context_id": str(self.context_id),
                "market_code": self.market_code,
                "market_state": self.market_state,
                "session": self.session,
            }
        )
        return payload
