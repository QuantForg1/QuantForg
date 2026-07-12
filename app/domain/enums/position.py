"""Position enumerations."""

from __future__ import annotations

from enum import StrEnum


class PositionSide(StrEnum):
    """Direction of an open position."""

    LONG = "long"
    SHORT = "short"


class PositionStatus(StrEnum):
    """Lifecycle status of a position."""

    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"
