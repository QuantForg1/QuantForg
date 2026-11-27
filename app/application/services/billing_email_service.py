"""Transactional billing email queue + optional Resend delivery.

Delivery requires ``RESEND_API_KEY`` (and optional ``BILLING_EMAIL_FROM``).
Without a provider key, notifications stay queued / marked skipped — never
falsely reported as delivered.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)

_TEMPLATE_ROOT = (
    Path(__file__).resolve().parents[3] / "docs" / "auth" / "email-templates"
)

TEMPLATE_SUBJECTS: dict[str, str] = {
    "trial_activated": "Your QuantForg Starter trial is active",
    "trial_expiring": "Your QuantForg trial ends soon",
    "trial_expired": "Your QuantForg trial has ended",
    "invoice_created": "Your QuantForg invoice is ready",
    "payment_pending": "QuantForg payment pending",
    "payment_confirmed": "QuantForg payment confirmed",
    "payment_failed": "QuantForg payment failed",
    "payment_expired": "QuantForg payment expired",
    "subscription_activated": "Your QuantForg subscription is active",
    "subscription_upgraded": "Your QuantForg plan was upgraded",
    "subscription_downgraded": "Your QuantForg plan was changed",
    "renewal_reminder": "QuantForg subscription renewal reminder",
    "subscription_past_due": "QuantForg subscription past due",
    "subscription_expired": "Your QuantForg subscription expired",
    "subscription_cancelled": "Your QuantForg subscription was cancelled",
}

# Map logical keys → on-disk HTML (when a dedicated file exists).
_TEMPLATE_FILES: dict[str, str] = {
    "trial_activated": "trial-activated.html",
    "trial_expiring": "trial-expiring.html",
    "trial_expired": "trial-expired.html",
    "invoice_created": "invoice-created.html",
    "payment_confirmed": "payment-received.html",
    "payment_failed": "payment-failed.html",
    "subscription_activated": "subscription-activated.html",
    "renewal_reminder": "subscription-renewal-reminder.html",
    "subscription_past_due": "subscription-past-due.html",
    "subscription_expired": "subscription-expired.html",
    "subscription_cancelled": "subscription-cancelled.html",
}


async def _uow() -> Any:
    from core.di.container import get_container

    factory = getattr(get_container(), "platform_uow_factory", None)
    if factory is None:
        raise RuntimeError("Billing email DB unavailable")
    uow = factory()
    await uow.__aenter__()
    return uow


def _fallback_html(template_key: str, payload: dict[str, Any]) -> str:
    """Minimal branded HTML when on-disk templates are unavailable."""
    title = TEMPLATE_SUBJECTS.get(template_key, "QuantForg billing update")
    detail = str(payload.get("summary") or "See Settings → Subscription for details.")
    return (
        '<!DOCTYPE html><html><body style="background:#111827;color:#F3F4F6;'
        'font-family:IBM Plex Sans,Segoe UI,Helvetica,Arial,sans-serif;padding:32px">'
        f'<div style="max-width:600px;margin:0 auto;background:#151B23;'
        f'border:1px solid #202938;border-radius:12px;padding:28px">'
        f'<h1 style="color:#F3F4F6;font-size:20px">{title}</h1>'
        f'<p style="color:#9CA3AF;line-height:1.6">{detail}</p>'
        '<p style="margin-top:24px"><a href="https://www.quantforg.com/settings" '
        'style="color:#00D4E0">Open Subscription settings</a></p>'
        "</div></body></html>"
    )


def _load_html(template_key: str, payload: dict[str, Any]) -> str:
    filename = _TEMPLATE_FILES.get(template_key)
    if not filename:
        return _fallback_html(template_key, payload)
    path = _TEMPLATE_ROOT / filename
    try:
        html = path.read_text(encoding="utf-8")
    except OSError:
        logger.warning(
            "billing_email_template_missing",
            template_key=template_key,
            path=str(path),
        )
        return _fallback_html(template_key, payload)
    # Safe substitutions only for known non-secret placeholders in product templates.
    for key, value in payload.items():
        if key.startswith("_"):
            continue
        token = "{{" + key + "}}"
        if token in html:
            html = html.replace(token, str(value))
    return html


def email_provider_configured(settings: Settings) -> bool:
    key = settings.resend_api_key.get_secret_value() if settings.resend_api_key else ""
    return bool(key.strip())


async def queue_billing_email(
    *,
    user_id: UUID | str,
    email_norm: str,
    template_key: str,
    dedupe_key: str,
    related_order_id: str | None = None,
    related_trial_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> bool:
    """Insert a queued notification. Returns False if duplicate (idempotent)."""
    if template_key not in TEMPLATE_SUBJECTS:
        logger.warning("billing_email_unknown_template", template_key=template_key)
        return False
    email = (email_norm or "").strip().lower()
    if not email or "@" not in email:
        logger.warning("billing_email_missing_recipient", template_key=template_key)
        return False
    uow = await _uow()
    try:
        session = uow._require_session()
        result = await session.execute(
            text("""
                INSERT INTO billing_email_notifications (
                  user_id, email_norm, template_key, dedupe_key,
                  related_order_id, related_trial_id, status, payload
                ) VALUES (
                  :user_id, :email_norm, :template_key, :dedupe_key,
                  :related_order_id, :related_trial_id, 'queued',
                  CAST(:payload AS jsonb)
                )
                ON CONFLICT (dedupe_key) DO NOTHING
                RETURNING id
                """),
            {
                "user_id": str(user_id),
                "email_norm": email,
                "template_key": template_key,
                "dedupe_key": dedupe_key[:200],
                "related_order_id": related_order_id,
                "related_trial_id": related_trial_id,
                "payload": json.dumps(payload or {}),
            },
        )
        row = result.mappings().first()
        await session.commit()
        return row is not None
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


async def _send_resend(
    *,
    settings: Settings,
    to_email: str,
    subject: str,
    html: str,
) -> str:
    api_key = (
        settings.resend_api_key.get_secret_value() if settings.resend_api_key else ""
    )
    if not api_key.strip():
        raise RuntimeError("RESEND_API_KEY not configured")
    from_addr = (
        settings.billing_email_from or ""
    ).strip() or "QuantForg <noreply@quantforg.com>"
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_addr,
                "to": [to_email],
                "subject": subject,
                "html": html,
            },
        )
    if resp.status_code >= 400:
        # Never log the API key; body may include provider error detail only.
        raise RuntimeError(f"Resend rejected send ({resp.status_code})")
    data = resp.json() if resp.content else {}
    message_id = str(data.get("id") or "").strip()
    if not message_id:
        raise RuntimeError("Resend accepted but returned no message id")
    return message_id


async def process_billing_email_queue(
    settings: Settings,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    """Drain queued notifications. Marks skipped when no provider is configured."""
    provider_ok = email_provider_configured(settings)
    uow = await _uow()
    sent = failed = skipped = 0
    try:
        session = uow._require_session()
        rows = (
            (
                await session.execute(
                    text("""
                        SELECT id, user_id, email_norm, template_key, payload, status
                        FROM billing_email_notifications
                        WHERE status = 'queued'
                        ORDER BY created_at ASC
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                        """),
                    {"limit": max(1, min(int(limit), 200))},
                )
            )
            .mappings()
            .all()
        )
        for row in rows:
            nid = str(row["id"])
            template_key = str(row["template_key"])
            to_email = str(row["email_norm"])
            raw_payload = row.get("payload") or {}
            if isinstance(raw_payload, str):
                with contextlib.suppress(Exception):
                    raw_payload = json.loads(raw_payload)
            payload = raw_payload if isinstance(raw_payload, dict) else {}

            if not provider_ok:
                await session.execute(
                    text("""
                        UPDATE billing_email_notifications
                        SET status = 'skipped',
                            error_detail = 'email_provider_not_configured'
                        WHERE id = :id AND status = 'queued'
                        """),
                    {"id": nid},
                )
                skipped += 1
                continue

            try:
                html = _load_html(template_key, payload)
                subject = str(
                    payload.get("_subject")
                    or TEMPLATE_SUBJECTS.get(template_key, "QuantForg billing update")
                )
                message_id = await _send_resend(
                    settings=settings,
                    to_email=to_email,
                    subject=subject,
                    html=html,
                )
                await session.execute(
                    text("""
                        UPDATE billing_email_notifications
                        SET status = 'sent',
                            provider_message_id = :mid,
                            error_detail = '',
                            sent_at = :sent_at
                        WHERE id = :id AND status = 'queued'
                        """),
                    {
                        "id": nid,
                        "mid": message_id[:120],
                        "sent_at": datetime.now(UTC),
                    },
                )
                sent += 1
            except Exception as exc:
                await session.execute(
                    text("""
                        UPDATE billing_email_notifications
                        SET status = 'failed',
                            error_detail = :err
                        WHERE id = :id AND status = 'queued'
                        """),
                    {"id": nid, "err": str(exc)[:400]},
                )
                failed += 1
                logger.warning(
                    "billing_email_send_failed",
                    notification_id=nid,
                    template_key=template_key,
                )
        await session.commit()
        return {
            "ok": True,
            "provider_configured": provider_ok,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "processed": sent + failed + skipped,
        }
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)


async def queue_trial_expiring_reminders(*, within_hours: int = 48) -> int:
    """Queue trial-ending-soon emails for active trials nearing expiry."""
    uow = await _uow()
    queued = 0
    try:
        session = uow._require_session()
        rows = (
            (
                await session.execute(
                    text("""
                        SELECT t.id, t.user_id, t.email_norm, t.expires_at
                        FROM billing_trials t
                        WHERE t.status = 'active'
                          AND t.expires_at > timezone('utc', now())
                          AND t.expires_at <= timezone('utc', now())
                               + make_interval(hours => :hours)
                        """),
                    {"hours": max(1, min(int(within_hours), 168))},
                )
            )
            .mappings()
            .all()
        )
        await session.commit()
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)

    for row in rows:
        ok = await queue_billing_email(
            user_id=str(row["user_id"]),
            email_norm=str(row["email_norm"]),
            template_key="trial_expiring",
            dedupe_key=f"trial_expiring:{row['id']}",
            related_trial_id=str(row["id"]),
            payload={
                "summary": "Your Starter trial ends within 48 hours. "
                "Upgrade via Crypto Payment to keep access."
            },
        )
        if ok:
            queued += 1
    return queued


_RENEWAL_STAGES_DAYS = (7, 3, 1)
_SITE = "https://www.quantforg.com"
_KNOWN_PLANS = {"starter", "professional", "premium"}


def _renewal_cta_url(tier: object) -> str:
    plan = str(tier or "").strip().lower()
    if plan not in _KNOWN_PLANS:
        plan = "professional"
    return f"{_SITE}/billing/checkout?plan={plan}"


def _renewal_stage(*, period_end: Any, now: Any) -> int | None:
    """Return 7, 3 or 1 (days before period end), 0 once in grace, or None."""
    left = period_end - now
    if left.total_seconds() <= 0:
        return 0
    days = left.total_seconds() / 86400.0
    if days > _RENEWAL_STAGES_DAYS[0]:
        return None
    for stage in sorted(_RENEWAL_STAGES_DAYS):
        if days <= stage:
            return stage
    return None


async def queue_renewal_reminders(
    *, within_hours: int | None = None, grace_days: int = 2
) -> int:
    """Queue renewal reminders 7, 3 and 1 day(s) before the paid period ends.

    Crypto payments do not auto-renew: the customer pays a new invoice before
    the period ends. ``licenses.expires_at`` already includes the grace period,
    so the period end is ``expires_at - grace_days``. Once the period has ended
    (customer is in grace) one "past due" notice states when access stops.
    One email per license, period end and stage (idempotent via dedupe key).
    """
    from datetime import UTC, datetime, timedelta

    grace = max(0, int(grace_days))
    window_h = (
        int(within_hours)
        if within_hours is not None
        else (_RENEWAL_STAGES_DAYS[0] * 24)
    )
    window_h = max(1, min(window_h, 336))
    uow = await _uow()
    queued = 0
    try:
        session = uow._require_session()
        rows = (
            (
                await session.execute(
                    text("""
                        SELECT l.id, l.user_id, lower(u.email) AS email_norm,
                               l.expires_at, l.tier
                        FROM licenses l
                        JOIN users u ON u.id = l.user_id
                        WHERE l.status = 'active'
                          AND l.expires_at IS NOT NULL
                          AND l.expires_at > timezone('utc', now())
                          AND l.expires_at <= timezone('utc', now())
                               + make_interval(hours => :hours)
                          AND lower(coalesce(l.tier::text, '')) <> 'trial'
                          AND lower(coalesce(u.role::text, ''))
                              NOT IN ('owner', 'admin')
                        """),
                    {"hours": window_h + grace * 24},
                )
            )
            .mappings()
            .all()
        )
        await session.commit()
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)

    now = datetime.now(UTC)
    for row in rows:
        expires = row["expires_at"]
        period_end = expires - timedelta(days=grace)
        stage = _renewal_stage(period_end=period_end, now=now)
        if stage is None:
            continue
        cta = _renewal_cta_url(row.get("tier"))
        end_s = period_end.date().isoformat()
        stop_s = expires.date().isoformat()
        if stage == 0:
            template_key = "subscription_past_due"
            subject = "Action needed: your QuantForg subscription period has ended"
            summary = (
                f"Your subscription period ended on {end_s}. You are in a "
                f"{grace}-day grace period: the robot keeps working until "
                f"{stop_s} UTC. Pay a new Crypto Payment invoice before then to "
                "avoid interruption. Automated trading access stops after the "
                "grace period."
            )
        else:
            template_key = "renewal_reminder"
            plural = "" if stage == 1 else "s"
            subject = f"Your QuantForg subscription ends in {stage} day{plural}"
            summary = (
                f"Your QuantForg subscription period ends on {end_s} UTC "
                f"(about {stage} day{plural} from now). Pay a new Crypto "
                f"Payment invoice before then to keep the robot running. "
                f"Automatic crypto charging is not enabled, and a "
                f"{grace}-day grace period follows the end date."
            )
        ok = await queue_billing_email(
            user_id=str(row["user_id"]),
            email_norm=str(row["email_norm"] or ""),
            template_key=template_key,
            dedupe_key=f"{template_key}:{row['id']}:{end_s}:{stage}",
            payload={"summary": summary, "cta_url": cta, "_subject": subject},
        )
        if ok:
            queued += 1
    return queued
