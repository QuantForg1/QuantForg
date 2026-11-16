"""Unit tests for billing email template mapping and provider gate."""

from __future__ import annotations

import pytest

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


def test_load_html_falls_back_when_template_file_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    import app.application.services.billing_email_service as mod

    monkeypatch.setattr(mod, "_TEMPLATE_ROOT", Path("/nonexistent/email-templates"))
    html = _load_html("trial_activated", {"summary": "fallback path"})
    assert "fallback path" in html
    assert "#00D4E0" in html or "00D4E0" in html
    assert "QuantForg" in html


@pytest.mark.asyncio
async def test_renewal_reminders_are_queued_once_per_period(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta
    from types import SimpleNamespace
    from uuid import uuid4

    from app.application.services import billing_email_service as bes

    expires = datetime.now(UTC) + timedelta(hours=30)
    rows = [
        {
            "id": uuid4(),
            "user_id": uuid4(),
            "email_norm": "a@x.io",
            "expires_at": expires,
        }
    ]

    class _Res:
        def mappings(self):
            return SimpleNamespace(all=lambda: rows)

    class _Session:
        async def execute(self, *_a, **_k):
            return _Res()

        async def commit(self) -> None:
            return None

    class _Uow:
        def _require_session(self) -> _Session:
            return _Session()

        async def __aexit__(self, *_a: object) -> None:
            return None

    async def _uow() -> _Uow:
        return _Uow()

    sent: list[dict[str, object]] = []

    async def _queue(**kw: object) -> bool:
        if any(k["dedupe_key"] == kw["dedupe_key"] for k in sent):
            return False
        sent.append(kw)
        return True

    monkeypatch.setattr(bes, "_uow", _uow)
    monkeypatch.setattr(bes, "queue_billing_email", _queue)
    assert await bes.queue_renewal_reminders() == 1
    assert await bes.queue_renewal_reminders() == 0  # idempotent
    assert sent[0]["template_key"] == "renewal_reminder"
