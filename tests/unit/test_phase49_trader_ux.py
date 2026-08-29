"""Phase 49 — trader-safe broker errors, session contract, research wall."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    reset_execution_binding_for_tests,
)
from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
)
from app.domain.exceptions.base import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.domain.institutional_trading.operations.control_plane import (
    reset_control_plane_for_tests,
)
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.broker_trader_errors import (
    CONNECTION_FAILED,
    GATEWAY_UNAVAILABLE,
    INVALID_CREDENTIALS,
    TRADER_BROKER_MESSAGES,
    classify_broker_connect_error,
)
from tests.unit.test_mt5_session_consistency import (
    FakeGatewayClient,
    seed_owned_mt5_connection,
)


@pytest.fixture(autouse=True)
def _reset_plane_and_binding() -> Iterator[None]:
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    yield
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()


@pytest.mark.unit
def test_trader_connect_errors_never_echo_gateway_text() -> None:
    cls, code, message = classify_broker_connect_error(
        RuntimeError("gateway TCP 503 traceback password=hunter2")
    )
    assert cls is ServiceUnavailableError
    assert code == GATEWAY_UNAVAILABLE
    assert "traceback" not in message.lower()
    assert "hunter2" not in message
    assert "password=" not in message
    assert message == TRADER_BROKER_MESSAGES[GATEWAY_UNAVAILABLE]


@pytest.mark.unit
def test_invalid_credentials_are_explicit() -> None:
    cls, code, message = classify_broker_connect_error(
        ValueError("Invalid login / wrong password from MT5")
    )
    assert cls is ValidationError
    assert code == INVALID_CREDENTIALS
    assert message == TRADER_BROKER_MESSAGES[INVALID_CREDENTIALS]


@pytest.mark.unit
def test_unknown_failure_is_connection_failed() -> None:
    cls, code, message = classify_broker_connect_error(RuntimeError("weird internal"))
    assert cls is ServiceUnavailableError
    assert code == CONNECTION_FAILED
    assert message == TRADER_BROKER_MESSAGES[CONNECTION_FAILED]
    assert "weird internal" not in message


@pytest.mark.unit
def test_session_mismatch_classifier() -> None:
    cls, code, _message = classify_broker_connect_error(
        ConflictError("session mismatch", code="account_session_mismatch")
    )
    assert cls is ConflictError
    assert code == ACCOUNT_SESSION_MISMATCH


@pytest.mark.unit
@pytest.mark.asyncio
async def test_robot_start_uses_broker_not_connected_code() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    with pytest.raises(NotFoundError) as exc:
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=uuid4(),
            role="trader",
            display_name="Trader",
            action="start",
        )
    assert exc.value.code == "BROKER_NOT_CONNECTED"
    assert exc.value.details.get("reason") == "not_connected"
    assert "password" not in str(exc.value)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_payload_has_no_secrets_or_live_broker_claim() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_id = uuid4()
    await seed_owned_mt5_connection(factory, user_id)
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    blob = str(snap)
    assert "password" not in blob.lower()
    assert "ciphertext" not in blob.lower()
    assert snap.get("catalogue_source") != "LIVE_BROKER"
    assert snap["concurrent_live_sessions_supported"] is False


@pytest.mark.unit
def test_research_submit_order_still_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")
