"""Unit tests — Weltrade bridge / GatewayMT5Client (no live network)."""

from __future__ import annotations

from typing import Any

import pytest

from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.interfaces.mt5_client import MT5LoginRequest
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.client import MockMT5Client
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client


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

    def test_connect_prefer_attach(self) -> None:
        from uuid import uuid4

        client = _StubGateway()
        adapter = MT5Adapter(client=client)
        svc = WeltradeIntegrationService(adapter=adapter)
        result = svc.connect(
            user_id=uuid4(),
            login=4242,
            password="",
            server="auto",
            account_type="demo",
            prefer_attach=True,
        )
        assert result["ok"] is True
        assert result["dashboard"]["connection"]["mt5_connected"] is True
        # Adapter must not retain broker password
        for req in adapter._sessions.values():
            assert req.password == ""

    def test_adapter_redacts_password_for_gateway_client(self) -> None:
        client = _StubGateway()
        client._fail_attach = True
        adapter = MT5Adapter(client=client)
        assert adapter.initialize()
        ref = adapter.login(
            MT5LoginRequest(login=7, password="never-store", server="Weltrade-MT5")
        )
        assert adapter._sessions[ref].password == ""
