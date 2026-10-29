"""Unit tests for Institutional Execution Engine."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.execution_gateway import ExecutionGateway
from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.application.services.execution_safety import ExecutionSafetyService
from app.application.services.institutional_execution_engine import (
    InstitutionalExecutionEngine,
    parse_order_intent,
)
from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.enums.execution import ExecutionOutcome
from app.domain.execution_engine.journal import ExecutionJournalStore
from app.domain.execution_engine.reasons import humanize_reason
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


def _engine(
    *, enabled: bool = True
) -> tuple[InstitutionalExecutionEngine, MockMT5Client]:
    client = MockMT5Client()
    client.initialize()
    client.login(MT5LoginRequest(login=1, password="p", server="S"))
    adapter = MT5Adapter(client=client, execution_enabled=enabled)
    validation = MT5OrderValidationService(adapter=adapter)
    return (
        InstitutionalExecutionEngine(
            gateway=ExecutionGateway(adapter=adapter, order_validation=validation),
            safety=ExecutionSafetyService(adapter=adapter, order_validation=validation),
            order_validation=validation,
            intelligence=ExecutionIntelligenceService(),
            journal=ExecutionJournalStore(),
        ),
        client,
    )


@pytest.mark.unit
def test_humanize_reason_market_closed() -> None:
    assert "Market is closed" in humanize_reason("market closed")


def _clear_kill_switch() -> None:
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.domain.institutional_trading.phase_a import get_phase_a_plane
    from app.domain.institutional_trading.phase_a.kill_state import HaltMode

    plane = get_control_plane()
    plane.kill_switch_armed = False
    halt = get_phase_a_plane().halt
    if halt.mode is not HaltMode.ACTIVE:
        halt.set_mode(HaltMode.ACTIVE, actor="unit-test", reason="clear test halt")


def _allow_broker_submit() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.domain.institutional_trading.operations.models import OperatorIdentity

    _clear_kill_switch()
    plane = get_control_plane()
    plane.daily_loss_exceeded = False
    ctrl = reset_live_trading_controller_for_tests()
    op = OperatorIdentity(user_id=uuid4(), role="owner", display_name="engine-test")
    ctrl.transition(op, "ARMED", confirmed=True, reason="test arm")
    ctrl.transition(op, "ENABLED", confirmed=True, reason="test enable")


@pytest.mark.unit
def test_pipeline_market_buy_observes_stages() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    engine, client = _engine(enabled=True)
    seen: dict[str, str] = {}
    original = client.order_send

    def _capture(request):  # type: ignore[no-untyped-def]
        seen["client_order_id"] = str(getattr(request, "client_order_id", ""))
        return original(request)

    client.order_send = _capture  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2301.80",
        take_profit="2349.30",
    )
    user_id = uuid4()
    try:
        _allow_broker_submit()
        pipeline, decision = engine.run_submit(
            user_id=user_id,
            request_id="eng-1",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    finally:
        reset_live_trading_controller_for_tests()
    assert decision is not None
    assert decision.decision.value == "allow"
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value, pipeline.message
    assert seen.get("client_order_id") == "eng-1"
    stage_names = [s.stage for s in pipeline.stages]
    assert "Draft" in stage_names
    assert "Validation" in stage_names
    assert "Risk Check" in stage_names
    assert "Execution Check" in stage_names
    assert "Broker Submission" in stage_names
    assert pipeline.journal_entry is not None
    rows = engine.journal.list_for_user(str(user_id), limit=10)
    assert rows


@pytest.mark.unit
def test_deal_history_failure_blocks_new_entry_without_sending() -> None:
    engine, client = _engine(enabled=True)
    calls: list[object] = []
    original = engine.risk_tracker.resolve_for_risk

    def _resolve(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs.get("deals"))
        return original(**kwargs)

    engine.risk_tracker.resolve_for_risk = _resolve  # type: ignore[method-assign]

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("history down")

    engine.gateway.adapter.history_deals = _boom  # type: ignore[method-assign]
    before = len(client.list_positions())
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2310",
        take_profit="2340",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id="history-fail",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == "rejected"
    assert "DEAL_HISTORY_UNAVAILABLE" in (pipeline.message or "")
    assert calls == []
    assert len(client.list_positions()) == before


@pytest.mark.unit
def test_deal_history_failure_does_not_treat_a_close_as_an_empty_day() -> None:
    engine, _client = _engine(enabled=True)
    calls: list[object] = []

    def _resolve(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs.get("deals"))
        raise AssertionError("failed history must not resolve a close")

    original = engine.risk_tracker.resolve_for_risk
    engine.risk_tracker.resolve_for_risk = _resolve  # type: ignore[method-assign]

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("history down")

    engine.gateway.adapter.history_deals = _boom  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="sell",
        order_type="market",
        volume="0.01",
        oms_kind="close",
        position=1,
    )
    try:
        pipeline, _decision = engine.run_submit(
            user_id=uuid4(),
            request_id="history-fail-close",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    finally:
        engine.risk_tracker.resolve_for_risk = original  # type: ignore[method-assign]
    assert "DEAL_HISTORY_UNAVAILABLE" not in (pipeline.message or "")
    assert calls == []


@pytest.mark.unit
def test_orders_may_submit_false_blocks_new_entry_before_send() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    engine, client = _engine(enabled=True)
    reset_live_trading_controller_for_tests()
    _clear_kill_switch()
    sends = {"n": 0}
    original = client.order_send

    def _count(request):  # type: ignore[no-untyped-def]
        sends["n"] += 1
        return original(request)

    client.order_send = _count  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2301.80",
        take_profit="2349.30",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id="blocked-entry",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == "rejected"
    assert "orders_may_submit" in (pipeline.message or "")
    assert sends["n"] == 0


@pytest.mark.unit
def test_kill_switch_blocks_new_entry_before_send() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )

    engine, client = _engine(enabled=True)
    plane = get_control_plane()
    sends = {"n": 0}
    original = client.order_send

    def _count(request):  # type: ignore[no-untyped-def]
        sends["n"] += 1
        return original(request)

    client.order_send = _count  # type: ignore[method-assign]
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2301.80",
        take_profit="2349.30",
    )
    try:
        _allow_broker_submit()
        plane.kill_switch_armed = True
        pipeline, _decision = engine.run_submit(
            user_id=uuid4(),
            request_id="killed-entry",
            intent=intent,
            connected=True,
            login=1,
            recent_decisions=[],
        )
    finally:
        plane.kill_switch_armed = False
        reset_live_trading_controller_for_tests()
    assert pipeline.outcome == "rejected"
    assert "KILL_SWITCH" in (pipeline.message or "")
    assert sends["n"] == 0


@pytest.mark.unit
def test_disabled_controller_still_allows_explicit_close_check() -> None:
    from app.application.services.institutional_execution_engine import (
        broker_submit_block_reason,
    )
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )

    reset_live_trading_controller_for_tests()
    _clear_kill_switch()
    plane = get_control_plane()
    close_intent = parse_order_intent(
        symbol="XAUUSD",
        side="sell",
        order_type="market",
        volume="0.01",
        oms_kind="close",
        position=1,
    )
    entry = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2301.80",
        take_profit="2349.30",
    )
    assert broker_submit_block_reason(close_intent) is None
    entry_block = broker_submit_block_reason(entry)
    assert entry_block is not None
    assert "orders_may_submit" in entry_block
    plane.kill_switch_armed = True
    try:
        close_block = broker_submit_block_reason(close_intent)
    finally:
        plane.kill_switch_armed = False
    assert close_block is not None
    assert "KILL_SWITCH" in close_block


@pytest.mark.unit
def test_pipeline_disabled_never_sends() -> None:
    engine, client = _engine(enabled=False)
    before = len(client.list_positions())
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="sell",
        order_type="market",
        volume="0.01",
        stop_loss="2339.50",
        take_profit="2292.00",
    )
    pipeline, _ = engine.run_submit(
        user_id=uuid4(),
        request_id="eng-dis",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == ExecutionOutcome.DISABLED.value
    assert len(client.list_positions()) == before


@pytest.mark.unit
def test_cancel_pending_gated() -> None:
    engine, client = _engine(enabled=True)
    pending = client.list_orders()
    assert pending
    pipeline = engine.run_cancel(
        user_id=uuid4(),
        request_id="eng-cancel",
        ticket=pending[0].ticket,
        symbol=pending[0].symbol,
        connected=True,
    )
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value
    assert client.order_by_ticket(pending[0].ticket) is None


@pytest.mark.unit
def test_all_order_types_parse() -> None:
    for ot in ("market", "limit", "stop", "stop_limit"):
        intent = parse_order_intent(
            symbol="XAUUSD",
            side="buy",
            order_type=ot,
            volume="0.01",
            price="1.1000" if ot != "market" else None,
        )
        assert intent.order_type.value == ot
