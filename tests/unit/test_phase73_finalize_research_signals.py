"""Phase 73 — finalize research signal honesty and STALE contract alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import signal_center_service
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.readiness import research_lifecycle
from app.domain.market_universe.registry import build_registry
from app.domain.market_universe.scheduler import research_scan_order
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_stale_not_research_eligible_and_lifecycle() -> None:
    reg = build_registry(
        [{"symbol": "EURUSD", "name": "EURUSD", "market_open": True}],
        quotes={
            "EURUSD": {
                "bid": 1.1,
                "ask": 1.1001,
                "quote_age_seconds": 900,
                "market_open": True,
            }
        },
    )
    instruments = list(reg.get("instruments") or [])
    assert instruments
    item = instruments[0]
    assert item.get("research_eligible") is False
    state = str((item.get("data_quality") or {}).get("state") or "")
    assert state == "STALE"
    assert research_lifecycle(data_state="STALE", has_score=False) == "STALE"
    assert research_lifecycle(data_state="STALE", has_score=True) == "ANALYZED"
    schedule = research_scan_order(instruments, max_batch=8)
    assert schedule["eligible_n"] == 0
    assert schedule["skipped_n"] >= 1
    assert any(
        str(s.get("reason") or "") == "STALE" for s in (schedule.get("skipped") or [])
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_merge_preserves_board_status_and_qualified() -> None:
    scan = [
        {
            "symbol": "XAUUSD",
            "direction": "BUY",
            "opportunity_score": None,
            "pipeline": {"final_decision": "WAIT", "forwarded_to_oms": False},
        }
    ]
    research_snap = {
        "catalogue_source": "LIVE_BROKER",
        "observability": {"catalogue_source": "LIVE_BROKER", "symbols_scored": 1},
        "opportunity_board": {
            "live_ranked": [
                {
                    "broker_symbol": "XAUUSD",
                    "symbol": "XAUUSD",
                    "direction": "BUY",
                    "opportunity_score": 80,
                    "directional_edge": 9,
                    "research_rank_score": 12.5,
                    "board_status": "QUALIFIED",
                    "qualified_research": True,
                    "price": 2400.5,
                    "entry": 2400.0,
                    "stop_loss": 2390.0,
                    "take_profit": 2420.0,
                    "RR": 2.0,
                    "evidence": {"WHY_THIS_DIRECTION": "Trend continuation"},
                    "authorizes_trade": False,
                }
            ]
        },
    }
    merged, meta = signal_center_service._merge_research_into_signals(
        scan, research_snap=research_snap
    )
    assert meta.get("scanner_status") == "ACTIVE"
    row = next(r for r in merged if str(r.get("symbol") or "").upper() == "XAUUSD")
    assert row.get("board_status") == "QUALIFIED"
    assert row.get("qualified_research") is True
    assert row.get("opportunity_score") == 80
    assert row.get("evidence", {}).get("WHY_THIS_DIRECTION") == "Trend continuation"
    assert row.get("authorizes_trade") is False
    assert (row.get("pipeline") or {}).get("forwarded_to_oms") is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_row_does_not_authorize_trade() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "direction": "SELL",
            "opportunity_score": 70,
            "directional_edge": 6,
            "board_status": "QUALIFIED",
            "qualified_research": True,
            "evidence": {"REGIME": "RANGE"},
        }
    )
    assert row["authorizes_trade"] is False
    assert row["pipeline"]["forwarded_to_oms"] is False
    assert row["pipeline"]["ALLOW_LIVE_PROMOTION"] is False
    assert row["pipeline"]["research_can_execute"] is False
    assert row["board_status"] == "QUALIFIED"
    assert row["qualified_research"] is True
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order({"symbol": "EURUSD"})


@pytest.mark.unit
@pytest.mark.trading_core
def test_xauusd_not_special_classifier() -> None:
    assert classify_instrument("EURUSD").asset_class == "FOREX"
    assert classify_instrument("BTCUSD").asset_class == "CRYPTO"
    assert classify_instrument("USDTHB").asset_class == "FOREX"
    assert classify_instrument("XAUUSD").asset_class == "METALS"


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_absent_from_trader_nav() -> None:
    nav = (
        ROOT / "frontend" / "src" / "components" / "layout" / "nav-config.ts"
    ).read_text(encoding="utf-8")
    assert "OPERATOR_RAIL_ORDER = TRADER_DESK_ORDER" in nav
    trader_block = nav.split("TRADER_DESK_ORDER")[1].split("]")[0]
    assert '"/admin"' not in trader_block
