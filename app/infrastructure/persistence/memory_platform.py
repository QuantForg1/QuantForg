"""In-memory User Platform Unit of Work (tests and local fallback)."""

from __future__ import annotations

from types import TracebackType
from typing import Self
from uuid import UUID

from app.domain.entities.audit_log import AuditLog
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
from app.domain.entities.user import User
from app.domain.enums.platform import OrganizationType
from app.domain.value_objects.email import EmailAddress


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.items.get(user_id)

    async def get_by_email(self, email: EmailAddress) -> User | None:
        for user in self.items.values():
            if user.email == email:
                return user
        return None

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> User | None:
        for user in self.items.values():
            if user.auth_user_id == auth_user_id:
                return user
        return None

    async def add(self, user: User) -> User:
        self.items[user.id] = user
        return user

    async def update(self, user: User) -> User:
        self.items[user.id] = user
        return user


class InMemoryAuditLogRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, AuditLog] = {}

    async def add(self, entry: AuditLog) -> AuditLog:
        self.items[entry.id] = entry
        return entry

    async def list_recent(self, *, limit: int = 200) -> list[AuditLog]:
        rows = list(self.items.values())
        rows.sort(
            key=lambda e: e.occurred_at or e.created_at,
            reverse=True,
        )
        return rows[:limit]


class InMemoryProfileRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, UserProfile] = {}

    async def get_by_user_id(self, user_id: UUID) -> UserProfile | None:
        return self.items.get(user_id)

    async def get_by_username(self, username: str) -> UserProfile | None:
        key = username.lower()
        for profile in self.items.values():
            if profile.username and profile.username.lower() == key:
                return profile
        return None

    async def add(self, profile: UserProfile) -> UserProfile:
        self.items[profile.user_id] = profile
        return profile

    async def update(self, profile: UserProfile) -> UserProfile:
        self.items[profile.user_id] = profile
        return profile


class InMemorySettingsRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, UserSettings] = {}

    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        return self.items.get(user_id)

    async def add(self, settings: UserSettings) -> UserSettings:
        self.items[settings.user_id] = settings
        return settings

    async def update(self, settings: UserSettings) -> UserSettings:
        self.items[settings.user_id] = settings
        return settings


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, UserDevice] = {}

    async def list_for_user(self, user_id: UUID) -> list[UserDevice]:
        return [d for d in self.items.values() if d.user_id == user_id]

    async def add(self, device: UserDevice) -> UserDevice:
        self.items[device.id] = device
        return device

    async def delete(self, device_id: UUID, user_id: UUID) -> None:
        device = self.items.get(device_id)
        if device is not None and device.user_id == user_id:
            del self.items[device_id]


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, UserSession] = {}

    async def list_active_for_user(self, user_id: UUID) -> list[UserSession]:
        return [s for s in self.items.values() if s.user_id == user_id and s.is_active]

    async def add(self, session: UserSession) -> UserSession:
        self.items[session.id] = session
        return session

    async def update(self, session: UserSession) -> UserSession:
        self.items[session.id] = session
        return session

    async def get_by_id(self, session_id: UUID) -> UserSession | None:
        return self.items.get(session_id)


class InMemoryOrganizationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Organization] = {}
        self.memberships: InMemoryOrganizationMemberRepository | None = None

    async def get_by_id(self, organization_id: UUID) -> Organization | None:
        return self.items.get(organization_id)

    async def get_by_slug(self, slug: str) -> Organization | None:
        key = slug.lower()
        for org in self.items.values():
            if org.slug == key:
                return org
        return None

    async def list_for_user(self, user_id: UUID) -> list[Organization]:
        if self.memberships is None:
            return [o for o in self.items.values() if o.owner_user_id == user_id]
        org_ids = {
            m.organization_id
            for m in self.memberships.items.values()
            if m.user_id == user_id
        }
        return [o for o in self.items.values() if o.id in org_ids]

    async def add(self, organization: Organization) -> Organization:
        self.items[organization.id] = organization
        return organization


class InMemoryOrganizationMemberRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, OrganizationMember] = {}

    async def list_for_organization(
        self, organization_id: UUID
    ) -> list[OrganizationMember]:
        return [m for m in self.items.values() if m.organization_id == organization_id]

    async def get_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        for member in self.items.values():
            if member.organization_id == organization_id and member.user_id == user_id:
                return member
        return None

    async def add(self, member: OrganizationMember) -> OrganizationMember:
        self.items[member.id] = member
        return member

    async def update(self, member: OrganizationMember) -> OrganizationMember:
        self.items[member.id] = member
        return member


class InMemoryInvitationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, OrganizationInvitation] = {}

    async def add(self, invitation: OrganizationInvitation) -> OrganizationInvitation:
        self.items[invitation.id] = invitation
        return invitation

    async def get_by_id(self, invitation_id: UUID) -> OrganizationInvitation | None:
        return self.items.get(invitation_id)

    async def list_pending(self, organization_id: UUID) -> list[OrganizationInvitation]:
        return [
            i
            for i in self.items.values()
            if i.organization_id == organization_id and i.status.value == "pending"
        ]

    async def update(
        self, invitation: OrganizationInvitation
    ) -> OrganizationInvitation:
        self.items[invitation.id] = invitation
        return invitation


class InMemoryActivityRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, ActivityEvent] = {}

    async def add(self, event: ActivityEvent) -> ActivityEvent:
        self.items[event.id] = event
        return event

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ActivityEvent]:
        events = [e for e in self.items.values() if e.user_id == user_id]
        events.sort(key=lambda e: e.created_at, reverse=True)
        return events[:limit]


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, Notification] = {}

    async def add(self, notification: Notification) -> Notification:
        self.items[notification.id] = notification
        return notification

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        items = [n for n in self.items.values() if n.user_id == user_id]
        if unread_only:
            items = [n for n in items if not n.is_read]
        items.sort(key=lambda n: n.created_at, reverse=True)
        return items[:limit]

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        return self.items.get(notification_id)

    async def update(self, notification: Notification) -> Notification:
        self.items[notification.id] = notification
        return notification


class InMemoryNotificationPreferenceRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[UUID, str], NotificationPreference] = {}

    async def list_for_user(self, user_id: UUID) -> list[NotificationPreference]:
        return [p for (uid, _), p in self.items.items() if uid == user_id]

    async def upsert(
        self, preference: NotificationPreference
    ) -> NotificationPreference:
        self.items[(preference.user_id, preference.category.value)] = preference
        return preference


class InMemoryStorageObjectRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, StorageObject] = {}

    async def add(self, obj: StorageObject) -> StorageObject:
        self.items[obj.id] = obj
        return obj

    async def list_for_user(self, user_id: UUID) -> list[StorageObject]:
        return [o for o in self.items.values() if o.user_id == user_id]


class InMemoryPlatformUnitOfWork:
    def __init__(self) -> None:
        self.users = InMemoryUserRepository()
        self.audit_logs = InMemoryAuditLogRepository()
        self.profiles = InMemoryProfileRepository()
        self.settings = InMemorySettingsRepository()
        self.devices = InMemoryDeviceRepository()
        self.sessions = InMemorySessionRepository()
        self.organization_members = InMemoryOrganizationMemberRepository()
        self.organizations = InMemoryOrganizationRepository()
        self.organizations.memberships = self.organization_members
        self.organization_invitations = InMemoryInvitationRepository()
        self.activity_events = InMemoryActivityRepository()
        self.notifications = InMemoryNotificationRepository()
        self.notification_preferences = InMemoryNotificationPreferenceRepository()
        self.storage_objects = InMemoryStorageObjectRepository()
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        if exc_type is not None and not self.committed:
            await self.rollback()

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class MemoryPlatformUnitOfWorkFactory:
    def __init__(self, uow: InMemoryPlatformUnitOfWork | None = None) -> None:
        self.uow = uow or InMemoryPlatformUnitOfWork()

    def __call__(self) -> InMemoryPlatformUnitOfWork:
        self.uow.committed = False
        self.uow.rolled_back = False
        return self.uow


# Silence unused enum import used for type clarity in list helpers
_ = OrganizationType
