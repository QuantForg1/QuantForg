"""Phase 54 — real broker connection and LIVE_BROKER universe validation."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.dto.auth import AuthUserDTO
from app.application.dto.broker import BrokerAccountDTO, BrokerConnectionDTO
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    bound_execution_account,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.institutional_ops_guards import GuardedOmsSubmitPort
from app.application.services.market_universe_service import (
    build_snapshot,
    reset_market_universe_cache_for_tests,
)
from app.application.services.mt5_session_guard import (
    ensure_live_mt5_session_for_user,
)
from app.application.services.trading_session import GetTradingSessionUseCase
from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.exceptions.base import ServiceUnavailableError
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    reset_control_plane_for_tests,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.market_universe.broker_catalogue import discover_live_catalogue
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    ASSET_CLASSES,
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_UNAVAILABLE,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
)
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.domain.trading.execution_universe import (
    MODE_BROKER_DISCOVERED,
    live_execution_snapshot,
    live_execution_symbols,
    reset_broker_execution_universe_for_tests,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.broker_trader_errors import (
    CONNECTION_FAILED,
    GATEWAY_UNAVAILABLE,
    INVALID_CREDENTIALS,
    TRADER_BROKER_MESSAGES,
    classify_broker_connect_error,
    raise_trader_broker_failure,
)
from app.presentation.dependencies.auth import get_current_user
from app.presentation.dependencies.weltrade import get_weltrade_service
from app.presentation.middleware.error_handler import register_exception_handlers
from app.presentation.routers.weltrade import router as weltrade_router
from tests.unit.test_broker_discovered_execution_universe import _LiveAdapter
from tests.unit.test_mt5_session_consistency import (
    FakeGatewayClient,
    seed_owned_mt5_connection,
)
from tests.unit.test_weltrade_integration import _StubGateway

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_ROOT = Path(__file__).resolve().parents[2]
_SECRET_PASSWORD = "phase54-secret-password"


@pytest.fixture(autouse=True)
def _reset_runtime() -> Iterator[None]:
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    reset_broker_execution_universe_for_tests()
    reset_market_universe_cache_for_tests()
    yield
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    reset_broker_execution_universe_for_tests()
    reset_market_universe_cache_for_tests()


@pytest.fixture
def broker_discovered(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        "app.domain.trading.execution_universe.execution_universe_mode",
        lambda: MODE_BROKER_DISCOVERED,
    )
    reset_broker_execution_universe_for_tests()
    yield
    reset_broker_execution_universe_for_tests()


def _http_client(svc: WeltradeIntegrationService) -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(weltrade_router, prefix="/api/v1")

    def _user() -> AuthUserDTO:
        return AuthUserDTO(
            id=uuid4(),
            email="phase54@example.com",
            display_name="Phase54",
            role="trader",
            status="active",
            auth_user_id=uuid4(),
        )

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_weltrade_service] = lambda: svc
    return TestClient(app)


@pytest.mark.asyncio
async def test_authenticated_connect_binds_owned_account() -> None:
    client = _StubGateway()
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=client)
    svc = WeltradeIntegrationService(adapter=adapter, uow_factory=factory)
    user_id = uuid4()
    result = await svc.connect(
        user_id=user_id,
        login=4242,
        password=_SECRET_PASSWORD,
        server="Weltrade-Demo",
        account_type="demo",
        prefer_attach=True,
    )
    assert result["ok"] is True
    bound_user, bound_login = bound_execution_account()
    assert bound_user == user_id
    assert bound_login == 4242
    blob = str(result).lower()
    assert _SECRET_PASSWORD.lower() not in blob
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    assert snap["owned"] is True
    assert snap["ownership"] == "owned"
    assert snap["concurrent_live_sessions_supported"] is False
    assert snap["authenticated"] is True
    assert "password" not in str(snap).lower()


def test_invalid_credentials_gateway_unavailable_and_connection_failed() -> None:
    _, invalid, invalid_msg = classify_broker_connect_error(
        RuntimeError("broker rejected credentials password=leak")
    )
    assert invalid == INVALID_CREDENTIALS
    assert invalid_msg == TRADER_BROKER_MESSAGES[INVALID_CREDENTIALS]
    assert "leak" not in invalid_msg
    _, gw, gw_msg = classify_broker_connect_error(
        RuntimeError("gateway health unreachable")
    )
    assert gw == GATEWAY_UNAVAILABLE
    assert gw_msg == TRADER_BROKER_MESSAGES[GATEWAY_UNAVAILABLE]
    _, failed, failed_msg = classify_broker_connect_error(
        RuntimeError("internal boom traceback")
    )
    assert failed == CONNECTION_FAILED
    assert "traceback" not in failed_msg
    with pytest.raises(ServiceUnavailableError) as exc:
        raise_trader_broker_failure(RuntimeError("weird failure password=hunter2"))
    assert exc.value.code == CONNECTION_FAILED
    assert "hunter2" not in exc.value.message


def test_connect_http_maps_safe_trader_errors() -> None:
    down = _StubGateway()
    down._fail_health = True
    http = _http_client(
        WeltradeIntegrationService(
            adapter=MT5Adapter(client=down),
            uow_factory=MemoryMT5UnitOfWorkFactory(),
        )
    )
    gw_resp = http.post(
        "/api/v1/weltrade/connect",
        json={
            "login": 4242,
            "password": _SECRET_PASSWORD,
            "server": "Weltrade-Demo",
            "account_type": "demo",
        },
    )
    assert gw_resp.status_code == 503
    gw_body = gw_resp.json()["error"]
    assert gw_body["code"] == GATEWAY_UNAVAILABLE
    assert gw_body["message"] == TRADER_BROKER_MESSAGES[GATEWAY_UNAVAILABLE]
    assert _SECRET_PASSWORD not in gw_resp.text
    assert "traceback" not in gw_body["message"].lower()


def test_password_cleared_and_absent_from_dto_and_logs() -> None:
    workspace = (
        _ROOT
        / "frontend"
        / "src"
        / "components"
        / "broker"
        / "broker-config-workspace.tsx"
    ).read_text(encoding="utf-8")
    assert "clearPasswordField" in workspace
    assert "key={passwordFieldKey}" in workspace
    assert "localStorage.setItem" not in workspace
    assert "password" not in BrokerAccountDTO.__dataclass_fields__
    assert "password" not in BrokerConnectionDTO.__dataclass_fields__
    weltrade = (
        _ROOT / "app" / "application" / "services" / "weltrade_integration.py"
    ).read_text(encoding="utf-8")
    for line in weltrade.splitlines():
        stripped = line.strip()
        if "logger." not in stripped:
            continue
        assert "password=" not in stripped or "password_provided" in stripped


@pytest.mark.asyncio
async def test_user_b_isolation_and_no_global_fallback() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    stolen = await ensure_live_mt5_session_for_user(factory, adapter, user_b)
    assert stolen is None
    gate_src = (
        _ROOT / "app" / "application" / "services" / "account_execution_gate.py"
    ).read_text(encoding="utf-8")
    assert "default account" not in gate_src.lower()
    assert "GLOBAL_ACCOUNT" not in gate_src
    assert submit_blocked_reason(user_id=user_b, login=1) is None


def test_account_session_mismatch_does_not_call_oms() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=16785006)
    assert submit_blocked_reason(user_id=user_b, login=16785006) == (
        ACCOUNT_SESSION_MISMATCH
    )
    inner = RecordingOmsPort()
    plane = OperationsControlPlane()
    plane.transition_mode(
        OperatorIdentity(user_id=user_a, role="owner", display_name="op"),
        OpsExecutionMode.CANARY,
        reason="phase54",
        confirmed=True,
    )
    guarded = GuardedOmsSubmitPort(inner=inner, plane=plane)
    intent = parse_order_intent(
        symbol="XAUUSD_i",
        side="buy",
        order_type="market",
        volume="0.01",
    )
    blocked = guarded.submit_market(
        user_id=user_b,
        request_id="p54",
        intent=intent,
        connected=True,
        login=16785006,
    )
    assert blocked.outcome == "disabled"
    assert ACCOUNT_SESSION_MISMATCH in (blocked.message or "")
    assert blocked.gateway_status == "not_called"
    assert inner.calls == []


def test_broker_symbols_authoritative_complete_catalogue(
    broker_discovered: None,
) -> None:
    rows = [
        {"code": f"PAIR{i}_i", "path": "Forex\\Majors", "trade_mode": 4}
        for i in range(12)
    ]
    rows.extend(
        (
            {"code": "BTCUSD", "path": "Crypto\\BTC", "trade_mode": 4},
            {"code": "XAUUSD_i", "path": "Metals\\XAUUSD", "trade_mode": 4},
            {"code": "NDXUSD", "path": "Indices\\US", "trade_mode": 4},
            {"code": "XTIUSD", "path": "Energy\\Oil", "trade_mode": 4},
            {"code": "AAPL", "path": "Stocks\\US", "trade_mode": 4},
        )
    )

    class _Boom:
        @property
        def code(self) -> str:
            raise RuntimeError("malformed symbol")

    class _Adapter:
        execution_enabled = False
        client = type("GatewayMT5Client", (), {})()

        def symbols(self) -> list[object]:
            return [*rows, _Boom()]

    discovered = discover_live_catalogue(_Adapter())
    assert discovered["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert discovered["count"] == len(rows)
    codes = {str(row["code"]).upper() for row in discovered["rows"]}
    assert "PAIR0_I" in codes
    assert "XAUUSD_I" in codes
    assert "BTCUSD" in codes
    live = {s.upper() for s in live_execution_symbols(mt5_adapter=_LiveAdapter())}
    assert "EURUSD_I" in live
    exec_src = (
        _ROOT / "app" / "domain" / "trading" / "execution_universe.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_SCALPING_UNIVERSE is never a production live allowlist" in exec_src
    gold_src = (_ROOT / "app" / "domain" / "trading" / "gold_only.py").read_text(
        encoding="utf-8"
    )
    assert "BROKER_DISCOVERED" in gold_src


def test_live_empty_catalogue_distinct_from_unavailable(
    broker_discovered: None,
) -> None:
    empty = discover_live_catalogue(_LiveAdapter(rows=()))
    assert empty["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert empty["count"] == 0
    unavailable = discover_live_catalogue(None)
    assert unavailable["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert empty["catalogue_source"] != unavailable["catalogue_source"]
    snap_empty = build_snapshot(mt5_adapter=_LiveAdapter(rows=()))
    assert snap_empty["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert snap_empty["global_market_status"]["FOREX"] == 0
    snap_down = build_snapshot(mt5_adapter=None)
    assert snap_down["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap_down["global_market_status"]["FOREX"] == CATALOGUE_UNAVAILABLE
    assert snap_down["global_market_status"]["FOREX"] != 0
    fail_closed = live_execution_snapshot(mt5_adapter=None)
    assert fail_closed["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert live_execution_symbols(mt5_adapter=None) == ()


def test_all_supported_asset_classes_from_broker_rows() -> None:
    samples = (
        ({"code": "EURUSD_i", "path": "Forex\\Majors"}, "FOREX"),
        ({"code": "BTCUSD", "path": "Crypto\\BTC"}, "CRYPTO"),
        ({"code": "XAUUSD_i", "path": "Metals\\XAUUSD"}, "METALS"),
        ({"code": "NDXUSD", "path": "Indices\\US"}, "INDICES"),
        ({"code": "XTIUSD", "path": "Energy\\Oil"}, "ENERGY"),
        ({"code": "AAPL", "path": "Stocks\\US"}, "STOCKS"),
        ({"code": "WHEAT", "path": "Commodities\\Softs"}, "COMMODITIES"),
        ({"code": "SYNTH01", "path": "Synthetics\\Other"}, "OTHER"),
        ({"code": "FOO"}, "UNKNOWN"),
    )
    found: set[str] = set()
    for row, expected in samples:
        cls = classify_instrument(str(row["code"]), broker_row=row).asset_class
        assert cls == expected
        found.add(cls)
    for name in ASSET_CLASSES:
        assert name in found
    xau = classify_instrument(
        "XAUUSD_i",
        broker_row={"code": "XAUUSD_i", "path": "Metals\\XAUUSD"},
    )
    assert xau.asset_class == "METALS"


def test_research_wall_and_frozen_thresholds() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD_i", side="buy")
    assert FROZEN_OPPORTUNITY_THRESHOLD == 70
    assert FROZEN_DIRECTIONAL_EDGE == 5
    assert FROZEN_MIN_RR == "1.20"


def test_no_second_gateway_scanner_engine_or_live_order() -> None:
    app_root = _ROOT / "app"
    gateway = [
        p.relative_to(_ROOT).as_posix()
        for p in app_root.rglob("*.py")
        if "class GatewayMT5Client" in p.read_text(encoding="utf-8")
    ]
    engines = [
        p.relative_to(_ROOT).as_posix()
        for p in app_root.rglob("*.py")
        if "class InstitutionalIteRuntime" in p.read_text(encoding="utf-8")
    ]
    scanners = [
        p.relative_to(_ROOT).as_posix()
        for p in app_root.rglob("*multi_asset_scanner*.py")
        if p.name.endswith(".py")
    ]
    assert gateway == ["app/infrastructure/brokers/mt5/gateway_client.py"]
    assert engines == ["app/application/services/institutional_ite_runtime.py"]
    assert scanners == [
        "app/application/services/institutional_multi_asset_scanner.py"
    ]
    for rel in (
        "app/domain/market_universe/broker_catalogue.py",
        "app/application/services/trading_session.py",
        "app/presentation/routers/weltrade.py",
    ):
        text = (_ROOT / rel).read_text(encoding="utf-8")
        assert "order_send" not in text
    inner = RecordingOmsPort()
    discover_live_catalogue(_LiveAdapter())
    assert inner.calls == []
