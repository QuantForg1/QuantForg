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
    "LTCUSD": ("LTCUSD", "LTCUSDT", "LTCUSD.a"),
    "XAUUSD": ("XAUUSD", "XAUUSD_I", "GOLD", "XAUUSDM"),
    "XAGUSD": ("XAGUSD", "XAGUSD_I", "SILVER"),
}

# Weltrade and similar CFDs expose index names as NDXUSD/DJIUSD/… not NAS100.
_INDEX_TOKENS: frozenset[str] = frozenset(
    {
        "NAS100",
        "US30",
        "GER40",
        "US500",
        "UK100",
        "SPX500",
        "USTEC",
        "DJ30",
        "DE40",
        "NDXUSD",
        "DJIUSD",
        "SPXUSD",
        "GEREUR",
        "F40EUR",
        "STXEUR",
        "AEXEUR",
        "FTSGBP",
        "HSIHKD",
        "JPXJPY",
        "AXJAUD",
        "IBXEUR",
        "IT4EUR",
    }
)

_INDEX_MARKERS: tuple[str, ...] = (
    "NDX",
    "DJI",
    "SPX",
    "GER",
    "FTS",
    "HSI",
    "JPX",
    "AXJ",
    "STX",
    "AEX",
    "F40",
    "IBX",
    "IT4",
    "NAS",
    "US30",
    "DE40",
    "USTEC",
)


def desk_symbol_code(symbol: str | None) -> str:
    """Canonical desk code — strip common broker suffixes (e.g. EURUSD_I → EURUSD)."""
    code = (symbol or "").strip().upper()
    if not code:
        return ""
    if code.endswith("_I") and len(code) > 3:
        return code[:-2]
    if code.endswith((".A", ".RAW", ".PRO")):
        return code.rsplit(".", 1)[0]
    return code


def asset_class_for_symbol(symbol: str | None) -> AssetClass:
    code = (symbol or "").strip().upper()
    if not code:
        return "other"
    desk = desk_symbol_code(code)
    if "XAU" in code or desk in {"GOLD", "XAUUSDM", "XAUUSD"}:
        return "gold"
    if "XAG" in code or desk in {"SILVER", "XAGUSD"}:
        # Silver uses gold-calibrated absolute spread ceiling via "other"/gold path
        # only when needed; treat as gold-family for ATR bands (metals).
        return "gold"
    if (
        desk in {"BTCUSD", "ETHUSD", "LTCUSD"}
        or code.startswith(("BTC", "ETH", "LTC"))
        or desk.startswith(("BTC", "ETH", "LTC"))
    ):
        return "crypto"
    if (
        desk in _INDEX_TOKENS
        or code in _INDEX_TOKENS
        or any(m in desk for m in _INDEX_MARKERS)
        or any(m in code for m in _INDEX_MARKERS)
    ):
        return "index"
    # Majors / crosses (letters + optional separators / broker suffix)
    if len(desk) >= 6 and desk[:6].isalpha():
        return "fx"
    if desk.endswith("USD") or desk.startswith("USD"):
        return "fx"
    if code.endswith("USD") or code.startswith("USD"):
        return "fx"
    return "other"


def broker_symbol_candidates(symbol: str) -> tuple[str, ...]:
    """Ordered broker names to try for market data / symbol_select.

    Prefers explicit alias tables, then desk code + common broker suffixes
    (e.g. Weltrade ``_I``). Never invents symbols outside these candidates —
    MT5/gateway still must accept the name.
    """
    code = (symbol or "").strip().upper()
    if not code:
        return ()
    desk = desk_symbol_code(code)
    alts = BROKER_SYMBOL_CANDIDATES.get(desk) or BROKER_SYMBOL_CANDIDATES.get(code)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        n = (name or "").strip().upper()
        if not n or n in seen:
            return
        seen.add(n)
        ordered.append(n)

    if alts:
        for a in alts:
            _add(a)
    _add(code)
    _add(desk)
    if desk and not desk.endswith("_I"):
        _add(f"{desk}_I")
    if code.endswith("_I"):
        _add(desk)
    return tuple(ordered)


def classify_atr_band_thresholds(
    symbol: str | None,
    *,
    gold_low: Decimal,
    gold_high: Decimal,
) -> tuple[Decimal, Decimal]:
    """Return (atr_low_pct, atr_high_pct) for band classification."""
    cls = asset_class_for_symbol(symbol)
    if cls == "gold":
        # Gold M15 ATR% typically clusters 0.08–0.30 on thin sessions.
        # Prior low=0.10 forced ATR%≈0.082 into the raised 88/88 low-vol band
        # (quality 84 tradable setups rejected before RiskEngine / order_send).
        return Decimal("0.08"), Decimal("0.35")
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
        code = desk_symbol_code(symbol)
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
