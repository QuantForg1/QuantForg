"""Application DTOs — immutable data carriers across the application boundary."""

from app.application.dto.audit import AuditEventDTO, RecordAuditEventCommand
from app.application.dto.broker import BrokerDTO, CreateBrokerCommand
from app.application.dto.health import DependencyStatus, HealthReport, HealthStatus
from app.application.dto.license import ActivateLicenseCommand, LicenseDTO
from app.application.dto.risk import RiskValidationDTO, ValidateRiskProfileCommand
from app.application.dto.signal import CreateSignalRecordCommand, SignalDTO
from app.application.dto.trading_account import (
    ConnectTradingAccountCommand,
    TradingAccountDTO,
)
from app.application.dto.trading_session import (
    CloseTradingSessionCommand,
    OpenTradingSessionCommand,
    TradingSessionDTO,
)
from app.application.dto.user import RegisterUserCommand, UserDTO
from app.application.dto.version import VersionInfo

__all__ = [
    "ActivateLicenseCommand",
    "AuditEventDTO",
    "BrokerDTO",
    "CloseTradingSessionCommand",
    "ConnectTradingAccountCommand",
    "CreateBrokerCommand",
    "CreateSignalRecordCommand",
    "DependencyStatus",
    "HealthReport",
    "HealthStatus",
    "LicenseDTO",
    "OpenTradingSessionCommand",
    "RecordAuditEventCommand",
    "RegisterUserCommand",
    "RiskValidationDTO",
    "SignalDTO",
    "TradingAccountDTO",
    "TradingSessionDTO",
    "UserDTO",
    "ValidateRiskProfileCommand",
    "VersionInfo",
]
