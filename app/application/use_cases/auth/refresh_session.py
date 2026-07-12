"""RefreshSessionUseCase — rotate access/refresh tokens."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.auth import AuthSessionDTO, RefreshSessionCommand
from app.application.use_cases.auth._profile import (
    ensure_user_may_authenticate,
    sync_profile_from_identity,
)
from app.domain.exceptions.auth import AuthenticationError
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class RefreshSessionUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory

    async def execute(self, command: RefreshSessionCommand) -> AuthSessionDTO:
        session = await self.auth.refresh_session(refresh_token=command.refresh_token)
        identity = session.user
        if identity is None:
            if not session.access_token:
                raise AuthenticationError(
                    "Refresh did not return a session",
                    code="refresh_failed",
                )
            identity = await self.auth.get_user(access_token=session.access_token)

        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(uow, identity)
            ensure_user_may_authenticate(user)
            await uow.commit()

        return AuthSessionDTO.from_session(session, user)
