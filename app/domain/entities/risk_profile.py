"""RiskProfile aggregate — risk limits bound to a user or account.

Why this entity exists
----------------------
RiskProfile captures declared risk appetite and hard limits (max risk per
trade, max daily loss, max open positions, max leverage). Application
services will later *enforce* these limits. This entity only defines and
validates the policy values — it does not run risk engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.risk import RiskLevel
from app.domain.value_objects.identity import Leverage
from app.domain.value_objects.market import Percentage


@dataclass(eq=False, kw_only=True)
class RiskProfile(Entity):
    """Rich domain model for a risk policy profile."""

    user_id: UUID
    trading_account_id: UUID | None = None
    risk_level: RiskLevel = RiskLevel.MODERATE
    max_risk_per_trade: Percentage = None  # type: ignore[assignment]
    max_daily_loss: Percentage = None  # type: ignore[assignment]
    max_open_positions: int = 5
    max_leverage: Leverage = None  # type: ignore[assignment]
    is_active: bool = True
    label: str = "default"

    def __post_init__(self) -> None:
        if self.max_risk_per_trade is None:
            self.max_risk_per_trade = Percentage.of("1")
        if self.max_daily_loss is None:
            self.max_daily_loss = Percentage.of("5")
        if self.max_leverage is None:
            self.max_leverage = Leverage.of(100)
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(
            self.max_open_positions >= 1,
            "max_open_positions must be at least 1",
            max_open_positions=self.max_open_positions,
        )
        require(
            self.max_open_positions <= 500,
            "max_open_positions exceeds maximum of 500",
            max_open_positions=self.max_open_positions,
        )
        require(
            self.max_risk_per_trade.value <= self.max_daily_loss.value,
            "max_risk_per_trade cannot exceed max_daily_loss",
            max_risk_per_trade=str(self.max_risk_per_trade.value),
            max_daily_loss=str(self.max_daily_loss.value),
        )
        require(bool(self.label.strip()), "label must not be blank")

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        trading_account_id: UUID | None = None,
        risk_level: RiskLevel = RiskLevel.MODERATE,
        max_risk_per_trade: Percentage | str = "1",
        max_daily_loss: Percentage | str = "5",
        max_open_positions: int = 5,
        max_leverage: Leverage | int = 100,
        label: str = "default",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: create an active risk profile with validated limits."""
        risk_pct = (
            max_risk_per_trade
            if isinstance(max_risk_per_trade, Percentage)
            else Percentage.of(max_risk_per_trade)
        )
        daily_pct = (
            max_daily_loss
            if isinstance(max_daily_loss, Percentage)
            else Percentage.of(max_daily_loss)
        )
        lev = (
            max_leverage
            if isinstance(max_leverage, Leverage)
            else Leverage.of(max_leverage)
        )
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "trading_account_id": trading_account_id,
            "risk_level": risk_level,
            "max_risk_per_trade": risk_pct,
            "max_daily_loss": daily_pct,
            "max_open_positions": max_open_positions,
            "max_leverage": lev,
            "is_active": True,
            "label": label.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def update_limits(
        self,
        *,
        max_risk_per_trade: Percentage | str | None = None,
        max_daily_loss: Percentage | str | None = None,
        max_open_positions: int | None = None,
        max_leverage: Leverage | int | None = None,
        risk_level: RiskLevel | None = None,
    ) -> None:
        """Update one or more risk limits atomically with re-validation."""
        require_state(self.is_active, "Cannot update an inactive risk profile")
        if max_risk_per_trade is not None:
            self.max_risk_per_trade = (
                max_risk_per_trade
                if isinstance(max_risk_per_trade, Percentage)
                else Percentage.of(max_risk_per_trade)
            )
        if max_daily_loss is not None:
            self.max_daily_loss = (
                max_daily_loss
                if isinstance(max_daily_loss, Percentage)
                else Percentage.of(max_daily_loss)
            )
        if max_open_positions is not None:
            self.max_open_positions = max_open_positions
        if max_leverage is not None:
            self.max_leverage = (
                max_leverage
                if isinstance(max_leverage, Leverage)
                else Leverage.of(max_leverage)
            )
        if risk_level is not None:
            self.risk_level = risk_level
        self.touch()
        self._validate_invariants()

    def deactivate(self) -> None:
        """Deactivate this risk profile."""
        require_state(self.is_active, "Risk profile is already inactive")
        self.is_active = False
        self.touch()

    def activate(self) -> None:
        """Re-activate a previously deactivated profile."""
        require_state(not self.is_active, "Risk profile is already active")
        self.is_active = True
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "trading_account_id": (
                    str(self.trading_account_id) if self.trading_account_id else None
                ),
                "risk_level": self.risk_level.value,
                "max_risk_per_trade": str(self.max_risk_per_trade),
                "max_daily_loss": str(self.max_daily_loss),
                "max_open_positions": self.max_open_positions,
                "max_leverage": self.max_leverage.value,
                "is_active": self.is_active,
                "label": self.label,
            }
        )
        return base
