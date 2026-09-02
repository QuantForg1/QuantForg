"""Small-account min-lot feasibility gate + performance telemetry.

Does not change stops, lots, the 80% ceiling, or Risk semantics.
Never sends orders.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.risk_engine import RiskEngine
from app.application.services.strategy_performance_telemetry import (
    classify_exit_reason,
    get_strategy_performance_telemetry,
    reset_strategy_performance_telemetry,
)
from app.domain.enums.risk import PositionSizingMethod
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.micro_account_mode import MicroAccountProfile
from app.domain.institutional_trading.operations.fast_decision_path import (
    DecisionState,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.min_lot_feasibility import (
    CLASS_FEASIBLE,
    CLASS_INFEASIBLE,
    evaluate_min_lot_feasibility,
    max_allowed_stop_at_min_lot,
    min_lot_needed_pct,
)
from app.domain.trading.xauusd_specs import CONTRACT_SIZE, VOLUME_MIN
from tests.unit.test_autonomous_gold_execution import _ready

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_EQUITY = Decimal("201.77")
_MIN_LOT = VOLUME_MIN
_CS = CONTRACT_SIZE
_HARD = MicroAccountProfile().hard_max_risk_pct


def _feas(*, stop: Decimal, equity: Decimal = _EQUITY):
    return evaluate_min_lot_feasibility(
        stop_distance=stop,
        equity=equity,
        min_lot=_MIN_LOT,
        contract_size=_CS,
        hard_max_risk_pct=_HARD,
    )


def test_max_allowed_stop_formula_current_account() -> None:
    max_stop = max_allowed_stop_at_min_lot(
        equity=_EQUITY,
        hard_max_risk_pct=_HARD,
        min_lot=_MIN_LOT,
        contract_size=_CS,
    )
    # 201.77 * 0.80 / (0.01 * 100) = 161.416
    assert max_stop == Decimal("161.416")
    assert _EQUITY * Decimal("0.80") == Decimal("161.416")


def test_stop_above_threshold_is_min_lot_infeasible() -> None:
    result = _feas(stop=Decimal("170"))
    assert result.classification == CLASS_INFEASIBLE
    assert result.infeasible is True
    assert result.skip_expensive_downstream is True
    assert result.needed_pct is not None and result.needed_pct > _HARD
    assert result.stop_changed is False
    assert result.lot_changed is False
    assert "MIN_LOT_INFEASIBLE" in result.risk_reasons
    assert "MIN_LOT_EXCEEDS_RISK_BUDGET" in result.risk_reasons


def test_observed_live_stops_are_infeasible_on_201_equity() -> None:
    for stop in (Decimal("170"), Decimal("180")):
        result = _feas(stop=stop)
        assert result.classification == CLASS_INFEASIBLE
        assert result.skip_expensive_downstream is True


def test_stop_within_threshold_continues_to_risk() -> None:
    result = _feas(stop=Decimal("8.00"))
    assert result.classification == CLASS_FEASIBLE
    assert result.infeasible is False
    assert result.skip_expensive_downstream is False
    assert result.risk_engine_authoritative is True
    assert result.needed_pct is not None and result.needed_pct <= _HARD


def test_boundary_needed_pct_equals_hard_max_is_not_false_reject() -> None:
    # min_loss = 10.09 → 10.09 / 201.77 * 100 = 5.00074 → 5.00 after quantize.
    stop = Decimal("10.09")
    needed = min_lot_needed_pct(
        stop_distance=stop,
        equity=_EQUITY,
        min_lot=_MIN_LOT,
        contract_size=_CS,
    )
    result = _feas(stop=stop)
    if needed <= _HARD:
        assert result.classification == CLASS_FEASIBLE
        assert result.skip_expensive_downstream is False
    else:
        assert result.classification == CLASS_INFEASIBLE


def test_filter_agrees_with_risk_engine_min_lot_math() -> None:
    """No false rejection: filter never blocks a stop Risk would approve."""
    engine = RiskEngine()
    for stop in (
        Decimal("8.00"),
        Decimal("9.72"),
        Decimal("10.08"),
        Decimal("10.09"),
        Decimal("11.6746"),
        Decimal("13.3846"),
    ):
        feas = _feas(stop=stop)
        sized = engine.size_position(
            equity=_EQUITY,
            method=PositionSizingMethod.PERCENTAGE_RISK,
            requested_lots=None,
            stop_distance=stop,
            atr=None,
            entry_price=Decimal("4600"),
            contract_size=_CS,
            risk_per_trade_pct=Decimal("1.0"),
        )
        if sized.approved_lots == _MIN_LOT:
            assert feas.infeasible is False
            assert feas.skip_expensive_downstream is False
        if feas.infeasible:
            assert sized.approved_lots == Decimal("0")


def test_risk_engine_remains_authoritative_on_feasible_stop() -> None:
    feas = _feas(stop=Decimal("5.00"))
    assert feas.classification == CLASS_FEASIBLE
    engine = RiskEngine()
    sized = engine.size_position(
        equity=_EQUITY,
        method=PositionSizingMethod.PERCENTAGE_RISK,
        requested_lots=None,
        stop_distance=Decimal("5.00"),
        atr=None,
        entry_price=Decimal("4600"),
        contract_size=_CS,
        risk_per_trade_pct=Decimal("1.0"),
    )
    assert sized.approved_lots == _MIN_LOT
    # Filter does not invent lots or a tighter stop.
    assert feas.lot_changed is False
    assert feas.stop_changed is False
    assert feas.hard_max_changed is False


def test_pipeline_gate_records_skip_vs_continue() -> None:
    reset_strategy_performance_telemetry()
    pipe = InstitutionalDecisionPipeline(config=ITEConfig())
    blocked = pipe.evaluate_min_lot_feasibility_gate(
        stop_distance=Decimal("170"),
        equity=_EQUITY,
        min_lot=_MIN_LOT,
        contract_size=_CS,
    )
    assert blocked.classification == CLASS_INFEASIBLE
    assert pipe.last_min_lot_feasibility()["classification"] == CLASS_INFEASIBLE

    ok = pipe.evaluate_min_lot_feasibility_gate(
        stop_distance=Decimal("8.00"),
        equity=_EQUITY,
        min_lot=_MIN_LOT,
        contract_size=_CS,
    )
    assert ok.classification == CLASS_FEASIBLE
    snap = get_strategy_performance_telemetry().snapshot()
    assert snap["cycle_efficiency"]["downstream_risk_overlay_skipped"] == 1
    assert snap["cycle_efficiency"]["feasible_continued_to_risk"] == 1
    assert snap["cycle_efficiency"]["scanner_rewritten"] is False


def test_contract_min_lot_infeasible_does_not_submit() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            direction="BUY",
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=(
                "MIN_LOT_INFEASIBLE",
                "MIN_LOT_CONSTRAINT: strategy-approved stop exceeds max",
            ),
        )
    )
    assert out.may_submit_oms is False
    assert out.blocking_stage == "RISK"
    assert out.decision_state == DecisionState.CANDIDATE_BLOCK.value
    assert out.fault_code in {
        "MIN_LOT_CONSTRAINT",
        "MIN_LOT_INFEASIBLE",
        "MIN_LOT_EXCEEDS_RISK_BUDGET",
    }
    assert out.execute_now_required is False


def test_telemetry_records_executed_trade_outcome() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_fill(
        ticket="562442610",
        signal_quality=88,
        confidence=82,
        direction="BUY",
        strategy_id="SCALPING_V1",
        approved_stop="8.40",
        approved_lot="0.01",
        trade_class="SCALP",
        entry="4608.167",
    )
    store.observe_close(
        ticket="562442610",
        exit_price="4615.31",
        realized_pnl="1.25",
        realized_r="0.43",
        exit_reason="break_even",
        hold_seconds=180.0,
    )
    snap = store.snapshot()
    assert snap["total_trades"] == 1
    assert snap["wins"] == 1
    assert snap["be_activations"] == 1
    assert snap["total_realized_pnl"] == pytest.approx(1.25)
    assert snap["average_r"] == pytest.approx(0.43)
    outcome = snap["recent_outcomes"][0]
    assert outcome["ticket"] == "562442610"
    assert outcome["signal_quality"] == 88
    assert outcome["confidence"] == 82
    assert outcome["direction"] == "BUY"
    assert outcome["strategy_id"] == "SCALPING_V1"
    assert outcome["approved_stop"] == "8.40"
    assert outcome["approved_lot"] == "0.01"
    assert outcome["trade_class"] == "SCALP"
    assert outcome["entry"] == "4608.167"
    assert outcome["exit"] == "4615.31"
    assert outcome["realized_pnl"] == pytest.approx(1.25)
    assert outcome["realized_r"] == pytest.approx(0.43)
    assert outcome["exit_reason"] == "break_even"


def test_telemetry_records_rejected_signals() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_cycle(
        cycle_key="cyc-min-lot-1",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_CONSTRAINT",
        ticket="562442610",
        this_cycle_forwarded=False,
        signal={"direction": "BUY", "confidence": 80},
    )
    snap = store.snapshot()
    assert snap["rejected_signals"] == 1
    assert snap["executed_signals"] == 0
    assert snap["min_lot_constraint_count"] == 1
    assert snap["risk_block_count"] == 1
    reject = snap["recent_rejects"][0]
    assert reject["ticket"] is None
    assert reject["stale_ticket_reused"] is False
    assert reject["forwarded_to_oms"] is False


def test_telemetry_no_stale_ticket_reuse() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_fill(
        ticket="111",
        direction="BUY",
        approved_lot="0.01",
        entry="4600",
    )
    row = store.observe_cycle(
        cycle_key="cyc-hold",
        forwarded_to_oms=False,
        blocking_stage="RISK",
        fault_code="MIN_LOT_INFEASIBLE",
        ticket="111",
        this_cycle_forwarded=False,
    )
    assert row["ticket"] is None
    assert row["stale_ticket_reused"] is False


def test_exit_reason_classes() -> None:
    assert classify_exit_reason("take_profit") == "TP"
    assert classify_exit_reason("stop_loss") == "SL"
    assert classify_exit_reason("break_even") == "BE"
    assert classify_exit_reason("trailing_stop") == "TRAILING"


def test_safety_block_counted_separately() -> None:
    reset_strategy_performance_telemetry()
    store = get_strategy_performance_telemetry()
    store.observe_cycle(
        cycle_key=str(uuid4()),
        forwarded_to_oms=False,
        blocking_stage="SAFETY",
        fault_code="SAFETY_BLOCKED",
        this_cycle_forwarded=False,
    )
    snap = store.snapshot()
    assert snap["safety_block_count"] == 1
    assert snap["risk_block_count"] == 0
