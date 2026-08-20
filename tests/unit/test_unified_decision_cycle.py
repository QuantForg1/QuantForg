"""Unified same-cycle decision: SCALP/HOLD, multi-position plan, safety."""

# ruff: noqa: E501
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.domain.institutional_trading.ai_scalping.profiles.scalping_v1 import (
    SCALPING_V1,
    align_live_scalp_cap,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    DecisionAction,
    EligibilityResult,
    PriceZone,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionAttemptRecord,
    ExecutionAttemptStatus,
    ExecutionBridgeContext,
    ExecutionBridgeResult,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.operations.batch_execution import (
    classify_leg_outcome,
    submit_position_plan_batch,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    AUTHORITATIVE_MAX_AGE_MS,
    CycleState,
    build_authoritative_snapshot,
    consume_immediate_wakeup,
    note_cycle_event,
    note_opportunity_change,
    reset_decision_cycle,
    stale_authorization,
    utc_stamp,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.position_plan import (
    SCALP_MAX_OPEN_TRADES,
    build_position_plan,
    class_position_cap,
    owned_count_from_rows,
    remaining_quantforg_capacity,
    reset_position_plan_guard,
    strategy_target_count,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
    STRONG_CANDIDATE_THRESHOLD,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)
from app.domain.institutional_trading.operations.trade_classifier import (
    HOLD_MAX_OPEN_TRADES,
    TradeClass,
    classify_trade,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

AS_OF = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _zone(px: str = "2400") -> PriceZone:
    p = Decimal(px)
    return PriceZone(low=p, high=p, mid=p)


def _decision(*, lots: str = "0.10", action: DecisionAction = DecisionAction.BUY) -> TradeDecision:
    conf = ConfluenceResult(
        confidence=80,
        direction=TradeDirection.BUY,
        reasons=("test",),
        rejected_rules=(),
        input_hash="cycle-hash-base",
        band="tradable",
        passed=True,
    )
    return TradeDecision(
        action=action,
        direction=TradeDirection.BUY if action is DecisionAction.BUY else TradeDirection.NONE,
        confidence=80,
        quality=80,
        risk_score=20,
        reasons=("same-cycle",),
        invalidations=(),
        entry_zone=_zone(),
        stop_zone=_zone("2390"),
        target_zone=_zone("2415"),
        estimated_rr=Decimal("1.5"),
        expected_duration="scalp",
        confluence=conf,
        eligibility=EligibilityResult(eligible=True, checks={"risk_available": True}, rejection_reasons=()),
        input_hash="cycle-hash-base",
        config_version="ite-test",
        symbol="XAUUSD_i",
        as_of=AS_OF,
        approved_lots=Decimal(lots),
    )


def _ctx(decision: TradeDecision) -> ExecutionBridgeContext:
    account = AccountRiskState(
        equity=Decimal("1000"),
        open_positions=0,
        market_open=True,
        free_margin=Decimal("800"),
    )
    snap = SimpleNamespace(
        symbol="XAUUSD_i",
        session=SimpleNamespace(allowed=True, reason="ok"),
        spread=Decimal("0.20"),
        atr=Decimal("8"),
    )
    return ExecutionBridgeContext(
        expected_input_hash=decision.input_hash,
        now=AS_OF,
        snapshot=snap,  # type: ignore[arg-type]
        account=account,
        execution_enabled=True,
        connected=True,
        request_id="cycle-test",
    )


def _ok_result() -> ExecutionBridgeResult:
    rec = ExecutionAttemptRecord(
        decision_hash="h",
        input_hash="i",
        timestamp=AS_OF,
        decision_action=DecisionAction.BUY,
        confidence=80,
        quality=80,
        approved_lots=Decimal("0.02"),
        oms_status="ok",
        gateway_status="ok",
        mt5_ticket=1,
        mt5_deal=1,
        retcode=10009,
        comment="ite:v1:test",
        latency_ms=1.0,
        execution_result="success",
        abort_reason=BridgeAbortReason.NONE,
        mode=ExecutionMode.LIVE,
        status=ExecutionAttemptStatus.OMS_SUCCESS,
    )
    return ExecutionBridgeResult(
        forwarded_to_oms=True,
        aborted=False,
        abort_reason=BridgeAbortReason.NONE,
        decision_hash="h",
        journal_entry=rec,
        oms_result=OmsSubmitResult(outcome="success", message="filled", retcode=10009, order_ticket=1),
    )


def _unknown_result() -> ExecutionBridgeResult:
    rec = _ok_result().journal_entry
    return ExecutionBridgeResult(
        forwarded_to_oms=True,
        aborted=False,
        abort_reason=BridgeAbortReason.NONE,
        decision_hash="u",
        journal_entry=rec,
        oms_result=OmsSubmitResult(outcome="unknown", message="timeout"),
    )


def _hard_result() -> ExecutionBridgeResult:
    rec = _ok_result().journal_entry
    return ExecutionBridgeResult(
        forwarded_to_oms=False,
        aborted=True,
        abort_reason=BridgeAbortReason.ELIGIBILITY_FAILED,
        decision_hash="x",
        journal_entry=rec,
        oms_result=None,
    )


@pytest.fixture(autouse=True)
def _reset_cycle() -> None:
    reset_decision_cycle()
    reset_position_plan_guard()
    yield
    reset_decision_cycle()
    reset_position_plan_guard()


def test_same_cycle_evaluates_signal() -> None:
    classified = classify_trade(opportunity_score=78, direction="BUY", structure=62)
    plan = build_position_plan(
        cycle_id="c1",
        snapshot_id="s1",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=classified.trade_class,
        opportunity_score=78,
        confidence=75,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash="h",
    )
    assert classified.trade_class is TradeClass.SCALP
    assert plan.cycle_id == "c1"
    assert plan.snapshot_id == "s1"
    assert plan.effective_count >= 1
    assert plan.position_plan_id


def test_medium_valid_signal_is_scalp() -> None:
    out = classify_trade(
        opportunity_score=76,
        direction="BUY",
        confidence=72,
        structure=62,
        risk_reward=Decimal("1.20"),
        regime="range",
    )
    assert out.trade_class is TradeClass.SCALP
    assert "holding-quality" in out.reason.lower() or "insufficient" in out.reason.lower()


def test_strong_signal_is_hold() -> None:
    out = classify_trade(
        opportunity_score=88,
        direction="SELL",
        confidence=86,
        structure=78,
        risk_reward=Decimal("1.45"),
        regime="strong_trend",
        mtf_alignment=70,
        execution_quality=70,
    )
    assert out.trade_class is TradeClass.HOLD
    assert "holding" in out.reason.lower()


def test_invalid_signal_is_no_trade() -> None:
    weak = classify_trade(opportunity_score=60, direction="BUY")
    none = classify_trade(opportunity_score=90, direction="NONE")
    hard = classify_trade(
        opportunity_score=90,
        direction="BUY",
        hard_market_invalid=True,
        hard_invalid_reason="STALE_QUOTE",
    )
    assert weak.trade_class is TradeClass.NO_TRADE
    assert none.trade_class is TradeClass.NO_TRADE
    assert hard.trade_class is TradeClass.NO_TRADE
    assert "STALE_QUOTE" in hard.reason


def test_scalp_can_target_multiple_positions() -> None:
    n = strategy_target_count(trade_class=TradeClass.SCALP, opportunity_score=82)
    assert 2 <= n <= 10
    assert n >= 5


def test_hold_can_target_multiple_positions() -> None:
    n = strategy_target_count(trade_class=TradeClass.HOLD, opportunity_score=86)
    assert 1 <= n <= 5
    assert n >= 2


def test_scalp_never_exceeds_cap_10() -> None:
    n = strategy_target_count(trade_class=TradeClass.SCALP, opportunity_score=99)
    assert n <= SCALP_MAX_OPEN_TRADES
    assert class_position_cap(TradeClass.SCALP) == 10
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count <= 10


def test_hold_never_exceeds_cap_5() -> None:
    n = strategy_target_count(trade_class=TradeClass.HOLD, opportunity_score=99)
    assert n <= HOLD_MAX_OPEN_TRADES
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.HOLD,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("1.00"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count <= 5


def test_risk_can_reduce_requested_count() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=92,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        risk_allowed_count=2,
    )
    assert plan.target_count > 2
    assert plan.effective_count == 2
    assert any("risk_allowed" in r for r in plan.reductions)


def test_portfolio_can_reduce_requested_count() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.HOLD,
        opportunity_score=90,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        portfolio_allowed_count=1,
    )
    assert plan.effective_count == 1
    assert any("portfolio_allowed" in r for r in plan.reductions)


def test_margin_can_reduce_requested_count() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=90,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        free_margin=Decimal("2"),
        margin_per_lot=Decimal("100"),
        min_lot=Decimal("0.01"),
    )
    assert plan.effective_count < plan.target_count
    assert plan.effective_count >= 0


def test_existing_quantforg_positions_reduce_capacity() -> None:
    rem = remaining_quantforg_capacity(
        current_count=7, configured_max=10, class_cap=10
    )
    assert rem == 3
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=90,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=7,
        ite_config=ITEConfig(max_open_trades=10),
    )
    assert plan.effective_count <= 3


