"""Risk profile enumerations."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    """Qualitative risk appetite classification."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"
