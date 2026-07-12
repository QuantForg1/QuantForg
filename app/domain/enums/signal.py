"""Signal enumerations.

Signal vocabulary only — no generation or AI logic lives here.
"""

from __future__ import annotations

from enum import StrEnum


class SignalDirection(StrEnum):
    """Suggested market direction carried by a signal."""

    BUY = "buy"
    SELL = "sell"
    NEUTRAL = "neutral"


class SignalStatus(StrEnum):
    """Lifecycle status of a signal."""

    PENDING = "pending"
    ACTIVE = "active"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class SignalSource(StrEnum):
    """Origin category of a signal (metadata only)."""

    MANUAL = "manual"
    SYSTEM = "system"
    EXTERNAL = "external"
    STRATEGY = "strategy"
