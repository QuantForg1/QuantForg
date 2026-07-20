"""HTTP schemas for portfolio / position engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AccountSnapshotResponse(BaseModel):
    login: int
    balance: str
    equity: str
    margin: str
    free_margin: str
    margin_level: str
    profit: str
    leverage: int
    currency: str
    server: str = ""


class PositionResponse(BaseModel):
    ticket: int
    symbol: str
    side: str
    volume: str
    open_price: str
    current_price: str
    stop_loss: str
    take_profit: str
    profit: str
    swap: str = "0"
    magic: int = 0
    comment: str = ""
    opened_at: datetime


class PendingOrderResponse(BaseModel):
    ticket: int
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    stop_loss: str = "0"
    take_profit: str = "0"
    magic: int = 0
    comment: str = ""
    created_at: datetime


class HistoryOrderResponse(BaseModel):
    ticket: int
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    state: str
    profit: str
    time_setup: datetime
    time_done: datetime | None = None


class DealResponse(BaseModel):
    ticket: int
    order_ticket: int
    symbol: str
    side: str
    volume: str
    price: str
    profit: str
    commission: str = "0"
    swap: str = "0"
    deal_type: str = ""
    time: datetime
    magic: int = 0
    comment: str = ""
    position_id: int = 0


class PortfolioResponse(BaseModel):
    sync_id: UUID
    account: AccountSnapshotResponse
    positions: list[PositionResponse] = Field(default_factory=list)
    pending_orders: list[PendingOrderResponse] = Field(default_factory=list)
    history_orders: list[HistoryOrderResponse] = Field(default_factory=list)
    history_deals: list[DealResponse] = Field(default_factory=list)
    synced_at: datetime
    position_count: int
    pending_order_count: int


class HistoryResponse(BaseModel):
    orders: list[HistoryOrderResponse] = Field(default_factory=list)
    deals: list[DealResponse] = Field(default_factory=list)
