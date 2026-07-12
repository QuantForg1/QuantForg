"""LoginUseCase — email/password authentication."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import AuthSessionDTO, LoginCommand
from app.application.use_cases.auth._profile import (
    ensure_user_may_authenticate,
    sync_profile_from_identity,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.user import UserStatus
from app.domain.exceptions.auth import AuthenticationError
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class LoginUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: LoginCommand) -> AuthSessionDTO:
        try:
            session = await self.auth.sign_in(
                email=command.email, password=command.password
            )
        except AuthenticationError:
            await self.audit.execute(
                RecordAuditEventCommand(
                    action=AuditAction.LOGIN,
                    outcome=AuditOutcome.FAILURE,
                    resource_type="auth",
                    message="Login failed",
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                    metadata={"email": command.email},
                )
            )
            raise

        identity = session.user
        if identity is None:
            identity = await self.auth.get_user(access_token=session.access_token)

        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(uow, identity)
            ensure_user_may_authenticate(user)
            if user.status == UserStatus.PENDING:
                raise AuthenticationError(
                    "Email verification required",
                    code="email_not_verified",
                )
            user.record_login()
            await uow.users.update(user)
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.LOGIN,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user",
                resource_id=user.id,
                actor_user_id=user.id,
                message="User logged in",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return AuthSessionDTO.from_session(session, user)
