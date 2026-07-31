"""Canonical portfolio correlation / sector / currency book for PRE v2.

Single source of truth for gold CFDs, FX majors, indices, and crypto groups.
Does not weaken quality filters — exposure caps only.
"""

from __future__ import annotations

from typing import Final

# Normalized symbol aliases → canonical book symbols
_SYMBOL_ALIASES: Final[dict[str, str]] = {
    "XAUUSD": "XAUUSD",
    "XAUUSDM": "XAUUSD",
    "GOLD": "XAUUSD",
    "XAU": "XAUUSD",
    "XAGUSD": "XAGUSD",
    "XAGUSDM": "XAGUSD",
    "SILVER": "XAGUSD",
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "AUDUSD": "AUDUSD",
    "NZDUSD": "NZDUSD",
    "USDJPY": "USDJPY",
    "EURJPY": "EURJPY",
    "GBPJPY": "GBPJPY",
    "NAS100": "NAS100",
    "USTEC": "NAS100",
    "US30": "US30",
    "DJ30": "US30",
    "US500": "US500",
    "SPX500": "US500",
    "BTCUSD": "BTCUSD",
    "ETHUSD": "ETHUSD",
}

# Correlation groups — members share one correlated exposure budget
PORTFOLIO_CORRELATION_GROUPS: Final[dict[str, frozenset[str]]] = {
    "metals_gold": frozenset({"XAUUSD", "XAGUSD"}),
    "usd_majors": frozenset({"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}),
    "usd_jpy": frozenset({"USDJPY", "EURJPY", "GBPJPY"}),
    "indices_us": frozenset({"NAS100", "US30", "US500"}),
    "crypto": frozenset({"BTCUSD", "ETHUSD"}),
}

_SECTOR_OF: Final[dict[str, str]] = {
    "XAUUSD": "metals",
    "XAGUSD": "metals",
    "EURUSD": "fx",
    "GBPUSD": "fx",
    "AUDUSD": "fx",
    "NZDUSD": "fx",
    "USDJPY": "fx",
    "EURJPY": "fx",
    "GBPJPY": "fx",
    "NAS100": "indices",
    "US30": "indices",
    "US500": "indices",
    "BTCUSD": "crypto",
    "ETHUSD": "crypto",
}

# Quote / risk currency for exposure bucketing (USD book)
_CURRENCY_OF: Final[dict[str, str]] = {
    "XAUUSD": "USD",
    "XAGUSD": "USD",
    "EURUSD": "USD",
    "GBPUSD": "USD",
    "AUDUSD": "USD",
    "NZDUSD": "USD",
    "USDJPY": "JPY",
    "EURJPY": "JPY",
    "GBPJPY": "JPY",
    "NAS100": "USD",
    "US30": "USD",
    "US500": "USD",
    "BTCUSD": "USD",
    "ETHUSD": "USD",
}


def normalize_book_symbol(symbol: str) -> str:
    """Strip broker suffixes and map aliases to canonical book symbols."""
    raw = "".join(ch for ch in (symbol or "").upper() if ch.isalnum())
    if not raw:
        return ""
    if raw in _SYMBOL_ALIASES:
        return _SYMBOL_ALIASES[raw]
    # Strip trailing m / pro / micro style suffixes after known stems
    for alias, canon in _SYMBOL_ALIASES.items():
        if raw.startswith(alias):
            return canon
    return raw


def correlation_group_name(symbol: str) -> str | None:
    """Return correlation group key for a symbol, or None if ungrouped."""
    canon = normalize_book_symbol(symbol)
    for name, members in PORTFOLIO_CORRELATION_GROUPS.items():
        if canon in members:
            return name
    return None


def correlation_group_members(symbol: str) -> frozenset[str] | None:
    name = correlation_group_name(symbol)
    if name is None:
        return None
    return PORTFOLIO_CORRELATION_GROUPS[name]


def sector_for(symbol: str) -> str:
    canon = normalize_book_symbol(symbol)
    return _SECTOR_OF.get(canon, "other")


def currency_for(symbol: str) -> str:
    canon = normalize_book_symbol(symbol)
    return _CURRENCY_OF.get(canon, "USD")


def same_correlation_group(a: str, b: str) -> bool:
    ga = correlation_group_name(a)
    if ga is None:
        return False
    return ga == correlation_group_name(b)
