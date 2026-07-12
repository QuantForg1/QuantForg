"""Capability discovery port — additive to BrokerAdapterPort."""

from __future__ import annotations

from typing import Protocol

from app.domain.enums.broker import BrokerCapabilityCode


class BrokerCapabilityDiscoveryPort(Protocol):
    """Optional adapter capability: report supported features."""

    def discover_capabilities(self) -> list[BrokerCapabilityCode]:
        """Return capability codes this adapter supports (static or probed)."""
        ...


# Default catalogue for platforms until live adapters exist.
_PLATFORM_CAPABILITIES: dict[str, tuple[BrokerCapabilityCode, ...]] = {
    "mt5": (
        BrokerCapabilityCode.CONNECT,
        BrokerCapabilityCode.DISCONNECT,
        BrokerCapabilityCode.VALIDATE,
        BrokerCapabilityCode.REFRESH,
        BrokerCapabilityCode.ACCOUNT_INFO,
        BrokerCapabilityCode.SYMBOLS,
        BrokerCapabilityCode.BALANCES,
        BrokerCapabilityCode.POSITIONS,
        BrokerCapabilityCode.ORDERS,
        BrokerCapabilityCode.MARKET_DATA,
        BrokerCapabilityCode.HISTORY,
    ),
    "mt4": (
        BrokerCapabilityCode.CONNECT,
        BrokerCapabilityCode.DISCONNECT,
        BrokerCapabilityCode.VALIDATE,
        BrokerCapabilityCode.ACCOUNT_INFO,
        BrokerCapabilityCode.SYMBOLS,
        BrokerCapabilityCode.BALANCES,
        BrokerCapabilityCode.POSITIONS,
        BrokerCapabilityCode.ORDERS,
        BrokerCapabilityCode.HISTORY,
    ),
    "ctrader": (
        BrokerCapabilityCode.CONNECT,
        BrokerCapabilityCode.DISCONNECT,
        BrokerCapabilityCode.VALIDATE,
        BrokerCapabilityCode.REFRESH,
        BrokerCapabilityCode.ACCOUNT_INFO,
        BrokerCapabilityCode.SYMBOLS,
        BrokerCapabilityCode.BALANCES,
        BrokerCapabilityCode.POSITIONS,
        BrokerCapabilityCode.ORDERS,
        BrokerCapabilityCode.MARKET_DATA,
    ),
    "dxtrade": (
        BrokerCapabilityCode.CONNECT,
        BrokerCapabilityCode.DISCONNECT,
        BrokerCapabilityCode.VALIDATE,
        BrokerCapabilityCode.ACCOUNT_INFO,
        BrokerCapabilityCode.SYMBOLS,
        BrokerCapabilityCode.BALANCES,
        BrokerCapabilityCode.POSITIONS,
        BrokerCapabilityCode.ORDERS,
    ),
    "other": (
        BrokerCapabilityCode.CONNECT,
        BrokerCapabilityCode.DISCONNECT,
        BrokerCapabilityCode.VALIDATE,
        BrokerCapabilityCode.ACCOUNT_INFO,
    ),
}


def default_capabilities_for_platform(
    platform_code: str,
) -> tuple[BrokerCapabilityCode, ...]:
    return _PLATFORM_CAPABILITIES.get(
        platform_code.strip().lower(),
        _PLATFORM_CAPABILITIES["other"],
    )


def discover_adapter_capabilities(adapter: object) -> list[BrokerCapabilityCode]:
    """Discover capabilities from an adapter if it implements the discovery port."""
    discover = getattr(adapter, "discover_capabilities", None)
    if callable(discover):
        result = discover()
        return list(result)
    platform = str(getattr(adapter, "platform_code", "other"))
    return list(default_capabilities_for_platform(platform))
