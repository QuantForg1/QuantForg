"""Independent multi-signal evaluation — no safety bypass."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.application.services.institutional_ite_runtime import InstitutionalIteRuntime
from app.application.services.institutional_multi_asset_scanner import (
    independent_evaluation_symbols,
)
from app.application.services.research_execution_bridge import (
    merge_research_into_execution_handoff,
    signal_card_lifecycle,
)
from app.application.services.telegram_events import (
    TRADE_OPENED,
    TRADE_REJECTED,
    classify_cycle_notices,
    format_trade_opened,
    format_trade_rejected,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    classify_candidate_outcome,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_independent_queue_includes_buy_sell_without_sniper_take() -> None:
    rows = [
        {
            "symbol": "EURJPY",
            "direction": "BUY",
            "opportunity_eligible": False,
            "reject": False,
            "opportunity_score": 82,
        },
        {
            "symbol": "USDCHF",
            "direction": "SELL",
            "opportunity_eligible": False,
            "reject": False,
            "opportunity_score": 88,
        },
        {
            "symbol": "DEAD",
            "direction": "BUY",
            "reject_reason": "SYMBOL_TIMEOUT",
        },
        {"symbol": "WAIT1", "direction": "WAIT"},
    ]
    queued = independent_evaluation_symbols(rows, existing=["GBPUSD"], cap=36)
    assert queued[0] == "GBPUSD"
    assert "EURJPY" in queued
    assert "USDCHF" in queued
    assert "DEAD" not in queued
    assert "WAIT1" not in queued


def test_hard_routing_failure_does_not_fill_queue() -> None:
    rows = [
        {
            "symbol": "AEXEUR",
            "direction": "SELL",
            "reject_reason": "symbol_select failed",
        },
        {"symbol": "EURUSD", "direction": "BUY"},
    ]
    queued = independent_evaluation_symbols(rows, cap=8)
    assert queued == ["EURUSD"]


def test_open_symbol_skipped_but_others_remain() -> None:
    rows = [
        {"symbol": "XAUUSD", "direction": "SELL"},
        {"symbol": "NZDUSD", "direction": "SELL"},
    ]
    queued = independent_evaluation_symbols(
        rows,
        open_symbols={"XAUUSD_I"},
        cap=8,
    )
    assert "XAUUSD" not in queued
    assert queued == ["NZDUSD"]


def test_research_merge_never_drops_scanner_eligible() -> None:
    eligible = [f"SYM{i:02d}" for i in range(20)]
    focus = [f"RES{i:02d}" for i in range(20)]
    universe = eligible + focus
    merged = merge_research_into_execution_handoff(
        eligible,
        universe=universe,
        research_focus=focus,
        limit=12,
    )
    for sym in eligible:
        assert sym in merged
    assert len(merged) >= len(eligible)
    room = merge_research_into_execution_handoff(
        ["GBPUSD", "USDJPY"],
        universe=["EURUSD", "GBPUSD", "USDJPY"],
        research_focus=["EURUSD", "GBPUSD"],
        limit=12,
    )
    assert room[0] == "EURUSD"
    assert "GBPUSD" in room
    assert "USDJPY" in room


def test_handoff_continues_after_one_symbol_consumed() -> None:
    rt = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
    )
    rt._eligible_handoff_queue = ["EURJPY", "USDCHF", "GBPUSD"]
    rt._eligible_consumed = {"EURJPY"}
    rt._entries_this_scan = 1
    assert rt._take_next_handoff_symbol() == "USDCHF"
    assert rt._take_next_handoff_symbol() == "GBPUSD"
    assert rt._take_next_handoff_symbol() is None


def test_cycle_timeout_rotates_instead_of_halting_scan() -> None:
    cls = classify_candidate_outcome(
        abort_reason="CYCLE_TIMEOUT",
        cycle_outcome="error",
        decision_action="NO_TRADE",
    )
    assert cls["skip_idle_sleep"] is True
    assert cls["release_entry_budget"] is True
    assert cls["candidate_action"] in {"ROTATE_FOCUS", "WAIT_SAME_FOCUS"}


def test_card_lifecycle_never_executed_without_ticket() -> None:
    filled = signal_card_lifecycle(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "FILLED"},
        },
        execution_status="EXECUTION_BLOCKED",
    )
    assert filled["card_status"] != "EXECUTED"
    opened = signal_card_lifecycle(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"ticket": 445566, "execution_lifecycle": "FILLED"},
        },
        execution_status="ORDER_SUBMITTED",
    )
    assert opened["card_status"] == "EXECUTED"
    assert opened["lifecycle"] == "EXECUTED"


def test_risk_and_waiting_card_status() -> None:
    risk = signal_card_lifecycle(
        {"symbol": "EURJPY", "direction": "BUY", "pipeline": {"risk": "BLOCK"}},
        execution_status="RISK_BLOCKED",
    )
    assert risk["card_status"] == "RISK_BLOCKED"
    waiting = signal_card_lifecycle(
        {
            "symbol": "USDCHF",
            "direction": "BUY",
            "reject_reason": "WAIT_NO_SNIPER_TRIGGER",
        },
        execution_status="LIVE_ELIGIBLE",
    )
    assert waiting["card_status"] == "WAITING"
    assert "WAIT" in waiting["reason"] or waiting["reason"]


def test_telegram_rejected_is_not_an_execution() -> None:
    text = format_trade_rejected(
        symbol="EURJPY",
        action="BUY",
        reason="MAX_POSITIONS_REACHED",
    )
    assert "QUANTFORG SIGNAL REJECTED" in text
    assert "MAX_POSITIONS_REACHED" in text
    assert "No MT5 ticket" in text
    assert "EXECUTED" not in text


def test_telegram_opened_requires_ticket_in_classifier() -> None:
    cycle = SimpleNamespace(
        ok=True,
        cycle_outcome="filled",
        abort_reason=None,
        decision_action="BUY",
        forwarded_to_oms=True,
        mt5_ticket=None,
        oms_message=None,
        decision_reasons=(),
        safety_failed_reasons=(),
        detail="no ticket",
        broker_retcode=None,
    )
    decision = SimpleNamespace(
        symbol="EURUSD",
        direction="BUY",
        action="BUY",
        confidence=80,
        estimated_rr=None,
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
        approved_lots=0.01,
    )
    notices = classify_cycle_notices(cycle=cycle, decision=decision, pipeline=None)
    events = [n["event"] for n in notices]
    assert TRADE_OPENED not in events
    opened = format_trade_opened(
        symbol="EURUSD",
        side="BUY",
        volume=0.01,
        entry=1.17,
        stop_loss=1.16,
        take_profit=1.18,
        ticket=998877,
    )
    assert "MT5 Ticket: 998877" in opened
    assert "EXECUTED" in opened


def test_generated_signal_abort_emits_rejection_not_fill() -> None:
    cycle = SimpleNamespace(
        ok=True,
        cycle_outcome="aborted",
        abort_reason="MIN_LOT_EXCEEDS_RISK_BUDGET",
        decision_action="NO_TRADE",
        forwarded_to_oms=False,
        mt5_ticket=None,
        oms_message=None,
        decision_reasons=("MIN_LOT_EXCEEDS_RISK_BUDGET",),
        safety_failed_reasons=(),
        detail="min lot",
        broker_retcode=None,
    )
    pipeline = SimpleNamespace(
        _last_ai_score={
            "symbol": "EURJPY",
            "direction": "BUY",
            "signal_action": "BUY",
            "opportunity_eligible": True,
            "opportunity_score": 82,
        }
    )
    notices = classify_cycle_notices(cycle=cycle, decision=None, pipeline=pipeline)
    events = [n["event"] for n in notices]
    assert TRADE_OPENED not in events
    assert TRADE_REJECTED in events or "RISK_BLOCKED" in events
    assert all("EXECUTED" not in n["text"] or "NO ORDER" in n["text"] for n in notices)
