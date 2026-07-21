"""Trading Kernel V1 API — orchestrates only; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.trading_kernel import TradingKernelService
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/trading-kernel", tags=["trading-kernel"])

_service = TradingKernelService()


class CycleRequest(BaseModel):
    side: str = "buy"
    spread: float | str | None = None
    confidence: float | str | None = None
    news_blackout: bool | None = None
    kill_switch: bool | None = None
    execution_mode: str | None = None
    alpha: dict[str, Any] | None = None
    risk_engine_passed: bool | None = None
    safety_engine_passed: bool | None = None
    decision: str | None = None
    plugin_snapshot: dict[str, Any] | None = None
    certification: dict[str, Any] | None = None
    go_nogo: str | None = None


class PoliciesRequest(BaseModel):
    max_spread: float | str | None = None
    min_confidence: float | str | None = None
    deterministic_replay: bool | None = None
    max_events: int | None = Field(default=None, ge=100, le=10000)
    max_cycles: int | None = Field(default=None, ge=10, le=1000)
    feature_flags: dict[str, bool] | None = None


class FlagRequest(BaseModel):
    flag: str = Field(min_length=1, max_length=64)
    enabled: bool = True


@router.get("/status")
async def trading_kernel_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.post("/cycle")
async def trading_kernel_cycle(
    body: CycleRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.run_cycle(body.model_dump())


@router.get("/events")
async def trading_kernel_events(
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    trace_id: str | None = None,
) -> dict[str, Any]:
    _ = user
    return _service.events(limit=limit, trace_id=trace_id)


@router.get("/replay/stage")
async def trading_kernel_stage_replay(
    user: CurrentUser,
    trace_id: str = Query(..., min_length=8, max_length=64),
    stage: str | None = None,
) -> dict[str, Any]:
    _ = user
    return _service.stage_replay(trace_id=trace_id, stage=stage)


@router.get("/replay/deterministic")
async def trading_kernel_deterministic_replay(
    user: CurrentUser,
    trace_id: str = Query(..., min_length=8, max_length=64),
) -> dict[str, Any]:
    _ = user
    return _service.deterministic_replay(trace_id)


@router.get("/policies")
async def trading_kernel_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def trading_kernel_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)


@router.get("/feature-flags")
async def trading_kernel_flags(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.feature_flags()


@router.post("/feature-flags")
async def trading_kernel_set_flag(
    body: FlagRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.set_feature_flag(body.flag, body.enabled)


@router.get("/plugins")
async def trading_kernel_plugins(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.plugins()


@router.get("/certification")
async def trading_kernel_certification(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.certification()
