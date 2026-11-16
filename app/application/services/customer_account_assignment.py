"""Automatic assignment of customer broker accounts to free worker slots.

A customer who connects an MT5 account in Broker Accounts gets the next free
isolated slot on the existing Windows host, oldest connection first. Only
accounts with active vault credentials qualify. An account already bound to a
worker is never assigned twice. When every slot is busy the account waits
(queued) — slots are never shared and capacity is never exceeded.

The environment filter comes from QF_AUTO_ASSIGN_ENVIRONMENTS (default
"demo"): LIVE multi-account submit is disabled, so LIVE accounts are only
assigned when the owner explicitly widens it for read-only verification.
"""

from __future__ import annotations

import os
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)


def allowed_environments() -> tuple[str, ...]:
    raw = os.environ.get("QF_AUTO_ASSIGN_ENVIRONMENTS", "demo")
    envs = tuple(e.strip().lower() for e in raw.split(",") if e.strip())
    return tuple(e for e in envs if e in {"demo", "live"})


def next_unassigned_account(
    *,
    taken_account_ids: set[str],
    fetch: Any | None = None,
    taken_user_ids: set[str] | None = None,
) -> tuple[UUID, UUID] | None:
    """(user_id, broker_account_id) of the oldest eligible unbound account.

    One active worker per user (the provisioner enforces it): an account whose
    owner already has a worker waits until that worker is released, instead
    of being handed to a slot that would alias the existing worker.
    """
    envs = allowed_environments()
    if not envs:
        return None
    if fetch is None:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch as _fetch,
        )

        if not direct_postgres_available():
            return None
        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT a.id, a.user_id
              FROM public.broker_accounts a
             WHERE lower(a.status) = 'active'
               AND lower(a.environment) = ANY($1::text[])
               AND EXISTS (
                     SELECT 1 FROM public.broker_credentials c
                      WHERE c.broker_account_id = a.id
                        AND lower(c.credential_type) = 'password'
                        AND coalesce(lower(c.status), 'active') = 'active')
             ORDER BY a.created_at
             LIMIT 200
            """,
            list(envs),
        )
    except Exception:
        logger.exception("auto_assign_query_failed")
        return None
    busy_users = taken_user_ids or set()
    for r in rows:
        if str(r["id"]) in taken_account_ids or str(r["user_id"]) in busy_users:
            continue
        return UUID(str(r["user_id"])), UUID(str(r["id"]))
    return None


def queue_depth(*, taken_account_ids: set[str], fetch: Any | None = None) -> int:
    """Eligible accounts still waiting for a slot (for capacity monitoring)."""
    count = 0
    seen = set(taken_account_ids)
    while True:
        nxt = next_unassigned_account(
            taken_account_ids=seen, fetch=fetch, taken_user_ids=set()
        )
        if nxt is None:
            return count
        seen.add(str(nxt[1]))
        count += 1
        if count > 200:
            return count
