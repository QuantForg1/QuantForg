"""Placeholder broker adapters — registration only, no live implementation.

These classes exist so the Broker Registry can advertise future platforms.
Every method raises ``NotImplementedError`` until a real adapter sprint.
"""

from __future__ import annotations

from decimal import Decimal

from app.domain.enums.broker import BrokerCapabilityCode
from app.domain.interfaces.broker_adapter import (
    BrokerAccountInfo,
    BrokerBalanceInfo,
    BrokerConnectRequest,
    BrokerOrderInfo,
    BrokerPositionInfo,
    BrokerSymbolInfo,
)


class PlaceholderBrokerAdapter:
    """Base placeholder — not a live broker integration."""

    platform_code: str = "other"

    def _nyi(self, method: str) -> NotImplementedError:
        return NotImplementedError(
            f"{type(self).__name__}.{method} is not implemented "
            f"(Broker Foundation placeholder for '{self.platform_code}')"
        )

    async def connect(self, request: BrokerConnectRequest) -> str:
        _ = request
        raise self._nyi("connect")

    async def disconnect(self, *, session_ref: str) -> None:
        _ = session_ref
        raise self._nyi("disconnect")

    async def validate_credentials(self, request: BrokerConnectRequest) -> bool:
        _ = request
        raise self._nyi("validate_credentials")

    async def refresh_session(self, *, session_ref: str) -> str:
        _ = session_ref
        raise self._nyi("refresh_session")

    async def list_accounts(self, *, session_ref: str) -> list[BrokerAccountInfo]:
        _ = session_ref
        raise self._nyi("list_accounts")

    async def get_account_info(self, *, session_ref: str) -> BrokerAccountInfo:
        _ = session_ref
        raise self._nyi("get_account_info")

    async def get_balance(self, *, session_ref: str) -> BrokerBalanceInfo:
        _ = session_ref
        raise self._nyi("get_balance")

    async def get_equity(self, *, session_ref: str) -> Decimal:
        _ = session_ref
        raise self._nyi("get_equity")

    async def get_symbols(self, *, session_ref: str) -> list[BrokerSymbolInfo]:
        _ = session_ref
        raise self._nyi("get_symbols")

    async def get_positions(self, *, session_ref: str) -> list[BrokerPositionInfo]:
        _ = session_ref
        raise self._nyi("get_positions")

    async def get_orders(self, *, session_ref: str) -> list[BrokerOrderInfo]:
        _ = session_ref
        raise self._nyi("get_orders")

    def discover_capabilities(self) -> list[BrokerCapabilityCode]:
        from app.domain.interfaces.broker_capability_discovery import (
            default_capabilities_for_platform,
        )

        return list(default_capabilities_for_platform(self.platform_code))


class MT5PlaceholderAdapter(PlaceholderBrokerAdapter):
    """Legacy placeholder retained for non-MT5 registry bootstrap.

    The production connection-layer adapter lives in
    ``app.infrastructure.brokers.mt5.MT5Adapter`` and overwrites ``mt5``
    on the registry at container startup.
    """

    platform_code = "mt5"


class MT4Adapter(PlaceholderBrokerAdapter):
    """Future MetaTrader 4 adapter placeholder."""

    platform_code = "mt4"


class CTraderAdapter(PlaceholderBrokerAdapter):
    """Future cTrader adapter placeholder."""

    platform_code = "ctrader"


class DXtradeAdapter(PlaceholderBrokerAdapter):
    """Future DXtrade adapter placeholder."""

    platform_code = "dxtrade"


def register_placeholder_adapters(registry: object) -> None:
    """Register placeholder adapters; MT5 is overwritten by the real adapter."""
    register = getattr(registry, "register", None)
    if not callable(register):
        msg = "registry must expose register()"
        raise TypeError(msg)
    for adapter in (
        MT5PlaceholderAdapter(),
        MT4Adapter(),
        CTraderAdapter(),
        DXtradeAdapter(),
    ):
        register(adapter)


# Backward-compatible name for tests that still import placeholders.MT5Adapter
MT5Adapter = MT5PlaceholderAdapter
