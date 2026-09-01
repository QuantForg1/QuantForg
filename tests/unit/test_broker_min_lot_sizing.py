"""Broker-aware min-lot sizing — never force min lot past the risk budget.

Does not send orders. Covers XAUUSD_i Weltrade-style specs (volume_min=0.01,
step=0.01, contract_size=100).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.ai_scalping.sizing import calculate_scalping_lots
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CODE_INVALID_BROKER_SPEC,
    CODE_MIN_LOT_CONSTRAINT,
    CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
    STATUS_CAPPED_MAX,
    STATUS_EXCEEDS_BUDGET,
    STATUS_INVALID_SPEC,
    STATUS_NORMALIZED_TO_MIN,
    STATUS_OK,
    normalize_lots_against_broker,
)
from app.domain.institutional_trading.operations.worker_runtime_state import (
    scheduler_is_stalled,
)
from tests.unit.test_autonomous_gold_execution import _ready

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_MIN = Decimal("0.01")
_STEP = Decimal("0.01")
_MAX = Decimal("10")
_CS = Decimal("100")
_EQUITY = Decimal("162.00")
_TICK_SIZE = Decimal("0.001")
_TICK_VALUE = Decimal("0.1")


def _norm(**overrides: object):
    base: dict[str, object] = {
        "calculated_lot": Decimal("0.0025"),
        "min_lot": _MIN,
        "lot_step": _STEP,
        "max_lot": _MAX,
        "equity": _EQUITY,
        "stop_distance": Decimal("4.00"),
        "contract_size": _CS,
        "risk_budget": Decimal("1.62"),
        "tick_size": _TICK_SIZE,
        "tick_value": _TICK_VALUE,
    }
    base.update(overrides)
    return normalize_lots_against_broker(**base)  # type: ignore[arg-type]


def _account(equity: Decimal = _EQUITY) -> AccountSnapshot:
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=equity,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=2000,
    )


def test_calculated_lot_below_min_uses_min_when_budget_allows() -> None:
    out = _norm(calculated_lot=Decimal("0.0025"), stop_distance=Decimal("4.00"))
    assert out.calculated_lot == Decimal("0.0025")
    assert out.broker_min_lot == _MIN
    assert out.normalized_lot == _MIN
    assert out.sizing_status == STATUS_NORMALIZED_TO_MIN
    assert out.block_reason is None
    assert out.estimated_risk_amount == Decimal("4.00")
    assert out.approved is True


def test_calculated_lot_exactly_at_broker_minimum() -> None:
    out = _norm(calculated_lot=_MIN, stop_distance=Decimal("4.00"))
    assert out.normalized_lot == _MIN
    assert out.sizing_status == STATUS_OK
    assert out.block_reason is None


def test_normalization_to_broker_lot_step() -> None:
    out = _norm(calculated_lot=Decimal("0.037"), stop_distance=Decimal("2.00"))
    assert out.normalized_lot == Decimal("0.03")
    assert out.broker_lot_step == _STEP
    assert out.sizing_status == STATUS_OK
    assert out.block_reason is None


def test_calculated_lot_above_minimum() -> None:
    out = _norm(calculated_lot=Decimal("0.05"), stop_distance=Decimal("2.00"))
    assert out.normalized_lot == Decimal("0.05")
    assert out.sizing_status == STATUS_OK
    assert out.approved is True


def test_minimum_lot_exceeding_risk_budget_is_blocked() -> None:
    # 0.01 * 100 * 12.00 = $12.00 → 7.41% of $162 > 5% hard max.
    out = _norm(calculated_lot=Decimal("0.002"), stop_distance=Decimal("12.00"))
    assert out.normalized_lot == Decimal("0")
    assert out.sizing_status == STATUS_EXCEEDS_BUDGET
    assert out.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET
    assert out.approved is False
    obs = out.to_observability()
    for key in (
        "calculated_lot",
        "broker_min_lot",
        "broker_lot_step",
        "broker_max_lot",
        "normalized_lot",
        "estimated_risk_amount",
        "risk_budget",
        "sizing_status",
        "block_reason",
    ):
        assert key in obs


def test_broker_max_lot_cap() -> None:
    out = _norm(calculated_lot=Decimal("25"), stop_distance=Decimal("1.00"))
    assert out.normalized_lot == _MAX
    assert out.broker_max_lot == _MAX
    assert out.sizing_status == STATUS_CAPPED_MAX
    assert out.block_reason is None


def test_zero_invalid_broker_specification_fail_closed() -> None:
    out = _norm(min_lot=Decimal("0"), lot_step=Decimal("0"))
    assert out.normalized_lot == Decimal("0")
    assert out.sizing_status == STATUS_INVALID_SPEC
    assert out.block_reason == CODE_INVALID_BROKER_SPEC
    out2 = _norm(min_lot=Decimal("1"), max_lot=Decimal("0.01"))
    assert out2.block_reason == CODE_INVALID_BROKER_SPEC


def test_xauusd_i_sizing_helper_and_scalping() -> None:
    sized = calculate_scalping_lots(
        equity=_EQUITY,
        stop_distance=Decimal("4.00"),
        risk_pct=Decimal("1.0"),
        contract_size=_CS,
        min_lot=_MIN,
        lot_step=_STEP,
    )
    assert sized.valid is True
    assert sized.lots == _MIN
    assert sized.broker_min_lot == _MIN
    assert sized.sizing_status == STATUS_NORMALIZED_TO_MIN
    assert sized.block_reason is None
    wide = calculate_scalping_lots(
        equity=_EQUITY,
        stop_distance=Decimal("12.00"),
        risk_pct=Decimal("1.0"),
        contract_size=_CS,
        min_lot=_MIN,
        lot_step=_STEP,
    )
    assert wide.valid is False
    assert wide.lots == Decimal("0")
    assert wide.block_reason == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET


def test_daily_loss_protection_outranks_min_lot() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            risk_eligible=True,
            approved_lots=_MIN,
            min_lot_infeasible=False,
            daily_loss_exceeded=True,
            risk_reasons=(f"daily loss exceeds {MAX_DAILY_LOSS_PCT}%",),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DAILY_LOSS_BLOCK"
    assert out.blocking_stage == "RISK"


def test_oms_rejection_does_not_claim_a_fill() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            oms_orders_allowed=False,
            optimizer_state="EXECUTE_NOW",
        )
    )
    assert out.may_submit_oms is False
    assert out.execution_readiness != "EXECUTION_READY"


def test_duplicate_order_protection_still_blocks_replay() -> None:
    from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
        may_add_scalping_trade,
    )

    decision = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="BUY",
        open_directions=("BUY",),
        entry=Decimal("4380.00"),
        open_entries=(Decimal("4380.00"),),
        min_entry_distance=Decimal("1.00"),
    )
    assert decision.allow is False
    assert "Duplicate" in decision.reason or "Identical" in decision.reason


def test_restart_recovery_does_not_treat_in_flight_cycle_as_stalled() -> None:
    import time

    now = time.monotonic()
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=0.0,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 120,
            running=True,
            cycle_started_mono=now - 30,
        )
        is False
    )


def test_risk_engine_xauusd_i_min_lot_within_budget() -> None:
    engine = RiskEngine()
    size = engine.size_position(
        equity=_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=Decimal("4.00"),
        atr=None,
        entry_price=Decimal("4380"),
        contract_size=_CS,
        risk_per_trade_pct=Decimal("1.0"),
    )
    assert size.approved_lots == _MIN
    assert size.capped is False
    assert size.block_reason is None


def test_risk_engine_labels_min_lot_exceeds_budget() -> None:
    engine = RiskEngine()
    result = engine.evaluate(
        RiskCheckInput(
            user_id=uuid4(),
            request_id="xau-min-lot-budget",
            symbol="XAUUSD_i",
            side="buy",
            requested_lots=Decimal("0.01"),
            stop_loss_distance=Decimal("12.00"),
            atr=Decimal("8.00"),
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=Decimal("4380"),
        ),
        account=_account(),
        positions=[],
    )
    assert result.decision is RiskDecision.REJECT
    assert result.approved_lots == Decimal("0")
    joined = " ".join(result.reasons)
    assert CODE_MIN_LOT_EXCEEDS_RISK_BUDGET in joined


def test_gold_contract_min_lot_exceeds_budget_does_not_submit() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            symbol="XAUUSD_i",
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=(
                CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
                "min_lot 0.01 needed_pct=7.41% > hard_max=5.0%",
            ),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET
    assert out.decision_state == DecisionState.CANDIDATE_BLOCK.value
    assert out.next_action == CandidateAction.WAIT_SAME_FOCUS.value


def test_institutional_equity_never_upsizes_to_min_lot() -> None:
    out = _norm(
        equity=Decimal("501.00"),
        calculated_lot=Decimal("0.002"),
        stop_distance=Decimal("4.00"),
        risk_budget=Decimal("5.01"),
    )
    assert out.normalized_lot == Decimal("0")
    assert out.block_reason == CODE_MIN_LOT_CONSTRAINT
    assert out.approved is False
