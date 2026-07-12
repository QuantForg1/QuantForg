"""Walk-Forward Validation domain events — offline validation facts only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class WalkForwardStarted(DomainEvent):
    event_type: ClassVar[str] = "walkforward.started"
    user_id: UUID
    run_id: UUID
    request_id: str
    symbol: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "run_id": str(self.run_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class WalkForwardFinished(DomainEvent):
    event_type: ClassVar[str] = "walkforward.finished"
    user_id: UUID
    run_id: UUID
    request_id: str
    status: str
    promotion: str | None
    fold_count: int

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "run_id": str(self.run_id),
                "request_id": self.request_id,
                "status": self.status,
                "promotion": self.promotion,
                "fold_count": self.fold_count,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class WalkForwardFoldCompleted(DomainEvent):
    event_type: ClassVar[str] = "walkforward.fold_completed"
    user_id: UUID
    run_id: UUID
    fold_index: int
    oos_return_pct: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "user_id": str(self.user_id),
                "run_id": str(self.run_id),
                "fold_index": self.fold_index,
                "oos_return_pct": self.oos_return_pct,
            }
        )
        return payload
