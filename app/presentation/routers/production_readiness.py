"""Production Readiness API — reliability desk; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.production_readiness import ProductionReadinessService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/production-readiness", tags=["production-readiness"])

_service = ProductionReadinessService()


class PoliciesBody(BaseModel):
    max_gateway_latency_ms: float | None = None
    max_order_latency_ms: float | None = None
    max_journal_latency_ms: float | None = None
    min_health_score: float | None = None
    require_gateway_available: bool | None = None
    require_mt5_connected: bool | None = None
    require_kill_switch_clear_for_live: bool | None = None
    require_risk_engine: bool | None = None
    require_safety_engine: bool | None = None
    auto_recover_gateway: bool | None = None
    auto_recover_mt5: bool | None = None


class LiveFeedsBody(BaseModel):
    pre_trade_facts: dict[str, Any] | None = None
    post_trade_rows: list[dict[str, Any]] | None = None
    security: dict[str, Any] | None = None
    shadow_readiness: dict[str, Any] | None = None


class RecoveryLogBody(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    ok: bool = True
    detail: str = Field(default="", max_length=2000)
    meta: dict[str, Any] = Field(default_factory=dict)


class FailureLogBody(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    detail: str = Field(min_length=1, max_length=2000)
    meta: dict[str, Any] = Field(default_factory=dict)


def _operator(user: CurrentUser) -> str:
    return str(
        getattr(user, "email", None) or getattr(user, "id", "") or "operator"
    )


@router.get("/status")
async def production_readiness_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/dashboard")
async def production_readiness_dashboard(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.dashboard()


@router.post("/dashboard")
async def production_readiness_dashboard_feeds(
    body: LiveFeedsBody, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.dashboard(
        pre_trade_facts=body.pre_trade_facts,
        post_trade_rows=body.post_trade_rows,
        security=body.security,
        shadow_readiness=body.shadow_readiness,
    )


@router.get("/policies")
async def production_readiness_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return {"policies": _service.policies()}


@router.post("/policies")
async def production_readiness_update_policies(
    body: PoliciesBody, user: CurrentUser
) -> dict[str, Any]:
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return {
        "policies": _service.update_policies(
            updates, operator=_operator(user)
        )
    }


@router.get("/audit")
async def production_readiness_audit(
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    _ = user
    return _service.audit(limit=limit)


@router.post("/audit/recovery")
async def production_readiness_log_recovery(
    body: RecoveryLogBody, user: CurrentUser
) -> dict[str, Any]:
    return _service.log_recovery(
        action=body.action,
        ok=body.ok,
        detail=body.detail,
        operator=_operator(user),
        meta=body.meta,
    )


@router.post("/audit/failure")
async def production_readiness_log_failure(
    body: FailureLogBody, user: CurrentUser
) -> dict[str, Any]:
    return _service.log_failure(
        action=body.action,
        detail=body.detail,
        operator=_operator(user),
        meta=body.meta,
    )
