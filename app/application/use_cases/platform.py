"""User platform use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.platform import (
    ActivityDTO,
    CreateTeamCommand,
    DeviceDTO,
    EnsurePlatformBootstrapCommand,
    InvitationDTO,
    InviteMemberCommand,
    NotificationDTO,
    NotificationPreferenceDTO,
    OrganizationDTO,
    ProfileDTO,
    SessionDTO,
    SettingsDTO,
    UpdateNotificationPreferenceCommand,
    UpdateProfileCommand,
    UpdateSettingsCommand,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.platform import (
    ActivityEvent,
    Notification,
    NotificationPreference,
    Organization,
    OrganizationInvitation,
    OrganizationMember,
    StorageObject,
    UserProfile,
    UserSettings,
)
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.platform import (
    ActivityCategory,
    NotificationCategory,
    OrganizationMemberRole,
    OrganizationType,
    StoragePurpose,
)
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.interfaces.platform_uow import PlatformUnitOfWorkFactory
from core.security.crypto import hash_value


@dataclass(frozen=True, slots=True)
class EnsurePlatformBootstrapUseCase:
    """Create default profile, settings, preferences, and personal workspace."""

    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, command: EnsurePlatformBootstrapCommand) -> ProfileDTO:
        async with self.uow_factory() as uow:
            profile = await uow.profiles.get_by_user_id(command.user_id)
            if profile is None:
                profile = UserProfile.create_default(
                    user_id=command.user_id,
                    full_name=command.display_name,
                )
                await uow.profiles.add(profile)

            settings = await uow.settings.get_by_user_id(command.user_id)
            if settings is None:
                await uow.settings.add(
                    UserSettings.create_default(user_id=command.user_id)
                )

            prefs = await uow.notification_preferences.list_for_user(command.user_id)
            if not prefs:
                for pref in NotificationPreference.defaults_for_user(command.user_id):
                    await uow.notification_preferences.upsert(pref)

            orgs = await uow.organizations.list_for_user(command.user_id)
            if not any(o.org_type == OrganizationType.PERSONAL for o in orgs):
                org = Organization.create_personal(
                    owner_user_id=command.user_id,
                    display_name=command.display_name or "User",
                )
                await uow.organizations.add(org)
                await uow.organization_members.add(
                    OrganizationMember(
                        organization_id=org.id,
                        user_id=command.user_id,
                        role=OrganizationMemberRole.OWNER,
                    )
                )

            await uow.commit()
            return ProfileDTO.from_entity(profile)


@dataclass(frozen=True, slots=True)
class GetProfileUseCase:
    uow_factory: PlatformUnitOfWorkFactory
    bootstrap: EnsurePlatformBootstrapUseCase

    async def execute(self, *, user_id: UUID, display_name: str = "") -> ProfileDTO:
        async with self.uow_factory() as uow:
            profile = await uow.profiles.get_by_user_id(user_id)
        if profile is None:
            return await self.bootstrap.execute(
                EnsurePlatformBootstrapCommand(
                    user_id=user_id, display_name=display_name
                )
            )
        return ProfileDTO.from_entity(profile)


@dataclass(frozen=True, slots=True)
class UpdateProfileUseCase:
    uow_factory: PlatformUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: UpdateProfileCommand) -> ProfileDTO:
        async with self.uow_factory() as uow:
            profile = await uow.profiles.get_by_user_id(command.user_id)
            if profile is None:
                profile = UserProfile.create_default(user_id=command.user_id)
                await uow.profiles.add(profile)

            if command.username is not None:
                existing = await uow.profiles.get_by_username(command.username)
                if existing is not None and existing.user_id != command.user_id:
                    raise ConflictError(
                        "Username already taken",
                        details={"username": command.username},
                    )

            profile.update_fields(
                full_name=command.full_name,
                username=command.username,
                bio=command.bio,
                country_code=command.country_code,
                timezone=command.timezone,
                preferred_language=command.preferred_language,
                trading_experience=command.trading_experience,
                risk_level=command.risk_level,
            )
            await uow.profiles.update(profile)
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=command.user_id,
                    category=ActivityCategory.PROFILE,
                    action="profile_updated",
                    message="Profile updated",
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
            )
            await uow.commit()

        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user_profile",
                resource_id=command.user_id,
                actor_user_id=command.user_id,
                message="Profile updated",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return ProfileDTO.from_entity(profile)


@dataclass(frozen=True, slots=True)
class GetSettingsUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> SettingsDTO:
        async with self.uow_factory() as uow:
            settings = await uow.settings.get_by_user_id(user_id)
            if settings is None:
                settings = UserSettings.create_default(user_id=user_id)
                await uow.settings.add(settings)
                await uow.commit()
            return SettingsDTO.from_entity(settings)


@dataclass(frozen=True, slots=True)
class UpdateSettingsUseCase:
    uow_factory: PlatformUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: UpdateSettingsCommand) -> SettingsDTO:
        async with self.uow_factory() as uow:
            settings = await uow.settings.get_by_user_id(command.user_id)
            if settings is None:
                settings = UserSettings.create_default(user_id=command.user_id)
                await uow.settings.add(settings)
            settings.update_fields(
                theme=command.theme,
                notifications_enabled=command.notifications_enabled,
                email_marketing=command.email_marketing,
                email_security=command.email_security,
                email_product=command.email_product,
                security_login_alerts=command.security_login_alerts,
                security_require_reauth=command.security_require_reauth,
                session_timeout_minutes=command.session_timeout_minutes,
            )
            await uow.settings.update(settings)
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=command.user_id,
                    category=ActivityCategory.SECURITY,
                    action="settings_updated",
                    message="User settings updated",
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
            )
            await uow.commit()
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user_settings",
                resource_id=command.user_id,
                actor_user_id=command.user_id,
                message="Settings updated",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return SettingsDTO.from_entity(settings)


@dataclass(frozen=True, slots=True)
class ListDevicesUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[DeviceDTO]:
        async with self.uow_factory() as uow:
            devices = await uow.devices.list_for_user(user_id)
            return [DeviceDTO.from_entity(d) for d in devices]


@dataclass(frozen=True, slots=True)
class ListSessionsUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[SessionDTO]:
        async with self.uow_factory() as uow:
            sessions = await uow.sessions.list_active_for_user(user_id)
            return [SessionDTO.from_entity(s) for s in sessions]


@dataclass(frozen=True, slots=True)
class RevokeSessionUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID, session_id: UUID) -> SessionDTO:
        async with self.uow_factory() as uow:
            session = await uow.sessions.get_by_id(session_id)
            if session is None or session.user_id != user_id:
                raise NotFoundError("Session not found")
            session.revoke()
            await uow.sessions.update(session)
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=user_id,
                    category=ActivityCategory.SECURITY,
                    action="session_revoked",
                    message="Session revoked",
                    metadata={"session_id": str(session_id)},
                )
            )
            await uow.commit()
            return SessionDTO.from_entity(session)


@dataclass(frozen=True, slots=True)
class ListOrganizationsUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[OrganizationDTO]:
        async with self.uow_factory() as uow:
            orgs = await uow.organizations.list_for_user(user_id)
            return [OrganizationDTO.from_entity(o) for o in orgs]


@dataclass(frozen=True, slots=True)
class CreateTeamOrganizationUseCase:
    uow_factory: PlatformUnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(self, command: CreateTeamCommand) -> OrganizationDTO:
        async with self.uow_factory() as uow:
            if await uow.organizations.get_by_slug(command.slug.lower()) is not None:
                raise ConflictError("Organization slug already exists")
            org = Organization.create_team(
                owner_user_id=command.owner_user_id,
                name=command.name,
                slug=command.slug,
            )
            await uow.organizations.add(org)
            await uow.organization_members.add(
                OrganizationMember(
                    organization_id=org.id,
                    user_id=command.owner_user_id,
                    role=OrganizationMemberRole.OWNER,
                )
            )
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=command.owner_user_id,
                    category=ActivityCategory.ORGANIZATION,
                    action="team_created",
                    message=f"Created team {org.name}",
                    metadata={"organization_id": str(org.id)},
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
            )
            await uow.commit()
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.CREATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="organization",
                resource_id=org.id,
                actor_user_id=command.owner_user_id,
                message="Team organization created",
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
        return OrganizationDTO.from_entity(org)


@dataclass(frozen=True, slots=True)
class InviteOrganizationMemberUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, command: InviteMemberCommand) -> InvitationDTO:
        async with self.uow_factory() as uow:
            membership = await uow.organization_members.get_membership(
                command.organization_id, command.invited_by
            )
            if membership is None or membership.role not in {
                OrganizationMemberRole.OWNER,
                OrganizationMemberRole.ADMIN,
            }:
                raise AuthorizationError("Only org admins can invite members")

            token = token_urlsafe(32)
            invitation = OrganizationInvitation(
                organization_id=command.organization_id,
                email=command.email,
                role=command.role,
                invited_by=command.invited_by,
                token_hash=hash_value(token),
                expires_at=datetime.now(UTC) + timedelta(days=7),
            )
            await uow.organization_invitations.add(invitation)
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=command.invited_by,
                    category=ActivityCategory.ORGANIZATION,
                    action="member_invited",
                    message=f"Invited {command.email}",
                    metadata={"organization_id": str(command.organization_id)},
                    ip_address=command.ip_address,
                    user_agent=command.user_agent,
                )
            )
            await uow.notifications.add(
                Notification(
                    user_id=command.invited_by,
                    category=NotificationCategory.ORGANIZATION,
                    title="Invitation sent",
                    body=f"Invitation sent to {command.email}",
                )
            )
            await uow.commit()
            return InvitationDTO.from_entity(invitation)


@dataclass(frozen=True, slots=True)
class ListActivityUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID, limit: int = 50) -> list[ActivityDTO]:
        async with self.uow_factory() as uow:
            events = await uow.activity_events.list_for_user(user_id, limit=limit)
            return [ActivityDTO.from_entity(e) for e in events]


@dataclass(frozen=True, slots=True)
class ListNotificationsUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(
        self, *, user_id: UUID, unread_only: bool = False
    ) -> list[NotificationDTO]:
        async with self.uow_factory() as uow:
            items = await uow.notifications.list_for_user(
                user_id, unread_only=unread_only
            )
            return [NotificationDTO.from_entity(n) for n in items]


@dataclass(frozen=True, slots=True)
class MarkNotificationReadUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID, notification_id: UUID) -> NotificationDTO:
        async with self.uow_factory() as uow:
            item = await uow.notifications.get_by_id(notification_id)
            if item is None or item.user_id != user_id:
                raise NotFoundError("Notification not found")
            item.mark_read()
            await uow.notifications.update(item)
            await uow.commit()
            return NotificationDTO.from_entity(item)


@dataclass(frozen=True, slots=True)
class ListNotificationPreferencesUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(self, *, user_id: UUID) -> list[NotificationPreferenceDTO]:
        async with self.uow_factory() as uow:
            prefs = await uow.notification_preferences.list_for_user(user_id)
            if not prefs:
                prefs = NotificationPreference.defaults_for_user(user_id)
                for pref in prefs:
                    await uow.notification_preferences.upsert(pref)
                await uow.commit()
            return [NotificationPreferenceDTO.from_entity(p) for p in prefs]


@dataclass(frozen=True, slots=True)
class UpdateNotificationPreferenceUseCase:
    uow_factory: PlatformUnitOfWorkFactory

    async def execute(
        self, command: UpdateNotificationPreferenceCommand
    ) -> NotificationPreferenceDTO:
        async with self.uow_factory() as uow:
            prefs = await uow.notification_preferences.list_for_user(command.user_id)
            pref = next((p for p in prefs if p.category == command.category), None)
            if pref is None:
                pref = NotificationPreference(
                    user_id=command.user_id, category=command.category
                )
            if command.in_app is not None:
                pref.in_app = command.in_app
            if command.email is not None:
                pref.email = command.email
            pref.touch()
            await uow.notification_preferences.upsert(pref)
            await uow.commit()
            return NotificationPreferenceDTO.from_entity(pref)


@dataclass(frozen=True, slots=True)
class SetAvatarUseCase:
    """Persist avatar metadata after a successful storage upload."""

    uow_factory: PlatformUnitOfWorkFactory

    async def execute(
        self,
        *,
        user_id: UUID,
        object_path: str,
        public_url: str,
        content_type: str,
        size_bytes: int,
    ) -> ProfileDTO:
        if size_bytes > 5_242_880:
            raise ValidationError("Avatar exceeds 5MB limit", code="avatar_too_large")
        async with self.uow_factory() as uow:
            profile = await uow.profiles.get_by_user_id(user_id)
            if profile is None:
                profile = UserProfile.create_default(user_id=user_id)
                await uow.profiles.add(profile)
            profile.avatar_path = object_path
            profile.avatar_url = public_url
            profile.touch()
            await uow.profiles.update(profile)
            await uow.storage_objects.add(
                StorageObject(
                    user_id=user_id,
                    bucket="avatars",
                    object_path=object_path,
                    content_type=content_type,
                    size_bytes=size_bytes,
                    purpose=StoragePurpose.AVATAR,
                    public_url=public_url,
                )
            )
            await uow.activity_events.add(
                ActivityEvent.record(
                    user_id=user_id,
                    category=ActivityCategory.PROFILE,
                    action="avatar_updated",
                    message="Avatar updated",
                )
            )
            await uow.commit()
            return ProfileDTO.from_entity(profile)
