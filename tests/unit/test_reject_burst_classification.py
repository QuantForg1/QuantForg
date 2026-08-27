"""REJECT_BURST classification: genuine execution rejects vs strategy/risk holds.

Does not submit orders, lower thresholds, disable the breaker, or force TAKE.
"""

from __future__ import annotations

import pytest

from app.application.services.signal_center_service import _overlay_last_ite_cycle
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionAttemptStatus,
    OmsSubmitResult,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    build_execution_handoff,
    classify_post_ai_execution_chain,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.phase_a.burst_latch import BurstLatch
from app.domain.institutional_trading.phase_a.control_vocab import (
    FinalControlState,
    map_to_final_control_state,
)
from app.domain.institutional_trading.phase_a.execution_reject import (
    BROKER_REJECTED,
    EXECUTION_REJECT_BURST,
    MT5_REJECTED,
    OMS_REJECTED,
    RISK_REJECTED,
    SAFETY_BLOCKED,
    apply_oms_outcome_to_burst,
    burst_record_stage_for_cycle,
    classify_downstream_execution_reject,
    first_blocking_gate_from_reasons,
)
from app.domain.institutional_trading.phase_a.plane import PhaseAControlPlane
from app.domain.institutional_trading.phase_a.config import PhaseAConfig

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _oms(
    *,
    outcome: str = "rejected",
    message: str = "broker reject",
    retcode: int | None = 10006,
    order_send: bool = True,
    order_check: bool = True,
    gateway_status: str = "order_send",
) -> OmsSubmitResult:
    return OmsSubmitResult(
        outcome=outcome,
        message=message,
        retcode=retcode,
        order_ticket=None,
        deal_ticket=None,
        oms_status=outcome,
        gateway_status=gateway_status,
        raw={
            "order_send_reached": order_send,
            "order_check_reached": order_check,
            "oms_reached": True,
            "gateway_reached": order_send or order_check,
        },
    )


def _pre_broker_oms_reject() -> OmsSubmitResult:
    return _oms(
        outcome="rejected",
        message="Risk engine rejected",
        retcode=None,
        order_send=False,
        order_check=False,
        gateway_status="not_called",
    )


def test_a_wait_does_not_increment_reject_burst() -> None:
    latch = BurstLatch(reject_threshold=1, cooldown_s=30.0)
    stage = burst_record_stage_for_cycle(
        decision_action="WAIT",
        oms_submit_called=False,
        abort_reason=None,
        oms_result=None,
    )
    assert stage is None
    assert apply_oms_outcome_to_burst(
        latch,
        abort_reason=BridgeAbortReason.IGNORED_ACTION,
        status=ExecutionAttemptStatus.ABORTED,
        oms_result=None,
    ) is None
    assert latch.snapshot()["rejected_entries_last_window"] == 0
    assert latch.is_latched(now=1.0) is False


def test_b_opportunity_wait_does_not_increment_reject_burst() -> None:
    latch = BurstLatch(reject_threshold=1)
    stage = burst_record_stage_for_cycle(
        decision_action="WAIT",
        oms_submit_called=False,
        abort_reason="OPPORTUNITY_SCORE_BELOW_THRESHOLD",
    )
    assert stage is None
    assert latch.snapshot()["reject_burst"]["count"] == 0


def test_c_sniper_wait_does_not_increment_reject_burst() -> None:
    stage = burst_record_stage_for_cycle(
        decision_action="WAIT",
        oms_submit_called=False,
        abort_reason="WAIT_NO_SNIPER_TRIGGER",
    )
    assert stage is None


def test_d_risk_block_before_oms_does_not_increment() -> None:
    latch = BurstLatch(reject_threshold=1)
    stage = burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason="RISK_REJECTED",
    )
    assert stage is None
    assert apply_oms_outcome_to_burst(
        latch,
        abort_reason=BridgeAbortReason.ELIGIBILITY_FAILED,
        status=ExecutionAttemptStatus.ABORTED,
        oms_result=_pre_broker_oms_reject(),
    ) is None
    assert latch.snapshot()["rejected_entries_last_window"] == 0


def test_e_safety_block_before_oms_does_not_increment() -> None:
    latch = BurstLatch(reject_threshold=1)
    stage = burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason=SAFETY_BLOCKED,
    )
    assert stage is None
    assert apply_oms_outcome_to_burst(
        latch,
        abort_reason=BridgeAbortReason.KILL_SWITCH,
        status=ExecutionAttemptStatus.ABORTED,
        oms_result=_pre_broker_oms_reject(),
    ) is None
    assert latch.is_latched(now=1.0) is False


