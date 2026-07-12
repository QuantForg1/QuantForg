"""Pydantic schemas for MT5 connection-layer REST API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MT5ConnectRequest(BaseModel):
    login: int = Field(gt=0)
    password: str = Field(min_length=1, max_length=512)
    server: str = Field(min_length=1, max_length=200)
    path: str = Field(default="", max_length=512)


class MT5StatusResponse(BaseModel):
    connected: bool
    status: str
    latency_ms: float | None = None
    terminal_build: int | None = None
    terminal_version: str = ""
    server: str = ""
    login: int | None = None
    login_status: str = "logged_out"
    last_heartbeat_at: datetime | None = None
    last_error: str = ""
    session_ref: str = ""


class MT5ConnectionResponse(BaseModel):
    id: UUID
    user_id: UUID
    login: int
    server: str
    status: str
    connected: bool
    terminal_build: int | None = None
    terminal_version: str = ""
    latency_ms: float | None = None
    last_heartbeat_at: datetime | None = None
    login_status: str
    session_ref: str = ""
    history: list[dict[str, object]] = Field(default_factory=list)


class MT5AccountResponse(BaseModel):
    login: int
    name: str
    server: str
    currency: str
    leverage: int
    balance: str
    equity: str
    company: str = ""
    trade_mode: str = ""


class MT5SymbolResponse(BaseModel):
    code: str
    description: str = ""
    digits: int = 5
    contract_size: str = "1"
    point: str = "0.00001"
    selected: bool = False
    trade_mode: str = ""
    currency_base: str = ""
    currency_profit: str = ""
    bid: str | None = None
    ask: str | None = None


class MT5TickResponse(BaseModel):
    symbol: str
    bid: str
    ask: str
    spread: str
    timestamp: datetime
    volume: str = "0"


class MT5CandleResponse(BaseModel):
    symbol: str
    timeframe: str
    open_time: datetime
    open: str
    high: str
    low: str
    close: str
    tick_volume: int = 0
    spread_points: int = 0


class MT5OrderValidateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(description="buy | sell")
    order_type: str = Field(default="market")
    volume: str = Field(default="0.01", min_length=1, max_length=32)
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = Field(default=10, ge=0)
    magic: int = Field(default=0, ge=0)
    comment: str = Field(default="", max_length=64)


class MT5OrderValidationResponse(BaseModel):
    id: UUID
    symbol: str
    side: str
    order_type: str
    volume: str
    valid: bool
    retcode: int
    expected_margin: str
    estimated_profit: str
    messages: list[str] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    request_snapshot: dict[str, object] = Field(default_factory=dict)
    validated_at: datetime


class MT5OrderCalculateResponse(BaseModel):
    symbol: str
    side: str
    order_type: str
    volume: str
    price: str
    expected_margin: str
    estimated_profit: str
    retcode: int
    messages: list[str] = Field(default_factory=list)
    request_snapshot: dict[str, object] = Field(default_factory=dict)
