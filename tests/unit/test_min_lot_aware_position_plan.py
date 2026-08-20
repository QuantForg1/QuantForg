"""Min-lot-aware gold position plans — reduce count, never upsize, never live-send."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

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
    submit_position_plan_batch,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    build_authoritative_snapshot,
)
from app.domain.institutional_trading.operations.position_plan import (
    build_position_plan,
    owned_count_from_rows,
    reset_position_plan_guard,
    split_aggregate_lots,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)
from app.domain.institutional_trading.operations.trade_classifier import TradeClass

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

AS_OF = datetime(2026, 8, 20, 13, 0, tzinfo=UTC)
MIN = Decimal("0.01")
STEP = Decimal("0.01")
MAX = Decimal("10")


def _plan(
    *,
    lots: str,
    score: int = 90,
    trade_class: TradeClass = TradeClass.SCALP,
    direction: str = "BUY",
    current: int = 0,
    risk_n: int | None = None,
    portfolio_n: int | None = None,
    broker_n: int | None = None,
    free_margin: Decimal | None = None,
    margin_per_lot: Decimal | None = None,
    min_lot: Decimal = MIN,
    lot_step: Decimal = STEP,
    max_lot: Decimal = MAX,
    cycle_id: str = "cycle-minlot",
) -> object:
    return build_position_plan(
        cycle_id=cycle_id,
        snapshot_id="snap-minlot",
        symbol="XAUUSD_i",
        direction=direction,
        trade_class=trade_class,
        opportunity_score=score,
        confidence=score,
        aggregate_lots=Decimal(lots),
        current_quantforg_count=current,
        ite_config=ITEConfig(max_open_trades=10),
        risk_allowed_count=risk_n,
        portfolio_allowed_count=portfolio_n,
        broker_allowed_count=broker_n,
        free_margin=free_margin,
        margin_per_lot=margin_per_lot,
        min_lot=min_lot,
        lot_step=lot_step,
        max_lot=max_lot,
        base_input_hash="minlot-hash",
    )


def _zone(px: str = "2400") -> PriceZone:
    p = Decimal(px)
    return PriceZone(low=p, high=p, mid=p)


def _decision(*, lots: str = "0.01") -> TradeDecision:
    conf = ConfluenceResult(
        confidence=80,
        direction=TradeDirection.BUY,
        reasons=("test",),
        rejected_rules=(),
        input_hash="minlot-hash",
        band="tradable",
        passed=True,
    )
    return TradeDecision(
        action=DecisionAction.BUY,
        direction=TradeDirection.BUY,
        confidence=80,
        quality=80,
        risk_score=20,
        reasons=("min-lot-plan",),
        invalidations=(),
        entry_zone=_zone(),
        stop_zone=_zone("2390"),
        target_zone=_zone("2415"),
        estimated_rr=Decimal("1.5"),
        expected_duration="scalp",
        confluence=conf,
        eligibility=EligibilityResult(
            eligible=True, checks={"risk_available": True}, rejection_reasons=()
        ),
        input_hash="minlot-hash",
        config_version="ite-test",
        symbol="XAUUSD_i",
        as_of=AS_OF,
        approved_lots=Decimal(lots),
        id=uuid4(),
    )


def _ok_result() -> ExecutionBridgeResult:
    rec = ExecutionAttemptRecord(
        decision_hash="h",
        input_hash="minlot-hash",
        timestamp=AS_OF,
        decision_action=DecisionAction.BUY,
        confidence=80,
        quality=80,
        approved_lots=Decimal("0.01"),
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
        oms_result=OmsSubmitResult(
            outcome="success", message="filled", retcode=10009, order_ticket=1
        ),
    )


@pytest.fixture(autouse=True)
def _reset_plan_guard() -> None:
    reset_position_plan_guard()
    yield
    reset_position_plan_guard()


def test_approved_lots_below_min_lot_is_genuine_block() -> None:
    plan = _plan(lots="0.004")
    assert plan.effective_count == 0
    assert plan.legs == ()
    assert plan.min_lot_constraint_reason is not None
    assert "MIN_LOT_CONSTRAINT" in plan.min_lot_constraint_reason
    assert plan.state == "SOFT_REJECT"


def test_approved_lots_exactly_min_lot_allows_one_position() -> None:
    plan = _plan(lots="0.01", score=92)
    assert plan.requested_count >= 2
    assert plan.effective_count == 1
    assert plan.per_position_lots == MIN
    assert plan.min_lot_constraint_reason is None
    assert plan.state == "POSITION_PLAN_READY"


def test_aggregate_lots_reduce_count_instead_of_rejecting() -> None:
    """0.03 approved / requested 6 → 3 x 0.01, still executable."""
    n, per = split_aggregate_lots(
        aggregate_lots=Decimal("0.03"),
        count=6,
        min_lot=MIN,
        lot_step=STEP,
    )
    assert n == 3
    assert per == MIN
    plan = _plan(lots="0.03", score=92)
    assert plan.requested_count > 3
    assert plan.effective_count == 3
    assert plan.per_position_lots == MIN
    assert plan.min_lot_constraint_reason is None


def test_five_cents_lots_permit_five_min_lot_positions() -> None:
    plan = _plan(lots="0.05", score=92)
    assert plan.effective_count == 5
    assert plan.per_position_lots == MIN
    assert plan.per_position_lots * plan.effective_count == Decimal("0.05")


def test_lot_step_normalization_rounds_down() -> None:
    n, per = split_aggregate_lots(
        aggregate_lots=Decimal("0.035"),
        count=5,
        min_lot=MIN,
        lot_step=STEP,
    )
    assert per == MIN
    assert n == 3
    assert per * n <= Decimal("0.035")


def test_max_lot_caps_per_position_without_upsizing() -> None:
    plan = _plan(lots="1.00", score=99, max_lot=Decimal("0.05"))
    assert plan.effective_count >= 1
    assert plan.per_position_lots <= Decimal("0.05")
    assert plan.per_position_lots * plan.effective_count <= Decimal("1.00")


def test_risk_reduction_happens_before_min_lot_failure() -> None:
    plan = _plan(lots="0.10", score=92, risk_n=2)
    assert plan.effective_count == 2
    assert plan.min_lot_constraint_reason is None
    assert any("risk_allowed" in r for r in plan.reductions)


def test_portfolio_reduction_keeps_candidate() -> None:
    plan = _plan(lots="0.10", score=90, trade_class=TradeClass.HOLD, portfolio_n=1)
    assert plan.effective_count == 1
    assert plan.min_lot_constraint_reason is None


def test_margin_reduction_keeps_candidate_when_one_leg_fits() -> None:
    plan = _plan(
        lots="0.10",
        score=90,
        free_margin=Decimal("5"),
        margin_per_lot=Decimal("400"),
    )
    assert plan.effective_count >= 1
    assert plan.per_position_lots >= MIN
    assert plan.min_lot_constraint_reason is None
    assert plan.margin_available == "5"
    assert plan.margin_required is not None


def test_existing_quantforg_positions_reduce_count() -> None:
    plan = _plan(lots="0.10", score=90, current=7)
    assert plan.effective_count <= 3
    assert plan.remaining_capacity == 3


def test_manual_positions_do_not_reduce_count() -> None:
    rows = [
        {"ticket": 1, "magic": 0, "comment": "manual", "symbol": "XAUUSD_i"},
        {"ticket": 2, "magic": QUANTFORG_MAGIC, "comment": "ite:v1:x",
         "symbol": "XAUUSD_i"},
    ]
    assert owned_count_from_rows(rows, symbol="XAUUSD_i") == 1
    snap = build_authoritative_snapshot(
        cycle_id="c-manual",
        snapshot_id="s-manual",
        opportunity={"opportunity_score": 80, "direction": "BUY"},
        account=AccountRiskState(equity=Decimal("1000"), open_positions=5),
        quantforg_count=owned_count_from_rows(rows, symbol="XAUUSD_i"),
    )
    assert snap.existing_quantforg_positions == 1
    omitted = build_authoritative_snapshot(
        cycle_id="c-omit",
        snapshot_id="s-omit",
        opportunity={"opportunity_score": 80, "direction": "BUY"},
        account=AccountRiskState(equity=Decimal("1000"), open_positions=5),
    )
    assert omitted.existing_quantforg_positions == 0


def test_candidate_remains_candidate_after_count_reduction() -> None:
    plan = _plan(lots="0.01", score=88)
    payload = plan.to_dict()
    assert payload["requested_count"] == plan.target_count
    assert payload["effective_count"] == 1
    assert payload["trade_class"] != TradeClass.NO_TRADE.value
    assert payload["min_lot_constraint_reason"] is None
    assert payload["broker_min_lot"] == "0.01"
    assert payload["approved_lots"] == "0.01"


def test_oms_receives_single_leg_plan_when_only_one_position_fits() -> None:
    decision = _decision(lots="0.01")
    account = AccountRiskState(
        equity=Decimal("1000"),
        open_positions=0,
        market_open=True,
        free_margin=Decimal("800"),
    )
    ctx = ExecutionBridgeContext(
        expected_input_hash=decision.input_hash,
        now=AS_OF,
        snapshot=SimpleNamespace(  # type: ignore[arg-type]
            symbol="XAUUSD_i",
            session=SimpleNamespace(allowed=True, reason="ok"),
            spread=Decimal("0.20"),
            atr=Decimal("8"),
        ),
        account=account,
        execution_enabled=True,
        connected=True,
        request_id="minlot-oms",
    )
    plan = _plan(lots="0.01", score=90, cycle_id="cycle-oms-one")
    assert plan.effective_count == 1
    calls: list[Decimal] = []

    def submit(
        dec: TradeDecision, _ctx: ExecutionBridgeContext
    ) -> ExecutionBridgeResult:
        calls.append(plan.per_position_lots)
        assert dec.action is DecisionAction.BUY
        return _ok_result()

    out, tally, last = submit_position_plan_batch(
        plan=plan, decision=decision, context=ctx, submit=submit, trade_class="SCALP"
    )
    assert len(calls) == 1
    assert calls[0] == MIN
    assert tally.requested_count == 1
    assert tally.accepted_count == 1
    assert last is not None
    assert last.forwarded_to_oms is True
    assert out.effective_count == 1


def test_no_risk_upsize_when_count_is_reduced() -> None:
    plan = _plan(lots="0.01", score=92)
    assert plan.per_position_lots * plan.effective_count <= Decimal("0.01")
    fat = _plan(lots="0.05", score=92)
    assert fat.per_position_lots * fat.effective_count <= Decimal("0.05")


def test_no_forced_trade_on_no_trade_or_none_direction() -> None:
    none = _plan(lots="0.10", direction="NONE", trade_class=TradeClass.NO_TRADE)
    assert none.effective_count == 0
    assert none.legs == ()
    assert none.min_lot_constraint_reason is None


def test_no_live_order_in_min_lot_suite() -> None:
    """This suite never calls order_send / gateway submit."""
    plan = _plan(lots="0.01")
    assert "order_send" not in plan.to_dict()
    n, per = split_aggregate_lots(
        aggregate_lots=Decimal("0.01"), count=4, min_lot=MIN, lot_step=STEP
    )
    assert (n, per) == (1, MIN)
