"""Phase 71 — full eligible universe coverage + score persistence."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import market_universe_service as mus
from app.application.services.research_analysis_worker import _coverage_pct
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.scheduler import (
    MAX_RESEARCH_BATCH,
    research_scan_order,
)
from app.domain.market_universe.classification import classify_instrument

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_fx_exotics_not_crypto() -> None:
    assert classify_instrument("USDTHB").asset_class == "FOREX"
    assert classify_instrument("USDTRY").asset_class == "FOREX"


@pytest.mark.unit
@pytest.mark.trading_core
def test_scheduler_reports_eligible_and_prefers_unscored() -> None:
    instruments = []
    for i in range(20):
        instruments.append(
            {
                "canonical_symbol": f"EUR{i:02d}",
                "broker_symbol": f"EUR{i:02d}",
                "asset_class": "FOREX",
                "data_quality": {"state": "LIVE"},
            }
        )
    for i in range(5):
        instruments.append(
            {
                "canonical_symbol": f"CLOSED{i}",
                "broker_symbol": f"CLOSED{i}",
                "asset_class": "FOREX",
                "data_quality": {"state": "MARKET_CLOSED"},
            }
        )
    last_opp = {f"EUR{i:02d}": 70 for i in range(10)}
    schedule = research_scan_order(
        instruments,
        last_opportunity=last_opp,
        max_batch=8,
    )
    assert schedule["eligible_n"] == 20
    assert schedule["skipped_n"] == 5
    assert schedule["batch_size"] == 8
    queue_desks = [q["canonical_symbol"] for q in schedule["queue"]]
    # Prefer never-analyzed desks first.
    unscored_in_queue = [d for d in queue_desks if d not in last_opp]
    assert len(unscored_in_queue) >= 4
    assert ALLOW_LIVE_PROMOTION is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_merge_scored_seed_prefers_live_then_prior() -> None:
    live = [
        {"symbol": "EURUSD", "opportunity_score": 80},
        {"symbol": "GBPUSD", "opportunity_score": "UNKNOWN"},
    ]
    prior = [
        {"symbol": "GBPUSD", "opportunity_score": 65},
        {"symbol": "USDJPY", "opportunity_score": 72},
        {"symbol": "EURUSD", "opportunity_score": 50},
    ]
    merged = mus._merge_scored_seed(live, prior)
    desks = {mus._desk_key(r): r.get("opportunity_score") for r in merged}
    assert desks["EURUSD"] == 80
    assert desks["GBPUSD"] == 65
    assert desks["USDJPY"] == 72


@pytest.mark.unit
@pytest.mark.trading_core
def test_coverage_uses_eligible_denominator() -> None:
    assert _coverage_pct(40, 40) == 100.0
    assert _coverage_pct(83, 42) == 50.6
    assert _coverage_pct(0, 10) is None


@pytest.mark.unit
@pytest.mark.trading_core
def test_max_research_batch_covers_typical_catalogue() -> None:
    assert MAX_RESEARCH_BATCH >= 83


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_row_safety_and_evidence() -> None:
    from app.application.services import signal_center_service

    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "USDJPY",
            "broker_symbol": "USDJPY",
            "direction": "BUY",
            "opportunity_score": 75,
            "directional_edge": 12,
            "entry": 160.1,
            "stop_loss": 160.0,
            "take_profit": 160.2,
            "price": 160.1,
            "reason": "Bullish structure",
            "evidence": {"WHY_THIS_DIRECTION": "BUY bias", "REGIME": "TREND"},
        }
    )
    assert row["authorizes_trade"] is False
    assert row["pipeline"]["forwarded_to_oms"] is False
    assert row["evidence"]["WHY_THIS_DIRECTION"] == "BUY bias"


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_still_absent_from_trader_rail() -> None:
    nav = (
        ROOT / "frontend" / "src" / "components" / "layout" / "nav-config.ts"
    ).read_text(encoding="utf-8")
    assert "OPERATOR_RAIL_ORDER = TRADER_DESK_ORDER" in nav
