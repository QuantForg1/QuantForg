"""User platform application DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.domain.entities.platform import (
    ActivityEvent,
    Notification,
    NotificationPreference,
    Organization,
    OrganizationInvitation,
    UserDevice,
    UserProfile,
    UserSession,
    UserSettings,
)
from app.domain.enums.platform import (
    NotificationCategory,
    OrganizationMemberRole,
    ProfileRiskLevel,
    TradingExperience,
    UiTheme,
)


@dataclass(frozen=True, slots=True)
class ProfileDTO:
    user_id: UUID
    avatar_url: str
    full_name: str
    username: str | None
    bio: str
    country_code: str | None
    timezone: str
    preferred_language: str
    trading_experience: str
    risk_level: str

    @classmethod
    def from_entity(cls, profile: UserProfile) -> ProfileDTO:
        return cls(
            user_id=profile.user_id,
            avatar_url=profile.avatar_url,
            full_name=profile.full_name,
            username=profile.username,
            bio=profile.bio,
            country_code=profile.country_code,
            timezone=profile.timezone,
            preferred_language=profile.preferred_language,
            trading_experience=profile.trading_experience.value,
            risk_level=profile.risk_level.value,
        )


@dataclass(frozen=True, slots=True)
class UpdateProfileCommand:
    user_id: UUID
    full_name: str | None = None
    username: str | None = None
    bio: str | None = None
    country_code: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None
    trading_experience: TradingExperience | None = None
    risk_level: ProfileRiskLevel | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class SettingsDTO:
    user_id: UUID
    theme: str
    notifications_enabled: bool
    email_marketing: bool
    email_security: bool
    email_product: bool
    security_login_alerts: bool
    security_require_reauth: bool
    session_timeout_minutes: int

    @classmethod
    def from_entity(cls, settings: UserSettings) -> SettingsDTO:
        return cls(
            user_id=settings.user_id,
            theme=settings.theme.value,
            notifications_enabled=settings.notifications_enabled,
            email_marketing=settings.email_marketing,
            email_security=settings.email_security,
            email_product=settings.email_product,
            security_login_alerts=settings.security_login_alerts,
            security_require_reauth=settings.security_require_reauth,
            session_timeout_minutes=settings.session_timeout_minutes,
        )


@dataclass(frozen=True, slots=True)
class UpdateSettingsCommand:
    user_id: UUID
    theme: UiTheme | None = None
    notifications_enabled: bool | None = None
    email_marketing: bool | None = None
    email_security: bool | None = None
    email_product: bool | None = None
    security_login_alerts: bool | None = None
    security_require_reauth: bool | None = None
    session_timeout_minutes: int | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class DeviceDTO:
    id: UUID
    device_label: str
    user_agent: str
    last_seen_at: str

    @classmethod
    def from_entity(cls, device: UserDevice) -> DeviceDTO:
        return cls(
            id=device.id,
            device_label=device.device_label,
            user_agent=device.user_agent,
            last_seen_at=device.last_seen_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class SessionDTO:
    id: UUID
    ip_address: str
    user_agent: str
    is_active: bool
    created_at: str
    last_active_at: str

    @classmethod
    def from_entity(cls, session: UserSession) -> SessionDTO:
        return cls(
            id=session.id,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            is_active=session.is_active,
            created_at=session.created_at.isoformat(),
            last_active_at=session.last_active_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class OrganizationDTO:
    id: UUID
    name: str
    slug: str
    org_type: str
    owner_user_id: UUID

    @classmethod
    def from_entity(cls, org: Organization) -> OrganizationDTO:
        return cls(
            id=org.id,
            name=org.name,
            slug=org.slug,
            org_type=org.org_type.value,
            owner_user_id=org.owner_user_id,
        )


@dataclass(frozen=True, slots=True)
class CreateTeamCommand:
    owner_user_id: UUID
    name: str
    slug: str
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class InviteMemberCommand:
    organization_id: UUID
    invited_by: UUID
    email: str
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class InvitationDTO:
    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: str

    @classmethod
    def from_entity(cls, invitation: OrganizationInvitation) -> InvitationDTO:
        return cls(
            id=invitation.id,
            organization_id=invitation.organization_id,
            email=invitation.email,
            role=invitation.role.value,
            status=invitation.status.value,
            expires_at=invitation.expires_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class ActivityDTO:
    id: UUID
    category: str
    action: str
    message: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_entity(cls, event: ActivityEvent) -> ActivityDTO:
        return cls(
            id=event.id,
            category=event.category.value,
            action=event.action,
            message=event.message,
            created_at=event.created_at.isoformat(),
            metadata=dict(event.metadata),
        )


@dataclass(frozen=True, slots=True)
class NotificationDTO:
    id: UUID
    category: str
    title: str
    body: str
    is_read: bool
    created_at: str

    @classmethod
    def from_entity(cls, notification: Notification) -> NotificationDTO:
        return cls(
            id=notification.id,
            category=notification.category.value,
            title=notification.title,
            body=notification.body,
            is_read=notification.is_read,
            created_at=notification.created_at.isoformat(),
        )


@dataclass(frozen=True, slots=True)
class NotificationPreferenceDTO:
    category: str
    in_app: bool
    email: bool

    @classmethod
    def from_entity(cls, pref: NotificationPreference) -> NotificationPreferenceDTO:
        return cls(
            category=pref.category.value,
            in_app=pref.in_app,
            email=pref.email,
        )


@dataclass(frozen=True, slots=True)
class UpdateNotificationPreferenceCommand:
    user_id: UUID
    category: NotificationCategory
    in_app: bool | None = None
    email: bool | None = None


@dataclass(frozen=True, slots=True)
class EnsurePlatformBootstrapCommand:
    user_id: UUID
    display_name: str = ""
