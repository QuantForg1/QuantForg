"""Optional Postgres persistence for MT5 broker verification evidence.

Never stores passwords. Falls back silently when the table is not migrated.
"""

from __future__ import annotations

import json
import logging
from typing import Any

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
              AND table_name = 'mt5_broker_verification_evidence'
            LIMIT 1
            """)
        _TABLE_READY = bool(rows)
    except Exception:
        logger.warning("mt5_broker_verification_table_probe_failed")
        _TABLE_READY = False
    return _TABLE_READY


def upsert_evidence(entry: dict[str, Any]) -> bool:
    """Upsert one broker evidence row. Returns False when unavailable."""
    if not table_ready():
        return False
    slug = str(entry.get("broker_slug") or "").strip().lower()
    if not slug:
        return False
    from app.infrastructure.persistence.direct_postgres import execute

    payload = {
        k: v
        for k, v in entry.items()
        if "password" not in str(k).lower() and "secret" not in str(k).lower()
    }
    try:
        execute(
            """
            INSERT INTO public.mt5_broker_verification_evidence (
              broker_slug, connectable, connection_status, evidence, last_error
            ) VALUES (
              $1, $2, $3, $4::jsonb, $5
            )
            ON CONFLICT (broker_slug) DO UPDATE SET
              connectable = EXCLUDED.connectable,
              connection_status = EXCLUDED.connection_status,
              evidence = EXCLUDED.evidence,
              last_error = EXCLUDED.last_error,
              updated_at = timezone('utc', now())
            """,
            slug,
            bool(payload.get("connectable")),
            str(payload.get("connection_status") or "not_verified"),
            json.dumps(payload),
            str(payload.get("last_error") or ""),
        )
        return True
    except Exception:
        logger.warning("mt5_broker_verification_upsert_failed slug=%s", slug)
        return False
