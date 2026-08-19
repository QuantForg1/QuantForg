"""Autonomous Gold execution contract — existing OMS path, no Execute Now."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    classify_candidate_outcome,
    record_cycle_classification,
    reset_fast_decision_path,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    CANONICAL_GOLD,
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
    scalping_v1_floors,
)
from app.domain.trading.gold_only import gold_only_diagnostics
from app.domain.trading.xauusd_specs import MAX_LEVERAGE

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]
FLOORS = scalping_v1_floors()


def _ready(**overrides: object) -> GoldExecutionFacts:
    base = dict(
        symbol="XAUUSD_I",
        direction="BUY",
        action="BUY",
        market_open=True,
        tradable=True,
        candles_ok=True,
        bid=Decimal("2400.10"),
        ask=Decimal("2400.30"),
        quote_age_seconds=1.0,
        spread=Decimal("0.20"),
        structure_score=70,
        momentum_score=65,
        quality=80,
        confidence=75,
        pa_confluence=55,
        risk_reward=Decimal("1.20"),
        market_regime="TREND",
        volatility_ok=True,
        session_quality_ok=True,
        safety_allowed=True,
        kill_switch=False,
        execution_enabled=True,
        auto_running=True,
        account_leverage=Decimal("2000"),
        risk_eligible=True,
        approved_lots=Decimal("0.01"),
        min_lot_infeasible=False,
        portfolio_allow=True,
        optimizer_state="EXECUTE_NOW",
        oms_orders_allowed=True,
        gateway_connected=True,
        broker_connected=True,
        force_shadow=False,
        gold_only=True,
    )
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


@pytest.mark.unit
def test_strong_natural_gold_setup_is_execution_ready() -> None:
    out = evaluate_gold_execution_contract(_ready())
    assert out.decision_state == DecisionState.EXECUTION_READY.value
    assert out.execution_readiness == "EXECUTION_READY"
    assert out.may_submit_oms is True
    assert out.execute_now_required is False
    assert out.direction == "BUY"
    assert out.symbol.upper().startswith("XAUUSD")
    assert all(v == "PASS" for v in out.stages.values())


@pytest.mark.unit
def test_execute_now_is_not_required_for_autonomous_submit() -> None:
    out = evaluate_gold_execution_contract(_ready())
    assert out.execute_now_required is False
    assert out.may_submit_oms is True
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(runtime_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_cycle":
            src = ast.get_source_segment(runtime_src, node) or ""
            assert "self.execute_now" not in src
            assert "evaluate_gold_execution_contract" in src
            assert "self.execution.bridge.handle" in src
            break
    else:
        pytest.fail("_run_cycle not found")


@pytest.mark.unit
def test_gold_only_universe_is_xauusd_i(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    diag = gold_only_diagnostics()
    assert diag["execution_universe"] == ["XAUUSD_i"]
    rejected = evaluate_gold_execution_contract(_ready(symbol="EURUSD_I"))
    assert rejected.may_submit_oms is False
    assert rejected.fault_code == "GOLD_ONLY_SYMBOL_REJECTED"


@pytest.mark.unit
def test_direction_none_never_executes() -> None:
    out = evaluate_gold_execution_contract(_ready(direction="NONE", action="NO_TRADE"))
    assert out.may_submit_oms is False
    assert out.fault_code == "DIRECTION_NONE"
    assert out.direction == "NONE"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("structure_score", 0, "Weak structure score 0 <"),
        ("momentum_score", 10, "Momentum 10 <"),
        ("quality", 40, "Trade quality 40 <"),
        ("confidence", 20, "Confidence 20 <"),
        ("pa_confluence", 10, "PA confluence 10 <"),
    ],
)
def test_weak_scalping_floors_block(field: str, value: int, needle: str) -> None:
    out = evaluate_gold_execution_contract(_ready(**{field: value}))
    assert out.may_submit_oms is False
    assert out.fault_code == "SETUP_NOT_READY"
    assert needle in out.fault_reason
    assert out.decision_state == DecisionState.SETUP_NOT_READY.value


@pytest.mark.unit
def test_leverage_2000_passes_and_2001_blocks() -> None:
    ok = evaluate_gold_execution_contract(_ready(account_leverage=Decimal("2000")))
    assert ok.may_submit_oms is True
    assert MAX_LEVERAGE == Decimal("2000")
    blocked = evaluate_gold_execution_contract(_ready(account_leverage=Decimal("2001")))
    assert blocked.may_submit_oms is False
    assert blocked.fault_code == "LEVERAGE_POLICY_EXCEEDED"
    assert blocked.fault_class == FaultClass.HARD_BLOCK.value
    assert blocked.next_action == CandidateAction.FAIL_CLOSED.value


@pytest.mark.unit
def test_risk_failure_blocks() -> None:
    out = evaluate_gold_execution_contract(
        _ready(risk_eligible=False, risk_reasons=("daily loss limit exceeded",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "RISK_REJECTED"
    assert "daily loss" in out.fault_reason.lower()


@pytest.mark.unit
def test_min_lot_risk_infeasible_blocks() -> None:
    out = evaluate_gold_execution_contract(_ready(min_lot_infeasible=True))
    assert out.may_submit_oms is False
    assert out.fault_code == "MIN_LOT_RISK_INFEASIBLE"
    assert out.next_action == CandidateAction.NO_EXECUTABLE_FOCUS.value


@pytest.mark.unit
def test_portfolio_failure_blocks() -> None:
    out = evaluate_gold_execution_contract(
        _ready(portfolio_allow=False, portfolio_reasons=("max exposure",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "PORTFOLIO_REJECTED"


@pytest.mark.unit
def test_optimizer_wait_does_not_execute() -> None:
    out = evaluate_gold_execution_contract(_ready(optimizer_state="WAIT_BOUNDED"))
    assert out.may_submit_oms is False
    assert out.fault_code == "OPTIMIZER_WAIT"
    assert out.next_action == CandidateAction.WAIT_SAME_FOCUS.value


@pytest.mark.unit
def test_optimizer_execute_now_continues() -> None:
    out = evaluate_gold_execution_contract(_ready(optimizer_state="EXECUTE_NOW"))
    assert out.may_submit_oms is True
    assert out.stages["OPTIMIZER"] == "PASS"


@pytest.mark.unit
def test_oms_and_gateway_required() -> None:
    oms = evaluate_gold_execution_contract(_ready(oms_orders_allowed=False))
    assert oms.may_submit_oms is False
    assert oms.fault_code == "OMS_NOT_READY"
    gw = evaluate_gold_execution_contract(_ready(gateway_connected=False))
    assert gw.may_submit_oms is False
    assert gw.fault_code == "GATEWAY_UNAVAILABLE"
    mt5 = evaluate_gold_execution_contract(_ready(broker_connected=False))
    assert mt5.may_submit_oms is False
    assert mt5.fault_code == "MT5_UNAVAILABLE"


@pytest.mark.unit
def test_stale_quote_hard_blocks() -> None:
    out = evaluate_gold_execution_contract(_ready(quote_age_seconds=200.0))
    assert out.may_submit_oms is False
    assert out.fault_code == "STALE_QUOTE"
    assert out.fault_class == FaultClass.HARD_BLOCK.value


@pytest.mark.unit
def test_no_forced_trade_and_no_second_path() -> None:
    runtime_src = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    assert "FORCE_FIRST_TRADE proceeding" in runtime_src
    engine_src = (
        ROOT / "app/application/services/institutional_execution_engine.py"
    ).read_text(encoding="utf-8")
    assert "self.gateway.submit" in engine_src
    tree = ast.parse(runtime_src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "order_send":
                pytest.fail("ITE must not call order_send directly")


@pytest.mark.unit
def test_order_check_and_single_order_send_remain_gateway() -> None:
    client_src = (
        ROOT / "app/infrastructure/brokers/mt5/gateway_client.py"
    ).read_text(encoding="utf-8")
    assert "Never retry order_send" in client_src
    assert "order_check" in client_src
    unknown = classify_candidate_outcome(abort_reason="ORDER_UNKNOWN")
    assert unknown["decision_state"] == DecisionState.ORDER_UNKNOWN.value
    assert unknown["next_action"] == CandidateAction.RECONCILE.value


@pytest.mark.unit
def test_floors_are_scalping_v1_not_lowered() -> None:
    assert FLOORS["structure"] == 60
    assert FLOORS["momentum"] == 55
    assert FLOORS["quality"] == 74
    assert FLOORS["confidence"] == 71
    assert FLOORS["pa_confluence"] == 45


@pytest.mark.unit
def test_tracker_records_readiness_stages() -> None:
    reset_fast_decision_path()
    out = evaluate_gold_execution_contract(_ready())
    record_cycle_classification(
        out.to_dict(),
        cycle_ms=12.5,
        forwarded_to_oms=False,
    )
    from app.domain.institutional_trading.operations.fast_decision_path import (
        opportunity_window_snapshot,
    )

    snap = opportunity_window_snapshot()
    events = snap.get("recent_events") or snap.get("cycle_events") or []
    assert events
    last = events[-1]
    assert last["market_ready"] is True
    assert last["optimizer_ready"] is True
    assert last["execution_readiness"] == "EXECUTION_READY"
    assert snap["execute_now_required"] is False
    assert snap["forces_trades"] is False


@pytest.mark.unit
def test_execute_now_signature_unchanged() -> None:
    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )
    from app.presentation.routers.institutional_ops import execute_now_auto_trading

    sig = inspect.signature(InstitutionalIteRuntime.execute_now)
    assert "symbol" not in sig.parameters
    http = inspect.signature(execute_now_auto_trading)
    assert "symbol" not in http.parameters
