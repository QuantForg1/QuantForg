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


def login_registered_to_user(
    user_id: UUID, login: int, *, fetch: Any | None = None
) -> bool:
    """True only if ``login`` is one of this user's own broker accounts.

    17 Nov 2026 incident: the owner's automatic gateway adoption re-pointed
    the owner's connection at a customer's account that a customer had logged
    the shared terminal into. Automatic adoption/rehydration may only bind a
    login the user registered themselves. Fails closed when unreadable.
    """
    login_i = int(login or 0)
    if login_i <= 1:
        return False
    if fetch is None:
        try:
            from app.infrastructure.persistence.direct_postgres import (
                direct_postgres_available,
                fetch as _fetch,
            )
        except Exception:
            return False
        if not direct_postgres_available():
            return False
        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT 1
              FROM public.broker_accounts
             WHERE user_id = $1::uuid
               AND external_account_id = $2
               AND lower(coalesce(status, '')) NOT IN ('revoked', 'deleted')
             LIMIT 1
            """,
            str(user_id),
            str(login_i),
        )
    except Exception:
        logger.warning("login_registration_check_failed")
        return False
    return bool(rows)


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
    if not login_registered_to_user(user_id, login_i):
        logger.warning(
            "broker_ownership_rehydrate_refused",
            reason="login_not_registered_to_owner",
        )
        return {"bound": False, "reason": "login_not_registered_to_owner"}
    bind_execution_account(user_id=user_id, login=login_i)
    _sync_runtime_user(user_id)
    logger.info("broker_ownership_restored", reason="designated_owner_claim")
    return {"bound": True, "reason": "restored"}


def _sync_runtime_user(user_id: UUID) -> None:
    """Point the live cycle at the restored owner. A missing runtime is fine."""
    try:
        from app.application.services.institutional_ite_runtime import (
            get_ite_runtime,
        )
    except Exception:
        return
    runtime = get_ite_runtime()
    if runtime is None:
        return
    runtime.user_id = user_id