def test_oms_pipeline_reject_without_order_send_does_not_increment() -> None:
    latch = BurstLatch(reject_threshold=1, failure_threshold=1)
    result = apply_oms_outcome_to_burst(
        latch,
        abort_reason=BridgeAbortReason.OMS_FAILURE,
        status=ExecutionAttemptStatus.OMS_REJECTED,
        oms_result=_pre_broker_oms_reject(),
    )
    assert result is None
    assert latch.snapshot()["rejected_entries_last_window"] == 0
    assert latch.snapshot()["execution_failures_last_window"] == 0
    assert classify_downstream_execution_reject(
        _pre_broker_oms_reject(), abort_reason="OMS_FAILURE"
    ) is None


def test_f_actual_mt5_execution_rejection_increments() -> None:
    latch = BurstLatch(reject_threshold=5, failure_threshold=5)
    ev = apply_oms_outcome_to_burst(
        latch,
        abort_reason=BridgeAbortReason.MT5_REJECTION,
        status=ExecutionAttemptStatus.OMS_REJECTED,
        oms_result=_oms(retcode=10006),
    )
    assert ev is None  # below threshold
    snap = latch.snapshot()
    assert snap["rejected_entries_last_window"] == 1
    assert snap["execution_failures_last_window"] == 1
    assert snap["reject_burst"]["last_event_stage"] == MT5_REJECTED
    assert classify_downstream_execution_reject(
        _oms(retcode=10006), abort_reason="MT5_REJECTION"
    ) == MT5_REJECTED


def test_g_repeated_genuine_failures_activate_reject_burst() -> None:
    latch = BurstLatch(
        reject_threshold=5,
        failure_threshold=5,
        cooldown_s=300.0,
        reject_window_s=120.0,
    )
    armed = None
    for i in range(5):
        armed = apply_oms_outcome_to_burst(
            latch,
            abort_reason=BridgeAbortReason.MT5_REJECTION,
            status=ExecutionAttemptStatus.OMS_REJECTED,
            oms_result=_oms(retcode=10016),
        )
    assert armed is not None
    assert latch.is_latched() is True
    snap = latch.snapshot()
    assert snap["latched"] is True
    assert snap["reject_burst"]["active"] is True
    assert snap["reject_burst"]["count"] >= 5
    assert snap["blocking_gate"] == EXECUTION_REJECT_BURST
    plane = PhaseAControlPlane(
        config=PhaseAConfig(burst_cooldown_seconds=300.0, reject_burst_threshold=5)
    )
    plane.burst = latch
    gate = plane.evaluate_new_entry_gate(
        symbol="XAUUSD_i", bid=2400.0, ask=2400.3, quote_age_seconds=1.0
    )
    assert gate["allow_new_entry"] is False
    assert gate["final_control_state"] == "HALT"
    assert gate["first_blocking_gate"] == EXECUTION_REJECT_BURST


def test_h_reject_burst_recovers_on_configured_cooldown_without_fill() -> None:
    latch = BurstLatch(reject_threshold=2, failure_threshold=99, cooldown_s=30.0)
    latch.record_broker_reject(now=1.0, stage=MT5_REJECTED)
    ev = latch.record_broker_reject(now=2.0, stage=MT5_REJECTED)
    assert ev is not None
    assert latch.is_latched(now=10.0) is True
    assert latch.is_latched(now=33.0) is False
    snap = latch.snapshot()
    cond = str(snap["reject_burst"]["clear_condition"])
    assert "fill not required" in cond
    assert "300" not in cond or "30" in cond


def test_i_valid_take_not_blocked_by_stale_scanner_eligibility() -> None:
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (
        _row_from_score,
    )
    from app.domain.institutional_trading.ai_scalping.symbol_state import (
        SymbolStateBook,
    )
    from app.domain.institutional_trading.operations.scalp_eligibility import (
        explain_scalp_handoff,
    )

    gold = "XAUUSD_I"
    book = SymbolStateBook()
    for _ in range(5):
        book.note_reject(gold)
    score = {
        "symbol": gold,
        "direction": "SELL",
        "signal_action": "SELL",
        "reject": False,
        "opportunity_score": 77,
        "opportunity_threshold": 70,
        "opportunity_eligible": True,
        "trade_quality": 69,
        "ai_confidence": 58,
        "setup_state": "TAKE",
        "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
    }
    row = _row_from_score(score, book=book, config=DEFAULT_AI_SCALPING_CONFIG)
    assert row.reject is False
    assert "execution health" not in str(row.reject_reason or "").lower()
    trace = explain_scalp_handoff(
        score,
        portfolio_row=row.to_dict(),
        universe=(gold,),
        in_portfolio_eligible=True,
    )
    assert trace.should_hand_off is True
    latch = BurstLatch(reject_threshold=5)
    assert burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason=None,
    ) is None
    assert latch.is_latched(now=1.0) is False


