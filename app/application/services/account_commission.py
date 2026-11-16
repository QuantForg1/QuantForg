"""Owner-verified commission per broker account (for the risk guard).

The risk guard needs the real per-order commission to size risk. It is never
guessed: unknown means the entry is rejected. The owner records a verified
value per account (from the broker's tariff or the account's own deal
history) in ``broker_accounts.metadata.verified_commission``; every change is
audited in the metadata itself (who, when, source).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

ALLOWED_SOURCES = frozenset(
    {"broker_tariff_document", "account_deal_history", "broker_support_confirmation"}
)


def verified_commission_usd(
    *, broker_account_id: UUID, fetch: Any | None = None
) -> Decimal | None:
    """Verified per-order commission in USD, or ``None`` when not verified."""
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
            SELECT metadata->'verified_commission' AS vc
              FROM public.broker_accounts WHERE id = $1::uuid LIMIT 1
            """,
            str(broker_account_id),
        )
    except Exception:
        logger.exception("verified_commission_read_failed")
        return None
    if not rows or not rows[0].get("vc"):
        return None
    vc = rows[0]["vc"]
    if isinstance(vc, str):
        import json

        try:
            vc = json.loads(vc)
        except ValueError:
            return None
    if not isinstance(vc, dict) or vc.get("source") not in ALLOWED_SOURCES:
        return None
    try:
        value = Decimal(str(vc.get("usd_per_order")))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite() or value < 0:
        return None
    return value


def record_verified_commission(
    *,
    broker_account_id: UUID,
    usd_per_order: Decimal,
    source: str,
    evidence: str,
    actor_id: UUID,
    execute: Any | None = None,
) -> dict[str, Any]:
    if source not in ALLOWED_SOURCES:
        raise ValueError(f"source must be one of {sorted(ALLOWED_SOURCES)}")
    if not usd_per_order.is_finite() or usd_per_order < 0:
        raise ValueError("usd_per_order must be a non-negative number")
    if len(evidence.strip()) < 10:
        raise ValueError("evidence must describe where the value was verified")
    if execute is None:
        from app.infrastructure.persistence.direct_postgres import execute as _execute

        execute = _execute
    import json

    payload = {
        "usd_per_order": str(usd_per_order),
        "source": source,
        "evidence": evidence.strip()[:500],
        "verified_by": str(actor_id),
        "verified_at": datetime.now(UTC).isoformat(),
    }
    execute(
        """
        UPDATE public.broker_accounts
           SET metadata = coalesce(metadata, '{}'::jsonb)
                 || jsonb_build_object('verified_commission', $2::jsonb),
               updated_at = now()
         WHERE id = $1::uuid
        """,
        str(broker_account_id),
        json.dumps(payload),
    )
    logger.info(
        "verified_commission_recorded",
        broker_account_id=str(broker_account_id),
        source=source,
    )
    return payload
