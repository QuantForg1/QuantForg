"""Risk Management Engine domain events — decisions only, never fills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class RiskApproved(DomainEvent):
    """Emitted when the risk engine returns ALLOW."""

    event_type: ClassVar[str] = "risk.approved"
    user_id: UUID
    assessment_id: UUID
    request_id: str
    symbol: str
    risk_score: int
    approved_lots: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "assessment_id": str(self.assessment_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "risk_score": self.risk_score,
                "approved_lots": self.approved_lots,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class RiskRejected(DomainEvent):
    """Emitted when the risk engine returns REJECT."""

    event_type: ClassVar[str] = "risk.rejected"
    user_id: UUID
    assessment_id: UUID
    request_id: str
    symbol: str
    risk_score: int
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "assessment_id": str(self.assessment_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "risk_score": self.risk_score,
                "reasons": list(self.reasons),
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class RiskReduced(DomainEvent):
    """Emitted when the risk engine returns REDUCE_SIZE."""

    event_type: ClassVar[str] = "risk.reduced"
    user_id: UUID
    assessment_id: UUID
    request_id: str
    symbol: str
    risk_score: int
    requested_lots: str
    approved_lots: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "assessment_id": str(self.assessment_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "risk_score": self.risk_score,
                "requested_lots": self.requested_lots,
                "approved_lots": self.approved_lots,
                "reasons": list(self.reasons),
            }
        )
        return payload
