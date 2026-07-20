"""Execution Audit Engine service — record stages forever; never fail a trade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from app.domain.entities.execution_audit import ExecutionAudit
from app.domain.enums.execution import ExecutionAuditStage
from core.logging import get_logger

logger = get_logger(__name__)

_SECRET_KEY_MARKERS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "token",
        "secret",
        "api_key",
        "apikey",
        "access_key",
        "private_key",
        "authorization",
        "credential",
        "credentials",
        "bearer",
    }
)


def _is_secret_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _SECRET_KEY_MARKERS:
        return True
    return any(marker in normalized for marker in _SECRET_KEY_MARKERS)


def sanitize_payload(value: object) -> object:
    """Strip password/token/secret keys from nested dicts before persist."""
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for raw_key, raw_val in value.items():
            key = str(raw_key)
            if _is_secret_key(key):
                cleaned[key] = "[redacted]"
            else:
                cleaned[key] = sanitize_payload(raw_val)
        return cleaned
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_payload(item) for item in value]
    return value


def sanitize_payload_dict(payload: dict[str, object] | None) -> dict[str, object]:
    cleaned = sanitize_payload(dict(payload or {}))
    return cleaned if isinstance(cleaned, dict) else {}


@dataclass(frozen=True, slots=True)
class ExecutionAuditService:
    """Persist and query execution-stage audits via UoW factory."""

    uow_factory: Any

    async def record(
        self,
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
    ) -> ExecutionAudit:
        audit = ExecutionAudit.record(
            user_id=user_id,
            request_id=request_id,
            stage=stage,
            symbol=symbol,
            side=side,
            volume=volume,
            outcome=outcome,
            retcode=retcode,
            order_ticket=order_ticket,
            deal_ticket=deal_ticket,
            latency_ms=latency_ms,
            gateway_latency_ms=gateway_latency_ms,
            railway_processing_ms=railway_processing_ms,
            cloudflare_latency_ms=cloudflare_latency_ms,
            spread=spread,
            slippage=slippage,
            commission=commission,
            swap=swap,
            margin_used=margin_used,
            free_margin=free_margin,
            balance=balance,
            equity=equity,
            leverage=leverage,
            broker_server_time=broker_server_time,
            market_session=market_session,
            execution_route=execution_route,
            payload_in=sanitize_payload_dict(payload_in),
            payload_out=sanitize_payload_dict(payload_out),
            related_ids=sanitize_payload_dict(related_ids),
        )
        async with self.uow_factory() as uow:
            stored = cast("ExecutionAudit", await uow.audits.add(audit))
            await uow.commit()
        return stored

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 50
    ) -> list[ExecutionAudit]:
        async with self.uow_factory() as uow:
            return cast(
                "list[ExecutionAudit]",
                await uow.audits.list_for_user(user_id, limit=limit),
            )

    async def get_timeline(
        self, user_id: UUID, request_id: str
    ) -> list[ExecutionAudit]:
        async with self.uow_factory() as uow:
            return cast(
                "list[ExecutionAudit]",
                await uow.audits.list_by_request_id(user_id, request_id),
            )
