"""Final production repair — gateway adopt + signal honesty contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.application.services import signal_center_service
from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
)
from app.application.services.market_universe_service import (
    ensure_gateway_session_for_research,
    reset_market_universe_cache_for_tests,
)
from app.application.services.research_analysis_worker import (
    reset_research_analysis_health_for_tests,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_market_universe_cache_for_tests()
    reset_research_analysis_health_for_tests()
    _store_last_scan({})
    yield
    reset_market_universe_cache_for_tests()
    reset_research_analysis_health_for_tests()
    _store_last_scan({})


@pytest.mark.unit
def test_ensure_gateway_session_adopts_when_disconnected() -> None:
    client = MagicMock()
    client.is_connected = False
    client.adopt_existing_session = MagicMock(return_value=True)
    adapter = MagicMock()
    adapter.client = client
    diag = ensure_gateway_session_for_research(adapter)
    assert diag["adopted"] is True
    assert diag["authorizes_trade"] is False
    client.adopt_existing_session.assert_called_once()


@pytest.mark.unit
def test_ensure_gateway_session_reports_not_connected() -> None:
    client = MagicMock()
    client.is_connected = False
    client.adopt_existing_session = MagicMock(return_value=False)
    adapter = MagicMock()
    adapter.client = client
    diag = ensure_gateway_session_for_research(adapter)
    assert diag["adopted"] is False
    assert "not connected" in str(diag.get("error") or "").lower()


@pytest.mark.unit
def test_signals_drop_ghosts_when_catalogue_unavailable() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-30T12:00:00Z",
            "universe": ["XAUUSD_I"],
            "ranked": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "NONE",
                    "opportunity_score": 0,
                    "reject": True,
                }
            ],
        }
    )
    with patch(
        "app.application.services.signal_center_service._research_universe_feed",
        return_value={
            "catalogue_source": "UNAVAILABLE",
            "as_of": "2026-08-30T12:00:00Z",
            "observability": {
                "catalogue_source": "UNAVAILABLE",
                "last_error": "MT5 gateway session not connected",
            },
            "opportunity_board": {"live_ranked": [], "rows": []},
            "research_signals": {"n": 0, "signals": []},
        },
    ):
        payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["research_can_execute"] is False
    assert payload["allow_live_promotion"] is False
    assert payload["scanner_status"] in {"UNAVAILABLE", "NO_ACTIVE_SIGNALS"}
    actionable = [
        i
        for i in payload["items"]
        if str(i.get("direction") or "").upper() in {"BUY", "SELL"}
    ]
    assert actionable == []
    # Ghost NONE/0 rows must not inflate active feed while catalogue is down.
    assert all(
        str(i.get("direction") or "").upper() not in {"NONE", "UNKNOWN"}
        or not isinstance(i.get("opportunity_score"), (int, float))
        or float(i.get("opportunity_score") or 0) <= 0
        for i in payload["items"]
    )
    assert len(payload["items"]) == 0


@pytest.mark.unit
def test_signals_keep_wait_when_catalogue_source_empty() -> None:
    """Empty catalogue_source must not wipe live-scan WAIT rows."""
    _store_last_scan(
        {
            "as_of": "2026-08-26T18:00:00Z",
            "universe": ["XAUUSD_i"],
            "noc_rows": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "signal_action": "WAIT",
                    "quality": 62,
                    "confidence": 48,
                    "reject": True,
                    "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
                    "decision": "WAIT",
                }
            ],
            "rows": [
                {
                    "symbol": "XAUUSD_I",
                    "direction": "BUY",
                    "signal_action": "WAIT",
                    "trade_quality": 62,
                    "ai_confidence": 48,
                    "reject": True,
                    "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
                    "opportunity_score": 64,
                }
            ],
        }
    )
    with patch(
        "app.application.services.signal_center_service._research_universe_feed",
        return_value={
            "catalogue_source": "",
            "as_of": "2026-08-26T18:00:00Z",
            "observability": {},
            "opportunity_board": {"live_ranked": [], "rows": []},
            "research_signals": {"n": 0, "signals": []},
        },
    ):
        payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["dashboard"]["wait"] == 1
    assert payload["items"][0]["direction"] == "WAIT"
