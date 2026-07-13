"""Broker Connectivity Framework — structured results, never fake venues."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ConnectivityStatus(StrEnum):
    OK = "ok"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class ConnectivityCapability(StrEnum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    HEALTH = "health"
    HEARTBEAT = "heartbeat"
    BALANCES = "balances"
    POSITIONS = "positions"
    ORDERS = "orders"
    HISTORY = "history"
    SYMBOLS = "symbols"
    QUOTES = "quotes"
    CANDLES = "candles"
    TRADING = "trading"
    CAPABILITIES = "capabilities"


@dataclass(frozen=True, slots=True)
class ConnectivityResult:
    """Uniform adapter response — unsupported never crashes the platform."""

    status: ConnectivityStatus
    capability: ConnectivityCapability
    platform: str
    data: Any = None
    reason: str = ""
    latency_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "capability": self.capability.value,
            "platform": self.platform,
            "data": self.data,
            "reason": self.reason,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True, slots=True)
class BrokerCapabilityProfile:
    """Static/declared capability matrix row (not invented market state)."""

    platform: str
    name: str
    implemented: bool
    order_types: tuple[str, ...]
    margin: bool
    leverage: bool
    netting: bool
    hedging: bool
    market_data: bool
    history: bool
    streaming: bool
    notes: str = ""
    capabilities: tuple[ConnectivityCapability, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "name": self.name,
            "implemented": self.implemented,
            "order_types": list(self.order_types),
            "margin": self.margin,
            "leverage": self.leverage,
            "netting": self.netting,
            "hedging": self.hedging,
            "market_data": self.market_data,
            "history": self.history,
            "streaming": self.streaming,
            "notes": self.notes,
            "capabilities": [c.value for c in self.capabilities],
        }
