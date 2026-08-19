"""NZDUSD_I leverage-policy reject + retcode=0 is not a broker fill."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    PipelineResult,
    PipelineStageRecord,
    parse_order_intent,
)
from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    ShadowCycleResult,
)
from app.application.services.institutional_oms_adapter import (
    map_pipeline_to_oms_result,
    pipeline_reach_flags,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.execution_safety import ExecutionPolicy
from app.domain.enums.execution import ExecutionDecision
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
from app.domain.trading.xauusd_specs import MAX_LEVERAGE
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


@pytest.mark.unit
def test_max_leverage_2000_is_hardcoded_gold_desk_constant() -> None:
    src = (REPO / "app/domain/trading/xauusd_specs.py").read_text(encoding="utf-8")
    assert 'MAX_LEVERAGE = Decimal("2000")' in src
    assert "os.environ" not in src
    assert "getenv" not in src
    assert MAX_LEVERAGE == Decimal("2000")
    policy = ExecutionPolicy()
    assert policy.max_leverage == MAX_LEVERAGE
    assert policy.max_leverage == Decimal("2000")


@pytest.mark.unit
def test_account_leverage_is_read_from_account_info() -> None:
    engine, client = _engine()
    orig = client.account_info

    def _lev2000():
        return replace(orig(), leverage=2000)

    client.account_info = _lev2000  # type: ignore[method-assign]
    info = engine.safety.adapter.account_info()
    assert info.leverage == 2000
    assert info.server == "Weltrade-Real"
    assert info.login == 16785006


@pytest.mark.unit
def test_leverage_policy_reject_is_fail_closed_hard_block() -> None:
    out = classify_candidate_outcome(
        abort_reason="oms_failure",
        failed_reasons=(
            "Account leverage exceeds desk policy "
            "(leverage 2001 exceeds max_leverage 2000).",
        ),
        cycle_outcome="forwarded",
        forwarded_to_oms=True,
        decision_action="SELL",
    )
    assert out["fault_class"] == FaultClass.HARD_BLOCK.value
    assert out["fault_code"] == "LEVERAGE_POLICY_EXCEEDED"
    assert out["blocking_stage"] == "SAFETY"
    assert out["next_action"] == CandidateAction.FAIL_CLOSED.value
    assert out["decision_state"] == DecisionState.HARD_BLOCK.value
    halt = classify_halt_condition(
        "Account leverage exceeds desk policy (leverage 2001 exceeds max_leverage 2000)."
    )
    assert halt is HaltClass.HARD_BLOCK


@pytest.mark.unit
def test_humanized_reason_matches_observed_toast() -> None:
    raw = "leverage 2001 exceeds max_leverage 2000"
    assert humanize_reason(raw).startswith("Account leverage exceeds desk policy")


@pytest.mark.unit
def test_retcode_zero_is_not_broker_execution_when_send_not_reached() -> None:
    pipeline = PipelineResult(
        request_id="lev-1",
        action="submit",
        outcome="rejected",
        message="Account leverage exceeds desk policy (leverage 2001 exceeds max_leverage 2000).",
        stages=[
            PipelineStageRecord(
                stage="Draft", status="ok", reason="Draft accepted", elapsed_ms=1.0
            ),
            PipelineStageRecord(
                stage="Validation",
                status="ok",
                reason="Validation passed",
                elapsed_ms=18000.0,
                meta={"component": "validation", "order_check_retcode": 0},
            ),
            PipelineStageRecord(
                stage="Risk Check",
                status="failed",
                reason="leverage 2001 exceeds max_leverage 2000",
                elapsed_ms=12.0,
                meta={"decision": "reject", "checks": {"leverage_limit": False}},
            ),
        ],
        rejection_reasons=["leverage 2001 exceeds max_leverage 2000"],
        latency_ms=18020.0,
    )
    reach = pipeline_reach_flags(pipeline)
    assert reach["oms_reached"] is True
    assert reach["order_check_reached"] is True
    assert reach["gateway_reached"] is True
    assert reach["order_send_reached"] is False
    mapped = map_pipeline_to_oms_result(pipeline)
    assert mapped.retcode is None
    assert mapped.gateway_status == "order_check_only"
    assert mapped.outcome == "rejected"


@pytest.mark.unit
def test_execute_now_payload_omits_retcode_zero_without_send() -> None:
    runtime = MagicMock(spec=InstitutionalIteRuntime)
    runtime._lock = __import__("threading").Lock()
    runtime._last_decision = SimpleNamespace(
        symbol="NZDUSD_I",
        direction=SimpleNamespace(value="SELL"),
        approved_lots=Decimal("0.01"),
        entry_zone=None,
        stop_zone=None,
        target_zone=None,
    )
    runtime._last_bridge_result = SimpleNamespace(
        oms_result=SimpleNamespace(
            outcome="rejected",
            order_ticket=None,
            deal_ticket=None,
            message="Account leverage exceeds desk policy "
            "(leverage 2001 exceeds max_leverage 2000).",
            raw={"order_send_reached": False},
        )
    )
    cycle = ShadowCycleResult(
        ok=True,
        trace_id="t-lev",
        mode="LIVE",
        forwarded_to_oms=True,
        oms_message="Account leverage exceeds desk policy "
        "(leverage 2001 exceeds max_leverage 2000).",
        abort_reason="oms_failure",
        cycle_outcome="forwarded",
        broker_retcode=0,
    )
    payload = InstitutionalIteRuntime.build_execute_now_payload(
        runtime, cycle, execution_ms=20323
    )
    assert payload["success"] is False
    assert "retcode=0" not in payload["reason"]
    assert "Account leverage exceeds desk policy" in payload["reason"]


@pytest.mark.unit
def test_run_submit_leverage_reject_never_calls_order_send() -> None:
    engine, client = _engine()
    orig = client.account_info

    def _lev2001():
        return replace(orig(), leverage=2001)

    client.account_info = _lev2001  # type: ignore[method-assign]
    positions_before = len(client.list_positions())
    sends: list[object] = []
    orig_send = client.order_send

    def _wrap_send(request):
        sends.append(request)
        return orig_send(request)

    client.order_send = _wrap_send  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD", side="sell", order_type="market", volume="0.01"
    )
    pipeline, decision = engine.run_submit(
        user_id=uuid4(),
        request_id="lev-nzd-audit",
        intent=intent,
        connected=True,
        login=16785006,
        recent_decisions=[],
    )
    assert decision is not None
    assert decision.decision is ExecutionDecision.REJECT
    assert any("leverage" in r.lower() and "exceeds" in r.lower() for r in (
        decision.rejection_reasons or []
    ))
    assert pipeline.outcome == "rejected"
    assert "Broker Submission" not in [s.stage for s in pipeline.stages]
    assert sends == []
    assert len(client.list_positions()) == positions_before
    mapped = map_pipeline_to_oms_result(pipeline)
    assert mapped.retcode is None
    assert pipeline_reach_flags(pipeline)["order_send_reached"] is False


@pytest.mark.unit
def test_leverage_reject_does_not_add_order_send_retry() -> None:
    client_src = (
        REPO / "app/infrastructure/brokers/mt5/gateway_client.py"
    ).read_text(encoding="utf-8")
    engine_src = (
        REPO / "app/application/services/institutional_execution_engine.py"
    ).read_text(encoding="utf-8")
    assert "Never retry order_send" in client_src
    assert "attempts = 2 if method.upper() == \"GET\"" in client_src or (
        "attempts = 2 if method.upper() == 'GET'" in client_src
        or 'attempts = 2 if method.upper() == "GET" else 1' in client_src
    )
    assert "self.gateway.submit" in engine_src
    # No extra polling/retry loop added for leverage.
    assert "while True:" not in (
        REPO / "app/application/services/execution_safety.py"
    ).read_text(encoding="utf-8")
