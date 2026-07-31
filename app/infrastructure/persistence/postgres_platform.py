"""Postgres persistence for User Platform aggregates."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text

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
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.platform import (
    ActivityCategory,
    InvitationStatus,
    NotificationCategory,
    OrganizationMemberRole,
    OrganizationMemberStatus,
    OrganizationType,
    ProfileRiskLevel,
    StoragePurpose,
    TradingExperience,
    UiTheme,
)
from app.domain.enums.user import UserRole, UserStatus
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import PersonName
from app.infrastructure.persistence.postgres_common import (
    PostgresUnitOfWorkBase,
    as_json,
    json_dict,
    parse_datetime,
    parse_datetime_optional,
    parse_uuid,
    parse_uuid_optional,
)
from core.database.session import DatabaseManager


def _audit_from_row(row: Any) -> AuditLog:
    return AuditLog(
        id=parse_uuid(row["id"]),
        action=AuditAction(str(row["action"])),
        outcome=AuditOutcome(str(row["outcome"])),
        resource_type=str(row["resource_type"]),
        resource_id=parse_uuid_optional(row["resource_id"]),
        actor_user_id=parse_uuid_optional(row["actor_user_id"]),
        occurred_at=parse_datetime_optional(row["occurred_at"]),
        ip_address=str(row["ip_address"] or ""),
        user_agent=str(row["user_agent"] or ""),
        message=str(row["message"] or ""),
        metadata=json_dict(row["metadata"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
        _frozen=False,
    )


def _user_from_row(row: Any) -> User:
    auth_raw = row.get("auth_user_id")
    return User(
        id=parse_uuid(row["id"]),
        email=EmailAddress(value=str(row["email"])),
        display_name=PersonName(value=str(row["display_name"])),
        role=UserRole(str(row["role"])),
        status=UserStatus(str(row["status"])),
        password_hash=str(row.get("password_hash") or ""),
        auth_user_id=parse_uuid(auth_raw) if auth_raw else None,
        last_login_at=parse_datetime_optional(row.get("last_login_at")),
        deactivated_at=parse_datetime_optional(row.get("deactivated_at")),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _profile_from_row(row: Any) -> UserProfile:
    user_id = parse_uuid(row["user_id"])
    return UserProfile(
        id=user_id,
        user_id=user_id,
        avatar_url=str(row["avatar_url"] or ""),
        avatar_path=str(row["avatar_path"] or ""),
        full_name=str(row["full_name"] or ""),
        username=str(row["username"]) if row["username"] else None,
        bio=str(row["bio"] or ""),
        country_code=str(row["country_code"]) if row["country_code"] else None,
        timezone=str(row["timezone"] or "UTC"),
        preferred_language=str(row["preferred_language"] or "en"),
        trading_experience=TradingExperience(
            str(row["trading_experience"] or "beginner")
        ),
        risk_level=ProfileRiskLevel(str(row["risk_level"] or "moderate")),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _settings_from_row(row: Any) -> UserSettings:
    user_id = parse_uuid(row["user_id"])
    return UserSettings(
        id=user_id,
        user_id=user_id,
        theme=UiTheme(str(row["theme"] or "system")),
        notifications_enabled=bool(row["notifications_enabled"]),
        email_marketing=bool(row["email_marketing"]),
        email_security=bool(row["email_security"]),
        email_product=bool(row["email_product"]),
        security_login_alerts=bool(row["security_login_alerts"]),
        security_require_reauth=bool(row["security_require_reauth"]),
        session_timeout_minutes=int(row["session_timeout_minutes"] or 10080),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _device_from_row(row: Any) -> UserDevice:
    return UserDevice(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        device_label=str(row["device_label"] or ""),
        user_agent=str(row["user_agent"] or ""),
        last_seen_at=parse_datetime(row["last_seen_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _session_from_row(row: Any) -> UserSession:
    return UserSession(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        device_id=parse_uuid_optional(row["device_id"]),
        ip_address=str(row["ip_address"] or ""),
        user_agent=str(row["user_agent"] or ""),
        is_active=bool(row["is_active"]),
        last_active_at=parse_datetime(row["last_active_at"]),
        revoked_at=parse_datetime_optional(row["revoked_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _org_from_row(row: Any) -> Organization:
    return Organization(
        id=parse_uuid(row["id"]),
        name=str(row["name"]),
        slug=str(row["slug"]),
        org_type=OrganizationType(str(row["org_type"])),
        owner_user_id=parse_uuid(row["owner_user_id"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _member_from_row(row: Any) -> OrganizationMember:
    return OrganizationMember(
        id=parse_uuid(row["id"]),
        organization_id=parse_uuid(row["organization_id"]),
        user_id=parse_uuid(row["user_id"]),
        role=OrganizationMemberRole(str(row["role"])),
        status=OrganizationMemberStatus(str(row["status"])),
        joined_at=parse_datetime(row["joined_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _invitation_from_row(row: Any) -> OrganizationInvitation:
    return OrganizationInvitation(
        id=parse_uuid(row["id"]),
        organization_id=parse_uuid(row["organization_id"]),
        email=str(row["email"]),
        role=OrganizationMemberRole(str(row["role"])),
        invited_by=parse_uuid(row["invited_by"]),
        token_hash=str(row["token_hash"]),
        expires_at=parse_datetime(row["expires_at"]),
        status=InvitationStatus(str(row["status"])),
        accepted_at=parse_datetime_optional(row["accepted_at"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _activity_from_row(row: Any) -> ActivityEvent:
    return ActivityEvent(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        category=ActivityCategory(str(row["category"])),
        action=str(row["action"]),
        message=str(row["message"] or ""),
        metadata=json_dict(row["metadata"]),
        ip_address=str(row["ip_address"] or ""),
        user_agent=str(row["user_agent"] or ""),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
        _frozen=False,
    )


def _notification_from_row(row: Any) -> Notification:
    return Notification(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        category=NotificationCategory(str(row["category"])),
        title=str(row["title"]),
        body=str(row["body"] or ""),
        is_read=bool(row["is_read"]),
        read_at=parse_datetime_optional(row["read_at"]),
        metadata=json_dict(row["metadata"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _pref_from_row(row: Any) -> NotificationPreference:
    return NotificationPreference(
        id=uuid4(),
        user_id=parse_uuid(row["user_id"]),
        category=NotificationCategory(str(row["category"])),
        in_app=bool(row["in_app"]),
        email=bool(row["email"]),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


def _storage_from_row(row: Any) -> StorageObject:
    return StorageObject(
        id=parse_uuid(row["id"]),
        user_id=parse_uuid(row["user_id"]),
        bucket=str(row["bucket"] or "avatars"),
        object_path=str(row["object_path"]),
        content_type=str(row["content_type"] or "application/octet-stream"),
        size_bytes=int(row["size_bytes"] or 0),
        purpose=StoragePurpose(str(row["purpose"] or "avatar")),
        public_url=str(row["public_url"] or ""),
        created_at=parse_datetime(row["created_at"]),
        updated_at=parse_datetime(row["updated_at"]),
    )


class PostgresAuditLogRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork | Any) -> None:
        self._uow = uow

    async def add(self, entry: AuditLog) -> AuditLog:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO audit_logs (
                    id, action, outcome, resource_type, resource_id, actor_user_id,
                    occurred_at, ip_address, user_agent, message, metadata,
                    created_at, updated_at
                ) VALUES (
                    :id, :action, :outcome, :resource_type, :resource_id,
                    :actor_user_id, :occurred_at, :ip_address, :user_agent,
                    :message, CAST(:metadata AS jsonb), :created_at, :updated_at
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(entry.id),
                "action": entry.action.value,
                "outcome": entry.outcome.value,
                "resource_type": entry.resource_type,
                "resource_id": (str(entry.resource_id) if entry.resource_id else None),
                "actor_user_id": (
                    str(entry.actor_user_id) if entry.actor_user_id else None
                ),
                "occurred_at": entry.occurred_at,
                "ip_address": entry.ip_address,
                "user_agent": entry.user_agent,
                "message": entry.message,
                "metadata": as_json(entry.metadata),
                "created_at": entry.created_at,
                "updated_at": entry.updated_at,
            },
        )
        return entry

    async def list_recent(self, *, limit: int = 200) -> list[AuditLog]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM audit_logs
                ORDER BY COALESCE(occurred_at, created_at) DESC
                LIMIT :limit
                """
            ),
            {"limit": limit},
        )
        return [_audit_from_row(r) for r in result.mappings().all()]


class PostgresUserRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def get_by_id(self, user_id: UUID) -> User | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM users WHERE id = :id"),
            {"id": str(user_id)},
        )
        row = result.mappings().first()
        return _user_from_row(row) if row else None

    async def get_by_email(self, email: EmailAddress) -> User | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM users WHERE lower(email) = lower(:email)"),
            {"email": str(email)},
        )
        row = result.mappings().first()
        return _user_from_row(row) if row else None

    async def get_by_auth_user_id(self, auth_user_id: UUID) -> User | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM users WHERE auth_user_id = :auth_user_id"),
            {"auth_user_id": str(auth_user_id)},
        )
        row = result.mappings().first()
        return _user_from_row(row) if row else None

    async def add(self, user: User) -> User:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO users (
                    id, auth_user_id, email, display_name, role, status,
                    password_hash, last_login_at, deactivated_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :auth_user_id, :email, :display_name, :role, :status,
                    :password_hash, :last_login_at, :deactivated_at,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    auth_user_id = EXCLUDED.auth_user_id,
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    status = EXCLUDED.status,
                    password_hash = EXCLUDED.password_hash,
                    last_login_at = EXCLUDED.last_login_at,
                    deactivated_at = EXCLUDED.deactivated_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(user.id),
                "auth_user_id": (str(user.auth_user_id) if user.auth_user_id else None),
                "email": str(user.email),
                "display_name": str(user.display_name),
                "role": user.role.value,
                "status": user.status.value,
                "password_hash": user.password_hash,
                "last_login_at": user.last_login_at,
                "deactivated_at": user.deactivated_at,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            },
        )
        return user

    async def update(self, user: User) -> User:
        return await self.add(user)


class PostgresProfileRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def get_by_user_id(self, user_id: UUID) -> UserProfile | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _profile_from_row(row) if row else None

    async def get_by_username(self, username: str) -> UserProfile | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM user_profiles
                WHERE lower(username) = lower(:username)
                LIMIT 1
                """
            ),
            {"username": username},
        )
        row = result.mappings().first()
        return _profile_from_row(row) if row else None

    async def add(self, profile: UserProfile) -> UserProfile:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO user_profiles (
                    user_id, avatar_url, avatar_path, full_name, username, bio,
                    country_code, timezone, preferred_language, trading_experience,
                    risk_level, created_at, updated_at
                ) VALUES (
                    :user_id, :avatar_url, :avatar_path, :full_name, :username, :bio,
                    :country_code, :timezone, :preferred_language, :trading_experience,
                    :risk_level, :created_at, :updated_at
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    avatar_url = EXCLUDED.avatar_url,
                    avatar_path = EXCLUDED.avatar_path,
                    full_name = EXCLUDED.full_name,
                    username = EXCLUDED.username,
                    bio = EXCLUDED.bio,
                    country_code = EXCLUDED.country_code,
                    timezone = EXCLUDED.timezone,
                    preferred_language = EXCLUDED.preferred_language,
                    trading_experience = EXCLUDED.trading_experience,
                    risk_level = EXCLUDED.risk_level,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "user_id": str(profile.user_id),
                "avatar_url": profile.avatar_url,
                "avatar_path": profile.avatar_path,
                "full_name": profile.full_name,
                "username": profile.username,
                "bio": profile.bio,
                "country_code": profile.country_code,
                "timezone": profile.timezone,
                "preferred_language": profile.preferred_language,
                "trading_experience": profile.trading_experience.value,
                "risk_level": profile.risk_level.value,
                "created_at": profile.created_at,
                "updated_at": profile.updated_at,
            },
        )
        return profile

    async def update(self, profile: UserProfile) -> UserProfile:
        return await self.add(profile)


class PostgresSettingsRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def get_by_user_id(self, user_id: UUID) -> UserSettings | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM user_settings WHERE user_id = :user_id"),
            {"user_id": str(user_id)},
        )
        row = result.mappings().first()
        return _settings_from_row(row) if row else None

    async def add(self, settings: UserSettings) -> UserSettings:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO user_settings (
                    user_id, theme, notifications_enabled, email_marketing,
                    email_security, email_product, security_login_alerts,
                    security_require_reauth, session_timeout_minutes,
                    created_at, updated_at
                ) VALUES (
                    :user_id, :theme, :notifications_enabled, :email_marketing,
                    :email_security, :email_product, :security_login_alerts,
                    :security_require_reauth, :session_timeout_minutes,
                    :created_at, :updated_at
                )
                ON CONFLICT (user_id) DO UPDATE SET
                    theme = EXCLUDED.theme,
                    notifications_enabled = EXCLUDED.notifications_enabled,
                    email_marketing = EXCLUDED.email_marketing,
                    email_security = EXCLUDED.email_security,
                    email_product = EXCLUDED.email_product,
                    security_login_alerts = EXCLUDED.security_login_alerts,
                    security_require_reauth = EXCLUDED.security_require_reauth,
                    session_timeout_minutes = EXCLUDED.session_timeout_minutes,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "user_id": str(settings.user_id),
                "theme": settings.theme.value,
                "notifications_enabled": settings.notifications_enabled,
                "email_marketing": settings.email_marketing,
                "email_security": settings.email_security,
                "email_product": settings.email_product,
                "security_login_alerts": settings.security_login_alerts,
                "security_require_reauth": settings.security_require_reauth,
                "session_timeout_minutes": settings.session_timeout_minutes,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at,
            },
        )
        return settings

    async def update(self, settings: UserSettings) -> UserSettings:
        return await self.add(settings)


class PostgresDeviceRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def list_for_user(self, user_id: UUID) -> list[UserDevice]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM user_devices
                WHERE user_id = :user_id
                ORDER BY last_seen_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_device_from_row(r) for r in result.mappings().all()]

    async def add(self, device: UserDevice) -> UserDevice:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO user_devices (
                    id, user_id, device_label, user_agent, last_seen_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :user_id, :device_label, :user_agent, :last_seen_at,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    device_label = EXCLUDED.device_label,
                    user_agent = EXCLUDED.user_agent,
                    last_seen_at = EXCLUDED.last_seen_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(device.id),
                "user_id": str(device.user_id),
                "device_label": device.device_label,
                "user_agent": device.user_agent,
                "last_seen_at": device.last_seen_at,
                "created_at": device.created_at,
                "updated_at": device.updated_at,
            },
        )
        return device

    async def delete(self, device_id: UUID, user_id: UUID) -> None:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                DELETE FROM user_devices
                WHERE id = :id AND user_id = :user_id
                """
            ),
            {"id": str(device_id), "user_id": str(user_id)},
        )


class PostgresSessionRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def list_active_for_user(self, user_id: UUID) -> list[UserSession]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM user_sessions
                WHERE user_id = :user_id AND is_active = true
                ORDER BY last_active_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_session_from_row(r) for r in result.mappings().all()]

    async def add(self, user_session: UserSession) -> UserSession:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO user_sessions (
                    id, user_id, device_id, ip_address, user_agent, is_active,
                    created_at, last_active_at, revoked_at, updated_at
                ) VALUES (
                    :id, :user_id, :device_id, :ip_address, :user_agent, :is_active,
                    :created_at, :last_active_at, :revoked_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    device_id = EXCLUDED.device_id,
                    ip_address = EXCLUDED.ip_address,
                    user_agent = EXCLUDED.user_agent,
                    is_active = EXCLUDED.is_active,
                    last_active_at = EXCLUDED.last_active_at,
                    revoked_at = EXCLUDED.revoked_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(user_session.id),
                "user_id": str(user_session.user_id),
                "device_id": (
                    str(user_session.device_id) if user_session.device_id else None
                ),
                "ip_address": user_session.ip_address,
                "user_agent": user_session.user_agent,
                "is_active": user_session.is_active,
                "created_at": user_session.created_at,
                "last_active_at": user_session.last_active_at,
                "revoked_at": user_session.revoked_at,
                "updated_at": user_session.updated_at,
            },
        )
        return user_session

    async def update(self, user_session: UserSession) -> UserSession:
        return await self.add(user_session)

    async def get_by_id(self, session_id: UUID) -> UserSession | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM user_sessions WHERE id = :id"),
            {"id": str(session_id)},
        )
        row = result.mappings().first()
        return _session_from_row(row) if row else None


class PostgresOrganizationMemberRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def list_for_organization(
        self, organization_id: UUID
    ) -> list[OrganizationMember]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM organization_members
                WHERE organization_id = :organization_id
                """
            ),
            {"organization_id": str(organization_id)},
        )
        return [_member_from_row(r) for r in result.mappings().all()]

    async def get_membership(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM organization_members
                WHERE organization_id = :organization_id AND user_id = :user_id
                LIMIT 1
                """
            ),
            {
                "organization_id": str(organization_id),
                "user_id": str(user_id),
            },
        )
        row = result.mappings().first()
        return _member_from_row(row) if row else None

    async def add(self, member: OrganizationMember) -> OrganizationMember:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO organization_members (
                    id, organization_id, user_id, role, status, joined_at,
                    created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :user_id, :role, :status, :joined_at,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    user_id = EXCLUDED.user_id,
                    role = EXCLUDED.role,
                    status = EXCLUDED.status,
                    joined_at = EXCLUDED.joined_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(member.id),
                "organization_id": str(member.organization_id),
                "user_id": str(member.user_id),
                "role": member.role.value,
                "status": member.status.value,
                "joined_at": member.joined_at,
                "created_at": member.created_at,
                "updated_at": member.updated_at,
            },
        )
        return member

    async def update(self, member: OrganizationMember) -> OrganizationMember:
        return await self.add(member)


class PostgresOrganizationRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow
        self.memberships: PostgresOrganizationMemberRepository | None = None

    async def get_by_id(self, organization_id: UUID) -> Organization | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM organizations WHERE id = :id"),
            {"id": str(organization_id)},
        )
        row = result.mappings().first()
        return _org_from_row(row) if row else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM organizations
                WHERE lower(slug) = lower(:slug)
                LIMIT 1
                """
            ),
            {"slug": slug},
        )
        row = result.mappings().first()
        return _org_from_row(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[Organization]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT o.* FROM organizations o
                INNER JOIN organization_members m ON m.organization_id = o.id
                WHERE m.user_id = :user_id
                ORDER BY o.created_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_org_from_row(r) for r in result.mappings().all()]

    async def add(self, organization: Organization) -> Organization:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO organizations (
                    id, name, slug, org_type, owner_user_id, created_at, updated_at
                ) VALUES (
                    :id, :name, :slug, :org_type, :owner_user_id,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    slug = EXCLUDED.slug,
                    org_type = EXCLUDED.org_type,
                    owner_user_id = EXCLUDED.owner_user_id,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(organization.id),
                "name": organization.name,
                "slug": organization.slug,
                "org_type": organization.org_type.value,
                "owner_user_id": str(organization.owner_user_id),
                "created_at": organization.created_at,
                "updated_at": organization.updated_at,
            },
        )
        return organization


class PostgresInvitationRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def add(self, invitation: OrganizationInvitation) -> OrganizationInvitation:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO organization_invitations (
                    id, organization_id, email, role, invited_by, token_hash,
                    status, expires_at, accepted_at, created_at, updated_at
                ) VALUES (
                    :id, :organization_id, :email, :role, :invited_by, :token_hash,
                    :status, :expires_at, :accepted_at, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    email = EXCLUDED.email,
                    role = EXCLUDED.role,
                    invited_by = EXCLUDED.invited_by,
                    token_hash = EXCLUDED.token_hash,
                    status = EXCLUDED.status,
                    expires_at = EXCLUDED.expires_at,
                    accepted_at = EXCLUDED.accepted_at,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(invitation.id),
                "organization_id": str(invitation.organization_id),
                "email": invitation.email,
                "role": invitation.role.value,
                "invited_by": str(invitation.invited_by),
                "token_hash": invitation.token_hash,
                "status": invitation.status.value,
                "expires_at": invitation.expires_at,
                "accepted_at": invitation.accepted_at,
                "created_at": invitation.created_at,
                "updated_at": invitation.updated_at,
            },
        )
        return invitation

    async def get_by_id(self, invitation_id: UUID) -> OrganizationInvitation | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM organization_invitations WHERE id = :id"),
            {"id": str(invitation_id)},
        )
        row = result.mappings().first()
        return _invitation_from_row(row) if row else None

    async def list_pending(self, organization_id: UUID) -> list[OrganizationInvitation]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM organization_invitations
                WHERE organization_id = :organization_id AND status = 'pending'
                ORDER BY created_at DESC
                """
            ),
            {"organization_id": str(organization_id)},
        )
        return [_invitation_from_row(r) for r in result.mappings().all()]

    async def update(
        self, invitation: OrganizationInvitation
    ) -> OrganizationInvitation:
        return await self.add(invitation)


class PostgresActivityRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def add(self, event: ActivityEvent) -> ActivityEvent:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO activity_events (
                    id, user_id, category, action, message, metadata,
                    ip_address, user_agent, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :category, :action, :message,
                    CAST(:metadata AS jsonb), :ip_address, :user_agent,
                    :created_at, :updated_at
                )
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {
                "id": str(event.id),
                "user_id": str(event.user_id),
                "category": event.category.value,
                "action": event.action,
                "message": event.message,
                "metadata": as_json(event.metadata),
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
                "created_at": event.created_at,
                "updated_at": event.updated_at,
            },
        )
        return event

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ActivityEvent]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM activity_events
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"user_id": str(user_id), "limit": limit},
        )
        return [_activity_from_row(r) for r in result.mappings().all()]


class PostgresNotificationRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def add(self, notification: Notification) -> Notification:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO notifications (
                    id, user_id, category, title, body, is_read, read_at,
                    metadata, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :category, :title, :body, :is_read, :read_at,
                    CAST(:metadata AS jsonb), :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    category = EXCLUDED.category,
                    title = EXCLUDED.title,
                    body = EXCLUDED.body,
                    is_read = EXCLUDED.is_read,
                    read_at = EXCLUDED.read_at,
                    metadata = EXCLUDED.metadata,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(notification.id),
                "user_id": str(notification.user_id),
                "category": notification.category.value,
                "title": notification.title,
                "body": notification.body,
                "is_read": notification.is_read,
                "read_at": notification.read_at,
                "metadata": as_json(notification.metadata),
                "created_at": notification.created_at,
                "updated_at": notification.updated_at,
            },
        )
        return notification

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[Notification]:
        session = self._uow._require_session()
        if unread_only:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM notifications
                    WHERE user_id = :user_id AND is_read = false
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": str(user_id), "limit": limit},
            )
        else:
            result = await session.execute(
                text(
                    """
                    SELECT * FROM notifications
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"user_id": str(user_id), "limit": limit},
            )
        return [_notification_from_row(r) for r in result.mappings().all()]

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        session = self._uow._require_session()
        result = await session.execute(
            text("SELECT * FROM notifications WHERE id = :id"),
            {"id": str(notification_id)},
        )
        row = result.mappings().first()
        return _notification_from_row(row) if row else None

    async def update(self, notification: Notification) -> Notification:
        return await self.add(notification)


class PostgresNotificationPreferenceRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def list_for_user(self, user_id: UUID) -> list[NotificationPreference]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM notification_preferences
                WHERE user_id = :user_id
                ORDER BY category
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_pref_from_row(r) for r in result.mappings().all()]

    async def upsert(
        self, preference: NotificationPreference
    ) -> NotificationPreference:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO notification_preferences (
                    user_id, category, in_app, email, created_at, updated_at
                ) VALUES (
                    :user_id, :category, :in_app, :email, :created_at, :updated_at
                )
                ON CONFLICT (user_id, category) DO UPDATE SET
                    in_app = EXCLUDED.in_app,
                    email = EXCLUDED.email,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "user_id": str(preference.user_id),
                "category": preference.category.value,
                "in_app": preference.in_app,
                "email": preference.email,
                "created_at": preference.created_at,
                "updated_at": preference.updated_at,
            },
        )
        return preference


class PostgresStorageObjectRepository:
    def __init__(self, uow: PostgresPlatformUnitOfWork) -> None:
        self._uow = uow

    async def add(self, obj: StorageObject) -> StorageObject:
        session = self._uow._require_session()
        await session.execute(
            text(
                """
                INSERT INTO storage_objects (
                    id, user_id, bucket, object_path, content_type, size_bytes,
                    purpose, public_url, created_at, updated_at
                ) VALUES (
                    :id, :user_id, :bucket, :object_path, :content_type, :size_bytes,
                    :purpose, :public_url, :created_at, :updated_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    bucket = EXCLUDED.bucket,
                    object_path = EXCLUDED.object_path,
                    content_type = EXCLUDED.content_type,
                    size_bytes = EXCLUDED.size_bytes,
                    purpose = EXCLUDED.purpose,
                    public_url = EXCLUDED.public_url,
                    updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "id": str(obj.id),
                "user_id": str(obj.user_id),
                "bucket": obj.bucket,
                "object_path": obj.object_path,
                "content_type": obj.content_type,
                "size_bytes": obj.size_bytes,
                "purpose": obj.purpose.value,
                "public_url": obj.public_url,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
            },
        )
        return obj

    async def list_for_user(self, user_id: UUID) -> list[StorageObject]:
        session = self._uow._require_session()
        result = await session.execute(
            text(
                """
                SELECT * FROM storage_objects
                WHERE user_id = :user_id
                ORDER BY created_at DESC
                """
            ),
            {"user_id": str(user_id)},
        )
        return [_storage_from_row(r) for r in result.mappings().all()]


class PostgresPlatformUnitOfWork(PostgresUnitOfWorkBase):
    def __init__(self, database: DatabaseManager) -> None:
        super().__init__(database)
        self.users = PostgresUserRepository(self)
        self.audit_logs = PostgresAuditLogRepository(self)
        self.profiles = PostgresProfileRepository(self)
        self.settings = PostgresSettingsRepository(self)
        self.devices = PostgresDeviceRepository(self)
        self.sessions = PostgresSessionRepository(self)
        self.organization_members = PostgresOrganizationMemberRepository(self)
        self.organizations = PostgresOrganizationRepository(self)
        self.organizations.memberships = self.organization_members
        self.organization_invitations = PostgresInvitationRepository(self)
        self.activity_events = PostgresActivityRepository(self)
        self.notifications = PostgresNotificationRepository(self)
        self.notification_preferences = PostgresNotificationPreferenceRepository(self)
        self.storage_objects = PostgresStorageObjectRepository(self)


class PostgresPlatformUnitOfWorkFactory:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    def __call__(self) -> PostgresPlatformUnitOfWork:
        return PostgresPlatformUnitOfWork(self._database)
