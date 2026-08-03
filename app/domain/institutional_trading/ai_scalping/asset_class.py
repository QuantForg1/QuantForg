"""Asset-class helpers for multi-symbol AI scalping gates.

Gold-calibrated ATR% / spread ceilings must not be applied verbatim to FX,
indices, or crypto — that silently rejects the entire MULTI_SYMBOL universe.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

AssetClass = Literal["gold", "fx", "index", "crypto", "other"]

# Broker / terminal aliases → canonical desk symbols (and reverse candidates).
BROKER_SYMBOL_CANDIDATES: dict[str, tuple[str, ...]] = {
    "NAS100": ("NAS100", "USTEC", "NAS100.cash", "US100", "NDX100"),
    "US30": ("US30", "DJ30", "US30.cash", "DJIA", "WallStreet30"),
    "GER40": ("GER40", "DE40", "GER40.cash", "DAX40", "DEU40"),
    "BTCUSD": ("BTCUSD", "BTCUSDT", "BTCUSD.a"),
    "ETHUSD": ("ETHUSD", "ETHUSDT", "ETHUSD.a"),
}


def asset_class_for_symbol(symbol: str | None) -> AssetClass:
    code = (symbol or "").strip().upper()
    if not code:
        return "other"
    if "XAU" in code or code in {"GOLD", "XAUUSDM"}:
        return "gold"
    if code in {"BTCUSD", "ETHUSD"} or code.startswith(("BTC", "ETH")):
        return "crypto"
    if code in {"NAS100", "US30", "GER40", "US500", "UK100", "SPX500", "USTEC", "DJ30", "DE40"}:
        return "index"
    # Majors / crosses (letters + optional separators)
    if len(code) >= 6 and code[:6].isalpha():
        return "fx"
    if code.endswith("USD") or code.startswith("USD"):
        return "fx"
    return "other"


def broker_symbol_candidates(symbol: str) -> tuple[str, ...]:
    """Ordered broker names to try for market data / symbol_select."""
    code = (symbol or "").strip().upper()
    if not code:
        return ()
    alts = BROKER_SYMBOL_CANDIDATES.get(code)
    if alts:
        return alts
    return (code,)


def classify_atr_band_thresholds(
    symbol: str | None,
    *,
    gold_low: Decimal,
    gold_high: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (atr_low_pct, atr_high_pct) for band classification."""
    cls = asset_class_for_symbol(symbol)
    if cls == "gold":
        # Gold M15 ATR% typically clusters 0.10–0.30 — prior low=0.40
        # forced nearly all live tape into the raised 88/88 low-vol band.
        return Decimal("0.10"), Decimal("0.35")
    if cls == "fx":
        return Decimal("0.04"), Decimal("0.12")
    if cls == "index":
        return Decimal("0.08"), Decimal("0.25")
    if cls == "crypto":
        return Decimal("0.25"), Decimal("1.20")
    return gold_low, gold_high


def resolve_spread_limits(
    symbol: str | None,
    *,
    max_spread_reject: Decimal,
    max_spread_for_full_score: Decimal,
    max_spread_atr_pct: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Return (reject, full_score, atr_pct, atr_cap_floor).

    atr_cap_floor prevents FX ATR*15% collapsing to ~0 and rejecting every tick.
    """
    cls = asset_class_for_symbol(symbol)
    if cls == "gold":
        return (
            max_spread_reject,
            max_spread_for_full_score,
            max_spread_atr_pct,
            Decimal("0"),
        )
    if cls == "crypto":
        return Decimal("80"), Decimal("20"), Decimal("35"), Decimal("5")
    if cls == "index":
        return Decimal("8.0"), Decimal("2.0"), Decimal("25"), Decimal("0.50")
    if cls == "fx":
        code = (symbol or "").strip().upper()
        if "JPY" in code:
            # JPY quotes: pip ≈ 0.01
            return Decimal("0.350"), Decimal("0.020"), Decimal("100"), Decimal("0.015")
        # 5-digit majors: pip ≈ 0.0001 — allow typical 1–3 pip spreads
        return Decimal("0.00100"), Decimal("0.00030"), Decimal("100"), Decimal("0.00040")
    return (
        max_spread_reject,
        max_spread_for_full_score,
        max_spread_atr_pct,
        Decimal("0"),
    )
