"""Customer-facing billing labels must not expose processor branding."""

from __future__ import annotations

from app.application.services.billing_service import billing_provider_status
from core.config.settings import Settings


def test_provider_status_uses_crypto_payment_label() -> None:
    status = billing_provider_status(Settings())
    assert status["payment_method_label"] == "Crypto Payment"
    assert status["payment_method"] == "crypto"
    assert "NOWPayments" not in str(status.get("note") or "")
    assert "NOWPayments" not in str(status.get("recurring_note") or "")


def test_provider_status_unconfigured_has_no_processor() -> None:
    status = billing_provider_status(Settings())
    assert status["configured"] is False
    assert status["processor"] is None
    assert status["payment_method_label"] == "Crypto Payment"
