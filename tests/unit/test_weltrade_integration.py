"""Unit tests — Weltrade bridge / GatewayMT5Client (no live network)."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.auth import AuthUserDTO
from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.client import MockMT5Client
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.dependencies.auth import get_current_user
from app.presentation.dependencies.weltrade import get_weltrade_service
from app.presentation.routers import weltrade as weltrade_router


class _StubGateway(GatewayMT5Client):
    def __init__(self) -> None:
        super().__init__(base_url="http://gateway.test:8765", token="tok")
        self.calls: list[tuple[str, str]] = []
        self._account_login = 4242
        self._fail_attach = False
        self._fail_health = False
        self._fail_connect = False

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
            if self._fail_health:
                raise RuntimeError("gateway health unreachable")
            return {
                "status": "ok",
                "bridge_available": True,
                "service": "mt5-gateway",
                "token_configured": True,
                "connected": self._connected,
                "session_mode": self._session_mode,
                "server": self._server or None,
                "mt5": {
                    "connected": self._connected,
                    "session_mode": self._session_mode,
                    "server": self._server or None,
                    "login": self._login,
                    "bridge_available": True,
                },
            }
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
            if self._fail_connect:
                raise RuntimeError("broker rejected credentials")
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
        # Fresh stub is disconnected → status adopt misses → POST attach.
        assert ("GET", "/session/status") in client.calls
        assert ("POST", "/session/attach") in client.calls
        assert client.stores_credentials_remotely is True

    def test_attach_adopts_existing_connected_session_without_relogin(self) -> None:
        client = _StubGateway()
        client._connected = True
        client._login = 12260878
        client._server = "Weltrade-Real"
        client._session_mode = "attached"
        client._fail_attach = True  # POST /session/attach would fail
        assert client.initialize()
        assert client.attach()
        assert ("GET", "/session/status") in client.calls
        assert ("POST", "/session/attach") not in client.calls
        assert ("POST", "/session/connect") not in client.calls
        assert client.is_connected is True
        assert client._login == 12260878

    def test_login_skips_connect_when_session_already_attached(self) -> None:
        client = _StubGateway()
        client._connected = True
        client._login = 99
        client._server = "Weltrade-Real"
        client._session_mode = "attached"
        assert client.initialize()
        ok = client.login(
            MT5LoginRequest(login=99, password="secret", server="Weltrade-Real")
        )
        assert ok
        assert ("GET", "/session/status") in client.calls
        assert ("POST", "/session/connect") not in client.calls

    def test_login_forwards_once_when_disconnected(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        assert client.initialize()
        ok = client.login(
            MT5LoginRequest(login=99, password="secret", server="Weltrade-Demo")
        )
        assert ok
        assert ("GET", "/session/status") in client.calls
        assert ("POST", "/session/connect") in client.calls


@pytest.mark.unit
class TestWeltradeIntegration:
    def test_profile_weltrade_only(self) -> None:
        svc = WeltradeIntegrationService(adapter=MT5Adapter(client=MockMT5Client()))
        profile = svc.profile()
        assert profile["broker"] == "weltrade"
        assert profile["gateway_backed"] is False

    @pytest.mark.asyncio
    async def test_connect_reuses_already_attached_gateway_without_login(self) -> None:
        """Attached session → success without POST /session/connect."""
        client = _StubGateway()
        client._connected = True
        client._login = 12260878
        client._server = "Weltrade-Real"
        client._session_mode = "attached"
        client._fail_attach = True  # POST attach must not be required
        adapter = MT5Adapter(client=client)
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
        user_id = uuid4()
        result = await svc.connect(
            user_id=user_id,
            login=12260878,
            password="should-not-be-used",
            server="Weltrade-Real",
            account_type="live",
            prefer_attach=False,  # even with prefer_attach off, reuse wins
        )
        assert result["ok"] is True
        assert any(
            s.get("step") == "reuse_session" and s.get("ok") for s in result["steps"]
        )
        assert ("POST", "/session/connect") not in client.calls
        assert ("POST", "/session/attach") not in client.calls
        assert ("GET", "/session/status") in client.calls
        async with factory() as uow:
            conn = await uow.connections.get_active_for_user(user_id)
        assert conn is not None
        assert conn.connected is True

    @pytest.mark.asyncio
    async def test_connect_disconnected_gateway_performs_login(self) -> None:
        """Disconnected gateway → password login via POST /session/connect."""
        client = _StubGateway()
        client._fail_attach = True
        adapter = MT5Adapter(client=client)
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
        user_id = uuid4()
        result = await svc.connect(
            user_id=user_id,
            login=5555,
            password="broker-secret",
            server="Weltrade-Demo",
            account_type="demo",
            prefer_attach=True,
        )
        assert result["ok"] is True
        assert ("POST", "/session/connect") in client.calls
        assert any(s.get("step") == "connect" and s.get("ok") for s in result["steps"])
        async with factory() as uow:
            conn = await uow.connections.get_active_for_user(user_id)
        assert conn is not None
        assert conn.connected is True
        assert conn.login == 5555

    @pytest.mark.asyncio
    async def test_connect_attach_failure_logs_traceback(self) -> None:
        """Attach failure on disconnected gateway logs exception then logs in."""
        client = _StubGateway()
        client._fail_attach = True
        adapter = MT5Adapter(client=client)
        factory = MemoryMT5UnitOfWorkFactory()
        svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
        with patch(
            "app.application.services.weltrade_integration.logger"
        ) as mock_logger:
            result = await svc.connect(
                user_id=uuid4(),
                login=7777,
                password="broker-secret",
                server="Weltrade-Demo",
                account_type="demo",
                prefer_attach=True,
            )
        assert result["ok"] is True
        mock_logger.exception.assert_any_call(
            "weltrade_attach_unavailable",
            error="MT5 attach failed",
            login=7777,
            server="Weltrade-Demo",
        )

    @pytest.mark.asyncio
    async def test_connect_gateway_unavailable_raises_clear_error(self) -> None:
        client = _StubGateway()
        client._fail_health = True
        adapter = MT5Adapter(client=client)
        svc = WeltradeIntegrationService(
            adapter=adapter, uow_factory=MemoryMT5UnitOfWorkFactory()
        )
        with pytest.raises(RuntimeError, match="MT5 gateway unavailable") as exc_info:
            await svc.connect(
                user_id=uuid4(),
                login=1,
                password="x",
                server="Weltrade-Demo",
                account_type="demo",
            )
        assert "gateway health unreachable" in str(exc_info.value)

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

    def test_adapter_login_preserves_upstream_detail(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        client._fail_connect = True
        adapter = MT5Adapter(client=client)
        assert adapter.initialize()
        with pytest.raises(RuntimeError, match="MT5 login failed") as exc_info:
            adapter.login(
                MT5LoginRequest(login=7, password="bad", server="Weltrade-MT5")
            )
        assert "broker rejected credentials" in str(exc_info.value) or str(
            exc_info.value
        ).startswith("MT5 login failed")

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
        assert ("GET", "/session/status") in client.calls
        # Connected gateway is adopted via status; POST attach is not required.
        assert ("POST", "/session/connect") not in client.calls

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


@pytest.mark.unit
class TestWeltradeConnectHTTP:
    def _client_for(self, svc: WeltradeIntegrationService) -> TestClient:
        app = FastAPI()
        app.include_router(weltrade_router.router, prefix="/api/v1")

        async def _user() -> AuthUserDTO:
            return AuthUserDTO(
                id=uuid4(),
                email="test@example.com",
                display_name="Tester",
                role="trader",
                status="active",
                auth_user_id=uuid4(),
            )

        app.dependency_overrides[get_current_user] = _user
        app.dependency_overrides[get_weltrade_service] = lambda: svc
        return TestClient(app)

    def test_http_attached_session_returns_200_without_login(self) -> None:
        client = _StubGateway()
        client._connected = True
        client._login = 12260878
        client._server = "Weltrade-Real"
        client._session_mode = "attached"
        client._fail_attach = True
        svc = WeltradeIntegrationService(
            adapter=MT5Adapter(client=client),
            uow_factory=MemoryMT5UnitOfWorkFactory(),
        )
        http = self._client_for(svc)
        response = http.post(
            "/api/v1/weltrade/connect",
            json={
                "login": 12260878,
                "password": "unused",
                "server": "Weltrade-Real",
                "account_type": "live",
                "prefer_attach": True,
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["ok"] is True
        assert ("POST", "/session/connect") not in client.calls
        assert any(s.get("step") == "reuse_session" for s in body["steps"])

    def test_http_gateway_unavailable_returns_503_with_detail(self) -> None:
        client = _StubGateway()
        client._fail_health = True
        svc = WeltradeIntegrationService(
            adapter=MT5Adapter(client=client),
            uow_factory=MemoryMT5UnitOfWorkFactory(),
        )
        http = self._client_for(svc)
        response = http.post(
            "/api/v1/weltrade/connect",
            json={
                "login": 1,
                "password": "x",
                "server": "Weltrade-Demo",
                "account_type": "demo",
            },
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "MT5 gateway unavailable" in detail
        assert "gateway health unreachable" in detail

    def test_http_login_failure_preserves_original_error(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        client._fail_connect = True
        svc = WeltradeIntegrationService(
            adapter=MT5Adapter(client=client),
            uow_factory=MemoryMT5UnitOfWorkFactory(),
        )
        http = self._client_for(svc)
        response = http.post(
            "/api/v1/weltrade/connect",
            json={
                "login": 99,
                "password": "bad",
                "server": "Weltrade-Demo",
                "account_type": "demo",
                "prefer_attach": True,
            },
        )
        assert response.status_code == 503
        detail = response.json()["detail"]
        assert "Weltrade authentication failed" in detail
        assert "MT5 login failed" in detail
