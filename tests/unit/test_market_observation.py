"""Market observation stays read-only and does not invent a regime."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.application.dto.auth import AuthUserDTO
from app.application.services.market_observation import observation_from_tick_bundle
from app.domain.market_observation import ObservationInput, build_market_observation

pytestmark = [pytest.mark.unit]

_NOW = datetime(2026, 11, 19, 14, 0, tzinfo=UTC)
_ROOT = Path(__file__).resolve().parents[2]


def _obs(**kwargs: object) -> dict:
    base = {
        "symbol": "XAUUSD",
        "read_at": _NOW,
        "quote_time": _NOW - timedelta(seconds=5),
        "bid": "2400.00",
        "ask": "2400.20",
        "source": "public_tick",
        "quote_status": "live",
    }
    base.update(kwargs)
    return build_market_observation(ObservationInput(**base))  # type: ignore[arg-type]


def test_fresh_quote_without_trend_stays_uncertain() -> None:
    report = _obs()
    assert report["regime"]["value"] == "uncertain"
    assert report["trend"]["status"] == "unavailable"
    assert report["momentum"]["status"] == "unavailable"
    assert report["spread"]["value"] == "0.20"
    assert report["spread_condition"]["status"] == "unavailable"
    assert report["liquidity"]["status"] == "unavailable"
    assert report["news"]["status"] == "unavailable"
    assert report["freshness"]["value"] == "fresh"
    assert report["session"]["value"] == "london_ny"
    assert report["strategy_suitability"]["value"] == "observation_only"
    assert report["places_orders"] is False
    assert report["authoritative_for_execution"] is False


def test_stale_quote_is_market_unavailable() -> None:
    report = _obs(quote_time=_NOW - timedelta(seconds=180))
    assert report["freshness"]["value"] == "delayed"
    assert report["regime"]["value"] == "market_unavailable"
    assert report["strategy_suitability"]["value"] == "unavailable"


def test_directional_regimes_use_supplied_trend_and_momentum() -> None:
    strong = _obs(trend="up", momentum="0.8", volatility="normal")
    weak = _obs(trend="down", momentum="-0.2", volatility="normal")
    flat = _obs(trend="flat", momentum="0", volatility="high")
    assert strong["regime"]["value"] == "strong_bullish"
    assert strong["regime"]["status"] == "verified"
    assert weak["regime"]["value"] == "weak_bearish"
    assert flat["regime"]["value"] == "high_volatility"
    assert strong["strategy_suitability"]["value"] == "observation_only"


def test_high_impact_news_does_not_become_an_order() -> None:
    report = _obs(trend="up", momentum="1", news="high_impact")
    assert report["news"]["value"] == "high_impact"
    assert report["strategy_suitability"]["value"] == "observation_only_caution"
    assert report["places_orders"] is False


def test_other_symbols_stay_outside_the_initial_set() -> None:
    report = _obs(symbol="EURUSD", trend="up", momentum="1")
    assert report["regime"]["value"] == "strong_bullish"
    assert report["strategy_suitability"]["value"] == "not_in_initial_observation_set"


def test_missing_quote_does_not_invent_prices() -> None:
    report = _obs(
        bid=None,
        ask=None,
        spread=None,
        quote_time=None,
        quote_status="unavailable",
    )
    assert report["spread"]["value"] is None
    assert report["regime"]["value"] == "market_unavailable"
    assert report["freshness"]["value"] == "unknown"


def test_float_quotes_are_rejected() -> None:
    report = _obs(bid=2400.1, ask=2400.3)  # type: ignore[arg-type]
    assert report["spread"]["value"] is None
    assert report["regime"]["value"] == "market_unavailable"


def test_tick_bundle_uses_only_quote_fields() -> None:
    tick = SimpleNamespace(
        bid="2410.00",
        ask="2410.30",
        spread="0.30",
        timestamp=_NOW - timedelta(seconds=2),
    )
    bundle = SimpleNamespace(symbol="XAUUSD", status="live", source="mt5", tick=tick)
    report = observation_from_tick_bundle(bundle, symbol="XAUUSD", read_at=_NOW)
    assert report["spread"]["value"] == "0.30"
    assert report["regime"]["value"] == "uncertain"
    assert report["places_orders"] is False
    assert report["strategy_suitability"]["value"] == "observation_only"
    assert report["strategy_suitability"]["execution_instruction"] is False


def test_missing_bundle_is_unavailable() -> None:
    report = observation_from_tick_bundle(None, symbol="XAUUSD", read_at=_NOW)
    assert report["regime"]["value"] == "market_unavailable"
    assert report["source"] == "none"


def test_modules_do_not_send_orders() -> None:
    for relative in (
        "app/domain/market_observation/report.py",
        "app/application/services/market_observation.py",
        "app/presentation/routers/market_observation.py",
    ):
        text = (_ROOT / relative).read_text(encoding="utf-8")
        assert "order_send" not in text
        assert "execution_gateway" not in text


def test_flag_defaults_off_and_router_is_registered() -> None:
    from app.main import _OPERATOR_ONLY_ROUTER_MODULES, _ROUTER_SPECS
    from core.config.settings import Settings

    spec = dict(_ROUTER_SPECS)
    assert spec["market_observation"] == "app.presentation.routers.market_observation"
    assert "market_observation" not in _OPERATOR_ONLY_ROUTER_MODULES
    assert Settings.model_fields["market_observation_enabled"].default is False


def _user() -> AuthUserDTO:
    return AuthUserDTO(
        id=uuid4(),
        email="a@example.invalid",
        display_name="A",
        role="trader",
        status="active",
        auth_user_id=None,
    )


@pytest.mark.asyncio
async def test_route_hidden_until_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.presentation.routers import market_observation as router_module

    def _forbidden() -> object:
        raise AssertionError("feed was called while the flag is off")

    monkeypatch.setattr(router_module, "_feed", _forbidden)
    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(market_observation_enabled=False),
    )
    with pytest.raises(HTTPException) as caught:
        await router_module.market_observation("XAUUSD", _user())
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_route_reads_a_quote_and_does_not_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.presentation.routers import market_observation as router_module

    tick = SimpleNamespace(
        bid="2400.00",
        ask="2400.10",
        spread="0.10",
        timestamp=_NOW,
    )

    class _Feed:
        async def tick(self, *, symbol: str) -> object:
            assert symbol == "XAUUSD"
            return SimpleNamespace(
                symbol=symbol, status="live", source="mt5", tick=tick
            )

    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(market_observation_enabled=True),
    )
    monkeypatch.setattr(router_module, "_feed", lambda: _Feed())
    report = await router_module.market_observation("XAUUSD", _user())
    assert report["places_orders"] is False
    assert report["spread"]["value"] == "0.10"
    assert str(_user().id) not in json.dumps(report)
