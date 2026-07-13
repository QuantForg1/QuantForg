"""Declared broker capability matrix — documentation of venue features."""

from __future__ import annotations

from app.domain.broker_connectivity.types import (
    BrokerCapabilityProfile,
    ConnectivityCapability,
)

_ALL = tuple(ConnectivityCapability)

_MT5_CAPS = (
    ConnectivityCapability.CONNECT,
    ConnectivityCapability.DISCONNECT,
    ConnectivityCapability.HEALTH,
    ConnectivityCapability.HEARTBEAT,
    ConnectivityCapability.BALANCES,
    ConnectivityCapability.POSITIONS,
    ConnectivityCapability.ORDERS,
    ConnectivityCapability.HISTORY,
    ConnectivityCapability.SYMBOLS,
    ConnectivityCapability.QUOTES,
    ConnectivityCapability.CANDLES,
    ConnectivityCapability.TRADING,
    ConnectivityCapability.CAPABILITIES,
)

# Declared venue profiles. unimplemented adapters still appear for matrix UI.
CAPABILITY_MATRIX: tuple[BrokerCapabilityProfile, ...] = (
    BrokerCapabilityProfile(
        platform="mt5",
        name="MetaTrader 5",
        implemented=True,
        order_types=("market", "limit", "stop", "stop_limit"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=True,
        market_data=True,
        history=True,
        streaming=False,
        notes="Live via existing MT5Adapter — streaming not exposed as push WS",
        capabilities=_MT5_CAPS,
    ),
    BrokerCapabilityProfile(
        platform="ctrader",
        name="cTrader",
        implemented=False,
        order_types=("market", "limit", "stop"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=True,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="interactive_brokers",
        name="Interactive Brokers",
        implemented=False,
        order_types=("market", "limit", "stop", "trailing_stop"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=True,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="binance",
        name="Binance",
        implemented=False,
        order_types=("market", "limit", "stop_loss", "take_profit"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=False,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported (intel market-data ≠ broker)",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="bybit",
        name="Bybit",
        implemented=False,
        order_types=("market", "limit", "conditional"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=False,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="okx",
        name="OKX",
        implemented=False,
        order_types=("market", "limit", "conditional"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=False,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="oanda",
        name="OANDA",
        implemented=False,
        order_types=("market", "limit", "stop"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=True,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="fxcm",
        name="FXCM",
        implemented=False,
        order_types=("market", "limit", "entry"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=True,
        market_data=True,
        history=True,
        streaming=False,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
    BrokerCapabilityProfile(
        platform="alpaca",
        name="Alpaca",
        implemented=False,
        order_types=("market", "limit", "stop", "trailing_stop"),
        margin=True,
        leverage=True,
        netting=True,
        hedging=False,
        market_data=True,
        history=True,
        streaming=True,
        notes="Future adapter — returns unsupported",
        capabilities=(),
    ),
)


def matrix_as_dicts() -> list[dict[str, object]]:
    return [p.to_dict() for p in CAPABILITY_MATRIX]


def profile_for(platform: str) -> BrokerCapabilityProfile | None:
    code = platform.strip().lower()
    for p in CAPABILITY_MATRIX:
        if p.platform == code:
            return p
    return None
