"""Server-side entitlement check for automated trading.

A customer may start or resume a robot, and a multi-account worker may send
an entry, only while the customer holds an active paid license. The free
trial was discontinued on 19 Nov 2026; an old trial row no longer entitles.
Owner/admin accounts are exempt (they operate the platform).
A suspended/deactivated customer, or one whose robot access an admin removed
(``user_access_overrides``), is not entitled even with a paid license.
Pause, Stop and Emergency Stop are never gated: a customer can always reduce
risk. Unknown state (storage unreadable) is not entitled.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

EXEMPT_ROLES = frozenset({"owner", "admin"})


@dataclass(frozen=True, slots=True)
class Entitlement:
    allowed: bool
    reason: str
    source: str = ""


def check_trading_entitlement(
    *, user_id: UUID, fetch: Any | None = None
) -> Entitlement:
    if fetch is None:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch as _fetch,
        )

        if not direct_postgres_available():
            # Local/tests without durable storage: no billing to enforce.
            return Entitlement(True, "no_billing_store", "none")
        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT
              (SELECT lower(role::text) FROM public.users WHERE id = $1::uuid) AS role,
              EXISTS (
                SELECT 1 FROM public.licenses l
                 WHERE l.user_id = $1::uuid AND lower(l.status) = 'active'
                   AND (l.expires_at IS NULL OR l.expires_at > now())
              ) AS licensed,
              EXISTS (
                SELECT 1 FROM public.billing_trials t
                 WHERE t.user_id = $1::uuid AND lower(t.status) = 'active'
                   AND t.expires_at > now()
              ) AS trial,
              (SELECT lower(status::text) FROM public.users WHERE id = $1::uuid)
                AS user_status,
              EXISTS (
                SELECT 1 FROM public.user_access_overrides o
                 WHERE o.user_id = $1::uuid AND o.feature = 'robot_trading'
                   AND o.allowed = false
              ) AS trading_removed
            """,
            str(user_id),
        )
    except Exception:
        logger.exception("entitlement_read_failed")
        return Entitlement(False, "SUBSCRIPTION_UNVERIFIED", "error")
    if not rows:
        return Entitlement(False, "SUBSCRIPTION_INACTIVE", "none")
    row = rows[0]
    if str(row.get("role") or "") in EXEMPT_ROLES:
        return Entitlement(True, "platform_operator", "role")
    if str(row.get("user_status") or "active") in {"suspended", "deactivated"}:
        return Entitlement(False, "ACCOUNT_SUSPENDED", "admin")
    if row.get("trading_removed"):
        return Entitlement(False, "ACCESS_REMOVED_BY_ADMIN", "admin")
    if row.get("licensed"):
        return Entitlement(True, "license_active", "license")
    return Entitlement(False, "SUBSCRIPTION_INACTIVE", "none")
