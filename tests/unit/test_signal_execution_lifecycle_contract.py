"""Qualified-signal lifecycle: no silent LIVE_ELIGIBLE, no fake EXECUTED.

Does not send orders. Does not lower P>70, sniper, RR, ATR, or $6/$20/$30.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.research_execution_bridge import (
    is_active_signal_card,
    signal_card_lifecycle,
    signal_execution_status,
)
from app.application.services.signal_center_service import _overlay_last_ite_cycle
from app.domain.institutional_trading.ai_scalping.same_symbol_requalification import (
    REQUALIFY_REJECT,
)
from app.domain.institutional_trading.config import (
    MAX_PLANNED_SL_RISK_USD,
    MAX_TOTAL_PLANNED_RISK_USD,
    MIN_PLANNED_RISK_USD,
)
from app.domain.institutional_trading.operations.scalp_eligibility import (
    sniper_is_take,
)
from app.domain.market_universe.constants import FROZEN_OPPORTUNITY_THRESHOLD

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _take(*, symbol: str = "EURUSD", direction: str = "BUY") -> dict:
    return {
        "symbol": symbol,
        "direction": direction,
        "pipeline": {
            "final_decision": "TAKE",
            "setup_state": "TAKE",
            "execution_lifecycle": "EXECUTION_READY",
            "sniper": "READY",
        },
    }


def test_qualified_research_is_not_execution_handoff() -> None:
    status = signal_execution_status(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "board_status": "QUALIFIED",
            "qualified_research": True,
            "pipeline": {"final_decision": "WAIT"},
        },
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["EURUSD"],
    )
    assert status == "WAITING_FOR_EXECUTION"
    assert status != "LIVE_ELIGIBLE"


def test_take_reaches_live_eligible_handoff() -> None:
    assert (
        signal_execution_status(
            _take(),
            live_state="ENABLED",
            orders_ok=True,
            research_focus=["EURUSD"],
        )
        == "LIVE_ELIGIBLE"
    )


def test_execution_timeout_rejects_take_and_leaves_active() -> None:
    over = _overlay_last_ite_cycle(
        _take(symbol="GBPUSD"),
        {
            "symbol": "GBPUSD",
            "decision_action": "BUY",
            "forwarded_to_oms": False,
            "abort_reason": "EXECUTION_TIMEOUT",
            "execution_blocked": {
                "stage": "OMS",
                "reason_code": "EXECUTION_TIMEOUT",
                "human_reason": "worker timed out before OMS ack",
            },
        },
    )
    assert over["rejection_reason"] == "EXECUTION_TIMEOUT"
    card = signal_card_lifecycle(over, execution_status="EXECUTION_BLOCKED")
    assert card["card_status"] == "REJECTED"
    assert is_active_signal_card({**over, "card_status": "REJECTED"}) is False


def test_stale_wait_abort_does_not_reject_take_snapshot() -> None:
    row = _take(symbol="NZDUSD")
    row["pipeline"]["abort_reason"] = "WAIT_INSUFFICIENT_RR"
    status = signal_execution_status(
        row,
        live_state="ENABLED",
        orders_ok=True,
        research_focus=["NZDUSD"],
    )
    assert status == "WAITING_FOR_EXECUTION"
    card = signal_card_lifecycle(row, execution_status=status)
    assert card["card_status"] == "WAITING"
    assert is_active_signal_card({**row, "card_status": "WAITING"}) is True


def test_opportunity_threshold_remains_strict_gt_70() -> None:
    assert FROZEN_OPPORTUNITY_THRESHOLD == 70


def test_sniper_confirmation_still_required() -> None:
    waiting = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "opportunity_score": 82,
        "sniper_entry": {"passed": False, "action": "WAIT", "setup_state": "WAIT"},
    }
    take = {
        "symbol": "EURUSD",
        "direction": "BUY",
        "opportunity_score": 82,
        "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
    }
    assert sniper_is_take(waiting) is False
    assert sniper_is_take(take) is True


def test_planned_risk_floors_unchanged() -> None:
    assert Decimal("6.00") == MIN_PLANNED_RISK_USD
    assert Decimal("20.00") == MAX_PLANNED_SL_RISK_USD
    assert Decimal("30.00") == MAX_TOTAL_PLANNED_RISK_USD


def test_gold_requalification_protection_still_imported() -> None:
    assert REQUALIFY_REJECT == "SAME_SYMBOL_REQUIRES_FRESH_STRUCTURE"


def test_duplicate_forward_without_new_ticket_is_not_executed() -> None:
    over = _overlay_last_ite_cycle(
        _take(),
        {
            "symbol": "EURUSD",
            "decision_action": "BUY",
            "forwarded_to_oms": True,
            "mt5_ticket": 0,
            "abort_reason": "ORDER_SEND_ERROR",
            "execution_blocked": {
                "stage": "BROKER",
                "reason_code": "ORDER_SEND_ERROR",
                "human_reason": "retcode 10019",
            },
        },
    )
    card = signal_card_lifecycle(over, execution_status="EXECUTION_BLOCKED")
    assert card["card_status"] != "EXECUTED"
    assert over.get("pipeline", {}).get("ticket") in (None, "", 0)
