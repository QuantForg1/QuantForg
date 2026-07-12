"""UTC time provider foundation adapter."""

from __future__ import annotations

from datetime import UTC, datetime


class UtcTimeProvider:
    """Returns the current wall-clock time in UTC.

    Why it exists
    -------------
    Implements :class:`TimeProviderPort` so domain/application code never
    hard-codes ``datetime.now``. Tests can substitute a frozen provider.
    """

    def now(self) -> datetime:
        """Return timezone-aware UTC now."""
        return datetime.now(UTC)


class FixedTimeProvider:
    """Test/double time provider that always returns a fixed UTC instant.

    Why it exists
    -------------
    Makes market-data and event timestamps deterministic in unit tests.
    """

    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        else:
            moment = moment.astimezone(UTC)
        self._moment = moment

    def now(self) -> datetime:
        return self._moment
