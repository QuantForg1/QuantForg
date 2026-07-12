"""Strategy Runtime domain events — decisions only, never fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class StrategyEvaluated(DomainEvent):
    """Emitted after a full Strategy Runtime evaluation pass."""

    event_type: ClassVar[str] = "strategy.evaluated"
    user_id: UUID
    evaluation_id: UUID
    request_id: str
    symbol: str
    timeframe: str
    decision: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "evaluation_id": str(self.evaluation_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "decision": self.decision,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class SignalGenerated(DomainEvent):
    """Emitted when the runtime produces a StrategySignal."""

    event_type: ClassVar[str] = "strategy.signal_generated"
    user_id: UUID
    signal_id: UUID
    evaluation_id: UUID
    symbol: str
    direction: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "signal_id": str(self.signal_id),
                "evaluation_id": str(self.evaluation_id),
                "symbol": self.symbol,
                "direction": self.direction,
                "confidence": self.confidence,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class SignalRejected(DomainEvent):
    """Emitted when a generated signal is rejected (e.g. risk gate)."""

    event_type: ClassVar[str] = "strategy.signal_rejected"
    user_id: UUID
    signal_id: UUID
    evaluation_id: UUID
    symbol: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "signal_id": str(self.signal_id),
                "evaluation_id": str(self.evaluation_id),
                "symbol": self.symbol,
                "reasons": list(self.reasons),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class StrategyBlocked(DomainEvent):
    """Emitted when the runtime returns BLOCKED."""

    event_type: ClassVar[str] = "strategy.blocked"
    user_id: UUID
    evaluation_id: UUID
    request_id: str
    symbol: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "evaluation_id": str(self.evaluation_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "reasons": list(self.reasons),
            }
        )
        return payload