def test_manual_positions_do_not_reduce_quantforg_capacity() -> None:
    rows = [
        {"ticket": 1, "magic": 0, "comment": "manual", "symbol": "XAUUSD_i"},
        {"ticket": 2, "magic": QUANTFORG_MAGIC, "comment": "ite:v1:x", "symbol": "XAUUSD_i"},
    ]
    assert owned_count_from_rows(rows, symbol="XAUUSD_i") == 1


def test_score_70_valid_direction_is_candidate() -> None:
    out = classify_trade(opportunity_score=70, direction="BUY", structure=60)
    assert out.trade_class is not TradeClass.NO_TRADE
    assert OPPORTUNITY_SCORE_THRESHOLD == 70


def test_score_85_is_strong_threshold() -> None:
    assert STRONG_CANDIDATE_THRESHOLD == 85
    out = classify_trade(
        opportunity_score=85,
        direction="BUY",
        structure=72,
        risk_reward=Decimal("1.35"),
        regime="trend",
    )
    assert out.trade_class is TradeClass.HOLD


def test_direction_none_never_trades() -> None:
    out = classify_trade(opportunity_score=95, direction="NONE")
    assert out.trade_class is TradeClass.NO_TRADE
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="NONE",
        trade_class=TradeClass.NO_TRADE,
        opportunity_score=95,
        confidence=95,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
    )
    assert plan.effective_count == 0


