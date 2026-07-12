"""Operations domain events — observability facts only."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.domain.events.base import DomainEvent


@dataclass(frozen=True, kw_only=True, slots=True)
class AlertTriggered(DomainEvent):
    event_type: ClassVar[str] = "ops.alert_triggered"
    alert_id: UUID
    code: str
    severity: str
    component: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update(
            {
                "alert_id": str(self.alert_id),
                "code": self.code,
                "severity": self.severity,
                "component": self.component,
            }
        )
        return payload


@dataclass(frozen=True, kw_only=True, slots=True)
class HealthSnapshotRecorded(DomainEvent):
    event_type: ClassVar[str] = "ops.health_snapshot_recorded"
    overall: str

    def to_dict(self) -> dict[str, Any]:
        payload = super().to_dict()
        payload.update({"overall": self.overall})
        return payload
