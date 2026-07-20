"""Build MetaTrader5 trade request dicts and map filling modes."""

from __future__ import annotations

import logging
from typing import Any

from services.mt5_gateway.symbol_specs import normalize_volume, serialize_symbol_specs


logger = logging.getLogger("quantforg.mt5_gateway.trade")

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

# Symbol filling_mode bit flags (SYMBOL_FILLING_*)
SYMBOL_FILLING_FOK = 1
SYMBOL_FILLING_IOC = 2
SYMBOL_FILLING_RETURN = 4

# SYMBOL_TRADE_EXECUTION
EXEC_REQUEST = 0
EXEC_INSTANT = 1
EXEC_MARKET = 2
EXEC_EXCHANGE = 3

# SYMBOL_TRADE_MODE
TRADE_MODE_DISABLED = 0
TRADE_MODE_LONGONLY = 1
TRADE_MODE_SHORTONLY = 2
TRADE_MODE_CLOSEONLY = 3
TRADE_MODE_FULL = 4

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

# Retcodes that often mean wrong type_filling / malformed request fields.
_FILLING_RETRY_RETCODES = {10013, 10030}


def order_type_for_action(action: str) -> int:
    key = (action or "").strip().lower()
    if key not in _ACTION_TO_ORDER_TYPE:
        raise ValueError(f"unsupported trade action: {action}")
    return _ACTION_TO_ORDER_TYPE[key]


def is_market_action(action: str) -> bool:
    return (action or "").strip().lower() in {"buy", "sell"}


def filling_name(mode: int) -> str:
    return _FILLING_NAME.get(int(mode), f"unknown:{mode}")


def _exec_mode(info: Any) -> int:
    if info is None:
        return EXEC_MARKET
    return int(getattr(info, "trade_exemode", EXEC_MARKET) or EXEC_MARKET)


def candidate_filling_modes(info: Any) -> list[int]:
    """Ordered ORDER_TYPE_FILLING values allowed by symbol_info.filling_mode.

    Never hardcode a single mode. Prefer broker bit flags; when none are set,
    Market/Exchange execution typically requires RETURN (MQL5 docs).
    """
    filling = int(getattr(info, "filling_mode", 0) or 0) if info is not None else 0
    exec_mode = _exec_mode(info)
    ordered: list[int] = []

    # Prefer IOC then FOK for deal-style brokers that advertise both.
    if filling & SYMBOL_FILLING_IOC:
        ordered.append(ORDER_FILLING_IOC)
    if filling & SYMBOL_FILLING_FOK:
        ordered.append(ORDER_FILLING_FOK)
    if filling & SYMBOL_FILLING_RETURN:
        ordered.append(ORDER_FILLING_RETURN)

    if not ordered:
        if exec_mode in {EXEC_MARKET, EXEC_EXCHANGE}:
            ordered.append(ORDER_FILLING_RETURN)
        else:
            # Instant/Request: try FOK then IOC then RETURN.
            ordered.extend(
                [ORDER_FILLING_FOK, ORDER_FILLING_IOC, ORDER_FILLING_RETURN]
            )

    # Always keep a full fallback chain so order_check can retry on 10013/10030.
    for mode in (
        ORDER_FILLING_IOC,
        ORDER_FILLING_FOK,
        ORDER_FILLING_RETURN,
    ):
        if mode not in ordered:
            ordered.append(mode)
    return ordered


def pick_filling_mode(mt5: Any, symbol: str) -> int:
    """Choose the primary allowed filling mode for the symbol from live MT5 flags."""
    info = mt5.symbol_info(symbol)
    return candidate_filling_modes(info)[0]


def normalize_price(price: float, digits: int) -> float:
    """Round price to symbol digits — float drift causes Invalid Request."""
    d = max(0, int(digits))
    return round(float(price), d)


def resolve_deal_price(
    mt5: Any,
    *,
    symbol: str,
    order_type: int,
    price: float,
    digits: int,
    force_tick: bool = True,
) -> float:
    """BUY → SYMBOL_ASK, SELL → SYMBOL_BID for market deals when required."""
    # Even-numbered types are buys (0,2,4…), odd are sells (1,3,5…).
    want_ask = (int(order_type) % 2) == 0
    if force_tick or float(price or 0) <= 0:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"no quote for {symbol}")
        raw = float(tick.ask if want_ask else tick.bid)
        if raw <= 0:
            raise RuntimeError(f"invalid tick price for {symbol}")
        return normalize_price(raw, digits)
    return normalize_price(float(price), digits)


