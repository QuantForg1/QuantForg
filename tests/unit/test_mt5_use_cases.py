"""Unit tests for MT5 connection-layer use cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.mt5 import MT5ConnectCommand, MT5DisconnectCommand
from app.application.use_cases.mt5 import (
    ConnectMT5UseCase,
    DisconnectMT5UseCase,
    GetMT5AccountUseCase,
    GetMT5StatusUseCase,
    ListMT5SymbolsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


def _wire(
    *, fail_login: bool = False
) -> tuple[MemoryMT5UnitOfWorkFactory, MT5Adapter, RecordAuditEventUseCase]:
    mt5_factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    adapter = MT5Adapter(client=MockMT5Client(fail_login=fail_login))
    return mt5_factory, adapter, audit


@pytest.mark.unit
class TestMT5UseCases:
    @pytest.mark.asyncio
    async def test_connect_status_account_symbols_disconnect(self) -> None:
        factory, adapter, audit = _wire()
        user_id = uuid4()

        connected = await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_id,
                login=1001,
                password="secret",
                server="Demo-Server",
            )
        )
        assert connected.connected is True
        assert connected.login == 1001
        assert connected.terminal_build == 3815
        assert connected.terminal_version.startswith("5.")
        assert connected.latency_ms is not None
        assert connected.login_status == "logged_in"
        assert any(h["event"] == "connected" for h in connected.history)

        status = await GetMT5StatusUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_id)
        assert status.connected is True
        assert status.server == "Demo-Server"
        assert status.latency_ms is not None

        account = await GetMT5AccountUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_id)
        assert account.login == 1001
        assert account.currency == "USD"

        symbols = await ListMT5SymbolsUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_id)
        assert any(s.code == "EURUSD" for s in symbols)

        disconnected = await DisconnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(MT5DisconnectCommand(user_id=user_id))
        assert disconnected.connected is False
        assert disconnected.login_status == "logged_out"

    @pytest.mark.asyncio
    async def test_connect_failure(self) -> None:
        factory, adapter, audit = _wire(fail_login=True)
        with pytest.raises(ValidationError):
            await ConnectMT5UseCase(
                uow_factory=factory, adapter=adapter, audit=audit
            ).execute(
                MT5ConnectCommand(
                    user_id=uuid4(),
                    login=1,
                    password="x",
                    server="S",
                )
            )

    @pytest.mark.asyncio
    async def test_account_requires_connection(self) -> None:
        factory, adapter, _audit = _wire()
        with pytest.raises(NotFoundError):
            await GetMT5AccountUseCase(uow_factory=factory, adapter=adapter).execute(
                user_id=uuid4()
            )

    @pytest.mark.asyncio
    async def test_cross_tenant_terminal_isolation(self) -> None:
        """User A must not read terminal data after User B claims the process login."""
        factory, adapter, audit = _wire()
        user_a = uuid4()
        user_b = uuid4()

        await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_a,
                login=1001,
                password="secret-a",
                server="Demo-Server",
            )
        )
        account_a = await GetMT5AccountUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_a)
        assert account_a.login == 1001

        await ConnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(
            MT5ConnectCommand(
                user_id=user_b,
                login=2002,
                password="secret-b",
                server="Demo-Server",
            )
        )

        with pytest.raises(NotFoundError):
            await GetMT5AccountUseCase(uow_factory=factory, adapter=adapter).execute(
                user_id=user_a
            )

        account_b = await GetMT5AccountUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_b)
        assert account_b.login == 2002

        # Stale disconnect must not tear down the live tenant terminal.
        await DisconnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(MT5DisconnectCommand(user_id=user_a))
        assert adapter.client.is_connected is True
        account_b2 = await GetMT5AccountUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(user_id=user_b)
        assert account_b2.login == 2002

        # Disconnect with no connection must not shut down another tenant.
        await DisconnectMT5UseCase(
            uow_factory=factory, adapter=adapter, audit=audit
        ).execute(MT5DisconnectCommand(user_id=uuid4()))
        assert adapter.client.is_connected is True
