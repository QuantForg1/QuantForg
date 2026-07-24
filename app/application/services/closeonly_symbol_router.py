"""Skip close-only symbols and rotate to the next full-mode opportunity.

Auto Trading must never stall because the top-ranked symbol is close-only.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.alpha_engine.config import (
    DEFAULT_ALPHA_UNIVERSE,
)
from app.domain.trading.gold_only import GOLD_SYMBOL
from core.logging import get_logger

logger = get_logger(__name__)

_CLOSE_ONLY = frozenset({"closeonly", "close_only", "3"})
_DISABLED = frozenset({"disabled", "0"})


def read_trade_mode(mt5_adapter: Any, symbol: str) -> str:
    """Return broker trade_mode string for symbol (full/closeonly/...)."""
    code = (symbol or "").strip().upper()
    if not code or mt5_adapter is None:
        return "unknown"
    try:
        info = mt5_adapter.symbol_info(code)
    except Exception as exc:
        logger.warning(
            "trade_mode_lookup_failed",
            symbol=code,
            error=str(exc),
        )
        return "unknown"
    raw = str(getattr(info, "trade_mode", "") or "").strip().lower()
    if raw in _CLOSE_ONLY or "close" in raw:
        return "closeonly"
    if raw in _DISABLED:
        return "disabled"
    if raw in {"full", "longonly", "shortonly", "long_only", "short_only"}:
        return raw.replace("_", "")
    # Numeric fallback from some adapters
    try:
        n = int(getattr(info, "trade_mode_raw", None) or raw)
        if n == 3:
            return "closeonly"
        if n == 0:
            return "disabled"
        if n == 4:
            return "full"
        if n == 1:
            return "longonly"
        if n == 2:
            return "shortonly"
    except Exception:
        pass
    return raw or "unknown"


def is_entry_allowed(trade_mode: str) -> bool:
    mode = (trade_mode or "").strip().lower()
    if mode in _CLOSE_ONLY or mode in _DISABLED or mode == "unknown":
        return False
    return mode in {"full", "longonly", "shortonly"} or mode not in {
        "closeonly",
        "close_only",
        "disabled",
    }


def build_opportunity_candidates(
    *,
    preferred: str | None,
    plane: Any | None = None,
    alpha_ranking: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Ranked symbol list: preferred first, then alpha ranks, then universe."""
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(sym: str | None) -> None:
        code = (sym or "").strip().upper()
        if not code or code in seen:
            return
        seen.add(code)
        ordered.append(code)

    _add(preferred)
    for row in alpha_ranking or []:
        if isinstance(row, dict):
            _add(str(row.get("symbol") or ""))
        else:
            _add(str(row))

    if plane is not None:
        for sym in getattr(plane, "allowed_symbols", ()) or ():
            _add(str(sym))

    for sym in DEFAULT_ALPHA_UNIVERSE:
        _add(sym)
    _add(GOLD_SYMBOL)
    return ordered


def select_full_mode_symbol(
    mt5_adapter: Any,
    candidates: list[str],
    *,
    direction: str | None = None,
) -> tuple[str | None, list[str]]:
    """Return (selected_full_symbol, skipped_closeonly_symbols).

    longonly/shortonly are allowed only when direction matches.
    """
    skipped: list[str] = []
    side = (direction or "").strip().upper()
    for sym in candidates:
        mode = read_trade_mode(mt5_adapter, sym)
        if mode == "closeonly":
            logger.warning("%s skipped (close-only)", sym)
            skipped.append(sym)
            continue
        if mode == "disabled":
            logger.warning("%s skipped (trade disabled)", sym)
            skipped.append(sym)
            continue
        if mode == "longonly" and side == "SELL":
            logger.warning("%s skipped (long-only, direction=SELL)", sym)
            skipped.append(sym)
            continue
        if mode == "shortonly" and side == "BUY":
            logger.warning("%s skipped (short-only, direction=BUY)", sym)
            skipped.append(sym)
            continue
        if not is_entry_allowed(mode) and mode != "unknown":
            logger.warning("%s skipped (trade_mode=%s)", sym, mode)
            skipped.append(sym)
            continue
        # unknown: try once (gateway may still accept); prefer known full
        if mode == "unknown":
            logger.warning(
                "%s trade_mode unknown — probing as candidate",
                sym,
            )
        logger.warning("Next opportunity: %s", sym)
        return sym, skipped
    return None, skipped


def resolve_executable_symbol(
    mt5_adapter: Any,
    *,
    preferred: str | None,
    plane: Any | None = None,
    alpha_ranking: list[dict[str, Any]] | None = None,
    direction: str | None = None,
) -> tuple[str | None, list[str]]:
    """Pick the highest-ranked symbol that allows new entries."""
    candidates = build_opportunity_candidates(
        preferred=preferred,
        plane=plane,
        alpha_ranking=alpha_ranking,
    )
    return select_full_mode_symbol(
        mt5_adapter,
        candidates,
        direction=direction,
    )
