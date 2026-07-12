"""Unit tests for MarketContext entity, resolvers, and engine."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.domain.events.market_context import (
    MarketClosed,
    MarketContextCreated,
    MarketContextUpdated,
    MarketOpened,
    SessionChanged,
)
from app.domain.market_context.engine import MarketContextEngine
from app.domain.market_context.enums import (
    DayType,
    LiquidityLevel,
    MarketSession,
    MarketState,
    VolatilityLevel,
)
from app.domain.market_context.liquidity_resolver import LiquidityProfileResolver
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.session_resolver import SessionResolver
from app.domain.market_context.trading_calendar import TradingCalendarService
from app.domain.market_context.volatility_resolver import VolatilityProfileResolver
from tests.unit.market_context_fakes import (
    FakeCalendarPort,
    FakeClock,
    FakeLiquidityProfilePort,
    FakeSessionPort,
    FakeVolatilityProfilePort,
    fx_schedule,
)


def _engine(
    moment: datetime,
    *,
    holidays: set[date] | None = None,
) -> MarketContextEngine:
    clock = MarketClock(FakeClock(moment))
    return MarketContextEngine(
        clock=clock,
        sessions=SessionResolver(
            sessions=FakeSessionPort(fx_schedule()),
            clock=clock,
        ),
        calendar=TradingCalendarService(
            calendar=FakeCalendarPort(holidays=holidays),
            clock=clock,
        ),
        liquidity=LiquidityProfileResolver(FakeLiquidityProfilePort()),
        volatility=VolatilityProfileResolver(FakeVolatilityProfilePort()),
    )


@pytest.mark.unit
class TestLiquidityAndVolatilityResolvers:
    def test_overlap_profiles(self) -> None:
        liq = LiquidityProfileResolver(FakeLiquidityProfilePort())
        vol = VolatilityProfileResolver(FakeVolatilityProfilePort())
        assert (
            liq.resolve(
                "FX", MarketSession.LONDON_NY_OVERLAP, DayType.TRADING_DAY
            ).level
            == LiquidityLevel.VERY_HIGH
        )
        assert (
            vol.resolve(
                "FX", MarketSession.LONDON_NY_OVERLAP, DayType.TRADING_DAY
            ).level
            == VolatilityLevel.HIGH
        )


@pytest.mark.unit
class TestMarketContextEngine:
    def test_build_open_london_session(self) -> None:
        moment = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)
        context = _engine(moment).build("FX", symbol_code="EURUSD")
        assert context.session == MarketSession.LONDON
        assert context.market_state == MarketState.OPEN
        assert context.day_type == DayType.TRADING_DAY
        assert context.liquidity_level == LiquidityLevel.HIGH
        assert context.symbol_code is not None
        assert context.symbol_code.value == "EURUSD"
        assert context.is_dst is False  # reference tz is UTC
        events = context.pull_events()
        types = {type(e) for e in events}
        assert MarketContextCreated in types
        assert MarketOpened in types

    def test_build_closed_on_holiday(self) -> None:
        moment = datetime(2026, 12, 25, 14, 0, tzinfo=UTC)
        context = _engine(moment, holidays={date(2026, 12, 25)}).build("FX")
        assert context.day_type == DayType.HOLIDAY
        assert context.market_state == MarketState.HOLIDAY
        assert context.session == MarketSession.CLOSED
        events = context.pull_events()
        assert any(isinstance(e, MarketClosed) for e in events)

    def test_refresh_emits_session_and_close_events(self) -> None:
        open_moment = datetime(2026, 7, 14, 14, 0, tzinfo=UTC)  # overlap
        engine = _engine(open_moment)
        context = engine.build("FX")
        context.pull_events()  # clear creation events

        # Move clock to off-hours same day (outside all FX windows).
        off_hours = datetime(2026, 7, 14, 21, 0, tzinfo=UTC)
        engine = _engine(off_hours)
        engine.refresh(context, at=off_hours)

        assert context.session == MarketSession.OFF_HOURS
        assert context.market_state == MarketState.CLOSED
        events = context.pull_events()
        types = [type(e) for e in events]
        assert MarketContextUpdated in types
        assert SessionChanged in types
        assert MarketClosed in types

        session_event = next(e for e in events if isinstance(e, SessionChanged))
        assert session_event.previous_session == MarketSession.LONDON_NY_OVERLAP.value
        assert session_event.current_session == MarketSession.OFF_HOURS.value
