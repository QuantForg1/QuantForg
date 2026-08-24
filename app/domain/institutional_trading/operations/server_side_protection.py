"""Report broker-side SL/TP on live positions. Never invent or send modifications."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _num(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def classify_position_protection(position: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Read-only classification. Does not modify the position."""
    if not isinstance(position, Mapping):
        sl = _num(getattr(position, "sl", None) or getattr(position, "stop_loss", None))
        tp = _num(getattr(position, "tp", None) or getattr(position, "take_profit", None))
        ticket = getattr(position, "ticket", None)
        symbol = getattr(position, "symbol", None)
        magic = getattr(position, "magic", None)
    else:
        sl = _num(position.get("sl") or position.get("stop_loss"))
        tp = _num(position.get("tp") or position.get("take_profit"))
        ticket = position.get("ticket")
        symbol = position.get("symbol")
        magic = position.get("magic")
    missing: list[str] = []
    if sl <= 0:
        missing.append("sl")
    if tp <= 0:
        missing.append("tp")
    return {
        "ticket": ticket,
        "symbol": symbol,
        "magic": magic,
        "sl": sl,
        "tp": tp,
        "missing": missing,
        "protected": not missing,
        "action": "REPORT_ONLY",
    }


def report_unprotected_positions(positions: Iterable[Any]) -> list[dict[str, Any]]:
    """Positions lacking valid server-side SL or TP. No silent modify."""
    rows: list[dict[str, Any]] = []
    for pos in positions or []:
        row = classify_position_protection(pos)
        if not row["protected"]:
            rows.append(row)
    return rows
