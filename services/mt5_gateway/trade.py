"""Build MetaTrader5 trade request dicts and map filling modes."""

from __future__ import annotations

from typing import Any

from services.mt5_gateway.symbol_specs import normalize_volume, serialize_symbol_specs


# MT5 trade action / order type constants (mirror MetaTrader5 package values).
TRADE_ACTION_DEAL = 1
TRADE_ACTION_PENDING = 5
TRADE_ACTION_SLTP = 6
TRADE_ACTION_MODIFY = 7
TRADE_ACTION_REMOVE = 8
TRADE_ACTION_CLOSE_BY = 10

ORDER_TYPE_BUY = 0
ORDER_TYPE_SELL = 1
ORDER_TYPE_BUY_LIMIT = 2
ORDER_TYPE_SELL_LIMIT = 3
ORDER_TYPE_BUY_STOP = 4
ORDER_TYPE_SELL_STOP = 5

ORDER_TIME_GTC = 0
ORDER_FILLING_FOK = 0
ORDER_FILLING_IOC = 1
ORDER_FILLING_RETURN = 2

# Symbol filling_mode bit flags
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2
SYMBOL_FILLING_RETURN = 4

_ACTION_TO_ORDER_TYPE: dict[str, int] = {
    "buy": ORDER_TYPE_BUY,
    "sell": ORDER_TYPE_SELL,
    "buy_limit": ORDER_TYPE_BUY_LIMIT,
    "sell_limit": ORDER_TYPE_SELL_LIMIT,
    "buy_stop": ORDER_TYPE_BUY_STOP,
    "sell_stop": ORDER_TYPE_SELL_STOP,
}

_PENDING_ACTIONS = {
    "buy_limit",
    "sell_limit",
    "buy_stop",
    "sell_stop",
}

_FILLING_NAME = {
    ORDER_FILLING_FOK: "fok",
    ORDER_FILLING_IOC: "ioc",
    ORDER_FILLING_RETURN: "return",
}


def order_type_for_action(action: str) -> int:
    key = (action or "").strip().lower()
    if key not in _ACTION_TO_ORDER_TYPE:
        raise ValueError(f"unsupported trade action: {action}")
    return _ACTION_TO_ORDER_TYPE[key]


def is_market_action(action: str) -> bool:
    return (action or "").strip().lower() in {"buy", "sell"}


def pick_filling_mode(mt5: Any, symbol: str) -> int:
    """Choose an allowed filling mode for the symbol from live MT5 flags."""
    info = mt5.symbol_info(symbol)
    filling = int(getattr(info, "filling_mode", 0) or 0) if info is not None else 0
    if filling & SYMBOL_FILLING_IOC:
        return ORDER_FILLING_IOC
    if filling & SYMBOL_FILLING_FOK:
        return ORDER_FILLING_FOK
    if filling & SYMBOL_FILLING_RETURN:
        return ORDER_FILLING_RETURN
    # Sparse flags — many brokers still accept IOC for deals.
    return ORDER_FILLING_IOC


def filling_name(mode: int) -> str:
    return _FILLING_NAME.get(int(mode), f"unknown:{mode}")


def normalize_lot_for_symbol(mt5: Any, symbol: str, volume: float) -> tuple[float, dict[str, Any]]:
    """Align volume to live volume_min / volume_max / volume_step."""
    info = mt5.symbol_info(symbol)
    specs = serialize_symbol_specs(info) if info is not None else {}
    vmin = float(specs.get("volume_min") or 0.01)
    vmax = float(specs.get("volume_max") or 100.0)
    vstep = float(specs.get("volume_step") or 0.01)
    aligned = normalize_volume(volume, volume_min=vmin, volume_max=vmax, volume_step=vstep)
    return aligned, specs


