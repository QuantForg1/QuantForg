"""Isolated MT5 -> Twelve Data failover unit test (no production disruption)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.dto.mt5 import MT5CandleDTO, MT5TickDTO
from app.application.services.public_market_feed import PublicMarketFeedService
from app.domain.exceptions.base import ServiceUnavailableError
from app.domain.market_data.timeframe import Timeframe


class _FakeSettings:
    twelvedata_api_key = "test-key-not-real"


@pytest.mark.asyncio
async def test_failover_to_twelve_when_mt5_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    market_data = MagicMock()
    market_data.adapter = object()
    market_data.historical_candles.side_effect = ServiceUnavailableError(
        "gateway offline",
        code="MARKET_FEED_UNAVAILABLE",
    )

    candle = MT5CandleDTO(
        symbol="XAUUSD",
        timeframe="H1",
        open_time=datetime(2026, 11, 10, 17, 0, tzinfo=UTC),
        open="4000",
        high="4010",
        low="3990",
        close="4005",
        tick_volume=1,
        spread_points=0,
    )

    svc = PublicMarketFeedService(market_data=market_data)

    async def _deny_mt5(*_a, **_k):
        raise ServiceUnavailableError("offline", code="GATEWAY_UNAVAILABLE")

    monkeypatch.setattr(
        "app.application.services.public_market_feed.require_platform_market_feed",
        _deny_mt5,
    )
    monkeypatch.setattr(
        "app.application.services.public_market_feed.get_settings",
        lambda: _FakeSettings(),
    )

    def _fake_twelve(**_kwargs):
        return SimpleNamespace(
            symbol="XAUUSD",
            timeframe="H1",
            status="delayed",
            source="twelvedata",
            as_of="2026-11-10T17:00:00+00:00",
            market_open=None,
            candles=[candle],
            last_price="4005",
            note="Reference OHLCV",
        )

    # PublicCandleBundle is a dataclass — return a real bundle via private method stub.
    from app.application.services.public_market_feed import PublicCandleBundle

    monkeypatch.setattr(
        svc,
        "_try_twelve_candles",
        lambda **kwargs: PublicCandleBundle(
            symbol="XAUUSD",
            timeframe="H1",
            status="delayed",
            source="twelvedata",
            as_of="2026-11-10T17:00:00+00:00",
            market_open=None,
            candles=[candle],
            last_price="4005",
            note="Reference OHLCV",
        ),
    )

    bundle = await svc.candles(symbol="XAUUSD", timeframe="H1", count=10)
    assert bundle.source == "twelvedata"
    assert bundle.status == "delayed"
    assert len(bundle.candles) == 1
    assert bundle.candles[0].close == "4005"


@pytest.mark.asyncio
async def test_mt5_preferred_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    market_data = MagicMock()
    market_data.adapter = object()
    market_data.historical_candles.return_value = [
        SimpleNamespace(
            # unused — we stub DTO conversion path by stubbing _try_mt5_candles
        )
    ]
    svc = PublicMarketFeedService(market_data=market_data)

    from app.application.services.public_market_feed import PublicCandleBundle

    mt5_bundle = PublicCandleBundle(
        symbol="XAUUSD",
        timeframe="H1",
        status="live",
        source="mt5_gateway",
        as_of="2026-11-10T18:00:00+00:00",
        market_open=True,
        candles=[],
        last_price="4025",
        note="Platform MT5 gateway feed.",
    )

    async def _mt5(**_k):
        return mt5_bundle

    monkeypatch.setattr(svc, "_try_mt5_candles", _mt5)
    called = {"twelve": False}

    def _twelve(**_k):
        called["twelve"] = True
        return None

    monkeypatch.setattr(svc, "_try_twelve_candles", _twelve)

    bundle = await svc.candles(symbol="XAUUSD", timeframe="H1", count=10)
    assert bundle.source == "mt5_gateway"
    assert bundle.status == "live"
    assert called["twelve"] is False