def normalize_lot_for_symbol(mt5: Any, symbol: str, volume: float) -> tuple[float, dict[str, Any]]:
    """Align volume to live volume_min / volume_max / volume_step."""
    info = mt5.symbol_info(symbol)
    specs = serialize_symbol_specs(info) if info is not None else {}
    vmin = float(specs.get("volume_min") or 0.01)
    vmax = float(specs.get("volume_max") or 100.0)
    vstep = float(specs.get("volume_step") or 0.01)
    aligned = normalize_volume(volume, volume_min=vmin, volume_max=vmax, volume_step=vstep)
    return aligned, specs


def validate_symbol_for_trade(
    info: Any,
    *,
    order_type: int,
    volume: float,
    is_close: bool = False,
) -> list[str]:
    """Compare request intent against symbol_info broker requirements."""
    if info is None:
        return ["symbol_info returned None"]
    notes: list[str] = []
    trade_mode = int(getattr(info, "trade_mode", TRADE_MODE_FULL) or 0)
    if trade_mode == TRADE_MODE_DISABLED:
        notes.append("trade_mode=disabled")
    if trade_mode == TRADE_MODE_CLOSEONLY and not is_close:
        notes.append("trade_mode=closeonly — new entries blocked")
    if trade_mode == TRADE_MODE_LONGONLY and int(order_type) % 2 == 1 and not is_close:
        notes.append("trade_mode=longonly — sell entry blocked")
    if trade_mode == TRADE_MODE_SHORTONLY and int(order_type) % 2 == 0 and not is_close:
        notes.append("trade_mode=shortonly — buy entry blocked")

    vmin = float(getattr(info, "volume_min", 0) or 0)
    vmax = float(getattr(info, "volume_max", 0) or 0)
    vstep = float(getattr(info, "volume_step", 0) or 0)
    if vmin > 0 and volume + 1e-12 < vmin:
        notes.append(f"volume {volume} < volume_min {vmin}")
    if vmax > 0 and volume - 1e-12 > vmax:
        notes.append(f"volume {volume} > volume_max {vmax}")
    if vstep > 0:
        steps = round(volume / vstep)
        if abs(volume - steps * vstep) > max(vstep * 1e-6, 1e-12):
            notes.append(f"volume {volume} not aligned to volume_step {vstep}")

    order_mode = int(getattr(info, "order_mode", -1) or -1)
    if order_mode > 0:
        # SYMBOL_ORDER_MODE flags (not ORDER_TYPE enum indices):
        # MARKET=1, LIMIT=2, STOP=4, STOP_LIMIT=8, SL=16, TP=32, CLOSEBY=64
        if order_type in {ORDER_TYPE_BUY, ORDER_TYPE_SELL}:
            needed = 1  # SYMBOL_ORDER_MARKET
        elif order_type in {ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT}:
            needed = 2  # SYMBOL_ORDER_LIMIT
        elif order_type in {ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP}:
            needed = 4  # SYMBOL_ORDER_STOP
        else:
            needed = 0
        if needed and (order_mode & needed) == 0:
            notes.append(
                f"order_mode={order_mode} does not allow order type {order_type}"
            )
    return notes


def mql_trade_request_fields(request: dict[str, Any]) -> dict[str, Any]:
    """Canonical MqlTradeRequest field dump for logging / diagnostics."""
    return {
        "action": int(request.get("action", 0) or 0),
        "symbol": str(request.get("symbol", "") or ""),
        "volume": float(request.get("volume", 0) or 0),
        "type": int(request.get("type", 0) or 0),
        "price": float(request.get("price", 0) or 0),
        "sl": float(request.get("sl", 0) or 0),
        "tp": float(request.get("tp", 0) or 0),
        "deviation": int(request.get("deviation", 0) or 0),
        "type_filling": int(request.get("type_filling", -1)),
        "type_filling_name": filling_name(int(request.get("type_filling", -1))),
        "type_time": int(request.get("type_time", 0) or 0),
        "expiration": int(request.get("expiration", 0) or 0),
        "magic": int(request.get("magic", 0) or 0),
        "comment": str(request.get("comment", "") or ""),
        "position": int(request.get("position", 0) or 0),
        "position_by": int(request.get("position_by", 0) or 0),
        "stoplimit": float(request.get("stoplimit", 0) or 0),
        "order": int(request.get("order", 0) or 0),
    }


