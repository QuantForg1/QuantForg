"""Test doubles for Market Context Engine ports (tests only)."""

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


class FakeClock:
    """Fixed UTC clock for deterministic tests."""

    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        self._moment = moment.astimezone(UTC)

    def now(self) -> datetime:
        return self._moment

    def set(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        self._moment = moment.astimezone(UTC)


class FakeSessionPort:
    """In-test session schedule provider."""

    def __init__(self, schedule: MarketSessionSchedule) -> None:
        self._schedule = schedule

    def get_schedule(self, market_code: str) -> MarketSessionSchedule:
        if market_code.upper() != self._schedule.market_code.upper():
            return MarketSessionSchedule(
                market_code=market_code,
                windows=(),
                reference_timezone=self._schedule.reference_timezone,
            )
        return self._schedule


class FakeCalendarPort:
    """In-test calendar with configurable weekends/holidays."""

    def __init__(
        self,
        *,
        holidays: set[date] | None = None,
        weekend_days: set[int] | None = None,
    ) -> None:
        self.holidays = holidays or set()
        # Python weekday(): Mon=0 … Sun=6
        self.weekend_days = weekend_days if weekend_days is not None else {5, 6}

    def is_weekend(self, market_code: str, local_date: date) -> bool:
        return local_date.weekday() in self.weekend_days

    def is_holiday(self, market_code: str, local_date: date) -> bool:
        return local_date in self.holidays

    def get_holidays(self, market_code: str, year: int) -> tuple[date, ...]:
        return tuple(sorted(d for d in self.holidays if d.year == year))


class FakeLiquidityProfilePort:
    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> LiquidityProfile:
        if day_type != DayType.TRADING_DAY:
            level = LiquidityLevel.VERY_LOW
        elif session == MarketSession.LONDON_NY_OVERLAP:
            level = LiquidityLevel.VERY_HIGH
        elif session in {MarketSession.LONDON, MarketSession.NEW_YORK}:
            level = LiquidityLevel.HIGH
        elif session in {MarketSession.TOKYO, MarketSession.SYDNEY}:
            level = LiquidityLevel.MEDIUM
        else:
            level = LiquidityLevel.LOW
        return LiquidityProfile(
            level=level,
            session=session,
            day_type=day_type,
            label=f"{market_code}:{session.value}",
        )


class FakeVolatilityProfilePort:
    def get_profile(
        self,
        market_code: str,
        session: MarketSession,
        day_type: DayType,
    ) -> VolatilityProfile:
        if day_type == DayType.HOLIDAY:
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


def fx_schedule() -> MarketSessionSchedule:
    """Representative FX session windows for tests (DST-aware zones)."""
    return MarketSessionSchedule(
        market_code="FX",
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
