"""TAKE must not silently vanish after Risk/Safety/OMS inference.

Live stall: Opportunity 73 PASS, Sniper READY, Decision SELL, Signal Center
OMS READY — while ITE last_cycle abort_reason=RISK_REJECTED (quality_weak)
and no MT5 ticket.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.institutional_ite_runtime import _merge_cycle_diagnostics
from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    execution_blocked_event,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_merge_keeps_execution_contract() -> None:
    ctx = {"equity": "139.90", "atr": "8.33"}
    cycle = {
        "equity": "139.90",
        "execution_contract": {"may_submit_oms": False, "fault_code": "RISK_REJECTED"},
        "execution_blocked": {"reason_code": "RISK_REJECTED", "stage": "RISK"},
    }
    merged = _merge_cycle_diagnostics(ctx, cycle)
    assert merged["execution_contract"]["fault_code"] == "RISK_REJECTED"
    assert merged["execution_blocked"]["stage"] == "RISK"
    assert merged["atr"] == "8.33"


def test_execution_blocked_event_shape() -> None:
    ev = execution_blocked_event(
        stage="RISK",
        reason_code="RISK_REJECTED",
        human_reason="Weak setup — sizing reject (quality=66 confidence=57)",
        correlation_id="trace-1",
    )
    assert ev["stage"] == "RISK"
    assert ev["reason_code"] == "RISK_REJECTED"
    assert ev["correlation_id"] == "trace-1"
    assert "timestamp" in ev


def test_signal_center_overlays_risk_reject_not_oms_ready() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 66,
            "ai_confidence": 57,
            "opportunity_score": 73,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    assert row["pipeline"]["oms"] == "READY"
    assert row["pipeline"]["execution_lifecycle"] == "EXECUTION_READY"
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "RISK_REJECTED",
            "decision_action": "NO_TRADE",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "RISK",
                "reason_code": "RISK_REJECTED",
                "human_reason": "Weak setup — sizing reject (quality=66 confidence=57)",
            },
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["pipeline"]["execution_lifecycle"] == "EXECUTION_BLOCKED"
    assert over["first_blocker"] == "RISK_REJECTED"
    assert over["execution_state"] == "EXECUTION_BLOCKED"


def test_signal_center_wait_unchanged_without_abort() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "trade_quality": 50,
            "ai_confidence": 50,
            "reject": True,
            "reason": "WAIT_CHASE",
            "sniper_entry": {"passed": False, "action": "WAIT"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {"forwarded_to_oms": False, "abort_reason": None, "decision_action": "NO_TRADE"},
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"].get("execution_lifecycle") != "FILLED"


def test_buy_and_sell_rows_overlay_independently() -> None:
    buy = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "BUY"},
        }
    )
    sell = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL"},
        }
    )
    last = {
        "forwarded_to_oms": False,
        "abort_reason": "SPREAD_UNACCEPTABLE",
        "execution_blocked": {
            "stage": "BROKER",
            "reason_code": "SPREAD_UNACCEPTABLE",
            "human_reason": "spread too wide",
        },
    }
    assert _overlay_last_ite_cycle(buy, last)["pipeline"]["broker"] == "BLOCK"
    assert _overlay_last_ite_cycle(sell, last)["pipeline"]["broker"] == "BLOCK"


def test_filled_ticket_not_overwritten_by_abort() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "trade_quality": 88,
            "ai_confidence": 81,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "BUY"},
            "order_status": "FILLED",
            "order_ticket": 12345,
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": True,
            "mt5_ticket": 12345,
            "abort_reason": None,
        },
    )
    assert over["pipeline"]["execution_lifecycle"] == "FILLED"


def test_quality_reject_still_zeros_lots() -> None:
    from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
        calculate_dynamic_lots_v2,
    )

    d = calculate_dynamic_lots_v2(
        equity=Decimal("5000"),
        stop_distance=Decimal("1.50"),
        risk_pct=Decimal("0.50"),
        quality_reject=True,
        quality_score=66,
        confidence=57,
        opportunity_score=73,
        sniper_passed=True,
        log=False,
    )
    assert d.valid is False
    assert d.final_lot == Decimal("0")
