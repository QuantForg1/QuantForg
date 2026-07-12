"""Trading account enumerations."""

from __future__ import annotations

from enum import StrEnum


class AccountType(StrEnum):
    """Type of trading account."""

    DEMO = "demo"
    LIVE = "live"
    CONTEST = "contest"


class AccountStatus(StrEnum):
    """Lifecycle status of a trading account."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"
