"""Resend signup verification email / OTP."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import MessageDTO, ResendVerificationCommand
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.interfaces.auth import AuthProviderPort


@dataclass(frozen=True, slots=True)
class ResendVerificationUseCase:
    auth: AuthProviderPort
    audit: RecordAuditEventUseCase

    async def execute(self, command: ResendVerificationCommand) -> MessageDTO:
        await self.auth.resend_signup_email(email=command.email)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth",
                message="Signup verification resent",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={"email": command.email},
            )
        )
        return MessageDTO(
            message=("If an account needs verification, a new code has been sent.")
        )
