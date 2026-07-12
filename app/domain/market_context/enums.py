"""Market-context enumerations.

Why these exist
---------------
They give the Market Context Engine a shared vocabulary for sessions,
market open/closed state, day types, and qualitative liquidity/volatility
regimes — without encoding indicator or strategy logic.
"""

from __future__ import annotations

from enum import StrEnum


class MarketSession(StrEnum):
    """Named trading session / regional liquidity window."""

    SYDNEY = "sydney"
    TOKYO = "tokyo"
    LONDON = "london"
    NEW_YORK = "new_york"
    LONDON_NY_OVERLAP = "london_ny_overlap"
    CLOSED = "closed"
    OFF_HOURS = "off_hours"


class MarketState(StrEnum):
    """Whether the referenced market is open for trading activity."""

    OPEN = "open"
    CLOSED = "closed"
    HOLIDAY = "holiday"
    WEEKEND = "weekend"


class DayType(StrEnum):
    """Calendar classification of the local market date."""

    TRADING_DAY = "trading_day"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class LiquidityLevel(StrEnum):
    """Qualitative liquidity regime (not a computed indicator)."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class VolatilityLevel(StrEnum):
    """Qualitative volatility regime (not a computed indicator)."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"
