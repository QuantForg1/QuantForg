"""LogoutUseCase — end an IdP session."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import LogoutCommand, MessageDTO
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.interfaces.auth import AuthProviderPort


@dataclass(frozen=True, slots=True)
class LogoutUseCase:
    auth: AuthProviderPort
    audit: RecordAuditEventUseCase

    async def execute(self, command: LogoutCommand) -> MessageDTO:
        await self.auth.sign_out(access_token=command.access_token)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.LOGOUT,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth",
                resource_id=command.actor_user_id,
                actor_user_id=command.actor_user_id,
                message="User logged out",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return MessageDTO(message="Logged out")
