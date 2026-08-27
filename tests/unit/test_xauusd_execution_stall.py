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
    assert over["pipeline"]["safety"] == "NOT_REACHED"
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


def test_signal_center_wait_not_oms_block_from_manage_only_last_cycle() -> None:
    """Opportunity WAIT must not inherit last_cycle NO_EXECUTABLE_SYMBOL as OMS BLOCK."""
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "trade_quality": 52,
            "ai_confidence": 58,
            "opportunity_score": 69,
            "opportunity_threshold": 70,
            "reject": True,
            "reason": "opportunity_score 69 < threshold 70 - WAIT",
            "sniper_entry": {
                "passed": True,
                "action": "WAIT",
                "setup_state": "SETUP_READY",
            },
        }
    )
    assert row["pipeline"]["oms"] == "NOT_REACHED"
    assert row["pipeline"]["final_decision"] == "WAIT"
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "NO_EXECUTABLE_SYMBOL",
            "cycle_outcome": "waiting_next_cycle",
            "decision_action": None,
            "mt5_ticket": None,
            "detail": "WAITING_NEXT_CYCLE — no executable symbol",
        },
    )
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["broker"] == "NOT_REACHED"
    assert over["pipeline"]["mt5"] == "NOT_REACHED"
    assert over["pipeline"]["final_decision"] == "WAIT"
    assert over["pipeline"].get("execution_lifecycle") != "EXECUTION_BLOCKED"
    assert over["pipeline"].get("first_blocker") != "NO_EXECUTABLE_SYMBOL"
    assert over.get("execution_state") != "EXECUTION_BLOCKED"


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


def test_bridge_abort_stage_eligibility_is_not_broker() -> None:
    from app.domain.institutional_trading.operations.execution_chain_log import (
        bridge_abort_stage,
    )

    assert bridge_abort_stage("eligibility_failed") == "ELIGIBILITY"
    assert bridge_abort_stage("ELIGIBILITY_FAILED") == "ELIGIBILITY"
    assert bridge_abort_stage("mt5_rejection") == "BROKER"
    assert bridge_abort_stage("RISK_REJECTED") == "RISK"
    assert bridge_abort_stage("kill_switch") == "SAFETY"


def test_signal_center_overlays_eligibility_failed_not_broker() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 66,
            "ai_confidence": 65,
            "opportunity_score": 71,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "eligibility_failed",
            "decision_action": "SELL",
            "mt5_ticket": None,
            "detail": "Confluence 65 (SELL) below institutional gate; Trade quality 66 below 80",
        },
    )
    assert over["first_blocker"] == "ELIGIBILITY_FAILED"
    assert over["pipeline"]["execution_lifecycle"] == "EXECUTION_BLOCKED"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["broker"] != "BLOCK"
    assert over["pipeline"]["mt5"] == "NOT_REACHED"


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_scalping_take_below_swing_quality_80_still_reaches_oms(side: str) -> None:
    """Live stall: Opportunity PASS + sniper TAKE, then swing quality 80 at the bridge."""
    from app.application.services.institutional_execution_integration import (
        InstitutionalExecutionIntegration,
    )
    from app.application.services.institutional_oms_adapter import RecordingOmsPort
    from app.domain.institutional_trading.ai_scalping.live_health import (
        get_live_health_monitor,
    )
    from app.domain.institutional_trading.config import ITEConfig
    from app.domain.institutional_trading.decision_models import (
        ConfluenceResult,
        TradeDirection,
    )
    from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
    from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
    from app.domain.institutional_trading.execution.models import (
        BridgeAbortReason,
        ExecutionMode,
    )
    from app.domain.institutional_trading.phase_a.plane import (
        reset_phase_a_plane_for_tests,
    )
    from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
    from app.domain.market_structure.enums import TrendDirection
    from tests.unit.test_institutional_trading_phase_c import (
        _account,
        _ctx,
        _snapshot,
    )

    trend = TrendDirection.UP if side == "BUY" else TrendDirection.DOWN
    direction = TradeDirection.BUY if side == "BUY" else TradeDirection.SELL
    snap = _snapshot(direction=trend, quality=66)
    conf = ConfluenceResult(
        confidence=65,
        direction=direction,
        reasons=("scalp",),
        rejected_rules=(),
        input_hash="scalp-elig",
        band="tradable",
        passed=True,
        factors={},
    )
    acct = _account()
    scalp = ITEConfig(trading_mode="scalping")
    elig = PositionEligibilityEngine(config=scalp).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    assert elig.eligible is True
    assert elig.checks.get("quality_ok") is True
    swing = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    assert swing.eligible is False
    decision = TradeDecisionEngine(config=scalp).decide(
        snapshot=snap,
        confluence=conf,
        eligibility=elig,
        account=acct,
        risk_score=20,
        approved_lots=Decimal("0.01"),
    )
    assert decision.action.value == side
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    reset_phase_a_plane_for_tests()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    assert integ.bridge.ite_config.is_scalping() is False
    result = integ.execute(decision, _ctx(decision, snap, acct))
    comment = str(getattr(getattr(result, "journal_entry", None), "comment", "") or "")
    assert result.abort_reason is not BridgeAbortReason.ELIGIBILITY_FAILED
    assert "below 80" not in comment
    assert "institutional gate" not in comment.lower()
    assert oms.calls, f"expected OMS submit, abort={result.abort_reason} {comment}"


