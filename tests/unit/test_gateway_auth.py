"""Unit tests — gateway token normalize / auth (no live MT5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.mt5_gateway.main import create_app
from services.mt5_gateway.runtime import MT5GatewayRuntime
from services.mt5_gateway.settings import (
    _PLACEHOLDER_TOKEN,
    get_gateway_settings,
)
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
        assert parse_authorization_bearer("\ufeffBearer secret") == "secret"

    def test_normalize_strips_invisible_middle_chars(self) -> None:
        # Soft hyphen / zero-width in the middle keep first/last-6 masks identical
        # while breaking naive compares — normalize must remove them.
        clean = "QuantForgTokenValueWithFortyThree!!Qw8Rt5"
        dirty = "QuantForgTokenValueWith\u00adFortyThree!!Qw8Rt5"
        assert mask_gateway_token(clean) == mask_gateway_token(dirty)
        assert tokens_equal(clean, dirty)

    def test_placeholder_is_exactly_32_chars(self) -> None:
        assert len(_PLACEHOLDER_TOKEN) == 32


@pytest.mark.unit
class TestGatewayAuthHardening:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        token = "HardenedGatewayToken99"
        env_path = tmp_path / ".env"
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
        fp = health.json()["token_fingerprint"]
        assert fp["preview"] == mask_gateway_token(token)
        assert fp["source"].startswith("dotenv:")
        assert fp["length"] == len(token)

        status = http.get(
            "/session/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status.status_code == 200

        bad = http.get(
            "/session/status",
            headers={"Authorization": "Bearer STALE-WRONG-TOKEN-VALUE-XX"},
        )
        assert bad.status_code == 401

    def test_accepts_x_gateway_token_when_authorization_is_wrong(
        self, client: tuple[TestClient, str]
    ) -> None:
        """Tunnel proxies may rewrite Authorization; X-Gateway-Token must still win."""
        http, token = client
        res = http.get(
            "/session/status",
            headers={
                "Authorization": "Bearer WRONG-TOKEN-BUT-SAME-LENGTH-XXXXXX",
                "X-Gateway-Token": token,
            },
        )
        assert res.status_code == 200

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


@pytest.mark.unit
class TestPlaceholderVsRealDotenv:
    def test_ignores_32_char_placeholder_process_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """expected_len=32 was the example placeholder; real token is ~43 chars."""
        import secrets

        real = secrets.token_urlsafe(32)
        assert len(real) == 43
        assert len(_PLACEHOLDER_TOKEN) == 32

        env_path = tmp_path / ".env"
        env_path.write_text(
            f"MT5_GATEWAY_TOKEN={real}\nMT5_GATEWAY_ENABLE_WEBSOCKET=false\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("MT5_GATEWAY_TOKEN", _PLACEHOLDER_TOKEN)
        monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
        monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "false")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(
            "services.mt5_gateway.settings.gateway_env_file_candidates",
            lambda: [env_path],
        )
        get_gateway_settings.cache_clear()
        try:
            app = create_app()
            with TestClient(app) as http:
                existing = getattr(http.app.state, "runtime", None)
                if existing is not None:
                    existing.stop_background()
                http.app.state.runtime = MT5GatewayRuntime(
                    settings=get_gateway_settings(),
                    bridge=_FakeBridge(prelogged=True),
                )
                health = http.get("/health").json()
                fp = health["token_fingerprint"]
                assert fp["length"] == 43
                assert fp["source"].startswith("dotenv:")
                assert fp["process_is_placeholder"] is True
                assert fp["process_env_len"] == 32
                assert fp["dotenv_len"] == 43

                ok = http.get(
                    "/session/status",
                    headers={"Authorization": f"Bearer {real}"},
                )
                assert ok.status_code == 200

                placeholder = http.get(
                    "/session/status",
                    headers={"Authorization": f"Bearer {_PLACEHOLDER_TOKEN}"},
                )
                assert placeholder.status_code == 401
        finally:
            get_gateway_settings.cache_clear()
