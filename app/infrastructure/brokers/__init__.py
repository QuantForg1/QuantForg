"""Broker infrastructure package — adapters register here in future phases."""

from app.infrastructure.brokers.placeholders import (
    CTraderAdapter,
    DXtradeAdapter,
    MT4Adapter,
    MT5Adapter,
    PlaceholderBrokerAdapter,
    register_placeholder_adapters,
)
from app.infrastructure.brokers.registry import BrokerRegistry

__all__ = [
    "BrokerRegistry",
    "CTraderAdapter",
    "DXtradeAdapter",
    "MT4Adapter",
    "MT5Adapter",
    "PlaceholderBrokerAdapter",
    "register_placeholder_adapters",
]
