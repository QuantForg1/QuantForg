"""Fast decision path — rotate candidate blocks, never force trades or retry order_send."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    apply_focus_hysteresis,
    classify_candidate_outcome,
    ensure_opportunity_window,
    opportunity_window_snapshot,
    record_cycle_classification,
    reset_fast_decision_path,
    set_focus,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_no_market_context_stays_hard_block() -> None:
    out = classify_candidate_outcome(
        abort_reason="NO_MARKET_CONTEXT",
        failed_reasons=(
            "CLOUDFLARE_ORIGIN_UNREACHABLE: Gateway /candles/AUDUSD_I "
            "failed upstream HTTP 530",
        ),
        cycle_outcome="no_snapshot",
    )
    assert out["fault_class"] == FaultClass.HARD_BLOCK.value
    assert out["decision_state"] == DecisionState.HARD_BLOCK.value
    assert out["next_action"] == CandidateAction.FAIL_CLOSED.value
    assert out["decision_state"] != DecisionState.DEGRADED.value


def test_advisory_does_not_block_or_rotate() -> None:
    out = classify_candidate_outcome(
        abort_reason="optional enrichment unavailable",
        cycle_outcome="ok",
    )
    assert out["fault_class"] == FaultClass.ADVISORY.value
    assert out["decision_state"] == DecisionState.DEGRADED.value
    assert out["candidate_action"] == CandidateAction.CONTINUE.value
    assert out["skip_idle_sleep"] is True
    assert out["release_entry_budget"] is True


def test_min_lot_infeasible_rotates_focus() -> None:
    out = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("minimum lot causes risk violation",),
        cycle_outcome="safety_blocked",
    )
    assert out["fault_class"] == FaultClass.CANDIDATE_BLOCK.value
    assert out["fault_code"] == "MIN_LOT_RISK_INFEASIBLE"
    assert out["next_action"] == CandidateAction.ROTATE_FOCUS.value
    assert out["skip_idle_sleep"] is True
    assert out["release_entry_budget"] is True


def test_symbol_not_tradable_rotates() -> None:
    out = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("symbol_tradable=false",),
    )
    assert out["next_action"] == CandidateAction.ROTATE_FOCUS.value
    assert out["fault_code"] == "SYMBOL_NOT_TRADEABLE"


def test_kill_switch_fail_closed() -> None:
    out = classify_candidate_outcome(
        abort_reason="SAFETY_BLOCKED",
        failed_reasons=("kill switch armed",),
    )
    assert out["candidate_action"] == CandidateAction.FAIL_CLOSED.value
    assert out["skip_idle_sleep"] is False
    assert out["release_entry_budget"] is False


def test_gateway_down_is_system_block() -> None:
    out = classify_candidate_outcome(abort_reason="Gateway unavailable")
    assert out["fault_class"] == FaultClass.SYSTEM_BLOCK.value
    assert out["candidate_action"] == CandidateAction.FAIL_CLOSED.value


def test_stale_quote_hard_blocks() -> None:
    out = classify_candidate_outcome(abort_reason="stale quote")
    assert out["decision_state"] == DecisionState.HARD_BLOCK.value
    assert out["candidate_action"] == CandidateAction.FAIL_CLOSED.value


def test_setup_not_ready_waits_same_focus() -> None:
    out = classify_candidate_outcome(
        abort_reason="NO_ELIGIBLE_SETUP",
        decision_action="NO_TRADE",
    )
    assert out["next_action"] == CandidateAction.WAIT_SAME_FOCUS.value
    assert out["decision_state"] in {
        DecisionState.SETUP_NOT_READY.value,
        DecisionState.WAIT_SAME_FOCUS.value,
    }


def test_spread_wait_does_not_rotate() -> None:
    out = classify_candidate_outcome(abort_reason="UNACCEPTABLE_SPREAD")
    assert out["next_action"] == CandidateAction.WAIT_SAME_FOCUS.value


def test_unknown_order_requires_reconciliation_not_retry() -> None:
    out = classify_candidate_outcome(abort_reason="ORDER_UNKNOWN")
    assert out["decision_state"] == DecisionState.ORDER_UNKNOWN.value
    assert out["next_action"] == CandidateAction.RECONCILE.value
    assert out["retryable"] is False


def test_oms_forward_is_submitted_not_no_trade() -> None:
    out = classify_candidate_outcome(
        abort_reason="",
        decision_action="BUY",
        forwarded_to_oms=True,
    )
    assert out["decision_state"] == DecisionState.ORDER_SUBMITTED.value
    assert out["retryable"] is False


def test_focus_hysteresis_holds_valid_focus() -> None:
    symbol, reason = apply_focus_hysteresis(
        current_focus="EURUSD_I",
        eligible_symbols=["GBPUSD_I", "EURUSD_I", "USDJPY_I"],
        scores={"EURUSD_I": 70, "GBPUSD_I": 74, "USDJPY_I": 60},
        proposed="GBPUSD_I",
    )
    assert symbol == "EURUSD_I"
    assert reason == "HOLD_FOCUS"


def test_focus_rotates_when_materially_better() -> None:
    symbol, reason = apply_focus_hysteresis(
        current_focus="EURUSD_I",
        eligible_symbols=["EURUSD_I", "GBPUSD_I"],
        scores={"EURUSD_I": 60, "GBPUSD_I": 80},
        proposed="GBPUSD_I",
    )
    assert symbol == "GBPUSD_I"
    assert reason == "ROTATE_MATERIAL_BETTER"


def test_focus_no_eligible_is_no_executable_focus() -> None:
    symbol, reason = apply_focus_hysteresis(
        current_focus="NZDUSD_I",
        eligible_symbols=[],
        scores={"NZDUSD_I": 40},
        proposed="NZDUSD_I",
    )
    assert symbol is None
    assert reason == "NO_EXECUTABLE_FOCUS"


def test_focus_rotates_when_current_invalid() -> None:
    symbol, reason = apply_focus_hysteresis(
        current_focus="XAUUSD_I",
        eligible_symbols=["NZDUSD_I", "EURUSD_I"],
        scores={"NZDUSD_I": 55, "EURUSD_I": 50},
        proposed="NZDUSD_I",
    )
    assert symbol == "NZDUSD_I"
    assert reason == "FOCUS_SELECTED"


def test_opportunity_window_does_not_force_trades() -> None:
    reset_fast_decision_path()
    ensure_opportunity_window(now_mono=1000.0)
    set_focus("NZDUSD_I", reason="FOCUS_SELECTED")
    record_cycle_classification(
        classify_candidate_outcome(
            abort_reason="SAFETY_BLOCKED",
            failed_reasons=("minimum lot causes risk violation",),
        ),
        cycle_ms=42.0,
    )
    snap = opportunity_window_snapshot(now_mono=1000.0 + 60)
    assert snap["forces_trades"] is False
    assert snap["order_send_retries"] is False
    assert snap["active"] is True
    assert snap["remaining_seconds"] == 30 * 60 - 60
    assert snap["current_focus"] == "NZDUSD_I"
    assert snap["candidate_blocks"] == 1
    assert snap["first_natural_trade"] is False


def test_window_expires_after_30_minutes() -> None:
    reset_fast_decision_path()
    ensure_opportunity_window(now_mono=0.0)
    snap = opportunity_window_snapshot(now_mono=30 * 60 + 1)
    assert snap["active"] is False
    assert snap["remaining_seconds"] == 0.0


def test_gateway_client_never_retries_order_send() -> None:
    src = Path("app/infrastructure/brokers/mt5/gateway_client.py").read_text(
        encoding="utf-8"
    )
    assert "Never retry order_send" in src
    assert "order_send" in src
