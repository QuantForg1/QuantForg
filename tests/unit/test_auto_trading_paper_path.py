"""Paper-path verification — signal → risk → OMS → audit (no live MT5)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionBridgeContext,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.models import (
    MarketAnalysisSnapshot,
    NewsProtectionStatus,
    SessionFilterResult,
    TradeQualityFactor,
    TradeQualityScore,
    TrendSnapshot,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode

AS_OF = datetime(2026, 7, 20, 14, 30, tzinfo=UTC)
INPUT_HASH = "auto_paper_hash_00112233445566778899"


def _op() -> OperatorIdentity:
    return OperatorIdentity(user_id=uuid4(), role="owner", display_name="paper")


def _snapshot() -> MarketAnalysisSnapshot:
    code = SymbolCode(value="XAUUSD")
    structure = StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=AS_OF,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=TrendDirection.UP,
            as_of=AS_OF,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=4,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=AS_OF,
        config_version="ite-v1.0.0",
        input_hash=INPUT_HASH,
        structure_by_tf={"H1": structure},
        primary_structure=structure,
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=TrendSnapshot(
            macro_bias=TrendDirection.UP,
            primary=TrendDirection.UP,
            entry=TrendDirection.UP,
            execution=TrendDirection.UP,
            alignment_score=95,
            aligned=True,
            frames={"H4": "up", "H1": "up"},
            why="aligned",
        ),
        session=SessionFilterResult(
            session=MarketSession.LONDON,
            allowed=True,
            reason="ok",
        ),
        news=NewsProtectionStatus(enabled=False, blocked=False, reason="clear"),
        trade_quality=TradeQualityScore(
            total=92,
            passed=True,
            band="high_confidence",
            factors=(TradeQualityFactor(code="trend", weight=20, score=92),),
        ),
        spread=Decimal("0.30"),
    )


def _buy_decision():
    cfg = ITEConfig()
    snap = _snapshot()
    conf = ConfluenceResult(
        confidence=91,
        direction=TradeDirection.BUY,
        reasons=("bullish",),
        rejected_rules=(),
        input_hash="conf_paper",
        band="high_confidence",
        passed=True,
        factors={},
    )
    account = AccountRiskState(
        equity=Decimal("10000"),
        free_margin=Decimal("8000"),
        open_positions=0,
        market_open=True,
        atr=Decimal("2.5"),
        mid_price=Decimal("2350"),
    )
    elig = PositionEligibilityEngine(config=cfg).evaluate(
        snapshot=snap,
        confluence=conf,
        account=account,
        risk_allowed=True,
    )
    assert elig.eligible
    decision = TradeDecisionEngine(config=cfg).decide(
        snapshot=snap,
        confluence=conf,
        eligibility=elig,
        account=account,
        risk_score=20,
        approved_lots=Decimal("0.10"),
    )
    return decision, snap, account


@pytest.mark.unit
def test_paper_auto_trade_path_signal_to_oms_audit() -> None:
    """Verify: signal → risk PASS → order submitted → broker accepted → audit."""
    plane = OperationsControlPlane()
    op = _op()
    plane.transition_mode(op, OpsExecutionMode.CANARY, reason="paper", confirmed=True)
    plane.transition_mode(
        op, OpsExecutionMode.LIVE, reason="paper live", confirmed=True
    )
    plane.update_auto_trade_controls(
        op,
        enabled=True,
        reason="enable for paper verification",
    )

    oms = RecordingOmsPort(
        result=OmsSubmitResult(
            outcome="success",
            message="accepted",
            retcode=10009,
            order_ticket=4242,
            deal_ticket=5252,
            oms_status="filled",
            gateway_status="ok",
        )
    )
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE),
    )
    integ.bridge.bind_ops(plane)

    decision, snap, account = _buy_decision()
    assert decision.action is DecisionAction.BUY
    assert decision.eligibility.eligible is True
    assert decision.approved_lots is not None

    ctx = ExecutionBridgeContext(
        snapshot=snap,
        account=account,
        expected_input_hash=decision.input_hash,
        now=AS_OF,
        execution_enabled=True,
        risk_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        connected=True,
    )
    result = integ.bridge.handle(decision, ctx)

    assert result.forwarded_to_oms is True
    assert result.abort_reason is BridgeAbortReason.NONE
    assert result.oms_result is not None
    assert result.oms_result.outcome == "success"
    assert result.oms_result.order_ticket == 4242
    assert result.journal_entry.mt5_ticket == 4242
    assert oms.calls, "OMS must receive the order"
    assert any(e.action == "auto_trade_controls_change" for e in plane.audit.list())


@pytest.mark.unit
def test_paper_auto_trade_blocked_shows_exact_reason() -> None:
    plane = OperationsControlPlane()
    op = _op()
    plane.transition_mode(op, OpsExecutionMode.CANARY, reason="x", confirmed=True)
    plane.transition_mode(op, OpsExecutionMode.LIVE, reason="y", confirmed=True)
    # toggle remains OFF

    oms = RecordingOmsPort()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE),
    )
    integ.bridge.bind_ops(plane)

    decision, snap, account = _buy_decision()
    ctx = ExecutionBridgeContext(
        snapshot=snap,
        account=account,
        expected_input_hash=decision.input_hash,
        now=AS_OF,
        execution_enabled=True,
        risk_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        connected=True,
    )
    result = integ.bridge.handle(decision, ctx)
    assert result.forwarded_to_oms is False
    assert result.abort_reason is BridgeAbortReason.AUTO_TRADING_BLOCKED
    assert "Auto Trading toggle is OFF" in result.journal_entry.comment
    assert oms.calls == []
