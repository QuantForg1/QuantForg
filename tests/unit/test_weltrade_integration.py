"""Unit tests — Weltrade bridge / GatewayMT5Client (no live network)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.client import MockMT5Client
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory


class _StubGateway(GatewayMT5Client):
    def __init__(self) -> None:
        super().__init__(base_url="http://gateway.test:8765", token="tok")
        self.calls: list[tuple[str, str]] = []
        self._account_login = 4242
        self._fail_attach = False

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        _ = auth, params
        self.calls.append((method, path))
        if path == "/health":
            return {"status": "ok", "bridge_available": True, "service": "mt5-gateway"}
        if path == "/session/attach":
            if self._fail_attach:
                raise RuntimeError("no session")
            self._connected = True
            self._login = self._account_login
            self._server = "Weltrade-Demo"
            self._session_mode = "attached"
            return {
                "connected": True,
                "session_mode": "attached",
                "login": self._account_login,
                "server": "Weltrade-Demo",
            }
        if path == "/session/connect":
            assert json_body is not None
            assert "password" in json_body
            self._connected = True
            self._login = int(json_body["login"])
            self._server = str(json_body["server"])
            self._session_mode = "connected"
            return {
                "connected": True,
                "session_mode": "connected",
                "login": self._login,
                "server": self._server,
            }
        if path == "/session/disconnect":
            self._connected = False
            return {"connected": False}
        if path == "/session/status":
            return {
                "connected": self._connected,
                "login": self._login,
                "server": self._server,
                "session_mode": self._session_mode,
                "health": {
                    "connected": self._connected,
                    "latency_ms": 12.5,
                    "login_status": "ok",
                    "version": "5.0.4000",
                    "terminal_build": 4000,
                },
            }
        if path == "/account":
            return {
                "login": self._login,
                "balance": "10000",
                "equity": "10010",
                "margin": "100",
                "free_margin": "9900",
                "margin_level": "10010",
                "profit": "10",
                "leverage": 100,
                "currency": "USD",
                "server": self._server,
                "name": "Weltrade Demo",
            }
        if path == "/positions":
            return {"items": []}
        if path == "/orders":
            return {"items": []}
        if path == "/history/deals":
            return {"items": []}
        if path == "/diagnostics":
            return {"connected": True, "password_in_memory": False}
        if path == "/heartbeat":
            return {"ok": True, "ping_ms": 11.0}
        if path.startswith("/quotes/"):
            return {"symbol": "EURUSD", "bid": "1.1", "ask": "1.2", "time": 1}
        if path == "/symbols":
            return {"items": [{"code": "EURUSD", "description": "Euro", "digits": 5}]}
        raise RuntimeError(f"unexpected {method} {path}")


@pytest.mark.unit
class TestGatewayMT5Client:
    def test_attach_does_not_send_password(self) -> None:
        client = _StubGateway()
        assert client.initialize()
        assert client.attach()
        assert ("POST", "/session/attach") in client.calls
        assert client.stores_credentials_remotely is True

    def test_login_forwards_once(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        assert client.initialize()
        ok = client.login(
            MT5LoginRequest(login=99, password="secret", server="Weltrade-Demo")
        )
        assert ok
        assert ("POST", "/session/connect") in client.calls


@pytest.mark.unit
class TestWeltradeIntegration:
    def test_profile_weltrade_only(self) -> None:
        svc = WeltradeIntegrationService(adapter=MT5Adapter(client=MockMT5Client()))
        profile = svc.profile()
        assert profile["broker"] == "weltrade"
        assert profile["gateway_backed"] is False

    @pytest.mark.asyncio
    async def test_connect_prefer_attach_binds_db_session(self) -> None:
        client = _StubGateway()
        adapter = MT5Adapter(client=client)
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
        user_id = uuid4()
        result = await svc.connect(
            user_id=user_id,
            login=4242,
            password="",
            server="auto",
            account_type="demo",
            prefer_attach=True,
        )
        assert result["ok"] is True
        assert result["dashboard"]["connection"]["mt5_connected"] is True
        for req in adapter._sessions.values():
            assert req.password == ""
        async with factory() as uow:
            conn = await uow.connections.get_active_for_user(user_id)
        assert conn is not None
        assert conn.connected is True
        assert conn.login == 4242
        assert adapter.is_live_session(conn.session_ref)

    def test_adapter_redacts_password_for_gateway_client(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        adapter = MT5Adapter(client=client)
        assert adapter.initialize()
        ref = adapter.login(
            MT5LoginRequest(login=7, password="never-store", server="Weltrade-MT5")
        )
        assert adapter._sessions[ref].password == ""

    @pytest.mark.asyncio
    async def test_health_reports_gateway(self) -> None:
        client = _StubGateway()
        assert client.attach()
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(
            adapter=MT5Adapter(client=client), uow_factory=factory
        )
        svc.adapter.attach()
        out = await svc.health(user_id=uuid4())
        assert out["gateway_reachable"] is True
        assert out["tunnel_reachable"] is True
        assert out["mt5_attached"] is True
        assert out["weltrade_connected"] is True
        assert out["account"] is not None
        assert out["account"]["login"] == 4242

    @pytest.mark.asyncio
    async def test_ensure_binds_when_gateway_live_without_session_ref(self) -> None:
        """After process restart: gateway connected, no local session_ref yet."""
        client = _StubGateway()
        client._account_login = 12260878
        # Simulate gateway-live state without an adapter session handle.
        client._connected = True
        client._login = 12260878
        client._server = "Weltrade-Real"
        client._session_token = ""
        adapter = MT5Adapter(client=client)
        adapter._live_session_ref = None
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
        user_id = uuid4()
        await svc.ensure_user_session_bound(user_id=user_id)
        async with factory() as uow:
            conn = await uow.connections.get_active_for_user(user_id)
        assert conn is not None
        assert conn.connected is True
        assert conn.login == 12260878
        assert adapter.is_live_session(conn.session_ref)
        assert ("POST", "/session/attach") in client.calls

        from types import SimpleNamespace

        from app.presentation.dependencies.weltrade import get_weltrade_service
        from core.di import container as container_mod

        adapter = MT5Adapter(client=_StubGateway())
        fake = SimpleNamespace(
            mt5_adapter=adapter,
            weltrade_integration=None,
            mt5_uow_factory=MemoryMT5UnitOfWorkFactory(),
        )
        previous = container_mod._container
        container_mod._container = fake  # type: ignore[assignment]
        try:
            svc = get_weltrade_service()
            assert isinstance(svc, WeltradeIntegrationService)
            assert fake.weltrade_integration is svc
            assert svc.uow_factory is fake.mt5_uow_factory
        finally:
            container_mod._container = previous
