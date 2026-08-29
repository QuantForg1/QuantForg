"""Phase 46 — multi-user broker ownership, credential safety, single runtime."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.application.dto.broker import (
    CreateBrokerAccountCommand,
    CreateBrokerCommand,
)
from app.application.services.mt5_session_guard import (
    ensure_live_mt5_session_for_user,
    require_live_mt5_connection,
    reset_session_heal_lock_for_tests,
)
from app.application.services.trading_session import (
    ControlTradingRobotUseCase,
    GetTradingSessionUseCase,
    resolve_trading_context,
)
from app.application.use_cases.broker import (
    CreateBrokerAccountUseCase,
    CreateBrokerUseCase,
    GetBrokerAccountUseCase,
    GetBrokerConnectionUseCase,
    ListBrokerAccountsUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.mt5 import MT5Connection
from app.domain.enums.broker import BrokerPlatform
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import NotFoundError
from app.domain.trading.trading_context import mask_broker_login
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from core.security.crypto import decrypt_secret, encrypt_secret
from tests.unit.fakes_broker import SharedBrokerUnitOfWorkFactory
from tests.unit.test_mt5_session_consistency import (
    FakeGatewayClient,
    seed_owned_mt5_connection,
)

_SECRET = "unit-test-secret-key-that-is-long-enough-32chars"
_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _reset_heal_lock() -> None:
    reset_session_heal_lock_for_tests()
    yield
    reset_session_heal_lock_for_tests()


@pytest.mark.unit
def test_mask_broker_login_never_returns_full_id() -> None:
    assert mask_broker_login(16785006) == "16•••06"
    assert "16785006" not in mask_broker_login(16785006)
    assert mask_broker_login(1) == "••••"


@pytest.mark.unit
def test_broker_account_dto_has_no_password_field() -> None:
    from app.application.dto.broker import BrokerAccountDTO, BrokerConnectionDTO

    assert "password" not in BrokerAccountDTO.__dataclass_fields__
    assert "password" not in BrokerConnectionDTO.__dataclass_fields__


@pytest.mark.unit
def test_credentials_persist_encrypted_not_plaintext() -> None:
    token = encrypt_secret("never-store-plaintext", secret_key=_SECRET)
    assert "never-store-plaintext" not in token
    assert decrypt_secret(token, secret_key=_SECRET) == "never-store-plaintext"


@pytest.mark.unit
def test_resolve_trading_context_fail_closed_when_disconnected() -> None:
    ctx = resolve_trading_context(user_id=uuid4(), connection=None)
    assert ctx.connection_status == "NOT_CONNECTED"
    assert ctx.robot_status == "Stopped"
    assert ctx.execution_permitted is False
    assert ctx.trading_enabled is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_user_b_cannot_claim_user_a_gateway_session() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    user_a = uuid4()
    user_b = uuid4()
    await seed_owned_mt5_connection(factory, user_a)

    owned = await require_live_mt5_connection(factory, adapter, user_a)
    assert owned.login == 16785006

    stolen = await ensure_live_mt5_session_for_user(factory, adapter, user_b)
    assert stolen is None
    with pytest.raises(NotFoundError, match="No active MT5 connection"):
        await require_live_mt5_connection(factory, adapter, user_b)

    async with factory() as uow:
        b_row = await uow.connections.get_active_for_user(user_b)
    assert b_row is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_mismatched_login_does_not_remap_to_live_terminal() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    user_b = uuid4()
    foreign = MT5Connection.create(
        user_id=user_b, login=99999999, server="Other-Server"
    )
    foreign.mark_connected(session_ref="foreign-session")
    async with factory() as uow:
        await uow.connections.upsert_for_user(foreign)
        await uow.commit()

    bound = await ensure_live_mt5_session_for_user(factory, adapter, user_b)
    assert bound is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_broker_connection_get_is_owner_scoped() -> None:
    factory = SharedBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
        CreateBrokerCommand(
            name="Venue",
            slug="venue-a",
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
    listed = await ListBrokerAccountsUseCase(uow_factory=factory).execute(
        user_id=user_b
    )
    assert listed == []
    with pytest.raises(NotFoundError):
        await GetBrokerAccountUseCase(uow_factory=factory).execute(
            user_id=user_b, account_id=account_a.id
        )
    async with factory() as uow:
        connection = await uow.connections.get_for_account(account_a.id)
    if connection is not None:
        with pytest.raises(NotFoundError):
            await GetBrokerConnectionUseCase(uow_factory=factory).execute(
                user_id=user_b, connection_id=connection.id
            )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_viewer_cannot_start_robot() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    user_id = uuid4()
    await seed_owned_mt5_connection(factory, user_id)
    await require_live_mt5_connection(factory, adapter, user_id)

    with pytest.raises(AuthorizationError):
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=user_id,
            role="viewer",
            display_name="Viewer",
            action="start",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_robot_start_requires_owned_connection() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    with pytest.raises(NotFoundError, match="No active"):
        await ControlTradingRobotUseCase(
            uow_factory=factory, adapter=adapter
        ).execute(
            user_id=uuid4(),
            role="owner",
            display_name="Owner",
            action="start",
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trading_session_status_hides_foreign_robot() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    user_b = uuid4()
    snap = await GetTradingSessionUseCase(
        uow_factory=factory, adapter=adapter
    ).execute(user_id=user_b)
    assert snap["broker"] == "Disconnected"
    assert snap["robot"] == "Stopped"
    assert snap["execution_permitted"] is False
    assert snap.get("balance") in {None, ""}


@pytest.mark.unit
def test_single_canonical_gateway_engine_and_scanner() -> None:
    app_root = _ROOT / "app"
    gateway = []
    engines = []
    for path in app_root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "class GatewayMT5Client" in text:
            gateway.append(path.relative_to(_ROOT).as_posix())
        if "class InstitutionalIteRuntime" in text:
            engines.append(path.relative_to(_ROOT).as_posix())
    assert gateway == ["app/infrastructure/brokers/mt5/gateway_client.py"]
    assert engines == ["app/application/services/institutional_ite_runtime.py"]
    scanner = (
        _ROOT
        / "app"
        / "application"
        / "services"
        / "institutional_multi_asset_scanner.py"
    )
    assert scanner.is_file()
    twins = [
        p
        for p in (_ROOT / "app").rglob("*multi_asset_scanner*.py")
        if p.name.endswith(".py")
    ]
    assert [p.relative_to(_ROOT).as_posix() for p in twins] == [
        "app/application/services/institutional_multi_asset_scanner.py"
    ]


@pytest.mark.unit
def test_opportunity_edge_rr_unchanged() -> None:
    from app.domain.institutional_trading.operations.probability_selector import (
        OPPORTUNITY_SCORE_THRESHOLD,
    )
    from app.domain.market_universe.constants import (
        FROZEN_DIRECTIONAL_EDGE,
        FROZEN_MIN_RR,
        FROZEN_OPPORTUNITY_THRESHOLD,
    )

    assert FROZEN_OPPORTUNITY_THRESHOLD == 70
    assert FROZEN_DIRECTIONAL_EDGE == 5
    assert FROZEN_MIN_RR == "1.20"
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
