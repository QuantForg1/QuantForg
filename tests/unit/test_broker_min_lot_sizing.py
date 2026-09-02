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
    CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
    CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED,
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
    out = _norm(
        calculated_lot=Decimal("0.0025"),
        stop_distance=Decimal("4.00"),
        risk_budget=Decimal("5.00"),
        min_planned_risk=Decimal("0"),
        remaining_portfolio_risk=Decimal("5.00"),
    )
    assert out.calculated_lot == Decimal("0.0025")
    assert out.broker_min_lot == _MIN
    assert out.normalized_lot == _MIN
    assert out.sizing_status == STATUS_NORMALIZED_TO_MIN
    assert out.block_reason is None
    assert out.estimated_risk_amount == Decimal("4.00")
    assert out.approved is True


def test_minimum_lot_exceeding_remaining_portfolio_is_blocked() -> None:
    out = _norm(
        calculated_lot=Decimal("0.0025"),
        stop_distance=Decimal("4.00"),
        remaining_portfolio_risk=Decimal("1.62"),
    )
    assert out.normalized_lot == Decimal("0")
    assert out.sizing_status == STATUS_EXCEEDS_BUDGET
    assert out.block_reason == CODE_REMAINING_PORTFOLIO_RISK_EXCEEDED
    assert out.approved is False


def test_calculated_lot_exactly_at_broker_minimum() -> None:
    out = _norm(
        calculated_lot=_MIN,
        stop_distance=Decimal("4.00"),
        min_planned_risk=Decimal("0"),
        remaining_portfolio_risk=Decimal("5.00"),
    )
    assert out.normalized_lot == _MIN
    assert out.sizing_status == STATUS_OK
    assert out.block_reason is None


def test_normalization_to_broker_lot_step() -> None:
    out = _norm(
        calculated_lot=Decimal("0.037"),
        stop_distance=Decimal("2.00"),
        min_planned_risk=Decimal("0"),
        remaining_portfolio_risk=Decimal("30.00"),
    )
    assert out.normalized_lot == Decimal("0.03")
    assert out.broker_lot_step == _STEP
    assert out.sizing_status == STATUS_OK
    assert out.block_reason is None


def test_calculated_lot_above_minimum() -> None:
    out = _norm(
        calculated_lot=Decimal("0.05"),
        stop_distance=Decimal("2.00"),
        min_planned_risk=Decimal("0"),
        remaining_portfolio_risk=Decimal("30.00"),
    )
    assert out.normalized_lot == Decimal("0.05")
    assert out.sizing_status == STATUS_OK
    assert out.approved is True


def test_minimum_lot_exceeding_risk_budget_is_blocked() -> None:
    # 0.01 * 100 * 150.00 = $150.00 — above the $20 per-trade planned SL cap.
    out = _norm(calculated_lot=Decimal("0.002"), stop_distance=Decimal("150.00"))
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
    out = _norm(
        calculated_lot=Decimal("25"),
        stop_distance=Decimal("1.00"),
        equity=Decimal("100000"),
        remaining_portfolio_risk=Decimal("2000"),
        min_planned_risk=Decimal("0"),
        max_planned_sl_risk=Decimal("0"),
    )
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
    assert sized.lots > _MIN
    assert sized.estimated_risk_amount > Decimal("6.00")
    assert sized.broker_min_lot == _MIN
    assert sized.block_reason is None
    wide = calculate_scalping_lots(
        equity=_EQUITY,
        stop_distance=Decimal("150.00"),
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
    assert size.approved_lots == Decimal("0.02")
    assert size.dollar_risk == Decimal("8.00")
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
            stop_loss_distance=Decimal("150.00"),
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


def test_institutional_equity_upsizes_to_meet_min_planned_risk() -> None:
    out = _norm(
        equity=Decimal("501.00"),
        calculated_lot=Decimal("0.002"),
        stop_distance=Decimal("4.00"),
        risk_budget=Decimal("7.00"),
        remaining_portfolio_risk=Decimal("30.00"),
    )
    assert out.normalized_lot > Decimal("0.01")
    assert out.estimated_risk_amount > Decimal("6.00")
    assert out.approved is True


def test_calculated_lot_0_001_normalizes_to_broker_min_when_budget_allows() -> None:
    out = _norm(
        calculated_lot=Decimal("0.001"),
        stop_distance=Decimal("4.00"),
        risk_budget=Decimal("5.00"),
        min_planned_risk=Decimal("0"),
        remaining_portfolio_risk=Decimal("5.00"),
    )
    assert out.normalized_lot == _MIN
    assert out.broker_min_lot == Decimal("0.01")
    assert out.sizing_status == STATUS_NORMALIZED_TO_MIN
    assert out.approved is True


def test_setup_tradeability_tight_stop_is_tradeable() -> None:
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        TRADEABLE,
        evaluate_setup_tradeability,
    )

    out = evaluate_setup_tradeability(
        stop_distance=Decimal("4.00"),
        equity=_EQUITY,
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=_MAX,
        contract_size=_CS,
    )
    assert out.tradeability == TRADEABLE
    assert out.feasibility.infeasible is False
    assert out.estimated_risk_at_min_lot == Decimal("4.00")
    assert out.maximum_tradeable_stop_distance == Decimal("129.6")
    assert out.feasibility.stop_changed is False


