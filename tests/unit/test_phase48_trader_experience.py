"""Phase 48 — trader session payload, robot gates, no global fallback."""

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
from app.domain.exceptions.base import NotFoundError
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
@pytest.mark.asyncio
async def test_no_owned_account_does_not_select_another_account() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    other = uuid4()
    await seed_owned_mt5_connection(factory, other)
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=uuid4())
    assert snap["broker"] == "Disconnected"
    assert snap["account"] in {"", "—"}
    assert snap["execution_permitted"] is False
    assert snap["robot_blocked_reason"] == "BROKER_NOT_CONNECTED"
    assert snap["concurrent_live_sessions_supported"] is False
    assert snap.get("balance") in {None, ""}


@pytest.mark.unit
@pytest.mark.trading_core
def test_robot_running_uses_bound_owner_not_random_runtime_user() -> None:
    from app.application.services.trading_session import _robot_status

    owner = uuid4()
    other = uuid4()
    assert (
        _robot_status(
            owned=True,
            run_state="running",
            runtime_user=None,
            user_id=owner,
        )
        == "Running"
    )
    assert (
        _robot_status(
            owned=True,
            run_state="running",
            runtime_user=other,
            user_id=owner,
        )
        == "Stopped"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_robot_start_blocked_without_connection() -> None:
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
    assert exc.value.details.get("reason") == "not_connected"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_robot_pause_blocked_without_connection() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    with pytest.raises(NotFoundError):
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=uuid4(),
            role="trader",
            display_name="Trader",
            action="pause",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connected_session_is_safe_and_has_last_verified() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_id = uuid4()
    await seed_owned_mt5_connection(factory, user_id)
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    assert snap["broker"] == "Connected"
    assert snap["last_verified"]
    assert "password" not in snap
    assert "ciphertext" not in snap
    assert "token" not in snap
    assert "16785006" not in str(snap.get("account") or "")
    assert snap["concurrent_live_sessions_supported"] is False
    assert snap["robot_blocked_reason"] is None


@pytest.mark.unit
def test_research_and_promotion_remain_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_session_mismatch_constant_unchanged() -> None:
    assert ACCOUNT_SESSION_MISMATCH == "ACCOUNT_SESSION_MISMATCH"
