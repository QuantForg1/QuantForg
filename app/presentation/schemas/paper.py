"""HTTP schemas for the Paper Trading Engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PlacePaperOrderRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(description="buy | sell")
    order_type: str = Field(default="market", description="market | limit | stop")
    volume: str = Field(default="0.10")
    price: str | None = Field(
        default=None, description="Required for limit/stop orders"
    )
    stop_loss: str | None = None
    take_profit: str | None = None
    client_order_id: str = Field(default="", max_length=64)
    reduce_position_id: UUID | None = Field(
        default=None, description="Close/reduce an open paper position"
    )
    initial_balance: str = Field(
        default="10000", description="Used when creating a new paper portfolio"
    )


class PaperOrderResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    order_type: str
    volume: str
    status: str
    requested_price: str | None = None
    fill_price: str | None = None
    filled_volume: str
    stop_loss: str | None = None
    take_profit: str | None = None
    spread: str
    slippage: str
    commission: str
    rejection_reason: str = ""
    position_id: UUID | None = None
    client_order_id: str = ""
    submitted_at: datetime
    filled_at: datetime | None = None


class PaperPositionResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    status: str
    volume: str
    remaining_volume: str
    entry_price: str
    current_price: str
    stop_loss: str | None = None
    take_profit: str | None = None
    floating_pnl: str
    realized_pnl: str
    commission: str
    opened_at: datetime
    closed_at: datetime | None = None


class PaperTradeResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    volume: str
    entry_price: str
    exit_price: str
    pnl: str
    commission: str
    spread: str
    slippage: str
    opened_at: datetime
    closed_at: datetime


class PlacePaperOrderResponse(BaseModel):
    order: PaperOrderResponse
    position: PaperPositionResponse | None = None
    trade: PaperTradeResponse | None = None
    portfolio: dict[str, object] = Field(default_factory=dict)
    quote: dict[str, object] = Field(default_factory=dict)


class PaperPositionListResponse(BaseModel):
    items: list[PaperPositionResponse]
    count: int
    portfolio: dict[str, object] = Field(default_factory=dict)


class PaperHistoryResponse(BaseModel):
    orders: list[PaperOrderResponse]
    trades: list[PaperTradeResponse]
    positions: list[PaperPositionResponse]


class PaperPerformanceResponse(BaseModel):
    performance: dict[str, object]
    portfolio: dict[str, object]
