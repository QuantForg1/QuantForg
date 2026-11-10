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
