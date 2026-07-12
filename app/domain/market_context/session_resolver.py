"""SessionResolver — determine the active trading session at a UTC instant.

Why it exists
-------------
Maps UTC time onto named sessions (Tokyo, London, New York, overlaps, …)
using DST-aware local windows from :class:`SessionPort`. Does not trade or
compute indicators.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

from app.domain.interfaces.market_context import SessionPort
from app.domain.market_context.enums import MarketSession
from app.domain.market_context.market_clock import MarketClock
from app.domain.market_context.value_objects import MarketSessionSchedule, SessionWindow


@dataclass(frozen=True, slots=True)
class SessionResolver:
    """Resolve the active :class:`MarketSession` for a market at a moment."""

    sessions: SessionPort
    clock: MarketClock

    def resolve(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
    ) -> MarketSession:
        """Return the highest-priority matching session, or CLOSED/OFF_HOURS."""
        moment = self.clock.ensure_utc(at or self.clock.now_utc())
        schedule = self.get_schedule(market_code)
        match = self._match_window(schedule, moment)
        if match is not None:
            return match.session
        return MarketSession.OFF_HOURS

    def resolve_window(
        self,
        market_code: str,
        *,
        at: datetime | None = None,
    ) -> SessionWindow | None:
        """Return the matching :class:`SessionWindow`, if any."""
        moment = self.clock.ensure_utc(at or self.clock.now_utc())
        schedule = self.get_schedule(market_code)
        return self._match_window(schedule, moment)

    def get_schedule(self, market_code: str) -> MarketSessionSchedule:
        """Return the session schedule from :class:`SessionPort`."""
        return self.sessions.get_schedule(market_code)

    def _match_window(
        self,
        schedule: MarketSessionSchedule,
        moment_utc: datetime,
    ) -> SessionWindow | None:
        # Windows are already sorted by descending priority.
        for window in schedule.windows:
            if self._is_within(window, moment_utc):
                return window
        return None

    def _is_within(self, window: SessionWindow, moment_utc: datetime) -> bool:
        local = self.clock.to_local(moment_utc, window.timezone)
        local_t = local.timetz().replace(tzinfo=None)
        return self._time_in_window(local_t, window.start_local, window.end_local)

    @staticmethod
    def _time_in_window(current: time, start: time, end: time) -> bool:
        """Inclusive start, exclusive end; supports overnight windows."""
        if start < end:
            return start <= current < end
        # Overnight: e.g. 22:00 → 06:00
        return current >= start or current < end
