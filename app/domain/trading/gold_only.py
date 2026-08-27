"""Trading symbol policy — gold-only autonomous universe.

``GOLD_ONLY_MODE`` is the single source of truth for autonomous execution.
Alpha, multi-symbol, and multi-asset scan flags must not silently expand the
universe when gold-only is enabled.

Logical desk remains ``XAUUSD``. Catalogue/MT5 operations use the broker form
returned by the existing canonical resolver (typically ``XAUUSD_I`` /
``XAUUSD_i``). This module never invents suffixes.
"""

from __future__ import annotations

from typing import Any

GOLD_SYMBOL = "XAUUSD"
CANONICAL_GOLD_BROKER_DISPLAY = "XAUUSD_i"
AUTONOMOUS_DISPLAY_NAME = "XAUUSD (Gold)"
DISABLED_AUTONOMOUS_SYMBOL = "DISABLED_AUTONOMOUS_SYMBOL"
_BARE_GOLD_CODES = frozenset({"XAUUSD", "GOLD", "XAUUSDM"})


class DisabledAutonomousSymbolError(ValueError):
    """Auditable reject — never converts another desk into XAUUSD_i."""

    code = DISABLED_AUTONOMOUS_SYMBOL

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol
        super().__init__(
            f"{DISABLED_AUTONOMOUS_SYMBOL}: QuantForg trades XAUUSD only — "
            f"rejected symbol {symbol!r}"
        )


def gold_only_enabled() -> bool:
    """Authoritative autonomous gold-only switch.

    Reads ``settings.gold_only_mode`` only. Institutional Alpha, multi-symbol,
    and multi-asset scan do not lift this mandate.
    """
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        return bool(getattr(settings, "gold_only_mode", True))
    except Exception:
        return True


def default_trading_symbol() -> str:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        if not gold_only_enabled():
            return str(
                getattr(settings, "default_trading_symbol", GOLD_SYMBOL) or GOLD_SYMBOL
            )
    except Exception:  # noqa: S110  # best-effort optional path
        pass
    return GOLD_SYMBOL


def is_bare_gold_symbol(code: str) -> bool:
    """True for unsuffixed gold aliases that Weltrade rejects (503)."""
    u = (code or "").strip().upper()
    if not u:
        return False
    if u in _BARE_GOLD_CODES:
        return True
    compact = "".join(ch for ch in u if ch.isalnum())
    return compact in {"XAUUSD", "GOLD", "XAUUSDM"}


def canonical_gold_execution_symbol(preferred: str | None = None) -> str:
    """Gold-only executable form. Never unsuffixed XAUUSD."""
    pref = (preferred or "").strip()
    if pref and is_gold_symbol(pref) and not is_bare_gold_symbol(pref):
        return display_autonomous_symbol(pref)
    try:
        for sym in autonomous_execution_symbols():
            if is_gold_symbol(sym) and not is_bare_gold_symbol(sym):
                return display_autonomous_symbol(sym)
    except Exception:  # noqa: S110  # best-effort optional path
        pass
    return CANONICAL_GOLD_BROKER_DISPLAY


def is_gold_symbol(code: str) -> bool:
    u = "".join(ch for ch in (code or "").strip().upper() if ch.isalnum() or ch == ".")
    if not u:
        return False
    if u in {GOLD_SYMBOL, "GOLD", "XAUUSDM"}:
        return True
    return "XAUUSD" in u or ("XAU" in u and "USD" in u)


def display_autonomous_symbol(code: str | None = None) -> str:
    """Operator-facing catalogue spelling (``XAUUSD_i``), never invented for MD."""
    raw = (code or "").strip()
    if not raw:
        return CANONICAL_GOLD_BROKER_DISPLAY if gold_only_enabled() else GOLD_SYMBOL
    u = raw.upper()
    if u.endswith("_I") and len(u) > 2:
        return f"{u[:-2]}_i"
    if is_gold_symbol(u):
        return CANONICAL_GOLD_BROKER_DISPLAY
    return raw


def autonomous_execution_symbols(
    *,
    broker_symbol_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
) -> tuple[str, ...]:
    """Authoritative autonomous execution universe.

    Gold-only: catalogue-resolved gold broker form only. Never unsuffixed
    ``XAUUSD`` — that form 503s on the live Weltrade catalogue.
    """
    if not gold_only_enabled():
        try:
            from app.domain.trading.execution_universe import canonical_execution_desks

            return tuple(sorted(canonical_execution_desks()))
        except Exception:
            return (GOLD_SYMBOL,)
    resolved = ""
    try:
        from app.domain.institutional_trading.ai_scalping.universe_discovery import (
            resolve_canonical_market_data_symbol,
        )

        resolved = resolve_canonical_market_data_symbol(
            GOLD_SYMBOL, broker_symbol_rows=broker_symbol_rows
        )
    except Exception:
        resolved = ""
    if resolved and is_gold_symbol(resolved) and not is_bare_gold_symbol(resolved):
        return (resolved,)
    return (CANONICAL_GOLD_BROKER_DISPLAY,)


