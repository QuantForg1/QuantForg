"""Broker connectivity adapters (MT5 live + future unsupported stubs)."""

from app.infrastructure.brokers.connectivity.mt5 import MT5ConnectivityAdapter
from app.infrastructure.brokers.connectivity.unsupported import (
    UnsupportedBrokerAdapter,
    default_unsupported_adapters,
)

__all__ = [
    "MT5ConnectivityAdapter",
    "UnsupportedBrokerAdapter",
    "default_unsupported_adapters",
]
