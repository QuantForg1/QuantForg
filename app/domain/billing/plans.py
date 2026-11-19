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
    entitlements: tuple[str, ...]


BILLING_PLANS: dict[str, BillingPlan] = {
    "starter": BillingPlan(
        plan_id="starter",
        license_tier="starter",
        name="Starter",
        amount_usd=Decimal("49.00"),
        positioning="For individual traders starting with automated trading.",
        entitlements=(
            "QuantForg dashboard",
            "Live market data and chart access",
            "Core strategies and signals",
            "1 verified broker account",
            "1 active robot",
            "Essential analytics and portfolio visibility",
            "Standard risk management (your own risk profile)",
            "Standard email support",
            "Subscription-controlled LIVE execution",
        ),
    ),
    "professional": BillingPlan(
        plan_id="professional",
        license_tier="professional",
        name="Professional",
        amount_usd=Decimal("99.00"),
        positioning="For active traders who need expanded trading intelligence.",
        entitlements=(
            "Everything in Starter",
            "Expanded strategy access",
            "Advanced analytics and performance reports",
            "Enhanced market and risk monitoring",
            "Advanced portfolio workspace",
            "Priority support",
        ),
    ),
    "premium": BillingPlan(
        plan_id="premium",
        license_tier="enterprise",
        name="Premium",
        amount_usd=Decimal("199.00"),
        positioning="For advanced operators who want every eligible tool.",
        entitlements=(
            "Everything in Professional",
            "Full eligible strategy access",
            "Advanced analytics and reporting",
            "Enhanced account and execution monitoring",
            "Advanced license management",
            "Premium onboarding",
            "Priority support",
        ),
    ),
}

TRIAL_FEATURES: tuple[str, ...] = (
    "Access to QuantForg dashboard",
    "Live market research and chart access",
    "Strategy and signal exploration",
    "Controlled introduction to automated trading",
    "Auto-trading only via approved broker and risk configurations",
    "Basic portfolio and position visibility",
    "Essential risk visibility",
    "Limited research and support",
)

PLAN_COMPARISON_ROWS: tuple[dict[str, str], ...] = (
    {
        "feature": "Account, broker connection & verification",
        "unpaid": "Included",
        "starter": "Included",
        "professional": "Included",
        "premium": "Included",
    },
    {
        "feature": "Balance, equity & broker details",
        "unpaid": "Included",
        "starter": "Included",
        "professional": "Included",
        "premium": "Included",
    },
    {
        "feature": "Start the robot / automated trading",
        "unpaid": "Subscription required",
        "starter": "Included",
        "professional": "Included",
        "premium": "Included",
    },
    {
        "feature": "Verified broker accounts",
        "unpaid": "1 (view only)",
        "starter": "1",
        "professional": "1",
        "premium": "1",
    },
    {
        "feature": "Strategies & signals",
        "unpaid": "View",
        "starter": "Core",
        "professional": "Expanded",
        "premium": "Full eligible",
    },
    {
        "feature": "Analytics & reports",
        "unpaid": "Basic",
        "starter": "Essential",
        "professional": "Advanced",
        "premium": "Advanced + reporting",
    },
    {
        "feature": "Risk controls",
        "unpaid": "Your risk profile",
        "starter": "Enforced",
        "professional": "Enforced",
        "premium": "Enforced",
    },
    {
        "feature": "Support",
        "unpaid": "Help center",
        "starter": "Email",
        "professional": "Priority",
        "premium": "Priority + onboarding",
    },
)

BILLING_DISCLAIMER = (
    "Subscriptions grant software access only. Trading execution remains "
    "subject to existing risk, Quality, OMS, broker, and owner safeguards. "
    "A subscription never bypasses risk controls or guarantees trades."
)

_PLAN_ID_ALIASES: dict[str, str] = {
    "enterprise": "premium",
}


def get_plan(plan_id: str) -> BillingPlan | None:
    normalized = (plan_id or "").strip().lower()
    normalized = _PLAN_ID_ALIASES.get(normalized, normalized)
    return BILLING_PLANS.get(normalized)


def plan_id_for_license_tier(tier: str | None) -> str | None:
    mapping = {
        "trial": "starter",
        "starter": "starter",
        "professional": "professional",
        "enterprise": "premium",
    }
    return mapping.get((tier or "").strip().lower())


def plans_public() -> list[dict[str, object]]:
    return [
        {
            "id": p.plan_id,
            "license_tier": p.license_tier,
            "name": p.name,
            "monthly_price_usd": float(p.amount_usd),
            "positioning": p.positioning,
            "entitlements": list(p.entitlements),
        }
        for p in BILLING_PLANS.values()
    ]


def trial_public(*, days: int) -> dict[str, object]:
    return {
        "id": "trial",
        "plan_id": "starter",
        "name": "Free Trial",
        "days": days,
        "monthly_price_usd": 0,
        "payment_required": False,
        "positioning": (
            f"{days}-day Starter access without payment details. "
            "One claim per customer. Does not auto-convert to a paid plan."
        ),
        "entitlements": list(TRIAL_FEATURES),
        "expires_behavior": (
            "When the trial ends, trial-only entitlements are revoked. "
            "Your account, profile, invoices, and history are preserved. "
            "Choose a paid plan to continue — you will not be charged automatically."
        ),
    }


def comparison_public() -> list[dict[str, str]]:
    return [dict(row) for row in PLAN_COMPARISON_ROWS]
