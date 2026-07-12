"""Portfolio synchronization service — read-only MT5 state sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.mt5_portfolio import (
    AccountSnapshot,
    MT5Deal,
    MT5HistoryOrder,
    MT5PendingOrder,
    MT5Position,
    PortfolioState,
    PortfolioSyncRecord,
)
from app.domain.events.base import DomainEvent
from app.domain.events.portfolio import (
    AccountUpdated,
    PendingOrderDetected,
    PortfolioSynchronized,
    PositionClosedDetected,
    PositionOpenedDetected,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class PortfolioSyncService:
    """Synchronize portfolio state from MT5. Never executes orders."""

    adapter: MT5Adapter
    _events: list[DomainEvent] = field(default_factory=list, init=False)
    _last_position_tickets: dict[UUID, set[int]] = field(
        default_factory=dict, init=False
    )
    _last_pending_tickets: dict[UUID, set[int]] = field(
        default_factory=dict, init=False
    )
    _last_account: dict[UUID, AccountSnapshot] = field(default_factory=dict, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def list_positions(self) -> list[MT5Position]:
        return self.adapter.list_positions()

    def position_by_ticket(self, ticket: int) -> MT5Position | None:
        return self.adapter.position_by_ticket(ticket)

    def position_by_symbol(self, symbol: str) -> list[MT5Position]:
        return self.adapter.position_by_symbol(symbol)

    def list_orders(self) -> list[MT5PendingOrder]:
        return self.adapter.list_orders()

    def order_by_ticket(self, ticket: int) -> MT5PendingOrder | None:
        return self.adapter.order_by_ticket(ticket)

    def history_orders(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5HistoryOrder]:
        return self.adapter.history_orders(date_from=date_from, date_to=date_to)

    def history_deals(
        self,
        *,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[MT5Deal]:
        return self.adapter.history_deals(date_from=date_from, date_to=date_to)

    def account_snapshot(self) -> AccountSnapshot:
        return self.adapter.account_snapshot()

    def synchronize(
        self,
        *,
        user_id: UUID,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PortfolioSyncRecord:
        """Pull positions, pending orders, account, and history (read-only)."""
        positions = self.list_positions()
        pending = self.list_orders()
        account = self.account_snapshot()
        hist_orders = self.history_orders(date_from=date_from, date_to=date_to)
        hist_deals = self.history_deals(date_from=date_from, date_to=date_to)

        state = PortfolioState(
            account=account,
            positions=tuple(positions),
            pending_orders=tuple(pending),
            history_orders=tuple(hist_orders),
            history_deals=tuple(hist_deals),
        )
        record = PortfolioSyncRecord.from_state(user_id=user_id, state=state)

        prev_pos = self._last_position_tickets.get(user_id, set())
        curr_pos = {p.ticket for p in positions}
        for ticket in curr_pos - prev_pos:
            pos = next(p for p in positions if p.ticket == ticket)
            self._events.append(
                PositionOpenedDetected(
                    user_id=user_id, ticket=ticket, symbol=pos.symbol
                )
            )
        for ticket in prev_pos - curr_pos:
            self._events.append(
                PositionClosedDetected(user_id=user_id, ticket=ticket, symbol="")
            )
        self._last_position_tickets[user_id] = curr_pos

        prev_ord = self._last_pending_tickets.get(user_id, set())
        curr_ord = {o.ticket for o in pending}
        for ticket in curr_ord - prev_ord:
            order = next(o for o in pending if o.ticket == ticket)
            self._events.append(
                PendingOrderDetected(
                    user_id=user_id, ticket=ticket, symbol=order.symbol
                )
            )
        self._last_pending_tickets[user_id] = curr_ord

        prev_acct = self._last_account.get(user_id)
        if (
            prev_acct is None
            or prev_acct.equity != account.equity
            or prev_acct.balance != account.balance
        ):
            self._events.append(
                AccountUpdated(
                    user_id=user_id,
                    login=account.login,
                    equity=str(account.equity),
                    balance=str(account.balance),
                )
            )
        self._last_account[user_id] = account

        self._events.append(
            PortfolioSynchronized(
                user_id=user_id,
                sync_id=record.id,
                login=account.login,
                position_count=len(positions),
                pending_order_count=len(pending),
            )
        )
        return record
