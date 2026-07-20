"""Serialize live MetaTrader5 symbol trading constraints — never hardcode."""

from __future__ import annotations

from typing import Any


# SYMBOL_TRADE_MODE
_TRADE_MODE = {
    0: "disabled",
    1: "longonly",
    2: "shortonly",
    3: "closeonly",
    4: "full",
}

# SYMBOL_TRADE_EXECUTION
_EXEC_MODE = {
    0: "request",
    1: "instant",
    2: "market",
    3: "exchange",
}

# SYMBOL_TRADE_CALC_MODE (margin)
_MARGIN_CALC = {
    0: "forex",
    1: "futures",
    2: "cfd",
    3: "cfdindex",
    4: "cfdleverage",
    5: "forex_no_leverage",
}


def serialize_symbol_specs(info: Any, *, tick: Any | None = None) -> dict[str, Any]:
    """Map an MT5 SymbolInfo (+ optional tick) to a JSON-safe specs payload."""
    if info is None:
        raise RuntimeError("symbol_info returned None")

    trade_mode_raw = int(getattr(info, "trade_mode", 0) or 0)
    exec_mode_raw = int(getattr(info, "trade_exemode", 0) or 0)
    calc_mode_raw = int(getattr(info, "trade_calc_mode", 0) or 0)
    filling_raw = int(getattr(info, "filling_mode", 0) or 0)
    visible = bool(getattr(info, "visible", True))
    selected = bool(getattr(info, "select", False))

    payload: dict[str, Any] = {
        "code": str(getattr(info, "name", "") or "").upper(),
        "description": str(getattr(info, "description", "") or ""),
        "digits": int(getattr(info, "digits", 0) or 0),
        "point": str(getattr(info, "point", 0) or 0),
        "contract_size": str(getattr(info, "trade_contract_size", 0) or 0),
        "volume_min": str(getattr(info, "volume_min", 0) or 0),
        "volume_max": str(getattr(info, "volume_max", 0) or 0),
        "volume_step": str(getattr(info, "volume_step", 0) or 0),
        "volume_limit": str(getattr(info, "volume_limit", 0) or 0),
        "stops_level": int(getattr(info, "trade_stops_level", 0) or 0),
        "freeze_level": int(getattr(info, "trade_freeze_level", 0) or 0),
        "filling_mode": filling_raw,
        "filling_fok": bool(filling_raw & 1),
        "filling_ioc": bool(filling_raw & 2),
        "filling_return": bool(filling_raw & 4),
        "order_mode": int(getattr(info, "order_mode", 0) or 0),
        "trade_mode": _TRADE_MODE.get(trade_mode_raw, f"unknown:{trade_mode_raw}"),
        "trade_mode_raw": trade_mode_raw,
        "execution_mode": _EXEC_MODE.get(exec_mode_raw, f"unknown:{exec_mode_raw}"),
        "execution_mode_raw": exec_mode_raw,
        "margin_calc_mode": _MARGIN_CALC.get(calc_mode_raw, f"unknown:{calc_mode_raw}"),
        "margin_calc_mode_raw": calc_mode_raw,
        "trade_allowed": trade_mode_raw
        not in {
            0,  # disabled
        },
        "visible": visible,
        "selected": selected,
        "currency_base": str(getattr(info, "currency_base", "") or ""),
        "currency_profit": str(getattr(info, "currency_profit", "") or ""),
        "currency_margin": str(getattr(info, "currency_margin", "") or ""),
        "swap_mode": int(getattr(info, "swap_mode", 0) or 0),
        "session_deals": int(getattr(info, "session_deals", 0) or 0),
        "session_buy_orders": int(getattr(info, "session_buy_orders", 0) or 0),
        "session_sell_orders": int(getattr(info, "session_sell_orders", 0) or 0),
        "time": int(getattr(info, "time", 0) or 0),
    }
    if tick is not None:
        payload["bid"] = str(getattr(tick, "bid", 0) or 0)
        payload["ask"] = str(getattr(tick, "ask", 0) or 0)
        payload["tick_time"] = int(getattr(tick, "time", 0) or 0)
        # Market session heuristic: no bid/ask ⇒ treat as closed for trading UX
        bid = float(getattr(tick, "bid", 0) or 0)
        ask = float(getattr(tick, "ask", 0) or 0)
        payload["market_open"] = bid > 0 and ask > 0
    else:
        payload["market_open"] = trade_mode_raw != 0
    return payload


def normalize_volume(volume: float, *, volume_min: float, volume_max: float, volume_step: float) -> float:
    """Round lot size down to broker volume_step and clamp to min/max."""
    if volume_step <= 0:
        volume_step = 0.01
    if volume_min <= 0:
        volume_min = volume_step
    if volume_max <= 0:
        volume_max = max(volume_min, volume)
    # Avoid float drift: work in step units
    steps = int(round(volume / volume_step))
    # Prefer floor for safety (never oversize)
    floored = int(volume / volume_step + 1e-12) * volume_step
    # If already aligned within epsilon, keep floored
    aligned = floored
    if abs(volume - steps * volume_step) < volume_step * 1e-6:
        aligned = steps * volume_step
    aligned = max(volume_min, min(volume_max, aligned))
    # Re-align after clamp
    aligned = int(aligned / volume_step + 1e-12) * volume_step
    if aligned < volume_min:
        aligned = volume_min
    # Digits from step
    step_s = f"{volume_step:.10f}".rstrip("0")
    decimals = len(step_s.split(".")[1]) if "." in step_s else 0
    return round(aligned, decimals)
