"""Server-side entitlement check for automated trading.

A customer may start or resume a robot, and a multi-account worker may send
an entry, only while the customer holds an active license (paid) or an
active trial. Owner/admin accounts are exempt (they operate the platform).
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
              ) AS trial
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
    if row.get("licensed"):
        return Entitlement(True, "license_active", "license")
    if row.get("trial"):
        return Entitlement(True, "trial_active", "trial")
    return Entitlement(False, "SUBSCRIPTION_INACTIVE", "none")
