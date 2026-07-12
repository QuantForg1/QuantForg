"""User platform enumerations."""

from __future__ import annotations

from enum import StrEnum


class TradingExperience(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    PROFESSIONAL = "professional"


class ProfileRiskLevel(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class UiTheme(StrEnum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class OrganizationType(StrEnum):
    PERSONAL = "personal"
    TEAM = "team"


class OrganizationMemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class OrganizationMemberStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    SUSPENDED = "suspended"
    LEFT = "left"


class InvitationStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ActivityCategory(StrEnum):
    LOGIN = "login"
    SECURITY = "security"
    PROFILE = "profile"
    API = "api"
    ORGANIZATION = "organization"


class NotificationCategory(StrEnum):
    SYSTEM = "system"
    SECURITY = "security"
    ORGANIZATION = "organization"
    TRADING = "trading"
    PRODUCT = "product"


class StoragePurpose(StrEnum):
    AVATAR = "avatar"
    PROFILE_ASSET = "profile_asset"
