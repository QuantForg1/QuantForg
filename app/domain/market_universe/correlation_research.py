"""Research-only correlation / concentration intelligence.

Surfaces CORRELATED_EXPOSURE. Does not bypass Risk and does not veto
live gold execution.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.classification import classify_or_unknown
from app.domain.market_universe.constants import INSUFFICIENT_SAMPLE, UNKNOWN
from app.domain.market_universe.identity import canonical_desk

_USD_QUOTE = ("USD",)
_USD_BASE = ("USD",)


def _currencies(desk: str) -> tuple[str, str]:
    if len(desk) >= 6 and desk[:6].isalpha():
        return desk[:3], desk[3:6]
    if desk.endswith("USD") and len(desk) > 3:
        return desk[:-3], "USD"
    if desk.startswith("USD") and len(desk) > 3:
        return "USD", desk[3:]
    return UNKNOWN, UNKNOWN


def analyze_correlation_exposure(
    symbols: list[str] | tuple[str, ...] | None,
    *,
    asset_classes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Flag concentrated / correlated research candidates.

    Never authorizes or blocks OMS. Risk remains authoritative.
    """
    rows: list[dict[str, Any]] = []
    usd = 0
    btc = 0
    metals = 0
    indices = 0
    energy = 0
    forex = 0
    crypto = 0
    by_desk: dict[str, int] = {}
    classes = asset_classes or {}
    for raw in symbols or ():
        desk = canonical_desk(raw)
        if not desk:
            continue
        by_desk[desk] = by_desk.get(desk, 0) + 1
        cls = str(classes.get(desk) or classify_or_unknown(desk)).upper()
        base, quote = _currencies(desk)
        usd_leg = base == "USD" or quote == "USD" or "USD" in desk
        if usd_leg:
            usd += 1
        if cls == "FOREX":
            forex += 1
        elif cls == "CRYPTO":
            crypto += 1
        elif cls == "METALS":
            metals += 1
        elif cls == "INDICES":
            indices += 1
        elif cls == "ENERGY":
            energy += 1
        if desk.startswith("BTC") or "BTC" in desk:
            btc += 1
        rows.append(
            {
                "symbol": raw,
                "canonical_symbol": desk,
                "asset_class": cls,
                "usd_leg": usd_leg,
                "base": base,
                "quote": quote,
            }
        )

    flags: list[str] = []
    n = len(rows)
    if n >= 2 and usd >= 2:
        flags.append("CORRELATED_EXPOSURE")
        flags.append("USD_CONCENTRATION")
    if btc >= 2 or (crypto >= 2):
        flags.append("CORRELATED_EXPOSURE")
        flags.append("BTC_CRYPTO_CONCENTRATION")
    if metals >= 2:
        flags.append("CORRELATED_EXPOSURE")
        flags.append("GOLD_METALS_CONCENTRATION")
    if indices >= 2:
        flags.append("CORRELATED_EXPOSURE")
        flags.append("INDEX_CONCENTRATION")
    if energy >= 2:
        flags.append("CORRELATED_EXPOSURE")
        flags.append("ENERGY_CONCENTRATION")
    if forex >= 3:
        flags.append("CORRELATED_EXPOSURE")
        flags.append("FOREX_CLUSTER")

    unique_flags = list(dict.fromkeys(flags))
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "bypasses_risk": False,
        "feeds_risk_research": True,
        "n": n,
        "usd_concentration": usd,
        "btc_crypto_concentration": max(btc, crypto),
        "metals_concentration": metals,
        "index_concentration": indices,
        "energy_concentration": energy,
        "forex_concentration": forex,
        "duplicate_desks": {k: v for k, v in by_desk.items() if v > 1},
        "flags": unique_flags,
        "status": "CORRELATED_EXPOSURE"
        if unique_flags
        else "INDEPENDENT_OR_INSUFFICIENT_SAMPLE",
        "instruments": rows,
        "clusters": {
            "USD": usd,
            "FOREX": forex,
            "CRYPTO": crypto,
            "METALS": metals,
            "INDICES": indices,
            "ENERGY": energy,
            "BTC": btc,
        },
        "correlation_matrix": "INSUFFICIENT_SAMPLE"
        if n < 2
        else {
            "price_correlation": INSUFFICIENT_SAMPLE
            if n < 20
            else UNKNOWN,
            "price_correlation_method": "not_computed_without_matched_history",
            "usd_cluster_n": usd,
            "crypto_cluster_n": crypto,
            "metals_cluster_n": metals,
            "indices_cluster_n": indices,
            "energy_cluster_n": energy,
            "forex_cluster_n": forex,
        },
        "same_direction_concentration": UNKNOWN,
        "inverse_exposure": UNKNOWN,
        "open_positions": UNKNOWN,
        "projected_portfolio_risk": UNKNOWN,
        "margin_concentration": UNKNOWN,
        "max_concurrent_positions": UNKNOWN,
        "total_open_risk": UNKNOWN,
        "note": (
            "Correlated opportunities are not independent trades. "
            "Risk remains authoritative."
        ),
    }


def analyze_portfolio_exposure(
    symbols: list[str] | tuple[str, ...] | None,
    *,
    directions: list[str] | tuple[str, ...] | None = None,
    open_positions: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    asset_classes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Research-only book overlay. Never bypasses live Risk."""
    base = analyze_correlation_exposure(symbols, asset_classes=asset_classes)
    dirs = [str(d or "").upper() for d in (directions or ())]
    buy_n = sum(1 for d in dirs if d == "BUY")
    sell_n = sum(1 for d in dirs if d == "SELL")
    same_dir = "UNKNOWN"
    if dirs:
        if buy_n >= 3:
            same_dir = "BUY_CONCENTRATION"
        elif sell_n >= 3:
            same_dir = "SELL_CONCENTRATION"
        else:
            same_dir = "MIXED_OR_SPARSE"
    inverse = "PRESENT" if buy_n and sell_n else "NONE_OR_UNKNOWN"
    positions = [p for p in (open_positions or ()) if isinstance(p, dict)]
    open_n = len(positions) if open_positions is not None else UNKNOWN
    flags = list(base.get("flags") or [])
    if same_dir in {"BUY_CONCENTRATION", "SELL_CONCENTRATION"}:
        flags.append("DIRECTIONAL_CONCENTRATION")
    if isinstance(open_n, int) and open_n >= 2:
        flags.append("OPEN_BOOK_OBSERVED")
    base.update(
        {
            "same_direction_concentration": same_dir,
            "inverse_exposure": inverse,
            "open_positions": open_n,
            "open_symbols": [
                str(p.get("symbol") or p.get("code") or "")
                for p in positions
                if p.get("symbol") or p.get("code")
            ],
            "projected_portfolio_risk": UNKNOWN,
            "margin_concentration": UNKNOWN,
            "max_concurrent_positions": UNKNOWN,
            "total_open_risk": UNKNOWN,
            "flags": list(dict.fromkeys(flags)),
            "bypasses_risk": False,
            "authorizes_trade": False,
            "live_risk_unchanged": True,
        }
    )
    return base
