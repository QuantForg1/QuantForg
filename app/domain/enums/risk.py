"""Risk profile and risk-engine enumerations."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    """Qualitative risk appetite classification (policy profile)."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class RiskDecision(StrEnum):
    """Risk engine gate outcome — never EXECUTE."""

    ALLOW = "allow"
    REDUCE_SIZE = "reduce_size"
    REJECT = "reject"


class RiskScoreBand(StrEnum):
    """Discrete band derived from a 0-100 risk score."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class PositionSizingMethod(StrEnum):
    """Supported position-sizing strategies."""

    FIXED_LOT = "fixed_lot"
    FIXED_DOLLAR_RISK = "fixed_dollar_risk"
    PERCENTAGE_RISK = "percentage_risk"
    ATR_BASED = "atr_based"
