"""Canonical Telegram/Jimvio user-channel policy — Gold signals only.

Internal logs, metrics, and operator health monitoring stay elsewhere.
This module only gates what is delivered to Telegram/Jimvio *users*.
"""

from __future__ import annotations

from typing import Any

from app.application.services.telegram_events import (
    BREAKEVEN_SET,
    PARTIAL_CLOSE,
    PUBLIC_MARKET_SCAN,
    PUBLIC_MARKET_WATCH,
    SIGNAL_CONFIRMED,
    SIGNAL_GENERATED,
    SL_UPDATED,
    STOP_LOSS,
    TAKE_PROFIT,
    TRADE_CLOSED,
    TRADE_OPENED,
    TRAILING_STOP_UPDATED,
)
from app.domain.trading.gold_only import is_gold_symbol

# User-facing Telegram/Jimvio event types that may be delivered.
USER_SIGNAL_EVENTS: frozenset[str] = frozenset(
    {
        SIGNAL_GENERATED,  # "signal may be coming"
        SIGNAL_CONFIRMED,  # confirmed Gold signal
        TRADE_OPENED,  # reply/update after confirmed (public text sanitized)
        BREAKEVEN_SET,
        SL_UPDATED,
        TRAILING_STOP_UPDATED,
        PARTIAL_CLOSE,
        TAKE_PROFIT,
        STOP_LOSS,
        TRADE_CLOSED,
    }
)

# Explicitly blocked from Telegram/Jimvio user delivery (scanner / health chatter).
USER_BLOCKED_EVENTS: frozenset[str] = frozenset(
    {
        PUBLIC_MARKET_SCAN,
        PUBLIC_MARKET_WATCH,
        "ROBOT_STARTED",
        "ROBOT_STOPPED",
        "MT5_CONNECTED",
        "MT5_DISCONNECTED",
        "GATEWAY_ONLINE",
        "GATEWAY_OFFLINE",
        "SYSTEM_ERROR",
        "RISK_BLOCKED",
        "OMS_REJECTED",
        "ORDER_EXECUTION_ERROR",
        "TRADE_REJECTED",
        "SL_CREATED",
        "TP_CREATED",
        "TP_UPDATED",
        "TELEGRAM_TEST",
    }
)


def is_user_signal_event(event: str) -> bool:
    name = str(event or "").strip()
    if not name or name in USER_BLOCKED_EVENTS:
        return False
    return name in USER_SIGNAL_EVENTS


def symbol_allowed_for_user_signal(symbol: object) -> bool:
    return is_gold_symbol(str(symbol or ""))


def filter_user_signal_notices(
    notices: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Drop non-Gold and non-signal chatter before Telegram/Jimvio fan-out."""
    out: list[dict[str, Any]] = []
    for notice in notices:
        event = str(notice.get("event") or "")
        if not is_user_signal_event(event):
            continue
        _fields_value = notice.get("fields")
        fields = _fields_value if isinstance(_fields_value, dict) else {}
        symbol = fields.get("symbol") or notice.get("symbol")
        # Lifecycle replies may omit symbol if thread-bound; still require gold
        # when a symbol is present.
        if (
            symbol is not None
            and str(symbol).strip()
            and not symbol_allowed_for_user_signal(symbol)
        ):
            continue
        out.append(notice)
    return out


def notification_policy_diagnostics() -> dict[str, Any]:
    return {
        "user_signal_events": sorted(USER_SIGNAL_EVENTS),
        "user_blocked_events": sorted(USER_BLOCKED_EVENTS),
        "gold_only_user_channel": True,
        "scanner_chatter_disabled": True,
        "operator_internal_monitoring_unaffected": True,
    }
