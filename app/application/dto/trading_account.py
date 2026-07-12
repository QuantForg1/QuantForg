"""Trading account application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.trading_account import TradingAccount
from app.domain.enums.trading_account import AccountType


@dataclass(frozen=True, slots=True)
class ConnectTradingAccountCommand:
    """Input for ConnectTradingAccountUseCase."""

    user_id: UUID
    broker_id: UUID
    account_number: str
    account_type: AccountType = AccountType.DEMO
    currency: str = "USD"
    leverage: int = 100
    label: str = ""
    activate: bool = True


@dataclass(frozen=True, slots=True)
class TradingAccountDTO:
    """Trading account representation for the presentation layer."""

    id: UUID
    user_id: UUID
    broker_id: UUID
    account_number: str
    account_type: str
    status: str
    currency: str
    leverage: int
    label: str

    @classmethod
    def from_entity(cls, account: TradingAccount) -> TradingAccountDTO:
        return cls(
            id=account.id,
            user_id=account.user_id,
            broker_id=account.broker_id,
            account_number=str(account.account_number),
            account_type=account.account_type.value,
            status=account.status.value,
            currency=account.currency.value,
            leverage=account.leverage.value,
            label=account.label,
        )
