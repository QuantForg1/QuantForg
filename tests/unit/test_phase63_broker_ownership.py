"""Phase 63b — broker connect ownership verification (no global fallback)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.entities.mt5 import MT5Connection
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.broker_trader_errors import (
    classify_broker_connect_error,
)


class _Account:
    def __init__(self, login: int, server: str = "Weltrade-Real") -> None:
        self.login = login
        self.server = server


class _FakeAdapter:
    def __init__(self, *, live_login: int) -> None:
        self._live_login = live_login
        self._live_session_ref = "sess-live"
        self._sessions = {
            "sess-live": type(
                "S",
                (),
                {"login": live_login, "server": "Weltrade-Real"},
            )()
        }
        self.client = type(
            "C",
            (),
            {
                "is_connected": True,
                "session_token": "sess-live",
                "_login": live_login,
                "stores_credentials_remotely": True,
            },
        )()
        self._shutdown = False

    def account_info(self) -> _Account:
        return _Account(self._live_login)

    def health(self) -> object:
        return type(
            "H",
            (),
            {"terminal_build": 1, "version": "1", "latency_ms": 1.0},
        )()

    def terminal_info(self) -> object:
        return type("T", (), {"build": 1})()

    def is_live_session(self, ref: str) -> bool:
        return ref == self._live_session_ref and not self._shutdown

    def attach(self, *, path: str = "") -> str:
        return self._live_session_ref

    def shutdown(self) -> None:
        self._shutdown = True
        self.client.is_connected = False  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset_bind() -> None:
    reset_execution_binding_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bind_user_session_rejects_claimed_vs_live_mismatch() -> None:
    user = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=11111111),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    bound = await svc.bind_user_session(
        user_id=user,
        login=22222222,
        server="Weltrade-Real",
        session_ref="sess-live",
    )
    assert bound is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bind_user_session_uses_live_login_identity() -> None:
    user = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=33333333),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    bound = await svc.bind_user_session(
        user_id=user,
        login=33333333,
        server="Weltrade-Real",
        session_ref="sess-live",
    )
    assert bound == "sess-live"
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(user)
    assert row is not None
    assert int(row.login) == 33333333


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_user_session_bound_does_not_steal_for_unbound_user() -> None:
    stranger = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=44444444),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=stranger)
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(stranger)
    assert row is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owner_adopts_live_gateway_when_unbound() -> None:
    owner = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=66666666),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=owner, role="owner")
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(owner)
    assert row is not None
    assert int(row.login) == 66666666
    assert row.connected is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trader_role_does_not_adopt_unbound_gateway() -> None:
    trader = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=77777777),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=trader, role="trader")
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(trader)
    assert row is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owner_adopt_does_not_steal_other_users_login() -> None:
    owner = uuid4()
    other = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    async with factory() as uow:
        claimed = MT5Connection.create(
            user_id=other,
            login=88888888,
            server="Weltrade-Real",
            terminal_path="",
        )
        claimed.mark_connected(session_ref="sess-live")
        await uow.connections.upsert_for_user(claimed)
        await uow.commit()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=88888888),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=owner, role="owner")
    async with factory() as uow:
        owner_row = await uow.connections.get_active_for_user(owner)
        other_row = await uow.connections.get_active_for_user(other)
    assert owner_row is None
    assert other_row is not None
    assert int(other_row.login) == 88888888


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_user_session_bound_heals_matching_owner() -> None:
    owner = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    async with factory() as uow:
        conn = MT5Connection.create(
            user_id=owner,
            login=55555555,
            server="Weltrade-Real",
            terminal_path="",
        )
        conn.mark_connected(session_ref="stale-ref")
        await uow.connections.upsert_for_user(conn)
        await uow.commit()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=55555555),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=owner)
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(owner)
    assert row is not None
    assert (row.session_ref or "").startswith("sess")


@pytest.mark.unit
def test_connect_error_classifier_maps_different_account() -> None:
    cls, code, _msg = classify_broker_connect_error(
        RuntimeError(
            "ACCOUNT_SESSION_MISMATCH: The gateway MT5 session belongs "
            "to a different account."
        )
    )
    assert code == ACCOUNT_SESSION_MISMATCH
    assert cls.__name__ == "ConflictError"


@pytest.mark.unit
def test_no_global_account_fallback_and_cross_account_blocked() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=99990001)
    assert submit_blocked_reason(user_id=user_b, login=99990001) == (
        ACCOUNT_SESSION_MISMATCH
    )
