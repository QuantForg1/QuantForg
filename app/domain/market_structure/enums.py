"""Market-structure enumerations.

Why these exist
---------------
Shared vocabulary for swing classification, structure roles, and trend
state — without encoding trading signals or classic technical indicators.
"""

from __future__ import annotations

from enum import StrEnum


class SwingKind(StrEnum):
    """Whether a swing point is a pivot high or pivot low."""

    HIGH = "high"
    LOW = "low"


class StructureRole(StrEnum):
    """Role of a swing within the evolving market structure."""

    HIGHER_HIGH = "hh"
    HIGHER_LOW = "hl"
    LOWER_HIGH = "lh"
    LOWER_LOW = "ll"
    EQUAL_HIGH = "eqh"
    EQUAL_LOW = "eql"
    UNKNOWN = "unknown"


class TrendDirection(StrEnum):
    """Qualitative trend state derived from structure (not an indicator)."""

    UP = "up"
    DOWN = "down"
    RANGE = "range"
    UNKNOWN = "unknown"


class StructureBreakKind(StrEnum):
    """Kind of structural break event."""

    BOS = "bos"  # Break of Structure — with-trend
    CHOCH = "choch"  # Change of Character — against-trend
