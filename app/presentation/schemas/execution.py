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
    position: int = Field(default=0, ge=0)
    order_ticket: int = Field(default=0, ge=0)
    oms_kind: str = Field(default="", max_length=32)


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
    stages: list[dict[str, object]] = Field(default_factory=list)
    latency_ms: float | None = None
    journal_entry: dict[str, object] | None = None


class ExecutionCancelRequest(BaseModel):
    request_id: str = Field(default="", max_length=128)
    ticket: int = Field(ge=1)
    symbol: str = Field(default="", max_length=32)


class ExecutionCancelResponse(BaseModel):
    request_id: str
    outcome: str
    message: str
    ticket: int
    stages: list[dict[str, object]] = Field(default_factory=list)
    latency_ms: float = 0
    journal_entry: dict[str, object] | None = None
    rejection_reasons: list[str] = Field(default_factory=list)


class ExecutionManageRequest(BaseModel):
    request_id: str = Field(default="", max_length=128)
    action: str = Field(
        description=(
            "close | partial_close | close_all | reverse | modify | modify_sltp | "
            "move_sl | move_tp | trailing_stop | break_even | cancel_pending"
        )
    )
    symbol: str = Field(min_length=1, max_length=32)
    ticket: int | None = None
    side: str | None = None
    order_type: str | None = None
    volume: str | None = None
    price: str | None = None
    stop_loss: str | None = None
    take_profit: str | None = None
    slippage: int = Field(default=10, ge=0)
    magic: int = Field(default=0, ge=0)
    comment: str = Field(default="", max_length=64)
    trailing_points: str | None = None


class ExecutionManageResponse(BaseModel):
    request_id: str
    action: str
    outcome: str
    message: str
    stages: list[dict[str, object]] = Field(default_factory=list)
    latency_ms: float = 0
    rejection_reasons: list[str] = Field(default_factory=list)
    journal_entry: dict[str, object] | None = None
    order_ticket: int | None = None
    deal_ticket: int | None = None
    price: str | None = None


class ExecutionJournalResponse(BaseModel):
    items: list[dict[str, object]] = Field(default_factory=list)
    count: int = 0


class ExecutionAnalyticsResponse(BaseModel):
    status: str
    metrics: dict[str, object] = Field(default_factory=dict)
    sample_sizes: dict[str, object] = Field(default_factory=dict)
    data_source: str = ""
    journal_count: int = 0


class ExecutionAuditItem(BaseModel):
    id: UUID
    user_id: UUID
    request_id: str
    stage: str
    symbol: str = ""
    side: str = ""
    volume: str = ""
    outcome: str = ""
    retcode: int = 0
    order_ticket: int | None = None
    deal_ticket: int | None = None
    latency_ms: float | None = None
    gateway_latency_ms: float | None = None
    railway_processing_ms: float | None = None
    cloudflare_latency_ms: float | None = None
    spread: str | None = None
    slippage: str | None = None
    commission: str | None = None
    swap: str | None = None
    margin_used: str | None = None
    free_margin: str | None = None
    balance: str | None = None
    equity: str | None = None
    leverage: str | None = None
    broker_server_time: str | None = None
    market_session: str | None = None
    execution_route: str = "mt5_gateway"
    payload_in: dict[str, object] = Field(default_factory=dict)
    payload_out: dict[str, object] = Field(default_factory=dict)
    related_ids: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class ExecutionAuditListResponse(BaseModel):
    items: list[ExecutionAuditItem] = Field(default_factory=list)
    count: int = 0


class ExecutionAuditTimelineResponse(BaseModel):
    request_id: str
    items: list[ExecutionAuditItem] = Field(default_factory=list)
    count: int = 0
