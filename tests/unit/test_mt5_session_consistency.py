"""MT5 session consistency — shared guard across status/book reads.

Does not weaken Safety, Risk, OMS, or leverage policy.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.mt5_session_guard import (
    ensure_live_mt5_session_for_user,
    require_live_mt5_connection,
    reset_session_heal_lock_for_tests,
    session_heal_count,
)
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.use_cases.mt5 import GetMT5StatusUseCase
from app.application.use_cases.portfolio import (
    GetHistoryUseCase,
    GetPortfolioUseCase,
    ListOrdersUseCase,
    ListPositionsUseCase,
)
from app.domain.entities.mt5 import MT5AccountInfo, MT5Connection
from app.domain.exceptions.base import NotFoundError, ServiceUnavailableError
from app.domain.interfaces.mt5_client import MT5HealthSnapshot
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.client import MockMT5Client
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.infrastructure.persistence.memory_portfolio import (
    MemoryPortfolioUnitOfWorkFactory,
)


@pytest.fixture(autouse=True)
def _reset_heal_lock() -> None:
    reset_session_heal_lock_for_tests()
    yield
    reset_session_heal_lock_for_tests()


@dataclass
class FakeGatewayClient:
    """Minimal gateway-backed client for session-guard tests."""

    stores_credentials_remotely: bool = True
    session_mode: str = "attached"
    session_token: str = "gw-live-token"
    delay_s: float = 0.0
    _connected: bool = True
    health_calls: int = 0
    attach_calls: int = 0
    _login: int = 16785006
    _server: str = "Weltrade-Real"

    @property
    def is_connected(self) -> bool:
        return self._connected

    def health(self) -> MT5HealthSnapshot:
        self.health_calls += 1
        if self.delay_s:
            time.sleep(self.delay_s)
        return MT5HealthSnapshot(
            connected=self._connected,
            latency_ms=1.2,
            terminal_build=6104,
            server=self._server,
            login_status="connected" if self._connected else "logged_out",
            version="5.0.6104",
        )

    def attach(self, *, path: str = "") -> bool:
        _ = path
        self.attach_calls += 1
        return self._connected

    def account_info(self) -> MT5AccountInfo:
        return MT5AccountInfo(
            login=self._login,
            name="QuantForg",
            server=self._server,
            currency="USD",
            leverage=2000,
            balance=Decimal("100.72"),
            equity=Decimal("100.72"),
        )

    def list_positions(self) -> list[object]:
        return []

    def position_by_ticket(self, ticket: int) -> object | None:
        _ = ticket
        return None

    def position_by_symbol(self, symbol: str) -> list[object]:
        _ = symbol
        return []

    def order_by_ticket(self, ticket: int) -> object | None:
        _ = ticket
        return None

    def list_orders(self) -> list[object]:
        return []

    def history_orders(self, **kwargs: object) -> list[object]:
        _ = kwargs
        return []

    def history_deals(self, **kwargs: object) -> list[object]:
        _ = kwargs
        return []

    def account_snapshot(self) -> object:
        from app.domain.entities.mt5_portfolio import AccountSnapshot

        return AccountSnapshot(
            login=self._login,
            server=self._server,
            currency="USD",
            leverage=2000,
            balance=Decimal("100.72"),
            equity=Decimal("100.72"),
            margin=Decimal("0"),
            free_margin=Decimal("100.72"),
            margin_level=Decimal("0"),
            profit=Decimal("0"),
        )


def _gateway_adapter() -> tuple[MemoryMT5UnitOfWorkFactory, MT5Adapter, FakeGatewayClient]:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    return factory, adapter, client


@pytest.mark.unit
@pytest.mark.asyncio
async def test_status_and_book_share_healed_session() -> None:
    factory, adapter, client = _gateway_adapter()
    user_id = uuid4()
    status = await GetMT5StatusUseCase(uow_factory=factory, adapter=adapter).execute(
        user_id=user_id
    )
    assert status.connected is True
    conn = await require_live_mt5_connection(factory, adapter, user_id)
    assert conn.session_ref == adapter._live_session_ref
    assert client.health_calls >= 1

    sync = PortfolioSyncService(adapter=adapter)
    positions = await ListPositionsUseCase(
        mt5_uow_factory=factory, sync_service=sync
    ).execute(user_id=user_id)
    orders = await ListOrdersUseCase(
        mt5_uow_factory=factory, sync_service=sync
    ).execute(user_id=user_id)
    history = await GetHistoryUseCase(
        mt5_uow_factory=factory, sync_service=sync
    ).execute(user_id=user_id)
    assert positions == []
    assert orders == []
    assert history.orders == []
    assert history.deals == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stale_db_uuid_remaps_instead_of_404() -> None:
    factory, adapter, _client = _gateway_adapter()
    user_id = uuid4()
    stale = MT5Connection.create(
        user_id=user_id, login=16785006, server="Weltrade-Real"
    )
    stale.mark_connected(session_ref="stale-db-uuid-from-previous-worker")
    async with factory() as uow:
        await uow.connections.upsert_for_user(stale)
        await uow.commit()

    conn = await require_live_mt5_connection(factory, adapter, user_id)
    assert conn.session_ref != "stale-db-uuid-from-previous-worker"
    assert adapter.is_live_session(conn.session_ref)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_reads_single_flight_heal() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient(delay_s=0.05)
    adapter = MT5Adapter(client=client)
    user_id = uuid4()
    results = await asyncio.gather(
        require_live_mt5_connection(factory, adapter, user_id),
        require_live_mt5_connection(factory, adapter, user_id),
        require_live_mt5_connection(factory, adapter, user_id),
    )
    assert all(r.connected for r in results)
    assert len({r.session_ref for r in results}) == 1
    assert session_heal_count() == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mock_without_session_still_404() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=MockMT5Client())
    with pytest.raises(NotFoundError, match="No active MT5 connection"):
        await require_live_mt5_connection(factory, adapter, uuid4())


@pytest.mark.unit
@pytest.mark.asyncio
async def test_gateway_mt5_disconnected_is_unavailable_not_false_404() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    client._connected = False
    adapter = MT5Adapter(client=client)
    with pytest.raises(ServiceUnavailableError) as exc:
        await require_live_mt5_connection(factory, adapter, uuid4())
    assert exc.value.code in {"MT5_UNAVAILABLE", "GATEWAY_UNAVAILABLE"}
    assert "No active MT5 connection" not in exc.value.message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_status_connected_false_when_gateway_down() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    client._connected = False
    adapter = MT5Adapter(client=client)
    status = await GetMT5StatusUseCase(uow_factory=factory, adapter=adapter).execute(
        user_id=uuid4()
    )
    assert status.connected is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_portfolio_uses_same_session_as_status() -> None:
    factory, adapter, _client = _gateway_adapter()
    user_id = uuid4()
    status = await GetMT5StatusUseCase(uow_factory=factory, adapter=adapter).execute(
        user_id=user_id
    )
    assert status.connected is True
    sync = PortfolioSyncService(adapter=adapter)
    dto = await GetPortfolioUseCase(
        mt5_uow_factory=factory,
        portfolio_uow_factory=MemoryPortfolioUnitOfWorkFactory(),
        sync_service=sync,
    ).execute(user_id=user_id)
    assert dto.position_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_process_live_handle_skips_second_heal() -> None:
    factory, adapter, client = _gateway_adapter()
    user_id = uuid4()
    first = await ensure_live_mt5_session_for_user(factory, adapter, user_id)
    assert first is not None
    heals = session_heal_count()
    calls = client.health_calls
    second = await ensure_live_mt5_session_for_user(factory, adapter, user_id)
    assert second is not None
    assert session_heal_count() == heals
    assert client.health_calls == calls
