"""Fair Value Gap domain events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGapDetected(DomainEvent):
    """Emitted when a new fair value gap is detected."""

    event_type: ClassVar[str] = "fair_value_gap.detected"
    gap_id: UUID
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
                "gap_id": str(self.gap_id),
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
class GapFilled(DomainEvent):
    """Emitted when a gap is fully filled."""

    event_type: ClassVar[str] = "fair_value_gap.filled"
    fill_id: UUID
    gap_id: UUID
    symbol_code: str
    timeframe: str
    fill_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "fill_id": str(self.fill_id),
                "gap_id": str(self.gap_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "fill_price": self.fill_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class GapPartiallyFilled(DomainEvent):
    """Emitted when a gap is partially filled."""

    event_type: ClassVar[str] = "fair_value_gap.partially_filled"
    fill_id: UUID
    gap_id: UUID
    symbol_code: str
    timeframe: str
    fill_ratio: str
    fill_price: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "fill_id": str(self.fill_id),
                "gap_id": str(self.gap_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "fill_ratio": self.fill_ratio,
                "fill_price": self.fill_price,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class GapInvalidated(DomainEvent):
    """Emitted when a gap is invalidated by opposing close-through."""

    event_type: ClassVar[str] = "fair_value_gap.invalidated"
    gap_id: UUID
    symbol_code: str
    timeframe: str
    invalidate_price: str
    previous_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "gap_id": str(self.gap_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "invalidate_price": self.invalidate_price,
                "previous_state": self.previous_state,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGapExpired(DomainEvent):
    """Emitted when a gap expires."""

    event_type: ClassVar[str] = "fair_value_gap.expired"
    gap_id: UUID
    symbol_code: str
    timeframe: str
    previous_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "gap_id": str(self.gap_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_state": self.previous_state,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class FairValueGapStateChanged(DomainEvent):
    """Emitted on any FVG lifecycle state transition."""

    event_type: ClassVar[str] = "fair_value_gap.state_changed"
    gap_id: UUID
    symbol_code: str
    timeframe: str
    previous_state: str
    current_state: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "gap_id": str(self.gap_id),
                "symbol_code": self.symbol_code,
                "timeframe": self.timeframe,
                "previous_state": self.previous_state,
                "current_state": self.current_state,
            }
        )
        return payload
