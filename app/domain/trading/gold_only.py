"""Gold-only trading mode — XAUUSD unless multi-symbol is enabled."""

from __future__ import annotations

from core.config.settings import get_settings

GOLD_SYMBOL = "XAUUSD"


def gold_only_enabled() -> bool:
    return bool(getattr(get_settings(), "gold_only_mode", True)) and not bool(
        getattr(get_settings(), "multi_symbol_enabled", False)
    )


def default_trading_symbol() -> str:
    settings = get_settings()
    raw = str(getattr(settings, "default_trading_symbol", GOLD_SYMBOL) or GOLD_SYMBOL)
    return raw.strip().upper() or GOLD_SYMBOL


def is_gold_symbol(code: str) -> bool:
    u = "".join(ch for ch in (code or "").strip().upper() if ch.isalnum() or ch == ".")
    if not u:
        return False
    if u in {GOLD_SYMBOL, "GOLD", "XAUUSDM"}:
        return True
    return "XAUUSD" in u or ("XAU" in u and "USD" in u)


def resolve_trading_symbol(code: str | None = None) -> str:
    if not gold_only_enabled():
        s = (code or "").strip().upper()
        return s or default_trading_symbol()
    return default_trading_symbol()


def filter_gold_symbols(codes: list[str]) -> list[str]:
    if not gold_only_enabled():
        return codes
    return [c for c in codes if is_gold_symbol(c)]