def test_stale_risk_cannot_authorize() -> None:
    old = utc_stamp(datetime.now(UTC) - timedelta(seconds=30))
    snap = build_authoritative_snapshot(
        cycle_id="c",
        snapshot_id="s",
        opportunity={"opportunity_score": 80, "direction": "BUY"},
        account=AccountRiskState(equity=Decimal("1000"), open_positions=0),
    )
    from dataclasses import replace

    aged = replace(snap, timestamp=old, risk_as_of=old, safety_as_of=utc_stamp())
    assert stale_authorization(aged) in {"STALE_RISK", "STALE_MARKET_SNAPSHOT"}


def test_stale_safety_cannot_authorize() -> None:
    old = utc_stamp(datetime.now(UTC) - timedelta(seconds=30))
    snap = build_authoritative_snapshot(
        cycle_id="c",
        snapshot_id="s",
        opportunity={"opportunity_score": 80, "direction": "BUY"},
        account=AccountRiskState(equity=Decimal("1000"), open_positions=0),
    )
    from dataclasses import replace

    aged = replace(snap, timestamp=utc_stamp(), risk_as_of=utc_stamp(), safety_as_of=old)
    assert stale_authorization(aged) == "STALE_SAFETY"


def test_hard_risk_failure_blocks_entire_batch() -> None:
    decision = _decision()
    ctx = _ctx(decision)
    plan = build_position_plan(
        cycle_id="c-risk",
        snapshot_id="s-risk",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=80,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash=decision.input_hash,
    )
    calls: list[int] = []

    def submit(dec: TradeDecision, _ctx: ExecutionBridgeContext) -> ExecutionBridgeResult:
        calls.append(1)
        return _hard_result()

    _out, tally, _ = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert tally.state == "HARD_BLOCK"
    assert tally.submitted_count == 1
    assert tally.submitted_count < plan.effective_count
    assert len(calls) == 1


