"""Dynamic scalping universe discovery from LIVE broker catalogue.

Discovers tradable symbols, classifies asset class, prefers liquid FX /
metals / crypto / indices / commodities. Never weakens quality gates.
Never invents symbols the broker does not expose.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Any, Literal

from app.domain.institutional_trading.ai_scalping.config import (
    BROKER_UNAVAILABLE_SCALP_SYMBOLS,
    DEFAULT_SCALPING_UNIVERSE,
)
from core.logging import get_logger

logger = get_logger(__name__)

ScalpAssetClass = Literal[
    "forex",
    "metals",
    "crypto",
    "indices",
    "commodities",
    "stocks",
    "other",
]

# MT5 SYMBOL_TRADE_MODE_FULL
_TRADE_MODE_FULL = 4

# Liquid scalping preference — broker must still expose the code.
_MAJOR_FX: frozenset[str] = frozenset(
    {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "USDCHF",
        "USDCAD",
        "AUDUSD",
        "NZDUSD",
    }
)
_CROSS_FX: frozenset[str] = frozenset(
    {
        "EURJPY",
        "GBPJPY",
        "EURGBP",
        "AUDJPY",
        "EURAUD",
        "EURCAD",
        "EURCHF",
        "GBPAUD",
        "GBPCAD",
        "GBPCHF",
        "CADJPY",
        "CHFJPY",
        "AUDCAD",
        "AUDCHF",
        "AUDNZD",
        "NZDJPY",
        "NZDCAD",
        "NZDCHF",
        "CADCHF",
        "EURNZD",
        "GBPNZD",
    }
)
_METALS: frozenset[str] = frozenset({"XAUUSD", "XAGUSD"})
_CRYPTO: frozenset[str] = frozenset({"BTCUSD", "ETHUSD", "LTCUSD"})
_INDICES: frozenset[str] = frozenset(
    {"NDXUSD", "DJIUSD", "SPXUSD", "GEREUR", "F40EUR", "STXEUR", "AEXEUR"}
)
_COMMODITIES: frozenset[str] = frozenset({"XTIUSD", "XBRUSD"})

# Exotic / illiquid / high-spread — never auto-promote even if broker lists them.
_ILLIQUID_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(RUB|TRY|MXN|ZAR|HUF|CNH|DKK|NOK|SEK|SGD|THB|HKD)$"),
    re.compile(r"^(EUR|USD|GBP).{3}(RUB|TRY|MXN|ZAR|HUF)$"),
)

_CATALOGUE_LOCK = threading.RLock()
_CATALOGUE_CACHE: tuple[tuple[dict[str, Any], ...], float] | None = None
_CATALOGUE_TTL_S = 300.0


def _trade_mode_int(item: Any) -> int:
    """Normalize broker trade_mode (int 4 / 'full' / raw dict) → MT5 int."""
    raw = getattr(item, "raw", None)
    if isinstance(raw, dict) and raw.get("trade_mode") not in (None, ""):
        try:
            return int(raw.get("trade_mode"))
        except Exception:
            pass
    mode = getattr(item, "trade_mode", None)
    if mode is None and isinstance(item, dict):
        mode = item.get("trade_mode")
    if isinstance(mode, int):
        return mode
    text = str(mode or "").strip().lower()
    if text in {"4", "full", "trade_mode_full"}:
        return _TRADE_MODE_FULL
    if text in {"3", "closeonly", "close_only", "trade_mode_closeonly"}:
        return 3
    if text.isdigit():
        return int(text)
    return _TRADE_MODE_FULL


@dataclass(frozen=True, slots=True)
class DiscoveredSymbol:
    code: str
    asset_class: ScalpAssetClass
    trade_mode: int
    digits: int
    description: str
    liquid_scalp: bool


def classify_broker_symbol(code: str, description: str = "") -> ScalpAssetClass:
    c = (code or "").strip().upper()
    d = (description or "").lower()
    if not c:
        return "other"
    if c in _METALS or "XAU" in c or "XAG" in c or "gold" in d or "silver" in d:
        return "metals"
    if c in _CRYPTO or (c.startswith(("BTC", "ETH", "LTC")) and c.endswith("USD")):
        return "crypto"
    if "USDT" in c or c.endswith("BTC"):
        return "crypto"
    if c in _INDICES or any(
        x in c for x in ("NDX", "DJI", "SPX", "GER", "FTS", "HSI", "JPX", "AXJ", "STX", "AEX", "F40", "IBX", "IT4")
    ):
        return "indices"
    if c in _COMMODITIES or c.startswith(("XTI", "XBR", "XPD", "XPT")):
        return "commodities"
    if "stock" in d or "share" in d:
        return "stocks"
    if len(c) >= 6 and c[:6].isalpha():
        return "forex"
    if c.endswith("USD") or c.startswith("USD"):
        return "forex"
    return "other"


def _is_illiquid(code: str) -> bool:
    c = code.upper()
    return any(p.search(c) for p in _ILLIQUID_PATTERNS)


def is_liquid_scalping_candidate(
    code: str,
    *,
    trade_mode: int | None = None,
    asset_class: ScalpAssetClass | None = None,
) -> bool:
    """Prefer liquid majors/crosses/metals/crypto/indices/commodities."""
    c = (code or "").strip().upper()
    if not c or c in BROKER_UNAVAILABLE_SCALP_SYMBOLS:
        return False
    if trade_mode is not None and int(trade_mode) != _TRADE_MODE_FULL:
        return False
    if _is_illiquid(c):
        return False
    cls = asset_class or classify_broker_symbol(c)
    if c in _MAJOR_FX or c in _CROSS_FX or c in _METALS or c in _CRYPTO:
        return True
    if c in _INDICES or c in _COMMODITIES:
        return True
    # Unknown broker codes: only auto-include major-like FX pairs (6 letters)
    if cls == "forex" and len(c) == 6 and c.isalpha() and not _is_illiquid(c):
        # Prefer USD/EUR/GBP/JPY/AUD/NZD/CAD/CHF crosses only
        ccy = {"USD", "EUR", "GBP", "JPY", "AUD", "NZD", "CAD", "CHF"}
        return c[:3] in ccy and c[3:] in ccy
    return False


def discover_from_broker_rows(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> tuple[DiscoveredSymbol, ...]:
    out: list[DiscoveredSymbol] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or row.get("name") or "").strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        try:
            mode = _trade_mode_int(row)
        except Exception:
            mode = _TRADE_MODE_FULL
        desc = str(row.get("description") or "")
        cls = classify_broker_symbol(code, desc)
        try:
            digits = int(row.get("digits") or 0)
        except Exception:
            digits = 0
        out.append(
            DiscoveredSymbol(
                code=code,
                asset_class=cls,
                trade_mode=mode,
                digits=digits,
                description=desc,
                liquid_scalp=is_liquid_scalping_candidate(
                    code, trade_mode=mode, asset_class=cls
                ),
            )
        )
    return tuple(out)


def build_dynamic_scalping_universe(
    discovered: tuple[DiscoveredSymbol, ...] | list[DiscoveredSymbol],
    *,
    seed: tuple[str, ...] = DEFAULT_SCALPING_UNIVERSE,
    max_symbols: int = 36,
    demoted: frozenset[str] | set[str] | None = None,
) -> tuple[str, ...]:
    """Seed + liquid broker discoveries; strip dead/demoted; capped.

    Ensures each liquid asset class keeps representation (not FX-only).
    """
    dem = set(demoted or ()) | set(BROKER_UNAVAILABLE_SCALP_SYMBOLS)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(code: str) -> bool:
        c = code.strip().upper()
        if not c or c in seen or c in dem:
            return False
        if len(ordered) >= max_symbols:
            return False
        seen.add(c)
        ordered.append(c)
        return True

    for s in seed:
        _add(s)

    buckets: dict[str, list[str]] = {
        "major": [],
        "metal": [],
        "cross": [],
        "crypto": [],
        "index": [],
        "commodity": [],
        "other": [],
    }
    for d in discovered:
        if not d.liquid_scalp or d.code in dem:
            continue
        if d.code in _MAJOR_FX:
            buckets["major"].append(d.code)
        elif d.code in _METALS:
            buckets["metal"].append(d.code)
        elif d.code in _CROSS_FX:
            buckets["cross"].append(d.code)
        elif d.asset_class == "crypto":
            buckets["crypto"].append(d.code)
        elif d.asset_class == "indices":
            buckets["index"].append(d.code)
        elif d.asset_class == "commodities":
            buckets["commodity"].append(d.code)
        else:
            buckets["other"].append(d.code)

    # Round-robin across classes so indices/commodities are not starved by FX crosses.
    class_order = ("major", "metal", "cross", "crypto", "index", "commodity", "other")
    pointers = {k: 0 for k in class_order}
    for k in class_order:
        buckets[k] = sorted(buckets[k])
    progress = True
    while progress and len(ordered) < max_symbols:
        progress = False
        for key in class_order:
            i = pointers[key]
            if i >= len(buckets[key]):
                continue
            if _add(buckets[key][i]):
                progress = True
            pointers[key] = i + 1
            if len(ordered) >= max_symbols:
                break
    return tuple(ordered[:max_symbols])


def fetch_broker_symbol_rows(mt5_adapter: Any) -> tuple[dict[str, Any], ...]:
    """Read LIVE catalogue via gateway adapter (cached TTL)."""
    global _CATALOGUE_CACHE
    now = time.monotonic()
    with _CATALOGUE_LOCK:
        if _CATALOGUE_CACHE and now - _CATALOGUE_CACHE[1] < _CATALOGUE_TTL_S:
            return _CATALOGUE_CACHE[0]
    rows: list[dict[str, Any]] = []
    try:
        # Prefer rich list_symbols when available
        listing = None
        if hasattr(mt5_adapter, "list_symbols"):
            listing = mt5_adapter.list_symbols()
        elif hasattr(mt5_adapter, "symbols"):
            listing = mt5_adapter.symbols()
        if listing:
            for item in listing:
                if isinstance(item, dict):
                    rows.append(item)
                    continue
                code = str(getattr(item, "code", None) or getattr(item, "name", "") or "")
                if not code:
                    continue
                rows.append(
                    {
                        "code": code,
                        "description": str(getattr(item, "description", "") or ""),
                        "digits": int(getattr(item, "digits", 0) or 0),
                        "trade_mode": _trade_mode_int(item),
                        "volume_min": getattr(item, "volume_min", None),
                        "volume_max": getattr(item, "volume_max", None),
                    }
                )
    except Exception:
        logger.exception("broker_symbol_catalogue_fetch_failed")
        with _CATALOGUE_LOCK:
            if _CATALOGUE_CACHE:
                return _CATALOGUE_CACHE[0]
        return ()
    payload = tuple(rows)
    with _CATALOGUE_LOCK:
        _CATALOGUE_CACHE = (payload, now)
    logger.warning(
        "broker_scalping_universe_catalogue",
        count=len(payload),
        sample=[r.get("code") for r in payload[:12]],
    )
    return payload


def classify_catalogue_summary(
    discovered: tuple[DiscoveredSymbol, ...] | list[DiscoveredSymbol],
) -> dict[str, Any]:
    by_class: dict[str, list[str]] = {}
    liquid: list[str] = []
    removed_close_only: list[str] = []
    for d in discovered:
        by_class.setdefault(d.asset_class, []).append(d.code)
        if d.liquid_scalp:
            liquid.append(d.code)
        if d.trade_mode != _TRADE_MODE_FULL:
            removed_close_only.append(d.code)
    return {
        "broker_symbols_found": len(discovered),
        "by_class": {k: sorted(v) for k, v in sorted(by_class.items())},
        "liquid_candidates": sorted(liquid),
        "removed_close_only_or_restricted": sorted(removed_close_only),
        "removed_permanently_unavailable": sorted(BROKER_UNAVAILABLE_SCALP_SYMBOLS),
    }
