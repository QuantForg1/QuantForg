"""Application DTOs for portfolio / position engine."""

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
)


@dataclass(frozen=True, slots=True)
class AccountSnapshotDTO:
    login: int
    balance: str
    equity: str
    margin: str
    free_margin: str
    margin_level: str
    profit: str
    leverage: int
    currency: str
    server: str

    @classmethod
    def from_entity(cls, snap: AccountSnapshot) -> AccountSnapshotDTO:
        return cls(
            login=snap.login,
            balance=str(snap.balance),
            equity=str(snap.equity),
            margin=str(snap.margin),
            free_margin=str(snap.free_margin),
            margin_level=str(snap.margin_level),
            profit=str(snap.profit),
            leverage=snap.leverage,
            currency=snap.currency,
            server=snap.server,
        )


@dataclass(frozen=True, slots=True)
class PositionDTO:
    ticket: int
    symbol: str
    side: str
    volume: str
    open_price: str
    current_price: str
    stop_loss: str
    take_profit: str
    profit: str
    swap: str
    magic: int
    comment: str
    opened_at: datetime

    @classmethod
    def from_entity(cls, pos: MT5Position) -> PositionDTO:
        return cls(
            ticket=pos.ticket,
            symbol=pos.symbol,
            side=pos.side,
            volume=str(pos.volume),
            open_price=str(pos.open_price),
            current_price=str(pos.current_price),
            stop_loss=str(pos.stop_loss),
            take_profit=str(pos.take_profit),
            profit=str(pos.profit),
            swap=str(pos.swap),
            magic=pos.magic,
            comment=pos.comment,
            opened_at=pos.opened_at,
        )


@dataclass(frozen=True, slots=True)
class PendingOrderDTO:
    ticket: int
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    stop_loss: str
    take_profit: str
    magic: int
    comment: str
    created_at: datetime

    @classmethod
    def from_entity(cls, order: MT5PendingOrder) -> PendingOrderDTO:
        return cls(
            ticket=order.ticket,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            volume=str(order.volume),
            price=str(order.price),
            stop_loss=str(order.stop_loss),
            take_profit=str(order.take_profit),
            magic=order.magic,
            comment=order.comment,
            created_at=order.created_at,
        )


@dataclass(frozen=True, slots=True)
class HistoryOrderDTO:
    ticket: int
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    state: str
    profit: str
    time_setup: datetime
    time_done: datetime | None

    @classmethod
    def from_entity(cls, order: MT5HistoryOrder) -> HistoryOrderDTO:
        return cls(
            ticket=order.ticket,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            volume=str(order.volume),
            price=str(order.price),
            state=order.state,
            profit=str(order.profit),
            time_setup=order.time_setup,
            time_done=order.time_done,
        )


@dataclass(frozen=True, slots=True)
class DealDTO:
    ticket: int
    order_ticket: int
    symbol: str
    side: str
    volume: str
    price: str
    profit: str
    commission: str
    swap: str
    deal_type: str
    time: datetime
    magic: int = 0
    comment: str = ""
    position_id: int = 0

    @classmethod
    def from_entity(cls, deal: MT5Deal) -> DealDTO:
        return cls(
            ticket=deal.ticket,
            order_ticket=deal.order_ticket,
            symbol=deal.symbol,
            side=deal.side,
            volume=str(deal.volume),
            price=str(deal.price),
            profit=str(deal.profit),
            commission=str(deal.commission),
            swap=str(deal.swap),
            deal_type=deal.deal_type,
            time=deal.time,
            magic=deal.magic,
            comment=deal.comment,
            position_id=deal.position_id,
        )


@dataclass(frozen=True, slots=True)
class PortfolioDTO:
    sync_id: UUID
    account: AccountSnapshotDTO
    positions: list[PositionDTO]
    pending_orders: list[PendingOrderDTO]
    history_orders: list[HistoryOrderDTO]
    history_deals: list[DealDTO]
    synced_at: datetime
    position_count: int
    pending_order_count: int


@dataclass(frozen=True, slots=True)
class HistoryDTO:
    orders: list[HistoryOrderDTO] = field(default_factory=list)
    deals: list[DealDTO] = field(default_factory=list)
