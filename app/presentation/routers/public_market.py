"""Unauthenticated public market-data endpoints (read-only)."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.public_market_feed import PublicMarketFeedService
from app.presentation.dependencies.mt5 import get_mt5_market_data
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.mt5 import MT5CandleResponse, MT5TickResponse

router = APIRouter(prefix="/public/market", tags=["public-market"])

_TICK_TTL_S = 1.0
_TICK_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _feed_service(
    market_data: Annotated[MT5MarketDataService, Depends(get_mt5_market_data)],
) -> PublicMarketFeedService:
    return PublicMarketFeedService(market_data=market_data)


@router.get("/candles/{symbol}")
async def public_market_candles(
    symbol: str,
    feed: Annotated[PublicMarketFeedService, Depends(_feed_service)],
    timeframe: str = Query(default="H1"),
    count: int = Query(default=400, ge=1, le=5000),
) -> dict[str, Any]:
    """Public OHLCV — no auth, no personal broker session required."""
    bundle = await feed.candles(symbol=symbol, timeframe=timeframe, count=count)
    return {
        "ok": True,
        "symbol": bundle.symbol,
        "timeframe": bundle.timeframe,
        "status": bundle.status,
        "source": bundle.source,
        "as_of": bundle.as_of,
        "market_open": bundle.market_open,
        "last_price": bundle.last_price,
        "note": bundle.note,
        "candles": [
            MT5CandleResponse(**dto_to_dict(c)).model_dump(mode="json")
            for c in bundle.candles
        ],
    }


@router.get("/tick/{symbol}")
async def public_market_tick(
    symbol: str,
    feed: Annotated[PublicMarketFeedService, Depends(_feed_service)],
) -> dict[str, Any]:
    """Public last quote — no auth, no personal broker session required.

    Shared 1 s cache per symbol: charts poll every ~2 s, so the gateway sees
    at most one quote request per second however many viewers are open.
    """
    key = symbol.strip().upper()
    now = time.monotonic()
    hit = _TICK_CACHE.get(key)
    if hit is not None and now - hit[0] < _TICK_TTL_S:
        return dict(hit[1])
    bundle = await feed.tick(symbol=symbol)
    tick_payload = None
    if bundle.tick is not None:
        tick_payload = MT5TickResponse(**dto_to_dict(bundle.tick)).model_dump(
            mode="json"
        )
    payload = {
        "ok": True,
        "symbol": bundle.symbol,
        "status": bundle.status,
        "source": bundle.source,
        "as_of": bundle.as_of,
        "market_open": bundle.market_open,
        "note": bundle.note,
        "tick": tick_payload,
    }
    if tick_payload is not None:
        _TICK_CACHE[key] = (now, payload)
    return payload


@router.get("/status")
async def public_market_status(
    feed: Annotated[PublicMarketFeedService, Depends(_feed_service)],
) -> dict[str, Any]:
    """Lightweight status probe for public market surfaces."""
    readiness = feed.provider_readiness()
    return {
        "ok": True,
        "service": "public-market",
        "as_of": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "auth_required": False,
        "personal_broker_required": False,
        **readiness,
    }


@router.get("/performance")
def public_performance() -> dict[str, Any]:
    """Audited public track record (all closed trades, wins and losses)."""
    import time as _t

    from app.application.services.public_performance import build_public_performance

    hit = _PERF_CACHE.get("v")
    now = _t.monotonic()
    if hit is not None and now - hit[0] < 300:
        return dict(hit[1])
    payload = build_public_performance()
    if payload.get("available"):
        _PERF_CACHE["v"] = (now, payload)
    return payload


_PERF_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
