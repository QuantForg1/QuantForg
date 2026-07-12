"""Application facade for Broker Foundation endpoints."""

from __future__ import annotations

from dataclasses import dataclass

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
    RegisterBrokerUseCase,
    UpdateBrokerAccountUseCase,
    UpdateBrokerUseCase,
    ValidateBrokerUseCase,
)
from app.application.use_cases.broker_health import (
    GetBrokerDiagnosticsUseCase,
    GetBrokerHealthUseCase,
)
from app.domain.interfaces.broker_registry import BrokerRegistryPort


@dataclass(frozen=True, slots=True)
class BrokerService:
    list_brokers: ListBrokersUseCase
    get_broker: GetBrokerUseCase
    create_broker: CreateBrokerUseCase
    register_broker: RegisterBrokerUseCase
    update_broker: UpdateBrokerUseCase
    delete_broker: DeleteBrokerUseCase
    list_accounts: ListBrokerAccountsUseCase
    get_account: GetBrokerAccountUseCase
    create_account: CreateBrokerAccountUseCase
    update_account: UpdateBrokerAccountUseCase
    delete_account: DeleteBrokerAccountUseCase
    list_connections: ListBrokerConnectionsUseCase
    get_connection: GetBrokerConnectionUseCase
    connect_broker: ConnectBrokerUseCase
    disconnect_broker: DisconnectBrokerUseCase
    validate_broker: ValidateBrokerUseCase
    get_broker_health: GetBrokerHealthUseCase
    get_broker_diagnostics: GetBrokerDiagnosticsUseCase
    registry: BrokerRegistryPort
