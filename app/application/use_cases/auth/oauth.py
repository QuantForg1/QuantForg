"""OAuth start and callback use cases (Google / GitHub via Supabase)."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import (
    AuthSessionDTO,
    OAuthCallbackCommand,
    OAuthStartCommand,
    OAuthUrlDTO,
)
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
class StartOAuthUseCase:
    auth: AuthProviderPort
    default_redirect_to: str

    async def execute(self, command: OAuthStartCommand) -> OAuthUrlDTO:
        redirect = command.redirect_to or self.default_redirect_to
        result = await self.auth.get_oauth_redirect(
            provider=command.provider,
            redirect_to=redirect,
        )
        return OAuthUrlDTO(provider=result.provider.value, url=result.url)


@dataclass(frozen=True, slots=True)
class CompleteOAuthUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase
    default_redirect_to: str

    async def execute(self, command: OAuthCallbackCommand) -> AuthSessionDTO:
        session = await self.auth.exchange_oauth_code(
            code=command.code,
            redirect_to=command.redirect_to or self.default_redirect_to,
        )
        identity = session.user
        if identity is None:
            if not session.access_token:
                raise AuthenticationError(
                    "OAuth exchange failed",
                    code="oauth_failed",
                )
            identity = await self.auth.get_user(access_token=session.access_token)

        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(
                uow,
                identity,
                role=command.role,
                activate_if_confirmed=True,
            )
            ensure_user_may_authenticate(user)
            if user.status == UserStatus.PENDING and identity.email_confirmed:
                user.activate()
            if user.is_active:
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
                message="OAuth login",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
                metadata={"providers": list(identity.providers)},
            )
        )
        return AuthSessionDTO.from_session(session, user)
