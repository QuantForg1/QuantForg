"""HTTP schemas for the Backtesting Engine."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BacktestBarRequest(BaseModel):
    open_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str = "0"
    close_time: str | None = None


class BacktestRunRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(default="m15", max_length=16)
    initial_balance: str = Field(default="10000")
    bars: list[BacktestBarRequest] = Field(default_factory=list)
    ticks: list[dict[str, object]] = Field(default_factory=list)
    replay_mode: str = Field(default="candle", description="candle | tick")
    spread: str = "0.00010"
    slippage: str = "0.00005"
    fee_per_lot: str = "7"
    lot_size: str = "0.10"
    stop_loss_distance: str = "0.0020"
    take_profit_distance: str = "0.0040"
    auto_analysis: bool = True
    max_open_trades: int = Field(default=1, ge=1, le=20)
    consult_execution_safety: bool = True


class SimulatedTradeResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    status: str
    volume: str
    entry_price: str
    exit_price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    spread: str
    slippage: str
    fees: str
    pnl: str
    exit_reason: str | None = None
    opened_at: datetime
    closed_at: datetime | None = None


class BacktestRunResponse(BaseModel):
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: str
    replay_mode: str
    initial_balance: str
    metrics: dict[str, object] = Field(default_factory=dict)
    equity_curve: list[dict[str, object]] = Field(default_factory=list)
    portfolio_snapshot: dict[str, object] = Field(default_factory=dict)
    trades: list[SimulatedTradeResponse] = Field(default_factory=list)
    trade_count: int = 0
    bar_count: int = 0
    replay_state: dict[str, object] = Field(default_factory=dict)
    assumptions: dict[str, object] = Field(default_factory=dict)
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None


class BacktestListResponse(BaseModel):
    items: list[BacktestRunResponse]
    count: int
