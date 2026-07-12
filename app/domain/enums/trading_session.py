"""Trading session enumerations."""

from __future__ import annotations

from enum import StrEnum


class SessionStatus(StrEnum):
    """Lifecycle status of a trading session."""

    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"
    EXPIRED = "expired"
    TERMINATED = "terminated"
