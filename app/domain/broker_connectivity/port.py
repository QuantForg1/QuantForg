"""Broker Connectivity Port — full venue surface with structured unsupported."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.broker_connectivity.types import (
    BrokerCapabilityProfile,
    ConnectivityResult,
)


class BrokerConnectivityPort(Protocol):
    """Unified broker adapter contract for the Connectivity Framework."""

    platform: str
    name: str

    def capability_profile(self) -> BrokerCapabilityProfile: ...

    def connect(self, params: dict[str, Any]) -> ConnectivityResult: ...

    def disconnect(self) -> ConnectivityResult: ...

    def health(self) -> ConnectivityResult: ...

    def heartbeat(self) -> ConnectivityResult: ...

    def balances(self) -> ConnectivityResult: ...

    def positions(self) -> ConnectivityResult: ...

    def orders(self) -> ConnectivityResult: ...

    def history(self, *, limit: int = 100) -> ConnectivityResult: ...

    def symbols(self) -> ConnectivityResult: ...

    def quotes(self, symbol: str) -> ConnectivityResult: ...

    def candles(
        self, symbol: str, *, timeframe: str = "H1", count: int = 100
    ) -> ConnectivityResult: ...

    def trading(self, intent: dict[str, Any]) -> ConnectivityResult:
        """Trading entry — must respect EXECUTION_ENABLED in implementations."""
        ...

    def capabilities(self) -> ConnectivityResult: ...
