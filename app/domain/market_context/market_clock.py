"""MarketClock — timezone and DST aware clock façade.

Why it exists
-------------
Wraps :class:`ClockPort` and adds conversion helpers so every market-context
component works in UTC internally while presenting correct local wall times
(including DST transitions via IANA timezones).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.entities._guards import require
from app.domain.interfaces.market_context import ClockPort
from app.domain.market_context.value_objects import resolve_zone


@dataclass(frozen=True, slots=True)
class MarketClock:
    """DST-aware clock utilities over an injectable UTC :class:`ClockPort`."""

    clock: ClockPort

    def now_utc(self) -> datetime:
        """Return current time normalised to timezone-aware UTC."""
        moment = self.clock.now()
        return self.ensure_utc(moment)

    @staticmethod
    def ensure_utc(moment: datetime) -> datetime:
        """Coerce ``moment`` to timezone-aware UTC."""
        if moment.tzinfo is None:
            return moment.replace(tzinfo=UTC)
        return moment.astimezone(UTC)

    def zone(self, tz_name: str) -> ZoneInfo:
        """Resolve an IANA timezone (DST rules included)."""
        return resolve_zone(tz_name)

    def to_local(self, moment_utc: datetime, tz_name: str) -> datetime:
        """Convert a UTC instant to local wall time in ``tz_name``."""
        utc = self.ensure_utc(moment_utc)
        return utc.astimezone(self.zone(tz_name))

    def to_utc(self, local_moment: datetime, tz_name: str) -> datetime:
        """Interpret ``local_moment`` in ``tz_name`` and return UTC.

        If ``local_moment`` is naïve, it is treated as wall time in ``tz_name``.
        If it is aware, it is converted to UTC directly (``tz_name`` ignored for
        the conversion source, but validated).
        """
        resolve_zone(tz_name)
        if local_moment.tzinfo is None:
            local_aware = local_moment.replace(tzinfo=self.zone(tz_name))
            return local_aware.astimezone(UTC)
        return local_moment.astimezone(UTC)

    def is_dst(self, moment_utc: datetime, tz_name: str) -> bool:
        """Return True when DST is in effect at ``moment_utc`` in ``tz_name``."""
        local = self.to_local(moment_utc, tz_name)
        return bool(local.dst()) and local.dst() != timedelta(0)

    def utc_offset(self, moment_utc: datetime, tz_name: str) -> timedelta:
        """Return the UTC offset of ``tz_name`` at ``moment_utc`` (DST-aware)."""
        local = self.to_local(moment_utc, tz_name)
        offset = local.utcoffset()
        require(offset is not None, "timezone offset must be available")
        assert offset is not None  # narrow for type checkers
        return offset

    def local_date(self, moment_utc: datetime, tz_name: str) -> date:
        """Return the local calendar date for ``moment_utc`` in ``tz_name``."""
        return self.to_local(moment_utc, tz_name).date()