def test_j_k_no_manufactured_ticket_executed_requires_forward_and_ticket() -> None:
    chain = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        may_submit_oms=False,
        blocking_stage="EXECUTION_REJECT_BURST",
        ticket=562442610,
        retcode=10009,
        this_cycle_forwarded=False,
    )
    assert chain["ticket"] is None
    assert chain["forwarded_to_oms"] is False
    assert chain["oms_submit"] != "PASS"
    handoff = build_execution_handoff(
        take=True,
        abort_reason="EXECUTION_REJECT_BURST",
        blocking_stage="EXECUTION_REJECT_BURST",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert handoff["execution_confirmed"] is False
    assert handoff["mt5_ticket"] is None
    assert handoff["oms_forwarded"] is False
    filled = classify_post_ai_execution_chain(
        forwarded_to_oms=True,
        may_submit_oms=True,
        blocking_stage=None,
        ticket=9001,
        retcode=10009,
        this_cycle_forwarded=True,
    )
    assert filled["forwarded_to_oms"] is True
    assert filled["ticket"] == 9001


def test_overlay_reject_burst_is_not_oms_or_risk_engine() -> None:
    over = _overlay_last_ite_cycle(
        {
            "direction": "SELL",
            "pipeline": {
                "decision": "SELL",
                "final_decision": "TAKE",
                "sniper": "READY",
                "risk": "READY",
            },
        },
        {
            "forwarded_to_oms": False,
            "abort_reason": "RISK_REJECTED",
            "detail": "continuous_ops_pause_new_entries; phase_a:REJECT_BURST",
            "execution_blocked": {
                "reason_code": "EXECUTION_REJECT_BURST",
                "human_reason": "continuous_ops_pause_new_entries; phase_a:REJECT_BURST",
                "stage": "EXECUTION_REJECT_BURST",
            },
            "mt5_ticket": None,
        },
    )
    pipe = over["pipeline"]
    assert pipe["first_blocker"] == EXECUTION_REJECT_BURST
    assert pipe["blocker_category"] == EXECUTION_REJECT_BURST
    assert pipe["risk"] == "READY"
    assert pipe["oms"] == "NOT_REACHED"
    assert pipe["broker"] == "NOT_REACHED"
    assert pipe["mt5"] == "NOT_REACHED"
    assert pipe["ticket"] is None
    assert pipe["forwarded_to_oms"] is False


def test_contract_burst_is_not_risk_rejected_or_direction_none() -> None:
    from decimal import Decimal

    facts = GoldExecutionFacts(
        symbol="XAUUSD_i",
        direction="SELL",
        action="SELL",
        market_open=True,
        tradable=True,
        candles_ok=True,
        bid=Decimal("2400"),
        ask=Decimal("2400.3"),
        quote_age_seconds=1.0,
        spread=Decimal("0.3"),
        structure_score=80,
        momentum_score=70,
        quality=70,
        confidence=70,
        pa_confluence=70,
        risk_reward=Decimal("2"),
        volatility_ok=True,
        session_quality_ok=True,
        safety_allowed=True,
        kill_switch=False,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=False,
        risk_reasons=(
            "continuous_ops_pause_new_entries",
            "phase_a:REJECT_BURST",
        ),
        approved_lots=Decimal("0"),
        portfolio_allow=True,
        optimizer_state="EXECUTE_NOW",
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        gold_only=True,
        opportunity_score=77,
        opportunity_threshold=70,
    )
    out = evaluate_gold_execution_contract(facts)
    assert out.may_submit_oms is False
    assert out.fault_code == EXECUTION_REJECT_BURST
    assert out.fault_code != "DIRECTION_NONE"
    assert out.fault_code != RISK_REJECTED


def test_first_blocking_gate_tokens() -> None:
    assert (
        first_blocking_gate_from_reasons(
            ("continuous_ops_pause_new_entries", "phase_a:REJECT_BURST")
        )
        == EXECUTION_REJECT_BURST
    )
    assert first_blocking_gate_from_reasons(("min lot constraint",)) == RISK_REJECTED
    assert first_blocking_gate_from_reasons(("SAFETY_BLOCKED",)) == SAFETY_BLOCKED
    assert bridge_abort_stage("EXECUTION_REJECT_BURST") == "EXECUTION_REJECT_BURST"
    assert bridge_abort_stage("phase_a:REJECT_BURST") == "EXECUTION_REJECT_BURST"
    final, gate = map_to_final_control_state(burst_latched=True)
    assert final is FinalControlState.HALT
    assert gate == EXECUTION_REJECT_BURST


def test_broker_reject_without_mt5_retcode_is_broker_rejected() -> None:
    result = _oms(retcode=None, order_send=True, gateway_status="order_send")
    assert (
        classify_downstream_execution_reject(result, abort_reason="OMS_FAILURE")
        == BROKER_REJECTED
    )
    assert OMS_REJECTED not in {
        classify_downstream_execution_reject(result, abort_reason="OMS_FAILURE")
    }
