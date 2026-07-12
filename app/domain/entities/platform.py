"""User platform domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
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
from app.domain.exceptions.base import ConflictError


@dataclass(eq=False, kw_only=True)
class UserProfile(Entity):
    """Extended profile for a platform user (1:1 with User)."""

    user_id: UUID
    avatar_url: str = ""
    avatar_path: str = ""
    full_name: str = ""
    username: str | None = None
    bio: str = ""
    country_code: str | None = None
    timezone: str = "UTC"
    preferred_language: str = "en"
    trading_experience: TradingExperience = TradingExperience.BEGINNER
    risk_level: ProfileRiskLevel = ProfileRiskLevel.MODERATE

    def __post_init__(self) -> None:
        self._normalize()
        self._validate()

    def _normalize(self) -> None:
        self.full_name = self.full_name.strip()
        self.bio = self.bio.strip()
        self.timezone = self.timezone.strip() or "UTC"
        self.preferred_language = self.preferred_language.strip().lower() or "en"
        if self.username is not None:
            self.username = self.username.strip() or None
        if self.country_code is not None:
            self.country_code = self.country_code.strip().upper() or None

    def _validate(self) -> None:
        require(len(self.bio) <= 1000, "bio must be at most 1000 characters")
        require(
            2 <= len(self.preferred_language) <= 16,
            "preferred_language length invalid",
        )
        if self.username is not None:
            require(
                3 <= len(self.username) <= 32
                and all(c.isalnum() or c == "_" for c in self.username),
                "username must be 3-32 alphanumeric/underscore characters",
            )
        if self.country_code is not None:
            require(
                len(self.country_code) == 2 and self.country_code.isalpha(),
                "country_code must be ISO-3166 alpha-2",
            )

    @classmethod
    def create_default(cls, *, user_id: UUID, full_name: str = "") -> Self:
        return cls(user_id=user_id, full_name=full_name, id=user_id)

    def update_fields(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)
        self._normalize()
        self._validate()
        self.touch()


@dataclass(eq=False, kw_only=True)
class UserSettings(Entity):
    user_id: UUID
    theme: UiTheme = UiTheme.SYSTEM
    notifications_enabled: bool = True
    email_marketing: bool = False
    email_security: bool = True
    email_product: bool = True
    security_login_alerts: bool = True
    security_require_reauth: bool = False
    session_timeout_minutes: int = 10080

    def __post_init__(self) -> None:
        require(
            5 <= self.session_timeout_minutes <= 525600,
            "session_timeout_minutes out of range",
        )

    @classmethod
    def create_default(cls, *, user_id: UUID) -> Self:
        return cls(user_id=user_id, id=user_id)

    def update_fields(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)
        require(
            5 <= self.session_timeout_minutes <= 525600,
            "session_timeout_minutes out of range",
        )
        self.touch()


@dataclass(eq=False, kw_only=True)
class UserDevice(Entity):
    user_id: UUID
    device_label: str = ""
    user_agent: str = ""
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def touch_seen(self) -> None:
        self.last_seen_at = datetime.now(UTC)
        self.touch()


@dataclass(eq=False, kw_only=True)
class UserSession(Entity):
    user_id: UUID
    device_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""
    is_active: bool = True
    last_active_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None

    def revoke(self) -> None:
        require_state(self.is_active, "Session already revoked")
        self.is_active = False
        self.revoked_at = datetime.now(UTC)
        self.touch()


@dataclass(eq=False, kw_only=True)
class Organization(Entity):
    name: str
    slug: str
    org_type: OrganizationType = OrganizationType.PERSONAL
    owner_user_id: UUID

    def __post_init__(self) -> None:
        self.name = self.name.strip()
        self.slug = self.slug.strip().lower()
        require(bool(self.name), "organization name required")
        require(bool(self.slug), "organization slug required")

    @classmethod
    def create_personal(cls, *, owner_user_id: UUID, display_name: str) -> Self:
        base = "".join(c if c.isalnum() else "-" for c in display_name.lower()).strip(
            "-"
        )
        slug = f"personal-{base[:24] or 'user'}-{str(owner_user_id)[:8]}"
        return cls(
            name=f"{display_name}'s Workspace",
            slug=slug,
            org_type=OrganizationType.PERSONAL,
            owner_user_id=owner_user_id,
        )

    @classmethod
    def create_team(cls, *, owner_user_id: UUID, name: str, slug: str) -> Self:
        return cls(
            name=name,
            slug=slug,
            org_type=OrganizationType.TEAM,
            owner_user_id=owner_user_id,
        )


@dataclass(eq=False, kw_only=True)
class OrganizationMember(Entity):
    organization_id: UUID
    user_id: UUID
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    status: OrganizationMemberStatus = OrganizationMemberStatus.ACTIVE
    joined_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(eq=False, kw_only=True)
class OrganizationInvitation(Entity):
    organization_id: UUID
    email: str
    role: OrganizationMemberRole = OrganizationMemberRole.MEMBER
    invited_by: UUID
    token_hash: str
    expires_at: datetime
    status: InvitationStatus = InvitationStatus.PENDING
    accepted_at: datetime | None = None

    def __post_init__(self) -> None:
        self.email = self.email.strip().lower()
        require(bool(self.email), "invitation email required")
        require(len(self.token_hash) >= 32, "token_hash too short")
        require(
            self.role != OrganizationMemberRole.OWNER,
            "cannot invite as owner",
        )

    def accept(self) -> None:
        require_state(
            self.status == InvitationStatus.PENDING,
            "Invitation is not pending",
        )
        require_state(
            self.expires_at > datetime.now(UTC),
            "Invitation has expired",
        )
        self.status = InvitationStatus.ACCEPTED
        self.accepted_at = datetime.now(UTC)
        self.touch()

    def revoke(self) -> None:
        require_state(
            self.status == InvitationStatus.PENDING,
            "Only pending invitations can be revoked",
        )
        self.status = InvitationStatus.REVOKED
        self.touch()


@dataclass(eq=False, kw_only=True)
class ActivityEvent(Entity):
    user_id: UUID
    category: ActivityCategory
    action: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    ip_address: str = ""
    user_agent: str = ""
    _frozen: bool = False

    def __post_init__(self) -> None:
        self.action = self.action.strip().lower()
        self.message = self.message.strip()
        require(bool(self.action) and len(self.action) <= 64, "invalid action")
        require(len(self.message) <= 1000, "message too long")
        self._frozen = True

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        category: ActivityCategory,
        action: str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
        ip_address: str = "",
        user_agent: str = "",
    ) -> Self:
        return cls(
            user_id=user_id,
            category=category,
            action=action,
            message=message,
            metadata=dict(metadata or {}),
            ip_address=ip_address,
            user_agent=user_agent,
            _frozen=False,
        )

    def touch(self) -> None:
        if self._frozen:
            raise ConflictError("ActivityEvent records are immutable")


@dataclass(eq=False, kw_only=True)
class Notification(Entity):
    user_id: UUID
    category: NotificationCategory
    title: str
    body: str = ""
    is_read: bool = False
    read_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.body = self.body.strip()
        require(bool(self.title) and len(self.title) <= 200, "invalid title")
        require(len(self.body) <= 2000, "body too long")

    def mark_read(self) -> None:
        if self.is_read:
            return
        self.is_read = True
        self.read_at = datetime.now(UTC)
        self.touch()


@dataclass(eq=False, kw_only=True)
class NotificationPreference(Entity):
    user_id: UUID
    category: NotificationCategory
    in_app: bool = True
    email: bool = True

    @classmethod
    def defaults_for_user(cls, user_id: UUID) -> list[NotificationPreference]:
        return [cls(user_id=user_id, category=cat) for cat in NotificationCategory]


@dataclass(eq=False, kw_only=True)
class StorageObject(Entity):
    user_id: UUID
    bucket: str = "avatars"
    object_path: str = ""
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    purpose: StoragePurpose = StoragePurpose.AVATAR
    public_url: str = ""

    def __post_init__(self) -> None:
        require(bool(self.object_path.strip()), "object_path required")
        require(self.size_bytes >= 0, "size_bytes must be >= 0")
