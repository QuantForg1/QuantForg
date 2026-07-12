"""Audit event application DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
from app.domain.enums.audit import AuditAction, AuditOutcome


@dataclass(frozen=True, slots=True)
class RecordAuditEventCommand:
    """Input for RecordAuditEventUseCase."""

    action: AuditAction
    outcome: AuditOutcome
    resource_type: str
    resource_id: UUID | None = None
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditEventDTO:
    """Audit event representation for the presentation layer."""

    id: UUID
    action: str
    outcome: str
    resource_type: str
    resource_id: UUID | None
    actor_user_id: UUID | None
    occurred_at: str | None
    message: str

    @classmethod
    def from_entity(cls, entry: AuditLog) -> AuditEventDTO:
        return cls(
            id=entry.id,
            action=entry.action.value,
            outcome=entry.outcome.value,
            resource_type=entry.resource_type,
            resource_id=entry.resource_id,
            actor_user_id=entry.actor_user_id,
            occurred_at=entry.occurred_at.isoformat() if entry.occurred_at else None,
            message=entry.message,
        )
