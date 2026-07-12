"""In-process broker adapter registry.

Adapters register by platform code (mt5, mt4, ctrader, dxtrade, …).
The foundation ships with an empty registry — no MT5/trading adapters.
"""

from __future__ import annotations

from app.domain.interfaces.broker_adapter import BrokerAdapterPort


class BrokerRegistry:
    """Thread-local process registry for broker adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapterPort] = {}

    def register(self, adapter: BrokerAdapterPort) -> None:
        code = adapter.platform_code.strip().lower()
        if not code:
            msg = "Adapter platform_code must be non-empty"
            raise ValueError(msg)
        self._adapters[code] = adapter

    def unregister(self, platform_code: str) -> None:
        self._adapters.pop(platform_code.strip().lower(), None)

    def get(self, platform_code: str) -> BrokerAdapterPort | None:
        return self._adapters.get(platform_code.strip().lower())

    def list_platforms(self) -> list[str]:
        return sorted(self._adapters)

    def has(self, platform_code: str) -> bool:
        return platform_code.strip().lower() in self._adapters

    def clear(self) -> None:
        self._adapters.clear()
