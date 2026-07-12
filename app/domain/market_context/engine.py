"""MarketContextEngine — orchestrates resolvers into a MarketContext.

Why it exists
-------------
Single entry point that combines clock, session, calendar, liquidity, and
volatility resolvers to create or refresh a :class:`MarketContext`. Emits
domain events via the aggregate. Does not trade, call MetaTrader, or run AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TypedDict
from uuid import UUID

from app.domain.market_context.enums import DayType, MarketSession, MarketState
from app.domain.market_context.liquidity_resolver import LiquidityProfileResolver
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.market_context import MarketContext
from app.domain.market_context.session_resolver import SessionResolver
from app.domain.market_context.trading_calendar import TradingCalendarService
from app.domain.market_context.value_objects import LiquidityProfile, VolatilityProfile
from app.domain.market_context.volatility_resolver import VolatilityProfileResolver
from app.domain.value_objects.identity import SymbolCode


class _ResolvedSnapshot(TypedDict):
    timezone: str
    session: MarketSession
    market_state: MarketState
    day_type: DayType
    liquidity: LiquidityProfile
    volatility: VolatilityProfile
    as_of_utc: datetime
    local_time: datetime
    is_dst: bool
    utc_offset_minutes: int


@dataclass(frozen=True, slots=True)
class MarketContextEngine:
    """Build and refresh :class:`MarketContext` aggregates."""

    clock: MarketClock
    sessions: SessionResolver
    calendar: TradingCalendarService
    liquidity: LiquidityProfileResolver
    volatility: VolatilityProfileResolver

    def build(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
        symbol_code: str | SymbolCode | None = None,
        entity_id: UUID | None = None,
    ) -> MarketContext:
        """Create a new market context for ``market_code`` at ``at`` (UTC)."""
        snapshot = self._resolve(market_code, at=at)
        return MarketContext.create(
            market_code=market_code,
            timezone=snapshot["timezone"],
            session=snapshot["session"],
            market_state=snapshot["market_state"],
            day_type=snapshot["day_type"],
            liquidity_level=snapshot["liquidity"].level,
            volatility_level=snapshot["volatility"].level,
            as_of_utc=snapshot["as_of_utc"],
            local_time=snapshot["local_time"],
            is_dst=snapshot["is_dst"],
            utc_offset_minutes=snapshot["utc_offset_minutes"],
            symbol_code=symbol_code,
            entity_id=entity_id,
        )

    def refresh(
        self,
        context: MarketContext,
        *,
        at: datetime | None = None,
    ) -> MarketContext:
        """Update ``context`` in place for a new instant and return it."""
        snapshot = self._resolve(context.market_code, at=at)
        context.apply_update(
            session=snapshot["session"],
            market_state=snapshot["market_state"],
            day_type=snapshot["day_type"],
            liquidity_level=snapshot["liquidity"].level,
            volatility_level=snapshot["volatility"].level,
            as_of_utc=snapshot["as_of_utc"],
            local_time=snapshot["local_time"],
            is_dst=snapshot["is_dst"],
            utc_offset_minutes=snapshot["utc_offset_minutes"],
        )
        return context

    def _resolve(
        self,
        market_code: str,
        *,
        at: datetime | None,
    ) -> _ResolvedSnapshot:
        moment = self.clock.ensure_utc(at or self.clock.now_utc())
        schedule = self.sessions.get_schedule(market_code)
        timezone = schedule.reference_timezone
        session = self.sessions.resolve(market_code, at=moment)
        day_type = self.calendar.day_type(
            market_code,
            at=moment,
            timezone=timezone,
        )
        calendar_state = self.calendar.market_state_from_calendar(
            market_code,
            at=moment,
            timezone=timezone,
        )

        # Calendar closed days force CLOSED regardless of session window.
        if calendar_state in {MarketState.HOLIDAY, MarketState.WEEKEND}:
            market_state = calendar_state
            if session not in {MarketSession.CLOSED, MarketSession.OFF_HOURS}:
                session = MarketSession.CLOSED
        elif session in {MarketSession.CLOSED, MarketSession.OFF_HOURS}:
            market_state = MarketState.CLOSED
        else:
            market_state = MarketState.OPEN

        liquidity = self.liquidity.resolve(market_code, session, day_type)
        volatility = self.volatility.resolve(market_code, session, day_type)
        local_time = self.clock.to_local(moment, timezone)
        offset = self.clock.utc_offset(moment, timezone)

        return {
            "timezone": timezone,
            "session": session,
            "market_state": market_state,
            "day_type": day_type,
            "liquidity": liquidity,
            "volatility": volatility,
            "as_of_utc": moment,
            "local_time": local_time,
            "is_dst": self.clock.is_dst(moment, timezone),
            "utc_offset_minutes": int(offset.total_seconds() // 60),
        }
