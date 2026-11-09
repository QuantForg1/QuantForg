"""Authenticated MT5 Windows worker ↔ Railway control-plane APIs (Phase 1C).

Every route requires ``Authorization: Bearer <WORKER_SERVICE_TOKEN>``.
Outbound HTTPS from Windows only — no inbound Windows ports.
Passwords are never accepted or returned on these routes.
LIVE multi-account submit remains off.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.presentation.dependencies.mt5_workers import WorkerApi, WorkerAuth
from app.presentation.schemas.mt5_workers import (
    WorkerHealthRequest,
    WorkerHeartbeatRequest,
    WorkerHostRegisterRequest,
    WorkerIdRequest,
    WorkerRegisterRequest,
)

router = APIRouter(prefix="/mt5-workers", tags=["mt5-workers"])


@router.post("/hosts/register")
async def register_host(
    body: WorkerHostRegisterRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return {
        "ok": True,
        **api.ensure_host(
            host_code=body.host_code,
            max_terminals=body.max_terminals,
            region=body.region,
        ),
    }


@router.post("/register")
async def register_worker(
    body: WorkerRegisterRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.register(
        host_code=body.host_code,
        slot_id=body.slot_id,
        platform=body.platform,
        max_terminals=body.max_terminals,
        user_id=body.user_id,
        broker_account_id=body.broker_account_id,
    )


@router.get("/assignments/{worker_id}")
async def get_assignment(
    worker_id: UUID,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.get_assignment(worker_id)


@router.post("/heartbeat")
async def worker_heartbeat(
    body: WorkerHeartbeatRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.heartbeat(
        worker_id=body.worker_id,
        slot_id=body.slot_id,
        lifecycle=body.lifecycle,
        ready=body.ready,
    )


@router.post("/health")
async def worker_health(
    body: WorkerHealthRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.report_health(
        worker_id=body.worker_id,
        cpu_percent=body.cpu_percent,
        ram_percent=body.ram_percent,
        disk_percent=body.disk_percent,
        healthy=body.healthy,
        details=body.details,
    )


@router.post("/release")
async def release_worker(
    body: WorkerIdRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.release(worker_id=body.worker_id)


@router.post("/revoke")
async def revoke_worker(
    body: WorkerIdRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.revoke(worker_id=body.worker_id)


@router.post("/reconnect")
async def reconnect_worker(
    body: WorkerIdRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.reconnect(worker_id=body.worker_id)


@router.post("/stale/scan")
async def scan_stale_workers(
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    return api.scan_stale()


@router.post("/credentials/authorize")
async def authorize_credentials(
    body: WorkerIdRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    """Assignment check only — never returns decrypted passwords."""
    return api.authorize_credentials(worker_id=body.worker_id)


@router.post("/credentials/claim")
async def claim_sealed_credentials(
    body: WorkerIdRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    """Issue opaque sealed envelope for assigned worker. No plaintext password field."""
    return api.claim_sealed_credentials(worker_id=body.worker_id)
