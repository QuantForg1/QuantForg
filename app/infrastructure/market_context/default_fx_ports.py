"""Production defaults for FX market context (session schedules, not prices)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from app.domain.market_context.enums import (
    DayType,
    LiquidityLevel,
    MarketSession,
    VolatilityLevel,
)
from app.domain.market_context.value_objects import (
    LiquidityProfile,
    MarketSessionSchedule,
    SessionWindow,
    VolatilityProfile,
)


class SystemClockPort:
    """UTC wall clock for market-context calculations."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class DefaultFxSessionPort:
    """Standard FX session windows (Tokyo / London / New York / overlap)."""

    def get_schedule(self, market_code: str) -> MarketSessionSchedule:
        code = (market_code or "FX").upper()
        return MarketSessionSchedule(
            market_code=code,
            reference_timezone="UTC",
            windows=(
                SessionWindow(
                    session=MarketSession.LONDON_NY_OVERLAP,
                    timezone="UTC",
                    start_local=time(13, 0),
                    end_local=time(17, 0),
                    priority=100,
                ),
                SessionWindow(
                    session=MarketSession.LONDON,
                    timezone="Europe/London",
                    start_local=time(8, 0),
                    end_local=time(16, 30),
                    priority=50,
                ),
                SessionWindow(
                    session=MarketSession.NEW_YORK,
                    timezone="America/New_York",
                    start_local=time(8, 0),
                    end_local=time(17, 0),
                    priority=40,
                ),
                SessionWindow(
                    session=MarketSession.TOKYO,
                    timezone="Asia/Tokyo",
                    start_local=time(9, 0),
                    end_local=time(18, 0),
                    priority=30,
                ),
            ),
        )


class WeekendCalendarPort:
    """Weekend classification only — no invented holiday vendor data."""

    def is_weekend(self, market_code: str, local_date: date) -> bool:
        _ = market_code
        return local_date.weekday() >= 5

    def is_holiday(self, market_code: str, local_date: date) -> bool:
        _ = market_code, local_date
        return False

    def get_holidays(self, market_code: str, year: int) -> tuple[date, ...]:
        _ = market_code, year
        return ()


class DefaultLiquidityProfilePort:
    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> LiquidityProfile:
        if day_type in {DayType.HOLIDAY, DayType.WEEKEND}:
            level = LiquidityLevel.VERY_LOW
        elif session == MarketSession.LONDON_NY_OVERLAP:
            level = LiquidityLevel.VERY_HIGH
        elif session in {MarketSession.LONDON, MarketSession.NEW_YORK}:
            level = LiquidityLevel.HIGH
        elif session == MarketSession.TOKYO:
            level = LiquidityLevel.MEDIUM
        else:
            level = LiquidityLevel.LOW
        return LiquidityProfile(
            level=level,
            session=session,
            day_type=day_type,
            label=f"{market_code}:{session.value}",
        )


class DefaultVolatilityProfilePort:
    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> VolatilityProfile:
        if day_type in {DayType.HOLIDAY, DayType.WEEKEND}:
            level = VolatilityLevel.VERY_LOW
        elif session == MarketSession.LONDON_NY_OVERLAP:
            level = VolatilityLevel.HIGH
        elif session == MarketSession.NEW_YORK:
            level = VolatilityLevel.MEDIUM
        else:
            level = VolatilityLevel.LOW
        return VolatilityProfile(
            level=level,
            session=session,
            day_type=day_type,
            label=f"{market_code}:{session.value}",
        )
