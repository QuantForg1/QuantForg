"""Integration Sprint V1 API — read-only feeds; never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.integration_sprint_v1 import (
    IntegrationSprintV1Service,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/integration-sprint-v1",
    tags=["integration-sprint-v1"],
)

_service = IntegrationSprintV1Service()


class PoliciesRequest(BaseModel):
    max_deals: int | None = Field(default=None, ge=1, le=10_000)
    max_journal: int | None = Field(default=None, ge=1, le=10_000)
    max_calendar_events: int | None = Field(default=None, ge=1, le=500)
    max_warehouse_bars: int | None = Field(default=None, ge=10, le=50_000)
    max_durable_per_namespace: int | None = Field(
        default=None, ge=10, le=50_000
    )
    stale_after_seconds: float | None = Field(default=None, ge=1, le=86_400)
    feature_flags: dict[str, bool] | None = None


class HydrateRequest(BaseModel):
    target: str = Field(description="ivp | llp | rmip | prc")
    overrides: dict[str, Any] | None = None


class StorageAppendRequest(BaseModel):
    namespace: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None
    id: str | None = None


class WarehouseIngestRequest(BaseModel):
    bars: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/status")
async def integration_status(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.status()


@router.get("/bus")
async def integration_bus(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.bus()


@router.get("/feeds/{feed_name}")
async def integration_feed(
    feed_name: str, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.feed(feed_name)


@router.post("/hydrate")
async def integration_hydrate(
    body: HydrateRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.hydrate(body.target, body.overrides)


@router.get("/storage/{namespace}")
async def integration_storage_list(
    namespace: str,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=500),
) -> dict[str, Any]:
    _ = user
    return _service.storage_list(namespace, limit=limit)


@router.post("/storage/append")
async def integration_storage_append(
    body: StorageAppendRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.storage_append(
        body.namespace,
        {
            "id": body.id,
            "payload": body.payload,
            "source": body.source or "api",
        },
    )


@router.post("/warehouse/ingest")
async def integration_warehouse_ingest(
    body: WarehouseIngestRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    return _service.ingest_warehouse(body.bars)


@router.get("/policies")
async def integration_policies(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return _service.policies()


@router.post("/policies")
async def integration_update_policies(
    body: PoliciesRequest, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return _service.update_policies(updates)
