"""Strategy metadata enumerations.

Describes catalogue entries for strategies. Does not define or execute
strategy logic.
"""

from __future__ import annotations

from enum import StrEnum


class StrategyType(StrEnum):
    """High-level strategy category (descriptive metadata)."""

    TREND = "trend"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    SCALPING = "scalping"
    GRID = "grid"
    CUSTOM = "custom"


class StrategyStatus(StrEnum):
    """Publication status of strategy metadata."""

    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"
