"""TradingAccount aggregate — a user's account at a broker.

Why this entity exists
----------------------
Orders, positions, and sessions hang off a TradingAccount. This aggregate
binds a User to a Broker with account number, type, currency, leverage, and
lifecycle status. Balance is stored as a Money snapshot attribute — the
entity does **not** implement deposit/withdrawal workflows or margin math.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.trading_account import AccountStatus, AccountType
from app.domain.value_objects.identity import AccountNumber, Leverage
from app.domain.value_objects.money import CurrencyCode, Money


@dataclass(eq=False, kw_only=True)
class TradingAccount(Entity):
    """Rich domain model for a trading account."""

    user_id: UUID
    broker_id: UUID
    account_number: AccountNumber
    account_type: AccountType = AccountType.DEMO
    status: AccountStatus = AccountStatus.PENDING
    currency: CurrencyCode = None  # type: ignore[assignment]
    leverage: Leverage = None  # type: ignore[assignment]
    balance: Money = None  # type: ignore[assignment]
    label: str = ""
    closed_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.currency is None:
            self.currency = CurrencyCode(value="USD")
        if self.leverage is None:
            self.leverage = Leverage(value=100)
        if self.balance is None:
            self.balance = Money.zero(self.currency.value)
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(
            self.balance.currency == self.currency,
            "Balance currency must match account currency",
            balance_currency=self.balance.currency.value,
            account_currency=self.currency.value,
        )
        if self.status == AccountStatus.CLOSED:
            require(
                self.closed_at is not None,
                "Closed accounts must record closed_at",
            )

    @classmethod
    def open(
        cls,
        *,
        user_id: UUID,
        broker_id: UUID,
        account_number: str | AccountNumber,
        account_type: AccountType = AccountType.DEMO,
        currency: str = "USD",
        leverage: int = 100,
        label: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: open a new trading account in PENDING status."""
        number_vo = (
            account_number
            if isinstance(account_number, AccountNumber)
            else AccountNumber(value=account_number)
        )
        currency_vo = CurrencyCode(value=currency)
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "broker_id": broker_id,
            "account_number": number_vo,
            "account_type": account_type,
            "status": AccountStatus.PENDING,
            "currency": currency_vo,
            "leverage": Leverage(value=leverage),
            "balance": Money.zero(currency_vo.value),
            "label": label.strip(),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def activate(self) -> None:
        """Activate a pending or suspended account."""
        require_state(
            self.status in {AccountStatus.PENDING, AccountStatus.SUSPENDED},
            "Only pending or suspended accounts can be activated",
            status=self.status.value,
        )
        self.status = AccountStatus.ACTIVE
        self.closed_at = None
        self.touch()

    def suspend(self) -> None:
        """Suspend an active account."""
        require_state(
            self.status == AccountStatus.ACTIVE,
            "Only active accounts can be suspended",
            status=self.status.value,
        )
        self.status = AccountStatus.SUSPENDED
        self.touch()

    def close(self) -> None:
        """Permanently close the account."""
        require_state(
            self.status != AccountStatus.CLOSED,
            "Account is already closed",
            status=self.status.value,
        )
        self.status = AccountStatus.CLOSED
        self.closed_at = datetime.now(UTC)
        self.touch()

    def change_leverage(self, leverage: int | Leverage) -> None:
        """Update account leverage. Closed accounts cannot change leverage."""
        require_state(
            self.status != AccountStatus.CLOSED,
            "Cannot change leverage on a closed account",
            status=self.status.value,
        )
        self.leverage = (
            leverage if isinstance(leverage, Leverage) else Leverage(value=leverage)
        )
        self.touch()

    def record_balance(self, balance: Money) -> None:
        """Replace the balance snapshot. Currency must match the account."""
        require_state(
            self.status != AccountStatus.CLOSED,
            "Cannot update balance on a closed account",
            status=self.status.value,
        )
        require(
            balance.currency == self.currency,
            "Balance currency must match account currency",
            balance_currency=balance.currency.value,
            account_currency=self.currency.value,
        )
        self.balance = balance
        self.touch()

    @property
    def is_tradable(self) -> bool:
        return self.status == AccountStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "broker_id": str(self.broker_id),
                "account_number": str(self.account_number),
                "account_type": self.account_type.value,
                "status": self.status.value,
                "currency": self.currency.value,
                "leverage": self.leverage.value,
                "balance": self.balance.to_dict(),
                "label": self.label,
                "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            }
        )
        return base
