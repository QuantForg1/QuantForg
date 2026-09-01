"""Research → existing ITE execution bridge. Does not submit orders."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.research_execution_bridge import (
    merge_research_into_execution_handoff,
    overlay_cycle_matches_row,
    research_live_focus_symbols,
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
def test_enabled_buy_in_focus_is_live_eligible_not_an_order() -> None:
    status = signal_execution_status(
        {"symbol": "EURUSD", "direction": "BUY"},
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
    assert blocked == "EXECUTION_BLOCKED"


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
