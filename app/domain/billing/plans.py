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
        positioning="Essential QuantForg workspace for individual operators.",
        entitlements=(
            "Essential QuantForg workspace",
            "Core market research and chart access",
            "Standard strategy access",
            "Broker connection workflows",
            "Core automated trading (eligibility and risk checks apply)",
            "Standard portfolio and position visibility",
            "Standard risk controls (never bypassed by plan)",
            "Email support",
        ),
    ),
    "professional": BillingPlan(
        plan_id="professional",
        license_tier="professional",
        name="Professional",
        amount_usd=Decimal("99.00"),
        positioning="Expanded tools for active professional desks.",
        entitlements=(
            "Everything in Starter",
            "Expanded strategy and research tools",
            "Advanced analytics surfaces",
            "Portfolio and performance workspaces",
            "Enhanced trading insights and monitoring",
            "Priority product support",
            "Professional operator features",
        ),
    ),
    "premium": BillingPlan(
        plan_id="premium",
        license_tier="enterprise",
        name="Premium",
        amount_usd=Decimal("199.00"),
        positioning="Full eligible platform access with enhanced support.",
        entitlements=(
            "Everything in Professional",
            "Full eligible platform feature access",
            "Advanced research and strategy tools",
            "Enhanced analytics and reporting",
            "Advanced monitoring and account management",
            "Priority support",
            "Premium onboarding assistance",
            "Advanced license management",
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
        "feature": "Dashboard & workspace",
        "trial": "Included",
        "starter": "Essential",
        "professional": "Full",
        "premium": "Full",
    },
    {
        "feature": "Market research & charts",
        "trial": "Included",
        "starter": "Core",
        "professional": "Expanded",
        "premium": "Advanced",
    },
    {
        "feature": "Strategy & signal exploration",
        "trial": "Exploration",
        "starter": "Standard",
        "professional": "Expanded",
        "premium": "Advanced",
    },
    {
        "feature": "Broker connection workflows",
        "trial": "Guided intro",
        "starter": "Included",
        "professional": "Included",
        "premium": "Included",
    },
    {
        "feature": "Automated trading access",
        "trial": "Controlled intro",
        "starter": "Core (risk-gated)",
        "professional": "Enhanced (risk-gated)",
        "premium": "Full eligible (risk-gated)",
    },
    {
        "feature": "Portfolio & positions",
        "trial": "Basic",
        "starter": "Standard",
        "professional": "Full workspace",
        "premium": "Advanced",
    },
    {
        "feature": "Risk controls",
        "trial": "Essential visibility",
        "starter": "Standard (enforced)",
        "professional": "Standard (enforced)",
        "premium": "Standard (enforced)",
    },
    {
        "feature": "Analytics & monitoring",
        "trial": "Limited",
        "starter": "Core",
        "professional": "Advanced",
        "premium": "Enhanced",
    },
    {
        "feature": "Support",
        "trial": "Limited",
        "starter": "Email",
        "professional": "Priority",
        "premium": "Priority + onboarding",
    },
    {
        "feature": "License management",
        "trial": "Trial license",
        "starter": "Standard",
        "professional": "Standard",
        "premium": "Advanced",
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
