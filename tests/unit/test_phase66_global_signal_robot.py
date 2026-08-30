"""Final robot / global signal intelligence — research analysis worker.

Does not authorize live trading. Does not call OMS.
Preserves gold-only clamp for live ITE path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.application.services import signal_center_service
from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
)
from app.application.services.market_universe_service import (
    reset_market_universe_cache_for_tests,
)
from app.application.services.research_analysis_worker import (
    get_research_analysis_health,
    reset_research_analysis_health_for_tests,
    run_research_analysis_once,
)
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.scheduler import (
    _WEEKEND_CLASS_ROTATION,
    research_scan_order,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_research_analysis_health_for_tests()
    reset_market_universe_cache_for_tests()
    _store_last_scan({})
    yield
    reset_research_analysis_health_for_tests()
    reset_market_universe_cache_for_tests()
    _store_last_scan({})


@pytest.mark.unit
def test_research_promotion_stays_false() -> None:
    assert ALLOW_LIVE_PROMOTION is False


@pytest.mark.unit
def test_weekend_rotation_prefers_crypto() -> None:
    assert _WEEKEND_CLASS_ROTATION[0] == "CRYPTO"
    assert "STOCKS" in _WEEKEND_CLASS_ROTATION
    assert "COMMODITIES" in _WEEKEND_CLASS_ROTATION


@pytest.mark.unit
def test_research_scan_skips_market_closed() -> None:
    instruments = [
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "MARKET_CLOSED"},
        },
        {
            "canonical_symbol": "BTCUSD",
            "broker_symbol": "BTCUSD",
            "asset_class": "CRYPTO",
            "data_quality": {"state": "LIVE"},
            "timeframe_quality": {"sufficient": True},
        },
    ]
    ordered = research_scan_order(instruments, max_batch=8)
    queue = ordered.get("queue") or []
    symbols = {str(r.get("canonical_symbol")) for r in queue}
    assert "BTCUSD" in symbols
    assert "EURUSD" not in symbols
    skipped_rows = ordered.get("skipped") or []
    skipped = {str(s.get("symbol")): s.get("reason") for s in skipped_rows}
    assert skipped.get("EURUSD") == "MARKET_CLOSED"


@pytest.mark.unit
def test_stocks_and_commodities_classification() -> None:
    stock = classify_instrument("AAPL", broker_row={"path": "Stocks\\US"})
    assert stock.asset_class == "STOCKS"
    commodity = classify_instrument("WHEAT", broker_row={"path": "Commodities\\Softs"})
    assert commodity.asset_class in {"COMMODITIES", "OTHER", "ENERGY"}


@pytest.mark.unit
def test_research_worker_never_calls_oms() -> None:
    snap = {
        "catalogue_source": "LIVE_BROKER",
        "observability": {"symbol_count": 12, "symbols_scored": 4},
        "research_signals": {"n": 2},
    }
    with (
        patch(
            "app.application.services.market_universe_service.MarketUniverseService.snapshot",
            return_value=snap,
        ),
        patch(
            "app.application.services.research_analysis_worker._resolve_adapter",
            return_value=None,
        ),
    ):
        health = run_research_analysis_once(mt5_adapter=None)
    assert health["authorizes_trade"] is False
    assert health["would_submit_order"] is False
    assert health["forwarded_to_oms"] is False
    assert health["second_scanner"] is False
    assert health["status"] in {"RUNNING", "DEGRADED"}


@pytest.mark.unit
def test_signal_center_includes_research_analysis_health() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-30T12:00:00Z",
            "universe": ["EURUSD", "BTCUSD", "XAUUSD"],
            "ranked": [
                {
                    "symbol": "EURUSD",
                    "direction": "BUY",
                    "opportunity_score": 72,
                    "directional_edge": 8,
                    "trade_quality": 72,
                    "ai_confidence": 80,
                    "reject": False,
                    "asset_class": "FOREX",
                    "research_rank_score": 12,
                },
                {
                    "symbol": "BTCUSD",
                    "direction": "SELL",
                    "opportunity_score": 71,
                    "directional_edge": 6,
                    "trade_quality": 71,
                    "ai_confidence": 78,
                    "reject": False,
                    "asset_class": "CRYPTO",
                    "research_rank_score": 10,
                },
            ],
        }
    )
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert "research_analysis" in payload
    assert payload["research_analysis"]["authorizes_trade"] is False
    assert payload["research_analysis"]["forwarded_to_oms"] is False
    assert payload["broker_required_for_research"] is False
    assert payload["research_can_execute"] is False
    symbols = {str(i.get("symbol")) for i in payload["items"]}
    assert "EURUSD" in symbols
    assert "BTCUSD" in symbols
    assert len(symbols) >= 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_research_mode_bypasses_gold_gate() -> None:
    from app.application.services.ite_cycle_market_context import (
        build_ite_cycle_market_context,
    )

    adapter = MagicMock()
    adapter.copy_rates_from_pos = MagicMock(return_value=[])
    with (
        patch(
            "app.domain.trading.gold_only.gold_only_enabled",
            return_value=True,
        ),
        patch(
            "app.application.services.ite_cycle_market_context._ensure_gateway_session",
            return_value=None,
        ),
        patch(
            "app.domain.institutional_trading.ai_scalping.universe_discovery.fetch_broker_symbol_rows",
            return_value=({"symbol": "EURUSD"},),
        ),
        patch(
            "app.domain.institutional_trading.ai_scalping.universe_discovery.catalogue_ordered_candidates",
            return_value=("EURUSD",),
        ),
    ):
        live = await build_ite_cycle_market_context(
            mt5_adapter=adapter,
            symbol="EURUSD",
            research_mode=False,
            reuse_cycle=False,
        )
        assert live.ok is False
        assert "DISABLED_AUTONOMOUS" in str(live.reason or "")

        research = await build_ite_cycle_market_context(
            mt5_adapter=adapter,
            symbol="EURUSD",
            research_mode=True,
            reuse_cycle=False,
        )
        diag = research.diagnostics or {}
        assert diag.get("research_gold_gate_bypassed") is True
        assert "DISABLED_AUTONOMOUS_SYMBOL" not in str(research.reason or "")


@pytest.mark.unit
def test_worker_health_reset() -> None:
    reset_research_analysis_health_for_tests()
    h = get_research_analysis_health()
    assert h["status"] == "STOPPED"
    assert h["cycles"] == 0
    assert h["authorizes_trade"] is False
