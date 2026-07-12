"""Domain enumerations for QuantForg.

All enums are string-backed (``StrEnum``) so they serialize cleanly to JSON
and database columns without opaque integer mappings.
"""

from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.broker import BrokerStatus, BrokerType
from app.domain.enums.license import LicenseStatus, LicenseTier
from app.domain.enums.order import OrderSide, OrderStatus, OrderType, TimeInForce
from app.domain.enums.position import PositionSide, PositionStatus
from app.domain.enums.risk import RiskLevel
from app.domain.enums.signal import SignalDirection, SignalSource, SignalStatus
from app.domain.enums.strategy import StrategyStatus, StrategyType
from app.domain.enums.symbol import SymbolAssetClass, SymbolStatus
from app.domain.enums.trading_account import AccountStatus, AccountType
from app.domain.enums.trading_session import SessionStatus
from app.domain.enums.user import UserRole, UserStatus

__all__ = [
    "AccountStatus",
    "AccountType",
    "AuditAction",
    "AuditOutcome",
    "BrokerStatus",
    "BrokerType",
    "LicenseStatus",
    "LicenseTier",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "PositionSide",
    "PositionStatus",
    "RiskLevel",
    "SessionStatus",
    "SignalDirection",
    "SignalSource",
    "SignalStatus",
    "StrategyStatus",
    "StrategyType",
    "SymbolAssetClass",
    "SymbolStatus",
    "TimeInForce",
    "UserRole",
    "UserStatus",
]
