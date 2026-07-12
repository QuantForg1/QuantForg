"""Symbol enumerations."""

from __future__ import annotations

from enum import StrEnum


class SymbolAssetClass(StrEnum):
    """Asset class of a tradable symbol."""

    FOREX = "forex"
    METALS = "metals"
    INDICES = "indices"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"
    STOCKS = "stocks"
    OTHER = "other"


class SymbolStatus(StrEnum):
    """Tradability status of a symbol."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELISTED = "delisted"
