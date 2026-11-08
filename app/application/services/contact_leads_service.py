"""Persist contact / sales leads with basic abuse controls."""

from __future__ import annotations

import contextlib
import re
from typing import Any

from sqlalchemy import text

from app.domain.exceptions.base import ServiceUnavailableError, ValidationError
from core.logging import get_logger

logger = get_logger(__name__)

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_RATE_LIMIT_PER_HOUR = 5


async def _uow() -> Any:
    from core.di.container import get_container

    factory = getattr(get_container(), "platform_uow_factory", None)
    if factory is None:
        raise ServiceUnavailableError(
            "Contact storage is unavailable",
            code="CONTACT_DB_UNAVAILABLE",
        )
    uow = factory()
    await uow.__aenter__()
    return uow


def _clean(value: str | None, *, max_len: int) -> str:
    return (value or "").strip()[:max_len]


async def create_contact_lead(
    *,
    full_name: str,
    email: str,
    message: str,
    company: str = "",
    country: str = "",
    phone: str = "",
    subject: str = "",
    plan_intent: str = "",
    experience: str = "",
    contact_method: str = "",
    source_ip: str = "",
    user_agent: str = "",
) -> dict[str, Any]:
    name = _clean(full_name, max_len=120)
    mail = _clean(email, max_len=254).lower()
    body = _clean(message, max_len=4000)
    if len(name) < 2:
        raise ValidationError("Name is required", code="CONTACT_NAME_INVALID")
    if not _EMAIL_RE.match(mail):
        raise ValidationError("Email is invalid", code="CONTACT_EMAIL_INVALID")
    if len(body) < 10:
        raise ValidationError(
            "Message must be at least 10 characters",
            code="CONTACT_MESSAGE_INVALID",
        )

    uow = await _uow()
    try:
        session = uow._require_session()
        if source_ip:
            count = (
                await session.execute(
                    text("""
                        SELECT COUNT(*) AS c
                        FROM contact_leads
                        WHERE source_ip = :ip
                          AND created_at > (timezone('utc', now()) - interval '1 hour')
                        """),
                    {"ip": source_ip[:64]},
                )
            ).scalar_one()
            if int(count or 0) >= _RATE_LIMIT_PER_HOUR:
                raise ValidationError(
                    "Too many contact requests. Please try again later.",
                    code="CONTACT_RATE_LIMITED",
                )

        # Soft duplicate: same email + identical message within 24h.
        dup = (
            (
                await session.execute(
                    text("""
                    SELECT id FROM contact_leads
                    WHERE lower(email) = :email
                      AND message = :message
                      AND created_at > (timezone('utc', now()) - interval '24 hours')
                    LIMIT 1
                    """),
                    {"email": mail, "message": body},
                )
            )
            .mappings()
            .first()
        )
        if dup is not None:
            return {
                "stored": True,
                "duplicate": True,
                "id": str(dup["id"]),
                "message": "Your message was already received.",
            }

        result = await session.execute(
            text("""
                INSERT INTO contact_leads (
                  full_name, email, company, country, phone, subject, message,
                  plan_intent, experience, contact_method, source_ip, user_agent
                ) VALUES (
                  :full_name, :email, :company, :country, :phone, :subject, :message,
                  :plan_intent, :experience, :contact_method, :source_ip, :user_agent
                )
                RETURNING id, created_at
                """),
            {
                "full_name": name,
                "email": mail,
                "company": _clean(company, max_len=160),
                "country": _clean(country, max_len=80),
                "phone": _clean(phone, max_len=40),
                "subject": _clean(subject, max_len=160),
                "message": body,
                "plan_intent": _clean(plan_intent, max_len=40),
                "experience": _clean(experience, max_len=80),
                "contact_method": _clean(contact_method, max_len=40),
                "source_ip": _clean(source_ip, max_len=64),
                "user_agent": _clean(user_agent, max_len=300),
            },
        )
        row = result.mappings().first()
        await session.commit()
        logger.info(
            "contact_lead_stored",
            lead_id=str(row["id"]) if row else None,
            email=mail,
            plan_intent=_clean(plan_intent, max_len=40),
        )
        return {
            "stored": True,
            "duplicate": False,
            "id": str(row["id"]) if row else None,
            "message": "Thanks — your message was received.",
        }
    finally:
        with contextlib.suppress(Exception):
            await uow.__aexit__(None, None, None)
