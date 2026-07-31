"""Portfolio Exposure Intelligence — live net/long/short/sector/correlation view.

Aggregates existing positions + correlation_book / PRE concepts. Observe-only
for reporting; enforcement remains in existing PRE / Risk limits.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.ai_scalping.correlation_book import (
    correlation_group_name,
    currency_for,
    sector_for,
)


def _side_of(pos: Any) -> str:
    raw = (
        getattr(getattr(pos, "direction", None), "value", None)
        or getattr(pos, "side", None)
        or getattr(pos, "type", None)
        or ""
    )
    s = str(raw).strip().lower()
    if s in {"buy", "long", "0"}:
        return "long"
    if s in {"sell", "short", "1"}:
        return "short"
    if "buy" in s or "long" in s:
        return "long"
    if "sell" in s or "short" in s:
        return "short"
    return "unknown"


def _vol(pos: Any) -> float:
    for key in ("volume", "lots", "qty"):
        v = getattr(pos, key, None)
        if v is not None:
            try:
                return abs(float(v))
            except Exception:
                pass
    return 0.0


def build_portfolio_exposure(
    positions: list[Any] | dict[Any, Any] | None,
) -> dict[str, Any]:
    """Compute live exposure breakdown from real open positions only."""
    items: list[Any]
    if positions is None:
        items = []
    elif isinstance(positions, dict):
        items = list(positions.values())
    else:
        items = list(positions)

    long_exp = 0.0
    short_exp = 0.0
    by_sector: dict[str, float] = {}
    by_currency: dict[str, float] = {}
    by_corr: dict[str, float] = {}
    by_symbol: dict[str, dict[str, Any]] = {}

    for pos in items:
        sym = str(getattr(pos, "symbol", "") or "").upper()
        if not sym:
            continue
        side = _side_of(pos)
        vol = _vol(pos)
        signed = vol if side == "long" else (-vol if side == "short" else 0.0)
        if side == "long":
            long_exp += vol
        elif side == "short":
            short_exp += vol
        sector = sector_for(sym)
        currency = currency_for(sym)
        corr = correlation_group_name(sym) or "ungrouped"
        by_sector[sector] = by_sector.get(sector, 0.0) + abs(signed)
        by_currency[currency] = by_currency.get(currency, 0.0) + abs(signed)
        by_corr[corr] = by_corr.get(corr, 0.0) + abs(signed)
        by_symbol[sym] = {
            "symbol": sym,
            "side": side,
            "volume": vol,
            "sector": sector,
            "currency": currency,
            "correlation_group": corr,
        }

    net = long_exp - short_exp
    return {
        "net_exposure": round(net, 4),
        "long_exposure": round(long_exp, 4),
        "short_exposure": round(short_exp, 4),
        "sector_exposure": {k: round(v, 4) for k, v in sorted(by_sector.items())},
        "currency_exposure": {k: round(v, 4) for k, v in sorted(by_currency.items())},
        "correlation_risk": {k: round(v, 4) for k, v in sorted(by_corr.items())},
        "symbols": list(by_symbol.values()),
        "open_positions": len(items),
        "enforcement": "existing_PRE_and_risk_limits",
        "fabricated": False,
        "observe_only": True,
    }
