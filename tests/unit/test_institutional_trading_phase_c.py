"""Phase C unit tests — Execution Bridge, journal, kill switch, canary, OMS port."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from app.domain.institutional_trading.execution.hashing import compute_decision_hash
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
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.timeframe import Timeframe
from app.domain.market_structure.enums import StructureRole, TrendDirection
from app.domain.market_structure.models import StructureSnapshot, TrendState
from app.domain.value_objects.identity import SymbolCode

AS_OF = datetime(2026, 7, 20, 14, 30, tzinfo=UTC)
INPUT_HASH = "phasec_snap_hash_00112233445566778899aabb"


def _trend(direction: TrendDirection = TrendDirection.UP) -> TrendSnapshot:
    return TrendSnapshot(
        macro_bias=direction,
        primary=direction,
        entry=direction,
        execution=direction,
        alignment_score=95,
        aligned=True,
        frames={"H4": direction.value, "H1": direction.value},
        why="aligned",
    )


def _quality(total: int = 92) -> TradeQualityScore:
    return TradeQualityScore(
        total=total,
        passed=total >= 80,
        band="high_confidence" if total >= 90 else "tradable",
        factors=(TradeQualityFactor(code="trend", weight=20, score=total),),
    )


def _structure(direction: TrendDirection = TrendDirection.UP) -> StructureSnapshot:
    code = SymbolCode(value="XAUUSD")
    return StructureSnapshot(
        symbol_code=code,
        timeframe=Timeframe.H1,
        as_of=AS_OF,
        swings=(),
        nodes=(),
        trend=TrendState(
            symbol_code=code,
            timeframe=Timeframe.H1,
            direction=direction,
            as_of=AS_OF,
            last_structure_role=StructureRole.HIGHER_HIGH,
            swing_count=4,
        ),
        breaks_of_structure=(),
        changes_of_character=(),
    )


def _snapshot(
    *,
    direction: TrendDirection = TrendDirection.UP,
    quality: int = 92,
    session_allowed: bool = True,
    news_blocked: bool = False,
    spread: Decimal = Decimal("0.30"),
    as_of: datetime = AS_OF,
) -> MarketAnalysisSnapshot:
    return MarketAnalysisSnapshot(
        symbol="XAUUSD",
        as_of=as_of,
        config_version="ite-v1.0.0",
        input_hash=INPUT_HASH,
        structure_by_tf={"H1": _structure(direction)},
        primary_structure=_structure(direction),
        liquidity=None,
        order_blocks=None,
        fair_value_gaps=None,
        trend=_trend(direction),
        session=SessionFilterResult(
            session=MarketSession.LONDON_NY_OVERLAP,
            allowed=session_allowed,
            reason="ok" if session_allowed else "session blocked",
        ),
        news=NewsProtectionStatus(
            enabled=news_blocked,
            blocked=news_blocked,
            reason="news" if news_blocked else "clear",
        ),
        trade_quality=_quality(quality),
        spread=spread,
    )


def _account(**kwargs: object) -> AccountRiskState:
    base: dict[str, object] = dict(  # noqa: C408
        equity=Decimal("10000"),
        peak_equity=Decimal("10000"),
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=0,
        already_in_trade=False,
        consecutive_losses=0,
        cooldown_active=False,
        market_open=True,
        atr=Decimal("5"),
        mid_price=Decimal("2300"),
        free_margin=Decimal("10000"),
    )
    base.update(kwargs)
    return AccountRiskState(**base)  # type: ignore[arg-type]


def _buy_decision(*, as_of: datetime = AS_OF):
    snap = _snapshot(as_of=as_of)
    conf = ConfluenceResult(
        confidence=92,
        direction=TradeDirection.BUY,
        reasons=("aligned",),
        rejected_rules=(),
        input_hash="conf1",
        band="high_confidence",
        passed=True,
        factors={"mtf": 95},
    )
    acct = _account()
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    assert elig.eligible
    return (
        TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=acct,
            risk_score=20,
            approved_lots=Decimal("0.10"),
        ),
        snap,
        acct,
    )


def _sell_decision(*, as_of: datetime = AS_OF):
    snap = _snapshot(direction=TrendDirection.DOWN, as_of=as_of)
    conf = ConfluenceResult(
        confidence=91,
        direction=TradeDirection.SELL,
        reasons=("bearish",),
        rejected_rules=(),
        input_hash="conf2",
        band="high_confidence",
        passed=True,
        factors={},
    )
    acct = _account()
    elig = PositionEligibilityEngine(config=ITEConfig()).evaluate(
        snapshot=snap,
        confluence=conf,
        account=acct,
        risk_allowed=True,
    )
    assert elig.eligible
    return (
        TradeDecisionEngine(config=ITEConfig()).decide(
            snapshot=snap,
            confluence=conf,
            eligibility=elig,
            account=acct,
            risk_score=20,
            approved_lots=Decimal("0.10"),
        ),
        snap,
        acct,
    )


def _ctx(
    decision,
    snap,
    acct,
    *,
    now: datetime | None = None,
    execution_enabled: bool = True,
    expected_hash: str | None = None,
) -> ExecutionBridgeContext:
    return ExecutionBridgeContext(
        expected_input_hash=expected_hash or decision.input_hash,
        now=now or AS_OF,
        snapshot=snap,
        account=acct,
        risk_allowed=True,
        execution_enabled=execution_enabled,
        connected=True,
        login=12345,
        user_id=uuid4(),
        request_id="ite-test-1",
    )


def _bridge(
    oms: RecordingOmsPort,
    *,
    mode: ExecutionMode = ExecutionMode.LIVE,
    ttl: int = 30,
) -> InstitutionalExecutionIntegration:
    return InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=mode, decision_ttl_seconds=ttl),
    )


@pytest.mark.unit
class TestExecutionBridgePhaseC:
    def test_watch_and_no_trade_ignored(self) -> None:
        decision, snap, acct = _buy_decision()
        watch = replace(
            decision,
            action=DecisionAction.WATCH,
            direction=TradeDirection.BUY,
        )
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        result = integ.execute(watch, _ctx(watch, snap, acct))
        assert result.aborted
        assert result.abort_reason is BridgeAbortReason.IGNORED_ACTION
        assert oms.calls == []

        no_trade = replace(decision, action=DecisionAction.NO_TRADE)
        result2 = integ.execute(no_trade, _ctx(no_trade, snap, acct))
        assert result2.abort_reason is BridgeAbortReason.IGNORED_ACTION
        assert oms.calls == []

    def test_shadow_mode_journals_without_oms(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.SHADOW)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.forwarded_to_oms is False
        assert result.aborted is False
        assert result.journal_entry.execution_result == "shadow"
        assert oms.calls == []
        assert len(integ.bridge.journal.list()) == 1

    def test_buy_execution_live(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.forwarded_to_oms is True
        assert result.aborted is False
        assert len(oms.calls) == 1
        assert oms.calls[0]["intent"]["side"] == "buy"
        assert result.journal_entry.mt5_ticket == 1001
        assert result.journal_entry.mt5_deal == 2001
        assert result.journal_entry.retcode == 10009

    def test_sell_execution_live(self) -> None:
        decision, snap, acct = _sell_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.forwarded_to_oms is True
        assert oms.calls[0]["intent"]["side"] == "sell"

    def test_duplicate_decision(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        ctx = _ctx(decision, snap, acct)
        first = integ.execute(decision, ctx)
        assert first.forwarded_to_oms is True
        second = integ.execute(decision, ctx)
        assert second.abort_reason is BridgeAbortReason.DUPLICATE_DECISION
        assert len(oms.calls) == 1
        assert integ.bridge.metrics.snapshot()["duplicates"] == 1

    def test_retry_not_allowed_after_oms_failure(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort(
            result=OmsSubmitResult(
                outcome="failed",
                message="oms down",
                retcode=10031,
                oms_status="failed",
                gateway_status="failed",
            )
        )
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        ctx = _ctx(decision, snap, acct)
        first = integ.execute(decision, ctx)
        assert first.forwarded_to_oms is True
        assert first.abort_reason is BridgeAbortReason.GATEWAY_FAILURE
        second = integ.execute(decision, ctx)
        assert second.abort_reason is BridgeAbortReason.DUPLICATE_DECISION
        assert len(oms.calls) == 1

    def test_expired_decision(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE, ttl=30)
        late = AS_OF + timedelta(seconds=31)
        result = integ.execute(decision, _ctx(decision, snap, acct, now=late))
        assert result.abort_reason is BridgeAbortReason.DECISION_EXPIRED
        assert oms.calls == []

    def test_kill_switch(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        integ.bridge.kill_switch.arm()
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.abort_reason is BridgeAbortReason.KILL_SWITCH
        assert oms.calls == []

    def test_execution_disabled(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        result = integ.execute(
            decision, _ctx(decision, snap, acct, execution_enabled=False)
        )
        assert result.abort_reason is BridgeAbortReason.EXECUTION_DISABLED
        assert oms.calls == []

    def test_canary_mode_one_trade_per_day(self) -> None:
        d1, snap1, acct1 = _buy_decision()
        d2 = replace(d1, confidence=93, quality=93)
        assert compute_decision_hash(d1) != compute_decision_hash(d2)

        oms = RecordingOmsPort()
        integ = InstitutionalExecutionIntegration.create(
            oms,
            config=ExecutionBridgeConfig(
                mode=ExecutionMode.CANARY_LIVE,
                canary_max_trades_per_day=1,
            ),
        )
        r1 = integ.execute(d1, _ctx(d1, snap1, acct1))
        assert r1.forwarded_to_oms is True
        r2 = integ.execute(d2, _ctx(d2, snap1, acct1))
        assert r2.abort_reason is BridgeAbortReason.CANARY_DAILY_CAP
        assert len(oms.calls) == 1

    def test_input_hash_mismatch(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms)
        result = integ.execute(
            decision,
            _ctx(decision, snap, acct, expected_hash="tampered"),
        )
        assert result.abort_reason is BridgeAbortReason.INPUT_HASH_MISMATCH
        assert oms.calls == []

    def test_oms_failure(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort(
            result=OmsSubmitResult(
                outcome="failed",
                message="pipeline rejected",
                retcode=0,
                oms_status="failed",
                gateway_status="ok",
            )
        )
        integ = _bridge(oms)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.forwarded_to_oms is True
        assert result.abort_reason is BridgeAbortReason.OMS_FAILURE

    def test_gateway_failure(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort(
            result=OmsSubmitResult(
                outcome="gateway_failure",
                message="gateway unreachable",
                retcode=10031,
                oms_status="failed",
                gateway_status="failed",
            )
        )
        integ = _bridge(oms)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.abort_reason is BridgeAbortReason.GATEWAY_FAILURE

    def test_mt5_rejection(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort(
            result=OmsSubmitResult(
                outcome="rejected",
                message="broker rejected",
                retcode=10006,
                oms_status="rejected",
                gateway_status="ok",
            )
        )
        integ = _bridge(oms)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        assert result.abort_reason is BridgeAbortReason.MT5_REJECTION
        assert result.journal_entry.retcode == 10006

    def test_eligibility_recheck_blocks(self) -> None:
        decision, snap, _acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms)
        bad_acct = _account(already_in_trade=True, open_positions=1)
        result = integ.execute(
            decision,
            ExecutionBridgeContext(
                expected_input_hash=decision.input_hash,
                now=AS_OF,
                snapshot=snap,
                account=bad_acct,
                risk_allowed=True,
                execution_enabled=True,
                user_id=uuid4(),
            ),
        )
        assert result.abort_reason is BridgeAbortReason.ELIGIBILITY_FAILED
        assert oms.calls == []

    def test_journal_schema_fields(self) -> None:
        decision, snap, acct = _buy_decision()
        oms = RecordingOmsPort()
        integ = _bridge(oms, mode=ExecutionMode.LIVE)
        result = integ.execute(decision, _ctx(decision, snap, acct))
        row = result.journal_entry.to_dict()
        for key in (
            "decision_hash",
            "input_hash",
            "timestamp",
            "decision_action",
            "confidence",
            "quality",
            "approved_lots",
            "oms_status",
            "gateway_status",
            "mt5_ticket",
            "mt5_deal",
            "retcode",
            "comment",
            "latency_ms",
            "execution_result",
        ):
            assert key in row

    def test_decision_hash_deterministic(self) -> None:
        decision, _, _ = _buy_decision()
        assert compute_decision_hash(decision) == compute_decision_hash(decision)
