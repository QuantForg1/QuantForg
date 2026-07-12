"""Unit of Work port for the User Platform module."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from app.domain.interfaces.platform_repositories import (
    ActivityEventRepositoryPort,
    NotificationPreferenceRepositoryPort,
    NotificationRepositoryPort,
    OrganizationInvitationRepositoryPort,
    OrganizationMemberRepositoryPort,
    OrganizationRepositoryPort,
    StorageObjectRepositoryPort,
    UserDeviceRepositoryPort,
    UserProfileRepositoryPort,
    UserSessionRepositoryPort,
    UserSettingsRepositoryPort,
)
from app.domain.interfaces.repositories import (
    AuditLogRepositoryPort,
    UserRepositoryPort,
)


class PlatformUnitOfWorkPort(Protocol):
    """Transactional boundary for user-platform aggregates."""

    users: UserRepositoryPort
    audit_logs: AuditLogRepositoryPort
    profiles: UserProfileRepositoryPort
    settings: UserSettingsRepositoryPort
    devices: UserDeviceRepositoryPort
    sessions: UserSessionRepositoryPort
    organizations: OrganizationRepositoryPort
    organization_members: OrganizationMemberRepositoryPort
    organization_invitations: OrganizationInvitationRepositoryPort
    activity_events: ActivityEventRepositoryPort
    notifications: NotificationRepositoryPort
    notification_preferences: NotificationPreferenceRepositoryPort
    storage_objects: StorageObjectRepositoryPort

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class PlatformUnitOfWorkFactory(Protocol):
    def __call__(self) -> PlatformUnitOfWorkPort: ...
