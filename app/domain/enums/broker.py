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


class BrokerPlatform(StrEnum):
    """Integration platform code for adapter selection.

    Concrete adapters (MT5, MT4, …) are registered against these codes.
    No adapter is implemented in the Broker Foundation phase.
    """

    MT5 = "mt5"
    MT4 = "mt4"
    CTRADER = "ctrader"
    DXTRADE = "dxtrade"
    OTHER = "other"


class BrokerCapabilityCode(StrEnum):
    """Capabilities an adapter may advertise for a broker."""

    CONNECT = "connect"
    DISCONNECT = "disconnect"
    VALIDATE = "validate"
    REFRESH = "refresh"
    ACCOUNT_INFO = "account_info"
    SYMBOLS = "symbols"
    BALANCES = "balances"
    POSITIONS = "positions"
    ORDERS = "orders"
    MARKET_DATA = "market_data"
    HISTORY = "history"


class BrokerHealthStatus(StrEnum):
    """Aggregated health status for a broker connection."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class BrokerAccountStatus(StrEnum):
    """Lifecycle status of a user-linked broker account."""

    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"


class BrokerEnvironment(StrEnum):
    """Trading environment for a broker account."""

    DEMO = "demo"
    LIVE = "live"


class BrokerCredentialType(StrEnum):
    """Kind of secret material stored for a broker account."""

    PASSWORD = "password"
    API_KEY = "api_key"
    API_SECRET = "api_secret"
    TOKEN = "token"
    CERTIFICATE = "certificate"


class BrokerConnectionStatus(StrEnum):
    """Runtime connection state for a broker account."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


# Sprint 1 alias — prefer BrokerConnectionStatus in new code.
ConnectionStatus = BrokerConnectionStatus


class CredentialStatus(StrEnum):
    """Lifecycle status of stored broker credential material."""

    ACTIVE = "active"
    ROTATED = "rotated"
    REVOKED = "revoked"
    EXPIRED = "expired"
