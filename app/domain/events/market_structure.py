"""Market structure domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class SwingDetected(DomainEvent):
    """Emitted when one or more swing points are confirmed."""

    event_type: ClassVar[str] = "market_structure.swing_detected"
    symbol_code: str
    timeframe: str
    swing_id: UUID
    kind: str
    price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "swing_id": str(self.swing_id),
                "kind": self.kind,
                "price": self.price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class StructureChanged(DomainEvent):
    """Emitted when a new structure snapshot is produced."""

    event_type: ClassVar[str] = "market_structure.structure_changed"
    snapshot_id: UUID
    symbol_code: str
    timeframe: str
    trend_direction: str
    node_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "snapshot_id": str(self.snapshot_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "trend_direction": self.trend_direction,
                "node_count": self.node_count,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class BreakOfStructureDetected(DomainEvent):
    """Emitted when a Break of Structure (BOS) is identified."""

    event_type: ClassVar[str] = "market_structure.bos_detected"
    bos_id: UUID
    symbol_code: str
    timeframe: str
    trend_direction: str
    break_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "bos_id": str(self.bos_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "trend_direction": self.trend_direction,
                "break_price": self.break_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class ChangeOfCharacterDetected(DomainEvent):
    """Emitted when a Change of Character (CHoCH) is identified."""

    event_type: ClassVar[str] = "market_structure.choch_detected"
    choch_id: UUID
    symbol_code: str
    timeframe: str
    previous_trend: str
    break_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "choch_id": str(self.choch_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_trend": self.previous_trend,
                "break_price": self.break_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class TrendChanged(DomainEvent):
    """Emitted when classified trend direction changes vs prior snapshot."""

    event_type: ClassVar[str] = "market_structure.trend_changed"
    symbol_code: str
    timeframe: str
    previous_direction: str
    current_direction: str
    trend_id: UUID

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_direction": self.previous_direction,
                "current_direction": self.current_direction,
                "trend_id": str(self.trend_id),
            }
        )
        return payload
