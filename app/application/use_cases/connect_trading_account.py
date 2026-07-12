"""ConnectTradingAccountUseCase — bind a user account to a broker.

Why this use case exists
------------------------
Orders, positions, and sessions hang off TradingAccount. Connecting an
account verifies the user and broker exist (and are usable), prevents
duplicate account numbers per broker, and creates the aggregate — without
opening a live broker connection or MetaTrader session.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.dto.trading_account import (
    ConnectTradingAccountCommand,
    TradingAccountDTO,
)
from app.domain.entities.trading_account import TradingAccount
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory
from app.domain.value_objects.identity import AccountNumber


@dataclass(frozen=True, slots=True)
class ConnectTradingAccountUseCase:
    """Connect a trading account for a user at a registered broker."""

    uow_factory: UnitOfWorkFactory

    async def execute(self, command: ConnectTradingAccountCommand) -> TradingAccountDTO:
        """Validate actors and persist a new trading account."""
        account_number = AccountNumber(value=command.account_number)

        async with self.uow_factory() as uow:
            user = await uow.users.get_by_id(command.user_id)
            if user is None:
                raise NotFoundError(
                    "User not found",
                    details={"user_id": str(command.user_id)},
                )
            if not user.is_active:
                raise ValidationError(
                    "User must be active to connect a trading account",
                    details={"user_id": str(user.id), "status": user.status.value},
                )

            broker = await uow.brokers.get_by_id(command.broker_id)
            if broker is None:
                raise NotFoundError(
                    "Broker not found",
                    details={"broker_id": str(command.broker_id)},
                )
            if not broker.is_usable:
                raise ValidationError(
                    "Broker is not usable",
                    details={
                        "broker_id": str(broker.id),
                        "status": broker.status.value,
                    },
                )

            duplicate = await uow.trading_accounts.get_by_broker_and_number(
                command.broker_id,
                account_number,
            )
            if duplicate is not None:
                raise ConflictError(
                    "Trading account already connected for this broker",
                    details={
                        "broker_id": str(command.broker_id),
                        "account_number": account_number.value,
                    },
                )

            account = TradingAccount.open(
                user_id=command.user_id,
                broker_id=command.broker_id,
                account_number=account_number,
                account_type=command.account_type,
                currency=command.currency,
                leverage=command.leverage,
                label=command.label,
            )
            if command.activate:
                account.activate()

            await uow.trading_accounts.add(account)
            await uow.commit()
            return TradingAccountDTO.from_entity(account)
