"""Domain value objects — immutable, validated building blocks."""

from app.domain.value_objects.base import ValueObject
from app.domain.value_objects.broker import (
    AccountId,
    BrokerId,
    BrokerRegion,
    ServerName,
)
from app.domain.value_objects.confidence import Confidence
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import (
    AccountNumber,
    EntitySlug,
    Leverage,
    PersonName,
    PipSize,
    SymbolCode,
    VersionLabel,
)
from app.domain.value_objects.market import Percentage, Price, Quantity
from app.domain.value_objects.money import CurrencyCode, Money

__all__ = [
    "AccountId",
    "AccountNumber",
    "BrokerId",
    "BrokerRegion",
    "Confidence",
    "CurrencyCode",
    "EmailAddress",
    "EntitySlug",
    "Leverage",
    "Money",
    "Percentage",
    "PersonName",
    "PipSize",
    "Price",
    "Quantity",
    "ServerName",
    "SymbolCode",
    "ValueObject",
    "VersionLabel",
]