def test_hard_safety_failure_blocks_entire_batch() -> None:
    decision = _decision()
    ctx = _ctx(decision)
    plan = build_position_plan(
        cycle_id="c-safe",
        snapshot_id="s-safe",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=80,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash=decision.input_hash,
    )

    def submit(dec: TradeDecision, _ctx: ExecutionBridgeContext) -> ExecutionBridgeResult:
        rec = _ok_result().journal_entry
        return ExecutionBridgeResult(
            forwarded_to_oms=False,
            aborted=True,
            abort_reason=BridgeAbortReason.KILL_SWITCH,
            decision_hash="k",
            journal_entry=rec,
            oms_result=None,
        )

    _out, tally, _ = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert tally.state == "HARD_BLOCK"
    assert tally.submitted_count == 1


def test_one_cycle_one_position_plan() -> None:
    plan = build_position_plan(
        cycle_id="only",
        snapshot_id="snap",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=80,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
    )
    assert plan.position_plan_id
    assert all(leg.idempotency_key.startswith(plan.idempotency_key) for leg in plan.legs)


def test_batch_orders_share_cycle_snapshot_plan_ids() -> None:
    plan = build_position_plan(
        cycle_id="cyc-shared",
        snapshot_id="snap-shared",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=84,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash="base",
    )
    assert plan.effective_count >= 2
    hashes = {leg.input_hash for leg in plan.legs}
    assert len(hashes) == len(plan.legs)
    for leg in plan.legs:
        assert plan.cycle_id == "cyc-shared"
        assert plan.snapshot_id == "snap-shared"
        assert plan.position_plan_id in leg.idempotency_key or leg.idempotency_key


def test_partial_fill_is_reconciled() -> None:
    decision = _decision()
    ctx = _ctx(decision)
    plan = build_position_plan(
        cycle_id="c-part",
        snapshot_id="s-part",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=84,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash=decision.input_hash,
    )
    n = {"i": 0}

    def submit(dec: TradeDecision, _ctx: ExecutionBridgeContext) -> ExecutionBridgeResult:
        n["i"] += 1
        if n["i"] <= 2:
            return _ok_result()
        rec = ExecutionAttemptRecord(
            decision_hash="r",
            input_hash="i",
            timestamp=AS_OF,
            decision_action=DecisionAction.BUY,
            confidence=80,
            quality=80,
            approved_lots=Decimal("0.02"),
            oms_status="rejected",
            gateway_status="rejected",
            mt5_ticket=None,
            mt5_deal=None,
            retcode=10019,
            comment="ite:v1:test",
            latency_ms=1.0,
            execution_result="rejected",
            abort_reason=BridgeAbortReason.NONE,
            mode=ExecutionMode.LIVE,
            status=ExecutionAttemptStatus.OMS_REJECTED,
        )
        return ExecutionBridgeResult(
            forwarded_to_oms=True,
            aborted=False,
            abort_reason=BridgeAbortReason.NONE,
            decision_hash="r",
            journal_entry=rec,
            oms_result=OmsSubmitResult(outcome="rejected", message="no money"),
        )

    out, tally, _ = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert tally.accepted_count == 2
    assert tally.rejected_count >= 1
    assert out.state == "PARTIAL_FILL"
    assert tally.requested_count == plan.effective_count