def log_trade_request(request: dict[str, Any], *, stage: str, specs: dict[str, Any] | None = None) -> None:
    fields = mql_trade_request_fields(request)
    logger.info(
        "mt5_trade_request stage=%s fields=%s specs=%s",
        stage,
        fields,
        {
            "trade_mode": (specs or {}).get("trade_mode"),
            "execution_mode": (specs or {}).get("execution_mode"),
            "filling_mode": (specs or {}).get("filling_mode"),
            "volume_min": (specs or {}).get("volume_min"),
            "volume_max": (specs or {}).get("volume_max"),
            "volume_step": (specs or {}).get("volume_step"),
            "stops_level": (specs or {}).get("stops_level"),
            "freeze_level": (specs or {}).get("freeze_level"),
            "digits": (specs or {}).get("digits"),
            "point": (specs or {}).get("point"),
            "order_mode": (specs or {}).get("order_mode"),
        },
    )


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
    type_filling: int | None = None,
) -> dict[str, Any]:
    """Build a live MT5 request with broker-normalized volume, price, and filling.

    Every field mirrors MetaTrader5 Python ``MqlTradeRequest`` expectations.
    """
    code = symbol.strip().upper()
    act = (action or "").strip().lower()
    kind = (oms_kind or "").strip().lower()
    info = mt5.symbol_info(code)
    specs = serialize_symbol_specs(info) if info is not None else {}
    digits = int(specs.get("digits") or getattr(info, "digits", 5) or 5)

    # SL/TP modify on an open position
    if kind in {"sltp", "modify_sltp"} or act in {"sltp", "modify_sltp"}:
        pos = int(position or 0)
        if pos <= 0:
            raise ValueError("position ticket is required for SL/TP modify")
        req = {
            "action": TRADE_ACTION_SLTP,
            "magic": int(magic),
            "order": 0,
            "symbol": code,
            "volume": 0.0,
            "price": 0.0,
            "stoplimit": 0.0,
            "sl": normalize_price(float(stop_loss or 0.0), digits),
            "tp": normalize_price(float(take_profit or 0.0), digits),
            "deviation": 0,
            "type": 0,
            "type_filling": ORDER_FILLING_FOK,
            "type_time": ORDER_TIME_GTC,
            "expiration": 0,
            "comment": (comment or "quantforg-sltp")[:31],
            "position": pos,
            "position_by": 0,
        }
        log_trade_request(req, stage="build_sltp", specs=specs)
        return req

    # Pending modify
    if kind in {"modify_pending"} or (
        kind == "modify" and int(order_ticket or 0) > 0 and int(position or 0) <= 0
    ):
        ot = int(order_ticket or 0)
        if ot <= 0:
            raise ValueError("order ticket is required for pending modify")
        req = {
            "action": TRADE_ACTION_MODIFY,
            "magic": int(magic),
            "order": ot,
            "symbol": code,
            "volume": 0.0,
            "price": normalize_price(float(price), digits),
            "stoplimit": 0.0,
            "sl": normalize_price(float(stop_loss or 0.0), digits),
            "tp": normalize_price(float(take_profit or 0.0), digits),
            "deviation": 0,
            "type": 0,
            "type_filling": ORDER_FILLING_FOK,
            "type_time": ORDER_TIME_GTC,
            "expiration": 0,
            "comment": (comment or "quantforg-mod")[:31],
            "position": 0,
            "position_by": 0,
        }
        log_trade_request(req, stage="build_modify", specs=specs)
        return req

    order_type = order_type_for_action(act)
    trade_action = TRADE_ACTION_PENDING if act in _PENDING_ACTIONS else TRADE_ACTION_DEAL
    filling = (
        int(type_filling)
        if type_filling is not None
        else candidate_filling_modes(info)[0]
    )
    aligned_volume, specs = normalize_lot_for_symbol(mt5, code, float(volume))
    if aligned_volume <= 0:
        raise ValueError(
            f"Lot size must be at least {specs.get('volume_min', '0.01')} "
            f"in {specs.get('volume_step', '0.01')} increments."
        )

    pos = int(position or 0)
    is_close = pos > 0 and trade_action == TRADE_ACTION_DEAL
    violations = validate_symbol_for_trade(
        info, order_type=order_type, volume=aligned_volume, is_close=is_close
    )
    if violations:
        logger.warning(
            "mt5_trade_request_validation_warnings symbol=%s notes=%s",
            code,
            violations,
        )
        hard = [v for v in violations if "blocked" in v or "disabled" in v]
        if hard:
            raise ValueError("; ".join(hard))

    # Market / Instant / Request deals: always use live ASK/BID (never stale client price).
    if trade_action == TRADE_ACTION_DEAL:
        deal_price = resolve_deal_price(
            mt5,
            symbol=code,
            order_type=order_type,
            price=float(price or 0),
            digits=digits,
            force_tick=True,
        )
    else:
        if float(price or 0) <= 0:
            deal_price = resolve_deal_price(
                mt5,
                symbol=code,
                order_type=order_type,
                price=0.0,
                digits=digits,
                force_tick=True,
            )
        else:
            deal_price = normalize_price(float(price), digits)

    sl = float(stop_loss or 0.0)
    tp = float(take_profit or 0.0)
    req: dict[str, Any] = {
        "action": trade_action,
        "magic": int(magic),
        "order": int(order_ticket or 0),
        "symbol": code,
        "volume": float(aligned_volume),
        "price": deal_price,
        "stoplimit": 0.0,
        "sl": normalize_price(sl, digits) if sl > 0 else 0.0,
        "tp": normalize_price(tp, digits) if tp > 0 else 0.0,
        "deviation": int(deviation),
        "type": order_type,
        "type_filling": filling,
        "type_time": ORDER_TIME_GTC,
        "expiration": 0,
        "comment": (comment or "quantforg")[:31],
        "position": pos if is_close else 0,
        "position_by": 0,
    }
    # Attach order_mode into specs for logging when present on SymbolInfo.
    if info is not None and "order_mode" not in specs:
        specs = {**specs, "order_mode": int(getattr(info, "order_mode", 0) or 0)}
    log_trade_request(req, stage="build_deal_or_pending", specs=specs)
    return req


