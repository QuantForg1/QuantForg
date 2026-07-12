"""Liquidity domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityPoolDetected(DomainEvent):
    """Emitted when a new liquidity pool is identified."""

    event_type: ClassVar[str] = "liquidity.pool_detected"
    pool_id: UUID
    symbol_code: str
    timeframe: str
    side: str
    price: str
    strength: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "pool_id": str(self.pool_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "side": self.side,
                "price": self.price,
                "strength": self.strength,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityZoneCreated(DomainEvent):
    """Emitted when a new liquidity zone is built."""

    event_type: ClassVar[str] = "liquidity.zone_created"
    zone_id: UUID
    symbol_code: str
    timeframe: str
    side: str
    low_price: str
    high_price: str
    pool_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "zone_id": str(self.zone_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "side": self.side,
                "low_price": self.low_price,
                "high_price": self.high_price,
                "pool_count": self.pool_count,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquiditySweepDetected(DomainEvent):
    """Emitted when a liquidity pool is swept."""

    event_type: ClassVar[str] = "liquidity.sweep_detected"
    sweep_id: UUID
    symbol_code: str
    timeframe: str
    kind: str
    pool_id: UUID
    sweep_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "sweep_id": str(self.sweep_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "kind": self.kind,
                "pool_id": str(self.pool_id),
                "sweep_price": self.sweep_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class LiquidityStateChanged(DomainEvent):
    """Emitted when classified liquidity state changes vs prior snapshot."""

    event_type: ClassVar[str] = "liquidity.state_changed"
    symbol_code: str
    timeframe: str
    previous_kind: str
    current_kind: str
    state_id: UUID

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_kind": self.previous_kind,
                "current_kind": self.current_kind,
                "state_id": str(self.state_id),
            }
        )
        return payload
