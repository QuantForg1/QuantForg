"""Presentation schemas for User Platform."""

from __future__ import annotations

from uuid import UUID

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class ProfileResponse(BaseModel):
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


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    username: str | None = Field(default=None, min_length=3, max_length=32)
    bio: str | None = Field(default=None, max_length=1000)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    timezone: str | None = Field(default=None, max_length=64)
    preferred_language: str | None = Field(default=None, min_length=2, max_length=16)
    trading_experience: str | None = None
    risk_level: str | None = None


class SettingsResponse(BaseModel):
    user_id: UUID
    theme: str
    notifications_enabled: bool
    email_marketing: bool
    email_security: bool
    email_product: bool
    security_login_alerts: bool
    security_require_reauth: bool
    session_timeout_minutes: int
    default_symbol: str = "XAUUSD"
    default_timeframe: str = "M15"
    date_format: str = "ymd"
    time_format: str = "24h"
    dashboard_prefs: dict[str, Any] = Field(default_factory=dict)
    trading_ui_prefs: dict[str, Any] = Field(default_factory=dict)


class UpdateSettingsRequest(BaseModel):
    theme: str | None = None
    notifications_enabled: bool | None = None
    email_marketing: bool | None = None
    email_security: bool | None = None
    email_product: bool | None = None
    security_login_alerts: bool | None = None
    security_require_reauth: bool | None = None
    session_timeout_minutes: int | None = Field(default=None, ge=5, le=525600)
    default_symbol: str | None = Field(default=None, min_length=1, max_length=32)
    default_timeframe: str | None = Field(
        default=None,
        pattern=r"^(M1|M5|M15|M30|H1|H4|D1|W1|MN1)$",
    )
    date_format: Literal["ymd", "dmy", "mdy"] | None = None
    time_format: Literal["24h", "12h"] | None = None
    dashboard_prefs: dict[str, Any] | None = None
    trading_ui_prefs: dict[str, Any] | None = None


class DeviceResponse(BaseModel):
    id: UUID
    device_label: str
    user_agent: str
    last_seen_at: str


class SessionResponse(BaseModel):
    id: UUID
    ip_address: str
    user_agent: str
    is_active: bool
    created_at: str
    last_active_at: str


class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    org_type: str
    owner_user_id: UUID


class CreateTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=2, max_length=64)


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: str = "member"


class InvitationResponse(BaseModel):
    id: UUID
    organization_id: UUID
    email: str
    role: str
    status: str
    expires_at: str


class ActivityResponse(BaseModel):
    id: UUID
    category: str
    action: str
    message: str
    created_at: str
    metadata: dict[str, object] = Field(default_factory=dict)


class NotificationResponse(BaseModel):
    id: UUID
    category: str
    title: str
    body: str
    is_read: bool
    created_at: str


class NotificationPreferenceResponse(BaseModel):
    category: str
    in_app: bool
    email: bool


class UpdateNotificationPreferenceRequest(BaseModel):
    in_app: bool | None = None
    email: bool | None = None


class AvatarUploadResponse(BaseModel):
    avatar_url: str
    object_path: str
