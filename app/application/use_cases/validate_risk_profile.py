"""ValidateRiskProfileUseCase — check a proposal against risk limits.

Why this use case exists
------------------------
Before any future order workflow, the platform must know whether a
*proposed* risk, leverage, and open-position count fit the user's
RiskProfile. This use case only validates — it never places orders or
computes trading signals.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.risk import RiskValidationDTO, ValidateRiskProfileCommand
from app.domain.entities.risk_profile import RiskProfile
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory, UnitOfWorkPort
from app.domain.value_objects.market import Percentage


@dataclass(frozen=True, slots=True)
class ValidateRiskProfileUseCase:
    """Validate a proposed exposure against an active risk profile."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: ValidateRiskProfileCommand) -> RiskValidationDTO:
        """Load the profile and return a structured validation result."""
        async with self.uow_factory() as uow:
            profile = await self._resolve_profile(uow, command)

            if not profile.is_active:
                raise ValidationError(
                    "Risk profile is inactive",
                    details={"risk_profile_id": str(profile.id)},
                )

            proposed_risk = Percentage.of(command.proposed_risk_percent)
            violations: list[str] = []

            if proposed_risk.value > profile.max_risk_per_trade.value:
                violations.append(
                    "proposed_risk_percent exceeds max_risk_per_trade "
                    f"({proposed_risk} > {profile.max_risk_per_trade})"
                )

            if command.proposed_leverage > profile.max_leverage.value:
                violations.append(
                    "proposed_leverage exceeds max_leverage "
                    f"({command.proposed_leverage} > {profile.max_leverage.value})"
                )

            if command.current_open_positions < 0:
                raise ValidationError(
                    "current_open_positions cannot be negative",
                    details={"current_open_positions": command.current_open_positions},
                )

            if command.current_open_positions >= profile.max_open_positions:
                violations.append(
                    "current_open_positions at or above max_open_positions "
                    f"({command.current_open_positions} >= "
                    f"{profile.max_open_positions})"
                )

            # Soft check: proposed risk should not exceed daily loss cap either.
            if proposed_risk.value > profile.max_daily_loss.value:
                violations.append(
                    "proposed_risk_percent exceeds max_daily_loss "
                    f"({proposed_risk} > {profile.max_daily_loss})"
                )

            return RiskValidationDTO(
                is_valid=len(violations) == 0,
                risk_profile_id=profile.id,
                risk_level=profile.risk_level.value,
                violations=tuple(violations),
                max_risk_per_trade=str(profile.max_risk_per_trade),
                max_daily_loss=str(profile.max_daily_loss),
                max_open_positions=profile.max_open_positions,
                max_leverage=profile.max_leverage.value,
            )

    @staticmethod
    async def _resolve_profile(
        uow: UnitOfWorkPort,
        command: ValidateRiskProfileCommand,
    ) -> RiskProfile:
        if command.risk_profile_id is not None:
            profile = await uow.risk_profiles.get_by_id(command.risk_profile_id)
            if profile is None:
                raise NotFoundError(
                    "Risk profile not found",
                    details={"risk_profile_id": str(command.risk_profile_id)},
                )
            return profile

        if command.trading_account_id is not None:
            profile = await uow.risk_profiles.get_active_for_account(
                command.trading_account_id
            )
            if profile is not None:
                return profile

        if command.user_id is not None:
            profile = await uow.risk_profiles.get_active_for_user(command.user_id)
            if profile is not None:
                return profile

        raise NotFoundError(
            "No active risk profile found for the given identifiers",
            details={
                "risk_profile_id": (
                    str(command.risk_profile_id) if command.risk_profile_id else None
                ),
                "user_id": str(command.user_id) if command.user_id else None,
                "trading_account_id": (
                    str(command.trading_account_id)
                    if command.trading_account_id
                    else None
                ),
            },
        )
