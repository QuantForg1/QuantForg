"""Unit tests for Broker Foundation use cases and registry."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.broker import (
    CreateBrokerAccountCommand,
    CreateBrokerCommand,
    DeleteBrokerAccountCommand,
    DeleteBrokerCommand,
    UpdateBrokerAccountCommand,
    UpdateBrokerCommand,
)
from app.application.services.broker_health import (
    AutomaticReconnectManager,
    ConnectionHealthMonitor,
)
from app.application.use_cases.broker import (
    CreateBrokerAccountUseCase,
    CreateBrokerUseCase,
    DeleteBrokerAccountUseCase,
    DeleteBrokerUseCase,
    GetBrokerAccountUseCase,
    ListBrokerAccountsUseCase,
    ListBrokersUseCase,
    UpdateBrokerAccountUseCase,
    UpdateBrokerUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.broker import (
    BrokerAccountStatus,
    BrokerCapabilityCode,
    BrokerEnvironment,
    BrokerPlatform,
    BrokerStatus,
)
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.infrastructure.brokers.registry import BrokerRegistry
from core.security.crypto import decrypt_secret
from tests.unit.fakes_broker import SharedBrokerUnitOfWorkFactory

_SECRET = "unit-test-secret-key-that-is-long-enough-32chars"


def _wire() -> tuple[SharedBrokerUnitOfWorkFactory, RecordAuditEventUseCase]:
    factory = SharedBrokerUnitOfWorkFactory()
    audit = RecordAuditEventUseCase(uow_factory=factory)  # type: ignore[arg-type]
    return factory, audit


@pytest.mark.unit
class TestBrokerCatalogue:
    @pytest.mark.asyncio
    async def test_create_list_and_update_broker(self) -> None:
        factory, audit = _wire()
        created = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="Demo MT5 Venue",
                slug="demo-mt5",
                platform_code=BrokerPlatform.MT5,
                country_code="cy",
                activate=True,
                capability_codes=(
                    BrokerCapabilityCode.CONNECT,
                    BrokerCapabilityCode.SYMBOLS,
                ),
            )
        )
        assert created.status == BrokerStatus.ACTIVE.value
        assert created.platform_code == "mt5"
        assert "connect" in created.capabilities
        assert "symbols" in created.capabilities

        listed = await ListBrokersUseCase(uow_factory=factory).execute()
        assert len(listed) == 1

        updated = await UpdateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            UpdateBrokerCommand(
                broker_id=created.id,
                description="Updated description",
                status=BrokerStatus.INACTIVE,
            )
        )
        assert updated.description == "Updated description"
        assert updated.status == BrokerStatus.INACTIVE.value

    @pytest.mark.asyncio
    async def test_duplicate_slug_rejected(self) -> None:
        factory, audit = _wire()
        cmd = CreateBrokerCommand(name="A", slug="same-slug", country_code="US")
        await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(cmd)
        with pytest.raises(ConflictError):
            await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(cmd)

    @pytest.mark.asyncio
    async def test_delete_blocked_when_accounts_linked(self) -> None:
        factory, audit = _wire()
        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="Linked",
                slug="linked-broker",
                country_code="US",
                activate=True,
            )
        )
        await CreateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            CreateBrokerAccountCommand(
                user_id=uuid4(),
                broker_id=broker.id,
                external_account_id="1001",
                password="super-secret-password",
            )
        )
        with pytest.raises(ConflictError):
            await DeleteBrokerUseCase(uow_factory=factory, audit=audit).execute(
                DeleteBrokerCommand(broker_id=broker.id)
            )


@pytest.mark.unit
class TestBrokerAccounts:
    @pytest.mark.asyncio
    async def test_create_encrypts_password_and_hides_secret(self) -> None:
        factory, audit = _wire()
        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="Secure",
                slug="secure-broker",
                country_code="US",
                activate=True,
            )
        )
        user_id = uuid4()
        account = await CreateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            CreateBrokerAccountCommand(
                user_id=user_id,
                broker_id=broker.id,
                external_account_id="ACCT-42",
                label="Demo",
                environment=BrokerEnvironment.DEMO,
                password="never-expose-me",
            )
        )
        assert account.credential_types == ("password",)
        assert account.connection_status == "disconnected"
        assert not any(
            isinstance(v, str) and v == "never-expose-me"
            for v in (
                account.external_account_id,
                account.label,
                account.server,
                *account.metadata.values(),
                *account.credential_types,
            )
        )

        stored = await factory.uow.credentials.list_for_account(account.id)
        assert len(stored) == 1
        assert stored[0].encrypted_payload != "never-expose-me"
        assert decrypt_secret(stored[0].encrypted_payload, secret_key=_SECRET) == (
            "never-expose-me"
        )
        public = stored[0].to_dict()
        assert "encrypted_payload" not in public
        assert public["has_secret"] is True

    @pytest.mark.asyncio
    async def test_inactive_broker_rejects_new_accounts(self) -> None:
        factory, audit = _wire()
        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="Pending Only",
                slug="pending-broker",
                country_code="US",
                activate=False,
            )
        )
        with pytest.raises(ValidationError):
            await CreateBrokerAccountUseCase(
                uow_factory=factory, audit=audit, encryption_key=_SECRET
            ).execute(
                CreateBrokerAccountCommand(
                    user_id=uuid4(),
                    broker_id=broker.id,
                    external_account_id="1",
                )
            )

    @pytest.mark.asyncio
    async def test_update_and_revoke_account(self) -> None:
        factory, audit = _wire()
        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="Revoke Me",
                slug="revoke-broker",
                country_code="US",
                activate=True,
            )
        )
        user_id = uuid4()
        created = await CreateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            CreateBrokerAccountCommand(
                user_id=user_id,
                broker_id=broker.id,
                external_account_id="9001",
                password="initial",
            )
        )
        updated = await UpdateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            UpdateBrokerAccountCommand(
                user_id=user_id,
                account_id=created.id,
                label="Live desk",
                status=BrokerAccountStatus.ACTIVE,
                password="rotated-secret",
            )
        )
        assert updated.label == "Live desk"
        assert updated.status == BrokerAccountStatus.ACTIVE.value

        await DeleteBrokerAccountUseCase(uow_factory=factory, audit=audit).execute(
            DeleteBrokerAccountCommand(user_id=user_id, account_id=created.id)
        )
        listed = await ListBrokerAccountsUseCase(uow_factory=factory).execute(
            user_id=user_id
        )
        assert listed[0].status == BrokerAccountStatus.REVOKED.value
        assert await factory.uow.credentials.list_for_account(created.id) == []
        assert await factory.uow.connections.get_for_account(created.id) is None

        with pytest.raises(NotFoundError):
            await GetBrokerAccountUseCase(uow_factory=factory).execute(
                user_id=uuid4(), account_id=created.id
            )


@pytest.mark.unit
class TestBrokerRegistry:
    def test_placeholders_register(self) -> None:
        from app.infrastructure.brokers.placeholders import (
            register_placeholder_adapters,
        )

        registry = BrokerRegistry()
        register_placeholder_adapters(registry)
        assert registry.list_platforms() == ["ctrader", "dxtrade", "mt4", "mt5"]
        assert registry.has("mt5")


class _FakeAdapter:
    platform_code = "mt5"

    async def connect(self, request: object) -> str:
        return "session-ref-1"

    async def disconnect(self, *, session_ref: str) -> None:
        return None

    async def validate_credentials(self, request: object) -> bool:
        return True

    async def refresh_session(self, *, session_ref: str) -> str:
        return session_ref

    async def list_accounts(self, *, session_ref: str) -> list[object]:
        return []

    async def get_account_info(self, *, session_ref: str) -> object:
        raise NotImplementedError

    async def get_balance(self, *, session_ref: str) -> object:
        raise NotImplementedError

    async def get_equity(self, *, session_ref: str) -> object:
        raise NotImplementedError

    async def get_symbols(self, *, session_ref: str) -> list[object]:
        return []

    async def get_positions(self, *, session_ref: str) -> list[object]:
        return []

    async def get_orders(self, *, session_ref: str) -> list[object]:
        return []


@pytest.mark.unit
class TestConnectDisconnectValidate:
    @pytest.mark.asyncio
    async def test_connect_disconnect_with_fake_adapter(self) -> None:
        from app.application.dto.broker import (
            ConnectBrokerCommand,
            DisconnectBrokerCommand,
            ValidateBrokerCommand,
        )
        from app.application.use_cases.broker import (
            ConnectBrokerUseCase,
            DisconnectBrokerUseCase,
            ValidateBrokerUseCase,
        )
        from app.domain.enums.broker import BrokerPlatform

        factory, audit = _wire()
        registry = BrokerRegistry()
        registry.register(_FakeAdapter())  # type: ignore[arg-type]

        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="MT5 Fake",
                slug="mt5-fake",
                platform_code=BrokerPlatform.MT5,
                country_code="US",
                activate=True,
            )
        )
        user_id = uuid4()
        account = await CreateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            CreateBrokerAccountCommand(
                user_id=user_id,
                broker_id=broker.id,
                external_account_id="777",
                password="demo-pass",
            )
        )

        valid = await ValidateBrokerUseCase(
            uow_factory=factory,
            audit=audit,
            registry=registry,
            encryption_key=_SECRET,
        ).execute(ValidateBrokerCommand(user_id=user_id, account_id=account.id))
        assert valid.valid is True

        connected = await ConnectBrokerUseCase(
            uow_factory=factory,
            audit=audit,
            registry=registry,
            encryption_key=_SECRET,
            health_monitor=ConnectionHealthMonitor(),
            reconnect_manager=AutomaticReconnectManager(),
        ).execute(ConnectBrokerCommand(user_id=user_id, account_id=account.id))
        assert connected.status == "connected"
        assert connected.adapter_session_ref == "session-ref-1"
        assert connected.session_id is not None

        disconnected = await DisconnectBrokerUseCase(
            uow_factory=factory,
            audit=audit,
            registry=registry,
            health_monitor=ConnectionHealthMonitor(),
            reconnect_manager=AutomaticReconnectManager(),
        ).execute(DisconnectBrokerCommand(user_id=user_id, account_id=account.id))
        assert disconnected.status == "disconnected"

    @pytest.mark.asyncio
    async def test_placeholder_connect_fails_cleanly(self) -> None:
        from app.application.dto.broker import ConnectBrokerCommand
        from app.application.use_cases.broker import ConnectBrokerUseCase
        from app.domain.enums.broker import BrokerPlatform
        from app.infrastructure.brokers.placeholders import (
            register_placeholder_adapters,
        )

        factory, audit = _wire()
        registry = BrokerRegistry()
        register_placeholder_adapters(registry)

        broker = await CreateBrokerUseCase(uow_factory=factory, audit=audit).execute(
            CreateBrokerCommand(
                name="MT5 Placeholder",
                slug="mt5-placeholder",
                platform_code=BrokerPlatform.MT5,
                country_code="US",
                activate=True,
            )
        )
        user_id = uuid4()
        account = await CreateBrokerAccountUseCase(
            uow_factory=factory, audit=audit, encryption_key=_SECRET
        ).execute(
            CreateBrokerAccountCommand(
                user_id=user_id,
                broker_id=broker.id,
                external_account_id="888",
                password="demo-pass",
            )
        )
        with pytest.raises(ValidationError):
            await ConnectBrokerUseCase(
                uow_factory=factory,
                audit=audit,
                registry=registry,
                encryption_key=_SECRET,
                health_monitor=ConnectionHealthMonitor(),
                reconnect_manager=AutomaticReconnectManager(),
            ).execute(ConnectBrokerCommand(user_id=user_id, account_id=account.id))


@pytest.mark.unit
class TestBrokerValueObjectsAndEvents:
    def test_value_objects(self) -> None:
        from app.domain.value_objects.broker import (
            AccountId,
            BrokerId,
            BrokerRegion,
            ServerName,
        )

        bid = BrokerId.of(uuid4())
        assert str(bid)
        assert str(AccountId.of(uuid4()))
        assert ServerName.of("Demo-Server").value == "Demo-Server"
        assert BrokerRegion.of("eu").value == "EU"

    def test_domain_events(self) -> None:
        from app.domain.events.broker import (
            BrokerConnected,
            BrokerDeleted,
            BrokerDisconnected,
            BrokerRegistered,
            CredentialsUpdated,
        )

        broker_id = uuid4()
        account_id = uuid4()
        connection_id = uuid4()
        assert (
            BrokerRegistered(
                broker_id=broker_id, slug="x", platform_code="mt5"
            ).event_type
            == "broker.registered"
        )
        assert (
            BrokerConnected(
                broker_id=broker_id,
                broker_account_id=account_id,
                connection_id=connection_id,
            ).event_type
            == "broker.connected"
        )
        assert (
            BrokerDisconnected(
                broker_id=broker_id,
                broker_account_id=account_id,
                connection_id=connection_id,
            ).event_type
            == "broker.disconnected"
        )
        assert (
            CredentialsUpdated(
                broker_account_id=account_id, credential_types=("password",)
            ).event_type
            == "broker.credentials_updated"
        )
        assert (
            BrokerDeleted(broker_id=broker_id, slug="x").event_type == "broker.deleted"
        )
