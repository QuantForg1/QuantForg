"""FastAPI dependencies for Broker Foundation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.application.services.broker_health import (
    AutomaticReconnectManager,
    ConnectionHealthMonitor,
)
from app.application.services.broker_service import BrokerService
from app.application.use_cases.broker import (
    ConnectBrokerUseCase,
    CreateBrokerAccountUseCase,
    CreateBrokerUseCase,
    DeleteBrokerAccountUseCase,
    DeleteBrokerUseCase,
    DisconnectBrokerUseCase,
    GetBrokerAccountUseCase,
    GetBrokerConnectionUseCase,
    GetBrokerUseCase,
    ListBrokerAccountsUseCase,
    ListBrokerConnectionsUseCase,
    ListBrokersUseCase,
    UpdateBrokerAccountUseCase,
    UpdateBrokerUseCase,
    ValidateBrokerUseCase,
)
from app.application.use_cases.broker_health import (
    GetBrokerDiagnosticsUseCase,
    GetBrokerHealthUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.interfaces.broker_uow import BrokerUnitOfWorkFactory
from app.infrastructure.brokers.registry import BrokerRegistry
from core.config.settings import Settings, get_settings
from core.di.container import get_container


def get_broker_uow_factory() -> BrokerUnitOfWorkFactory:
    factory = getattr(get_container(), "broker_uow_factory", None)
    if factory is None:
        msg = "Broker Unit of Work factory is not available"
        raise RuntimeError(msg)
    return factory  # type: ignore[no-any-return]


def get_broker_registry() -> BrokerRegistry:
    registry = getattr(get_container(), "broker_registry", None)
    if registry is None:
        msg = "Broker registry is not available"
        raise RuntimeError(msg)
    return registry  # type: ignore[no-any-return]


def get_broker_health_monitor() -> ConnectionHealthMonitor:
    monitor = getattr(get_container(), "broker_health_monitor", None)
    if monitor is None:
        msg = "Broker health monitor is not available"
        raise RuntimeError(msg)
    return monitor  # type: ignore[no-any-return]


def get_broker_reconnect_manager() -> AutomaticReconnectManager:
    manager = getattr(get_container(), "broker_reconnect_manager", None)
    if manager is None:
        msg = "Broker reconnect manager is not available"
        raise RuntimeError(msg)
    return manager  # type: ignore[no-any-return]


def get_broker_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BrokerService:
    uow_factory = get_broker_uow_factory()
    audit = RecordAuditEventUseCase(uow_factory=uow_factory)  # type: ignore[arg-type]
    encryption_key = settings.secret_key.get_secret_value()
    previous_keys = tuple(
        k.get_secret_value() for k in settings.credential_encryption_previous_keys
    )
    key_version = settings.encryption_key_version
    registry = get_broker_registry()
    health_monitor = get_broker_health_monitor()
    reconnect_manager = get_broker_reconnect_manager()
    create_broker = CreateBrokerUseCase(uow_factory=uow_factory, audit=audit)
    return BrokerService(
        list_brokers=ListBrokersUseCase(uow_factory=uow_factory),
        get_broker=GetBrokerUseCase(uow_factory=uow_factory),
        create_broker=create_broker,
        register_broker=create_broker,
        update_broker=UpdateBrokerUseCase(uow_factory=uow_factory, audit=audit),
        delete_broker=DeleteBrokerUseCase(uow_factory=uow_factory, audit=audit),
        list_accounts=ListBrokerAccountsUseCase(uow_factory=uow_factory),
        get_account=GetBrokerAccountUseCase(uow_factory=uow_factory),
        create_account=CreateBrokerAccountUseCase(
            uow_factory=uow_factory,
            audit=audit,
            encryption_key=encryption_key,
            encryption_key_version=key_version,
            previous_encryption_keys=previous_keys,
        ),
        update_account=UpdateBrokerAccountUseCase(
            uow_factory=uow_factory,
            audit=audit,
            encryption_key=encryption_key,
            encryption_key_version=key_version,
            previous_encryption_keys=previous_keys,
        ),
        delete_account=DeleteBrokerAccountUseCase(uow_factory=uow_factory, audit=audit),
        list_connections=ListBrokerConnectionsUseCase(uow_factory=uow_factory),
        get_connection=GetBrokerConnectionUseCase(uow_factory=uow_factory),
        connect_broker=ConnectBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
            encryption_key=encryption_key,
            health_monitor=health_monitor,
            reconnect_manager=reconnect_manager,
        ),
        disconnect_broker=DisconnectBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
            health_monitor=health_monitor,
            reconnect_manager=reconnect_manager,
        ),
        validate_broker=ValidateBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
            encryption_key=encryption_key,
        ),
        get_broker_health=GetBrokerHealthUseCase(
            uow_factory=uow_factory,
            health_monitor=health_monitor,
        ),
        get_broker_diagnostics=GetBrokerDiagnosticsUseCase(
            uow_factory=uow_factory,
            health_monitor=health_monitor,
            reconnect_manager=reconnect_manager,
            registry=registry,
        ),
        registry=registry,
    )


BrokerSvc = Annotated[BrokerService, Depends(get_broker_service)]
