"""Session-aware symbol scan priority — reorder only, never weaken gates."""

from __future__ import annotations

from app.domain.institutional_trading.ai_scalping.config import (
    MICRO_SAFE_USD_MAJOR_DESKS,
)
from app.domain.market_context.enums import MarketSession

# Soft weights for micro-safe USD majors (desk codes). Reorder only — does not
# change eligibility, risk_pct, hard_max, min-lot, Safety, or OMS.
_MICRO_SAFE_BASE: dict[str, int] = {
    "EURUSD": 100,
    "GBPUSD": 98,
    "AUDUSD": 96,
    "NZDUSD": 95,
    "USDCHF": 94,
    "USDCAD": 93,
}

# Higher weight → scanned / preferred earlier within the same quality rank.
# Gold/JPY remain scannable; soft weights place micro-safe majors ahead of
# crosses that typically fail Safety allowlist on the operator desk.
_SESSION_WEIGHTS: dict[str, dict[str, int]] = {
    MarketSession.LONDON.value: {
        **_MICRO_SAFE_BASE,
        "EURGBP": 80,
        "EURJPY": 78,
        "GBPJPY": 76,
        "XAUUSD": 85,
        "XAGUSD": 70,
        "EURCHF": 72,
        "USDJPY": 74,
    },
    MarketSession.NEW_YORK.value: {
        **_MICRO_SAFE_BASE,
        "EURUSD": 98,
        "GBPUSD": 94,
        "USDCAD": 96,
        "USDCHF": 92,
        "USDJPY": 80,
        "XAUUSD": 85,
        "XAGUSD": 75,
        "BTCUSD": 70,
        "ETHUSD": 68,
        "NDXUSD": 72,
        "DJIUSD": 70,
        "SPXUSD": 68,
        "XTIUSD": 60,
    },
    MarketSession.LONDON_NY_OVERLAP.value: {
        **_MICRO_SAFE_BASE,
        "EURUSD": 100,
        "GBPUSD": 98,
        "USDCAD": 95,
        "XAUUSD": 86,
        "USDJPY": 78,
        "EURJPY": 74,
        "GBPJPY": 72,
        "BTCUSD": 65,
        "NDXUSD": 70,
    },
    MarketSession.TOKYO.value: {
        **_MICRO_SAFE_BASE,
        "AUDUSD": 100,
        "NZDUSD": 98,
        "USDJPY": 82,
        "AUDJPY": 70,
        "NZDJPY": 68,
        "XAUUSD": 78,
        "BTCUSD": 66,
        "ETHUSD": 64,
    },
    MarketSession.SYDNEY.value: {
        **_MICRO_SAFE_BASE,
        "AUDUSD": 100,
        "NZDUSD": 98,
        "AUDNZD": 80,
        "AUDJPY": 70,
        "XAUUSD": 75,
        "BTCUSD": 62,
    },
}


def session_priority_score(symbol: str, session: str | None) -> int:
    """0–100 soft priority for scan ordering (does not change eligibility)."""
    from app.domain.institutional_trading.ai_scalping.asset_class import (
        desk_symbol_code,
    )

    raw = (symbol or "").strip().upper()
    sym = desk_symbol_code(raw) or raw
    sess = (session or "").strip().lower()
    if not sym:
        return 0
    table = _SESSION_WEIGHTS.get(sess) or {}
    if sym in table:
        return int(table[sym])
    if raw in table:
        return int(table[raw])
    # Micro-safe desks keep elevated floor even if session table omitted them.
    if sym in MICRO_SAFE_USD_MAJOR_DESKS:
        return int(_MICRO_SAFE_BASE.get(sym, 90))
    # Class soft defaults
    if sym.startswith(("EUR", "GBP")) and sess in {
        MarketSession.LONDON.value,
        MarketSession.LONDON_NY_OVERLAP.value,
    }:
        return 60
    if "JPY" in sym and sess == MarketSession.TOKYO.value:
        return 55
    if sym.startswith(("BTC", "ETH", "LTC")):
        return 40
    if sym.startswith("XAU"):
        return 50
    return 25


def prioritize_universe_for_session(
    universe: tuple[str, ...] | list[str],
    session: str | None,
    *,
    performance_boost: dict[str, float] | None = None,
) -> tuple[str, ...]:
    """Stable reorder: session weight + optional live performance boost."""
    boost = performance_boost or {}
    scored = []
    for i, sym in enumerate(universe):
        s = str(sym).upper()
        scored.append(
            (
                -(session_priority_score(s, session) + float(boost.get(s, 0.0))),
                i,  # stable
                s,
            )
        )
    scored.sort()
    return tuple(s for _, __, s in scored)
