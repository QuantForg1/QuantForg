"""DB overlays for SaaS plan catalog (prices / active / intervals)."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.billing.plans import BILLING_PLANS, BillingPlan, get_plan, plans_public

ALLOWED_PLAN_IDS = frozenset(BILLING_PLANS.keys())


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


async def fetch_overrides(session: Any) -> dict[str, dict[str, Any]]:
    try:
        rows = (
            (
                await session.execute(
                    text("""
                    SELECT plan_id, active, monthly_price_usd, annual_price_usd,
                           billing_interval, trial_days, positioning, entitlements,
                           grace_period_days, updated_at, updated_by
                    FROM billing_plan_overrides
                    """)
                )
            )
            .mappings()
            .all()
        )
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        pid = str(row.get("plan_id") or "")
        if pid in ALLOWED_PLAN_IDS:
            out[pid] = dict(row)
    return out


def merge_plan_public(
    base: dict[str, object],
    override: dict[str, Any] | None,
) -> dict[str, object]:
    merged = dict(base)
    if not override:
        merged.setdefault("active", True)
        merged.setdefault("billing_interval", "monthly")
        return merged
    if override.get("active") is not None:
        merged["active"] = bool(override["active"])
    monthly = _dec(override.get("monthly_price_usd"))
    if monthly is not None:
        merged["monthly_price_usd"] = float(monthly)
    annual = _dec(override.get("annual_price_usd"))
    if annual is not None:
        merged["annual_price_usd"] = float(annual)
    elif monthly is not None:
        merged["annual_price_usd"] = float(
            (monthly * Decimal("10")).quantize(Decimal("0.01"))
        )
    interval = str(override.get("billing_interval") or "monthly")
    if interval in {"monthly", "annual", "both"}:
        merged["billing_interval"] = interval
    if override.get("trial_days") is not None:
        merged["trial_days"] = int(override["trial_days"])
    if override.get("positioning"):
        merged["positioning"] = str(override["positioning"])
    ents = override.get("entitlements")
    if isinstance(ents, list) and ents:
        merged["entitlements"] = [str(x) for x in ents]
    if override.get("grace_period_days") is not None:
        merged["grace_period_days"] = int(override["grace_period_days"])
    updated = override.get("updated_at")
    if updated is not None and hasattr(updated, "isoformat"):
        merged["override_updated_at"] = updated.isoformat()
    elif updated is not None:
        merged["override_updated_at"] = updated
    return merged


async def list_plans_merged(session: Any | None) -> list[dict[str, object]]:
    base = plans_public()
    overrides: dict[str, dict[str, Any]] = {}
    if session is not None:
        overrides = await fetch_overrides(session)
    return [merge_plan_public(p, overrides.get(str(p["id"]))) for p in base]


def resolve_plan_amount(
    plan: BillingPlan,
    override: dict[str, Any] | None,
    *,
    interval: str = "monthly",
) -> Decimal:
    if override:
        if interval == "annual":
            annual = _dec(override.get("annual_price_usd"))
            if annual is not None:
                return annual
            monthly = _dec(override.get("monthly_price_usd"))
            if monthly is not None:
                return (monthly * Decimal("10")).quantize(Decimal("0.01"))
        monthly = _dec(override.get("monthly_price_usd"))
        if monthly is not None:
            return monthly
    if interval == "annual":
        return (plan.amount_usd * Decimal("10")).quantize(Decimal("0.01"))
    return plan.amount_usd


async def upsert_override(
    session: Any,
    *,
    plan_id: str,
    actor_user_id: UUID | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    pid = (plan_id or "").strip().lower()
    if pid not in ALLOWED_PLAN_IDS or get_plan(pid) is None:
        raise ValueError("unknown_plan")

    existing = (
        (
            await session.execute(
                text("""
                SELECT plan_id, active, monthly_price_usd, annual_price_usd,
                       billing_interval, trial_days, positioning, entitlements,
                       grace_period_days
                FROM billing_plan_overrides WHERE plan_id = :plan_id
                """),
                {"plan_id": pid},
            )
        )
        .mappings()
        .first()
    )
    current = dict(existing) if existing else {}

    active = (
        bool(payload["active"])
        if "active" in payload and payload["active"] is not None
        else bool(current.get("active", True))
    )
    monthly = _dec(payload.get("monthly_price_usd"))
    if monthly is None:
        monthly = _dec(current.get("monthly_price_usd"))
    annual = _dec(payload.get("annual_price_usd"))
    if annual is None:
        annual = _dec(current.get("annual_price_usd"))
    interval = str(
        payload.get("billing_interval") or current.get("billing_interval") or "both"
    )
    if interval not in {"monthly", "annual", "both"}:
        interval = "both"
    trial_days = payload.get("trial_days", current.get("trial_days"))
    grace = payload.get("grace_period_days", current.get("grace_period_days", 3))
    positioning = payload.get("positioning", current.get("positioning"))
    entitlements = payload.get("entitlements", current.get("entitlements"))

    await session.execute(
        text("""
            INSERT INTO billing_plan_overrides (
              plan_id, active, monthly_price_usd, annual_price_usd,
              billing_interval, trial_days, positioning, entitlements,
              grace_period_days, updated_by, updated_at
            ) VALUES (
              :plan_id, :active, :monthly, :annual,
              :interval, :trial_days, :positioning, CAST(:entitlements AS jsonb),
              :grace, :updated_by, timezone('utc', now())
            )
            ON CONFLICT (plan_id) DO UPDATE SET
              active = EXCLUDED.active,
              monthly_price_usd = EXCLUDED.monthly_price_usd,
              annual_price_usd = EXCLUDED.annual_price_usd,
              billing_interval = EXCLUDED.billing_interval,
              trial_days = EXCLUDED.trial_days,
              positioning = EXCLUDED.positioning,
              entitlements = EXCLUDED.entitlements,
              grace_period_days = EXCLUDED.grace_period_days,
              updated_by = EXCLUDED.updated_by,
              updated_at = timezone('utc', now())
            """),
        {
            "plan_id": pid,
            "active": active,
            "monthly": str(monthly) if monthly is not None else None,
            "annual": str(annual) if annual is not None else None,
            "interval": interval,
            "trial_days": int(trial_days) if trial_days is not None else None,
            "positioning": str(positioning) if positioning else None,
            "entitlements": (
                json.dumps(entitlements) if isinstance(entitlements, list) else None
            ),
            "grace": int(grace) if grace is not None else 3,
            "updated_by": str(actor_user_id) if actor_user_id else None,
        },
    )
    row = (
        (
            await session.execute(
                text("""
                SELECT plan_id, active, monthly_price_usd, annual_price_usd,
                       billing_interval, trial_days, positioning, entitlements,
                       grace_period_days, updated_at
                FROM billing_plan_overrides WHERE plan_id = :plan_id
                """),
                {"plan_id": pid},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else {"plan_id": pid}
