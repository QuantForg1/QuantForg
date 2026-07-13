"""HTTP schemas for Execution Intelligence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ObserveLifecycleRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    symbol: str = Field(min_length=1, max_length=32)
    side: str = Field(default="buy", max_length=16)
    order_type: str = Field(default="market", max_length=32)
    volume: str = Field(default="0.01", max_length=32)
    state: str = Field(min_length=1, max_length=64)
    reason: str = Field(default="observed", max_length=500)
    source: str = Field(default="client", max_length=64)
    meta: dict[str, Any] = Field(default_factory=dict)
    force: bool = False


class ChecklistRequest(BaseModel):
    broker_connected: bool | None = None
    market_open: bool | None = None
    risk_passed: bool | None = None
    margin_sufficient: bool | None = None
    strategy_signal_valid: bool | None = None
    # execution_enabled is always read from settings — not accepted from client


class PostTradeRequest(BaseModel):
    trades: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
