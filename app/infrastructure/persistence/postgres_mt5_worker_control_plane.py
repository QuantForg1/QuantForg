"""Durable MT5 worker control-plane persistence (Phase 1E).

Uses direct Postgres (service role / DATABASE_URL). Never stores passwords.
Falls back silently when the durable table is not yet migrated.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)

_TABLE_READY: bool | None = None


def _available() -> bool:
    try:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
        )

        return direct_postgres_available()
    except Exception:
        return False


def table_ready() -> bool:
    """True when ``mt5_worker_control_plane`` exists."""
    global _TABLE_READY
    if _TABLE_READY is not None:
        return _TABLE_READY
    if not _available():
        _TABLE_READY = False
        return False
    try:
        from app.infrastructure.persistence.direct_postgres import fetch

        rows = fetch("""
            SELECT 1 AS ok
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'mt5_worker_control_plane'
            LIMIT 1
            """)
        _TABLE_READY = bool(rows)
    except Exception:
        logger.warning("mt5_worker_cp_table_probe_failed")
        _TABLE_READY = False
    return _TABLE_READY


def reset_table_ready_cache() -> None:
    global _TABLE_READY
    _TABLE_READY = None


def upsert_worker_row(row: dict[str, Any]) -> bool:
    """Insert/update durable worker row. Returns False when persistence unavailable."""
    if not table_ready():
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    meta = row.get("metadata") or {}
    if not isinstance(meta, str):
        meta = json.dumps(meta)
    execute(
        """
        INSERT INTO public.mt5_worker_control_plane (
          worker_id, host_code, slot_id, host_id, user_id, broker_account_id,
          lifecycle_status, runtime_session_id, platform, last_heartbeat_at,
          last_health_check_at, last_error, attempt_count, trade_allowed,
          account_login_verified, server_verified, revoked, metadata
        ) VALUES (
          $1::uuid, $2, $3, $4::uuid, $5::uuid, $6::uuid,
          $7, $8, $9, $10::timestamptz,
          $11::timestamptz, $12, $13, $14,
          $15, $16, $17, $18::jsonb
        )
        ON CONFLICT (worker_id) DO UPDATE SET
          host_code = EXCLUDED.host_code,
          slot_id = EXCLUDED.slot_id,
          host_id = EXCLUDED.host_id,
          user_id = EXCLUDED.user_id,
          broker_account_id = EXCLUDED.broker_account_id,
          lifecycle_status = EXCLUDED.lifecycle_status,
          runtime_session_id = EXCLUDED.runtime_session_id,
          platform = EXCLUDED.platform,
          last_heartbeat_at = EXCLUDED.last_heartbeat_at,
          last_health_check_at = EXCLUDED.last_health_check_at,
          last_error = EXCLUDED.last_error,
          attempt_count = EXCLUDED.attempt_count,
          trade_allowed = EXCLUDED.trade_allowed,
          account_login_verified = EXCLUDED.account_login_verified,
          server_verified = EXCLUDED.server_verified,
          revoked = EXCLUDED.revoked,
          metadata = EXCLUDED.metadata,
          updated_at = timezone('utc', now())
        """,
        row["worker_id"],
        row["host_code"],
        row["slot_id"],
        row.get("host_id"),
        row.get("user_id"),
        row.get("broker_account_id"),
        row["lifecycle_status"],
        row.get("runtime_session_id") or "",
        row.get("platform") or "windows-local",
        row.get("last_heartbeat_at"),
        row.get("last_health_check_at"),
        row.get("last_error") or "",
        int(row.get("attempt_count") or 0),
        row.get("trade_allowed"),
        row.get("account_login_verified") or "",
        row.get("server_verified") or "",
        bool(row.get("revoked")),
        meta,
    )
    return True


def load_all_workers() -> list[dict[str, Any]]:
    if not table_ready():
        return []
    from app.infrastructure.persistence.direct_postgres import fetch

    return fetch("""
        SELECT worker_id, host_code, slot_id, host_id, user_id, broker_account_id,
               lifecycle_status, runtime_session_id, platform, last_heartbeat_at,
               last_health_check_at, last_error, attempt_count, trade_allowed,
               account_login_verified, server_verified, revoked, metadata,
               created_at, updated_at
        FROM public.mt5_worker_control_plane
        ORDER BY created_at ASC
        """)


def load_worker(worker_id: UUID | str) -> dict[str, Any] | None:
    if not table_ready():
        return None
    from app.infrastructure.persistence.direct_postgres import fetch

    rows = fetch(
        """
        SELECT worker_id, host_code, slot_id, host_id, user_id, broker_account_id,
               lifecycle_status, runtime_session_id, platform, last_heartbeat_at,
               last_health_check_at, last_error, attempt_count, trade_allowed,
               account_login_verified, server_verified, revoked, metadata,
               created_at, updated_at
        FROM public.mt5_worker_control_plane
        WHERE worker_id = $1::uuid
        LIMIT 1
        """,
        str(worker_id),
    )
    return rows[0] if rows else None


def mark_revoked(worker_id: UUID | str) -> bool:
    if not table_ready():
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    status = execute(
        """
        UPDATE public.mt5_worker_control_plane
        SET revoked = true,
            lifecycle_status = 'revoked',
            updated_at = timezone('utc', now())
        WHERE worker_id = $1::uuid
        """,
        str(worker_id),
    )
    return bool(status)


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
