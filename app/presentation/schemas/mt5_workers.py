"""Request schemas for MT5 worker control-plane APIs. No password fields."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class WorkerHostRegisterRequest(BaseModel):
    host_code: str = Field(min_length=1, max_length=128)
    max_terminals: int = Field(default=4, ge=1, le=64)
    region: str = Field(default="", max_length=64)


class WorkerRegisterRequest(BaseModel):
    host_code: str = Field(min_length=1, max_length=128)
    slot_id: str = Field(min_length=1, max_length=64)
    platform: str = Field(default="windows-local", max_length=64)
    max_terminals: int = Field(default=4, ge=1, le=64)
    user_id: UUID | None = None
    broker_account_id: UUID | None = None


class WorkerHeartbeatRequest(BaseModel):
    worker_id: UUID
    slot_id: str | None = Field(default=None, max_length=64)
    lifecycle: str | None = Field(default=None, max_length=32)
    ready: bool | None = None


class WorkerHealthRequest(BaseModel):
    worker_id: UUID
    cpu_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    ram_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    disk_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    healthy: bool = True
    details: dict[str, object] | None = None


class WorkerIdRequest(BaseModel):
    worker_id: UUID


class WorkerVerificationReport(BaseModel):
    """Redacted Windows MT5 verification evidence. No password fields."""

    ok: bool
    broker_slug: str = Field(min_length=1, max_length=64)
    environment: str = Field(default="demo", max_length=16)
    server: str = Field(default="", max_length=128)
    login: str | int | None = None
    trade_allowed: bool = False
    market_data_ok: bool = False
    balance: float | None = None
    equity: float | None = None
    currency: str = Field(default="", max_length=16)
    symbols_total: int | None = None
    quote_symbol: str = Field(default="", max_length=64)
    host_code: str = Field(default="", max_length=128)
    slot_id: str = Field(default="", max_length=64)
    worker_id: str = Field(default="", max_length=64)
    source: str = Field(default="windows_mt5_demo_verify", max_length=64)
    error: str = Field(default="", max_length=200)


class DispatchClaimRequest(BaseModel):
    """Worker claim for next durable dispatch job (delivery only, no LIVE submit)."""

    worker_id: UUID
    user_id: UUID
    broker_account_id: UUID


class DispatchAckRequest(BaseModel):
    worker_id: UUID
    intent_id: UUID
    detail: str = Field(default="", max_length=500)


class DispatchFailRequest(BaseModel):
    worker_id: UUID
    intent_id: UUID
    reason: str = Field(default="failed", max_length=500)


class DispatchExecuteAuthorizeRequest(BaseModel):
    """Worker requests OMS execution authorization for a claimed intent."""

    worker_id: UUID
    intent_id: UUID
    account_environment: str = Field(default="demo", max_length=16)


class DispatchExecutionResultRequest(BaseModel):
    """Worker reports actual broker response (not delivery ACK)."""

    worker_id: UUID
    intent_id: UUID
    ok: bool = False
    retcode: int | None = None
    order_ticket: int | None = None
    deal_ticket: int | None = None
    symbol: str = Field(default="", max_length=32)
    side: str = Field(default="", max_length=8)
    volume: str = Field(default="", max_length=32)
    price: str | None = Field(default=None, max_length=32)
    environment: str = Field(default="demo", max_length=16)
    idempotency_key: str = Field(default="", max_length=256)
    comment: str = Field(default="", max_length=200)
    detail: str = Field(default="", max_length=500)
    uncertain: bool = False
    order_send: bool | None = None


class DispatchLabEnqueueRequest(BaseModel):
    """Staging lab enqueue for assigned worker only. Never LIVE submit."""

    worker_id: UUID
    symbol: str = Field(default="XAUUSD", min_length=3, max_length=32)
    side: str = Field(default="BUY", max_length=8)
    quality: int = Field(default=80, ge=1, le=100)
    idempotency_key: str = Field(default="", max_length=128)


class DispatchDemoEnqueueRequest(BaseModel):
    """Production/Staging DEMO enqueue for a dispatch_ready worker only."""

    worker_id: UUID
    symbol: str = Field(default="XAUUSD", min_length=3, max_length=32)
    side: str = Field(default="BUY", max_length=8)
    quality: int = Field(default=80, ge=1, le=100)
    volume: str = Field(default="0.01", max_length=16)
    entry: str = Field(default="4000", max_length=32)
    stop_loss: str = Field(default="3990", max_length=32)
    take_profit: str = Field(default="4010", max_length=32)
    idempotency_key: str = Field(default="", max_length=128)


class LabAttestAssignmentRequest(BaseModel):
    """Staging-only attestation that a lab worker assignment is verified.

    Registration alone is insufficient. Requires a prior authenticated heartbeat.
    Forbidden in production.
    """

    worker_id: UUID
