"""Public market feed — no personal broker; no invented prices."""

from __future__ import annotations

from app.application.services.public_market_feed import provider_symbol_for


def test_provider_symbol_maps_broker_gold_spellings() -> None:
    assert provider_symbol_for("XAUUSD") == "XAU/USD"
    assert provider_symbol_for("XAUUSD_i") == "XAU/USD"
    assert provider_symbol_for("xauusd_i") == "XAU/USD"
    assert provider_symbol_for("GOLD") == "XAU/USD"


def test_public_market_router_is_anonymous() -> None:
    from app.presentation.routers import public_market

    paths = {getattr(r, "path", "") for r in public_market.router.routes}
    assert any("/candles/{symbol}" in p for p in paths)
    assert any("/tick/{symbol}" in p for p in paths)
    # No auth dependency names on the router itself — endpoints omit CurrentUser.
    for route in public_market.router.routes:
        deps = getattr(route, "dependant", None)
        if deps is None:
            continue
        names = [d.call.__name__ for d in deps.dependencies if getattr(d, "call", None)]
        assert "get_current_user" not in names


def test_market_chat_public_list_route_exists() -> None:
    from app.presentation.routers import market_chat

    paths = {getattr(r, "path", "") for r in market_chat.router.routes}
    assert "/public/market/chat" in paths
    assert "/market/chat" in paths


def test_public_candles_shared_cache_exact_fetch_and_single_flight(monkeypatch) -> None:
    """Many chart/desk callers -> one gateway call per series, exact bar count."""
    import asyncio as _asyncio

    from app.application.services import public_market_feed as pmf
    from app.domain.market_data.timeframe import Timeframe as _TF

    calls: list[dict] = []

    class MD:
        adapter = object()

        def historical_candles(self, symbol, tf, **kw):
            calls.append(kw)
            return list(range(kw["count"]))

    async def ok(_adapter):
        return None

    monkeypatch.setattr(pmf, "require_platform_market_feed", ok)
    svc = pmf.PublicMarketFeedService(market_data=MD())

    async def go():
        res = await _asyncio.gather(
            *[
                svc._cached_rates(symbol="XAUUSD", tf=_TF.parse("M15"), count=n)
                for n in (400, 120, 400, 150)
            ]
        )
        assert [len(r) for r in res] == [400, 120, 400, 150]
        big = await svc._cached_rates(symbol="XAUUSD", tf=_TF.parse("M15"), count=3000)
        assert len(big) == 3000
        again = await svc._cached_rates(symbol="XAUUSD", tf=_TF.parse("M15"), count=400)
        assert len(again) == 400

    _asyncio.run(go())
    # one standard-size call (shared) + one large call; start_pos path, no over-fetch
    assert [c["count"] for c in calls] == [500, 3000]
    assert all(c["start_pos"] == 0 for c in calls)
