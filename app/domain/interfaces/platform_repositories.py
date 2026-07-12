"""Repository ports for the User Platform."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.entities.platform import (
    ActivityEvent,
    Notification,
    NotificationPreference,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    StorageObject,
    UserDevice,
    UserProfile,
    UserSession,
    UserSettings,
)


class UserProfileRepositoryPort(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> UserProfile | None: ...

    async def get_by_username(self, username: str) -> UserProfile | None: ...

    async def add(self, profile: UserProfile) -> UserProfile: ...

    async def update(self, profile: UserProfile) -> UserProfile: ...


class UserSettingsRepositoryPort(Protocol):
    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None: ...

    async def add(self, settings: UserSettings) -> UserSettings: ...

    async def update(self, settings: UserSettings) -> UserSettings: ...


class UserDeviceRepositoryPort(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[UserDevice]: ...

    async def add(self, device: UserDevice) -> UserDevice: ...

    async def delete(self, device_id: UUID, user_id: UUID) -> None: ...


class UserSessionRepositoryPort(Protocol):
    async def list_active_for_user(self, user_id: UUID) -> list[UserSession]: ...

    async def add(self, session: UserSession) -> UserSession: ...

    async def update(self, session: UserSession) -> UserSession: ...

    async def get_by_id(self, session_id: UUID) -> UserSession | None: ...


class OrganizationRepositoryPort(Protocol):
    async def get_by_id(self, organization_id: UUID) -> Organization | None: ...

    async def get_by_slug(self, slug: str) -> Organization | None: ...

    async def list_for_user(self, user_id: UUID) -> list[Organization]: ...

    async def add(self, organization: Organization) -> Organization: ...


class OrganizationMemberRepositoryPort(Protocol):
    async def list_for_organization(
        self, organization_id: UUID
    ) -> list[OrganizationMember]: ...

    async def get_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None: ...

    async def add(self, member: OrganizationMember) -> OrganizationMember: ...

    async def update(self, member: OrganizationMember) -> OrganizationMember: ...


class OrganizationInvitationRepositoryPort(Protocol):
    async def add(
        self, invitation: OrganizationInvitation
    ) -> OrganizationInvitation: ...

    async def get_by_id(self, invitation_id: UUID) -> OrganizationInvitation | None: ...

    async def list_pending(
        self, organization_id: UUID
    ) -> list[OrganizationInvitation]: ...

    async def update(
        self, invitation: OrganizationInvitation
    ) -> OrganizationInvitation: ...


class ActivityEventRepositoryPort(Protocol):
    async def add(self, event: ActivityEvent) -> ActivityEvent: ...

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ActivityEvent]: ...


class NotificationRepositoryPort(Protocol):
    async def add(self, notification: Notification) -> Notification: ...

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]: ...

    async def get_by_id(self, notification_id: UUID) -> Notification | None: ...

    async def update(self, notification: Notification) -> Notification: ...


class NotificationPreferenceRepositoryPort(Protocol):
    async def list_for_user(self, user_id: UUID) -> list[NotificationPreference]: ...

    async def upsert(
        self, preference: NotificationPreference
    ) -> NotificationPreference: ...


class StorageObjectRepositoryPort(Protocol):
    async def add(self, obj: StorageObject) -> StorageObject: ...

    async def list_for_user(self, user_id: UUID) -> list[StorageObject]: ...
