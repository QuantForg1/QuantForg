"""Unit tests for MT5 Gateway — no live MetaTrader5 required."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.mt5_gateway.main import create_app
from services.mt5_gateway.runtime import LiveMT5Bridge, MT5GatewayRuntime
from services.mt5_gateway.settings import MT5GatewaySettings, get_gateway_settings


class _FakeBridge(LiveMT5Bridge):
    def __init__(self) -> None:
        self._mt5 = object()
        self._import_error: str | None = None
        self._initialized = False
        self._logged_in = False
        self._login = 0
        self._server = ""

    def initialize(self, path: str = "") -> bool:
        _ = path
        self._initialized = True
        return True

    def login(self, login: int, password: str, server: str) -> bool:
        _ = password
        if not self._initialized:
            return False
        self._logged_in = True
        self._login = login
        self._server = server
        return True

    def shutdown(self) -> None:
        self._logged_in = False
        self._initialized = False

    def last_error(self) -> Any:
        return (1, "fake")

    def account_info(self) -> Any:
        if not self._logged_in:
            return None
        return SimpleNamespace(
            login=self._login,
            balance=1000.0,
            equity=1005.0,
            margin=10.0,
            margin_free=990.0,
            margin_level=10050.0,
            profit=5.0,
            leverage=100,
            currency="USD",
            server=self._server,
            name="Demo",
        )

    def terminal_info(self) -> Any:
        return SimpleNamespace(build=4000)

    def version(self) -> tuple[int, int, int]:
        return (5, 0, 4000)

    def symbols_get(self) -> Any:
        return [SimpleNamespace(name="EURUSD", description="Euro", digits=5)]

    def symbol_info_tick(self, symbol: str) -> Any:
        _ = symbol
        return SimpleNamespace(bid=1.1, ask=1.2, time=1_700_000_000)

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        _ = symbol, timeframe, start_pos, count
        return [
            {
                "time": 1_700_000_000,
                "open": 1.1,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
            }
        ]

    def positions_get(self) -> Any:
        return []

    def orders_get(self) -> Any:
        return []

    def history_orders_get(self, date_from: Any, date_to: Any) -> Any:
        _ = date_from, date_to
        return []

    def history_deals_get(self, date_from: Any, date_to: Any) -> Any:
        _ = date_from, date_to
        return []


@pytest.fixture
def gateway_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[MT5GatewaySettings]:
    monkeypatch.setenv("MT5_GATEWAY_TOKEN", "test-gateway-token")
    monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
    get_gateway_settings.cache_clear()
    settings = get_gateway_settings()
    yield settings
    get_gateway_settings.cache_clear()


@pytest.fixture
def client(gateway_env: MT5GatewaySettings) -> Iterator[TestClient]:
    _ = gateway_env
    app = create_app()
    with TestClient(app) as test_client:
        existing = getattr(test_client.app.state, "runtime", None)
        if existing is not None:
            existing.stop_background()
        fake = MT5GatewayRuntime(
            settings=get_gateway_settings(), bridge=_FakeBridge()
        )
        test_client.app.state.runtime = fake
        yield test_client


@pytest.mark.unit
class TestMT5Gateway:
    def test_health_open(self, client: TestClient) -> None:
        res = client.get("/health")
        assert res.status_code == 200
        body = res.json()
        assert body["service"] == "mt5-gateway"
        assert body["token_configured"] is True

    def test_requires_token(self, client: TestClient) -> None:
        res = client.get("/account")
        assert res.status_code == 401

    def test_connect_and_account_sync(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        res = client.post(
            "/session/connect",
            headers=headers,
            json={
                "login": 12345,
                "password": "secret",
                "server": "Demo-Server",
            },
        )
        assert res.status_code == 200
        assert res.json()["connected"] is True
        assert "password" not in res.json()

        acct = client.get("/account", headers=headers)
        assert acct.status_code == 200
        assert acct.json()["currency"] == "USD"
        assert acct.json()["login"] == 12345

        quotes = client.get("/quotes/EURUSD", headers=headers)
        assert quotes.status_code == 200
        assert "bid" in quotes.json()

        candles = client.get("/candles/EURUSD", headers=headers)
        assert candles.status_code == 200
        assert candles.json()["items"]

        assert client.get("/positions", headers=headers).status_code == 200
        assert client.get("/orders", headers=headers).status_code == 200
        assert client.get("/history/deals", headers=headers).status_code == 200

        diag = client.get("/diagnostics", headers=headers)
        assert diag.status_code == 200
        assert diag.json()["credentials_in_memory"] is True
        assert "Railway" in diag.json()["credentials_note"]

        hb = client.get("/heartbeat", headers=headers)
        assert hb.status_code == 200
        assert hb.json()["ok"] is True

    def test_x_gateway_token_header(self, client: TestClient) -> None:
        headers = {"X-Gateway-Token": "test-gateway-token"}
        res = client.get("/session/status", headers=headers)
        assert res.status_code == 200
