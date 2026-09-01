"""Session GET stays fail-closed without 500s; no live-trading bypass."""

from __future__ import annotations

from collections.abc import Iterator
from uuid import uuid4

import pytest

from app.application.services.account_execution_gate import (
    reset_execution_binding_for_tests,
)
from app.application.services.trading_session import GetTradingSessionUseCase
from app.domain.institutional_trading.live_trading_control import recover_after_restart
from app.domain.institutional_trading.operations.control_plane import (
    reset_control_plane_for_tests,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from tests.unit.test_mt5_session_consistency import FakeGatewayClient


@pytest.fixture(autouse=True)
def _reset_plane_and_binding() -> Iterator[None]:
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    yield
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_survives_ensure_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("gateway attach failed")

    monkeypatch.setattr(
        "app.application.services.trading_session.ensure_live_mt5_session_for_user",
        boom,
    )
    snap = await GetTradingSessionUseCase(
        uow_factory=MemoryMT5UnitOfWorkFactory(),
        adapter=MT5Adapter(client=FakeGatewayClient()),
    ).execute(user_id=uuid4())
    assert snap["owned"] is False
    assert snap["execution_permitted"] is False
    assert snap["trading"] == "Disabled"
    blob = str(snap).lower()
    assert "password" not in blob
    assert "ciphertext" not in blob


@pytest.mark.unit
def test_restart_never_restores_enabled_live_trading() -> None:
    assert recover_after_restart("ENABLED") == "PAUSED"
    assert recover_after_restart("LIVE_ENABLED") == "PAUSED"
    assert recover_after_restart("PAUSED") == "PAUSED"
    assert recover_after_restart("DISABLED") == "DISABLED"
