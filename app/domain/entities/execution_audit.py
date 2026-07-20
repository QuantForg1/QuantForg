"""Execution Audit Engine domain model — immutable stage history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.execution import ExecutionAuditStage


@dataclass(eq=False, kw_only=True)
class ExecutionAudit(Entity):
    """One persisted execution-pipeline stage (never mutates a live order)."""

    user_id: UUID
    request_id: str
    stage: ExecutionAuditStage
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
    payload_in: dict[str, object] = field(default_factory=dict)
    payload_out: dict[str, object] = field(default_factory=dict)
    related_ids: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        self.symbol = self.symbol.strip().upper()
        self.side = self.side.strip().lower()
        self.volume = str(self.volume or "")
        self.outcome = str(self.outcome or "")
        self.execution_route = (self.execution_route or "mt5_gateway").strip() or (
            "mt5_gateway"
        )
        self.payload_in = dict(self.payload_in or {})
        self.payload_out = dict(self.payload_out or {})
        self.related_ids = dict(self.related_ids or {})

    @classmethod
    def record(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        stage: ExecutionAuditStage | str,
        symbol: str = "",
        side: str = "",
        volume: str = "",
        outcome: str = "",
        retcode: int = 0,
        order_ticket: int | None = None,
        deal_ticket: int | None = None,
        latency_ms: float | None = None,
        gateway_latency_ms: float | None = None,
        railway_processing_ms: float | None = None,
        cloudflare_latency_ms: float | None = None,
        spread: str | None = None,
        slippage: str | None = None,
        commission: str | None = None,
        swap: str | None = None,
        margin_used: str | None = None,
        free_margin: str | None = None,
        balance: str | None = None,
        equity: str | None = None,
        leverage: str | None = None,
        broker_server_time: str | None = None,
        market_session: str | None = None,
        execution_route: str = "mt5_gateway",
        payload_in: dict[str, object] | None = None,
        payload_out: dict[str, object] | None = None,
        related_ids: dict[str, object] | None = None,
        entity_id: UUID | None = None,
    ) -> Self:
        stage_val = (
            stage
            if isinstance(stage, ExecutionAuditStage)
            else ExecutionAuditStage(str(stage).strip().lower())
        )
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "stage": stage_val,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "outcome": outcome,
            "retcode": int(retcode),
            "order_ticket": order_ticket,
            "deal_ticket": deal_ticket,
            "latency_ms": latency_ms,
            "gateway_latency_ms": gateway_latency_ms,
            "railway_processing_ms": railway_processing_ms,
            "cloudflare_latency_ms": cloudflare_latency_ms,
            "spread": spread,
            "slippage": slippage,
            "commission": commission,
            "swap": swap,
            "margin_used": margin_used,
            "free_margin": free_margin,
            "balance": balance,
            "equity": equity,
            "leverage": leverage,
            "broker_server_time": broker_server_time,
            "market_session": market_session,
            "execution_route": execution_route,
            "payload_in": dict(payload_in or {}),
            "payload_out": dict(payload_out or {}),
            "related_ids": dict(related_ids or {}),
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "stage": self.stage.value,
                "symbol": self.symbol,
                "side": self.side,
                "volume": self.volume,
                "outcome": self.outcome,
                "retcode": self.retcode,
                "order_ticket": self.order_ticket,
                "deal_ticket": self.deal_ticket,
                "latency_ms": self.latency_ms,
                "gateway_latency_ms": self.gateway_latency_ms,
                "railway_processing_ms": self.railway_processing_ms,
                "cloudflare_latency_ms": self.cloudflare_latency_ms,
                "spread": self.spread,
                "slippage": self.slippage,
                "commission": self.commission,
                "swap": self.swap,
                "margin_used": self.margin_used,
                "free_margin": self.free_margin,
                "balance": self.balance,
                "equity": self.equity,
                "leverage": self.leverage,
                "broker_server_time": self.broker_server_time,
                "market_session": self.market_session,
                "execution_route": self.execution_route,
                "payload_in": dict(self.payload_in),
                "payload_out": dict(self.payload_out),
                "related_ids": dict(self.related_ids),
            }
        )
        return base
