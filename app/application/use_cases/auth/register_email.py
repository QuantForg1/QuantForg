"""RegisterWithEmailUseCase — email/password signup via Supabase Auth."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import AuthSessionDTO, MessageDTO, RegisterEmailCommand
from app.application.use_cases.auth._profile import sync_profile_from_identity
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.user import UserStatus
from app.domain.exceptions.auth import AuthenticationError
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class RegisterWithEmailUseCase:
    """Create an IdP user and sync the application profile."""

    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(
        self, command: RegisterEmailCommand
    ) -> AuthSessionDTO | MessageDTO:
        if len(command.password) < 8:
            raise ValidationError(
                "Password must be at least 8 characters",
                code="weak_password",
            )

        try:
            session = await self.auth.sign_up(
                email=command.email,
                password=command.password,
                display_name=command.display_name,
            )
        except AuthenticationError:
            await self.audit.execute(
                RecordAuditEventCommand(
                    action=AuditAction.CREATE,
                    outcome=AuditOutcome.FAILURE,
                    resource_type="auth",
                    message="Email registration failed",
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                    metadata={"email": command.email},
                )
            )
            raise

        identity = session.user
        if identity is None:
            raise AuthenticationError(
                "Registration did not return an identity",
                code="registration_incomplete",
            )

        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(
                uow,
                identity,
                display_name_fallback=command.display_name,
                role=command.role,
                activate_if_confirmed=True,
            )
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.CREATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user",
                resource_id=user.id,
                actor_user_id=user.id,
                message="User registered via email",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )

        if not session.access_token or user.status == UserStatus.PENDING:
            return MessageDTO(
                message=(
                    "Registration successful. Please verify your email "
                    "before signing in."
                )
            )
        return AuthSessionDTO.from_session(session, user)
