"""Order enumerations."""

from __future__ import annotations

from enum import StrEnum


class OrderType(StrEnum):
    """Order execution style."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(StrEnum):
    """Direction of an order."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    """Lifecycle status of an order.

    Transitions are enforced by the Order aggregate — this enum only defines
    the allowed vocabulary.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class TimeInForce(StrEnum):
    """How long an order remains valid."""

    GTC = "gtc"  # Good till cancelled
    IOC = "ioc"  # Immediate or cancel
    FOK = "fok"  # Fill or kill
    DAY = "day"  # Valid for the trading day
