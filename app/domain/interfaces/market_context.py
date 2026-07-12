"""Ports for the Market Context Engine.

Why these ports exist
---------------------
They isolate schedule, calendar, clock, and profile *configuration sources*
from the resolvers that interpret them. Infrastructure adapters (files, DB,
vendor calendars) implement these contracts later — this sprint defines
interfaces only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol

from app.domain.market_context.enums import DayType, MarketSession
from app.domain.market_context.value_objects import (
    LiquidityProfile,
    MarketSessionSchedule,
    VolatilityProfile,
)


class ClockPort(Protocol):
    """Supplies the current time in UTC.

    Why it exists
    -------------
    All market-context calculations start from a single injectable clock so
    tests can freeze time and production can share one time source.
    """

    def now(self) -> datetime:
        """Return timezone-aware UTC now."""
        ...


class SessionPort(Protocol):
    """Provides trading-session schedules per market.

    Why it exists
    -------------
    Session windows differ by asset class and venue. The port returns an
    immutable :class:`MarketSessionSchedule`; :class:`SessionResolver`
    interprets it against the clock.
    """

    def get_schedule(self, market_code: str) -> MarketSessionSchedule:
        """Return the session schedule for ``market_code``."""
        ...


class CalendarPort(Protocol):
    """Provides trading-calendar facts (weekends / holidays).

    Why it exists
    -------------
    Holidays are market-specific. The calendar port answers day-type
    questions without embedding a particular holiday database in the domain.
    """

    def is_weekend(self, market_code: str, local_date: date) -> bool:
        """Return True when ``local_date`` is a weekend for the market."""
        ...

    def is_holiday(self, market_code: str, local_date: date) -> bool:
        """Return True when ``local_date`` is a scheduled holiday."""
        ...

    def get_holidays(self, market_code: str, year: int) -> tuple[date, ...]:
        """Return known holidays for ``year`` (may be empty)."""
        ...


class LiquidityProfilePort(Protocol):
    """Provides qualitative liquidity profiles.

    Why it exists
    -------------
    Maps (session, day_type) → liquidity level from configuration, not from
    live order-book maths.
    """

    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> LiquidityProfile:
        """Return the liquidity profile for the given context key."""
        ...


class VolatilityProfilePort(Protocol):
    """Provides qualitative volatility profiles.

    Why it exists
    -------------
    Maps (session, day_type) → volatility level from configuration, not from
    indicator calculations.
    """

    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> VolatilityProfile:
        """Return the volatility profile for the given context key."""
        ...
