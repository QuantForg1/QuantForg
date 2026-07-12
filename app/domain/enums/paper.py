"""Paper Trading enumerations — simulation only, never live broker orders."""

from __future__ import annotations

from enum import StrEnum


class PaperOrderStatus(StrEnum):
    """Lifecycle of a paper order."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class PaperPositionStatus(StrEnum):
    """Lifecycle of a paper position."""

    OPENED = "opened"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class PaperOrderType(StrEnum):
    """Supported paper order types (simulation only)."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class PaperOrderSide(StrEnum):
    """Paper order / position side."""

    BUY = "buy"
    SELL = "sell"