def is_autonomous_execution_symbol(code: str | None) -> bool:
    raw = (code or "").strip()
    if not raw:
        return False
    if gold_only_enabled():
        return is_gold_symbol(raw)
    try:
        from app.domain.trading.execution_universe import execution_symbol_allowed

        return execution_symbol_allowed(raw)
    except Exception:
        return True


def filter_autonomous_symbols(codes: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in codes:
        code = str(raw or "").strip().upper()
        if not code or code in seen:
            continue
        if not is_autonomous_execution_symbol(code):
            continue
        seen.add(code)
        out.append(code)
    return tuple(out)


def same_gold_identity(left: str | None, right: str | None) -> bool:
    """True when both codes are the same desk, including XAUUSD vs XAUUSD_i."""
    a = str(left or "").strip().upper()
    b = str(right or "").strip().upper()
    if not a or not b:
        return False
    if a == b:
        return True
    return is_gold_symbol(a) and is_gold_symbol(b)


def symbol_in_scan_universe(
    symbol: str | None,
    universe: tuple[str, ...] | list[str] | set[str] | None,
) -> bool:
    """Membership with gold-identity — XAUUSD_i is not dropped vs XAUUSD."""
    code = str(symbol or "").strip().upper()
    if not code:
        return False
    pool = {
        str(item or "").strip().upper()
        for item in (universe or ())
        if str(item or "").strip()
    }
    if not pool:
        return True
    if code in pool:
        return True
    if is_gold_symbol(code) and any(is_gold_symbol(item) for item in pool):
        return True
    return False


def gold_only_diagnostics(
    *,
    broker_symbol_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Operator/API visibility. Backend remains authoritative."""
    enabled = gold_only_enabled()
    universe = list(autonomous_execution_symbols(broker_symbol_rows=broker_symbol_rows))
    if enabled:
        display = [display_autonomous_symbol(s) for s in universe] or [
            CANONICAL_GOLD_BROKER_DISPLAY
        ]
        canonical = display[0]
    else:
        display = universe
        canonical = universe[0] if universe else GOLD_SYMBOL
    from app.domain.trading.xauusd_specs import MAX_LEVERAGE

    desk_max = str(MAX_LEVERAGE)
    return {
        "gold_only_mode": enabled,
        "execution_universe": display,
        "execution_universe_gateway": universe,
        "logical_symbol": GOLD_SYMBOL,
        "canonical_symbol": canonical,
        "display_name": AUTONOMOUS_DISPLAY_NAME,
        "other_pairs_autonomous": "DISABLED" if enabled else "ENABLED",
        "trading_mode": "GOLD_ONLY" if enabled else "MULTI_SYMBOL",
        "rotate_focus_allowed": not enabled,
        "desk_max_leverage": desk_max,
        "disabled_autonomous_code": DISABLED_AUTONOMOUS_SYMBOL,
    }


def resolve_trading_symbol(code: str | None = None) -> str:
    """Resolve symbol — gold-only mandate when enabled; else pass-through.

    Preserves catalogue broker form (``XAUUSD_I``) when provided. Does not
    strip gold to bare ``XAUUSD``.
    """
    raw = (code or "").strip().upper()
    if gold_only_enabled():
        if not raw:
            return canonical_gold_execution_symbol().upper()
        if is_gold_symbol(raw) and not is_bare_gold_symbol(raw):
            return raw
        if is_gold_symbol(raw):
            return canonical_gold_execution_symbol(raw).upper()
        # Never silently convert EURUSD/etc into XAUUSD_i (read-only pass-through).
        return raw
    return raw or default_trading_symbol() or GOLD_SYMBOL


def filter_gold_symbols(codes: list[str]) -> list[str]:
    return [c for c in codes if is_gold_symbol(c)]


def require_xauusd(symbol: str) -> str:
    """Normalize and reject non-gold symbols when gold-only is active.

    Keeps the incoming gold broker form. Never rewrites ``XAUUSD_I`` to
    bare ``XAUUSD``.
    """
    raw = (symbol or "").strip().upper()
    if gold_only_enabled() and not is_gold_symbol(raw):
        raise DisabledAutonomousSymbolError(symbol)
    if gold_only_enabled():
        if raw and is_gold_symbol(raw) and not is_bare_gold_symbol(raw):
            return raw
        return canonical_gold_execution_symbol(raw).upper()
    return resolve_trading_symbol(symbol)
