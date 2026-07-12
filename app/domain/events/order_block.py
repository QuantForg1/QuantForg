"""Order-block domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockDetected(DomainEvent):
    """Emitted when a new order block is detected."""

    event_type: ClassVar[str] = "order_block.detected"
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    side: str
    state: str
    low_price: str
    high_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "side": self.side,
                "state": self.state,
                "low_price": self.low_price,
                "high_price": self.high_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockValidated(DomainEvent):
    """Emitted when a detected order block passes validation."""

    event_type: ClassVar[str] = "order_block.validated"
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    side: str
    quality_score: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "side": self.side,
                "quality_score": self.quality_score,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BreakerDetected(DomainEvent):
    """Emitted when an order block is broken into a breaker."""

    event_type: ClassVar[str] = "order_block.breaker_detected"
    breaker_id: UUID
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    break_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "breaker_id": str(self.breaker_id),
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "break_price": self.break_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class MitigationDetected(DomainEvent):
    """Emitted when price mitigates an order-block zone."""

    event_type: ClassVar[str] = "order_block.mitigation_detected"
    mitigation_id: UUID
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    kind: str
    touch_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "mitigation_id": str(self.mitigation_id),
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "kind": self.kind,
                "touch_price": self.touch_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockExpired(DomainEvent):
    """Emitted when an order block expires without further relevance."""

    event_type: ClassVar[str] = "order_block.expired"
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    previous_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_state": self.previous_state,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class OrderBlockStateChanged(DomainEvent):
    """Emitted on any order-block lifecycle state transition."""

    event_type: ClassVar[str] = "order_block.state_changed"
    order_block_id: UUID
    symbol_code: str
    timeframe: str
    previous_state: str
    current_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "order_block_id": str(self.order_block_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_state": self.previous_state,
                "current_state": self.current_state,
            }
        )
        return payload
