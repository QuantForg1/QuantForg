"""Unit tests for MT5 Gateway — no live MetaTrader5 required."""

from __future__ import annotations

import time
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.mt5_gateway.main import create_app
from services.mt5_gateway.runtime import LiveMT5Bridge, MT5GatewayRuntime
from services.mt5_gateway.settings import MT5GatewaySettings, get_gateway_settings


class _FakeBridge(LiveMT5Bridge):
    def __init__(self, *, prelogged: bool = False) -> None:
        self._mt5 = object()
        self._import_error: str | None = None
        self._last_initialize_ok: bool | None = None
        self._last_initialize_error: Any | None = None
        self._last_initialize_path: str | None = None
        self._initialized = False
        self._logged_in = prelogged
        self._login = 99901 if prelogged else 0
        self._server = "XMGlobal-Demo" if prelogged else ""
        self.selected: list[str] = []
        self.login_calls = 0

    def _ensure_module(self) -> bool:
        return self._mt5 is not None

    def initialize(self, path: str = "") -> bool:
        _ = path
        self._initialized = True
        return True

    def login(self, login: int, password: str, server: str) -> bool:
        _ = password
        if not self._initialized:
            return False
        self.login_calls += 1
        self._logged_in = True
        self._login = login
        self._server = server
        return True

    def shutdown(self) -> None:
        self._logged_in = False
        self._initialized = False

    def last_error(self) -> Any:
        return (1, "fake")

    def require(self) -> Any:
        """Tests treat the fake bridge itself as the MetaTrader5 module surface."""
        return self

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        _ = enable
        self.selected.append(symbol)
        return True

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
        return SimpleNamespace(
            build=4000,
            trade_allowed=True,
            dlls_allowed=True,
        )

    def version(self) -> tuple[int, int, str]:
        return (5, 0, "4000")

    def symbols_get(self) -> Any:
        return [SimpleNamespace(name="EURUSD", description="Euro", digits=5)]

    def symbol_info_tick(self, symbol: str) -> Any:
        _ = symbol
        return SimpleNamespace(bid=1.1, ask=1.2, time=1_700_000_000)

    def symbol_info(self, symbol: str) -> Any:
        return SimpleNamespace(
            name=symbol,
            description="Euro",
            digits=5,
            point=0.00001,
            trade_contract_size=100000.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            volume_limit=0.0,
            trade_stops_level=0,
            trade_freeze_level=0,
            filling_mode=2,
            trade_mode=4,
            trade_exemode=2,
            trade_calc_mode=0,
            order_mode=127,
            visible=True,
            select=True,
            currency_base="EUR",
            currency_profit="USD",
            currency_margin="USD",
            swap_mode=0,
            session_deals=0,
            session_buy_orders=0,
            session_sell_orders=0,
            time=1_700_000_000,
        )

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
        return [
            SimpleNamespace(
                ticket=1,
                symbol="EURUSD",
                type=0,
                volume=0.1,
                price_open=1.1,
                price_current=1.11,
                profit=1.0,
            )
        ]

    def orders_get(self) -> Any:
        return []

    def history_orders_get(self, date_from: Any, date_to: Any) -> Any:
        _ = date_from, date_to
        return []

    def history_deals_get(self, date_from: Any, date_to: Any) -> Any:
        _ = date_from, date_to
        return [SimpleNamespace(ticket=9, symbol="EURUSD", profit=2.5, volume=0.1)]

    def order_check(self, request: dict[str, Any]) -> Any:
        filling = int(request.get("type_filling", -1))
        # Simulate brokers that reject IOC (1) with 10013 but accept FOK (0).
        # Success uses retcode 0 (common on live MT5) — must not be treated as falsy.
        if filling == 1:
            return SimpleNamespace(
                retcode=10013,
                comment="Invalid request",
                balance=1000.0,
                equity=1005.0,
                margin=10.0,
                margin_free=990.0,
                profit=0.0,
            )
        return SimpleNamespace(
            retcode=0,
            comment="Done",
            balance=1000.0,
            equity=1005.0,
            margin=10.0,
            margin_free=990.0,
            profit=0.0,
        )

    def order_send(self, request: dict[str, Any]) -> Any:
        check = self.order_check(request)
        if int(getattr(check, "retcode", 10013)) not in {0, 10009}:
            return SimpleNamespace(
                retcode=int(check.retcode),
                comment=str(check.comment),
                order=0,
                deal=0,
                volume=0.0,
                price=0.0,
                bid=0.0,
                ask=0.0,
            )
        return SimpleNamespace(
            retcode=10009,
            comment="Request executed",
            order=424242,
            deal=525252,
            volume=float(request.get("volume") or 0),
            price=float(request.get("price") or 0),
            bid=1.1,
            ask=1.2,
        )

    def order_calc_margin(
        self, order_type: int, symbol: str, volume: float, price: float
    ) -> Any:
        _ = order_type, symbol, volume, price
        return 10.0

    def order_calc_profit(
        self,
        order_type: int,
        symbol: str,
        volume: float,
        price_open: float,
        price_close: float,
    ) -> Any:
        _ = order_type, symbol, volume, price_open, price_close
        return 1.5


