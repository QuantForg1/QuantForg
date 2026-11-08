"""Billing catalog, trial labels, and subscription derivation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.services.billing_service import _derive_subscription
from app.domain.billing.plans import get_plan, plans_public
from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from core.config.settings import Settings


@pytest.mark.unit
def test_plans_monthly_prices_match_catalog() -> None:
    public = {p["id"]: p for p in plans_public()}
    assert float(public["starter"]["monthly_price_usd"]) == 49.0
    assert float(public["professional"]["monthly_price_usd"]) == 99.0
    assert float(public["premium"]["monthly_price_usd"]) == 199.0
    assert get_plan("starter") is not None
    assert get_plan("premium") is not None
    assert get_plan("premium").license_tier == "enterprise"


@pytest.mark.unit
def test_trial_catalog_default_days() -> None:
    settings = Settings()
    assert int(settings.billing_trial_days) == 7


@pytest.mark.unit
def test_designated_owner_email_constant() -> None:
    assert DESIGNATED_OWNER_EMAIL == "p7provider@gmail.com"


@pytest.mark.unit
def test_get_plan_enterprise_alias_maps_to_premium() -> None:
    plan = get_plan("enterprise")
    assert plan is not None
    assert plan.plan_id == "premium"
    assert plan.license_tier == "enterprise"


@pytest.mark.unit
def test_derive_subscription_prefers_paid_over_trial() -> None:
    settings = Settings()
    now = datetime.now(UTC)
    active_order = {
        "status": "active",
        "plan_id": "professional",
        "period_start": now,
        "period_end": now + timedelta(days=30),
    }
    trial = {
        "status": "active",
        "expires_at": (now + timedelta(days=5)).isoformat(),
        "days_remaining": 5,
    }
    sub = _derive_subscription(None, [active_order], settings, trial=trial)
    assert sub["state"] == "active"
    assert sub["plan_id"] == "professional"


@pytest.mark.unit
def test_derive_subscription_trial_expired() -> None:
    settings = Settings()
    trial = {
        "status": "expired",
        "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    }
    sub = _derive_subscription(None, [], settings, trial=trial)
    assert sub["state"] == "trial_expired"
    assert sub["plan_id"] == "starter"
    assert sub["payment_method_label"] == "Crypto Payment"