def test_setup_tradeability_wide_stop_is_not_tradeable() -> None:
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        NOT_TRADEABLE,
        evaluate_setup_tradeability,
    )

    out = evaluate_setup_tradeability(
        stop_distance=Decimal("150.00"),
        equity=_EQUITY,
        min_lot=_MIN,
        lot_step=_STEP,
        max_lot=_MAX,
        contract_size=_CS,
    )
    assert out.tradeability == NOT_TRADEABLE
    assert out.tradeability_reason == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET
    assert out.estimated_risk_at_min_lot == Decimal("150.00")
    assert out.maximum_tradeable_stop_distance == Decimal("129.6")
    assert out.feasibility.stop_changed is False
    assert out.stop_distance == Decimal("150.00")


def test_small_account_vs_larger_account_tradeability() -> None:
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        NOT_TRADEABLE,
        TRADEABLE,
        evaluate_setup_tradeability,
    )

    stop = Decimal("150.00")
    small = evaluate_setup_tradeability(
        stop_distance=stop,
        equity=Decimal("162.00"),
        min_lot=_MIN,
        contract_size=_CS,
    )
    large = evaluate_setup_tradeability(
        stop_distance=stop,
        equity=Decimal("2000.00"),
        min_lot=_MIN,
        contract_size=_CS,
    )
    assert small.tradeability == NOT_TRADEABLE
    assert large.tradeability == TRADEABLE
    assert large.estimated_risk_at_min_lot == Decimal("150.00")


def test_hard_max_risk_pct_stays_eighty() -> None:
    from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile

    assert MicroAccountProfile().hard_max_risk_pct == Decimal("80.0")


def test_kill_switch_blocks_before_oms() -> None:
    out = evaluate_gold_execution_contract(_ready(kill_switch=True))
    assert out.may_submit_oms is False
    assert out.fault_code == "SAFETY_BLOCKED"


def test_broker_disconnect_and_mt5_unavailable_block_oms() -> None:
    gw = evaluate_gold_execution_contract(_ready(gateway_connected=False))
    assert gw.may_submit_oms is False
    assert gw.fault_code == "GATEWAY_UNAVAILABLE"
    mt5 = evaluate_gold_execution_contract(_ready(broker_connected=False))
    assert mt5.may_submit_oms is False
    assert mt5.fault_code == "MT5_UNAVAILABLE"


def test_mt5_timeout_is_execution_failed_not_a_fill() -> None:
    from app.application.services.institutional_ite_runtime import ShadowCycleResult
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        EXEC_EXECUTION_FAILED,
        classify_cycle_execution_status,
    )

    status = classify_cycle_execution_status(
        abort_reason="CYCLE_TIMEOUT",
        cycle_outcome="error",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert status == EXEC_EXECUTION_FAILED
    cycle = ShadowCycleResult(
        ok=False,
        trace_id="t",
        mode="live",
        cycle_outcome="error",
        abort_reason="CYCLE_TIMEOUT",
        forwarded_to_oms=True,
        mt5_ticket=None,
    )
    payload = cycle.to_dict()
    assert payload["execution_status"] == EXEC_EXECUTION_FAILED
    assert payload["execution_result"] == "NO BROKER ORDER WAS SUBMITTED"
    assert payload["broker_ticket"] is None


def test_min_lot_rejection_does_not_stop_worker_or_stall_scheduler() -> None:
    from app.application.services.institutional_ite_runtime import ShadowCycleResult
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        EXEC_WAITING_FOR_SETUP,
        classify_cycle_execution_status,
    )
    from app.domain.institutional_trading.operations.worker_runtime_state import (
        RUNNING,
        derive_scheduler_state,
        derive_worker_state,
        last_blocker_from_cycle,
        scheduler_is_stalled,
    )

    cycle = ShadowCycleResult(
        ok=True,
        trace_id="t",
        mode="live",
        decision_action="SELL",
        forwarded_to_oms=False,
        cycle_outcome="execution_contract",
        abort_reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        mt5_ticket=None,
        market_context_diagnostics={
            "tradeability": "NOT_TRADEABLE",
            "tradeability_reason": CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
            "estimated_risk_at_min_lot": "13.14",
            "maximum_tradeable_stop_distance": "8.10",
        },
    )
    payload = cycle.to_dict()
    assert payload["execution_status"] == EXEC_WAITING_FOR_SETUP
    assert payload["tradeability"] == "NOT_TRADEABLE"
    assert payload["execution_result"] == "NO BROKER ORDER WAS SUBMITTED"
    assert classify_cycle_execution_status(
        abort_reason=CODE_MIN_LOT_EXCEEDS_RISK_BUDGET,
        cycle_outcome="execution_contract",
        forwarded_to_oms=False,
        mt5_ticket=None,
        tradeability="NOT_TRADEABLE",
    ) == EXEC_WAITING_FOR_SETUP
    blocker, stage = last_blocker_from_cycle(cycle)
    assert blocker == CODE_MIN_LOT_EXCEEDS_RISK_BUDGET
    assert stage == "risk"
    assert (
        derive_worker_state(
            running=True,
            cycles=12,
            broker_session_open=True,
            operator_halt=False,
            risk_halt=False,
            recovering=False,
            degraded=False,
            last_outcome="execution_contract",
            stalled=False,
        )
        == RUNNING
    )
    assert (
        derive_scheduler_state(
            running=True,
            stalled=False,
            broker_session_open=True,
        )
        == RUNNING
    )
    now = 1_000_000.0
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=now - 5.0,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 600.0,
            running=True,
            cycle_started_mono=now - 5.0,
        )
        is False
    )
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=now - 4.0,
            now_mono=now,
            interval_seconds=5.0,
            started_mono=now - 3600.0,
            running=True,
            cycle_started_mono=0.0,
        )
        is False
    )


