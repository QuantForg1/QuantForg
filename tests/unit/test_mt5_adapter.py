"""Unit tests for MT5 mock client and connection-layer adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.interfaces.broker_adapter import BrokerConnectRequest
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5 import MockMT5Client, MT5Adapter


@pytest.mark.unit
class TestMockMT5Client:
    def test_initialize_login_ping_shutdown(self) -> None:
        client = MockMT5Client()
        assert client.initialize(path="/mock/path") is True
        assert (
            client.login(
                MT5LoginRequest(login=123456, password="secret", server="Demo-Server")
            )
            is True
        )
        assert client.is_connected is True
        assert client.ping() == pytest.approx(4.5)
        terminal = client.terminal_info()
        assert terminal.build == 3815
        assert terminal.connected is True
        version = client.version()
        assert version == (5, 0, 3815)
        account = client.account_info()
        assert account.login == 123456
        assert account.server == "Demo-Server"
        symbols = client.symbols()
        assert any(s.code == "EURUSD" for s in symbols)
        health = client.health()
        assert health.connected is True
        assert health.terminal_build == 3815
        client.shutdown()
        assert client.is_connected is False

    def test_login_failure(self) -> None:
        client = MockMT5Client(fail_login=True)
        client.initialize()
        assert client.login(MT5LoginRequest(login=1, password="x", server="S")) is False

    def test_reconnect(self) -> None:
        client = MockMT5Client()
        req = MT5LoginRequest(login=99, password="p", server="S1")
        assert client.reconnect(req) is True
        assert client.is_connected is True


@pytest.mark.unit
class TestMT5Adapter:
    @pytest.mark.asyncio
    async def test_connect_disconnect_account_symbols(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        request = BrokerConnectRequest(
            broker_account_id=uuid4(),
            external_account_id="424242",
            server="Mock-Server",
            password="demo-pass",
        )
        session_ref = await adapter.connect(request)
        assert session_ref.startswith("mock-mt5-")
        assert adapter.ping() > 0
        assert adapter.terminal_info().build > 0
        assert adapter.version()[0] == 5
        info = await adapter.get_account_info(session_ref=session_ref)
        assert info.external_account_id == "424242"
        symbols = await adapter.get_symbols(session_ref=session_ref)
        assert len(symbols) >= 1
        health = adapter.health()
        assert health.connected is True
        await adapter.disconnect(session_ref=session_ref)
        assert adapter.client.is_connected is False

    @pytest.mark.asyncio
    async def test_orders_and_positions_read_only(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        request = BrokerConnectRequest(
            broker_account_id=uuid4(),
            external_account_id="1",
            server="S",
            password="p",
        )
        session_ref = await adapter.connect(request)
        positions = await adapter.get_positions(session_ref=session_ref)
        orders = await adapter.get_orders(session_ref=session_ref)
        assert len(positions) >= 1
        assert len(orders) >= 1
        assert positions[0].symbol
        assert orders[0].order_type

    @pytest.mark.asyncio
    async def test_validate_credentials(self) -> None:
        adapter = MT5Adapter(client=MockMT5Client())
        ok = await adapter.validate_credentials(
            BrokerConnectRequest(
                broker_account_id=uuid4(),
                external_account_id="55",
                server="Demo",
                password="ok",
            )
        )
        assert ok is True
        bad = MT5Adapter(client=MockMT5Client(fail_login=True))
        assert (
            await bad.validate_credentials(
                BrokerConnectRequest(
                    broker_account_id=uuid4(),
                    external_account_id="55",
                    server="Demo",
                    password="ok",
                )
            )
            is False
        )

    def test_discover_capabilities_includes_portfolio_reads(self) -> None:
        caps = {c.value for c in MT5Adapter().discover_capabilities()}
        assert "connect" in caps
        assert "symbols" in caps
        assert "account_info" in caps
        assert "orders" in caps
        assert "positions" in caps
        assert "history" in caps
