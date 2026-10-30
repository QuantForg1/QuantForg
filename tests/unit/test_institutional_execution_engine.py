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


def _allow_broker_submit() -> None:
    """Hydrate first, then authorize. Hydrate would otherwise force DISABLED."""
    from app.domain.institutional_trading.live_trading_control import (
        get_live_trading_controller,
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.domain.institutional_trading.operations.models import OperatorIdentity
    from app.domain.institutional_trading.phase_a import get_phase_a_plane
    from app.domain.institutional_trading.phase_a.kill_state import HaltMode

    get_control_plane()
    plane = get_control_plane()
    plane.kill_switch_armed = False
    halt = get_phase_a_plane().halt
    if halt.mode is not HaltMode.ACTIVE:
        halt.set_mode(HaltMode.ACTIVE, actor="unit-test", reason="clear test halt")
    ctrl = reset_live_trading_controller_for_tests()
    operator = OperatorIdentity(user_id=uuid4(), role="owner", display_name="unit-test")
    ctrl.transition(operator, "ARMED", confirmed=True, reason="unit-test")
    ctrl.transition(operator, "ENABLED", confirmed=True, reason="unit-test")
    # Touch the controller so a later hydrate-free read sees ENABLED.
    assert get_live_trading_controller().snapshot_state() == "ENABLED"


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


@pytest.mark.unit
def test_pipeline_market_buy_observes_stages() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    engine, client = _engine(enabled=True)
    client._positions = []  # owner limit: one open position, start flat
    _allow_broker_submit()
    # Mock ask 2320.80: SL 1.80 away ($1.80), TP 3.20 away -> RR 1.52 after spread.
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.00",
    )
    user_id = uuid4()
    pipeline, decision = engine.run_submit(
        user_id=user_id,
        request_id="eng-1",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert decision is not None
    assert decision.decision.value == "allow"
    assert pipeline.outcome == ExecutionOutcome.SUCCESS.value
    stage_names = [s.stage for s in pipeline.stages]
    assert "Draft" in stage_names
    assert "Validation" in stage_names
    assert "Risk Check" in stage_names
    assert "Execution Check" in stage_names
    assert "Broker Submission" in stage_names
    assert pipeline.journal_entry is not None
    reset_live_trading_controller_for_tests()


@pytest.mark.unit
def test_disabled_controller_blocks_a_new_entry_before_send() -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )
    from app.domain.institutional_trading.operations.control_plane import (
        get_control_plane,
    )
    from app.domain.institutional_trading.phase_a import get_phase_a_plane
    from app.domain.institutional_trading.phase_a.kill_state import HaltMode

    get_control_plane().kill_switch_armed = False
    halt = get_phase_a_plane().halt
    if halt.mode is not HaltMode.ACTIVE:
        halt.set_mode(HaltMode.ACTIVE, actor="unit-test", reason="clear test halt")
    reset_live_trading_controller_for_tests()
    engine, client = _engine(enabled=True)
    client._positions = []
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.00",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id="eng-blocked",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    assert pipeline.outcome == "rejected"
    assert "orders_may_submit" in pipeline.message


@pytest.mark.unit
def test_deal_history_failure_blocks_a_new_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.live_trading_control import (
        reset_live_trading_controller_for_tests,
    )

    _allow_broker_submit()
    engine, client = _engine(enabled=True)
    client._positions = []

    def _history_down(*_args: object, **_kwargs: object) -> list[object]:
        raise RuntimeError("history down")

    monkeypatch.setattr(engine.gateway.adapter, "history_deals", _history_down)
    intent = parse_order_intent(
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        volume="0.01",
        stop_loss="2319.00",
        take_profit="2324.00",
    )
    pipeline, _decision = engine.run_submit(
        user_id=uuid4(),
        request_id="eng-history",
        intent=intent,
        connected=True,
        login=1,
        recent_decisions=[],
    )
    reset_live_trading_controller_for_tests()
    assert pipeline.outcome == "rejected"
    assert "DEAL_HISTORY_UNAVAILABLE" in pipeline.message


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
