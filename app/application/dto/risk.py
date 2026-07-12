"""Risk profile validation DTOs."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ValidateRiskProfileCommand:
    """Input for ValidateRiskProfileUseCase.

    Evaluates a *proposed* exposure against stored risk limits.
    Does not place orders or compute trading signals.
    """

    risk_profile_id: UUID | None = None
    user_id: UUID | None = None
    trading_account_id: UUID | None = None
    proposed_risk_percent: str = "0"
    proposed_leverage: int = 1
    current_open_positions: int = 0


@dataclass(frozen=True, slots=True)
class RiskValidationDTO:
    """Result of validating a proposal against a risk profile."""

    is_valid: bool
    risk_profile_id: UUID
    risk_level: str
    violations: tuple[str, ...] = field(default_factory=tuple)
    max_risk_per_trade: str = ""
    max_daily_loss: str = ""
    max_open_positions: int = 0
    max_leverage: int = 0