def build_mt5_trade_request(
    mt5: Any,
    *,
    symbol: str,
    action: str,
    volume: float,
    price: float,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    deviation: int = 20,
    magic: int = 0,
    comment: str = "quantforg",
    position: int = 0,
    order_ticket: int = 0,
    oms_kind: str = "",
) -> dict[str, Any]:
    """Build a live MT5 request with broker-normalized volume and filling."""
    code = symbol.strip().upper()
    act = (action or "").strip().lower()
    kind = (oms_kind or "").strip().lower()

    # SL/TP modify on an open position
    if kind in {"sltp", "modify_sltp"} or act in {"sltp", "modify_sltp"}:
        pos = int(position or 0)
        if pos <= 0:
            raise ValueError("position ticket is required for SL/TP modify")
        return {
            "action": TRADE_ACTION_SLTP,
            "symbol": code,
            "position": pos,
            "sl": float(stop_loss or 0.0),
            "tp": float(take_profit or 0.0),
            "magic": int(magic),
            "comment": (comment or "quantforg-sltp")[:31],
        }

    # Pending modify
    if kind in {"modify_pending"} or (
        kind == "modify" and int(order_ticket or 0) > 0 and int(position or 0) <= 0
    ):
        ot = int(order_ticket or 0)
        if ot <= 0:
            raise ValueError("order ticket is required for pending modify")
        return {
            "action": TRADE_ACTION_MODIFY,
            "order": ot,
            "price": float(price),
            "sl": float(stop_loss or 0.0),
            "tp": float(take_profit or 0.0),
            "type_time": ORDER_TIME_GTC,
            "magic": int(magic),
            "comment": (comment or "quantforg-mod")[:31],
        }

    order_type = order_type_for_action(act)
    trade_action = TRADE_ACTION_PENDING if act in _PENDING_ACTIONS else TRADE_ACTION_DEAL
    filling = pick_filling_mode(mt5, code)
    aligned_volume, specs = normalize_lot_for_symbol(mt5, code, float(volume))
    if aligned_volume <= 0:
        raise ValueError(
            f"Lot size must be at least {specs.get('volume_min', '0.01')} "
            f"in {specs.get('volume_step', '0.01')} increments."
        )

    req: dict[str, Any] = {
        "action": trade_action,
        "symbol": code,
        "volume": float(aligned_volume),
        "type": order_type,
        "price": float(price),
        "sl": float(stop_loss or 0.0),
        "tp": float(take_profit or 0.0),
        "deviation": int(deviation),
        "magic": int(magic),
        "comment": (comment or "quantforg")[:31],
        "type_time": ORDER_TIME_GTC,
        "type_filling": filling,
    }
    # Close / partial close against a specific position ticket
    pos = int(position or 0)
    if pos > 0 and trade_action == TRADE_ACTION_DEAL:
        req["position"] = pos
    return req


def serialize_check_result(result: Any, request: dict[str, Any]) -> dict[str, Any]:
    if result is None:
        return {
            "retcode": 10013,
            "comment": "order_check returned None",
            "ok": False,
            "request": request,
        }
    retcode = int(getattr(result, "retcode", 10013) or 10013)
    comment = str(getattr(result, "comment", "") or "")
    return {
        "retcode": retcode,
        "comment": comment,
        "ok": retcode in {0, 10009},
        "balance": str(getattr(result, "balance", 0) or 0),
        "equity": str(getattr(result, "equity", 0) or 0),
        "margin": str(getattr(result, "margin", 0) or 0),
        "margin_free": str(getattr(result, "margin_free", 0) or 0),
        "profit": str(getattr(result, "profit", 0) or 0),
        "request": request,
        "type_filling": filling_name(int(request.get("type_filling", -1))),
    }


def serialize_send_result(result: Any, request: dict[str, Any]) -> dict[str, Any]:
    if result is None:
        return {
            "retcode": 10013,
            "comment": "order_send returned None — check AutoTrading / terminal",
            "ok": False,
            "order_ticket": 0,
            "deal_ticket": 0,
            "volume": str(request.get("volume", 0)),
            "price": str(request.get("price", 0)),
            "request": request,
        }
    retcode = int(getattr(result, "retcode", 10013) or 10013)
    comment = str(getattr(result, "comment", "") or "")
    return {
        "retcode": retcode,
        "comment": comment,
        "ok": retcode in {0, 10008, 10009},
        "order_ticket": int(getattr(result, "order", 0) or 0),
        "deal_ticket": int(getattr(result, "deal", 0) or 0),
        "volume": str(getattr(result, "volume", request.get("volume", 0)) or 0),
        "price": str(getattr(result, "price", request.get("price", 0)) or 0),
        "request": request,
        "type_filling": filling_name(int(request.get("type_filling", -1))),
    }
