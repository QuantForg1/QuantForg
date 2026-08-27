"""EXECUTION_REJECT_BURST counts genuine execution failures only.

Does not disable the 5/120s breaker, lower Opportunity 70, force TAKE,
or send live orders. OMS application / Risk / Safety / WAIT must not increment.
"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.ai_scalping.live_health import (
    LiveHealthMonitor,
    get_live_health_monitor,
)
from app.domain.institutional_trading.decision_models import DecisionAction
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionAttemptStatus,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    classify_post_ai_execution_chain,
)
from app.domain.institutional_trading.phase_a.burst_latch import BurstLatch
from app.domain.institutional_trading.phase_a.execution_reject import (
    BROKER_REJECTED,
    EXECUTION_REJECT_BURST,
    MT5_REJECTED,
    apply_oms_outcome_to_burst,
    burst_record_stage_for_cycle,
    classify_downstream_execution_reject,
    execution_observability,
    should_count_execution_reject,
)
from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from tests.unit.test_institutional_trading_phase_c import (
    _ctx,
    _sell_decision,
)
from tests.unit.test_reject_burst_classification import _oms, _pre_broker_oms_reject

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _reset() -> None:
    get_live_health_monitor().reset()
    reset_phase_a_plane_for_tests()


def _daily_loss_oms() -> OmsSubmitResult:
    return OmsSubmitResult(
        outcome="rejected",
        message="daily loss 15.21% exceeds 5%",
        retcode=None,
        order_ticket=None,
        deal_ticket=None,
        oms_status="rejected",
        gateway_status="order_check_only",
        raw={
            "order_send_reached": False,
            "order_check_reached": True,
            "oms_reached": True,
            "gateway_reached": True,
        },
    )


def _mt5_reject_oms(*, retcode: int = 10016) -> OmsSubmitResult:
    return _oms(retcode=retcode, order_send=True, gateway_status="order_send")


def _broker_reject_oms() -> OmsSubmitResult:
    return _oms(
        retcode=10004,
        message="requote",
        order_send=True,
        gateway_status="order_send",
    )


def _count(symbol: str = "XAUUSD_I") -> int:
    snap = get_live_health_monitor().reject_burst_observability(symbol)
    return int(snap.get("reject_burst_count") or 0)


def test_1_wait_does_not_increment_reject_burst() -> None:
    _reset()
    latch = BurstLatch(reject_threshold=1)
    assert burst_record_stage_for_cycle(
        decision_action="WAIT",
        oms_submit_called=False,
        abort_reason=None,
    ) is None
    decision, snap, acct = _sell_decision()
    watch = replace(decision, action=DecisionAction.WATCH)
    oms = RecordingOmsPort()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(watch, _ctx(watch, snap, acct))
    assert result.abort_reason is BridgeAbortReason.IGNORED_ACTION
    assert oms.calls == []
    assert _count() == 0
    assert latch.snapshot()["rejected_entries_last_window"] == 0


def test_2_opportunity_wait_does_not_increment_reject_burst() -> None:
    _reset()
    assert burst_record_stage_for_cycle(
        decision_action="WAIT",
        oms_submit_called=False,
        abort_reason="OPPORTUNITY_SCORE_BELOW_THRESHOLD",
    ) is None
    assert should_count_execution_reject(None, oms_submit_called=False) is False
    assert _count() == 0


def test_3_sniper_wait_does_not_increment_reject_burst() -> None:
    _reset()
    for abort in (
        "WAIT_NO_SNIPER_TRIGGER",
        "WAIT_CHASING",
        "WAIT_STALE_FVG",
        "SNIPER_STALE",
    ):
        assert burst_record_stage_for_cycle(
            decision_action="WAIT",
            oms_submit_called=False,
            abort_reason=abort,
        ) is None
    assert _count() == 0


def test_4_risk_block_does_not_increment_reject_burst() -> None:
    _reset()
    assert burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason="RISK_REJECTED",
    ) is None
    assert should_count_execution_reject(
        _daily_loss_oms(),
        abort_reason=BridgeAbortReason.OMS_FAILURE,
        oms_submit_called=True,
    ) is False
    decision, snap, acct = _sell_decision()
    oms = RecordingOmsPort(result=_daily_loss_oms())
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is BridgeAbortReason.OMS_FAILURE
    assert oms.calls, "OMS was reached for the application daily-loss reject"
    assert _count(str(decision.symbol)) == 0
    obs = execution_observability(
        oms_result=_daily_loss_oms(),
        abort_reason=BridgeAbortReason.OMS_FAILURE,
        oms_submit_called=True,
    )
    assert obs["execution_attempted"] is False
    assert obs["mt5_reached"] is False
    assert obs["counted_toward_reject_burst"] is False
    assert obs["reject_source"] == "OMS_APPLICATION"


def test_5_safety_block_does_not_increment_reject_burst() -> None:
    _reset()
    assert burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason="SAFETY_BLOCKED",
    ) is None
    assert apply_oms_outcome_to_burst(
        BurstLatch(reject_threshold=1),
        abort_reason=BridgeAbortReason.KILL_SWITCH,
        status=ExecutionAttemptStatus.ABORTED,
        oms_result=_pre_broker_oms_reject(),
    ) is None
    assert _count() == 0


def test_6_optimizer_block_without_execution_attempt_does_not_increment() -> None:
    _reset()
    assert burst_record_stage_for_cycle(
        decision_action="SELL",
        oms_submit_called=False,
        abort_reason="EXECUTION_OPTIMIZER_DEFER",
    ) is None
    assert should_count_execution_reject(
        None,
        abort_reason="EXECUTION_OPTIMIZER_DEFER",
        oms_submit_called=False,
    ) is False
    assert _count() == 0


def test_7_oms_not_reached_does_not_increment() -> None:
    _reset()
    assert should_count_execution_reject(None, oms_submit_called=False) is False
    obs = execution_observability(
        abort_reason=BridgeAbortReason.SELF_PROTECTION,
        oms_submit_called=False,
        reject_reason="New entries paused: EXECUTION_REJECT_BURST",
    )
    assert obs["oms_reached"] is False
    assert obs["execution_attempted"] is False
    assert obs["counted_toward_reject_burst"] is False


def test_8_oms_genuine_rejection_increments() -> None:
    _reset()
    stage = classify_downstream_execution_reject(
        _oms(retcode=10006, gateway_status="order_send"),
        abort_reason=BridgeAbortReason.MT5_REJECTION,
    )
    assert stage in {MT5_REJECTED, BROKER_REJECTED}
    decision, snap, acct = _sell_decision()
    oms = RecordingOmsPort(result=_mt5_reject_oms())
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is BridgeAbortReason.MT5_REJECTION
    assert _count(str(decision.symbol)) == 1


def test_9_broker_genuine_rejection_increments() -> None:
    _reset()
    decision, snap, acct = _sell_decision()
    oms = RecordingOmsPort(result=_broker_reject_oms())
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is BridgeAbortReason.MT5_REJECTION
    assert _count(str(decision.symbol)) == 1
    obs = execution_observability(
        oms_result=_broker_reject_oms(),
        abort_reason=result.abort_reason,
        oms_submit_called=True,
    )
    assert obs["oms_reached"] is True
    assert obs["execution_attempted"] is True
    assert obs["broker_reached"] is True
    assert obs["counted_toward_reject_burst"] is True


def test_10_mt5_genuine_rejection_increments() -> None:
    _reset()
    assert classify_downstream_execution_reject(
        _mt5_reject_oms(retcode=10016),
        abort_reason="MT5_REJECTION",
    ) == MT5_REJECTED
    get_live_health_monitor().record_reject(
        symbol="XAUUSD_I",
        source=MT5_REJECTED,
        reason="TRADE_RETCODE_INVALID_STOPS",
        mt5_retcode=10016,
        broker_retcode=10016,
    )
    assert _count("XAUUSD_I") == 1


def test_11_duplicate_retry_is_handled_correctly() -> None:
    """Rejected hashes are released so the next cycle may retry.

    Application OMS rejects must not increment on retry.
    Genuine MT5 rejects increment once per actual order_send attempt.
    A filled hash remains reserved (DUPLICATE) and does not increment.
    """
    _reset()
    decision, snap, acct = _sell_decision()
    oms_app = RecordingOmsPort(result=_daily_loss_oms())
    integ_app = InstitutionalExecutionIntegration.create(
        oms_app,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    first_app = integ_app.execute(decision, _ctx(decision, snap, acct))
    second_app = integ_app.execute(decision, _ctx(decision, snap, acct))
    assert first_app.abort_reason is BridgeAbortReason.OMS_FAILURE
    assert second_app.abort_reason is BridgeAbortReason.OMS_FAILURE
    assert len(oms_app.calls) == 2
    assert _count(str(decision.symbol)) == 0

    _reset()
    oms_mt5 = RecordingOmsPort(result=_mt5_reject_oms())
    integ_mt5 = InstitutionalExecutionIntegration.create(
        oms_mt5,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    first_mt5 = integ_mt5.execute(decision, _ctx(decision, snap, acct))
    second_mt5 = integ_mt5.execute(decision, _ctx(decision, snap, acct))
    assert first_mt5.abort_reason is BridgeAbortReason.MT5_REJECTION
    assert second_mt5.abort_reason is BridgeAbortReason.MT5_REJECTION
    assert len(oms_mt5.calls) == 2
    assert _count(str(decision.symbol)) == 2

    _reset()
    oms_ok = RecordingOmsPort()
    integ_ok = InstitutionalExecutionIntegration.create(
        oms_ok,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    filled = integ_ok.execute(decision, _ctx(decision, snap, acct))
    assert filled.forwarded_to_oms is True
    dup = integ_ok.execute(decision, _ctx(decision, snap, acct))
    assert dup.abort_reason is BridgeAbortReason.DUPLICATE_DECISION
    assert len(oms_ok.calls) == 1
    assert _count(str(decision.symbol)) == 0


def test_12_five_genuine_rejects_within_120s_arm_execution_reject_burst() -> None:
    _reset()
    mon = get_live_health_monitor()
    for _ in range(5):
        mon.record_reject(symbol="XAUUSD_I", source=MT5_REJECTED, mt5_retcode=10016)
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is False
    assert EXECUTION_REJECT_BURST in why
    snap = mon.reject_burst_observability("XAUUSD_I")
    assert snap["active"] is True
    assert snap["reject_burst_count"] == 5
    assert snap["reject_burst_window_seconds"] == 120
    assert snap["threshold"] == 5


def test_13_old_rejects_outside_120s_expire_automatically() -> None:
    _reset()
    mon = get_live_health_monitor()
    old = datetime.now(UTC) - timedelta(seconds=121)
    mon._symbol_rejects["XAUUSD_I"] = deque([old] * 5)
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is True
    assert why == "ok"
    assert _count("XAUUSD_I") == 0
    snap = mon.snapshot()
    assert snap["allow_new_entries"] is True


def test_14_recovered_execution_allows_subsequent_valid_take() -> None:
    _reset()
    mon = get_live_health_monitor()
    old = datetime.now(UTC) - timedelta(seconds=121)
    mon._symbol_rejects["XAUUSD_I"] = deque([old] * 5)
    assert mon.allow_new_entries(symbol="XAUUSD_I")[0] is True
    decision, snap, acct = _sell_decision()
    oms = RecordingOmsPort()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert oms.calls, f"recovered TAKE must reach OMS, abort={result.abort_reason}"
    assert result.forwarded_to_oms is True
    assert result.oms_result is not None
    assert result.oms_result.order_ticket == 1001


def test_15_no_permanent_latch() -> None:
    _reset()
    mon = LiveHealthMonitor(reject_burst_threshold=5, reject_window_seconds=120)
    now = datetime.now(UTC)
    mon._symbol_rejects["XAUUSD_I"] = deque(
        [now - timedelta(seconds=s) for s in (119, 80, 40, 20, 1)]
    )
    assert mon.allow_new_entries(symbol="XAUUSD_I")[0] is False
    mon._symbol_rejects["XAUUSD_I"] = deque(
        [now - timedelta(seconds=121)] * 5
    )
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is True
    assert why == "ok"
    assert mon.snapshot()["allow_new_entries"] is True


def test_16_take_is_not_execution() -> None:
    _reset()
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "OMS_FAILURE",
            "detail": "daily loss 15.21% exceeds 5%",
            "mt5_ticket": None,
            "oms_message": "daily loss 15.21% exceeds 5%",
            "market_context_diagnostics": {
                "execution_observability": execution_observability(
                    oms_result=_daily_loss_oms(),
                    abort_reason=BridgeAbortReason.OMS_FAILURE,
                    oms_submit_called=True,
                )
            },
        },
    )
    pipe = over["pipeline"]
    assert pipe["final_decision"] == "TAKE" or over.get("direction") == "SELL"
    assert pipe.get("forwarded_to_oms") is False
    assert pipe.get("ticket") in {None, ""}
    assert pipe.get("execution_attempted") is False
    assert pipe.get("mt5_reached") is False
    assert over.get("execution_state") != "EXECUTED"
    chain = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        may_submit_oms=False,
        blocking_stage="DAILY_LOSS_BLOCK",
        ticket=None,
        retcode=None,
        this_cycle_forwarded=False,
    )
    assert chain["forwarded_to_oms"] is False
    assert chain["ticket"] is None


def test_17_executed_requires_forwarded_to_oms_and_real_mt5_ticket() -> None:
    chain = classify_post_ai_execution_chain(
        forwarded_to_oms=True,
        may_submit_oms=True,
        blocking_stage=None,
        ticket=562442610,
        retcode=10009,
        this_cycle_forwarded=True,
    )
    assert chain["forwarded_to_oms"] is True
    assert chain["ticket"] == 562442610
    fake = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        may_submit_oms=False,
        blocking_stage="EXECUTION_REJECT_BURST",
        ticket=562442610,
        retcode=10009,
        this_cycle_forwarded=False,
    )
    assert fake["ticket"] is None
    assert fake["forwarded_to_oms"] is False
    take_only = classify_post_ai_execution_chain(
        forwarded_to_oms=False,
        may_submit_oms=True,
        blocking_stage=None,
        ticket=None,
        retcode=None,
        this_cycle_forwarded=False,
    )
    assert take_only["ticket"] is None
    assert take_only["forwarded_to_oms"] is False


def test_live_health_snapshot_reports_symbol_pause() -> None:
    _reset()
    mon = get_live_health_monitor()
    for _ in range(5):
        mon.record_reject(symbol="XAUUSD_I", source=MT5_REJECTED)
    snap = mon.snapshot()
    assert snap["allow_new_entries"] is False
    assert "EXECUTION_REJECT_BURST" in str(snap.get("block_reason") or "")
    assert snap["reject_burst_count"] == 5
    assert snap["reject_burst_window_seconds"] == 120
    assert snap["symbol_rejects"]["XAUUSD_I"]["paused"] is True
