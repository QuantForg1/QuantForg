"""Unsupported / future broker connectivity adapter — clean structured refusals."""

from __future__ import annotations

from typing import Any

from app.domain.broker_connectivity.matrix import profile_for
from app.domain.broker_connectivity.types import (
    BrokerCapabilityProfile,
    ConnectivityCapability,
    ConnectivityResult,
    ConnectivityStatus,
)


class UnsupportedBrokerAdapter:
    """Future-ready adapter: every operation returns status=unsupported."""

    def __init__(self, platform: str, name: str | None = None) -> None:
        self.platform = platform.strip().lower()
        profile = profile_for(self.platform)
        self.name = name or (profile.name if profile else self.platform)

    def capability_profile(self) -> BrokerCapabilityProfile:
        profile = profile_for(self.platform)
        if profile is not None:
            return profile
        return BrokerCapabilityProfile(
            platform=self.platform,
            name=self.name,
            implemented=False,
            order_types=(),
            margin=False,
            leverage=False,
            netting=False,
            hedging=False,
            market_data=False,
            history=False,
            streaming=False,
            notes="Unknown platform — unsupported",
            capabilities=(),
        )

    def _unsupported(self, capability: ConnectivityCapability) -> ConnectivityResult:
        return ConnectivityResult(
            status=ConnectivityStatus.UNSUPPORTED,
            capability=capability,
            platform=self.platform,
            data=None,
            reason=(
                f"{self.name} adapter is not implemented. "
                "No simulated connectivity is provided."
            ),
        )

    def connect(self, params: dict[str, Any]) -> ConnectivityResult:
        _ = params
        return self._unsupported(ConnectivityCapability.CONNECT)

    def disconnect(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.DISCONNECT)

    def health(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.HEALTH)

    def heartbeat(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.HEARTBEAT)

    def balances(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.BALANCES)

    def positions(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.POSITIONS)

    def orders(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.ORDERS)

    def history(self, *, limit: int = 100) -> ConnectivityResult:
        _ = limit
        return self._unsupported(ConnectivityCapability.HISTORY)

    def symbols(self) -> ConnectivityResult:
        return self._unsupported(ConnectivityCapability.SYMBOLS)

    def quotes(self, symbol: str) -> ConnectivityResult:
        _ = symbol
        return self._unsupported(ConnectivityCapability.QUOTES)

    def candles(
        self, symbol: str, *, timeframe: str = "H1", count: int = 100
    ) -> ConnectivityResult:
        _ = symbol, timeframe, count
        return self._unsupported(ConnectivityCapability.CANDLES)

    def trading(self, intent: dict[str, Any]) -> ConnectivityResult:
        _ = intent
        return self._unsupported(ConnectivityCapability.TRADING)

    def capabilities(self) -> ConnectivityResult:
        profile = self.capability_profile()
        return ConnectivityResult(
            status=ConnectivityStatus.OK,
            capability=ConnectivityCapability.CAPABILITIES,
            platform=self.platform,
            data=profile.to_dict(),
            reason="Declared capability matrix only — adapter not implemented",
        )


def default_unsupported_adapters() -> list[UnsupportedBrokerAdapter]:
    return [
        UnsupportedBrokerAdapter("ctrader", "cTrader"),
        UnsupportedBrokerAdapter("interactive_brokers", "Interactive Brokers"),
        UnsupportedBrokerAdapter("binance", "Binance"),
        UnsupportedBrokerAdapter("bybit", "Bybit"),
        UnsupportedBrokerAdapter("okx", "OKX"),
        UnsupportedBrokerAdapter("oanda", "OANDA"),
        UnsupportedBrokerAdapter("fxcm", "FXCM"),
        UnsupportedBrokerAdapter("alpaca", "Alpaca"),
    ]
