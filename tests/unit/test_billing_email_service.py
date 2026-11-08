"""Unit tests for billing email template mapping and provider gate."""

from __future__ import annotations

from app.application.services.billing_email_service import (
    TEMPLATE_SUBJECTS,
    _load_html,
    email_provider_configured,
)
from core.config.settings import Settings


def test_required_template_keys_present() -> None:
    required = {
        "trial_activated",
        "trial_expiring",
        "trial_expired",
        "invoice_created",
        "payment_pending",
        "payment_confirmed",
        "payment_failed",
        "payment_expired",
        "subscription_activated",
        "subscription_upgraded",
        "subscription_downgraded",
        "renewal_reminder",
        "subscription_past_due",
        "subscription_expired",
        "subscription_cancelled",
    }
    assert required.issubset(TEMPLATE_SUBJECTS.keys())


def test_load_html_uses_branded_trial_template() -> None:
    html = _load_html("trial_activated", {"summary": "x"})
    assert "#00D4E0" in html or "00D4E0" in html
    assert "quantforg-mark" in html.lower() or "QuantForg" in html


def test_email_provider_configured_false_without_key() -> None:
    assert email_provider_configured(Settings()) is False
