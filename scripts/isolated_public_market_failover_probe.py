#!/usr/bin/env python3
"""Isolated public-market failover probe (does NOT touch production MT5).

Simulates MT5 unavailable in-process, then exercises the real Twelve Data
fallback using TWELVEDATA_API_KEY from the environment.

Never prints the API key. Never sends LIVE orders.
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

# Allow running from repo root without installing the package editable.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


async def _main() -> int:
    key = (os.environ.get("TWELVEDATA_API_KEY") or "").strip()
    print("twelvedata_configured", bool(key), "key_len", len(key))
    if not key:
        print("BLOCKED: TWELVEDATA_API_KEY missing")
        return 2

    from app.application.services.public_market_feed import PublicMarketFeedService
    from app.domain.exceptions.base import ServiceUnavailableError

    market_data = MagicMock()
    market_data.adapter = object()
    market_data.historical_candles.side_effect = ServiceUnavailableError(
        "isolated probe: gateway offline",
        code="GATEWAY_UNAVAILABLE",
    )
    market_data.latest_tick.side_effect = ServiceUnavailableError(
        "isolated probe: gateway offline",
        code="GATEWAY_UNAVAILABLE",
    )

    async def _deny(*_a, **_k):
        raise ServiceUnavailableError("offline", code="GATEWAY_UNAVAILABLE")

    import app.application.services.public_market_feed as feed_mod

    feed_mod.require_platform_market_feed = _deny  # type: ignore[assignment]
    feed_mod.get_settings = lambda: SimpleNamespace(twelvedata_api_key=key)  # type: ignore[assignment]

    svc = PublicMarketFeedService(market_data=market_data)

    # B: MT5 unavailable -> Twelve Data
    candles = await svc.candles(symbol="XAUUSD", timeframe="H1", count=5)
    print(
        "failover_candles",
        f"source={candles.source}",
        f"status={candles.status}",
        f"n={len(candles.candles)}",
        f"as_of={candles.as_of}",
        f"last={candles.last_price}",
    )
    if candles.source != "twelvedata" or not candles.candles:
        print("FAIL: expected twelvedata candles")
        return 1
    if candles.status != "delayed":
        print("FAIL: twelve candles must be labelled delayed")
        return 1
    times = [c.open_time for c in candles.candles]
    if times != sorted(times):
        print("FAIL: out-of-order candles")
        return 1

    tick = await svc.tick(symbol="XAUUSD")
    print(
        "failover_tick",
        f"source={tick.source}",
        f"status={tick.status}",
        f"as_of={tick.as_of}",
        f"has_tick={tick.tick is not None}",
    )
    if tick.source != "twelvedata" or tick.tick is None:
        print("FAIL: expected twelvedata tick")
        return 1
    if tick.status != "delayed":
        print("FAIL: twelve tick must be labelled delayed")
        return 1

    # C: recovery — preferred MT5 returns when healthy again
    mt5_time = datetime(2026, 11, 10, 19, 0, tzinfo=UTC)

    async def _mt5_ok(**_k):
        from app.application.dto.mt5 import MT5CandleDTO
        from app.application.services.public_market_feed import PublicCandleBundle

        candle = MT5CandleDTO(
            symbol="XAUUSD",
            timeframe="H1",
            open_time=mt5_time,
            open="4020",
            high="4025",
            low="4018",
            close="4022",
            tick_volume=1,
            spread_points=0,
        )
        return PublicCandleBundle(
            symbol="XAUUSD",
            timeframe="H1",
            status="live",
            source="mt5_gateway",
            as_of=mt5_time.isoformat(),
            market_open=True,
            candles=[candle],
            last_price="4022",
            note="Platform MT5 gateway feed.",
        )

    svc._try_mt5_candles = _mt5_ok  # type: ignore[method-assign]
    recovered = await svc.candles(symbol="XAUUSD", timeframe="H1", count=5)
    print(
        "recovery_candles",
        f"source={recovered.source}",
        f"status={recovered.status}",
        f"n={len(recovered.candles)}",
    )
    if recovered.source != "mt5_gateway" or recovered.status != "live":
        print("FAIL: recovery did not return to mt5_gateway")
        return 1

    print("PASS isolated failover+recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
