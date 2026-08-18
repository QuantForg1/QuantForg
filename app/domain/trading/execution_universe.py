"""Canonical approved execution-symbol policy.

Scanner, Safety, OMS, and Gateway execution policy must share this desk
universe. Broker catalogue forms (USDCHF → USDCHF_I) are identity aliases,
not a wider product set.

Does not change leverage, min-lot, Safety, Risk, or OMS choke points.
Does not invent symbols absent from the approved desk list.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.trading.gold_only import GOLD_SYMBOL


def canonical_execution_desks() -> frozenset[str]:
    """Approved live-execution desks (canonical codes, no broker suffix)."""
    from app.domain.trading.gold_only import gold_only_enabled

    if gold_only_enabled():
        return frozenset({GOLD_SYMBOL})
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_SCALPING_UNIVERSE,
        )

        return frozenset(
            str(s).strip().upper() for s in DEFAULT_SCALPING_UNIVERSE if s
        )
    except Exception:
        return frozenset(
            {
                GOLD_SYMBOL,
                "EURUSD",
                "GBPUSD",
                "AUDUSD",
                "NZDUSD",
                "USDCHF",
                "USDCAD",
                "USDJPY",
                "BTCUSD",
                "ETHUSD",
            }
        )


def desk_code_for_execution(symbol: str | None) -> str:
    """Normalize broker catalogue codes to the canonical desk (USDCHF_I → USDCHF)."""
    try:
        from app.domain.institutional_trading.ai_scalping.asset_class import (
            desk_symbol_code,
        )

        return desk_symbol_code(symbol)
    except Exception:
        code = (symbol or "").strip().upper()
        if code.endswith("_I") and len(code) > 3:
            return code[:-2]
        return code


def with_broker_execution_forms(desks: Iterable[str]) -> frozenset[str]:
    """Desk codes plus known catalogue aliases. Never adds unapproved desks."""
    out: set[str] = set()
    alias_map: dict[str, tuple[str, ...]] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.asset_class import (
            BROKER_SYMBOL_CANDIDATES,
        )

        alias_map = BROKER_SYMBOL_CANDIDATES
    except Exception:
        alias_map = {}
    for raw in desks:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        desk = desk_code_for_execution(code) or code
        out.add(code)
        out.add(desk)
        if desk and not desk.endswith("_I"):
            out.add(f"{desk}_I")
        for alias in alias_map.get(desk, ()):
            a = str(alias or "").strip().upper()
            if a:
                out.add(a)
    return frozenset(out)


def canonical_execution_universe() -> frozenset[str]:
    """Canonical desks plus broker forms for policy membership checks."""
    return with_broker_execution_forms(canonical_execution_desks())


def execution_symbol_allowed(
    symbol: str,
    allowed: Iterable[str] | None = None,
) -> bool:
    """True when *symbol* is the same desk as an approved execution name.

    ``USDCHF`` allowlist authorizes ``USDCHF_I``. Unapproved crosses stay blocked.
    """
    symbol_u = (symbol or "").strip().upper()
    if not symbol_u:
        return False
    allowed_set = {
        str(s).strip().upper() for s in (allowed if allowed is not None else ()) if s
    }
    if not allowed_set:
        allowed_set = set(canonical_execution_universe())
    if symbol_u in allowed_set:
        return True
    desk = desk_code_for_execution(symbol_u)
    if desk and desk in allowed_set:
        return True
    if desk and any(desk_code_for_execution(a) == desk for a in allowed_set):
        return True
    return False
