"""Local MT5 market order_send for multi-account OMS (Windows worker only).

Requires an already-authenticated portable terminal session.
Never logs passwords. Never uses Program Files LIVE terminal.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def execute_market_order(
    *,
    symbol: str,
    side: str,
    volume: str | float | Decimal,
    stop_loss: str | float | Decimal | None,
    take_profit: str | float | Decimal | None = None,
    deviation: int = 20,
    magic: int = 120212,
    comment: str = "qf-ma-oms",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Place a market order on the current MT5 session.

    Returns a sanitized result dict (no secrets).
    """
    sym = str(symbol or "").strip()
    sd = str(side or "").strip().upper()
    if not sym or sd not in {"BUY", "SELL"}:
        return {"ok": False, "error": "invalid_symbol_or_side", "order_send": False}
    if stop_loss is None or str(stop_loss).strip() == "":
        return {
            "ok": False,
            "error": "mandatory_stop_loss_missing",
            "order_send": False,
        }
    try:
        vol = float(Decimal(str(volume)))
        sl = float(Decimal(str(stop_loss)))
        tp = float(Decimal(str(take_profit))) if take_profit not in (None, "") else 0.0
    except Exception:
        return {"ok": False, "error": "invalid_numeric_fields", "order_send": False}
    if vol <= 0:
        return {"ok": False, "error": "volume_non_positive", "order_send": False}

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "order_send": False,
            "symbol": sym,
            "side": sd,
            "volume": str(vol),
            "stop_loss": str(sl),
            "take_profit": str(tp) if tp else None,
            "retcode": None,
            "order_ticket": None,
            "deal_ticket": None,
            "comment": "dry_run_no_broker_submit",
        }

    try:
        import MetaTrader5 as mt5  # type: ignore
    except Exception as exc:
        return {
            "ok": False,
            "error": "mt5_package_unavailable",
            "detail": type(exc).__name__,
            "order_send": False,
        }

    if not mt5.symbol_select(sym, True):
        return {"ok": False, "error": "symbol_select_failed", "symbol": sym}

    info = mt5.symbol_info(sym)
    tick = mt5.symbol_info_tick(sym)
    if info is None or tick is None:
        return {"ok": False, "error": "symbol_quote_unavailable", "symbol": sym}

    order_type = mt5.ORDER_TYPE_BUY if sd == "BUY" else mt5.ORDER_TYPE_SELL
    price = float(tick.ask if sd == "BUY" else tick.bid)
    point = float(getattr(info, "point", 0.0) or 0.0) or 0.01
    sl_adjusted = False
    # Keep mandatory SL, but ensure it is on the correct side of market.
    if sd == "BUY" and sl >= price:
        sl = price - max(point * 100.0, abs(price) * 0.001)
        sl_adjusted = True
    elif sd == "SELL" and sl <= price:
        sl = price + max(point * 100.0, abs(price) * 0.001)
        sl_adjusted = True
    if tp:
        if sd == "BUY" and tp <= price:
            tp = price + max(point * 150.0, abs(price) * 0.0015)
            sl_adjusted = True
        elif sd == "SELL" and tp >= price:
            tp = price - max(point * 150.0, abs(price) * 0.0015)
            sl_adjusted = True
    request: dict[str, Any] = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": sym,
        "volume": vol,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": int(deviation),
        "magic": int(magic),
        "comment": str(comment)[:31],
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    # Prefer symbol filling mode when available.
    filling = int(getattr(info, "filling_mode", 0) or 0)
    if filling & 1:
        request["type_filling"] = mt5.ORDER_FILLING_FOK
    elif filling & 2:
        request["type_filling"] = mt5.ORDER_FILLING_IOC

    result = mt5.order_send(request)
    if result is None:
        err = mt5.last_error()
        return {
            "ok": False,
            "error": "order_send_null",
            "mt5_last_error": str(err),
            "order_send": True,
            "symbol": sym,
            "side": sd,
            "volume": str(vol),
            "price": str(price),
        }

    retcode = int(getattr(result, "retcode", -1))
    ok = retcode == 10009  # TRADE_RETCODE_DONE
    return {
        "ok": ok,
        "order_send": True,
        "retcode": retcode,
        "order_ticket": int(getattr(result, "order", 0) or 0) or None,
        "deal_ticket": int(getattr(result, "deal", 0) or 0) or None,
        "symbol": sym,
        "side": sd,
        "volume": str(vol),
        "price": str(getattr(result, "price", price)),
        "comment": str(getattr(result, "comment", "") or "")[:200],
        "request_price": str(price),
        "stop_loss": str(sl),
        "take_profit": str(tp) if tp else None,
        "sl_adjusted_for_market": sl_adjusted,
    }
