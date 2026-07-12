"""Time provider port.

Why it exists
-------------
Domain and application code must obtain "now" without calling
``datetime.now`` directly, so tests can inject a frozen clock and all
timestamps remain explicitly UTC.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class TimeProviderPort(Protocol):
    """Supplies the current UTC time."""

    def now(self) -> datetime:
        """Return the current time as timezone-aware UTC."""
        ...
