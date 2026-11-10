"""Unauthenticated public market-data endpoints (read-only)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.application.services.mt5_market_data import MT5MarketDataService
from app.application.services.public_market_feed import PublicMarketFeedService
from app.presentation.dependencies.mt5 import get_mt5_market_data
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.mt5 import MT5CandleResponse, MT5TickResponse

router = APIRouter(prefix="/public/market", tags=["public-market"])


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
    """Public last quote — no auth, no personal broker session required."""
    bundle = await feed.tick(symbol=symbol)
    tick_payload = None
    if bundle.tick is not None:
        tick_payload = MT5TickResponse(**dto_to_dict(bundle.tick)).model_dump(
            mode="json"
        )
    return {
        "ok": True,
        "symbol": bundle.symbol,
        "status": bundle.status,
        "source": bundle.source,
        "as_of": bundle.as_of,
        "market_open": bundle.market_open,
        "note": bundle.note,
        "tick": tick_payload,
    }


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
