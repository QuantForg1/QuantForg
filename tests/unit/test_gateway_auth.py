"""Unit tests — gateway token normalize / auth (no live MT5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.mt5_gateway.main import create_app
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.settings import get_gateway_settings
from services.mt5_gateway.token_util import (
    mask_gateway_token,
    normalize_gateway_token,
    parse_authorization_bearer,
    tokens_equal,
)
from tests.unit.test_mt5_gateway import _FakeBridge


@pytest.mark.unit
class TestGatewayTokenUtil:
    def test_normalize_strips_bom_cr_quotes(self) -> None:
        raw = '\ufeff"secret-token-value"\r\n'
        assert normalize_gateway_token(raw) == "secret-token-value"

    def test_tokens_equal_ignores_whitespace_and_bom(self) -> None:
        assert tokens_equal("\ufeffabc123def456\r", " abc123def456 ")
        assert not tokens_equal("abc123def456", "abc123def457")
        assert not tokens_equal("short", "much-longer-token")

    def test_mask_preview(self) -> None:
        raw = "QuantForgTokenQw8Rt5"
        masked = mask_gateway_token(raw)
        assert masked == "QuantF******Qw8Rt5"
        assert "******" in masked

    def test_parse_authorization_bearer(self) -> None:
        assert parse_authorization_bearer("Bearer  abc\r") == "abc"
        assert parse_authorization_bearer("bearer xyz") == "xyz"
        assert parse_authorization_bearer("Token xyz") == ""
        assert parse_authorization_bearer(None) == ""


@pytest.mark.unit
class TestGatewayAuthHardening:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        token = "HardenedGatewayToken99"
        env_path = tmp_path / ".env"
        # File has the real token; process env has a stale conflicting value.
        env_path.write_text(
            f"MT5_GATEWAY_TOKEN={token}\nMT5_GATEWAY_ENABLE_WEBSOCKET=false\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("MT5_GATEWAY_TOKEN", "STALE-WRONG-TOKEN-VALUE-XX")
        monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
        monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "false")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "services.mt5_gateway.settings.gateway_env_file_candidates",
            lambda: [env_path],
        )
        get_gateway_settings.cache_clear()
        app = create_app()
        with TestClient(app) as test_client:
            existing = getattr(test_client.app.state, "runtime", None)
            if existing is not None:
                existing.stop_background()
            fake = MT5GatewayRuntime(
                settings=get_gateway_settings(),
                bridge=_FakeBridge(prelogged=True),
            )
            test_client.app.state.runtime = fake
            yield test_client, token
        get_gateway_settings.cache_clear()

    def test_prefers_dotenv_over_stale_process_env(
        self, client: tuple[TestClient, str]
    ) -> None:
        http, token = client
        health = http.get("/health")
        assert health.status_code == 200
        preview = health.json()["token_fingerprint"]["preview"]
        assert preview == mask_gateway_token(token)

        # Bearer matching the .env file succeeds even though process env differs.
        status = http.get(
            "/session/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status.status_code == 200

        # Stale process-env token must fail.
        bad = http.get(
            "/session/status",
            headers={"Authorization": "Bearer STALE-WRONG-TOKEN-VALUE-XX"},
        )
        assert bad.status_code == 401

    def test_bearer_with_trailing_whitespace(
        self, client: tuple[TestClient, str]
    ) -> None:
        http, token = client
        res = http.get(
            "/session/status",
            headers={"Authorization": f"Bearer {token}  "},
        )
        assert res.status_code == 200

    def test_session_attach_and_connect_share_auth(
        self, client: tuple[TestClient, str]
    ) -> None:
        http, token = client
        headers = {"Authorization": f"Bearer {token}"}
        assert http.get("/session/status", headers=headers).status_code == 200
        assert (
            http.post("/session/attach", headers=headers, json={"path": ""}).status_code
            == 200
        )
        assert (
            http.post(
                "/session/connect",
                headers=headers,
                json={
                    "login": 1,
                    "password": "x",
                    "server": "Demo",
                },
            ).status_code
            == 200
        )