def test_eligible_tight_setup_reaches_oms_without_fabricating_ticket() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            symbol="XAUUSD_i",
            approved_lots=_MIN,
            min_lot_infeasible=False,
            risk_eligible=True,
        )
    )
    assert out.may_submit_oms is True
    assert out.execution_readiness == "EXECUTION_READY"
    assert out.execute_now_required is False


def test_strategy_stop_never_clamped_to_min_lot_max() -> None:
    from types import SimpleNamespace

    from app.domain.institutional_trading.ai_scalping.structure_targets import (
        choose_strategy_stop_distance,
    )
    from app.domain.institutional_trading.decision_models import TradeDirection
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        evaluate_setup_tradeability,
        max_allowed_stop_at_min_lot,
    )

    snap = SimpleNamespace(
        primary_structure=SimpleNamespace(
            last_swing_low=None,
            last_swing_high=Decimal("4600"),
            swings=(),
        ),
        structure_by_tf=None,
        fair_value_gaps=None,
        order_blocks=None,
        liquidity=None,
    )
    atr = Decimal("12.00")
    chosen, source = choose_strategy_stop_distance(
        snap,  # type: ignore[arg-type]
        direction=TradeDirection.SELL,
        entry=Decimal("4380"),
        atr=atr,
        stop_atr_mult=Decimal("1.10"),
    )
    max_stop = max_allowed_stop_at_min_lot(
        equity=_EQUITY,
        hard_max_risk_pct=Decimal("80.0"),
        min_lot=_MIN,
        contract_size=_CS,
    )
    assert chosen == atr * Decimal("1.10")
    assert source == "atr_cap" or source == "atr_fallback"
    assert chosen != max_stop
    trade = evaluate_setup_tradeability(
        stop_distance=chosen,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
    )
    assert trade.feasibility.stop_changed is False


def test_tight_structure_stop_is_tradeable_without_moving_sl() -> None:
    from types import SimpleNamespace

    from app.domain.institutional_trading.ai_scalping.structure_targets import (
        choose_strategy_stop_distance,
    )
    from app.domain.institutional_trading.decision_models import TradeDirection
    from app.domain.institutional_trading.operations.min_lot_feasibility import (
        TRADEABLE,
        evaluate_setup_tradeability,
    )

    snap = SimpleNamespace(
        primary_structure=SimpleNamespace(
            last_swing_low=None,
            last_swing_high=Decimal("4384.00"),
            swings=(),
        ),
        structure_by_tf=None,
        fair_value_gaps=None,
        order_blocks=None,
        liquidity=None,
    )
    atr = Decimal("12.00")
    chosen, source = choose_strategy_stop_distance(
        snap,  # type: ignore[arg-type]
        direction=TradeDirection.SELL,
        entry=Decimal("4380.00"),
        atr=atr,
        stop_atr_mult=Decimal("1.10"),
    )
    assert source == "structure"
    assert chosen is not None
    assert chosen < Decimal("8.10")
    trade = evaluate_setup_tradeability(
        stop_distance=chosen,
        equity=_EQUITY,
        min_lot=_MIN,
        contract_size=_CS,
    )
    assert trade.tradeability == TRADEABLE
    assert trade.feasibility.stop_changed is False
