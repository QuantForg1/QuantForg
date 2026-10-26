"""Restore the process execution binding from the persisted owner claim.

The Windows gateway keeps the MT5 login across a Railway redeploy. The
in-process binding does not. This module rebinds only when the live login
matches a connected ``mt5_connections`` row whose user email is the
designated owner. It never invents ownership and never logs the login.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.services.account_execution_gate import (
    bind_execution_account,
)
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from core.logging import get_logger

logger = get_logger(__name__)


def rehydrate_designated_owner_binding(live_login: int) -> dict[str, Any]:
    """Bind the live login when the designated owner's claim matches it."""
    login_i = int(live_login or 0)
    if login_i <= 1:
        return {"bound": False, "reason": "live_login_unknown"}
    try:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch,
        )
    except Exception:
        return {"bound": False, "reason": "database_unavailable"}
    if not direct_postgres_available():
        return {"bound": False, "reason": "database_unavailable"}
    try:
        rows = fetch(
            """
            SELECT c.user_id::text AS user_id, u.email AS email
            FROM mt5_connections c
            JOIN users u ON u.id = c.user_id
            WHERE c.connected IS TRUE AND c.login = $1
            ORDER BY CASE
                WHEN lower(u.email) = lower($2) THEN 0 ELSE 1
            END, c.updated_at DESC
            LIMIT 1
            """,
            login_i,
            DESIGNATED_OWNER_EMAIL,
        )
    except Exception:
        logger.warning("broker_ownership_rehydrate_failed", error_type="query_failed")
        return {"bound": False, "reason": "query_failed"}
    if not rows:
        return {"bound": False, "reason": "no_connected_claim"}
    email = str(rows[0].get("email") or "")
    from app.domain.identity.designated_owner import is_designated_owner_email

    if not is_designated_owner_email(email):
        return {"bound": False, "reason": "claim_not_designated_owner"}
    try:
        user_id = UUID(str(rows[0].get("user_id") or ""))
    except (TypeError, ValueError):
        return {"bound": False, "reason": "claim_user_invalid"}
    bind_execution_account(user_id=user_id, login=login_i)
    logger.info("broker_ownership_restored", reason="designated_owner_claim")
    return {"bound": True, "reason": "restored"}
