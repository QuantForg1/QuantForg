"""Phase 72 — continuous global signal intelligence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.readiness import research_lifecycle
from app.domain.market_universe.research_signals import build_research_signals
from app.domain.market_universe.scheduler import research_scan_order
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_fx_exotics_not_substring_crypto() -> None:
    assert classify_instrument("USDTHB").asset_class == "FOREX"
    assert classify_instrument("USDTRY").asset_class == "FOREX"
    assert classify_instrument("BTCUSD").asset_class == "CRYPTO"


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_lifecycle_states() -> None:
    assert (
        research_lifecycle(data_state="MARKET_CLOSED", has_score=False)
        == "MARKET_CLOSED"
    )
    assert (
        research_lifecycle(data_state="NO_DATA", has_score=False)
        == "DATA_UNAVAILABLE"
    )
    assert research_lifecycle(data_state="ERROR", has_score=False) == "FAILED"
    assert (
        research_lifecycle(data_state="UNSUPPORTED", has_score=False) == "UNSUPPORTED"
    )
    assert research_lifecycle(data_state="LIVE", has_score=True) == "ANALYZED"
    assert (
        research_lifecycle(data_state="LIVE", has_score=False, in_queue=True)
        == "QUEUED"
    )
    assert research_lifecycle(data_state="LIVE", has_score=False) == "READY"


@pytest.mark.unit
@pytest.mark.trading_core
def test_scheduler_stale_first_after_unscored() -> None:
    now = datetime.now(UTC)
    instruments = [
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "LIVE"},
        },
        {
            "canonical_symbol": "GBPUSD",
            "broker_symbol": "GBPUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "LIVE"},
        },
        {
            "canonical_symbol": "USDJPY",
            "broker_symbol": "USDJPY",
            "asset_class": "FOREX",
            "data_quality": {"state": "LIVE"},
        },
        {
            "canonical_symbol": "AUDUSD",
            "broker_symbol": "AUDUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "MARKET_CLOSED"},
        },
    ]
    schedule = research_scan_order(
        instruments,
        last_opportunity={"EURUSD": 70, "GBPUSD": 65},
        last_analyzed={
            "EURUSD": (now - timedelta(hours=1)).isoformat(),
            "GBPUSD": (now - timedelta(hours=12)).isoformat(),
        },
        max_batch=3,
    )
    queue = [q["canonical_symbol"] for q in schedule["queue"]]
    assert "AUDUSD" not in queue
    assert schedule["skipped_n"] == 1
    # Unscored USDJPY first among FOREX, then older GBPUSD before fresher EURUSD.
    assert queue[0] == "USDJPY"
    assert queue.index("GBPUSD") < queue.index("EURUSD")


@pytest.mark.unit
@pytest.mark.trading_core
def test_crypto_remains_eligible_when_live() -> None:
    instruments = [
        {
            "canonical_symbol": "BTCUSD",
            "broker_symbol": "BTCUSD",
            "asset_class": "CRYPTO",
            "data_quality": {"state": "LIVE"},
        },
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "MARKET_CLOSED"},
        },
    ]
    schedule = research_scan_order(instruments, max_batch=8)
    desks = {q["canonical_symbol"] for q in schedule["queue"]}
    assert "BTCUSD" in desks
    assert "EURUSD" not in desks
    assert schedule["eligible_n"] == 1
    assert schedule["skipped_n"] == 1


@pytest.mark.unit
@pytest.mark.trading_core
def test_closed_market_reopens_into_queue() -> None:
    closed = [
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "MARKET_CLOSED"},
        }
    ]
    closed_sched = research_scan_order(closed, max_batch=4)
    assert closed_sched["eligible_n"] == 0
    open_ = [
        {
            "canonical_symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "asset_class": "FOREX",
            "data_quality": {"state": "LIVE"},
        }
    ]
    open_sched = research_scan_order(open_, max_batch=4)
    assert open_sched["eligible_n"] == 1
    assert open_sched["queue"][0]["canonical_symbol"] == "EURUSD"


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_signal_preserves_contract_fields() -> None:
    payload = build_research_signals(
        [
            {
                "symbol": "EURUSD",
                "broker_symbol": "EURUSD",
                "asset_class": "FOREX",
                "direction": "BUY",
                "opportunity_score": 78,
                "directional_edge": 11,
                "research_rank_score": 9.2,
                "board_status": "QUALIFIED",
                "price": 1.1,
                "entry": 1.101,
                "stop_loss": 1.09,
                "take_profit": 1.12,
                "RR": 2.1,
                "data_state": "LIVE",
                "features_as_of": "2026-08-30T12:00:00+00:00",
                "evidence": {
                    "REGIME": "TREND",
                    "MOMENTUM": "Up",
                    "VOLATILITY": "Normal",
                    "WHY_THIS_DIRECTION": "Structure bias",
                },
            }
        ]
    )
    assert payload["ALLOW_LIVE_PROMOTION"] is False
    assert payload["forwarded_to_oms"] is False
    sig = payload["signals"][0]
    assert sig["price"] == 1.1
    assert sig["entry"] == 1.101
    assert sig["stop_loss"] == 1.09
    assert sig["take_profit"] == 1.12
    assert sig["RR"] == 2.1
    assert sig["edge"] == 11
    assert sig["research_rank_score"] == 9.2
    assert sig["evidence"]["WHY_THIS_DIRECTION"] == "Structure bias"
    assert sig["authorizes_trade"] is False
    assert sig["not"] == "LIVE_ORDER"


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_never_calls_oms() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order({"symbol": "EURUSD", "side": "buy"})


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_absent_from_trader_nav() -> None:
    nav = (
        ROOT / "frontend" / "src" / "components" / "layout" / "nav-config.ts"
    ).read_text(encoding="utf-8")
    assert "OPERATOR_RAIL_ORDER = TRADER_DESK_ORDER" in nav
    # Admin must not appear in the trader desk order list.
    trader_block = nav.split("TRADER_DESK_ORDER")[1].split("]")[0]
    assert '"/admin"' not in trader_block
    assert "'/admin'" not in trader_block


@pytest.mark.unit
@pytest.mark.trading_core
def test_fair_rotation_scales_beyond_100() -> None:
    instruments = []
    classes = (
        "FOREX",
        "METALS",
        "CRYPTO",
        "INDICES",
        "ENERGY",
        "STOCKS",
        "COMMODITIES",
        "OTHER",
    )
    for cls in classes:
        for i in range(20):
            instruments.append(
                {
                    "canonical_symbol": f"{cls[:3]}{i:02d}",
                    "broker_symbol": f"{cls[:3]}{i:02d}",
                    "asset_class": cls,
                    "data_quality": {"state": "LIVE"},
                }
            )
    schedule = research_scan_order(instruments, max_batch=48)
    assert schedule["eligible_n"] == 160
    assert schedule["batch_size"] == 48
    classes_in_queue = {q["asset_class"] for q in schedule["queue"]}
    # Fair rotation should not collapse to a single class.
    assert len(classes_in_queue) >= 4
