"""Phase 64 — global research signals without second scanner / OMS."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services import signal_center_service
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
)
from app.application.services.market_universe_service import (
    reset_market_universe_cache_for_tests,
)
from app.application.services.research_universe_scanner import (
    evaluate_injected_contexts,
    score_symbols_for_research,
)
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.shadow_wall import scan_package_isolation


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_execution_binding_for_tests()
    _store_last_scan({})
    reset_market_universe_cache_for_tests()
    yield
    reset_execution_binding_for_tests()
    _store_last_scan({})
    reset_market_universe_cache_for_tests()


@pytest.mark.unit
def test_research_promotion_and_isolation_flags() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    iso = scan_package_isolation()
    assert iso.get("would_submit_order") is False or iso.get("isolated") is True


@pytest.mark.unit
def test_signals_without_broker_connection_do_not_require_broker() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-30T12:00:00Z",
            "universe": ["EURUSD", "GBPUSD", "XAUUSD"],
            "ranked": [
                {
                    "symbol": "EURUSD",
                    "direction": "BUY",
                    "opportunity_score": 72,
                    "directional_edge": 8,
                    "trade_quality": 72,
                    "ai_confidence": 80,
                    "reject": False,
                },
                {
                    "symbol": "GBPUSD",
                    "direction": "SELL",
                    "opportunity_score": 71,
                    "directional_edge": 6,
                    "trade_quality": 71,
                    "ai_confidence": 78,
                    "reject": False,
                },
            ],
        }
    )
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["broker_required_for_research"] is False
    assert payload["research_can_execute"] is False
    assert payload["allow_live_promotion"] is False
    assert payload["fabricated"] is False
    symbols = {str(i.get("symbol")) for i in payload["items"]}
    assert "EURUSD" in symbols
    assert "GBPUSD" in symbols


@pytest.mark.unit
def test_empty_scan_is_no_active_not_fabricated_zero_universe() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-30T12:00:00Z",
            "universe": ["EURUSD", "XAUUSD"],
            "ranked": [],
            "rows": [],
        }
    )
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload.get("fabricated") is False
    assert payload["scanner_status"] in {
        "NO_ACTIVE_SIGNALS",
        "ACTIVE",
        "UNAVAILABLE",
        "UNKNOWN",
    }


@pytest.mark.unit
def test_research_row_projection_keeps_entry_honest() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "canonical_symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 80,
            "directional_edge": 10,
            "RR": "UNKNOWN",
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "asset_class": "FOREX",
            "session": "LONDON",
            "research_rank_score": 12.5,
        }
    )
    assert row["direction"] == "BUY"
    assert row["entry"] is None
    assert row["stop_loss"] is None
    assert row["take_profit"] is None
    assert row["signal_type"] is None
    assert row["authorizes_trade"] is False
    assert row["rr"] is None


@pytest.mark.unit
def test_buy_and_sell_research_projection() -> None:
    buy = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 82,
            "directional_edge": 11,
            "entry": 1.1,
            "stop_loss": 1.09,
            "take_profit": 1.12,
            "signal_type": "LIMIT",
            "research_rank_score": 20,
        }
    )
    sell = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "GBPUSD",
            "direction": "SELL",
            "opportunity_score": 75,
            "directional_edge": 9,
            "entry": 1.3,
            "stop_loss": 1.31,
            "take_profit": 1.28,
            "signal_type": "MARKET",
            "research_rank_score": 18,
        }
    )
    assert buy["direction"] == "BUY"
    assert buy["signal_type"] == "LIMIT"
    assert buy["entry"] == 1.1
    assert sell["direction"] == "SELL"
    assert sell["signal_type"] == "MARKET"


@pytest.mark.unit
def test_malformed_symbol_does_not_kill_research_eval() -> None:
    out = evaluate_injected_contexts(
        [
            {"symbol": "EURUSD", "direction": "BUY", "opportunity_score": 70},
            {"not_a_row": True},
            {"symbol": "GBPUSD", "direction": "SELL", "opportunity_score": 71},
        ]
    )
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["n"] >= 2
    symbols = {r["symbol"] for r in out["rows"]}
    assert "EURUSD" in symbols
    assert "GBPUSD" in symbols


@pytest.mark.unit
def test_score_symbols_for_research_without_adapter_is_honest() -> None:
    out = score_symbols_for_research(None, ["EURUSD", "GBPUSD"])
    assert out["n"] == 0
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["second_scanner"] is False


@pytest.mark.unit
def test_research_merge_prefers_multi_symbol_board() -> None:
    base = [
        {
            "symbol": "XAUUSD",
            "direction": "BUY",
            "badge": "BUY",
            "quality": 70,
            "confidence": 70,
        }
    ]
    snap = {
        "catalogue_source": "LIVE_BROKER",
        "as_of": "2026-08-30T12:00:00Z",
        "opportunity_board": {
            "live_ranked": [
                {
                    "symbol": "EURUSD",
                    "broker_symbol": "EURUSD",
                    "direction": "BUY",
                    "opportunity_score": 80,
                    "directional_edge": 12,
                    "research_rank_score": 30,
                    "asset_class": "FOREX",
                },
                {
                    "symbol": "BTCUSD",
                    "broker_symbol": "BTCUSD",
                    "direction": "SELL",
                    "opportunity_score": 78,
                    "directional_edge": 9,
                    "research_rank_score": 25,
                    "asset_class": "CRYPTO",
                },
            ]
        },
        "observability": {
            "catalogue_source": "LIVE_BROKER",
            "symbols_scored": 2,
            "research_signal_count": 2,
        },
    }
    merged, meta = signal_center_service._merge_research_into_signals(
        base, research_snap=snap
    )
    symbols = {str(r.get("symbol")) for r in merged}
    assert "EURUSD" in symbols
    assert "BTCUSD" in symbols
    assert "XAUUSD" in symbols
    assert meta["scanner_status"] == "ACTIVE"
    assert meta["catalogue_source"] == "LIVE_BROKER"


@pytest.mark.unit
def test_account_isolation_and_mismatch_still_fail_closed() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=11112222)
    assert submit_blocked_reason(user_id=user_b, login=11112222) == (
        ACCOUNT_SESSION_MISMATCH
    )


@pytest.mark.unit
def test_no_oms_import_from_research_scanner_source() -> None:
    from pathlib import Path

    text = Path(
        "app/application/services/research_universe_scanner.py"
    ).read_text(encoding="utf-8")
    assert "order_send(" not in text
    assert "forwarded_to_oms" in text
    assert "authorizes_trade" in text
