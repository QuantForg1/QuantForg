"""Resolve the current application user from an access token."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.auth import AuthUserDTO
from app.application.use_cases.auth._profile import (
    ensure_user_may_authenticate,
    sync_profile_from_identity,
)
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class GetCurrentUserUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory

    async def execute(self, *, access_token: str) -> AuthUserDTO:
        identity = await self.auth.get_user(access_token=access_token)
        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(uow, identity)
            ensure_user_may_authenticate(user)
            await uow.commit()
        return AuthUserDTO.from_entity(user)
