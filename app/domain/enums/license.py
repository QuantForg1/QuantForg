"""License-related enumerations."""

from __future__ import annotations

from enum import StrEnum


class LicenseTier(StrEnum):
    """Commercial tier of a QuantForg license."""

    TRIAL = "trial"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class LicenseStatus(StrEnum):
    """Lifecycle status of a license grant."""

    PENDING = "pending"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
