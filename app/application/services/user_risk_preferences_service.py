"""Per-user risk preferences bounded by owner hard ceilings.

Does not mutate global owner / platform policy. The existing risk engine
remains the final LIVE authority; this service only persists and resolves
customer-editable knobs.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ValidationError
from app.domain.institutional_trading.owner_live_limits import (
    OWNER_DAILY_LOSS_PCT,
    OWNER_MAX_AGGREGATE_OPEN_RISK_PCT,
    OWNER_MAX_LOT,
    OWNER_MAX_OPEN_POSITIONS,
    OWNER_MAX_PLANNED_RISK_PCT,
)
from app.domain.multi_account.effective_risk import (
    RiskSettingProposal,
    default_user_risk_proposal,
    resolve_effective_risk,
)
from app.infrastructure.persistence.direct_postgres import (
    direct_postgres_available,
    execute,
    fetch,
)

_PROTECTION_COPY = (
    {
        "id": "stop_loss",
        "title": "Mandatory stop-loss",
        "detail": "Every new order must include a valid stop-loss. This protection cannot be disabled.",
    },
    {
        "id": "risk_validation",
        "title": "Pre-trade risk validation",
        "detail": "Orders are checked against your effective risk limits before submission.",
    },
    {
        "id": "exposure",
        "title": "Exposure restrictions",
        "detail": "Open risk and concurrent positions are capped so a single account cannot over-extend.",
    },
    {
        "id": "trade_quality",
        "title": "Trade-quality checks",
        "detail": "Low-quality setups are blocked by platform quality gates before they reach the OMS.",
    },
    {
        "id": "position_limits",
        "title": "Position limits",
        "detail": "Your personal concurrent-position preference cannot exceed the platform hard ceiling.",
    },
    {
        "id": "daily_loss",
        "title": "Daily loss protection",
        "detail": "When daily loss usage reaches your effective halt threshold, new entries are blocked.",
    },
    {
        "id": "restricted_strategies",
        "title": "Restricted strategy types",
        "detail": "Grid, martingale, and averaging-down strategies remain disabled for all accounts.",
    },
)


def preference_bounds() -> dict[str, Any]:
    """Customer-facing allowed ranges (ceilings), not the full owner policy document."""
    return {
        "planned_risk_pct": {
            "min": "0.1",
            "max": str(OWNER_MAX_PLANNED_RISK_PCT),
            "unit": "percent",
            "label": "Preferred risk per trade",
            "help": "Share of equity you are willing to risk on a single trade.",
        },
        "aggregate_open_risk_pct": {
            "min": "0.1",
            "max": str(OWNER_MAX_AGGREGATE_OPEN_RISK_PCT),
            "unit": "percent",
            "label": "Aggregate open risk",
            "help": "Total open risk across positions. Must stay at or above risk per trade.",
        },
        "max_lot": {
            "min": "0.01",
            "max": str(OWNER_MAX_LOT),
            "unit": "lots",
            "label": "Personal maximum lot",
            "help": "Hard-capped by the platform maximum lot size.",
        },
        "daily_loss_pct": {
            "min": "0.1",
            "max": str(OWNER_DAILY_LOSS_PCT),
            "unit": "percent",
            "label": "Personal daily loss threshold",
            "help": "Cannot exceed the platform daily-loss halt ceiling.",
        },
        "max_concurrent_positions": {
            "min": 1,
            "max": OWNER_MAX_OPEN_POSITIONS,
            "unit": "count",
            "label": "Personal maximum concurrent positions",
            "help": "Cannot exceed the platform concurrent-position ceiling.",
        },
    }


def protection_status() -> list[dict[str, str]]:
    return [dict(row) for row in _PROTECTION_COPY]


def _row_to_proposal(row: dict[str, Any] | None) -> RiskSettingProposal:
    if not row:
        return default_user_risk_proposal()
    return RiskSettingProposal(
        planned_risk_pct=_as_dec(row.get("planned_risk_pct")),
        aggregate_open_risk_pct=_as_dec(row.get("aggregate_open_risk_pct")),
        max_lot=_as_dec(row.get("max_lot")),
        daily_loss_pct=_as_dec(row.get("daily_loss_pct")),
        max_concurrent_positions=_as_int(row.get("max_concurrent_positions")),
    )


def _as_dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _as_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _serialize_prefs(row: dict[str, Any] | None, *, source: str) -> dict[str, Any]:
    proposal = _row_to_proposal(row)
    effective = resolve_effective_risk(proposal)
    return {
        "preferences": {
            "planned_risk_pct": str(proposal.planned_risk_pct),
            "aggregate_open_risk_pct": str(proposal.aggregate_open_risk_pct),
            "max_lot": str(proposal.max_lot),
            "daily_loss_pct": str(proposal.daily_loss_pct),
            "max_concurrent_positions": proposal.max_concurrent_positions,
        },
        "source": source if row else "default_copy",
        "updated_at": str(row.get("updated_at") or "") if row else None,
        "persisted": bool(row),
        "effective": effective.to_dict(),
        "bounds": preference_bounds(),
        "protections": protection_status(),
    }


def get_user_risk_preferences(user_id: UUID) -> dict[str, Any]:
    row = _load_active_row(user_id)
    source = str((row or {}).get("source") or "default_copy")
    return _serialize_prefs(row, source=source)


def update_user_risk_preferences(
    user_id: UUID,
    *,
    planned_risk_pct: Decimal,
    aggregate_open_risk_pct: Decimal,
    max_lot: Decimal,
    daily_loss_pct: Decimal,
    max_concurrent_positions: int,
) -> dict[str, Any]:
    proposal = RiskSettingProposal(
        planned_risk_pct=planned_risk_pct,
        aggregate_open_risk_pct=aggregate_open_risk_pct,
        max_lot=max_lot,
        daily_loss_pct=daily_loss_pct,
        max_concurrent_positions=max_concurrent_positions,
    )
    effective = resolve_effective_risk(proposal)
    if not effective.ok:
        raise ValidationError(
            "Preference update rejected by hard ceilings",
            code="risk_preference_rejected",
            details={
                "block_reason": effective.block_reason,
                "rejected_fields": list(effective.rejected_fields),
            },
        )

    if not direct_postgres_available():
        raise ValidationError(
            "Preference storage is temporarily unavailable",
            code="risk_preference_storage_unavailable",
        )

    existing = _load_active_row(user_id)
    if existing:
        execute(
            """
            UPDATE public.user_risk_settings
               SET planned_risk_pct = $2,
                   aggregate_open_risk_pct = $3,
                   max_lot = $4,
                   daily_loss_pct = $5,
                   max_concurrent_positions = $6,
                   source = 'user_edit',
                   updated_at = timezone('utc', now())
             WHERE id = $1::uuid
            """,
            str(existing["id"]),
            str(effective.planned_risk_pct),
            str(effective.aggregate_open_risk_pct),
            str(effective.max_lot),
            str(effective.daily_loss_pct),
            int(effective.max_concurrent_positions),
        )
    else:
        execute(
            """
            INSERT INTO public.user_risk_settings (
              user_id,
              planned_risk_pct,
              aggregate_open_risk_pct,
              max_lot,
              daily_loss_pct,
              max_concurrent_positions,
              is_active,
              source
            ) VALUES (
              $1::uuid, $2, $3, $4, $5, $6, true, 'user_edit'
            )
            """,
            str(user_id),
            str(effective.planned_risk_pct),
            str(effective.aggregate_open_risk_pct),
            str(effective.max_lot),
            str(effective.daily_loss_pct),
            int(effective.max_concurrent_positions),
        )

    return get_user_risk_preferences(user_id)


def list_risk_history(user_id: UUID, *, limit: int = 40) -> dict[str, Any]:
    """Best-effort history from audit logs; never fabricates events."""
    if not direct_postgres_available():
        return {"items": [], "available": False, "reason": "storage_unavailable"}
    try:
        rows = fetch(
            """
            SELECT action, outcome, resource_type, message, occurred_at
              FROM public.audit_logs
             WHERE actor_user_id = $1::uuid
               AND (
                    resource_type ILIKE '%risk%'
                 OR resource_type ILIKE '%policy%'
                 OR action ILIKE '%risk%'
                 OR message ILIKE '%risk%'
               )
             ORDER BY occurred_at DESC
             LIMIT $2
            """,
            str(user_id),
            max(1, min(int(limit), 100)),
        )
    except Exception:
        return {"items": [], "available": False, "reason": "query_failed"}
    items = [
        {
            "action": row.get("action"),
            "outcome": row.get("outcome"),
            "resource_type": row.get("resource_type"),
            "message": row.get("message") or "",
            "occurred_at": str(row.get("occurred_at") or ""),
        }
        for row in rows
    ]
    return {"items": items, "available": True, "reason": None}


def assert_own_user(actor_id: UUID, target_user_id: UUID | None) -> None:
    if target_user_id is not None and target_user_id != actor_id:
        raise AuthorizationError(
            "Cannot access another user's risk preferences",
            code="foreign_user_risk_forbidden",
        )


def _load_active_row(user_id: UUID) -> dict[str, Any] | None:
    if not direct_postgres_available():
        return None
    rows = fetch(
        """
        SELECT id, user_id, planned_risk_pct, aggregate_open_risk_pct, max_lot,
               daily_loss_pct, max_concurrent_positions, source, updated_at
          FROM public.user_risk_settings
         WHERE user_id = $1::uuid AND is_active = true
         LIMIT 1
        """,
        str(user_id),
    )
    return rows[0] if rows else None