def test_scalping_eligibility_still_blocks_already_in_trade() -> None:
    from uuid import uuid4

    from app.application.services.institutional_execution_integration import (
        InstitutionalExecutionIntegration,
    )
    from app.application.services.institutional_oms_adapter import RecordingOmsPort
    from app.domain.institutional_trading.ai_scalping.live_health import (
        get_live_health_monitor,
    )
    from app.domain.institutional_trading.config import ITEConfig
    from app.domain.institutional_trading.decision_models import (
        ConfluenceResult,
        TradeDirection,
    )
    from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
    from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
    from app.domain.institutional_trading.execution.models import (
        BridgeAbortReason,
        ExecutionBridgeContext,
        ExecutionMode,
    )
    from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
    from tests.unit.test_institutional_trading_phase_c import (
        AS_OF,
        _account,
        _snapshot,
    )

    snap = _snapshot(quality=66)
    conf = ConfluenceResult(
        confidence=65,
        direction=TradeDirection.BUY,
        reasons=("scalp",),
        rejected_rules=(),
        input_hash="scalp-book",
        band="tradable",
        passed=True,
        factors={},
    )
    scalp = ITEConfig(trading_mode="scalping", max_open_trades=1)
    acct = _account()
    elig = PositionEligibilityEngine(config=scalp).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    decision = TradeDecisionEngine(config=scalp).decide(
        snapshot=snap,
        confluence=conf,
        eligibility=elig,
        account=acct,
        risk_score=20,
        approved_lots=Decimal("0.01"),
    )
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
        ite_config=scalp,
    )
    bad = _account(already_in_trade=True, open_positions=1)
    result = integ.execute(
        decision,
        ExecutionBridgeContext(
            expected_input_hash=decision.input_hash,
            now=AS_OF,
            snapshot=snap,
            account=bad,
            risk_allowed=True,
            execution_enabled=True,
            connected=True,
            login=12345,
            user_id=uuid4(),
            request_id="ite-test-book",
        ),
    )
    assert result.abort_reason is BridgeAbortReason.ELIGIBILITY_FAILED
    assert oms.calls == []


def test_apply_trading_mode_syncs_bridge_ite_config() -> None:
    from types import SimpleNamespace

    from app.application.services.ai_scalping_mode import apply_trading_mode_to_runtime
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    runtime = SimpleNamespace(
        decision_pipeline=SimpleNamespace(
            config=DEFAULT_ITE_CONFIG,
            risk_engine=None,
        ),
        position_management=SimpleNamespace(
            engine=SimpleNamespace(config=None),
        ),
        plane=SimpleNamespace(max_open_trades=1, trading_mode="swing"),
        execution=SimpleNamespace(
            bridge=SimpleNamespace(ite_config=DEFAULT_ITE_CONFIG),
        ),
    )
    apply_trading_mode_to_runtime(runtime, mode="scalping")
    assert runtime.decision_pipeline.config.is_scalping() is True
    assert runtime.execution.bridge.ite_config.is_scalping() is True
    assert runtime.execution.bridge.ite_config is runtime.decision_pipeline.config


def test_scalping_take_reaches_oms_without_quality_ok_check() -> None:
    """Residual stall: eligible BUY/SELL with empty checks must not hit swing 80."""
    from dataclasses import replace

    from app.application.services.institutional_execution_integration import (
        InstitutionalExecutionIntegration,
    )
    from app.application.services.institutional_oms_adapter import RecordingOmsPort
    from app.domain.institutional_trading.ai_scalping.live_health import (
        get_live_health_monitor,
    )
    from app.domain.institutional_trading.config import ITEConfig
    from app.domain.institutional_trading.decision_models import (
        ConfluenceResult,
        EligibilityResult,
        TradeDirection,
    )
    from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
    from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
    from app.domain.institutional_trading.execution.models import (
        BridgeAbortReason,
        ExecutionMode,
    )
    from app.domain.institutional_trading.phase_a.plane import (
        reset_phase_a_plane_for_tests,
    )
    from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
    from app.domain.market_structure.enums import TrendDirection
    from tests.unit.test_institutional_trading_phase_c import (
        _account,
        _ctx,
        _snapshot,
    )

    snap = _snapshot(direction=TrendDirection.UP, quality=66)
    conf = ConfluenceResult(
        confidence=65,
        direction=TradeDirection.BUY,
        reasons=("scalp",),
        rejected_rules=(),
        input_hash="scalp-no-qok",
        band="tradable",
        passed=True,
        factors={},
    )
    acct = _account()
    scalp = ITEConfig(trading_mode="scalping")
    elig = PositionEligibilityEngine(config=scalp).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    decision = TradeDecisionEngine(config=scalp).decide(
        snapshot=snap,
        confluence=conf,
        eligibility=elig,
        account=acct,
        risk_score=20,
        approved_lots=Decimal("0.01"),
    )
    decision = replace(
        decision,
        eligibility=EligibilityResult(
            eligible=True, checks={}, rejection_reasons=()
        ),
        reasons=("scalp take",),
    )
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    reset_phase_a_plane_for_tests()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    assert integ.bridge.ite_config.is_scalping() is False
    result = integ.execute(decision, _ctx(decision, snap, acct))
    comment = str(getattr(getattr(result, "journal_entry", None), "comment", "") or "")
    assert result.abort_reason is not BridgeAbortReason.ELIGIBILITY_FAILED
    assert "below 80" not in comment
    assert oms.calls, f"expected OMS submit, abort={result.abort_reason} {comment}"
