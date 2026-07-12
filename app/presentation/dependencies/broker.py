"""FastAPI dependencies for Broker Foundation."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

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


def get_broker_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BrokerService:
    uow_factory = get_broker_uow_factory()
    audit = RecordAuditEventUseCase(uow_factory=uow_factory)  # type: ignore[arg-type]
    encryption_key = settings.secret_key.get_secret_value()
    registry = get_broker_registry()
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
        ),
        update_account=UpdateBrokerAccountUseCase(
            uow_factory=uow_factory,
            audit=audit,
            encryption_key=encryption_key,
        ),
        delete_account=DeleteBrokerAccountUseCase(uow_factory=uow_factory, audit=audit),
        list_connections=ListBrokerConnectionsUseCase(uow_factory=uow_factory),
        get_connection=GetBrokerConnectionUseCase(uow_factory=uow_factory),
        connect_broker=ConnectBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
            encryption_key=encryption_key,
        ),
        disconnect_broker=DisconnectBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
        ),
        validate_broker=ValidateBrokerUseCase(
            uow_factory=uow_factory,
            audit=audit,
            registry=registry,
            encryption_key=encryption_key,
        ),
        registry=registry,
    )


BrokerSvc = Annotated[BrokerService, Depends(get_broker_service)]
