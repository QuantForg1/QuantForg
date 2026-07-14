"""Unit tests — Railway→Gateway transport (URL join, redirects, auth headers)."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.infrastructure.brokers.mt5.gateway_client import (
    GatewayMT5Client,
    classify_gateway_failure,
    join_gateway_url,
    normalize_gateway_base_url,
)


@pytest.mark.unit
class TestGatewayDiagnostics:
    def test_classify_common_failures(self) -> None:
        assert (
            classify_gateway_failure(status_code=401, cloudflare=True)
            == "Invalid Gateway Token"
        )
        assert classify_gateway_failure(status_code=403) == "403 Forbidden"
        assert classify_gateway_failure(status_code=404) == "404 Endpoint"
        assert (
            classify_gateway_failure(error="ConnectError connection refused")
            == "Gateway refused connection"
        )
        assert (
            classify_gateway_failure(
                error="timeout reading", cloudflare=True, error_type="ReadTimeout"
            )
            == "Cloudflare timeout"
        )
        assert (
            classify_gateway_failure(error="SSL: CERTIFICATE_VERIFY_FAILED")
            == "TLS failure"
        )
        assert (
            classify_gateway_failure(error="Too many redirects") == "Redirect loop"
        )
        assert (
            classify_gateway_failure(
                error="non-JSON body",
                error_type="JSONDecodeError",
            )
            == "JSON parse error"
        )


@pytest.mark.unit
class TestGatewayUrlHelpers:
    def test_normalize_strips_trailing_slash(self) -> None:
        assert (
            normalize_gateway_base_url("https://abc.trycloudflare.com/")
            == "https://abc.trycloudflare.com"
        )

    def test_normalize_requires_absolute_url(self) -> None:
        with pytest.raises(ValueError, match="absolute URL"):
            normalize_gateway_base_url("/health")

    def test_join_health_and_session_paths(self) -> None:
        base = "https://abc.trycloudflare.com"
        assert join_gateway_url(base, "/health") == "https://abc.trycloudflare.com/health"
        assert (
            join_gateway_url(base + "/", "/session/status")
            == "https://abc.trycloudflare.com/session/status"
        )
        assert (
            join_gateway_url(base, "session/connect")
            == "https://abc.trycloudflare.com/session/connect"
        )

    def test_join_does_not_drop_path_segment(self) -> None:
        # urljoin without trailing base slash historically ate last segments.
        base = "https://abc.trycloudflare.com/gw"
        assert (
            join_gateway_url(base, "/health") == "https://abc.trycloudflare.com/gw/health"
        )


@pytest.mark.unit
class TestGatewayHttpTransport:
    def test_follows_cloudflare_https_redirect(self) -> None:
        """httpx defaults to follow_redirects=False — Railway must enable it."""
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if request.url.path == "/health" and request.url.scheme == "http":
                return httpx.Response(
                    301,
                    headers={"Location": "https://tunnel.example/health"},
                )
            assert request.url.scheme == "https"
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "service": "mt5-gateway",
                    "bridge_available": True,
                    "token_configured": True,
                },
            )

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(
            base_url="http://tunnel.example",
            token="secret-token",
            timeout_seconds=5.0,
        )

        # Inject mock transport via monkeypatch of httpx.Client
        original = httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                kwargs.setdefault("follow_redirects", True)
                super().__init__(*args, **kwargs)

        import app.infrastructure.brokers.mt5.gateway_client as mod

        previous = mod.httpx.Client
        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            data = client.gateway_health()
        finally:
            mod.httpx.Client = previous  # type: ignore[misc]

        assert data["status"] == "ok"
        assert any(u.startswith("http://") for u in calls)
        assert any(u.startswith("https://") for u in calls)
        assert client.last_upstream().get("status_code") == 200

    def test_sends_both_auth_headers_on_protected_routes(self) -> None:
        seen: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["authorization"] = request.headers.get("authorization", "")
            seen["x-gateway-token"] = request.headers.get("x-gateway-token", "")
            return httpx.Response(
                200,
                json={
                    "connected": True,
                    "login": 1,
                    "server": "Weltrade-Demo",
                    "session_mode": "attached",
                    "health": {"latency_ms": 1.0, "login_status": "ok"},
                },
            )

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(
            base_url="https://tunnel.example",
            token="caller-secret",
            timeout_seconds=5.0,
        )

        import app.infrastructure.brokers.mt5.gateway_client as mod

        original = mod.httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            snap = client.health()
        finally:
            mod.httpx.Client = original  # type: ignore[misc]

        assert snap.connected is True
        assert seen["authorization"] == "Bearer caller-secret"
        assert seen["x-gateway-token"] == "caller-secret"

    def test_health_route_has_no_auth_header(self) -> None:
        seen_auth = {"present": False}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_auth["present"] = bool(
                request.headers.get("authorization")
                or request.headers.get("x-gateway-token")
            )
            return httpx.Response(200, json={"status": "ok", "bridge_available": True})

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(
            base_url="https://tunnel.example",
            token="caller-secret",
        )

        import app.infrastructure.brokers.mt5.gateway_client as mod

        original = mod.httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            client.gateway_health()
        finally:
            mod.httpx.Client = original  # type: ignore[misc]

        assert seen_auth["present"] is False

    def test_non_json_body_raises_exact_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>bad gateway</html>")

        transport = httpx.MockTransport(handler)
        client = GatewayMT5Client(base_url="https://tunnel.example", token="t")

        import app.infrastructure.brokers.mt5.gateway_client as mod

        original = mod.httpx.Client

        class PatchedClient(original):  # type: ignore[valid-type,misc]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        mod.httpx.Client = PatchedClient  # type: ignore[misc]
        try:
            with pytest.raises(RuntimeError, match="non-JSON"):
                client.gateway_health()
        finally:
            mod.httpx.Client = original  # type: ignore[misc]

        assert "non-JSON" in str(client.last_upstream().get("error", ""))
        assert client.last_upstream().get("body_preview")


@pytest.mark.unit
class TestWeltradeSurfacesUpstreamError:
    def test_health_includes_exact_upstream_message(self) -> None:
        from uuid import uuid4

        from app.application.services.weltrade_integration import (
            WeltradeIntegrationService,
        )
        from app.infrastructure.brokers.mt5.adapter import MT5Adapter

        class BoomGateway(GatewayMT5Client):
            def __init__(self) -> None:
                super().__init__(base_url="https://tunnel.example", token="tok")

            def gateway_health(self) -> dict[str, Any]:
                self._record_upstream(
                    {
                        "ok": False,
                        "url": "https://tunnel.example/health",
                        "error": (
                            "Gateway unreachable calling GET "
                            "https://tunnel.example/health: Connection refused"
                        ),
                    }
                )
                raise RuntimeError(
                    "Gateway unreachable calling GET "
                    "https://tunnel.example/health: Connection refused"
                )

        svc = WeltradeIntegrationService(adapter=MT5Adapter(client=BoomGateway()))
        out = svc.health(user_id=uuid4())
        assert out["gateway_online"] is False
        assert "Connection refused" in str(out["upstream_error"])
        assert out["detail"] == out["upstream_error"]
        assert out["configuration"]["mt5_gateway_base_url"] == "https://tunnel.example"
        assert out["configuration"]["mt5_gateway_caller_token_configured"] is True
