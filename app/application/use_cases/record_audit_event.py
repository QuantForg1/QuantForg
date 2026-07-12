"""RecordAuditEventUseCase — append an immutable audit trail entry.

Why this use case exists
------------------------
Compliance and forensics require every significant action to leave an
audit record. This use case constructs an AuditLog via the domain factory
and persists it. The record is immutable after creation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import AuditEventDTO, RecordAuditEventCommand
from app.domain.entities.audit_log import AuditLog
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class RecordAuditEventUseCase:
    """Persist a new audit event."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: RecordAuditEventCommand) -> AuditEventDTO:
        """Create and store an immutable audit log entry."""
        entry = AuditLog.record(
            action=command.action,
            outcome=command.outcome,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            actor_user_id=command.actor_user_id,
            ip_address=command.ip_address,
            user_agent=command.user_agent,
            message=command.message,
            metadata=command.metadata,
        )

        async with self.uow_factory() as uow:
            await uow.audit_logs.add(entry)
            await uow.commit()
            return AuditEventDTO.from_entity(entry)
