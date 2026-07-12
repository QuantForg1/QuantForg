"""OpenTradingSessionUseCase — start a session on a trading account.

Why this use case exists
------------------------
A TradingSession models a connected window for a user on an account.
Opening a session verifies the user is active and the account is tradable,
then creates the session aggregate. It does not open market connectivity
or broker sockets.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.trading_session import (
    OpenTradingSessionCommand,
    TradingSessionDTO,
)
from app.domain.entities.trading_session import TradingSession
from app.domain.exceptions.base import NotFoundError, ValidationError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory


@dataclass(frozen=True, slots=True)
class OpenTradingSessionUseCase:
    """Open a new trading session."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: OpenTradingSessionCommand) -> TradingSessionDTO:
        """Validate account ownership context and open a session."""
        async with self.uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise NotFoundError(
                    "User not found",
                    details={"user_id": str(command.user_id)},
                )
            if not user.is_active:
                raise ValidationError(
                    "User must be active to open a trading session",
                    details={"user_id": str(user.id), "status": user.status.value},
                )

            account = await uow.trading_accounts.get_by_id(command.trading_account_id)
            if account is None:
                raise NotFoundError(
                    "Trading account not found",
                    details={"trading_account_id": str(command.trading_account_id)},
                )
            if account.user_id != command.user_id:
                raise ValidationError(
                    "Trading account does not belong to the user",
                    details={
                        "trading_account_id": str(account.id),
                        "user_id": str(command.user_id),
                    },
                )
            if not account.is_tradable:
                raise ValidationError(
                    "Trading account is not tradable",
                    details={
                        "trading_account_id": str(account.id),
                        "status": account.status.value,
                    },
                )

            session = TradingSession.open(
                trading_account_id=command.trading_account_id,
                user_id=command.user_id,
                client_label=command.client_label,
            )
            await uow.trading_sessions.add(session)
            await uow.commit()
            return TradingSessionDTO.from_entity(session)
