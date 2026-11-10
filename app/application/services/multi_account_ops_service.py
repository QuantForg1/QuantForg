"""Phase 7 — multi-account operational observability (read-only).

Aggregates durable queue metrics and redacted worker health. Never exposes
credentials. Never enables LIVE submit. Customer views are user-scoped.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
    get_durable_dispatch_queue,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.infrastructure.persistence import postgres_signal_dispatch as pg_dispatch


def _delivery_latency_ms(queue: DurableDispatchQueue) -> dict[str, Any]:
    events = list(queue._events)
    claimed_at: dict[str, datetime] = {}
    samples: list[float] = []
    for e in events:
        key = str(e.intent_id)
        if e.event_type == "claimed":
            claimed_at[key] = e.created_at
        elif e.event_type == "acked" and key in claimed_at:
            delta = (e.created_at - claimed_at[key]).total_seconds() * 1000.0
            if delta >= 0:
                samples.append(delta)
    if not samples:
        return {"sample_count": 0, "p50_ms": None, "p95_ms": None, "max_ms": None}
    samples.sort()
    n = len(samples)

    def _pct(p: float) -> float:
        idx = min(n - 1, max(0, round((p / 100.0) * (n - 1))))
        return round(samples[idx], 2)

    return {
        "sample_count": n,
        "p50_ms": _pct(50),
        "p95_ms": _pct(95),
        "max_ms": round(samples[-1], 2),
    }


def _retry_counts(queue: DurableDispatchQueue) -> dict[str, int]:
    retries = 0
    max_attempt = 0
    with queue._lock:
        for job in queue._jobs.values():
            if job.attempt_count > 1:
                retries += job.attempt_count - 1
            max_attempt = max(max_attempt, job.attempt_count)
    return {"retry_events": retries, "max_attempt_count": max_attempt}


def owner_ops_snapshot(
    *,
    queue: DurableDispatchQueue | None = None,
    worker_summary: dict[str, Any] | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Owner/admin aggregate view — no passwords, no sealed envelopes."""
    q = queue or get_durable_dispatch_queue()
    metrics = q.metrics().to_dict()
    by_d = metrics.get("by_delivery_status") or {}
    pg_counts = pg_dispatch.queue_depth_counts()
    workers_pg = None
    brokers: list[dict[str, Any]] = []
    if hasattr(pg_dispatch, "worker_ops_counts"):
        workers_pg = pg_dispatch.worker_ops_counts()
    if hasattr(pg_dispatch, "broker_ops_status"):
        brokers = pg_dispatch.broker_ops_status() or []
    in_proc_workers = worker_summary or {}
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "observe_only": True,
        "feature_flags": {
            "MULTI_ACCOUNT_DISPATCH_ENABLED": multi_account_dispatch_allowed(settings),
            "MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED": multi_account_live_submit_allowed(
                settings
            ),
        },
        "cards": {
            "queue_depth": metrics.get("depth", 0),
            "pending": int(by_d.get("pending") or 0),
            "claimed": int(by_d.get("claimed") or metrics.get("claimed") or 0),
            "delivered": int(by_d.get("delivered") or 0),
            "acknowledged": int(by_d.get("acked") or 0),
            "failed": int(by_d.get("failed") or metrics.get("failed") or 0),
            "expired": int(by_d.get("expired") or metrics.get("expired_leases") or 0),
            "dead_letter": int(
                by_d.get("dead_letter") or metrics.get("dead_letter") or 0
            ),
            "by_lifecycle_state": metrics.get("by_execution_state") or {},
            "by_delivery_status": by_d,
            "retry_counts": _retry_counts(q),
            "delivery_latency": _delivery_latency_ms(q),
            "workers": {
                "active": (workers_pg or {}).get(
                    "active", in_proc_workers.get("worker_count")
                ),
                "healthy": (workers_pg or {}).get("healthy"),
                "stale": (workers_pg or {}).get("stale"),
                "total": (workers_pg or {}).get(
                    "total", in_proc_workers.get("worker_count")
                ),
                "oldest_heartbeat_age_sec": (workers_pg or {}).get(
                    "oldest_heartbeat_age_sec"
                ),
                "in_process_count": in_proc_workers.get("worker_count"),
            },
            "brokers": brokers,
        },
        "dispatch_queue": metrics,
        "postgres_queue": pg_counts,
        "workers_source": workers_pg,
        "workers_in_process": in_proc_workers,
        "safety": {
            "live_submit_allowed": False,
            "delivery_suppressed_default": True,
            "weltrade_singleton_not_shared": True,
            "refresh_does_not_enqueue": True,
        },
    }


def customer_dispatch_status(
    *,
    user_id: UUID,
    queue: DurableDispatchQueue | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Customer-scoped dispatch status — own jobs only.

    Never fabricates connected/verified states. Never exposes credentials,
    worker tokens, or other customers' jobs.
    """
    q = queue or get_durable_dispatch_queue()
    jobs = [j.to_public_dict() for j in q.list_for_user(user_id)]
    events = [
        {
            "event_id": str(e.event_id),
            "intent_id": str(e.intent_id),
            "event_type": e.event_type,
            "detail": e.detail,
            "created_at": e.created_at.isoformat(),
        }
        for e in q.events_for_user(user_id)
    ]
    dispatch_on = multi_account_dispatch_allowed(settings)
    live_on = multi_account_live_submit_allowed(settings)
    blocked_reasons: list[str] = []
    if not dispatch_on:
        blocked_reasons.append("multi_account_dispatch_disabled")
    if not live_on:
        blocked_reasons.append("live_submit_disabled")
    if not jobs and not dispatch_on:
        blocked_reasons.append("awaiting_owner_enablement")
    return {
        "user_id": str(user_id),
        "job_count": len(jobs),
        "jobs": jobs,
        "events": events[-50:],
        "live_submit_allowed": False,
        "dispatch_enabled": bool(dispatch_on),
        "eligibility": {
            "dispatch_ready": bool(dispatch_on),
            "live_submit_ready": False,
            "blocked": bool(blocked_reasons),
            "blocked_reasons": blocked_reasons,
        },
        "worker_availability": {
            # Customer surface never invents online workers.
            "reported": False,
            "note": (
                "Worker online status is owner/ops-only until a verified "
                "assignment exists for this account."
            ),
        },
        "connection_verification": {
            "verified": False,
            "note": (
                "Connection stays unverified until broker ownership evidence "
                "is recorded for this account. Demo vs Live is shown from "
                "broker server metadata only — never fabricated."
            ),
        },
        "credentials_exposed": False,
    }
