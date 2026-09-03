"""Research → existing ITE execution bridge. Does not submit orders."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.research_execution_bridge import (
    is_active_signal_card,
    merge_research_into_execution_handoff,
    overlay_cycle_matches_row,
    research_live_focus_symbols,
    signal_card_lifecycle,
    signal_execution_status,
)
from app.application.services.signal_center_service import _overlay_last_ite_cycle
from app.domain.institutional_trading.live_trading_control import (
    public_authorization_state,
    recover_after_restart,
    reset_live_trading_controller_for_tests,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity


def _op() -> OperatorIdentity:
    return OperatorIdentity(user_id=uuid4(), role="owner", display_name="bridge")


@pytest.mark.unit
@pytest.mark.trading_core
def test_overlay_does_not_paint_unrelated_symbol() -> None:
    buy = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "pipeline": {"final_decision": "TAKE"},
    }
    last = {
        "symbol": "XAUUSD_I",
        "forwarded_to_oms": False,
        "abort_reason": "RISK_REJECTED",
        "execution_blocked": {
            "stage": "RISK",
            "reason_code": "RISK_REJECTED",
            "human_reason": "margin",
        },
    }
    assert overlay_cycle_matches_row(buy, last) is False
    over = _overlay_last_ite_cycle(buy, last)
    assert over.get("pipeline", {}).get("execution_lifecycle") != "EXECUTION_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_overlay_still_applies_matching_symbol() -> None:
    row = {
        "symbol": "XAUUSD_I",
        "direction": "BUY",
        "pipeline": {"final_decision": "TAKE"},
    }
    last = {
        "symbol": "XAUUSD_I",
        "forwarded_to_oms": False,
        "abort_reason": "RISK_REJECTED",
        "execution_blocked": {
            "stage": "RISK",
            "reason_code": "RISK_REJECTED",
            "human_reason": "margin",
        },
    }
    over = _overlay_last_ite_cycle(row, last)
    assert over["pipeline"]["execution_lifecycle"] == "EXECUTION_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_disabled_live_trading_keeps_research_only() -> None:
    reset_live_trading_controller_for_tests()
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="DISABLED",
        orders_ok=False,
        research_focus=["EURUSD"],
    )
    assert status == "RESEARCH_ONLY"
    assert research_live_focus_symbols() == []


@pytest.mark.unit
@pytest.mark.trading_core
def test_paused_live_trading_does_not_mark_live_eligible() -> None:
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="PAUSED",
        orders_ok=False,
        research_focus=["EURUSD"],
    )
    assert status == "RESEARCH_ONLY"


@pytest.mark.unit
@pytest.mark.trading_core
def test_enabled_buy_in_focus_is_waiting_until_ite_take() -> None:
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "WAITING_FOR_EXECUTION"


@pytest.mark.unit
@pytest.mark.trading_core
def test_enabled_sniper_take_in_focus_is_live_eligible_not_an_order() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {
                "final_decision": "TAKE",
                "setup_state": "TAKE",
                "execution_lifecycle": "EXECUTION_READY",
                "sniper": "READY",
            },
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "LIVE_ELIGIBLE"


@pytest.mark.unit
@pytest.mark.trading_core
def test_invalid_or_stale_signal_is_not_live_eligible() -> None:
    stale = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY", "freshness": "STALE"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert stale == "EXPIRED"
    wait = signal_execution_status(
        {"symbol": "EURUSD", "direction": "WAIT"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert wait == "RESEARCH_ONLY"


@pytest.mark.unit
@pytest.mark.trading_core
def test_risk_or_oms_block_is_execution_blocked() -> None:
    blocked = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "EXECUTION_BLOCKED", "risk": "BLOCK"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert blocked == "RISK_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_enabled_without_submit_flag_waits_until_take() -> None:
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="ENABLED",
        orders_ok=False,
        research_focus=["EURUSD"],
    )
    assert status == "WAITING_FOR_EXECUTION"


@pytest.mark.unit
@pytest.mark.trading_core
def test_take_without_submit_flag_is_execution_blocked() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {
                "final_decision": "TAKE",
                "execution_lifecycle": "EXECUTION_READY",
                "sniper": "READY",
            },
        },
        live_state="ENABLED",
        orders_ok=False,
        research_focus=["EURUSD"],
    )
    assert status == "EXECUTION_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_order_submitted_requires_ticket() -> None:
    no_ticket = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "ORDER_SENT"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert no_ticket != "ORDER_SUBMITTED"
    with_ticket = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {
                "execution_lifecycle": "ORDER_SENT",
                "ticket": "12345",
                "broker": "SUBMITTED",
            },
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert with_ticket == "ORDER_SUBMITTED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_broker_disconnected_research_focus_empty() -> None:
    ctrl = reset_live_trading_controller_for_tests()
    op = _op()
    ctrl.transition(op, "ARMED", confirmed=True, reason="arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="enable")
    ctrl.safety_pause(reason="mt5_disconnected")
    assert ctrl.snapshot_state() == "PAUSED"
    assert research_live_focus_symbols() == []


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_handoff_prefers_focus_inside_universe() -> None:
    merged = merge_research_into_execution_handoff(
        ["GBPUSD", "USDJPY"],
        universe=["EURUSD", "GBPUSD", "USDJPY"],
        research_focus=["EURUSD", "GBPUSD"],
    )
    assert merged[0] == "EURUSD"
    assert "GBPUSD" in merged
    assert "USDJPY" in merged


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_handoff_does_not_inject_outside_universe() -> None:
    merged = merge_research_into_execution_handoff(
        ["XAUUSD_I"],
        universe=["XAUUSD_I"],
        research_focus=["EURUSD"],
    )
    assert "EURUSD" not in merged
    assert merged == ["XAUUSD_I"]


@pytest.mark.unit
@pytest.mark.trading_core
def test_restart_recovery_still_fail_closed_at_hydrate() -> None:
    assert recover_after_restart("ENABLED") == "PAUSED"
    ctrl = reset_live_trading_controller_for_tests()
    recovered = ctrl.hydrate({"live_trading_state": "ENABLED"})
    assert recovered == "PAUSED"
    assert ctrl.research_can_execute() is False
    assert research_live_focus_symbols() == []


@pytest.mark.unit
@pytest.mark.trading_core
def test_no_fill_claimed_without_broker_ticket() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "FILLED"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "EXECUTION_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_oms_rejection_is_not_an_order() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"oms": "REJECT", "final_decision": "TAKE"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "EXECUTION_BLOCKED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_open_position_is_not_a_new_order() -> None:
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
        open_symbols=["EURUSD_I"],
    )
    assert status == "POSITION_OPEN"


@pytest.mark.unit
@pytest.mark.trading_core
def test_public_authorization_never_inferred_from_broker() -> None:
    assert public_authorization_state("ENABLED") == "LIVE_ENABLED"
    assert public_authorization_state("PAUSED") == "LIVE_PAUSED"
    assert public_authorization_state("DISABLED") == "LIVE_DISABLED"
    assert (
        public_authorization_state("ENABLED", orders_may_submit_flag=False)
        == "EXECUTION_BLOCKED"
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_empty_universe_does_not_inject_research_symbols() -> None:
    merged = merge_research_into_execution_handoff(
        ["XAUUSD_I"],
        universe=[],
        research_focus=["EURUSD"],
    )
    assert merged == ["XAUUSD_I"]


@pytest.mark.unit
@pytest.mark.trading_core
def test_gold_only_research_handoff_does_not_reinject_fx(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    merged = merge_research_into_execution_handoff(
        ["XAUUSD_I"],
        universe=["EURUSD", "GBPUSD", "XAUUSD_I"],
        research_focus=["EURUSD", "NZDUSD", "XAUUSD_I"],
    )
    assert "EURUSD" not in merged
    assert "NZDUSD" not in merged
    assert any(str(s).upper().startswith("XAUUSD") for s in merged)


@pytest.mark.unit
@pytest.mark.trading_core
def test_gold_only_live_eligible_is_gold_not_research_focus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    gold = signal_execution_status(
        {
            "symbol": "XAUUSD",
            "direction": "SELL",
            "pipeline": {
                "final_decision": "TAKE",
                "execution_lifecycle": "EXECUTION_READY",
                "sniper": "READY",
            },
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD", "NZDUSD"],
    )
    fx = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD", "NZDUSD"],
    )
    assert gold == "LIVE_ELIGIBLE"
    assert fx == "RESEARCH_ONLY"


@pytest.mark.unit
@pytest.mark.trading_core
def test_promote_pipeline_levels_does_not_invent_values() -> None:
    from app.application.services.signal_center_service import (
        _promote_pipeline_trade_levels,
    )

    row = _promote_pipeline_trade_levels(
        {
            "symbol": "XAUUSD",
            "direction": "SELL",
            "entry": None,
            "stop_loss": None,
            "take_profit": None,
            "pipeline": {
                "entry": "4429.935",
                "stop": "4438.14",
                "target": "4420.08",
                "opportunity_score": 75,
            },
        }
    )
    assert row["entry"] == 4429.935
    assert row["stop_loss"] == 4438.14
    assert row["take_profit"] == 4420.08
    assert row["opportunity_score"] == 75
    empty = _promote_pipeline_trade_levels({"symbol": "XAUUSD", "pipeline": {}})
    assert empty.get("entry") is None
    assert empty.get("stop_loss") is None


@pytest.mark.unit
@pytest.mark.trading_core
def test_overlay_wait_cycle_does_not_reject_research_buy() -> None:
    row = {
        "symbol": "GBPUSD",
        "direction": "BUY",
        "board_status": "QUALIFIED",
        "pipeline": {"final_decision": "WAIT", "forwarded_to_oms": False},
    }
    last = {
        "symbol": "GBPUSD",
        "forwarded_to_oms": False,
        "decision_action": "NO_TRADE",
        "abort_reason": "WAIT_INSUFFICIENT_RR",
        "cycle_outcome": "waiting_next_cycle",
    }
    over = _overlay_last_ite_cycle(row, last)
    assert over.get("pipeline", {}).get("execution_lifecycle") != "EXECUTION_BLOCKED"
    assert over.get("rejection_reason") in (None, "")
    status = signal_execution_status(
        over,
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["GBPUSD"],
    )
    assert status == "WAITING_FOR_EXECUTION"
    card = signal_card_lifecycle(over, execution_status=status)
    assert card["card_status"] == "WAITING"
    assert is_active_signal_card({**over, "card_status": card["card_status"]}) is True


@pytest.mark.unit
@pytest.mark.trading_core
def test_take_oms_reject_becomes_rejected_and_leaves_active_feed() -> None:
    row = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "pipeline": {
            "final_decision": "TAKE",
            "execution_lifecycle": "EXECUTION_READY",
            "sniper": "READY",
        },
    }
    last = {
        "symbol": "EURUSD",
        "decision_action": "BUY",
        "forwarded_to_oms": False,
        "abort_reason": "OMS_REJECTED",
        "execution_blocked": {
            "stage": "OMS",
            "reason_code": "OMS_REJECTED",
            "human_reason": "duplicate guard",
        },
    }
    over = _overlay_last_ite_cycle(row, last)
    assert over["rejection_reason"] == "OMS_REJECTED"
    assert over["rejection_stage"] == "OMS"
    card = signal_card_lifecycle(over, execution_status="EXECUTION_BLOCKED")
    assert card["card_status"] == "REJECTED"
    assert is_active_signal_card({**over, "card_status": "REJECTED"}) is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_take_mt5_reject_becomes_rejected_with_reason() -> None:
    row = {
        "symbol": "AUDUSD",
        "direction": "SELL",
        "pipeline": {
            "final_decision": "TAKE",
            "execution_lifecycle": "EXECUTING",
            "sniper": "READY",
            "oms": "READY",
        },
    }
    last = {
        "symbol": "AUDUSD",
        "decision_action": "SELL",
        "forwarded_to_oms": True,
        "abort_reason": "MT5_REJECTED",
        "mt5_ticket": None,
        "execution_blocked": {
            "stage": "BROKER",
            "reason_code": "MT5_REJECTED",
            "human_reason": "order_send failed",
        },
    }
    over = _overlay_last_ite_cycle(row, last)
    assert over["rejection_reason"] == "MT5_REJECTED"
    card = signal_card_lifecycle(over, execution_status="EXECUTION_BLOCKED")
    assert card["card_status"] == "REJECTED"
    assert card["lifecycle"] in {
        "BROKER_REJECTED",
        "OMS_REJECTED",
        "EXECUTION_ERROR",
        "FILTERED",
    }


@pytest.mark.unit
@pytest.mark.trading_core
def test_executed_requires_real_mt5_ticket() -> None:
    no_ticket = signal_card_lifecycle(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {"execution_lifecycle": "FILLED", "final_decision": "TAKE"},
        },
        execution_status="EXECUTION_BLOCKED",
    )
    assert no_ticket["card_status"] != "EXECUTED"
    with_ticket = signal_card_lifecycle(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "pipeline": {
                "execution_lifecycle": "FILLED",
                "ticket": 778899,
                "final_decision": "TAKE",
            },
        },
        execution_status="ORDER_SUBMITTED",
    )
    assert with_ticket["card_status"] == "EXECUTED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_terminal_cards_excluded_from_active_query() -> None:
    assert is_active_signal_card({"card_status": "WAITING"}) is True
    assert is_active_signal_card({"card_status": "TRADEABLE"}) is True
    assert is_active_signal_card({"card_status": "REJECTED"}) is False
    assert is_active_signal_card({"card_status": "EXPIRED"}) is False
    assert is_active_signal_card({"card_status": "CANCELLED"}) is False
    assert (
        is_active_signal_card(
            {"signal_lifecycle": "EXPIRED", "card_status": "WAITING"}
        )
        is False
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_xauusd_i_overlay_matches_canonical_gold() -> None:
    row = {
        "symbol": "XAUUSD",
        "direction": "SELL",
        "pipeline": {"final_decision": "TAKE", "sniper": "READY"},
    }
    last = {
        "symbol": "XAUUSD_I",
        "decision_action": "SELL",
        "forwarded_to_oms": False,
        "abort_reason": "RISK_REJECTED",
        "execution_blocked": {
            "stage": "RISK",
            "reason_code": "RISK_REJECTED",
            "human_reason": "min planned risk",
        },
    }
    assert overlay_cycle_matches_row(row, last) is True
    over = _overlay_last_ite_cycle(row, last)
    assert over["pipeline"]["execution_lifecycle"] == "EXECUTION_BLOCKED"
    assert over["rejection_reason"] == "RISK_REJECTED"


@pytest.mark.unit
@pytest.mark.trading_core
def test_eligible_fx_uses_same_live_eligible_path() -> None:
    for symbol, direction in (
        ("EURUSD", "BUY"),
        ("GBPUSD", "SELL"),
        ("USDJPY", "BUY"),
        ("XAUUSD_I", "SELL"),
    ):
        status = signal_execution_status(
            {
                "symbol": symbol,
                "direction": direction,
                "pipeline": {
                    "final_decision": "TAKE",
                    "execution_lifecycle": "EXECUTION_READY",
                    "sniper": "READY",
                },
            },
            live_state="ENABLED",
            orders_ok=True,
            research_focus=[symbol, "EURUSD", "GBPUSD", "USDJPY", "XAUUSD_I"],
        )
        assert status == "LIVE_ELIGIBLE", symbol
