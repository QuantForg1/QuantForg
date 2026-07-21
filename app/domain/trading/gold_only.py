"""XAUUSD-only trading mode — QuantForg is a single-instrument gold desk."""

from __future__ import annotations

GOLD_SYMBOL = "XAUUSD"


def gold_only_enabled() -> bool:
    """Platform mandate: always XAUUSD-only (multi-asset mode removed)."""
    return True


def default_trading_symbol() -> str:
    return GOLD_SYMBOL


def is_gold_symbol(code: str) -> bool:
    u = "".join(ch for ch in (code or "").strip().upper() if ch.isalnum() or ch == ".")
    if not u:
        return False
    if u in {GOLD_SYMBOL, "GOLD", "XAUUSDM"}:
        return True
    return "XAUUSD" in u or ("XAU" in u and "USD" in u)


def resolve_trading_symbol(code: str | None = None) -> str:
    """Always resolve to XAUUSD regardless of caller input."""
    _ = code
    return GOLD_SYMBOL


def filter_gold_symbols(codes: list[str]) -> list[str]:
    return [c for c in codes if is_gold_symbol(c)]


def require_xauusd(symbol: str) -> str:
    """Normalize and reject non-gold symbols."""
    if not is_gold_symbol(symbol):
        msg = f"QuantForg trades XAUUSD only — rejected symbol {symbol!r}"
        raise ValueError(msg)
    return GOLD_SYMBOL
