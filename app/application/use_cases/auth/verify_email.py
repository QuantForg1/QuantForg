"""VerifyEmailUseCase — confirm email via Supabase token hash."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import AuthSessionDTO, VerifyEmailCommand
from app.application.use_cases.auth._profile import sync_profile_from_identity
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.exceptions.auth import AuthenticationError
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class VerifyEmailUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: VerifyEmailCommand) -> AuthSessionDTO:
        session = await self.auth.verify_email(
            token_hash=command.token_hash,
            type=command.type,
        )
        identity = session.user
        if identity is None:
            if not session.access_token:
                raise AuthenticationError(
                    "Email verification failed",
                    code="verification_failed",
                )
            identity = await self.auth.get_user(access_token=session.access_token)

        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(
                uow, identity, activate_if_confirmed=True
            )
            if not user.is_active:
                user.activate()
                await uow.users.update(user)
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.ACTIVATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user",
                resource_id=user.id,
                actor_user_id=user.id,
                message="Email verified",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return AuthSessionDTO.from_session(session, user)
