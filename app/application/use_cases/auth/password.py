"""Password reset and change-password use cases."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import (
    ChangePasswordCommand,
    MessageDTO,
    RequestPasswordResetCommand,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.auth import AuthProviderPort


@dataclass(frozen=True, slots=True)
class RequestPasswordResetUseCase:
    """Trigger IdP password-reset email (does not reveal whether email exists)."""

    auth: AuthProviderPort
    audit: RecordAuditEventUseCase
    default_redirect_to: str

    async def execute(self, command: RequestPasswordResetCommand) -> MessageDTO:
        redirect = command.redirect_to or self.default_redirect_to
        await self.auth.request_password_reset(
            email=command.email, redirect_to=redirect
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.SYSTEM,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth",
                message="Password reset requested",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={"email": command.email},
            )
        )
        return MessageDTO(
            message="If an account exists for that email, a reset link has been sent."
        )


@dataclass(frozen=True, slots=True)
class ChangePasswordUseCase:
    """Change password for the currently authenticated session."""

    auth: AuthProviderPort
    audit: RecordAuditEventUseCase

    async def execute(self, command: ChangePasswordCommand) -> MessageDTO:
        if len(command.new_password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters",
                code="weak_password",
            )
        await self.auth.update_password(
            access_token=command.access_token,
            new_password=command.new_password,
        )
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth",
                resource_id=command.actor_user_id,
                actor_user_id=command.actor_user_id,
                message="Password changed",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return MessageDTO(message="Password updated")
