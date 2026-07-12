"""Domain layer — pure business concepts for QuantForg.

Contains entities, value objects, enumerations, exceptions, and ports.
Zero framework, database, or HTTP dependencies beyond Pydantic for
value-object validation.
"""

from app.domain import enums as enums
from app.domain.entities import (
    AuditLog,
    Broker,
    Entity,
    License,
    Order,
    Position,
    RiskProfile,
    Signal,
    StrategyMetadata,
    Symbol,
    Trade,
    TradingAccount,
    TradingSession,
    User,
)
from app.domain.exceptions import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)
from app.domain.value_objects import (
    AccountNumber,
    Confidence,
    CurrencyCode,
    EmailAddress,
    EntitySlug,
    Leverage,
    Money,
    Percentage,
    PersonName,
    PipSize,
    Price,
    Quantity,
    SymbolCode,
    ValueObject,
    VersionLabel,
)

__all__ = [
    "AccountNumber",
    "AuditLog",
    "Broker",
    "Confidence",
    "ConflictError",
    "CurrencyCode",
    "DomainError",
    "EmailAddress",
    "Entity",
    "EntitySlug",
    "Leverage",
    "License",
    "Money",
    "NotFoundError",
    "Order",
    "Percentage",
    "PersonName",
    "PipSize",
    "Position",
    "Price",
    "Quantity",
    "RiskProfile",
    "Signal",
    "StrategyMetadata",
    "Symbol",
    "SymbolCode",
    "Trade",
    "TradingAccount",
    "TradingSession",
    "User",
    "ValidationError",
    "ValueObject",
    "VersionLabel",
    "enums",
]