def apply_filling_mode(request: dict[str, Any], filling: int) -> dict[str, Any]:
    updated = dict(request)
    updated["type_filling"] = int(filling)
    return updated


def serialize_check_result(result: Any, request: dict[str, Any]) -> dict[str, Any]:
    if result is None:
        return {
            "retcode": 10013,
            "comment": "order_check returned None",
            "ok": False,
            "request": mql_trade_request_fields(request),
            "request_raw": request,
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
        "request": mql_trade_request_fields(request),
        "request_raw": request,
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
            "request": mql_trade_request_fields(request),
            "request_raw": request,
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
        "bid": str(getattr(result, "bid", 0) or 0),
        "ask": str(getattr(result, "ask", 0) or 0),
        "request": mql_trade_request_fields(request),
        "request_raw": request,
        "type_filling": filling_name(int(request.get("type_filling", -1))),
    }


def order_check_with_filling_fallback(
    mt5: Any,
    request: dict[str, Any],
    *,
    info: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """Run order_check; on Invalid Request / unsupported filling, try other modes."""
    symbol = str(request.get("symbol") or "")
    if info is None and symbol:
        info = mt5.symbol_info(symbol)
    modes = candidate_filling_modes(info)
    primary = int(request.get("type_filling", modes[0]))
    # Put primary first, then remaining candidates.
    try_modes = [primary] + [m for m in modes if m != primary]

    last_result: Any = None
    last_req = request
    attempts: list[dict[str, Any]] = []
    for mode in try_modes:
        last_req = apply_filling_mode(request, mode)
        log_trade_request(last_req, stage="order_check_attempt")
        last_result = mt5.order_check(last_req)
        retcode = (
            10013
            if last_result is None
            else int(getattr(last_result, "retcode", 10013) or 10013)
        )
        comment = (
            "order_check returned None"
            if last_result is None
            else str(getattr(last_result, "comment", "") or "")
        )
        attempts.append(
            {
                "type_filling": mode,
                "type_filling_name": filling_name(mode),
                "retcode": retcode,
                "comment": comment,
            }
        )
        if last_result is not None and retcode not in _FILLING_RETRY_RETCODES:
            break
        if last_result is not None and retcode in {0, 10009}:
            break

    logger.info("mt5_order_check_filling_attempts attempts=%s", attempts)
    # Attach attempts onto request dict copy for callers (non-MT5 field stripped later).
    annotated = dict(last_req)
    annotated["_filling_attempts"] = attempts
    return last_result, annotated
