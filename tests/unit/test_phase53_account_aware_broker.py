"""Phase 53 — account-aware broker connection and LIVE_BROKER universe."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.dto.broker import (
    BrokerAccountDTO,
    BrokerConnectionDTO,
    CreateBrokerAccountCommand,
    CreateBrokerCommand,
)
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.institutional_execution_engine import parse_order_intent
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.institutional_ops_guards import GuardedOmsSubmitPort
from app.application.services.mt5_session_guard import (
    ensure_live_mt5_session_for_user,
    require_live_mt5_connection,
)
from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
)
from app.application.use_cases.broker import (
    CreateBrokerAccountUseCase,
    CreateBrokerUseCase,
    GetBrokerAccountUseCase,
    ListBrokerAccountsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.broker import BrokerPlatform
from app.domain.exceptions.base import ConflictError, NotFoundError
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    reset_control_plane_for_tests,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from app.domain.market_universe.broker_catalogue import discover_live_catalogue
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.domain.trading.execution_universe import (
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_UNAVAILABLE,
    MODE_BROKER_DISCOVERED,
    live_execution_snapshot,
    live_execution_symbols,
    reset_broker_execution_universe_for_tests,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.middleware.error_handler import _safe_error_details
from tests.unit.fakes_broker import SharedBrokerUnitOfWorkFactory
from tests.unit.test_broker_discovered_execution_universe import _LiveAdapter
from tests.unit.test_mt5_session_consistency import (
    FakeGatewayClient,
    seed_owned_mt5_connection,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_SECRET = "unit-test-secret-key-that-is-long-enough-32chars"
_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_plane_and_binding() -> Iterator[None]:
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    reset_broker_execution_universe_for_tests()
    yield
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    reset_broker_execution_universe_for_tests()


@pytest.fixture
def broker_discovered(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(
        "app.domain.trading.execution_universe.execution_universe_mode",
        lambda: MODE_BROKER_DISCOVERED,
    )
    reset_broker_execution_universe_for_tests()
    yield
    reset_broker_execution_universe_for_tests()


@pytest.mark.asyncio
async def test_user_a_owns_account_user_b_cannot_read_it() -> None:
    factory = SharedBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
        CreateBrokerCommand(
            name="Venue",
            slug="venue-53",
            platform_code=BrokerPlatform.MT5,
            country_code="US",
            activate=True,
        )
    )
    user_a = uuid4()
    user_b = uuid4()
    account_a = await CreateBrokerAccountUseCase(
        uow_factory=factory, audit=audit, encryption_key=_SECRET
    ).execute(
        CreateBrokerAccountCommand(
            user_id=user_a,
            broker_id=broker.id,
            external_account_id="111",
            password="alpha-secret",
        )
    )
    owned = await ListBrokerAccountsUseCase(uow_factory=factory).execute(user_id=user_a)
    assert len(owned) == 1
    assert owned[0].id == account_a.id
    assert "password" not in asdict(account_a)
    assert "alpha-secret" not in str(asdict(account_a))
    listed_b = await ListBrokerAccountsUseCase(uow_factory=factory).execute(
        user_id=user_b
    )
    assert listed_b == []
    with pytest.raises(NotFoundError):
        await GetBrokerAccountUseCase(uow_factory=factory).execute(
            user_id=user_b, account_id=account_a.id
        )


@pytest.mark.asyncio
async def test_user_b_cannot_inherit_user_a_session() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    await require_live_mt5_connection(factory, adapter, user_a)
    stolen = await ensure_live_mt5_session_for_user(factory, adapter, user_b)
    assert stolen is None
    with pytest.raises(NotFoundError, match="No active MT5 connection"):
        await require_live_mt5_connection(factory, adapter, user_b)


def test_account_session_mismatch_blocks_oms_and_does_not_call_it() -> None:
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
        reason="phase53",
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
        request_id="b1",
        intent=intent,
        connected=True,
        login=16785006,
    )
    assert blocked.outcome == "disabled"
    assert ACCOUNT_SESSION_MISMATCH in (blocked.message or "")
    assert blocked.gateway_status == "not_called"
    assert inner.calls == []


@pytest.mark.asyncio
async def test_missing_broker_connection_is_broker_not_connected() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_id = uuid4()
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    assert snap["robot_blocked_reason"] == "BROKER_NOT_CONNECTED"
    assert snap["owned"] is False
    assert snap["ownership"] == "none"
    with pytest.raises(NotFoundError) as exc:
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=user_id,
            role="trader",
            display_name="Trader",
            action="start",
        )
    assert exc.value.code == "BROKER_NOT_CONNECTED"


@pytest.mark.asyncio
async def test_session_dto_never_includes_broker_password() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_id = uuid4()
    await seed_owned_mt5_connection(factory, user_id)
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    blob = str(snap).lower()
    assert "password" not in blob
    assert "ciphertext" not in blob
    assert snap["authenticated"] is True
    assert snap["concurrent_live_sessions_supported"] is False
    assert "password" not in BrokerAccountDTO.__dataclass_fields__
    assert "password" not in BrokerConnectionDTO.__dataclass_fields__


def test_broker_password_never_appears_in_logs_or_error_details() -> None:
    text = (
        _ROOT / "app" / "application" / "services" / "weltrade_integration.py"
    ).read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if "logger." not in stripped:
            continue
        assert "password=" not in stripped or "password_provided" in stripped
    details = _safe_error_details(
        {"reason": "not_connected", "password": "hunter2", "note": "password=leak"}
    )
    assert "password" not in details
    assert "note" not in details
    assert details["reason"] == "not_connected"


def test_password_is_cleared_from_frontend_after_submit() -> None:
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
    assert 'autoComplete="off"' in workspace
    assert "showConnectForm = !connected" in workspace
    assert "localStorage.setItem" not in workspace
    assert "localStorage.getItem" not in workspace


def test_broker_symbols_are_authoritative_not_static_or_gold_only(
    broker_discovered: None,
) -> None:
    adapter = _LiveAdapter()
    snap = live_execution_snapshot(mt5_adapter=adapter)
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    symbols = {s.upper() for s in live_execution_symbols(mt5_adapter=adapter)}
    assert "EURUSD_I" in symbols
    assert "XAUUSD_I" in symbols
    exec_src = (
        _ROOT / "app" / "domain" / "trading" / "execution_universe.py"
    ).read_text(encoding="utf-8")
    assert "DEFAULT_SCALPING_UNIVERSE is never a production live allowlist" in exec_src
    gold_src = (_ROOT / "app" / "domain" / "trading" / "gold_only.py").read_text(
        encoding="utf-8"
    )
    assert "BROKER_DISCOVERED" in gold_src


def test_catalogue_unavailable_is_not_zero_and_not_live_broker(
    broker_discovered: None,
) -> None:
    snap = live_execution_snapshot(mt5_adapter=None)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert snap["catalogue_source"] != 0
    assert snap["catalogue_source"] != "0"
    assert live_execution_symbols(mt5_adapter=None) == ()


def test_live_broker_requires_real_adapter_rows_and_empty_is_distinct(
    broker_discovered: None,
) -> None:
    live = discover_live_catalogue(_LiveAdapter())
    assert live["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert live["count"] > 0
    empty = discover_live_catalogue(_LiveAdapter(rows=()))
    assert empty["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert empty["count"] == 0
    assert empty["rows"] == ()
    unavailable = discover_live_catalogue(None)
    assert unavailable["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert empty["catalogue_source"] != unavailable["catalogue_source"]


def test_one_malformed_broker_symbol_does_not_destroy_valid_symbols() -> None:
    class _Boom:
        @property
        def code(self) -> str:
            raise RuntimeError("malformed symbol")

    class _Adapter:
        execution_enabled = False
        client = type("GatewayMT5Client", (), {})()

        def symbols(self) -> list[object]:
            return [
                {"code": "EURUSD_i", "path": "Forex\\Majors", "trade_mode": 4},
                _Boom(),
                {"code": "XAUUSD_i", "path": "Metals\\XAUUSD", "trade_mode": 4},
            ]

    result = discover_live_catalogue(_Adapter())
    assert result["catalogue_source"] == CATALOGUE_LIVE_BROKER
    codes = {str(row["code"]).upper() for row in result["rows"]}
    assert "EURUSD_I" in codes
    assert "XAUUSD_I" in codes
    assert result["count"] == 2


def test_research_submit_order_remains_blocked() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD_i", side="buy")


def test_xauusd_i_supported_when_broker_exposes_it(broker_discovered: None) -> None:
    symbols = {s.upper() for s in live_execution_symbols(mt5_adapter=_LiveAdapter())}
    assert "XAUUSD_I" in symbols
    without_gold = _LiveAdapter(
        rows=(
            {
                "code": "EURUSD_i",
                "path": "Forex\\Majors",
                "trade_mode": 4,
                "digits": 5,
            },
        )
    )
    other = {s.upper() for s in live_execution_symbols(mt5_adapter=without_gold)}
    assert "EURUSD_I" in other
    assert "XAUUSD_I" not in other


def test_no_second_gateway_engine_or_scanner() -> None:
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
    assert scanners == ["app/application/services/institutional_multi_asset_scanner.py"]


@pytest.mark.asyncio
async def test_foreign_robot_start_is_account_session_mismatch() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    await seed_owned_mt5_connection(factory, user_b)
    started = await ControlTradingRobotUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(
        user_id=user_a,
        role="trader",
        display_name="Trader A",
        action="start",
    )
    assert started["robot"] == "Running"
    with pytest.raises(ConflictError) as exc:
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=user_b,
            role="trader",
            display_name="Trader B",
            action="start",
        )
    assert exc.value.code == "account_session_mismatch"
