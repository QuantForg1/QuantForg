"""Canonical SaaS plan catalog (server-side source of truth)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class BillingPlan:
    plan_id: str
    license_tier: str
    name: str
    amount_usd: Decimal
    positioning: str


BILLING_PLANS: dict[str, BillingPlan] = {
    "starter": BillingPlan(
        plan_id="starter",
        license_tier="starter",
        name="Starter",
        amount_usd=Decimal("49.00"),
        positioning="Entry-level access for customers exploring the platform.",
    ),
    "professional": BillingPlan(
        plan_id="professional",
        license_tier="professional",
        name="Professional",
        amount_usd=Decimal("99.00"),
        positioning=(
            "Advanced access for customers who need more platform functionality."
        ),
    ),
    "premium": BillingPlan(
        plan_id="premium",
        license_tier="enterprise",
        name="Premium",
        amount_usd=Decimal("199.00"),
        positioning="Higher-tier platform access and enhanced support.",
    ),
}


def get_plan(plan_id: str) -> BillingPlan | None:
    return BILLING_PLANS.get((plan_id or "").strip().lower())


def plans_public() -> list[dict[str, object]]:
    return [
        {
            "id": p.plan_id,
            "license_tier": p.license_tier,
            "name": p.name,
            "monthly_price_usd": float(p.amount_usd),
            "positioning": p.positioning,
        }
        for p in BILLING_PLANS.values()
    ]
