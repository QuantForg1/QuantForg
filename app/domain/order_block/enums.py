"""Order-block enumerations.

Why these exist
---------------
Shared vocabulary for order-block lifecycle, side, origin, mitigation, and
quality — without encoding trade signals or classic indicators.
"""

from __future__ import annotations

from enum import StrEnum


class OrderBlockSide(StrEnum):
    """Directional bias of an order block (structural, not a signal)."""

    BULLISH = "bullish"  # demand / last down-close before up displacement
    BEARISH = "bearish"  # supply / last up-close before down displacement


class OrderBlockState(StrEnum):
    """Lifecycle states for an order block."""

    DETECTED = "detected"
    VALIDATED = "validated"
    ACTIVE = "active"
    MITIGATED = "mitigated"
    BREAKER = "breaker"
    EXPIRED = "expired"


class OrderBlockOrigin(StrEnum):
    """What structural event anchored the order block."""

    BOS = "bos"
    CHOCH = "choch"
    DISPLACEMENT = "displacement"


class MitigationKind(StrEnum):
    """How deeply price revisited the order-block zone."""

    PARTIAL = "partial"
    FULL = "full"


class QualityGrade(StrEnum):
    """Discrete quality band derived from :class:`OrderBlockQuality` score."""

    A = "a"
    B = "b"
    C = "c"
    D = "d"
