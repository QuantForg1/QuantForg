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


def _fake_env(monkeypatch, bes, rows):
    from types import SimpleNamespace

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
    return sent


def _row(expires, tier="starter"):
    from uuid import uuid4

    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "email_norm": "a@x.io",
        "expires_at": expires,
        "tier": tier,
    }


@pytest.mark.asyncio
async def test_renewal_reminder_stages_and_grace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    from app.application.services import billing_email_service as bes

    now = datetime.now(UTC)
    grace = 2
    # period ends in 6d -> stage 7; 2.5d -> stage 3; 0.5d -> stage 1; ended -> grace
    cases = {
        "7": now + timedelta(days=6 + grace),
        "3": now + timedelta(days=2, hours=12 + grace * 24),
        "1": now + timedelta(hours=12 + grace * 24),
        "0": now + timedelta(hours=24),  # period ended 1d ago, still in grace
        "far": now + timedelta(days=20 + grace),
    }
    rows = [_row(v, tier="premium") for v in cases.values()]
    sent = _fake_env(monkeypatch, bes, rows)
    assert await bes.queue_renewal_reminders(grace_days=grace) == 4
    assert await bes.queue_renewal_reminders(grace_days=grace) == 0  # idempotent
    keys = sorted(str(k["dedupe_key"]).rsplit(":", 1)[1] for k in sent)
    assert keys == ["0", "1", "3", "7"]
    templates = {
        str(k["dedupe_key"]).rsplit(":", 1)[1]: k["template_key"] for k in sent
    }
    assert templates["0"] == "subscription_past_due"
    assert templates["7"] == "renewal_reminder"
    payload = sent[0]["payload"]
    assert payload["cta_url"].endswith("/billing/checkout?plan=premium")
    assert "_subject" in payload


def test_renewal_cta_defaults_to_professional() -> None:
    from app.application.services.billing_email_service import _renewal_cta_url

    assert _renewal_cta_url("weird").endswith("plan=professional")
    assert _renewal_cta_url("Starter").endswith("plan=starter")
