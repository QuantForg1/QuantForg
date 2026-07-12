"""Unit tests for MarketClock, SessionResolver, and TradingCalendarService."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest

from app.domain.market_context.enums import DayType, MarketSession, MarketState
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.session_resolver import SessionResolver
from app.domain.market_context.trading_calendar import TradingCalendarService
from app.domain.market_context.value_objects import (
    MarketSessionSchedule,
    SessionWindow,
)
from tests.unit.market_context_fakes import (
    FakeCalendarPort,
    FakeClock,
    FakeSessionPort,
    fx_schedule,
)


@pytest.mark.unit
class TestMarketClock:
    def test_utc_normalisation_and_local_conversion(self) -> None:
        clock = MarketClock(FakeClock(datetime(2026, 7, 12, 12, 0, tzinfo=UTC)))
        assert clock.now_utc().tzinfo == UTC
        local = clock.to_local(clock.now_utc(), "America/New_York")
        assert local.tzinfo is not None
        assert local.hour == 8  # EDT in July (UTC-4)

    def test_dst_flag_summer_vs_winter(self) -> None:
        clock = MarketClock(FakeClock(datetime(2026, 1, 15, 12, 0, tzinfo=UTC)))
        winter = datetime(2026, 1, 15, 17, 0, tzinfo=UTC)
        summer = datetime(2026, 7, 15, 16, 0, tzinfo=UTC)
        assert clock.is_dst(winter, "America/New_York") is False
        assert clock.is_dst(summer, "America/New_York") is True

    def test_utc_offset_changes_with_dst(self) -> None:
        clock = MarketClock(FakeClock(datetime(2026, 1, 1, tzinfo=UTC)))
        winter_offset = clock.utc_offset(
            datetime(2026, 1, 15, 12, 0, tzinfo=UTC),
            "Europe/London",
        )
        summer_offset = clock.utc_offset(
            datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
            "Europe/London",
        )
        assert winter_offset == timedelta(0)  # GMT
        assert summer_offset == timedelta(hours=1)  # BST

    def test_to_utc_interprets_naive_local(self) -> None:
        clock = MarketClock(FakeClock(datetime(2026, 7, 1, tzinfo=UTC)))
        # 08:00 America/New_York in July = 12:00 UTC
        utc = clock.to_utc(datetime(2026, 7, 1, 8, 0), "America/New_York")
        assert utc == datetime(2026, 7, 1, 12, 0, tzinfo=UTC)


@pytest.mark.unit
class TestSessionResolver:
    def test_london_session_in_bst(self) -> None:
        # 10:00 UTC in July = 11:00 BST → inside London 08:00-16:30
        moment = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
        resolver = SessionResolver(
            sessions=FakeSessionPort(fx_schedule()),
            clock=MarketClock(FakeClock(moment)),
        )
        assert resolver.resolve("FX", at=moment) == MarketSession.LONDON

    def test_overlap_has_priority(self) -> None:
        # 14:00 UTC is inside the UTC overlap window 13:00-17:00
        moment = datetime(2026, 7, 14, 14, 0, tzinfo=UTC)
        resolver = SessionResolver(
            sessions=FakeSessionPort(fx_schedule()),
            clock=MarketClock(FakeClock(moment)),
        )
        assert resolver.resolve("FX", at=moment) == MarketSession.LONDON_NY_OVERLAP

    def test_off_hours_when_no_window(self) -> None:
        # 21:00 UTC is outside overlap, London, NY (exclusive end), and Tokyo.
        moment = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)
        resolver = SessionResolver(
            sessions=FakeSessionPort(fx_schedule()),
            clock=MarketClock(FakeClock(moment)),
        )
        assert resolver.resolve("FX", at=moment) == MarketSession.OFF_HOURS

    def test_overnight_window(self) -> None:
        schedule = MarketSessionSchedule(
            market_code="CRYPTO",
            reference_timezone="UTC",
            windows=(
                SessionWindow(
                    session=MarketSession.SYDNEY,
                    timezone="UTC",
                    start_local=time(22, 0),
                    end_local=time(6, 0),
                    priority=10,
                ),
            ),
        )
        resolver = SessionResolver(
            sessions=FakeSessionPort(schedule),
            clock=MarketClock(FakeClock(datetime(2026, 1, 1, tzinfo=UTC))),
        )
        assert (
            resolver.resolve("CRYPTO", at=datetime(2026, 1, 1, 23, 0, tzinfo=UTC))
            == MarketSession.SYDNEY
        )
        assert (
            resolver.resolve("CRYPTO", at=datetime(2026, 1, 1, 5, 0, tzinfo=UTC))
            == MarketSession.SYDNEY
        )
        assert (
            resolver.resolve("CRYPTO", at=datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
            == MarketSession.OFF_HOURS
        )


@pytest.mark.unit
class TestTradingCalendarService:
    def test_weekend_and_holiday(self) -> None:
        calendar = FakeCalendarPort(holidays={date(2026, 12, 25)})
        service = TradingCalendarService(
            calendar=calendar,
            clock=MarketClock(FakeClock(datetime(2026, 12, 25, tzinfo=UTC))),
        )
        assert service.classify_date("FX", date(2026, 12, 25)) == DayType.HOLIDAY
        assert service.classify_date("FX", date(2026, 12, 26)) == DayType.WEEKEND
        assert service.classify_date("FX", date(2026, 12, 24)) == DayType.TRADING_DAY
        assert (
            service.market_state_from_calendar(
                "FX",
                at=datetime(2026, 12, 25, 12, 0, tzinfo=UTC),
                timezone="UTC",
            )
            == MarketState.HOLIDAY
        )
