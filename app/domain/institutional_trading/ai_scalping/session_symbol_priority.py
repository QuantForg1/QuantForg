"""Session-aware symbol scan priority — reorder only, never weaken gates."""

from __future__ import annotations

from app.domain.market_context.enums import MarketSession

# Higher weight → scanned / preferred earlier within the same quality rank.
_SESSION_WEIGHTS: dict[str, dict[str, int]] = {
    MarketSession.LONDON.value: {
        "EURUSD": 100,
        "GBPUSD": 98,
        "EURGBP": 92,
        "EURJPY": 90,
        "GBPJPY": 88,
        "XAUUSD": 95,
        "XAGUSD": 70,
        "USDCHF": 75,
        "EURCHF": 72,
    },
    MarketSession.NEW_YORK.value: {
        "EURUSD": 95,
        "GBPUSD": 90,
        "USDJPY": 88,
        "USDCAD": 86,
        "XAUUSD": 98,
        "XAGUSD": 75,
        "BTCUSD": 80,
        "ETHUSD": 78,
        "NDXUSD": 85,
        "DJIUSD": 82,
        "SPXUSD": 80,
        "XTIUSD": 70,
    },
    MarketSession.LONDON_NY_OVERLAP.value: {
        "EURUSD": 100,
        "GBPUSD": 98,
        "XAUUSD": 100,
        "USDJPY": 90,
        "USDCAD": 88,
        "EURJPY": 86,
        "GBPJPY": 84,
        "BTCUSD": 75,
        "NDXUSD": 80,
    },
    MarketSession.TOKYO.value: {
        "USDJPY": 100,
        "AUDUSD": 95,
        "NZDUSD": 90,
        "AUDJPY": 88,
        "NZDJPY": 85,
        "XAUUSD": 80,
        "BTCUSD": 78,
        "ETHUSD": 75,
    },
    MarketSession.SYDNEY.value: {
        "AUDUSD": 100,
        "NZDUSD": 95,
        "AUDNZD": 85,
        "AUDJPY": 80,
        "XAUUSD": 75,
        "BTCUSD": 70,
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
