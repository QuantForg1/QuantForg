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


def owner_ops_snapshot(
    *,
    queue: DurableDispatchQueue | None = None,
    worker_summary: dict[str, Any] | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Owner/admin aggregate view — no passwords, no sealed envelopes."""
    q = queue or get_durable_dispatch_queue()
    metrics = q.metrics().to_dict()
    pg_counts = pg_dispatch.queue_depth_counts()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "feature_flags": {
            "MULTI_ACCOUNT_DISPATCH_ENABLED": multi_account_dispatch_allowed(settings),
            "MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED": multi_account_live_submit_allowed(
                settings
            ),
        },
        "dispatch_queue": metrics,
        "postgres_queue": pg_counts,
        "workers": worker_summary or {},
        "safety": {
            "live_submit_allowed": False,
            "delivery_suppressed_default": True,
            "weltrade_singleton_not_shared": True,
        },
    }


def customer_dispatch_status(
    *,
    user_id: UUID,
    queue: DurableDispatchQueue | None = None,
) -> dict[str, Any]:
    """Customer-scoped dispatch status — own jobs only."""
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
    return {
        "user_id": str(user_id),
        "job_count": len(jobs),
        "jobs": jobs,
        "events": events[-50:],
        "live_submit_allowed": False,
    }