@pytest.fixture
def gateway_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[MT5GatewaySettings]:
    monkeypatch.setenv("MT5_GATEWAY_TOKEN", "test-gateway-token")
    monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
    monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "false")
    monkeypatch.setattr(
        "services.mt5_gateway.settings._read_token_from_dotenv_files",
        lambda: ("", ""),
    )
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
        fake = MT5GatewayRuntime(settings=get_gateway_settings(), bridge=_FakeBridge())
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
        assert body.get("gateway_version") == "1.1.7"
        assert body["auto_attach_enabled"] is False
        mt5 = body.get("mt5") or {}
        # No session yet — capabilities not probed (never invent Enabled).
        assert mt5.get("mt5_autotrading_enabled") is None
        assert mt5.get("dlls_allowed") is None
        support = mt5.get("capability_support") or {}
        assert support.get("autotrading") == "NOT_SUPPORTED"
        assert support.get("dll") == "NOT_SUPPORTED"

    def test_health_exposes_bridge_import_error_when_unavailable(
        self, gateway_env: MT5GatewaySettings, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _ = gateway_env

        class _BrokenBridge(LiveMT5Bridge):
            def __init__(self) -> None:
                self._mt5 = None
                self._import_error = (
                    "ModuleNotFoundError: No module named 'MetaTrader5'"
                )
                self._last_initialize_ok = None
                self._last_initialize_error = None
                self._last_initialize_path = None

            def _ensure_module(self) -> bool:
                return False

        app = create_app()
        with TestClient(app) as test_client:
            existing = getattr(test_client.app.state, "runtime", None)
            if existing is not None:
                existing.stop_background()
            runtime = MT5GatewayRuntime(
                settings=get_gateway_settings(), bridge=_BrokenBridge()
            )
            test_client.app.state.runtime = runtime
            res = test_client.get("/health")
            assert res.status_code == 200
            body = res.json()
            assert body["bridge_available"] is False
            assert "MetaTrader5" in (body.get("bridge_import_error") or "")
            assert body["mt5"]["bridge_available"] is False
            assert "MetaTrader5" in (body["mt5"].get("bridge_import_error") or "")

    def test_health_reports_terminal_capabilities_when_connected(
        self, client: TestClient
    ) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        res = client.post(
            "/session/connect",
            headers=headers,
            json={
                "login": 111,
                "password": "secret",
                "server": "Weltrade-Demo",
            },
        )
        assert res.status_code == 200
        health = client.get("/health")
        assert health.status_code == 200
        mt5 = health.json()["mt5"]
        assert mt5["connected"] is True
        # FakeBridge.terminal_info exposes trade_allowed / dlls_allowed.
        assert mt5.get("mt5_autotrading_enabled") is True
        assert mt5.get("dlls_allowed") is True
        support = mt5.get("capability_support") or {}
        assert support.get("autotrading") == "SUPPORTED"
        assert support.get("dll") == "SUPPORTED"

    def test_health_hints_when_token_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MT5_GATEWAY_TOKEN", raising=False)
        monkeypatch.setenv("MT5_GATEWAY_TOKEN", "")
        monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
        monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "false")
        monkeypatch.setattr(
            "services.mt5_gateway.settings._read_token_from_dotenv_files",
            lambda: ("", ""),
        )
        get_gateway_settings.cache_clear()
        app = create_app()
        with TestClient(app) as test_client:
            res = test_client.get("/health")
            assert res.status_code == 200
            body = res.json()
            assert body["token_configured"] is False
            assert "MT5_GATEWAY_TOKEN" in body["setup_hint"]
        get_gateway_settings.cache_clear()

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
        assert res.json()["session_mode"] == "connected"
        assert "password" not in res.json()

        acct = client.get("/account", headers=headers)
        assert acct.status_code == 200
        assert acct.json()["currency"] == "USD"
        assert acct.json()["login"] == 12345

        quotes = client.get("/quotes/EURUSD", headers=headers)
        assert quotes.status_code == 200
        assert "bid" in quotes.json()
        runtime = client.app.state.runtime
        assert "EURUSD" in runtime.bridge.selected

        candles = client.get("/candles/EURUSD", headers=headers)
        assert candles.status_code == 200
        assert candles.json()["items"]

        positions = client.get("/positions", headers=headers)
        assert positions.status_code == 200
        assert positions.json()["items"][0]["ticket"] == 1

        assert client.get("/orders", headers=headers).status_code == 200
        deals = client.get("/history/deals", headers=headers)
        assert deals.status_code == 200
        assert deals.json()["items"]

        diag = client.get("/diagnostics", headers=headers)
        assert diag.status_code == 200
        assert diag.json()["credentials_in_memory"] is True
        assert diag.json()["password_in_memory"] is True
        assert "Railway" in diag.json()["credentials_note"]

        hb = client.get("/heartbeat", headers=headers)
        assert hb.status_code == 200
        assert hb.json()["ok"] is True

    def test_attach_reuses_logged_in_terminal(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        runtime = client.app.state.runtime
        runtime.bridge = _FakeBridge(prelogged=True)

        res = client.post("/session/attach", headers=headers, json={})
        assert res.status_code == 200
        body = res.json()
        assert body["connected"] is True
        assert body["session_mode"] == "attached"
        assert body["login"] == 99901
        assert body["server"] == "XMGlobal-Demo"
        assert "password" not in body
        assert runtime.bridge.login_calls == 0

        acct = client.get("/account", headers=headers)
        assert acct.status_code == 200
        assert acct.json()["login"] == 99901
        assert acct.json()["session_mode"] == "attached"

        diag = client.get("/diagnostics", headers=headers)
        assert diag.json()["session_mode"] == "attached"
        assert diag.json()["password_in_memory"] is False

        quotes = client.get("/quotes/EURUSD", headers=headers)
        assert quotes.status_code == 200

    def test_attach_fails_without_terminal_session(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        res = client.post("/session/attach", headers=headers, json={})
        assert res.status_code == 503
        assert "no active account" in res.json()["detail"].lower()

    def test_auto_attach_on_startup(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MT5_GATEWAY_TOKEN", "test-gateway-token")
        monkeypatch.setenv("MT5_GATEWAY_ENABLE_WEBSOCKET", "false")
        monkeypatch.setenv("MT5_GATEWAY_AUTO_ATTACH", "true")
        monkeypatch.setattr(
            "services.mt5_gateway.settings._read_token_from_dotenv_files",
            lambda: ("", ""),
        )
        get_gateway_settings.cache_clear()

        prelogged = _FakeBridge(prelogged=True)
        original_init = MT5GatewayRuntime.__init__

        def _patched_init(self: MT5GatewayRuntime, *args: Any, **kwargs: Any) -> None:
            kwargs["bridge"] = prelogged
            original_init(self, *args, **kwargs)

        monkeypatch.setattr(MT5GatewayRuntime, "__init__", _patched_init)
        app = create_app()
        with TestClient(app) as test_client:
            headers = {"Authorization": "Bearer test-gateway-token"}
            status = test_client.get("/session/status", headers=headers)
            assert status.status_code == 200
            assert status.json()["connected"] is True
            assert status.json()["session_mode"] == "attached"
            assert status.json()["login"] == 99901
            acct = test_client.get("/account", headers=headers)
            assert acct.status_code == 200
        get_gateway_settings.cache_clear()

    def test_x_gateway_token_header(self, client: TestClient) -> None:
        headers = {"X-Gateway-Token": "test-gateway-token"}
        res = client.get("/session/status", headers=headers)
        assert res.status_code == 200

    def test_order_check_retries_filling_on_10013(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        runtime = client.app.state.runtime
        runtime.bridge = _FakeBridge(prelogged=True)
        runtime.diagnostics.connected = True
        connect = client.post("/session/attach", headers=headers, json={})
        assert connect.status_code == 200

        res = client.post(
            "/trade/order_check",
            headers=headers,
            json={"symbol": "EURUSD", "action": "buy", "volume": 0.01, "price": 0},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["retcode"] == 0
        # Primary pick is IOC (filling_mode=2); fake rejects IOC then accepts FOK.
        assert body["request"]["type_filling"] == 0
        assert body["request"]["price"] == 1.2  # ASK for buy
        assert any(a["retcode"] == 10013 for a in body.get("filling_attempts", []))
        assert any(a["retcode"] == 0 for a in body.get("filling_attempts", []))

    def test_order_send_live_after_check(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        runtime = client.app.state.runtime
        runtime.bridge = _FakeBridge(prelogged=True)
        runtime.diagnostics.connected = True
        assert (
            client.post("/session/attach", headers=headers, json={}).status_code == 200
        )

        res = client.post(
            "/trade/order_send",
            headers=headers,
            json={"symbol": "EURUSD", "action": "buy", "volume": 0.01},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["ok"] is True
        assert body["retcode"] == 10009
        assert body["order_ticket"] == 424242
        assert body["deal_ticket"] == 525252
        assert float(body["price"]) == 1.2


@pytest.mark.unit
class TestFillingModeSelection:
    def test_market_exec_defaults_to_return_when_no_flags(self) -> None:
        from services.mt5_gateway.trade import (
            ORDER_FILLING_RETURN,
            candidate_filling_modes,
        )

        info = SimpleNamespace(filling_mode=0, trade_exemode=2)
        assert candidate_filling_modes(info)[0] == ORDER_FILLING_RETURN

    def test_ioc_bit_preferred_when_advertised(self) -> None:
        from services.mt5_gateway.trade import (
            ORDER_FILLING_IOC,
            candidate_filling_modes,
        )

        info = SimpleNamespace(filling_mode=2, trade_exemode=2)
        assert candidate_filling_modes(info)[0] == ORDER_FILLING_IOC

    def test_normalize_price_digits(self) -> None:
        from services.mt5_gateway.trade import normalize_price

        assert normalize_price(2650.123456, 2) == 2650.12

    def test_mt5_retcode_preserves_zero(self) -> None:
        from services.mt5_gateway.trade import mt5_retcode

        assert mt5_retcode(SimpleNamespace(retcode=0)) == 0
        assert mt5_retcode(SimpleNamespace(retcode=10009)) == 10009
        assert mt5_retcode(None) == 10013

    """Regression: MetaTrader5.version()[2] is often a human date string."""

    @pytest.mark.parametrize(
        "release",
        ["28 Apr 2026", "15 Jan 2027", "2026-04-28", "16 Dec 2020"],
    )
    def test_parse_mt5_version_keeps_date_strings(self, release: str) -> None:
        from services.mt5_gateway.runtime import _parse_mt5_version, _safe_int

        major, build, date_str = _parse_mt5_version((500, 3815, release))
        assert major == 500
        assert build == 3815
        assert date_str == release
        assert _safe_int(release) == 0

    def test_safe_int_never_raises_on_dates(self) -> None:
        from services.mt5_gateway.runtime import _safe_int

        for value in ("28 Apr 2026", "15 Jan 2027", "2026-04-28", "01 May 2025"):
            assert _safe_int(value, default=0) == 0

    def test_health_survives_mt5_release_date_string(self, client: TestClient) -> None:
        headers = {"Authorization": "Bearer test-gateway-token"}
        runtime = client.app.state.runtime

        class _DateBridge(_FakeBridge):
            def version(self) -> tuple[int, int, str]:
                return (500, 3815, "28 Apr 2026")

            def terminal_info(self) -> Any:
                # Some terminals may surface unexpected build shapes.
                return SimpleNamespace(build="28 Apr 2026")

        runtime.bridge = _DateBridge(prelogged=False)
        res = client.post(
            "/session/connect",
            headers=headers,
            json={
                "login": 111,
                "password": "secret",
                "server": "Weltrade-Demo",
            },
        )
        assert res.status_code == 200

        health = client.get("/health")
        assert health.status_code == 200
        mt5 = health.json()["mt5"]
        assert mt5["connected"] is True
        assert mt5["login_status"] == "connected"
        assert "ValueError" not in str(mt5.get("login_status"))
        assert mt5["build_date"] == "28 Apr 2026"

    def test_health_never_hangs_on_blocking_account_info(
        self, client: TestClient
    ) -> None:
        """MT5 API hang must return quickly with degraded probe — not forever."""
        import time

        runtime = client.app.state.runtime
        headers = {"Authorization": "Bearer test-gateway-token"}

        class _HangingBridge(_FakeBridge):
            def account_info(self) -> Any:
                time.sleep(5.0)
                return super().account_info()

        runtime.bridge = _HangingBridge(prelogged=False)
        runtime.settings.mt5_health_probe_timeout_seconds = 0.15
        connect = client.post(
            "/session/connect",
            headers=headers,
            json={
                "login": 222,
                "password": "secret",
                "server": "Weltrade-Demo",
            },
        )
        assert connect.status_code == 200
        # Seed a fresh heartbeat so timeout path can report degraded-connected.
        runtime.diagnostics.last_heartbeat_at = (
            __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat()
        )
        runtime.diagnostics.last_heartbeat_ms = 12.0

        t0 = time.perf_counter()
        health = client.get("/health")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert health.status_code == 200
        assert elapsed_ms < 500.0
        body = health.json()
        assert body["status"] == "ok"
        mt5 = body["mt5"]
        assert mt5["probe"] == "timeout"
        assert mt5["degraded"] is True
        assert mt5["connected"] is True
        assert mt5["login_status"] == "degraded"

    def test_call_mt5_bounded_raises_on_hang(self) -> None:
        import time

        from services.mt5_gateway.runtime import MT5CallTimeout, call_mt5_bounded

        def _hang() -> None:
            time.sleep(2.0)

        with pytest.raises(MT5CallTimeout):
            call_mt5_bounded(_hang, timeout_seconds=0.1, label="test")

    def test_health_live_never_touches_mt5(self, client: TestClient) -> None:
        runtime = client.app.state.runtime

        class _BoomBridge(_FakeBridge):
            def account_info(self) -> Any:
                raise RuntimeError("health/live must not call MT5")

            def symbol_info_tick(self, symbol: str) -> Any:
                raise RuntimeError("health/live must not call MT5")

        runtime.bridge = _BoomBridge()
        res = client.get("/health/live")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["probe"] == "live"
        assert body["gateway_version"] == "1.1.7"
        assert "mt5" not in body

    def test_market_data_timeout_returns_503_not_hang(
        self, client: TestClient
    ) -> None:
        import time

        runtime = client.app.state.runtime
        runtime.settings.mt5_market_data_timeout_seconds = 0.15
        headers = {"Authorization": "Bearer test-gateway-token"}

        class _SlowQuote(_FakeBridge):
            def symbol_info_tick(self, symbol: str) -> Any:
                time.sleep(2.0)
                return super().symbol_info_tick(symbol)

        runtime.bridge = _SlowQuote(prelogged=True)
        runtime.diagnostics.connected = True
        runtime.diagnostics.session_mode = "attached"
        t0 = time.perf_counter()
        res = client.get("/quotes/XAUUSD_I", headers=headers)
        elapsed = time.perf_counter() - t0
        assert res.status_code == 503
        assert elapsed < 2.0
        assert "exceeded" in (res.json().get("detail") or "").lower()

    def test_xauusd_i_quote_and_candles(self, client: TestClient) -> None:
        runtime = client.app.state.runtime
        runtime.bridge = _FakeBridge(prelogged=True)
        runtime.diagnostics.connected = True
        runtime.diagnostics.session_mode = "attached"
        headers = {"Authorization": "Bearer test-gateway-token"}
        q = client.get("/quotes/XAUUSD_I", headers=headers)
        assert q.status_code == 200
        assert float(q.json()["bid"]) > 0
        c = client.get(
            "/candles/XAUUSD_I",
            headers=headers,
            params={"timeframe": "H1", "count": 20},
        )
        assert c.status_code == 200
        assert len(c.json().get("items") or []) >= 1

    def test_try_lock_snapshot_reports_busy(self) -> None:
        import threading

        from services.mt5_gateway.runtime import MT5GatewayRuntime

        rt = MT5GatewayRuntime(bridge=_FakeBridge(prelogged=True))
        held = threading.Event()
        release = threading.Event()

        def _hold() -> None:
            with rt._mt5_ops_lock:
                held.set()
                release.wait(timeout=5.0)

        t = threading.Thread(target=_hold, daemon=True)
        t.start()
        assert held.wait(timeout=2.0)
        try:
            snap = rt.try_lock_snapshot(wait_seconds=0.0)
            assert snap["lock"] == "busy"
        finally:
            release.set()
            t.join(timeout=2.0)


@pytest.mark.unit
class TestLiveMT5BridgeImport:
    def test_available_retries_import_after_initial_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import services.mt5_gateway.runtime as runtime_mod

        calls = {"n": 0}
        sentinel = object()

        def fake_import(name: str) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ModuleNotFoundError("No module named 'MetaTrader5'")
            if name != "MetaTrader5":
                raise ModuleNotFoundError(name)
            return sentinel

        monkeypatch.setattr(runtime_mod.importlib, "import_module", fake_import)
        bridge = LiveMT5Bridge()
        assert bridge._mt5 is None
        assert bridge._import_error is not None
        assert "ModuleNotFoundError" in (bridge._import_error or "")
        assert isinstance(bridge._import_context, dict)
        assert "executable" in (bridge._import_context or {})
        # Second attempt (simulates package becoming importable later).
        assert bridge.available is True
        assert bridge._mt5 is sentinel
        assert bridge._import_error is None

    def test_initialize_records_last_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import services.mt5_gateway.runtime as runtime_mod

        class _Mod:
            @staticmethod
            def initialize(path: str = "") -> bool:
                _ = path
                return False

            @staticmethod
            def last_error() -> tuple[int, str]:
                return (1, "IPC timeout")

        monkeypatch.setattr(
            runtime_mod.importlib, "import_module", lambda _name: _Mod()
        )
        bridge = LiveMT5Bridge()
        assert bridge.available is True
        assert bridge.initialize(path="") is False
        assert bridge._last_initialize_ok is False
        assert bridge._last_initialize_error == (1, "IPC timeout")


@pytest.mark.unit
class TestMT5GatewayReconnectLoop:
    """Prove reconnect continues after connected=false without process restart."""

    def _fast_settings(self, gateway_env: MT5GatewaySettings) -> MT5GatewaySettings:
        gateway_env.mt5_heartbeat_interval_seconds = 0.05
        gateway_env.mt5_reconnect_backoff_seconds = 0.05
        gateway_env.mt5_reconnect_max_attempts = 3
        gateway_env.mt5_reconnect_enabled = True
        gateway_env.mt5_api_call_timeout_seconds = 1.0
        return gateway_env

    def test_attached_session_recovers_after_connected_flag_drop(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        settings = self._fast_settings(gateway_env)
        bridge = _FakeBridge(prelogged=True)
        runtime = MT5GatewayRuntime(settings=settings, bridge=bridge)
        attached = runtime.attach(path="")
        assert attached["connected"] is True
        assert runtime._creds is not None
        login_before = runtime._creds.login
        server_before = runtime._creds.server
        mode_before = runtime._creds.mode

        # Simulate the soak failure mode: connected dropped, credentials retained.
        runtime.diagnostics.connected = False
        runtime.diagnostics.reconnect_attempts = 0

        runtime.start_background()
        try:
            deadline = time.time() + 3.0
            while time.time() < deadline and not runtime.diagnostics.connected:
                time.sleep(0.05)
        finally:
            runtime.stop_background()

        assert runtime.diagnostics.connected is True
        assert runtime._creds is not None
        assert runtime._creds.login == login_before
        assert runtime._creds.server == server_before
        assert runtime._creds.mode == mode_before
        assert any(
            ev.get("result") == "ok" for ev in runtime.diagnostics.reconnect_events
        )

    def test_reconnect_preserves_credentials_across_failures(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        settings = self._fast_settings(gateway_env)
        bridge = _FakeBridge(prelogged=False)
        runtime = MT5GatewayRuntime(settings=settings, bridge=bridge)
        runtime.connect(login=4242, password="secret", server="Weltrade-Demo", path="")
        assert runtime._creds is not None
        assert runtime._creds.password == "secret"
        assert runtime._creds.login == 4242

        # Fail first reconnects, then succeed — credentials must remain.
        fail_budget = {"n": 2}

        original_initialize = bridge.initialize

        def flaky_initialize(path: str = "") -> bool:
            if fail_budget["n"] > 0:
                fail_budget["n"] -= 1
                return False
            return original_initialize(path)

        bridge.initialize = flaky_initialize  # type: ignore[method-assign]
        runtime.diagnostics.connected = False
        runtime.diagnostics.reconnect_attempts = 0

        runtime.start_background()
        try:
            deadline = time.time() + 4.0
            while time.time() < deadline and not runtime.diagnostics.connected:
                time.sleep(0.05)
        finally:
            runtime.stop_background()

        assert runtime.diagnostics.connected is True
        assert runtime._creds is not None
        assert runtime._creds.password == "secret"
        assert runtime._creds.login == 4242
        assert runtime._creds.server == "Weltrade-Demo"

    def test_self_recovers_after_max_attempt_burst_without_process_restart(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        settings = self._fast_settings(gateway_env)
        settings.mt5_reconnect_max_attempts = 2
        bridge = _FakeBridge(prelogged=True)
        runtime = MT5GatewayRuntime(settings=settings, bridge=bridge)
        runtime.attach(path="")
        runtime.diagnostics.connected = False

        # Exhaust a full burst, then allow recovery — must not require restart.
        fail_budget = {"n": 2}
        original_initialize = bridge.initialize

        def flaky_initialize(path: str = "") -> bool:
            if fail_budget["n"] > 0:
                fail_budget["n"] -= 1
                return False
            return original_initialize(path)

        bridge.initialize = flaky_initialize  # type: ignore[method-assign]
        # Pretend prior burst already exhausted so cool-down + new burst path runs.
        runtime.diagnostics.reconnect_attempts = settings.mt5_reconnect_max_attempts

        runtime.start_background()
        try:
            deadline = time.time() + 5.0
            while time.time() < deadline and not runtime.diagnostics.connected:
                time.sleep(0.05)
        finally:
            runtime.stop_background()

        assert runtime.diagnostics.connected is True
        assert runtime._creds is not None
        assert runtime._hb_thread is not None

    def test_intentional_disconnect_does_not_auto_reconnect(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        settings = self._fast_settings(gateway_env)
        bridge = _FakeBridge(prelogged=True)
        runtime = MT5GatewayRuntime(settings=settings, bridge=bridge)
        runtime.attach(path="")
        runtime.disconnect()
        assert runtime._creds is None
        assert runtime.diagnostics.connected is False

        runtime.start_background()
        try:
            time.sleep(0.4)
        finally:
            runtime.stop_background()

        assert runtime.diagnostics.connected is False
        assert runtime._creds is None
        assert runtime.diagnostics.reconnect_events == []


@pytest.mark.unit
class TestDelayedAutoAttach:
    """Gateway may start before MT5 is logged in; retry attach without shutdown."""

    def test_waiting_account_does_not_shutdown_or_trade(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        gateway_env.mt5_gateway_auto_attach = True
        bridge = _FakeBridge(prelogged=False)
        runtime = MT5GatewayRuntime(settings=gateway_env, bridge=bridge)
        assert runtime.try_delayed_auto_attach() == "waiting_account"
        assert runtime._creds is None
        assert bridge._initialized is True
        bridge._logged_in = True
        assert runtime.try_delayed_auto_attach() == "ok"
        assert runtime.diagnostics.session_mode == "attached"
        assert runtime._creds is not None
        assert runtime._creds.password == ""

    def test_disabled_when_auto_attach_off(
        self, gateway_env: MT5GatewaySettings
    ) -> None:
        gateway_env.mt5_gateway_auto_attach = False
        runtime = MT5GatewayRuntime(
            settings=gateway_env, bridge=_FakeBridge(prelogged=True)
        )
        assert runtime.try_delayed_auto_attach() == "disabled"
