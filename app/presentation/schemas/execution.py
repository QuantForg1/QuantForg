"""HTTP schemas for execution safety checks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionCheckRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
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


class ExecutionCheckResponse(BaseModel):
    id: UUID
    request_id: str
    decision: str = Field(description="allow | reject | retry")
    symbol: str
    side: str
    order_type: str
    volume: str
    rejection_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    calculated_risk: dict[str, object] = Field(default_factory=dict)
    checks: dict[str, bool] = Field(default_factory=dict)
    idempotent_replay: bool = False
    decided_at: datetime


class ExecutionSubmitRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
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


class ExecutionSubmitResponse(BaseModel):
    id: UUID
    request_id: str
    outcome: str = Field(
        description="success | failed | disabled | retry | cancelled | prepared"
    )
    retcode: int
    message: str
    symbol: str
    side: str
    order_type: str
    volume: str
    order_ticket: int | None = None
    deal_ticket: int | None = None
    price: str = "0"
    retryable: bool = False
    idempotent_replay: bool = False
    submitted_at: datetime
