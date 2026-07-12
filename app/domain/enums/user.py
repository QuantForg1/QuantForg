"""User-related enumerations."""

from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    """Authorisation role assigned to a platform user."""

    OWNER = "owner"
    ADMIN = "admin"
    TRADER = "trader"
    VIEWER = "viewer"
    SUPPORT = "support"


class UserStatus(StrEnum):
    """Lifecycle status of a user account."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
