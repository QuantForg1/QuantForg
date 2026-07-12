"""Broker-related enumerations."""

from __future__ import annotations

from enum import StrEnum


class BrokerType(StrEnum):
    """Classification of a brokerage venue.

    Describes the broker category for domain modelling. Does not imply any
    specific platform integration.
    """

    RETAIL = "retail"
    PRIME = "prime"
    ECN = "ecn"
    MARKET_MAKER = "market_maker"
    PROP = "prop"
    OTHER = "other"


class BrokerStatus(StrEnum):
    """Operational status of a registered broker."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"
