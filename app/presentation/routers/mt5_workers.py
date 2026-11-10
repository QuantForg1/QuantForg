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

from app.application.services.multi_account_dispatch_queue import (
    get_durable_dispatch_queue,
)
from app.application.services.multi_account_ops_service import owner_ops_snapshot
from app.domain.exceptions.auth import AuthorizationError
from app.presentation.dependencies.mt5_workers import WorkerApi, WorkerAuth
from app.presentation.schemas.mt5_workers import (
    DispatchAckRequest,
    DispatchClaimRequest,
    DispatchFailRequest,
    WorkerHealthRequest,
    WorkerHeartbeatRequest,
    WorkerHostRegisterRequest,
    WorkerIdRequest,
    WorkerRegisterRequest,
    WorkerVerificationReport,
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


@router.post("/verification/report")
async def report_verification(
    body: WorkerVerificationReport,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    """Accept redacted Windows MT5 verification evidence. Never accepts passwords."""
    return api.report_verification(body.model_dump())


@router.get("/ops/summary")
async def worker_ops_summary(
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    """Worker + verification + Phase 7 owner ops snapshot (no passwords)."""
    worker_summary = api.ops_summary()
    snap = owner_ops_snapshot(worker_summary=worker_summary)
    # Preserve legacy worker summary keys while adding Phase 7 aggregates.
    return {
        **worker_summary,
        **snap,
        "live_submit_allowed": False,
    }


@router.post("/dispatch/claim")
async def dispatch_claim(
    body: DispatchClaimRequest,
    _: WorkerAuth,
    api: WorkerApi,
) -> dict[str, Any]:
    """Claim next queued delivery job for this worker's assigned account.

    Delivery only — never invokes OMS / order_send. LIVE submit stays off.
    Claim is bound to the registered worker assignment (no body spoofing).
    """
    try:
        worker = api.require_worker(body.worker_id)
    except AuthorizationError as exc:
        code = getattr(exc, "code", None) or "worker_unauthorized"
        return {"ok": False, "error": code}
    assigned_ok = (
        worker.user_id == body.user_id
        and worker.broker_account_id == body.broker_account_id
    )
    if not assigned_ok:
        return {
            "ok": False,
            "error": "assignment_mismatch",
            "live_submit_allowed": False,
        }
    queue = get_durable_dispatch_queue()
    job = queue.claim_next(
        worker_id=body.worker_id,
        user_id=worker.user_id,
        broker_account_id=worker.broker_account_id,
    )
    if job is None:
        return {"ok": True, "job": None, "live_submit_allowed": False}
    return {
        "ok": True,
        "job": job.to_public_dict(),
        "live_submit_allowed": False,
        "delivery_suppressed": True,
    }


@router.post("/dispatch/ack")
async def dispatch_ack(
    body: DispatchAckRequest,
    _: WorkerAuth,
) -> dict[str, Any]:
    """Acknowledge delivery (not broker fill). No order_send."""
    queue = get_durable_dispatch_queue()
    try:
        job = queue.acknowledge(
            intent_id=body.intent_id,
            worker_id=body.worker_id,
            detail=body.detail,
        )
    except KeyError:
        return {"ok": False, "error": "intent_not_found"}
    except PermissionError:
        return {"ok": False, "error": "lease_owner_mismatch"}
    except TimeoutError:
        return {"ok": False, "error": "lease_expired"}
    return {"ok": True, "job": job.to_public_dict(), "live_submit_allowed": False}


@router.post("/dispatch/fail")
async def dispatch_fail(
    body: DispatchFailRequest,
    _: WorkerAuth,
) -> dict[str, Any]:
    """Report delivery failure with idempotent retry / dead-letter."""
    queue = get_durable_dispatch_queue()
    try:
        job = queue.fail(
            intent_id=body.intent_id,
            worker_id=body.worker_id,
            reason=body.reason,
        )
    except KeyError:
        return {"ok": False, "error": "intent_not_found"}
    except PermissionError:
        return {"ok": False, "error": "lease_owner_mismatch"}
    except TimeoutError:
        return {"ok": False, "error": "lease_expired"}
    return {"ok": True, "job": job.to_public_dict(), "live_submit_allowed": False}


@router.post("/dispatch/recover")
async def dispatch_recover(
    _: WorkerAuth,
) -> dict[str, Any]:
    """Release claimed leases after process restart (ops / worker token)."""
    queue = get_durable_dispatch_queue()
    recovered = queue.recover_after_restart()
    expired = queue.expire_leases()
    return {
        "ok": True,
        "recovered": recovered,
        "expired_leases": expired,
        "metrics": queue.metrics().to_dict(),
        "live_submit_allowed": False,
    }
