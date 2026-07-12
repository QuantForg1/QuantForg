"""TradingCalendarService — classify local market dates.

Why it exists
-------------
Decides whether a local calendar date is a trading day, weekend, or holiday
using :class:`CalendarPort`. DST-aware local dates come from
:class:`MarketClock`. No venue APIs or trade execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.interfaces.market_context import CalendarPort
from app.domain.market_context.enums import DayType, MarketState
from app.domain.market_context.market_clock import MarketClock


@dataclass(frozen=True, slots=True)
class TradingCalendarService:
    """Resolve day type and market-state hints from the trading calendar."""

    calendar: CalendarPort
    clock: MarketClock

    def day_type(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
        timezone: str = "UTC",
    ) -> DayType:
        """Classify the local date of ``at`` for ``market_code``."""
        moment = self.clock.ensure_utc(at or self.clock.now_utc())
        local_day = self.clock.local_date(moment, timezone)
        return self.classify_date(market_code, local_day)

    def classify_date(self, market_code: str, local_date: date) -> DayType:
        """Classify an explicit local calendar date."""
        if self.calendar.is_weekend(market_code, local_date):
            return DayType.WEEKEND
        if self.calendar.is_holiday(market_code, local_date):
            return DayType.HOLIDAY
        return DayType.TRADING_DAY

    def is_trading_day(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
        timezone: str = "UTC",
    ) -> bool:
        """Return True when the local date is a normal trading day."""
        return (
            self.day_type(market_code, at=at, timezone=timezone) == DayType.TRADING_DAY
        )

    def market_state_from_calendar(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
        timezone: str = "UTC",
    ) -> MarketState:
        """Map day type to a coarse market state (holiday/weekend/open hint)."""
        dtype = self.day_type(market_code, at=at, timezone=timezone)
        if dtype == DayType.HOLIDAY:
            return MarketState.HOLIDAY
        if dtype == DayType.WEEKEND:
            return MarketState.WEEKEND
        return MarketState.OPEN

    def holidays(self, market_code: str, year: int) -> tuple[date, ...]:
        """Proxy to :meth:`CalendarPort.get_holidays`."""
        return self.calendar.get_holidays(market_code, year)
