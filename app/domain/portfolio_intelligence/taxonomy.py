"""Deterministic symbol taxonomy — no invented market facts."""

from __future__ import annotations

# Known FX quote currencies (second leg of 6-char pairs)
_QUOTE_CCY = {
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CHF",
    "AUD",
    "NZD",
    "CAD",
    "CNH",
    "SGD",
    "HKD",
}

_METALS = frozenset({"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"})
_CRYPTO = frozenset({"BTCUSD", "ETHUSD", "XBTUSD", "BTCUSDT", "ETHUSDT"})
_INDICES = frozenset({"US30", "US500", "NAS100", "GER40", "UK100", "JP225"})


def classify_sector(symbol: str) -> str:
    code = symbol.strip().upper()
    if code in _METALS or code.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "metals"
    if code in _CRYPTO or "BTC" in code or "ETH" in code:
        return "crypto"
    if code in _INDICES:
        return "indices"
    if len(code) >= 6 and code[:3].isalpha() and code[3:6].isalpha():
        return "fx"
    return "other"


def classify_currency(symbol: str) -> str:
    """Primary exposure currency for allocation display (quote or metal/crypto)."""
    code = symbol.strip().upper()
    if code in _METALS or code.startswith("XAU"):
        return "XAU"
    if code.startswith("XAG"):
        return "XAG"
    if "BTC" in code:
        return "BTC"
    if "ETH" in code:
        return "ETH"
    if len(code) >= 6:
        base, quote = code[:3], code[3:6]
        if quote in _QUOTE_CCY:
            return quote
        if base in _QUOTE_CCY:
            return base
    return "UNK"
