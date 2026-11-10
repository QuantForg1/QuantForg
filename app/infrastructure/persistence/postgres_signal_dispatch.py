"""Postgres mirror for Phase 6.1 durable dispatch queue.

Uses service-role DATABASE_URL. Never stores plaintext credentials.
Falls back silently when lease columns / tables are not yet migrated.
Does not enable LIVE multi-account submit.
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.domain.multi_account.dispatch_queue import DispatchJob
from app.domain.multi_account.signal_dispatch import CentralSignalIntent

logger = logging.getLogger(__name__)

_READY: bool | None = None


def _available() -> bool:
    try:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
        )

        return direct_postgres_available()
    except Exception:
        return False


def table_ready() -> bool:
    """True when lease columns exist on account_execution_intents."""
    global _READY
    if _READY is not None:
        return _READY
    if not _available():
        _READY = False
        return False
    try:
        from app.infrastructure.persistence.direct_postgres import fetch

        rows = fetch("""
            SELECT 1 AS ok
              FROM information_schema.columns
             WHERE table_schema = 'public'
               AND table_name = 'account_execution_intents'
               AND column_name = 'delivery_status'
             LIMIT 1
            """)
        _READY = bool(rows)
    except Exception:
        logger.warning("dispatch_queue_table_probe_failed")
        _READY = False
    return _READY


def reset_table_ready_cache() -> None:
    global _READY
    _READY = None


def upsert_central_signal(signal: CentralSignalIntent) -> bool:
    if not table_ready():
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    payload = {
        k: v
        for k, v in (signal.metadata or {}).items()
        if k.lower() not in {"password", "token", "secret", "sealed_credentials"}
    }
    execute(
        """
        INSERT INTO public.central_signals (
          id, idempotency_key, symbol, side, quality,
          entry_price, stop_loss, take_profit, strategy_id, trace_id,
          status, payload
        ) VALUES (
          $1::uuid, $2, $3, $4, $5,
          $6, $7, $8, $9, $10,
          'recorded', $11::jsonb
        )
        ON CONFLICT (idempotency_key) DO UPDATE SET
          updated_at = timezone('utc', now())
        """,
        signal.signal_id,
        signal.idempotency_key,
        signal.symbol,
        signal.side,
        int(signal.quality),
        signal.entry,
        signal.stop_loss,
        signal.take_profit,
        signal.strategy_id,
        signal.trace_id,
        json.dumps(payload),
    )
    return True


def upsert_intent_job(job: DispatchJob) -> bool:
    if not table_ready():
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    execute(
        """
        INSERT INTO public.account_execution_intents (
          id, signal_id, user_id, broker_account_id, idempotency_key,
          state, block_reason, attempt_count, last_error, payload,
          delivery_status, lease_owner_worker_id, lease_expires_at,
          available_at, delivered_at, acked_at, max_attempts,
          next_retry_at, kill_switch
        ) VALUES (
          $1::uuid, $2::uuid, $3::uuid, $4::uuid, $5,
          $6, $7, $8, $9, $10::jsonb,
          $11, $12::uuid, $13::timestamptz,
          $14::timestamptz, $15::timestamptz, $16::timestamptz, $17,
          $18::timestamptz, $19
        )
        ON CONFLICT (idempotency_key) DO UPDATE SET
          state = EXCLUDED.state,
          block_reason = EXCLUDED.block_reason,
          attempt_count = EXCLUDED.attempt_count,
          last_error = EXCLUDED.last_error,
          payload = EXCLUDED.payload,
          delivery_status = EXCLUDED.delivery_status,
          lease_owner_worker_id = EXCLUDED.lease_owner_worker_id,
          lease_expires_at = EXCLUDED.lease_expires_at,
          available_at = EXCLUDED.available_at,
          delivered_at = EXCLUDED.delivered_at,
          acked_at = EXCLUDED.acked_at,
          max_attempts = EXCLUDED.max_attempts,
          next_retry_at = EXCLUDED.next_retry_at,
          kill_switch = EXCLUDED.kill_switch,
          updated_at = timezone('utc', now())
        """,
        job.intent_id,
        job.signal_id,
        job.user_id,
        job.broker_account_id,
        job.idempotency_key,
        job.state.value,
        job.block_reason or "",
        job.attempt_count,
        job.last_error,
        json.dumps(job.payload or {}),
        job.delivery_status.value,
        job.lease_owner_worker_id,
        job.lease_expires_at,
        job.available_at,
        job.delivered_at,
        job.acked_at,
        job.max_attempts,
        job.next_retry_at,
        job.kill_switch,
    )
    return True


def record_delivery_event(
    *,
    intent_id: UUID,
    user_id: UUID,
    broker_account_id: UUID,
    event_type: str,
    worker_id: UUID | None = None,
    detail: str = "",
    metadata: dict[str, Any] | None = None,
) -> bool:
    if not table_ready():
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    safe_meta = {
        k: v
        for k, v in (metadata or {}).items()
        if k.lower() not in {"password", "token", "secret", "sealed_credentials"}
    }
    try:
        execute(
            """
            INSERT INTO public.dispatch_delivery_events (
              intent_id, user_id, broker_account_id, worker_id,
              event_type, detail, metadata
            ) VALUES (
              $1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, $6, $7::jsonb
            )
            """,
            intent_id,
            user_id,
            broker_account_id,
            worker_id,
            event_type,
            detail[:500],
            json.dumps(safe_meta),
        )
        return True
    except Exception:
        logger.warning("dispatch_delivery_event_insert_failed", exc_info=True)
        return False


def queue_depth_counts() -> dict[str, Any] | None:
    """Owner/ops aggregate counts — no PII beyond counts."""
    if not table_ready():
        return None
    from app.infrastructure.persistence.direct_postgres import fetch

    rows = fetch("""
        SELECT delivery_status, count(*)::int AS n
          FROM public.account_execution_intents
         GROUP BY delivery_status
         ORDER BY 1
        """)
    return {
        "by_delivery_status": {r["delivery_status"]: r["n"] for r in rows},
        "live_submit_enabled": False,
    }

def worker_ops_counts() -> dict[str, Any] | None:
    """Aggregate worker health from execution_workers (no credentials)."""
    if not _available():
        return None
    from app.infrastructure.persistence.direct_postgres import fetch

    try:
        rows = fetch(
            """
            SELECT
              count(*)::int AS total,
              count(*) FILTER (
                WHERE status IN ('registered', 'healthy', 'degraded', 'offline')
              )::int AS active,
              count(*) FILTER (WHERE status = 'healthy')::int AS healthy,
              count(*) FILTER (
                WHERE last_heartbeat_at IS NULL
                   OR last_heartbeat_at < timezone('utc', now())
                       - interval '90 seconds'
              )::int AS stale,
              coalesce(
                extract(
                  epoch FROM (timezone('utc', now()) - max(last_heartbeat_at))
                )::int,
                -1
              ) AS oldest_heartbeat_age_sec
              FROM public.execution_workers
            """
        )
        if not rows:
            return {
                "total": 0,
                "active": 0,
                "healthy": 0,
                "stale": 0,
                "oldest_heartbeat_age_sec": None,
            }
        row = dict(rows[0])
        age = row.get("oldest_heartbeat_age_sec")
        return {
            "total": int(row.get("total") or 0),
            "active": int(row.get("active") or 0),
            "healthy": int(row.get("healthy") or 0),
            "stale": int(row.get("stale") or 0),
            "oldest_heartbeat_age_sec": (
                None if age is None or int(age) < 0 else int(age)
            ),
        }
    except Exception:
        logger.warning("worker_ops_counts_failed", exc_info=True)
        return None


def broker_ops_status() -> list[dict[str, Any]]:
    """Per-broker operational counts — redacted (no logins/passwords)."""
    if not _available():
        return []
    from app.infrastructure.persistence.direct_postgres import fetch

    try:
        rows = fetch(
            """
            SELECT coalesce(b.platform_code, 'unknown') AS platform,
                   coalesce(b.slug, b.name, 'unknown') AS broker,
                   a.status,
                   a.environment,
                   count(*)::int AS n
              FROM public.broker_accounts a
              LEFT JOIN public.brokers b ON b.id = a.broker_id
             GROUP BY 1, 2, 3, 4
             ORDER BY 1, 2, 3
             LIMIT 50
            """
        )
        return [dict(r) for r in rows]
    except Exception:
        logger.warning("broker_ops_status_failed", exc_info=True)
        return []


def claim_next_skip_locked(
    *,
    worker_id: UUID,
    user_id: UUID,
    broker_account_id: UUID,
    lease_seconds: int = 60,
) -> dict[str, Any] | None:
    """Atomically claim one queued intent with FOR UPDATE SKIP LOCKED."""
    if not table_ready():
        return None
    from app.infrastructure.persistence.direct_postgres import fetch

    try:
        rows = fetch(
            """
            WITH candidate AS (
              SELECT id
                FROM public.account_execution_intents
               WHERE state = 'queued'
                 AND delivery_status IN ('pending', 'failed', 'expired')
                 AND kill_switch = false
                 AND user_id = $1::uuid
                 AND broker_account_id = $2::uuid
                 AND available_at <= timezone('utc', now())
                 AND (
                   lease_owner_worker_id IS NULL
                   OR lease_expires_at IS NULL
                   OR lease_expires_at <= timezone('utc', now())
                 )
               ORDER BY available_at ASC, created_at ASC
               FOR UPDATE SKIP LOCKED
               LIMIT 1
            )
            UPDATE public.account_execution_intents AS a
               SET delivery_status = 'claimed',
                   lease_owner_worker_id = $3::uuid,
                   lease_expires_at =
                     timezone('utc', now()) + make_interval(secs => $4::int),
                   attempt_count = a.attempt_count + 1,
                   updated_at = timezone('utc', now())
              FROM candidate
             WHERE a.id = candidate.id
         RETURNING a.id, a.signal_id, a.user_id, a.broker_account_id,
                   a.idempotency_key, a.state, a.delivery_status,
                   a.attempt_count, a.lease_expires_at
            """,
            user_id,
            broker_account_id,
            worker_id,
            int(lease_seconds),
        )
    except Exception:
        logger.warning("claim_next_skip_locked_failed", exc_info=True)
        return None
    if not rows:
        return None
    row = dict(rows[0])
    return {
        "intent_id": str(row["id"]),
        "signal_id": str(row["signal_id"]),
        "user_id": str(row["user_id"]),
        "broker_account_id": str(row["broker_account_id"]),
        "idempotency_key": row["idempotency_key"],
        "state": row["state"],
        "delivery_status": row["delivery_status"],
        "attempt_count": int(row["attempt_count"] or 0),
        "lease_expires_at": (
            row["lease_expires_at"].isoformat()
            if row.get("lease_expires_at") is not None
            else None
        ),
        "live_submit_allowed": False,
        "delivery_suppressed": True,
    }
