"""Phase 1a — one-account-per-user multi-tenant registry (no LIVE MT5).

Proves registration / ownership / worker-assignment uniqueness only.
Does NOT prove simultaneous multi-user MT5 LIVE execution or provisioned
isolated terminals.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.broker import CreateBrokerAccountCommand
from app.application.use_cases.broker import CreateBrokerAccountUseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.entities.broker import Broker
from app.domain.entities.broker_integration import BrokerAccount
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerEnvironment,
    BrokerPlatform,
    BrokerStatus,
    BrokerType,
)
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.multi_account import REGISTRY_CAPABILITY_STATEMENT
from app.domain.multi_account.execution_worker_registry import (
    InMemoryExecutionWorkerRegistry,
    assert_tenant_safe_worker_metadata,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.ownership_claim import InMemoryOwnershipClaimRegistry
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionIntent,
    AccountExecutionState,
    CentralSignalIntent,
)
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from core.config.settings import Settings

pytestmark = [pytest.mark.unit]

_SECRET = "unit-test-secret-key-that-is-long-enough-32chars"


class _AuthOk:
    async def validate_credentials(
        self, *, login: str, password: str, server: str
    ) -> bool:
        _ = login, server
        return password == "correct-password"


class _AuthFail:
    async def validate_credentials(
        self, *, login: str, password: str, server: str
    ) -> bool:
        _ = login, password, server
        return False


def test_capability_statement_is_honest() -> None:
    text = REGISTRY_CAPABILITY_STATEMENT.lower()
    assert "one active mt5" in text
    assert "does not yet prove simultaneous" in text or (
        "does not yet support simultaneous" in text
    )


def test_migration_sql_enforces_db_uniqueness() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sql = (
        root / "supabase" / "migrations" / "20261109120000_multi_account_foundation.sql"
    ).read_text(encoding="utf-8")
    assert "broker_accounts_global_active_claim_uidx" in sql
    assert "broker_accounts_one_active_per_user_uidx" in sql
    assert "execution_workers_one_active_per_account_uidx" in sql
    assert "execution_workers_one_active_per_user_uidx" in sql
    assert "execution_workers_active_requires_account" in sql
    assert "ownership_verified" in sql
    assert "Simultaneous MT5 LIVE execution is NOT supported" in sql


def test_flags_remain_off() -> None:
    settings = Settings(_env_file=None)
    assert settings.multi_account_dispatch_enabled is False
    assert settings.multi_account_live_submit_enabled is False
    assert multi_account_dispatch_allowed(settings) is False
    assert multi_account_live_submit_allowed(settings) is False


def test_many_users_each_one_account() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    user_a, user_b, user_c, user_d = (uuid4() for _ in range(4))
    brokers = [uuid4() for _ in range(4)]

    a = registry.register_claim(
        user_id=user_a, broker_id=brokers[0], login="1001", server="Exness-MT5Real"
    )
    b = registry.register_claim(
        user_id=user_b, broker_id=brokers[1], login="2001", server="ICMarkets-Demo"
    )
    c = registry.register_claim(
        user_id=user_c, broker_id=brokers[2], login="3001", server="XM-MT5"
    )
    d = registry.register_claim(
        user_id=user_d, broker_id=brokers[3], login="4001", server="HFM-Live"
    )

    assert registry.active_for_user(user_a) == a
    assert registry.active_for_user(user_b) == b
    assert registry.active_for_user(user_c) == c
    assert registry.active_for_user(user_d) == d
    assert len(registry.list_for_user(user_a)) == 1


def test_second_active_account_for_same_user_rejected() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    user = uuid4()
    registry.register_claim(
        user_id=user, broker_id=uuid4(), login="1001", server="Srv-A"
    )
    with pytest.raises(ConflictError, match="already has an active MT5"):
        registry.register_claim(
            user_id=user, broker_id=uuid4(), login="1002", server="Srv-B"
        )


def test_duplicate_active_ownership_across_users_rejected() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    broker = uuid4()
    owner = registry.register_claim(
        user_id=uuid4(),
        broker_id=broker,
        login="7777",
        server="Broker-Server",
    )
    with pytest.raises(ConflictError, match="already claimed"):
        registry.register_claim(
            user_id=uuid4(),
            broker_id=broker,
            login="7777",
            server="Broker-Server",
        )
    other = registry.register_claim(
        user_id=uuid4(),
        broker_id=broker,
        login="7777",
        server="Broker-Server-2",
    )
    assert other.account_id != owner.account_id


@pytest.mark.asyncio
async def test_verify_requires_successful_auth() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    user = uuid4()
    claim = registry.register_claim(
        user_id=user, broker_id=uuid4(), login="8888", server="Srv"
    )

    with pytest.raises(ValidationError, match="authentication failed"):
        await registry.verify_ownership(
            account_id=claim.account_id,
            user_id=user,
            password="wrong",
            auth=_AuthFail(),
        )

    verified = await registry.verify_ownership(
        account_id=claim.account_id,
        user_id=user,
        password="correct-password",
        auth=_AuthOk(),
    )
    assert verified.ownership_verified is True
    assert verified.status == "active"
    assert verified.ownership_verified_at is not None


def test_revoke_releases_claim_for_reconnect() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    broker = uuid4()
    user_a, user_b = uuid4(), uuid4()
    first = registry.register_claim(
        user_id=user_a, broker_id=broker, login="9001", server="Srv"
    )
    registry.revoke(account_id=first.account_id, user_id=user_a)
    assert registry.active_for_user(user_a) is None
    second = registry.reconnect_claim(
        user_id=user_b, broker_id=broker, login="9001", server="Srv"
    )
    assert second.user_id == user_b
    assert second.ownership_verified is False

    # Same user may reconnect after revoke.
    registry.revoke(account_id=second.account_id, user_id=user_b)
    again = registry.register_claim(
        user_id=user_a, broker_id=broker, login="9001", server="Srv"
    )
    assert again.user_id == user_a


@pytest.mark.asyncio
async def test_cross_user_access_denied() -> None:
    registry = InMemoryOwnershipClaimRegistry()
    owner = uuid4()
    claim = registry.register_claim(
        user_id=owner, broker_id=uuid4(), login="42", server="Srv"
    )
    with pytest.raises(NotFoundError):
        registry.require_owner(account_id=claim.account_id, user_id=uuid4())
    with pytest.raises(NotFoundError):
        await registry.verify_ownership(
            account_id=claim.account_id,
            user_id=uuid4(),
            password="correct-password",
            auth=_AuthOk(),
        )


def test_worker_assignment_one_per_user_and_account() -> None:
    workers = InMemoryExecutionWorkerRegistry()
    user_a, user_b, user_c = uuid4(), uuid4(), uuid4()
    acct_a, acct_b, acct_c = uuid4(), uuid4(), uuid4()

    w_a = workers.assign(
        user_id=user_a,
        broker_account_id=acct_a,
        account_owner_user_id=user_a,
        worker_code="worker-a",
        metadata={"region": "eu", "host_label": "mt5-slot-1"},
    )
    w_b = workers.assign(
        user_id=user_b,
        broker_account_id=acct_b,
        account_owner_user_id=user_b,
        worker_code="worker-b",
    )
    w_c = workers.assign(
        user_id=user_c,
        broker_account_id=acct_c,
        account_owner_user_id=user_c,
        worker_code="worker-c",
    )
    assert workers.active_for_user(user_a) == w_a
    assert workers.active_for_user(user_b) == w_b
    assert workers.active_for_user(user_c) == w_c

    with pytest.raises(ConflictError, match="already has an active worker"):
        workers.assign(
            user_id=user_a,
            broker_account_id=acct_a,
            account_owner_user_id=user_a,
            worker_code="worker-a-dup",
        )

    with pytest.raises(NotFoundError):
        workers.assign(
            user_id=user_b,
            broker_account_id=acct_a,
            account_owner_user_id=user_a,
            worker_code="worker-steal",
        )

    # Disconnect A does not affect B/C.
    workers.disable(worker_id=w_a.worker_id, user_id=user_a)
    assert workers.active_for_user(user_a) is None
    assert workers.active_for_user(user_b) == w_b
    assert workers.active_for_user(user_c) == w_c

    reconnected = workers.assign(
        user_id=user_a,
        broker_account_id=acct_a,
        account_owner_user_id=user_a,
        worker_code="worker-a-reconnect",
    )
    assert reconnected.worker_id != w_a.worker_id


def test_worker_metadata_rejects_secrets() -> None:
    with pytest.raises(ValidationError, match="must not contain credentials"):
        assert_tenant_safe_worker_metadata({"password": "x", "region": "eu"})
    with pytest.raises(ValidationError, match="must not contain credentials"):
        assert_tenant_safe_worker_metadata({"api_token": "abc"})
    safe = assert_tenant_safe_worker_metadata({"region": "eu", "slot": 3})
    assert safe == {"region": "eu", "slot": 3}


def test_signal_isolation_and_idempotency_models() -> None:
    signal = CentralSignalIntent.create(
        symbol="XAUUSD",
        side="BUY",
        quality=80,
        idempotency_key="central-sig-1",
    )
    user_a, user_b = uuid4(), uuid4()
    acct_a, acct_b = uuid4(), uuid4()
    exec_a = AccountExecutionIntent.for_account(
        signal=signal, user_id=user_a, broker_account_id=acct_a
    )
    exec_b = AccountExecutionIntent.for_account(
        signal=signal, user_id=user_b, broker_account_id=acct_b
    )
    blocked = exec_a.transition(
        AccountExecutionState.BLOCKED, block_reason="daily_loss_halt"
    )
    eligible = exec_b.transition(AccountExecutionState.ELIGIBLE)
    assert blocked.is_terminal
    assert eligible.state is AccountExecutionState.ELIGIBLE
    assert exec_a.idempotency_key != exec_b.idempotency_key


@pytest.mark.asyncio
async def test_memory_broker_repo_enforces_one_per_user_and_global_claim() -> None:
    factory = MemoryBrokerUnitOfWorkFactory()
    async with factory() as uow:
        broker = Broker.register(
            name="Demo Broker",
            slug="demo-broker-phase1a",
            broker_type=BrokerType.RETAIL,
            platform_code=BrokerPlatform.MT5,
        )
        broker.activate()
        assert broker.status is BrokerStatus.ACTIVE
        await uow.brokers.add(broker)

        user_a, user_b = uuid4(), uuid4()
        acct_a = BrokerAccount.link(
            user_id=user_a,
            broker_id=broker.id,
            external_account_id="5555",
            server="Demo-Server",
            environment=BrokerEnvironment.DEMO,
        )
        await uow.accounts.add(acct_a)

        second_for_a = BrokerAccount.link(
            user_id=user_a,
            broker_id=broker.id,
            external_account_id="5556",
            server="Demo-Server-2",
            environment=BrokerEnvironment.DEMO,
        )
        with pytest.raises(ConflictError, match="already has an active MT5"):
            await uow.accounts.add(second_for_a)

        conflict = BrokerAccount.link(
            user_id=user_b,
            broker_id=broker.id,
            external_account_id="5555",
            server="Demo-Server",
            environment=BrokerEnvironment.DEMO,
        )
        with pytest.raises(ConflictError, match="already claimed"):
            await uow.accounts.add(conflict)

        acct_a.revoke()
        await uow.accounts.update(acct_a)
        assert acct_a.status is BrokerAccountStatus.REVOKED
        await uow.accounts.add(conflict)
        claimed = await uow.accounts.get_active_global_claim(
            broker.id, server="Demo-Server", external_account_id="5555"
        )
        assert claimed is not None
        assert claimed.user_id == user_b
        owned = await uow.accounts.get_non_revoked_for_user(user_b)
        assert owned is not None and owned.id == conflict.id


@pytest.mark.asyncio
async def test_create_broker_account_use_case_one_per_user() -> None:
    broker_factory = MemoryBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=broker_factory)  # type: ignore[arg-type]
    use_case = CreateBrokerAccountUseCase(
        uow_factory=broker_factory,
        audit=audit,
        encryption_key=_SECRET,
    )

    async with broker_factory() as uow:
        broker = Broker.register(
            name="Weltrade Demo",
            slug="weltrade-demo-phase1a",
            broker_type=BrokerType.RETAIL,
            platform_code=BrokerPlatform.MT5,
        )
        broker.activate()
        await uow.brokers.add(broker)
        broker_id = broker.id

    user = uuid4()
    first = await use_case.execute(
        CreateBrokerAccountCommand(
            user_id=user,
            broker_id=broker_id,
            external_account_id="1111",
            server="Weltrade-Demo",
            label="Primary",
            environment=BrokerEnvironment.DEMO,
            password="secret-pass",
        )
    )
    assert first.external_account_id == "1111"

    with pytest.raises(ConflictError, match="already has an active MT5"):
        await use_case.execute(
            CreateBrokerAccountCommand(
                user_id=user,
                broker_id=broker_id,
                external_account_id="2222",
                server="Weltrade-Demo",
                label="Second",
                environment=BrokerEnvironment.DEMO,
                password="secret-pass",
            )
        )
