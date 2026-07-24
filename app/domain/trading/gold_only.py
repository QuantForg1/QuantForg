"""Trading symbol policy — XAUUSD-only by default; multi-symbol when Alpha enabled."""

from __future__ import annotations

GOLD_SYMBOL = "XAUUSD"


def gold_only_enabled() -> bool:
    """True unless multi-symbol / Institutional Alpha is explicitly enabled."""
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        if bool(getattr(settings, "institutional_alpha_enabled", False)):
            return False
        if bool(getattr(settings, "multi_symbol_enabled", False)):
            return False
        return bool(getattr(settings, "gold_only_mode", True))
    except Exception:
        return True


def default_trading_symbol() -> str:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        if not gold_only_enabled():
            return str(getattr(settings, "default_trading_symbol", GOLD_SYMBOL) or GOLD_SYMBOL)
    except Exception:
        pass
    return GOLD_SYMBOL


def is_gold_symbol(code: str) -> bool:
    u = "".join(ch for ch in (code or "").strip().upper() if ch.isalnum() or ch == ".")
    if not u:
        return False
    if u in {GOLD_SYMBOL, "GOLD", "XAUUSDM"}:
        return True
    return "XAUUSD" in u or ("XAU" in u and "USD" in u)


def resolve_trading_symbol(code: str | None = None) -> str:
    """Resolve symbol — gold-only mandate when enabled; else pass-through."""
    if gold_only_enabled():
        return GOLD_SYMBOL
    raw = (code or default_trading_symbol() or GOLD_SYMBOL).strip().upper()
    return raw or GOLD_SYMBOL


def filter_gold_symbols(codes: list[str]) -> list[str]:
    return [c for c in codes if is_gold_symbol(c)]


def require_xauusd(symbol: str) -> str:
    """Normalize and reject non-gold symbols when gold-only is active."""
    if gold_only_enabled() and not is_gold_symbol(symbol):
        msg = f"QuantForg trades XAUUSD only — rejected symbol {symbol!r}"
        raise ValueError(msg)
    if gold_only_enabled():
        return GOLD_SYMBOL
    return resolve_trading_symbol(symbol)
