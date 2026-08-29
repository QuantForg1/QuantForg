"""Phase 47 — account-aware runtime, isolation, credential safety, single engine."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.dto.broker import (
    CreateBrokerAccountCommand,
    CreateBrokerCommand,
)
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    bound_execution_account,
    classify_account_session,
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
from app.application.services.portfolio_sync import PortfolioSyncService
from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
)
from app.application.use_cases.broker import (
    CreateBrokerAccountUseCase,
    CreateBrokerUseCase,
    GetBrokerAccountUseCase,
    GetBrokerConnectionUseCase,
    ListBrokerAccountsUseCase,
)
from app.application.use_cases.portfolio import ListPositionsUseCase
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
from tests.unit.fakes_broker import SharedBrokerUnitOfWorkFactory
from tests.unit.test_mt5_session_consistency import (
    FakeGatewayClient,
    seed_owned_mt5_connection,
)

_SECRET = "unit-test-secret-key-that-is-long-enough-32chars"
_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_plane_and_binding() -> Iterator[None]:
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()
    yield
    reset_control_plane_for_tests()
    reset_execution_binding_for_tests()


@pytest.mark.unit
def test_session_mismatch_fails_closed_when_bound_to_other_user() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=16785006)
    assert classify_account_session(
        user_id=user_b, owned_login=16785006, live_login=16785006
    ) == ACCOUNT_SESSION_MISMATCH
    assert submit_blocked_reason(user_id=user_b, login=16785006) == (
        ACCOUNT_SESSION_MISMATCH
    )
    assert submit_blocked_reason(user_id=user_a, login=16785006) is None


@pytest.mark.unit
def test_guarded_oms_blocks_foreign_user_when_bound() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=16785006)
    inner = RecordingOmsPort()
    plane = OperationsControlPlane()
    plane.transition_mode(
        OperatorIdentity(user_id=user_a, role="owner", display_name="op"),
        OpsExecutionMode.CANARY,
        reason="phase47",
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
    ok = guarded.submit_market(
        user_id=user_a,
        request_id="a1",
        intent=intent,
        connected=True,
        login=16785006,
    )
    assert ok.outcome == "success"
    assert len(inner.calls) == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_broker_account() -> None:
    factory = SharedBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
        CreateBrokerCommand(
            name="Venue",
            slug="venue-47",
            platform_code=BrokerPlatform.MT5,
            country_code="US",
            activate=True,
        )
    )
    user_a = uuid4()
    user_b = uuid4()
    account_b = await CreateBrokerAccountUseCase(
        uow_factory=factory, audit=audit, encryption_key=_SECRET
    ).execute(
        CreateBrokerAccountCommand(
            user_id=user_b,
            broker_id=broker.id,
            external_account_id="222",
            password="bravo-secret",
        )
    )
    assert await ListBrokerAccountsUseCase(uow_factory=factory).execute(
        user_id=user_a
    ) == []
    with pytest.raises(NotFoundError):
        await GetBrokerAccountUseCase(uow_factory=factory).execute(
            user_id=user_a, account_id=account_b.id
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_connection() -> None:
    factory = SharedBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
        CreateBrokerCommand(
            name="Venue",
            slug="venue-47b",
            platform_code=BrokerPlatform.MT5,
            country_code="US",
            activate=True,
        )
    )
    user_a = uuid4()
    user_b = uuid4()
    account_b = await CreateBrokerAccountUseCase(
        uow_factory=factory, audit=audit, encryption_key=_SECRET
    ).execute(
        CreateBrokerAccountCommand(
            user_id=user_b,
            broker_id=broker.id,
            external_account_id="333",
            password="charlie-secret",
        )
    )
    async with factory() as uow:
        connection = await uow.connections.get_for_account(account_b.id)
    assert connection is not None
    with pytest.raises(NotFoundError):
        await GetBrokerConnectionUseCase(uow_factory=factory).execute(
            user_id=user_a, connection_id=connection.id
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_a_cannot_read_user_b_positions() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    sync = PortfolioSyncService(adapter=adapter)
    owned = await ListPositionsUseCase(
        mt5_uow_factory=factory, sync_service=sync
    ).execute(user_id=user_a)
    assert owned == []
    with pytest.raises(NotFoundError, match="No active MT5 connection"):
        await ListPositionsUseCase(
            mt5_uow_factory=factory, sync_service=sync
        ).execute(user_id=user_b)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trader_can_start_own_robot_not_foreign() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    await seed_owned_mt5_connection(factory, user_b)
    await require_live_mt5_connection(factory, adapter, user_a)

    started = await ControlTradingRobotUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(
        user_id=user_a,
        role="trader",
        display_name="Trader A",
        action="start",
    )
    assert started["robot"] == "Running"
    bound_user, bound_login = bound_execution_account()
    assert bound_user == user_a
    assert bound_login == 16785006

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


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_b_cannot_inherit_user_a_mt5_session() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)
    await require_live_mt5_connection(factory, adapter, user_a)
    stolen = await ensure_live_mt5_session_for_user(factory, adapter, user_b)
    assert stolen is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_session_payload_never_includes_credentials() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    adapter = MT5Adapter(client=FakeGatewayClient())
    user_id = uuid4()
    await seed_owned_mt5_connection(factory, user_id)
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_id)
    keys = {str(k).lower() for k in snap}
    assert "password" not in keys
    assert "ciphertext" not in keys
    assert "token" not in keys
    assert "secret_key" not in keys
    blob = str(snap.values()).lower()
    assert "password" not in blob
    assert "16785006" not in str(snap.get("account") or "")
    assert snap["concurrent_live_sessions_supported"] is False


@pytest.mark.unit
def test_broker_password_never_logged_in_weltrade_bind() -> None:
    text = (
        _ROOT / "app" / "application" / "services" / "weltrade_integration.py"
    ).read_text(encoding="utf-8")
    assert "password_provided=bool(password)" in text
    assert "password=password," in text
    for line in text.splitlines():
        stripped = line.strip()
        if "logger." not in stripped:
            continue
        assert "password=" not in stripped or "password_provided" in stripped


@pytest.mark.unit
def test_catalogue_unavailable_is_not_zero_symbols(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.execution_universe.execution_universe_mode",
        lambda: MODE_BROKER_DISCOVERED,
    )
    reset_broker_execution_universe_for_tests()
    snap = live_execution_snapshot(mt5_adapter=None)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert live_execution_symbols(mt5_adapter=None) == ()
    assert snap["catalogue_source"] != 0
    assert snap["catalogue_source"] != "0"
    reset_broker_execution_universe_for_tests()


@pytest.mark.unit
def test_no_second_gateway_scanner_or_engine() -> None:
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
    assert gateway == ["app/infrastructure/brokers/mt5/gateway_client.py"]
    assert engines == ["app/application/services/institutional_ite_runtime.py"]
    twins = [
        p.relative_to(_ROOT).as_posix()
        for p in app_root.rglob("*multi_asset_scanner*.py")
        if p.name.endswith(".py")
    ]
    assert twins == ["app/application/services/institutional_multi_asset_scanner.py"]


@pytest.mark.unit
def test_research_submit_order_blocked_and_promotion_false() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD", side="BUY", volume="0.01")


@pytest.mark.unit
def test_broker_account_dto_excludes_password() -> None:
    from app.application.dto.broker import BrokerAccountDTO, BrokerConnectionDTO

    assert "password" not in BrokerAccountDTO.__dataclass_fields__
    assert "password" not in BrokerConnectionDTO.__dataclass_fields__
    assert "ciphertext" not in BrokerAccountDTO.__dataclass_fields__
