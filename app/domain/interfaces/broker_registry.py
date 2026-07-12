"""Broker adapter registry port."""

from __future__ import annotations

from typing import Protocol

from app.domain.interfaces.broker_adapter import BrokerAdapterPort


class BrokerRegistryPort(Protocol):
    """Registers and resolves broker adapters by platform code."""

    def register(self, adapter: BrokerAdapterPort) -> None:
        """Register an adapter. Overwrites any prior adapter for the same code."""
        ...

    def unregister(self, platform_code: str) -> None:
        """Remove an adapter registration if present."""
        ...

    def get(self, platform_code: str) -> BrokerAdapterPort | None:
        """Return the adapter for ``platform_code``, or ``None``."""
        ...

    def list_platforms(self) -> list[str]:
        """Return sorted registered platform codes."""
        ...

    def has(self, platform_code: str) -> bool:
        """Return whether a platform code is registered."""
        ...
