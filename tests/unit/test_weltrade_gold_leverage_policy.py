"""Weltrade XAUUSD desk leverage policy: 2000 allowed, above 2000 hard-blocked."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.institutional_oms_adapter import pipeline_reach_flags
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.entities.mt5_order import OrderIntent
from app.domain.enums.execution import ExecutionDecision
from app.domain.enums.order import OrderSide, OrderType
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.execution_engine.reasons import humanize_reason
from app.domain.institutional_trading.operations.execution_halt_policy import (
    HaltClass,
    classify_halt_condition,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
    FaultClass,
    classify_candidate_outcome,
)
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.domain.trading.xauusd_specs import EXPOSURE_LEVERAGE_FALLBACK, MAX_LEVERAGE
from app.domain.value_objects.mt5_order import LotSize
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter

REPO = Path(__file__).resolve().parents[2]


def _engine() -> tuple[InstitutionalExecutionEngine, MockMT5Client]:
    client = MockMT5Client()
    client.initialize()
    client.login(MT5LoginRequest(login=16785006, password="p", server="Weltrade-Real"))
    adapter = MT5Adapter(client=client, execution_enabled=True)
    validation = MT5OrderValidationService(adapter=adapter)
    return (
        InstitutionalExecutionEngine(
            gateway=ExecutionGateway(adapter=adapter, order_validation=validation),
            safety=ExecutionSafetyService(
                adapter=adapter, order_validation=validation
            ),
            order_validation=validation,
            intelligence=ExecutionIntelligenceService(),
            journal=ExecutionJournalStore(),
        ),
        client,
    )


def _safety() -> ExecutionSafetyService:
    adapter = MT5Adapter(client=MockMT5Client())
    return ExecutionSafetyService(
        adapter=adapter,
        order_validation=MT5OrderValidationService(adapter=adapter),
        policy=ExecutionPolicy(),
    )


def _gold_intent() -> OrderIntent:
    return OrderIntent(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.01"),
    )


@pytest.mark.unit
def test_policy_ceiling_is_single_source_2000() -> None:
    src = (REPO / "app/domain/trading/xauusd_specs.py").read_text(encoding="utf-8")
    assert src.count('MAX_LEVERAGE = Decimal("2000")') == 1
    assert 'MAX_LEVERAGE = Decimal("1000")' not in src
    assert MAX_LEVERAGE == Decimal("2000")
    assert ExecutionPolicy().max_leverage == MAX_LEVERAGE
    assert EXPOSURE_LEVERAGE_FALLBACK == Decimal("1000")
    assert EXPOSURE_LEVERAGE_FALLBACK != MAX_LEVERAGE


@pytest.mark.unit
def test_account_leverage_2000_passes_desk_policy() -> None:
    ok, reasons, _warnings, checks = _safety().evaluate_policy(
        _gold_intent(),
        login=16785006,
        spread=Decimal("0.30"),
        leverage=Decimal("2000"),
    )
    assert ok is True
    assert checks["leverage_limit"] is True
    assert not any("exceeds max_leverage" in r for r in reasons)


@pytest.mark.unit
@pytest.mark.parametrize("account_leverage", [Decimal("2001"), Decimal("3000")])
def test_account_leverage_above_2000_hard_blocks(account_leverage: Decimal) -> None:
    ok, reasons, _warnings, checks = _safety().evaluate_policy(
        _gold_intent(),
        login=16785006,
        spread=Decimal("0.30"),
        leverage=account_leverage,
    )
    assert ok is False
    assert checks["leverage_limit"] is False
    expected = f"leverage {account_leverage} exceeds max_leverage {MAX_LEVERAGE}"
    assert any(expected in r for r in reasons)
    human = humanize_reason(expected)
    assert human.startswith("Account leverage exceeds desk policy")
    assert f"max_leverage {MAX_LEVERAGE}" in human
    assert "max_leverage 1000" not in human
    classified = classify_candidate_outcome(
        abort_reason="oms_failure",
        failed_reasons=(human,),
        cycle_outcome="forwarded",
        forwarded_to_oms=True,
        decision_action="BUY",
    )
    assert classified["fault_code"] == "LEVERAGE_POLICY_EXCEEDED"
    assert classified["fault_class"] == FaultClass.HARD_BLOCK.value
    assert classified["next_action"] == CandidateAction.FAIL_CLOSED.value
    assert classified["decision_state"] == DecisionState.HARD_BLOCK.value
    assert classify_halt_condition(human) is HaltClass.HARD_BLOCK


@pytest.mark.unit
def test_leverage_check_remains_authoritative_fail_closed() -> None:
    safety_src = (
        REPO / "app/application/services/execution_safety.py"
    ).read_text(encoding="utf-8")
    assert "ok_lev = leverage <= self.policy.max_leverage" in safety_src
    assert "checks[\"leverage_limit\"] = ok_lev" in safety_src
    fast_src = (
        REPO / "app/domain/institutional_trading/operations/fast_decision_path.py"
    ).read_text(encoding="utf-8")
    assert '"fault_code": "LEVERAGE_POLICY_EXCEEDED"' in fast_src
    assert "ALLOW_RISK_LOCK_OVERRIDE" not in safety_src
    assert "FORCE_FIRST_TRADE" not in safety_src


@pytest.mark.unit
def test_live_path_account_2000_reaches_leverage_pass_not_order_send() -> None:
    """GET /account leverage=2000 → ExecutionSafety → policy.max_leverage=2000 → PASS.

    Does not send a live broker order. Continues to the next authoritative stage
    only if other gates also pass.
    """
    engine, client = _engine()
    orig = client.account_info

    def _account_2000():
        return replace(orig(), leverage=2000)

    client.account_info = _account_2000  # type: ignore[method-assign]
    account = engine.safety.adapter.account_info()
    assert account.leverage == 2000
    assert engine.safety.policy.max_leverage == MAX_LEVERAGE
    assert engine.safety.policy.max_leverage == Decimal("2000")
    ok, reasons, _warnings, checks = engine.safety.evaluate_policy(
        _gold_intent(),
        login=account.login,
        spread=Decimal("0.30"),
        leverage=Decimal(str(account.leverage)),
    )
    assert checks["leverage_limit"] is True
    assert ok is True
    assert reasons == []


@pytest.mark.unit
def test_run_submit_above_2000_never_calls_order_send() -> None:
    engine, client = _engine()
    orig = client.account_info

    def _account_3000():
        return replace(orig(), leverage=3000)

    client.account_info = _account_3000  # type: ignore[method-assign]
    positions_before = len(client.list_positions())
    sends: list[object] = []
    orig_send = client.order_send

    def _wrap_send(request):
        sends.append(request)
        return orig_send(request)

    client.order_send = _wrap_send  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD", side="buy", order_type="market", volume="0.01"
    )
    pipeline, decision = engine.run_submit(
        user_id=uuid4(),
        request_id="lev-policy-3000",
        intent=intent,
        connected=True,
        login=16785006,
        recent_decisions=[],
    )
    assert decision is not None
    assert decision.decision is ExecutionDecision.REJECT
    assert any(
        "leverage" in r.lower() and "exceeds" in r.lower()
        for r in (decision.rejection_reasons or [])
    )
    assert any(f"max_leverage {MAX_LEVERAGE}" in r for r in (decision.rejection_reasons or []))
    assert pipeline.outcome == "rejected"
    assert "Broker Submission" not in [s.stage for s in pipeline.stages]
    assert sends == []
    assert len(client.list_positions()) == positions_before
    assert pipeline_reach_flags(pipeline)["order_send_reached"] is False


@pytest.mark.unit
def test_min_lot_and_safety_unchanged_by_leverage_ceiling() -> None:
    adapter = MT5Adapter(client=MockMT5Client())
    adapter.initialize()
    adapter.login(MT5LoginRequest(login=7, password="p", server="S"))
    safety = ExecutionSafetyService(
        adapter=adapter,
        order_validation=MT5OrderValidationService(adapter=adapter),
        policy=ExecutionPolicy(),
    )
    intent = OrderIntent(
        symbol="XAUUSD",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        volume=LotSize.of("0.015"),
    )
    record = safety.decide(
        user_id=uuid4(),
        request_id="lev-min-lot-unchanged",
        intent=intent,
        connected=True,
        login=7,
        recent=[],
    )
    assert record.decision is ExecutionDecision.REJECT
    assert record.checks.get("volume_limits") is False
    assert record.checks.get("leverage_limit") is True
