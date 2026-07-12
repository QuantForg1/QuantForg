"""MarketContext entity — current regime snapshot for a market.

Why it exists
-------------
Aggregates session, calendar day type, open/closed state, and qualitative
liquidity/volatility profiles at a UTC instant. It is the output of the
Market Context Engine — not a trading signal and not an indicator set.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.events.base import DomainEvent
from app.domain.events.market_context import (
    MarketClosed,
    MarketContextCreated,
    MarketContextUpdated,
    MarketOpened,
    SessionChanged,
)
from app.domain.market_context.enums import (
    DayType,
    LiquidityLevel,
    MarketSession,
    MarketState,
    VolatilityLevel,
)
from app.domain.market_context.market_clock import MarketClock
from app.domain.value_objects.identity import SymbolCode


def _is_open_state(state: MarketState) -> bool:
    return state == MarketState.OPEN


@dataclass(eq=False, kw_only=True)
class MarketContext(Entity):
    """Rich aggregate describing the market regime at ``as_of_utc``."""

    market_code: str
    timezone: str
    session: MarketSession
    market_state: MarketState
    day_type: DayType
    liquidity_level: LiquidityLevel
    volatility_level: VolatilityLevel
    as_of_utc: datetime
    local_time: datetime
    is_dst: bool
    utc_offset_minutes: int
    symbol_code: SymbolCode | None = None
    _pending_events: list[DomainEvent] = field(
        default_factory=list,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        require(bool(self.market_code.strip()), "market_code must not be blank")
        require(bool(self.timezone.strip()), "timezone must not be blank")
        self.as_of_utc = MarketClock.ensure_utc(self.as_of_utc)
        if self.local_time.tzinfo is None:
            raise ValueError("local_time must be timezone-aware")

    @classmethod
    def create(
        cls,
        *,
        market_code: str,
        timezone: str,
        session: MarketSession,
        market_state: MarketState,
        day_type: DayType,
        liquidity_level: LiquidityLevel,
        volatility_level: VolatilityLevel,
        as_of_utc: datetime,
        local_time: datetime,
        is_dst: bool,
        utc_offset_minutes: int,
        symbol_code: str | SymbolCode | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create a context and record :class:`MarketContextCreated`."""
        code = None
        if symbol_code is not None:
            code = (
                symbol_code
                if isinstance(symbol_code, SymbolCode)
                else SymbolCode(value=symbol_code)
            )
        kwargs: dict[str, object] = {
            "market_code": market_code.strip().upper(),
            "timezone": timezone,
            "session": session,
            "market_state": market_state,
            "day_type": day_type,
            "liquidity_level": liquidity_level,
            "volatility_level": volatility_level,
            "as_of_utc": as_of_utc,
            "local_time": local_time,
            "is_dst": is_dst,
            "utc_offset_minutes": utc_offset_minutes,
            "symbol_code": code,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        context = cls(**kwargs)  # type: ignore[arg-type]
        context._record(
            MarketContextCreated(
                context_id=context.id,
                market_code=context.market_code,
                session=context.session.value,
                market_state=context.market_state.value,
                occurred_at=context.as_of_utc,
            )
        )
        if _is_open_state(context.market_state):
            context._record(
                MarketOpened(
                    context_id=context.id,
                    market_code=context.market_code,
                    session=context.session.value,
                    occurred_at=context.as_of_utc,
                )
            )
        else:
            context._record(
                MarketClosed(
                    context_id=context.id,
                    market_code=context.market_code,
                    market_state=context.market_state.value,
                    session=context.session.value,
                    occurred_at=context.as_of_utc,
                )
            )
        return context

    def apply_update(
        self,
        *,
        session: MarketSession,
        market_state: MarketState,
        day_type: DayType,
        liquidity_level: LiquidityLevel,
        volatility_level: VolatilityLevel,
        as_of_utc: datetime,
        local_time: datetime,
        is_dst: bool,
        utc_offset_minutes: int,
    ) -> None:
        """Refresh context fields and emit lifecycle events as needed."""
        previous_session = self.session
        previous_state = self.market_state

        self.session = session
        self.market_state = market_state
        self.day_type = day_type
        self.liquidity_level = liquidity_level
        self.volatility_level = volatility_level
        self.as_of_utc = MarketClock.ensure_utc(as_of_utc)
        if local_time.tzinfo is None:
            raise ValueError("local_time must be timezone-aware")
        self.local_time = local_time
        self.is_dst = is_dst
        self.utc_offset_minutes = utc_offset_minutes
        self.touch()

        self._record(
            MarketContextUpdated(
                context_id=self.id,
                market_code=self.market_code,
                session=self.session.value,
                market_state=self.market_state.value,
                liquidity_level=self.liquidity_level.value,
                volatility_level=self.volatility_level.value,
                occurred_at=self.as_of_utc,
            )
        )

        if previous_session != self.session:
            self._record(
                SessionChanged(
                    context_id=self.id,
                    market_code=self.market_code,
                    previous_session=previous_session.value,
                    current_session=self.session.value,
                    occurred_at=self.as_of_utc,
                )
            )

        was_open = _is_open_state(previous_state)
        is_open = _is_open_state(self.market_state)
        if not was_open and is_open:
            self._record(
                MarketOpened(
                    context_id=self.id,
                    market_code=self.market_code,
                    session=self.session.value,
                    occurred_at=self.as_of_utc,
                )
            )
        elif was_open and not is_open:
            self._record(
                MarketClosed(
                    context_id=self.id,
                    market_code=self.market_code,
                    market_state=self.market_state.value,
                    session=self.session.value,
                    occurred_at=self.as_of_utc,
                )
            )

    @property
    def is_market_open(self) -> bool:
        return _is_open_state(self.market_state)

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events."""
        events = list(self._pending_events)
        self._pending_events.clear()
        return events

    def _record(self, event: DomainEvent) -> None:
        self._pending_events.append(event)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update(
            {
                "market_code": self.market_code,
                "symbol_code": str(self.symbol_code) if self.symbol_code else None,
                "timezone": self.timezone,
                "session": self.session.value,
                "market_state": self.market_state.value,
                "day_type": self.day_type.value,
                "liquidity_level": self.liquidity_level.value,
                "volatility_level": self.volatility_level.value,
                "as_of_utc": self.as_of_utc.isoformat(),
                "local_time": self.local_time.isoformat(),
                "is_dst": self.is_dst,
                "utc_offset_minutes": self.utc_offset_minutes,
                "is_market_open": self.is_market_open,
            }
        )
        return base
