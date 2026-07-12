"""Fair Value Gap enumerations.

Why these exist
---------------
Shared vocabulary for FVG side, lifecycle, fill depth, and quality —
without encoding trade signals or classic indicators.
"""

from __future__ import annotations

from enum import StrEnum


class FairValueGapSide(StrEnum):
    """Directional classification of an FVG (structural, not a signal)."""

    BULLISH = "bullish"  # imbalance below price (gap up)
    BEARISH = "bearish"  # imbalance above price (gap down)


class FairValueGapState(StrEnum):
    """Lifecycle states for a fair value gap."""

    DETECTED = "detected"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    INVALIDATED = "invalidated"
    EXPIRED = "expired"


class FillKind(StrEnum):
    """How deeply price has filled the gap."""

    PARTIAL = "partial"
    FULL = "full"


class QualityGrade(StrEnum):
    """Discrete quality band derived from :class:`GapQuality` score."""

    A = "a"
    B = "b"
    C = "c"
    D = "d"