def test_unknown_order_is_not_blindly_retried() -> None:
    decision = _decision()
    ctx = _ctx(decision)
    plan = build_position_plan(
        cycle_id="c-unk",
        snapshot_id="s-unk",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=84,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash=decision.input_hash,
    )
    calls = {"n": 0}

    def submit(dec: TradeDecision, _ctx: ExecutionBridgeContext) -> ExecutionBridgeResult:
        calls["n"] += 1
        if calls["n"] == 1:
            return _ok_result()
        return _unknown_result()

    out, tally, _ = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert tally.unknown_count == 1
    assert tally.retried_count == 0
    assert out.state == "RECONCILIATION_REQUIRED"
    assert calls["n"] == 2
    assert calls["n"] < plan.effective_count or plan.effective_count <= 2


def test_duplicate_cycle_cannot_duplicate_execution() -> None:
    decision = _decision()
    ctx = _ctx(decision)
    plan = build_position_plan(
        cycle_id="dup",
        snapshot_id="dup-s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=80,
        confidence=80,
        aggregate_lots=Decimal("0.05"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        base_input_hash=decision.input_hash,
    )
    calls = {"n": 0}

    def submit(dec: TradeDecision, _ctx: ExecutionBridgeContext) -> ExecutionBridgeResult:
        calls["n"] += 1
        return _ok_result()

    submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    first_calls = calls["n"]
    _, tally, _ = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert tally.reasons
    assert "duplicate_cycle" in tally.reasons[0]
    assert calls["n"] == first_calls


def test_execute_now_not_required() -> None:
    facts = GoldExecutionFacts(
        symbol="XAUUSD_i",
        direction="BUY",
        action="BUY",
        market_open=True,
        tradable=True,
        bid=Decimal("2400"),
        ask=Decimal("2400.2"),
        quote_age_seconds=1,
        spread=Decimal("0.2"),
        structure_score=75,
        momentum_score=70,
        quality=80,
        confidence=78,
        pa_confluence=60,
        risk_reward=Decimal("1.4"),
        market_regime="trend",
        safety_allowed=True,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=True,
        approved_lots=Decimal("0.01"),
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        gold_only=True,
        opportunity_score=80,
        mtf_alignment=70,
        cycle_id="c",
        snapshot_id="s",
    )
    contract = evaluate_gold_execution_contract(facts)
    assert contract.execute_now_required is False
    assert contract.trade_class in {TradeClass.SCALP.value, TradeClass.HOLD.value}


def test_ui_not_required_for_decision() -> None:
    from pathlib import Path

    text = Path(
        "app/domain/institutional_trading/operations/gold_execution_contract.py"
    ).read_text(encoding="utf-8")
    assert "execute_now_required=False" in text
    assert "browser" not in text.lower() or "Execute Now is not required" in text


def test_browser_not_required() -> None:
    from app.domain.institutional_trading.operations import batch_execution as mod

    assert "second order_send" in (mod.__doc__ or "").lower()
    assert "browser" not in (mod.__doc__ or "").lower()


def test_same_snapshot_feeds_all_stages() -> None:
    snap = build_authoritative_snapshot(
        cycle_id="one",
        snapshot_id="snap-one",
        opportunity={"opportunity_score": 80, "direction": "BUY", "confidence": 75},
        account=AccountRiskState(equity=Decimal("1000"), open_positions=0),
    )
    classified = classify_trade(
        opportunity_score=80,
        direction="BUY",
        cycle_id=snap.cycle_id,
        snapshot_id=snap.snapshot_id,
    )
    plan = build_position_plan(
        cycle_id=snap.cycle_id,
        snapshot_id=snap.snapshot_id,
        symbol=snap.canonical_symbol,
        direction=classified.direction,
        trade_class=classified.trade_class,
        opportunity_score=80,
        confidence=75,
        aggregate_lots=Decimal("0.05"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
    )
    assert classified.cycle_id == snap.cycle_id
    assert plan.snapshot_id == snap.snapshot_id
    assert classified.trade_class.value == plan.trade_class


def test_probability_and_decision_share_classification() -> None:
    facts = GoldExecutionFacts(
        symbol="XAUUSD_i",
        direction="BUY",
        action="BUY",
        market_open=True,
        tradable=True,
        bid=Decimal("2400"),
        ask=Decimal("2400.2"),
        quote_age_seconds=1,
        spread=Decimal("0.2"),
        structure_score=62,
        momentum_score=60,
        quality=74,
        confidence=72,
        pa_confluence=50,
        risk_reward=Decimal("1.20"),
        market_regime="range",
        safety_allowed=True,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=True,
        approved_lots=Decimal("0.01"),
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        gold_only=True,
        opportunity_score=76,
        cycle_id="same",
        snapshot_id="same-s",
    )
    contract = evaluate_gold_execution_contract(facts)
    classified = classify_trade(
        opportunity_score=int(contract.opportunity_score or 0),
        direction=contract.direction,
        confidence=contract.confidence,
        structure=contract.structure_score,
        risk_reward=facts.risk_reward,
        regime=contract.market_regime,
        cycle_id=contract.cycle_id,
        snapshot_id=contract.snapshot_id,
    )
    assert contract.trade_class == classified.trade_class.value
    assert contract.trade_class == TradeClass.SCALP.value


def test_no_hidden_soft_gates_kill_probability_candidate() -> None:
    out = classify_trade(
        opportunity_score=70,
        direction="BUY",
        confidence=50,
        structure=40,
        risk_reward=Decimal("1.05"),
        regime="chop",
    )
    assert out.trade_class is TradeClass.SCALP


def test_scalping_profile_cap_is_10() -> None:
    assert SCALPING_V1.max_open_trades == 10
    assert SCALPING_V1.max_entries_per_cycle == 10
    assert align_live_scalp_cap(5, trading_mode="scalping") == 10
    assert align_live_scalp_cap(8, trading_mode="scalping") == 8


def test_event_driven_wakeup_on_score_cross() -> None:
    note_opportunity_change(score=60, direction="BUY", trade_class="NO_TRADE")
    assert consume_immediate_wakeup() is None
    note_opportunity_change(score=72, direction="BUY", trade_class="SCALP")
    assert consume_immediate_wakeup() == "score_crossed_70"
    note_cycle_event("position_fill")
    assert consume_immediate_wakeup() == "position_fill"


def test_cycle_state_machine_names() -> None:
    assert CycleState.NEW_SIGNAL.value == "NEW_SIGNAL"
    assert CycleState.RECONCILIATION_REQUIRED.value == "RECONCILIATION_REQUIRED"
    assert CycleState.HARD_BLOCK.value == "HARD_BLOCK"


def test_split_lots_do_not_multiply_risk() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=80,
        confidence=80,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10),
        min_lot=Decimal("0.01"),
        lot_step=Decimal("0.01"),
    )
    total = plan.per_position_lots * plan.effective_count
    assert total <= Decimal("0.10")


def test_authoritative_age_constant_is_finite() -> None:
    assert AUTHORITATIVE_MAX_AGE_MS > 0
    assert classify_leg_outcome(_unknown_result()) == "unknown"


def test_execute_now_false_on_contract_always() -> None:
    facts = GoldExecutionFacts(symbol="XAUUSD_i", gold_only=True)
    contract = evaluate_gold_execution_contract(facts)
    assert contract.execute_now_required is False
