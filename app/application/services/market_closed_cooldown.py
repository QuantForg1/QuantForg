"""Broker market-closed cooldown — skip symbols after MT5 retcode 10018.

Quotes can exist while the session is closed (weekends). order_check may still
pass. After a definitive Market closed reject, cool the symbol so Auto Trading
does not spam order_send every cycle.
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

# MT5 TRADE_RETCODE_MARKET_CLOSED
MARKET_CLOSED_RETCODE = 10018

# Default cool-down: 30 minutes (session reopen is slow; avoids weekend hammering)
_DEFAULT_COOLDOWN_SECONDS = 30 * 60

_LOCK = Lock()
_UNTIL: dict[str, float] = {}


def mark_market_closed(
    symbol: str,
    *,
    retcode: int | None = None,
    comment: str | None = None,
    cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
) -> None:
    code = (symbol or "").strip().upper()
    if not code:
        return
    until = time.monotonic() + max(60.0, float(cooldown_seconds))
    with _LOCK:
        _UNTIL[code] = max(_UNTIL.get(code, 0.0), until)
    logger.warning(
        "symbol_market_closed_cooldown",
        symbol=code,
        retcode=retcode,
        comment=comment or "",
        cooldown_seconds=int(cooldown_seconds),
    )


def is_market_closed_cooled(symbol: str) -> bool:
    code = (symbol or "").strip().upper()
    if not code:
        return False
    now = time.monotonic()
    with _LOCK:
        until = _UNTIL.get(code, 0.0)
        if until <= now:
            _UNTIL.pop(code, None)
            return False
        return True


def clear_market_closed(symbol: str | None = None) -> None:
    with _LOCK:
        if symbol is None:
            _UNTIL.clear()
            return
        _UNTIL.pop((symbol or "").strip().upper(), None)


def note_oms_reject(
    *,
    symbol: str,
    retcode: int | None,
    message: str | None = None,
) -> bool:
    """If reject is market-closed, start cooldown. Returns True when cooled."""
    msg = (message or "").lower()
    code = int(retcode or 0)
    if (
        code == MARKET_CLOSED_RETCODE
        or "market closed" in msg
        or "market is closed" in msg
    ):
        mark_market_closed(
            symbol, retcode=code or MARKET_CLOSED_RETCODE, comment=message
        )
        return True
    return False


def filter_cooled_candidates(candidates: list[str]) -> tuple[list[str], list[str]]:
    """Split candidates into (tradable_now, skipped_market_closed)."""
    kept: list[str] = []
    skipped: list[str] = []
    for sym in candidates:
        if is_market_closed_cooled(sym):
            skipped.append(sym)
        else:
            kept.append(sym)
    return kept, skipped


def cooled_symbols_snapshot() -> dict[str, Any]:
    now = time.monotonic()
    with _LOCK:
        return {
            sym: max(0, int(until - now))
            for sym, until in list(_UNTIL.items())
            if until > now
        }
