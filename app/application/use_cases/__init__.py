"""Application use cases — orchestration of domain operations.

Each use case depends solely on domain ports (Dependency Inversion),
accepts a command DTO, and returns a result DTO. No SQL, HTTP, or
infrastructure imports belong here.
"""

from app.application.use_cases.activate_license import ActivateLicenseUseCase
from app.application.use_cases.close_trading_session import CloseTradingSessionUseCase
from app.application.use_cases.connect_trading_account import (
    ConnectTradingAccountUseCase,
)
from app.application.use_cases.create_broker import CreateBrokerUseCase
from app.application.use_cases.create_signal_record import CreateSignalRecordUseCase
from app.application.use_cases.get_health import GetHealthUseCase
from app.application.use_cases.get_version import GetVersionUseCase
from app.application.use_cases.open_trading_session import OpenTradingSessionUseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.application.use_cases.validate_risk_profile import ValidateRiskProfileUseCase

__all__ = [
    "ActivateLicenseUseCase",
    "CloseTradingSessionUseCase",
    "ConnectTradingAccountUseCase",
    "CreateBrokerUseCase",
    "CreateSignalRecordUseCase",
    "GetHealthUseCase",
    "GetVersionUseCase",
    "OpenTradingSessionUseCase",
    "RecordAuditEventUseCase",
    "RegisterUserUseCase",
    "ValidateRiskProfileUseCase",
]
