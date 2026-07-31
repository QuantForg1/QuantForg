"""Map MetaTrader5 AccountInfo.trade_mode → demo|contest|real.

Never invent a mode. Returns unknown only when MT5 provides no mappable value.
"""

from __future__ import annotations

from typing import Any

_MODE_BY_INT = {0: "demo", 1: "contest", 2: "real"}
_INT_BY_MODE = {"demo": 0, "contest": 1, "real": 2}


def map_account_trade_mode(raw: Any) -> tuple[str, int | None]:
    """Return (account_mode, trade_mode_raw_int_or_none)."""
    if raw is None:
        return "unknown", None

    value = getattr(raw, "value", raw)
    if isinstance(value, bool):
        return "unknown", None

    if isinstance(value, int):
        return _MODE_BY_INT.get(value, "unknown"), value if value >= 0 else None

    if isinstance(value, float) and value.is_integer():
        iv = int(value)
        return _MODE_BY_INT.get(iv, "unknown"), iv if iv >= 0 else None

    text = str(value).strip()
    if not text:
        return "unknown", None

    try:
        iv = int(text)
        return _MODE_BY_INT.get(iv, "unknown"), iv if iv >= 0 else None
    except ValueError:
        pass

    lower = text.lower().replace(" ", "_")
    for mode, iv in _INT_BY_MODE.items():
        if lower == mode or lower.endswith(f"_{mode}") or f"mode_{mode}" in lower:
            return mode, iv
        if mode in lower.split("_") or mode == lower:
            return mode, iv

    for mode, iv in _INT_BY_MODE.items():
        if mode in lower:
            return mode, iv

    return "unknown", None
