"""Referral reward: 30 subscription days for the referrer.

Runs inside the payment-confirmation transaction (``_fulfill_finished``),
in a savepoint, so a referral problem can never block or roll back a
customer's paid activation.

Rules (owner decision 2026-11-20: "1 free month"):

* Qualifies only when a referred customer's **first** paid order is
  confirmed, and only if the referral was attributed **before** that payment.
* One reward per referred customer, ever (unique index in the database).
* The referrer's active subscription is extended by 30 days immediately.
  If the referrer has no active subscription, the reward stays ``pending``
  and is added to the referrer's next confirmed payment.
* No cash, no payout, no price change.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)

REWARD_KIND = "free_month"
REWARD_DAYS = 30


async def _scalar(session: Any, sql: str, params: dict[str, Any]) -> Any:
    row = (await session.execute(text(sql), params)).first()
    return None if row is None else row[0]


async def _active_license(session: Any, user_id: str, now: datetime) -> Any:
    return (
        (
            await session.execute(
                text("""
                    SELECT id, expires_at FROM licenses
                    WHERE user_id = :user_id AND status = 'active'
                      AND tier <> 'trial'
                      AND (expires_at IS NULL OR expires_at > :now)
                    ORDER BY expires_at DESC NULLS FIRST
                    LIMIT 1
                    """),
                {"user_id": user_id, "now": now},
            )
        )
        .mappings()
        .first()
    )


async def _extend(session: Any, *, user_id: str, license_row: Any, days: int) -> None:
    if license_row["expires_at"] is None:
        return  # non-expiring licence: nothing to extend
    new_expiry = license_row["expires_at"] + timedelta(days=days)
    await session.execute(
        text("""
            UPDATE licenses SET expires_at = :expires_at,
                updated_at = timezone('utc', now())
            WHERE id = :id
            """),
        {"expires_at": new_expiry, "id": str(license_row["id"])},
    )
    await session.execute(
        text("""
            UPDATE users SET subscription_expires_at = :expires_at,
                updated_at = timezone('utc', now())
            WHERE id = :user_id
            """),
        {"expires_at": new_expiry, "user_id": user_id},
    )


async def _mark_applied(
    session: Any, event_key: str, license_id: str, now: datetime
) -> None:
    await session.execute(
        text("""
            UPDATE referral_events
            SET reward_status = 'applied', applied_at = :now,
                applied_license_id = :license_id
            WHERE event_key = :key AND reward_status = 'pending'
            """),
        {"now": now, "license_id": license_id, "key": event_key},
    )


async def _issue_for_referred(
    session: Any, *, user_id: str, order_id: str, now: datetime
) -> str:
    """The paying customer was referred: create the referrer's reward."""
    attribution = (
        (
            await session.execute(
                text("""
                    SELECT referrer_user_id, created_at FROM referral_attributions
                    WHERE referred_user_id = :user_id
                    """),
                {"user_id": user_id},
            )
        )
        .mappings()
        .first()
    )
    if attribution is None:
        return "no_attribution"
    if attribution["created_at"] is not None and attribution["created_at"] > now:
        return "attributed_after_payment"
    earlier_paid = await _scalar(
        session,
        """
        SELECT count(*) FROM billing_orders
        WHERE user_id = :user_id AND paid_at IS NOT NULL AND id <> :order_id
        """,
        {"user_id": user_id, "order_id": order_id},
    )
    if int(earlier_paid or 0) > 0:
        return "not_first_payment"
    referrer = str(attribution["referrer_user_id"])
    if referrer == user_id:
        return "self_referral"
    key = f"paid_order:{order_id}"
    inserted = await _scalar(
        session,
        """
        INSERT INTO referral_events (
          event_key, event_type, referred_user_id, beneficiary_user_id,
          reward_kind, reward_days, reward_status
        ) VALUES (
          :key, 'paid_invoice', :referred, :referrer, :kind, :days, 'pending'
        )
        ON CONFLICT DO NOTHING
        RETURNING event_key
        """,
        {
            "key": key,
            "referred": user_id,
            "referrer": referrer,
            "kind": REWARD_KIND,
            "days": REWARD_DAYS,
        },
    )
    if inserted is None:
        return "already_rewarded"
    lic = await _active_license(session, referrer, now)
    if lic is None or lic["expires_at"] is None:
        return "pending_until_referrer_pays"
    await _extend(session, user_id=referrer, license_row=lic, days=REWARD_DAYS)
    await _mark_applied(session, key, str(lic["id"]), now)
    return "applied_to_referrer"


async def _redeem_pending(session: Any, *, user_id: str, now: datetime) -> int:
    """The paying customer is a referrer with pending rewards: add them now."""
    rows = (
        (
            await session.execute(
                text("""
                    SELECT event_key, reward_days FROM referral_events
                    WHERE beneficiary_user_id = :user_id AND reward_status = 'pending'
                    ORDER BY created_at
                    FOR UPDATE
                    """),
                {"user_id": user_id},
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        return 0
    lic = await _active_license(session, user_id, now)
    if lic is None or lic["expires_at"] is None:
        return 0
    days = sum(int(r["reward_days"] or 0) for r in rows)
    await _extend(session, user_id=user_id, license_row=lic, days=days)
    for r in rows:
        await _mark_applied(session, str(r["event_key"]), str(lic["id"]), now)
    return len(rows)


async def apply_referral_rewards(
    session: Any, *, user_id: str, order_id: str, now: datetime
) -> dict[str, Any]:
    """Best effort; never raises into the payment flow."""
    try:
        async with session.begin_nested():
            issued = await _issue_for_referred(
                session, user_id=user_id, order_id=order_id, now=now
            )
            redeemed = await _redeem_pending(session, user_id=user_id, now=now)
    except Exception as exc:  # referral tables missing or any DB error
        logger.warning(
            "referral_reward_skipped",
            user_id=user_id,
            order_id=order_id,
            error=str(exc),
        )
        return {"issued": "error", "redeemed": 0}
    if issued not in {"no_attribution"} or redeemed:
        logger.info(
            "referral_reward",
            user_id=user_id,
            order_id=order_id,
            issued=issued,
            redeemed=redeemed,
        )
    return {"issued": issued, "redeemed": redeemed}
