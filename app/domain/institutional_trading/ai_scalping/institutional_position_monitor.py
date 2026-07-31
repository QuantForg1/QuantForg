"""Institutional Position Monitor — live floating PnL / heat / RR / phase."""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any

_LOCK = threading.RLock()
_LAST: dict[str, Any] | None = None


def _iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _f(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _side_of(pos: Any) -> str:
    raw = (
        getattr(getattr(pos, "direction", None), "value", None)
        or getattr(pos, "side", None)
        or ""
    )
    s = str(raw).strip().lower()
    if "buy" in s or s in {"0", "long"}:
        return "long"
    if "sell" in s or s in {"1", "short"}:
        return "short"
    return "unknown"


def build_position_monitor(
    positions: list[Any] | dict[Any, Any] | None,
    *,
    mid_price: float | None = None,
    atr: float | None = None,
    market_session: str | None = None,
) -> dict[str, Any]:
    """Build live monitor rows from real managed positions only."""
    items: list[Any]
    if positions is None:
        items = []
    elif isinstance(positions, dict):
        items = list(positions.values())
    else:
        items = list(positions)

    rows: list[dict[str, Any]] = []
    for pos in items:
        sym = str(getattr(pos, "symbol", "") or "").upper()
        if not sym:
            continue
        side = _side_of(pos)
        entry = _f(
            getattr(pos, "entry_price", None) or getattr(pos, "price_open", None)
        )
        sl = _f(getattr(pos, "current_sl", None) or getattr(pos, "sl", None))
        tp = _f(getattr(pos, "current_tp", None) or getattr(pos, "tp", None))
        vol = _f(getattr(pos, "remaining_volume", None) or getattr(pos, "volume", None))
        risk_dist = _f(getattr(pos, "risk_distance", None))
        state = getattr(getattr(pos, "state", None), "value", None) or getattr(
            pos, "state", None
        )
        mid = mid_price
        floating = None
        remaining_rr = None
        stop_distance = None
        heat = None
        if mid is not None and entry is not None and vol is not None:
            if side == "long":
                floating = (mid - entry) * vol * 100.0  # soft display units
            elif side == "short":
                floating = (entry - mid) * vol * 100.0
        if mid is not None and sl is not None:
            stop_distance = abs(mid - sl)
        if risk_dist and risk_dist > 0 and mid is not None and entry is not None:
            if side == "long":
                remaining_rr = (mid - entry) / risk_dist
            elif side == "short":
                remaining_rr = (entry - mid) / risk_dist
        if atr and atr > 0 and stop_distance is not None:
            heat = round(stop_distance / atr, 3)

        corr = None
        try:
            from app.domain.institutional_trading.ai_scalping.correlation_book import (
                correlation_group_name,
            )

            corr = correlation_group_name(sym)
        except Exception:
            corr = None

        rows.append(
            {
                "ticket": getattr(pos, "ticket", None),
                "symbol": sym,
                "side": side,
                "volume": vol,
                "floating_pnl": round(floating, 4) if floating is not None else None,
                "heat": heat,
                "volatility_atr": atr,
                "session": market_session,
                "correlation_group": corr,
                "remaining_rr": (
                    round(remaining_rr, 3) if remaining_rr is not None else None
                ),
                "stop_distance": (
                    round(stop_distance, 6) if stop_distance is not None else None
                ),
                "management_phase": str(state) if state is not None else None,
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "mid": mid,
            }
        )

    payload = {
        "as_of": _iso(),
        "open_positions": len(rows),
        "rows": rows,
        "fabricated": False,
        "observe_only": True,
        "source": "real_open_positions_only",
    }
    global _LAST
    with _LOCK:
        _LAST = dict(payload)
    return payload


def get_last_position_monitor() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_LAST) if _LAST else None
