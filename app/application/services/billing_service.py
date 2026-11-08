"""Server-side SaaS billing: NOWPayments LIVE invoices → licenses."""

# SQL strings and structured logs intentionally exceed 88 cols.
# ruff: noqa: E501

from __future__ import annotations

import contextlib
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.domain.billing.nowpayments import (
    FAILED_STATUSES,
    FINISHED_STATUS,
    PENDING_STATUSES,
    NowPaymentsLiveClient,
    verify_ipn_signature,
)
from app.domain.billing.plans import (
    BILLING_DISCLAIMER,
    comparison_public,
    get_plan,
    plan_id_for_license_tier,
    plans_public,
    trial_public,
)
from app.domain.exceptions.base import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
)
from app.domain.identity.designated_owner import (
    DESIGNATED_OWNER_EMAIL,
    is_designated_owner_email,
    normalize_email,
)
from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)


async def _uow() -> Any:
    from core.di.container import get_container

    factory = getattr(get_container(), "platform_uow_factory", None)
    if factory is None:
        raise ServiceUnavailableError(
            "Billing database is unavailable",
            code="BILLING_DB_UNAVAILABLE",
        )
    uow = factory()
    await uow.__aenter__()
    return uow


def _order_code() -> str:
    return f"qf_{datetime.now(UTC).strftime('%Y%m%d')}_{secrets.token_hex(8)}"


def _configured(settings: Settings) -> bool:
    key = (
        settings.nowpayments_api_key.get_secret_value()
        if settings.nowpayments_api_key
        else ""
    )
    secret = (
        settings.nowpayments_ipn_secret.get_secret_value()
        if settings.nowpayments_ipn_secret
        else ""
    )
    return bool(key.strip() and secret.strip())


def billing_provider_status(settings: Settings) -> dict[str, Any]:
    """Customer-safe payment method status. Provider brand stays internal."""
    configured = _configured(settings)
    return {
        "configured": configured,
        "payment_method": "crypto",
        "payment_method_label": "Crypto Payment",
        "mode": "live" if configured else None,
        "recurring_supported": False,
        "recurring_note": (
            "Automatic monthly crypto charging is not enabled. "
            "Customers renew by paying a new invoice before the period ends."
        ),
        "note": (
            "Crypto Payment is available. Paid access activates only after "
            "QuantForg verifies a completed payment — never from a browser redirect alone."
            if configured
            else (
                "Crypto Payment is not configured on the API yet. "
                "Checkout will remain unavailable until production credentials are set."
            )
        ),
        # Internal processor id for operators/logs — UI must not render this label.
        "processor": "nowpayments" if configured else None,
    }


class BillingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self) -> NowPaymentsLiveClient:
        if not _configured(self.settings):
            raise ServiceUnavailableError(
                "NOWPayments LIVE credentials are not configured",
                code="NOWPAYMENTS_NOT_CONFIGURED",
                details={
                    "required": ["NOWPAYMENTS_API_KEY", "NOWPAYMENTS_IPN_SECRET"],
                    "api_host": "https://api.nowpayments.io/v1",
                },
            )
        api_key = self.settings.nowpayments_api_key
        if api_key is None:
            raise ServiceUnavailableError(
                "NOWPayments LIVE credentials are not configured",
                code="NOWPAYMENTS_NOT_CONFIGURED",
                details={"required": ["NOWPAYMENTS_API_KEY"]},
            )
        return NowPaymentsLiveClient(
            api_key=api_key.get_secret_value(),
            base_url=self.settings.nowpayments_api_base,
        )

    def list_plans(self) -> dict[str, Any]:
        days = int(self.settings.billing_trial_days)
        return {
            "plans": plans_public(),
            "trial": trial_public(days=days),
            "comparison": comparison_public(),
            "provider": billing_provider_status(self.settings),
            "grace_days": int(self.settings.billing_grace_days),
            "period_days": int(self.settings.billing_period_days),
            "trial_days": days,
            "payment_method_label": "Crypto Payment",
            "disclaimer": BILLING_DISCLAIMER,
        }

    async def list_plans_with_overrides(self) -> dict[str, Any]:
        """Public plan catalog merged with admin DB overlays when available."""
        from app.domain.billing.plan_overrides import list_plans_merged

        days = int(self.settings.billing_trial_days)
        plans = plans_public()
        uow = await _uow()
        try:
            session = uow._require_session()
            plans = await list_plans_merged(session)
            await uow.rollback()
        except Exception:
            with contextlib.suppress(Exception):
                await uow.rollback()
            plans = plans_public()
        active_plans = [p for p in plans if p.get("active", True) is not False]
        return {
            "plans": active_plans,
            "all_plans": plans,
            "trial": trial_public(days=days),
            "comparison": comparison_public(),
            "provider": billing_provider_status(self.settings),
            "grace_days": int(self.settings.billing_grace_days),
            "period_days": int(self.settings.billing_period_days),
            "trial_days": days,
            "payment_method_label": "Crypto Payment",
            "disclaimer": BILLING_DISCLAIMER,
        }

    def list_currencies(self) -> dict[str, Any]:
        client = self._client()
        try:
            currencies = client.currencies()
        except RuntimeError as exc:
            raise ServiceUnavailableError(
                "Unable to load NOWPayments currencies",
                code="NOWPAYMENTS_CURRENCIES_UNAVAILABLE",
                details={"error": str(exc)},
            ) from exc
        return {
            "currencies": currencies,
            "payment_method": "crypto",
            "payment_method_label": "Crypto Payment",
            "mode": "live",
        }

    async def get_customer_billing(self, *, user_id: UUID) -> dict[str, Any]:
        uow = await _uow()
        try:
            session = uow._require_session()
            license_row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, tier, status, seats, issued_at, expires_at, notes
                        FROM licenses
                        WHERE user_id = :user_id
                        ORDER BY
                          CASE status
                            WHEN 'active' THEN 0
                            WHEN 'pending' THEN 1
                            WHEN 'suspended' THEN 2
                            WHEN 'expired' THEN 3
                            ELSE 4
                          END,
                          COALESCE(expires_at, issued_at) DESC NULLS LAST
                        LIMIT 1
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .first()
            )
            orders = (
                (
                    await session.execute(
                        text("""
                        SELECT id, order_code, plan_id, license_tier, amount_usd, currency,
                               status, provider_status, invoice_url, provider_invoice_id,
                               provider_payment_id, pay_currency, period_start, period_end,
                               paid_at, cancelled_at, expires_at, created_at
                        FROM billing_orders
                        WHERE user_id = :user_id
                        ORDER BY created_at DESC
                        LIMIT 25
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .all()
            )
            trial_row = None
            try:
                trial_row = (
                    (
                        await session.execute(
                            text("""
                            SELECT id, plan_id, status, started_at, expires_at,
                                   converted_at, cancelled_at
                            FROM billing_trials
                            WHERE user_id = :user_id
                            LIMIT 1
                            """),
                            {"user_id": str(user_id)},
                        )
                    )
                    .mappings()
                    .first()
                )
            except Exception:
                # Migration 20261108193000 not applied yet.
                await session.rollback()
                trial_row = None
            trial = await _sync_trial_row(session, trial_row)
            return {
                "provider": billing_provider_status(self.settings),
                "payment_method_label": "Crypto Payment",
                "license": _row_license(license_row),
                "orders": [_row_order(r) for r in orders],
                "invoices": [_row_invoice(r) for r in orders],
                "trial": trial,
                "subscription": _derive_subscription(
                    license_row, orders, self.settings, trial=trial
                ),
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def start_trial(
        self,
        *,
        user_id: UUID,
        email: str,
        email_verified: bool,
        source_ip: str = "",
        claim_fingerprint: str = "",
    ) -> dict[str, Any]:
        if not email_verified:
            raise ValidationError(
                "Verify your email before starting a free trial",
                code="TRIAL_EMAIL_UNVERIFIED",
            )
        email_norm = normalize_email(email)
        if not email_norm or "@" not in email_norm:
            raise ValidationError("Valid email required", code="TRIAL_EMAIL_INVALID")
        days = int(self.settings.billing_trial_days)
        now = datetime.now(UTC)
        expires = now + timedelta(days=days)
        fingerprint = (claim_fingerprint or source_ip or "")[:160]

        uow = await _uow()
        try:
            session = uow._require_session()
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
                {"lock_key": f"trial:{email_norm}:{user_id}"},
            )
            existing = (
                (
                    await session.execute(
                        text("""
                        SELECT id, status, started_at, expires_at
                        FROM billing_trials
                        WHERE user_id = :user_id OR email_norm = :email_norm
                        LIMIT 1
                        """),
                        {"user_id": str(user_id), "email_norm": email_norm},
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                raise ValidationError(
                    "A free trial was already used for this account. "
                    "Choose a paid plan to continue.",
                    code="TRIAL_ALREADY_USED",
                    details={"status": existing.get("status")},
                )
            prior_trial_license = (
                (
                    await session.execute(
                        text("""
                        SELECT id FROM licenses
                        WHERE user_id = :user_id AND tier = 'trial'
                        LIMIT 1
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .first()
            )
            if prior_trial_license is not None:
                raise ValidationError(
                    "A free trial was already used for this account. "
                    "Choose a paid plan to continue.",
                    code="TRIAL_ALREADY_USED",
                    details={"status": "license_history"},
                )

            active_paid = (
                (
                    await session.execute(
                        text("""
                        SELECT id FROM billing_orders
                        WHERE user_id = :user_id AND status = 'active'
                        LIMIT 1
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .first()
            )
            if active_paid is not None:
                raise ValidationError(
                    "An active paid subscription already covers this account",
                    code="TRIAL_PAID_ACTIVE",
                )

            await session.execute(
                text("""
                    INSERT INTO licenses (
                      user_id, tier, status, seats, issued_at, expires_at, notes
                    ) VALUES (
                      :user_id, 'trial', 'active', 1, :issued_at, :expires_at,
                      :notes
                    )
                    """),
                {
                    "user_id": str(user_id),
                    "issued_at": now,
                    "expires_at": expires,
                    "notes": "Starter trial — no payment required; expires automatically",
                },
            )
            lic = (
                (
                    await session.execute(
                        text("""
                        SELECT id FROM licenses
                        WHERE user_id = :user_id AND tier = 'trial'
                        ORDER BY created_at DESC LIMIT 1
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .first()
            )
            try:
                inserted = await session.execute(
                    text("""
                        INSERT INTO billing_trials (
                          user_id, email_norm, plan_id, status, started_at, expires_at,
                          license_id, source_ip
                        ) VALUES (
                          :user_id, :email_norm, 'starter', 'active', :started_at,
                          :expires_at, :license_id, :source_ip
                        )
                        ON CONFLICT (user_id) DO NOTHING
                        RETURNING id
                        """),
                    {
                        "user_id": str(user_id),
                        "email_norm": email_norm,
                        "started_at": now,
                        "expires_at": expires,
                        "license_id": str(lic["id"]) if lic else None,
                        "source_ip": (source_ip or "")[:120],
                    },
                )
                trial_id_row = inserted.mappings().first()
            except Exception as exc:
                raise ValidationError(
                    "A free trial was already used for this account. "
                    "Choose a paid plan to continue.",
                    code="TRIAL_ALREADY_USED",
                    details={"status": "conflict"},
                ) from exc
            if trial_id_row is None:
                raise ValidationError(
                    "A free trial was already used for this account. "
                    "Choose a paid plan to continue.",
                    code="TRIAL_ALREADY_USED",
                    details={"status": "conflict"},
                )
            with contextlib.suppress(Exception):
                await session.execute(
                    text("""
                        UPDATE billing_trials
                        SET claim_fingerprint = :fp
                        WHERE id = :id
                        """),
                    {"fp": fingerprint, "id": str(trial_id_row["id"])},
                )
            await session.execute(
                text("""
                    UPDATE users
                    SET subscription_plan_id = 'starter',
                        subscription_status = 'trial',
                        subscription_expires_at = :expires_at,
                        trial_started_at = :started_at,
                        trial_expires_at = :expires_at,
                        trial_status = 'active',
                        updated_at = timezone('utc', now())
                    WHERE id = :user_id
                    """),
                {
                    "user_id": str(user_id),
                    "started_at": now,
                    "expires_at": expires,
                },
            )
            await session.commit()
            logger.info(
                "billing_trial_started",
                user_id=str(user_id),
                expires_at=expires.isoformat(),
            )
            return {
                "started": True,
                "trial": {
                    "status": "active",
                    "plan_id": "starter",
                    "plan_name": "Starter Trial",
                    "started_at": now.isoformat(),
                    "expires_at": expires.isoformat(),
                    "days_total": days,
                    "days_remaining": days,
                    "payment_required": False,
                },
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def get_invoice(self, *, user_id: UUID, order_code: str) -> dict[str, Any]:
        uow = await _uow()
        try:
            session = uow._require_session()
            row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, order_code, plan_id, license_tier, amount_usd, currency,
                               status, provider_status, invoice_url, provider_invoice_id,
                               provider_payment_id, pay_currency, period_start, period_end,
                               paid_at, cancelled_at, expires_at, created_at
                        FROM billing_orders
                        WHERE user_id = :user_id AND order_code = :order_code
                        LIMIT 1
                        """),
                        {"user_id": str(user_id), "order_code": order_code},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise NotFoundError("Invoice not found", code="INVOICE_NOT_FOUND")
            return {
                "invoice": _row_invoice(row),
                "payment_method_label": "Crypto Payment",
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def create_checkout(
        self,
        *,
        user_id: UUID,
        plan_id: str,
        pay_currency: str | None = None,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> dict[str, Any]:
        plan = get_plan(plan_id)
        if plan is None:
            raise ValidationError(
                "Unknown plan",
                code="UNKNOWN_PLAN",
                details={"plan_id": plan_id},
            )
        client = self._client()
        app_url = (self.settings.public_app_url or "https://www.quantforg.com").rstrip(
            "/"
        )
        api_public = (self.settings.public_api_url or "").rstrip(
            "/"
        ) or "https://quantforg-production.up.railway.app/api/v1"
        ipn_url = f"{api_public}/billing/ipn/nowpayments"
        success = success_url or f"{app_url}/billing/return?status=return"
        cancel = cancel_url or f"{app_url}/billing/return?status=cancel"

        uow = await _uow()
        try:
            session = uow._require_session()
            # Idempotent reuse of a fresh pending invoice for the same plan.
            existing = (
                (
                    await session.execute(
                        text("""
                        SELECT id, order_code, invoice_url, status, provider_invoice_id,
                               amount_usd, plan_id, license_tier, currency, provider_status,
                               provider_payment_id, pay_currency, period_start, period_end,
                               paid_at, cancelled_at, expires_at, created_at
                        FROM billing_orders
                        WHERE user_id = :user_id
                          AND plan_id = :plan_id
                          AND status IN ('pending_payment', 'confirming', 'partially_paid')
                          AND created_at > (timezone('utc', now()) - interval '30 minutes')
                          AND invoice_url IS NOT NULL
                        ORDER BY created_at DESC
                        LIMIT 1
                        """),
                        {"user_id": str(user_id), "plan_id": plan.plan_id},
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None and existing.get("invoice_url"):
                return {
                    "reused": True,
                    "order": _row_order(existing),
                    "invoice": _row_invoice(existing),
                    "invoice_url": existing["invoice_url"],
                    "payment_method": "crypto",
                    "payment_method_label": "Crypto Payment",
                    "mode": "live",
                }

            code = _order_code()
            invoice_number = (
                f"INV-{datetime.now(UTC).strftime('%Y%m%d')}-"
                f"{secrets.token_hex(4).upper()}"
            )
            await session.execute(
                text("""
                    INSERT INTO billing_orders (
                      order_code, user_id, plan_id, license_tier, amount_usd, currency,
                      provider, status
                    ) VALUES (
                      :order_code, :user_id, :plan_id, :license_tier, :amount_usd, 'usd',
                      'nowpayments', 'pending_payment'
                    )
                    """),
                {
                    "order_code": code,
                    "user_id": str(user_id),
                    "plan_id": plan.plan_id,
                    "license_tier": plan.license_tier,
                    "amount_usd": str(plan.amount_usd),
                },
            )
            # Optional column from 20261108193000 — ignore if migration not yet applied.
            with contextlib.suppress(Exception):
                await session.execute(
                    text("""
                        UPDATE billing_orders
                        SET invoice_number = :invoice_number
                        WHERE order_code = :order_code
                        """),
                    {"invoice_number": invoice_number, "order_code": code},
                )
            await session.commit()

            body: dict[str, Any] = {
                "price_amount": float(plan.amount_usd),
                "price_currency": "usd",
                "order_id": code,
                "order_description": f"QuantForg {plan.name} monthly subscription",
                "ipn_callback_url": ipn_url,
                "success_url": success,
                "cancel_url": cancel,
            }
            if pay_currency:
                body["pay_currency"] = pay_currency.strip().lower()

            try:
                invoice = client.create_invoice(body)
            except RuntimeError as exc:
                await session.execute(
                    text("""
                        UPDATE billing_orders
                        SET status = 'payment_failed',
                            provider_status = 'invoice_create_failed',
                            updated_at = timezone('utc', now())
                        WHERE order_code = :order_code
                        """),
                    {"order_code": code},
                )
                await session.commit()
                raise ServiceUnavailableError(
                    "Unable to create Crypto Payment invoice",
                    code="CRYPTO_INVOICE_FAILED",
                    details={"error": str(exc)},
                ) from exc

            invoice_id = str(invoice.get("id") or invoice.get("invoice_id") or "")
            invoice_url = str(invoice.get("invoice_url") or "")
            if not invoice_url:
                raise ServiceUnavailableError(
                    "Crypto Payment did not return an invoice URL",
                    code="CRYPTO_INVOICE_INCOMPLETE",
                )

            await session.execute(
                text("""
                    UPDATE billing_orders
                    SET provider_invoice_id = :invoice_id,
                        invoice_url = :invoice_url,
                        pay_currency = :pay_currency,
                        metadata = CAST(:metadata AS jsonb),
                        updated_at = timezone('utc', now())
                    WHERE order_code = :order_code
                    """),
                {
                    "invoice_id": invoice_id or None,
                    "invoice_url": invoice_url,
                    "pay_currency": body.get("pay_currency"),
                    "metadata": _json_dump(
                        {
                            "invoice_token_id": invoice.get("token_id"),
                            "created_at": invoice.get("created_at"),
                        }
                    ),
                    "order_code": code,
                },
            )
            await session.commit()
            row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, order_code, plan_id, license_tier, amount_usd, currency,
                               status, provider_status, invoice_url, provider_invoice_id,
                               provider_payment_id, pay_currency, period_start, period_end,
                               paid_at, cancelled_at, expires_at, created_at
                        FROM billing_orders WHERE order_code = :order_code
                        """),
                        {"order_code": code},
                    )
                )
                .mappings()
                .first()
            )
            logger.info(
                "billing_invoice_created",
                order_code=code,
                user_id=str(user_id),
                plan_id=plan.plan_id,
                provider_invoice_id=invoice_id,
            )
            return {
                "reused": False,
                "order": _row_order(row),
                "invoice": _row_invoice(row),
                "invoice_url": invoice_url,
                "payment_method": "crypto",
                "payment_method_label": "Crypto Payment",
                "mode": "live",
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def cancel_subscription(self, *, user_id: UUID) -> dict[str, Any]:
        """Mark active paid period as cancelled at period end (no auto-charge)."""
        uow = await _uow()
        try:
            session = uow._require_session()
            row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, order_code, status, period_end
                        FROM billing_orders
                        WHERE user_id = :user_id AND status = 'active'
                        ORDER BY paid_at DESC NULLS LAST
                        LIMIT 1
                        """),
                        {"user_id": str(user_id)},
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise NotFoundError(
                    "No active subscription to cancel",
                    code="NO_ACTIVE_SUBSCRIPTION",
                )
            await session.execute(
                text("""
                    UPDATE billing_orders
                    SET status = 'cancelled',
                        cancelled_at = timezone('utc', now()),
                        updated_at = timezone('utc', now())
                    WHERE id = :id
                    """),
                {"id": str(row["id"])},
            )
            await session.execute(
                text("""
                    UPDATE users
                    SET subscription_status = 'cancelled',
                        updated_at = timezone('utc', now())
                    WHERE id = :user_id
                    """),
                {"user_id": str(user_id)},
            )
            await session.commit()
            return {
                "cancelled": True,
                "order_code": row["order_code"],
                "access_until": (
                    row["period_end"].isoformat() if row.get("period_end") else None
                ),
                "note": "Access remains until the paid period ends unless suspended by an operator.",
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def grant_owner_compensation_premium(
        self,
        *,
        email: str | None = None,
        actor_user_id: UUID | None = None,
        actor_email: str | None = None,
        actor_role: str | None = None,
    ) -> dict[str, Any]:
        """Grant Premium to DESIGNATED_OWNER_EMAIL only (audited)."""
        _ = actor_role
        actor_ok = is_designated_owner_email(actor_email or "")
        email_ok = is_designated_owner_email(email or "")
        if actor_email and not actor_ok and not email_ok:
            raise ValidationError(
                "Only the designated owner may execute this grant",
                code="OWNER_GRANT_FORBIDDEN",
            )
        if email and not email_ok:
            raise ValidationError(
                "Owner compensation applies only to the designated owner email",
                code="OWNER_COMPENSATION_FORBIDDEN",
                details={"expected": DESIGNATED_OWNER_EMAIL},
            )
        plan = get_plan("premium")
        if plan is None:
            raise ServiceUnavailableError(
                "Premium plan is not configured",
                code="PLAN_UNAVAILABLE",
            )
        target_email = DESIGNATED_OWNER_EMAIL
        uow = await _uow()
        try:
            session = uow._require_session()
            user_row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, email, status, auth_user_id
                        FROM users
                        WHERE lower(trim(email)) = :email
                        LIMIT 1
                        """),
                        {"email": target_email},
                    )
                )
                .mappings()
                .first()
            )
            if user_row is None:
                raise NotFoundError(
                    "Designated owner account was not found in trusted user records",
                    code="OWNER_ACCOUNT_NOT_FOUND",
                )
            auth_ok = None
            if user_row.get("auth_user_id") is not None:
                with contextlib.suppress(Exception):
                    auth_row = (
                        (
                            await session.execute(
                                text("""
                                SELECT id, email FROM auth.users
                                WHERE id = :auth_id LIMIT 1
                                """),
                                {"auth_id": str(user_row["auth_user_id"])},
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if auth_row is None:
                        raise ValidationError(
                            "Owner auth identity could not be verified",
                            code="OWNER_AUTH_MISSING",
                        )
                    if normalize_email(auth_row.get("email")) != target_email:
                        raise ValidationError(
                            "Owner auth email does not match designated owner",
                            code="OWNER_AUTH_EMAIL_MISMATCH",
                        )
                    auth_ok = True
            user_id = str(user_row["id"])
            now = datetime.now(UTC)
            period_end = now + timedelta(days=3650)
            notes = f"Premium grant reason=owner_compensation (auth_verified={auth_ok})"
            existing = (
                (
                    await session.execute(
                        text("""
                        SELECT id FROM licenses
                        WHERE user_id = :user_id
                        ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                                 created_at DESC
                        LIMIT 1
                        """),
                        {"user_id": user_id},
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                await session.execute(
                    text("""
                        UPDATE licenses
                        SET tier = :tier, status = 'active', seats = 1,
                            issued_at = COALESCE(issued_at, :issued_at),
                            expires_at = :expires_at, revoked_at = NULL,
                            notes = :notes, updated_at = timezone('utc', now())
                        WHERE id = :id
                        """),
                    {
                        "tier": plan.license_tier,
                        "issued_at": now,
                        "expires_at": period_end,
                        "notes": notes,
                        "id": str(existing["id"]),
                    },
                )
                license_id = str(existing["id"])
            else:
                await session.execute(
                    text("""
                        INSERT INTO licenses (
                          user_id, tier, status, seats, issued_at, expires_at, notes
                        ) VALUES (
                          :user_id, :tier, 'active', 1, :issued_at, :expires_at, :notes
                        )
                        """),
                    {
                        "user_id": user_id,
                        "tier": plan.license_tier,
                        "issued_at": now,
                        "expires_at": period_end,
                        "notes": notes,
                    },
                )
                lic = (
                    (
                        await session.execute(
                            text("""
                            SELECT id FROM licenses
                            WHERE user_id = :user_id AND tier = 'enterprise'
                            ORDER BY created_at DESC LIMIT 1
                            """),
                            {"user_id": user_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                license_id = str(lic["id"]) if lic is not None else ""
            await session.execute(
                text("""
                    UPDATE users
                    SET subscription_plan_id = :plan_id,
                        subscription_status = 'active',
                        subscription_expires_at = :expires_at,
                        subscription_provider = 'owner_compensation',
                        updated_at = timezone('utc', now())
                    WHERE id = :user_id
                    """),
                {
                    "plan_id": plan.plan_id,
                    "expires_at": period_end,
                    "user_id": user_id,
                },
            )
            with contextlib.suppress(Exception):
                await session.execute(
                    text("""
                        INSERT INTO billing_admin_events (
                          actor_user_id, target_user_id, target_email, action, reason,
                          plan_id, license_tier, details
                        ) VALUES (
                          :actor_user_id, :target_user_id, :target_email,
                          'owner_compensation_premium_grant', 'owner_compensation',
                          'premium', 'enterprise', CAST(:details AS jsonb)
                        )
                        """),
                    {
                        "actor_user_id": (
                            str(actor_user_id) if actor_user_id else None
                        ),
                        "target_user_id": user_id,
                        "target_email": target_email,
                        "details": _json_dump(
                            {
                                "license_id": license_id,
                                "auth_verified": auth_ok,
                                "period_end": period_end.isoformat(),
                            }
                        ),
                    },
                )
            await session.commit()
            logger.info(
                "billing_owner_compensation_premium_granted",
                user_id=user_id,
                license_id=license_id,
            )
            return {
                "granted": True,
                "plan_id": plan.plan_id,
                "license_tier": plan.license_tier,
                "reason": "owner_compensation",
                "target_user_id": user_id,
                "license_id": license_id,
                "period_end": period_end.isoformat(),
                "grace_end": period_end.isoformat(),
                "auth_verified": auth_ok,
                "payment_method_label": "Crypto Payment",
                "note": notes,
            }
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def admin_upsert_plan_override(
        self,
        *,
        plan_id: str,
        actor_user_id: UUID,
        actor_email: str | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not is_designated_owner_email(actor_email or ""):
            raise ValidationError(
                "Only the designated owner may edit plan catalog overlays",
                code="OWNER_PLAN_EDIT_FORBIDDEN",
            )
        from app.domain.billing.plan_overrides import upsert_override

        uow = await _uow()
        try:
            session = uow._require_session()
            row = await upsert_override(
                session,
                plan_id=plan_id,
                actor_user_id=actor_user_id,
                payload=payload,
            )
            await session.execute(
                text("""
                    INSERT INTO billing_admin_events (
                      actor_user_id, target_user_id, target_email, action, reason,
                      plan_id, details
                    ) VALUES (
                      :actor, :actor, :email, 'manual_license_adjust',
                      'plan_override_upsert', :plan_id, CAST(:details AS jsonb)
                    )
                    """),
                {
                    "actor": str(actor_user_id),
                    "email": normalize_email(actor_email or DESIGNATED_OWNER_EMAIL),
                    "plan_id": plan_id,
                    "details": __import__("json").dumps({"override": row}, default=str),
                },
            )
            await uow.commit()
            return {"ok": True, "override": row, "fabricated": False}
        except ValueError as exc:
            await uow.rollback()
            raise ValidationError(str(exc), code="UNKNOWN_PLAN") from exc
        except Exception:
            await uow.rollback()
            raise

    async def admin_assign_plan(
        self,
        *,
        target_user_id: UUID,
        plan_id: str,
        days: int,
        actor_user_id: UUID,
        actor_email: str | None,
        reason: str,
    ) -> dict[str, Any]:
        """Owner-only audited license assignment (does not invent payments)."""
        if not is_designated_owner_email(actor_email or ""):
            raise ValidationError(
                "Only the designated owner may assign plans",
                code="OWNER_ASSIGN_FORBIDDEN",
            )
        plan = get_plan(plan_id)
        if plan is None:
            raise ValidationError("Unknown plan", code="UNKNOWN_PLAN")
        days_n = max(1, min(int(days), 3650))
        reason_n = (reason or "").strip()
        if len(reason_n) < 3:
            raise ValidationError("Assignment reason required", code="REASON_REQUIRED")
        uow = await _uow()
        try:
            session = uow._require_session()
            user_row = (
                (
                    await session.execute(
                        text("""
                        SELECT id, email, status FROM users WHERE id = :id LIMIT 1
                        """),
                        {"id": str(target_user_id)},
                    )
                )
                .mappings()
                .first()
            )
            if user_row is None:
                raise NotFoundError("User not found", code="USER_NOT_FOUND")
            now = datetime.now(UTC)
            period_end = now + timedelta(days=days_n)
            notes = f"Admin assign plan={plan.plan_id} reason={reason_n}"
            existing = (
                (
                    await session.execute(
                        text("""
                        SELECT id FROM licenses
                        WHERE user_id = :user_id
                        ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                                 created_at DESC
                        LIMIT 1
                        """),
                        {"user_id": str(target_user_id)},
                    )
                )
                .mappings()
                .first()
            )
            if existing is not None:
                await session.execute(
                    text("""
                        UPDATE licenses
                        SET tier = :tier, status = 'active', seats = 1,
                            issued_at = COALESCE(issued_at, :issued_at),
                            expires_at = :expires_at, revoked_at = NULL,
                            notes = :notes, updated_at = timezone('utc', now())
                        WHERE id = :id
                        """),
                    {
                        "tier": plan.license_tier,
                        "issued_at": now,
                        "expires_at": period_end,
                        "notes": notes,
                        "id": str(existing["id"]),
                    },
                )
                license_id = str(existing["id"])
            else:
                inserted = (
                    (
                        await session.execute(
                            text("""
                            INSERT INTO licenses (
                              user_id, tier, status, seats, issued_at, expires_at, notes
                            ) VALUES (
                              :user_id, :tier, 'active', 1, :issued_at, :expires_at, :notes
                            )
                            RETURNING id
                            """),
                            {
                                "user_id": str(target_user_id),
                                "tier": plan.license_tier,
                                "issued_at": now,
                                "expires_at": period_end,
                                "notes": notes,
                            },
                        )
                    )
                    .mappings()
                    .first()
                )
                license_id = str(inserted["id"]) if inserted else ""
            await session.execute(
                text("""
                    INSERT INTO billing_admin_events (
                      actor_user_id, target_user_id, target_email, action, reason,
                      plan_id, license_tier, details
                    ) VALUES (
                      :actor, :target, :email, 'manual_license_adjust', :reason,
                      :plan_id, :tier, CAST(:details AS jsonb)
                    )
                    """),
                {
                    "actor": str(actor_user_id),
                    "target": str(target_user_id),
                    "email": normalize_email(str(user_row.get("email") or "")),
                    "reason": reason_n,
                    "plan_id": plan.plan_id,
                    "tier": plan.license_tier,
                    "details": __import__("json").dumps(
                        {
                            "license_id": license_id,
                            "days": days_n,
                            "expires_at": period_end.isoformat(),
                            "payment_invented": False,
                        }
                    ),
                },
            )
            await uow.commit()
            return {
                "ok": True,
                "license_id": license_id,
                "plan_id": plan.plan_id,
                "expires_at": period_end.isoformat(),
                "payment_invented": False,
                "fabricated": False,
            }
        except Exception:
            await uow.rollback()
            raise

    async def admin_revenue_snapshot(self) -> dict[str, Any]:
        """MRR/revenue from real billing_orders only (no fabricated totals)."""
        uow = await _uow()
        try:
            session = uow._require_session()
            paid = (
                (
                    await session.execute(
                        text("""
                        SELECT COALESCE(SUM(amount_usd), 0) AS revenue,
                               COUNT(*) AS paid_orders
                        FROM billing_orders
                        WHERE status = 'paid'
                        """)
                    )
                )
                .mappings()
                .first()
            )
            pending = (
                (
                    await session.execute(
                        text("""
                        SELECT COUNT(*) AS pending_orders
                        FROM billing_orders
                        WHERE status IN ('pending_payment', 'confirming', 'partially_paid')
                        """)
                    )
                )
                .mappings()
                .first()
            )
            active_licenses = (
                (
                    await session.execute(
                        text("""
                        SELECT COUNT(*) AS active_licenses
                        FROM licenses WHERE status = 'active'
                        """)
                    )
                )
                .mappings()
                .first()
            )
            recent = (
                (
                    await session.execute(
                        text("""
                        SELECT order_code, plan_id, amount_usd, currency, status,
                               paid_at, created_at, user_id
                        FROM billing_orders
                        ORDER BY created_at DESC
                        LIMIT 40
                        """)
                    )
                )
                .mappings()
                .all()
            )
            await uow.rollback()
            return {
                "revenue_usd_paid": float(paid["revenue"]) if paid else 0.0,
                "paid_orders": int(paid["paid_orders"] or 0) if paid else 0,
                "pending_orders": int(pending["pending_orders"] or 0) if pending else 0,
                "active_licenses": (
                    int(active_licenses["active_licenses"] or 0)
                    if active_licenses
                    else 0
                ),
                "orders": [dict(r) for r in recent],
                "fabricated": False,
                "note": "Totals reflect recorded billing_orders only.",
            }
        except Exception:
            with contextlib.suppress(Exception):
                await uow.rollback()
            raise

    async def reconcile_expired_trials(self, *, limit: int = 200) -> dict[str, Any]:
        """Expire due trials and revoke trial-only licenses (idempotent)."""
        uow = await _uow()
        try:
            session = uow._require_session()
            due = (
                (
                    await session.execute(
                        text("""
                        SELECT id, user_id, license_id
                        FROM billing_trials
                        WHERE status = 'active'
                          AND expires_at <= timezone('utc', now())
                        ORDER BY expires_at ASC
                        LIMIT :limit
                        """),
                        {"limit": max(1, min(int(limit), 500))},
                    )
                )
                .mappings()
                .all()
            )
            expired = 0
            for row in due:
                await session.execute(
                    text("""
                        UPDATE billing_trials
                        SET status = 'expired', updated_at = timezone('utc', now())
                        WHERE id = :id AND status = 'active'
                        """),
                    {"id": str(row["id"])},
                )
                if row.get("license_id") is not None:
                    await session.execute(
                        text("""
                            UPDATE licenses
                            SET status = 'expired', updated_at = timezone('utc', now())
                            WHERE id = :id AND tier = 'trial' AND status = 'active'
                            """),
                        {"id": str(row["license_id"])},
                    )
                await session.execute(
                    text("""
                        UPDATE users
                        SET trial_status = 'expired',
                            subscription_status = CASE
                              WHEN subscription_status = 'trial' THEN 'expired'
                              ELSE subscription_status
                            END,
                            updated_at = timezone('utc', now())
                        WHERE id = :user_id
                        """),
                    {"user_id": str(row["user_id"])},
                )
                expired += 1
            await session.commit()
            return {"ok": True, "expired_count": expired}
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def handle_ipn(
        self,
        *,
        payload: dict[str, Any],
        signature: str,
    ) -> dict[str, Any]:
        secret = (
            self.settings.nowpayments_ipn_secret.get_secret_value()
            if self.settings.nowpayments_ipn_secret
            else ""
        )
        if not secret.strip():
            raise ServiceUnavailableError(
                "NOWPayments IPN secret is not configured",
                code="NOWPAYMENTS_IPN_NOT_CONFIGURED",
            )
        valid = verify_ipn_signature(
            payload=payload, signature=signature, ipn_secret=secret
        )
        payment_status = str(payload.get("payment_status") or "").strip().lower()
        order_code = str(payload.get("order_id") or "").strip()
        payment_id = str(payload.get("payment_id") or payload.get("id") or "").strip()
        event_key = f"{payment_id}:{payment_status}:{payload.get('updated_at') or payload.get('actually_paid_at') or 'na'}"

        uow = await _uow()
        try:
            session = uow._require_session()
            prior = (
                (
                    await session.execute(
                        text("""
                        SELECT id, processed, process_result
                        FROM billing_webhook_events
                        WHERE provider = 'nowpayments' AND event_key = :event_key
                        LIMIT 1
                        """),
                        {"event_key": event_key},
                    )
                )
                .mappings()
                .first()
            )
            if prior is not None and prior.get("processed"):
                return {
                    "ok": True,
                    "duplicate": True,
                    "result": prior.get("process_result") or "already_processed",
                }

            await session.execute(
                text("""
                    INSERT INTO billing_webhook_events (
                      provider, event_key, payment_id, order_code, payment_status,
                      signature_valid, processed, process_result, payload
                    ) VALUES (
                      'nowpayments', :event_key, :payment_id, :order_code, :payment_status,
                      :signature_valid, false, '', CAST(:payload AS jsonb)
                    )
                    ON CONFLICT (provider, event_key) DO NOTHING
                    """),
                {
                    "event_key": event_key,
                    "payment_id": payment_id or None,
                    "order_code": order_code or None,
                    "payment_status": payment_status,
                    "signature_valid": valid,
                    "payload": _json_dump(_safe_ipn_payload(payload)),
                },
            )
            await session.commit()

            if not valid:
                logger.warning(
                    "billing_ipn_invalid_signature",
                    order_code=order_code,
                    payment_id=payment_id,
                )
                await _mark_event(
                    session,
                    event_key=event_key,
                    processed=True,
                    result="invalid_signature",
                )
                await session.commit()
                raise ValidationError(
                    "Invalid NOWPayments IPN signature",
                    code="INVALID_IPN_SIGNATURE",
                )

            if not order_code:
                await _mark_event(
                    session,
                    event_key=event_key,
                    processed=True,
                    result="missing_order_id",
                )
                await session.commit()
                raise ValidationError(
                    "IPN missing order_id",
                    code="IPN_MISSING_ORDER",
                )

            order = (
                (
                    await session.execute(
                        text("""
                        SELECT id, user_id, plan_id, license_tier, amount_usd, currency,
                               status, order_code
                        FROM billing_orders
                        WHERE order_code = :order_code
                        LIMIT 1
                        """),
                        {"order_code": order_code},
                    )
                )
                .mappings()
                .first()
            )
            if order is None:
                await _mark_event(
                    session,
                    event_key=event_key,
                    processed=True,
                    result="order_not_found",
                )
                await session.commit()
                raise NotFoundError(
                    "Billing order not found for IPN",
                    code="BILLING_ORDER_NOT_FOUND",
                )

            expected = Decimal(str(order["amount_usd"]))
            reported = Decimal(str(payload.get("price_amount") or "0"))
            currency = str(payload.get("price_currency") or "").strip().lower()
            if currency and currency != "usd":
                await _mark_event(
                    session,
                    event_key=event_key,
                    processed=True,
                    result="currency_mismatch",
                )
                await session.commit()
                raise ValidationError(
                    "IPN currency mismatch",
                    code="IPN_CURRENCY_MISMATCH",
                    details={"expected": "usd", "got": currency},
                )
            if reported > 0 and abs(reported - expected) > Decimal("0.01"):
                await _mark_event(
                    session,
                    event_key=event_key,
                    processed=True,
                    result="amount_mismatch",
                )
                await session.commit()
                raise ValidationError(
                    "IPN amount mismatch",
                    code="IPN_AMOUNT_MISMATCH",
                    details={
                        "expected": str(expected),
                        "got": str(reported),
                    },
                )

            mapped = _map_provider_status(payment_status)
            await session.execute(
                text("""
                    UPDATE billing_orders
                    SET provider_status = :provider_status,
                        provider_payment_id = COALESCE(:payment_id, provider_payment_id),
                        pay_currency = COALESCE(:pay_currency, pay_currency),
                        status = CASE
                          WHEN :mapped = 'active' THEN status
                          ELSE :mapped
                        END,
                        updated_at = timezone('utc', now())
                    WHERE id = :id
                    """),
                {
                    "provider_status": payment_status,
                    "payment_id": payment_id or None,
                    "pay_currency": str(payload.get("pay_currency") or "") or None,
                    "mapped": mapped if mapped != "active" else order["status"],
                    "id": str(order["id"]),
                },
            )

            result = f"status:{payment_status}"
            if payment_status == FINISHED_STATUS:
                result = await self._fulfill_finished(
                    session,
                    order=order,
                    payment_id=payment_id,
                    pay_currency=str(payload.get("pay_currency") or "") or None,
                )
            elif payment_status in FAILED_STATUSES:
                await session.execute(
                    text("""
                        UPDATE billing_orders
                        SET status = CASE
                              WHEN :ps = 'refunded' THEN 'refunded'
                              WHEN :ps = 'expired' THEN 'expired'
                              ELSE 'payment_failed'
                            END,
                            updated_at = timezone('utc', now())
                        WHERE id = :id AND status <> 'active'
                        """),
                    {"ps": payment_status, "id": str(order["id"])},
                )
                result = f"terminal:{payment_status}"
            elif payment_status in PENDING_STATUSES:
                pending_status = (
                    "partially_paid"
                    if payment_status == "partially_paid"
                    else (
                        "confirming"
                        if payment_status in {"confirming", "confirmed", "sending"}
                        else "pending_payment"
                    )
                )
                await session.execute(
                    text("""
                        UPDATE billing_orders
                        SET status = :st, updated_at = timezone('utc', now())
                        WHERE id = :id AND status NOT IN ('active', 'cancelled', 'refunded')
                        """),
                    {"st": pending_status, "id": str(order["id"])},
                )
                result = f"pending:{payment_status}"

            await _mark_event(
                session, event_key=event_key, processed=True, result=result
            )
            await session.commit()
            logger.info(
                "billing_ipn_processed",
                order_code=order_code,
                payment_id=payment_id,
                payment_status=payment_status,
                result=result,
            )
            return {"ok": True, "duplicate": False, "result": result}
        finally:
            with contextlib.suppress(Exception):
                await uow.__aexit__(None, None, None)

    async def _fulfill_finished(
        self,
        session: Any,
        *,
        order: Any,
        payment_id: str,
        pay_currency: str | None,
    ) -> str:
        """Activate license only after verified finished LIVE payment."""
        if str(order["status"]) == "active":
            return "already_active"
        now = datetime.now(UTC)
        period_end = now + timedelta(days=int(self.settings.billing_period_days))
        grace_end = period_end + timedelta(days=int(self.settings.billing_grace_days))
        user_id = str(order["user_id"])
        tier = str(order["license_tier"])

        await session.execute(
            text("""
                UPDATE billing_orders
                SET status = 'active',
                    provider_status = 'finished',
                    provider_payment_id = COALESCE(:payment_id, provider_payment_id),
                    pay_currency = COALESCE(:pay_currency, pay_currency),
                    paid_at = :paid_at,
                    period_start = :period_start,
                    period_end = :period_end,
                    expires_at = :grace_end,
                    updated_at = timezone('utc', now())
                WHERE id = :id
                """),
            {
                "payment_id": payment_id or None,
                "pay_currency": pay_currency,
                "paid_at": now,
                "period_start": now,
                "period_end": period_end,
                "grace_end": grace_end,
                "id": str(order["id"]),
            },
        )

        existing = (
            (
                await session.execute(
                    text("""
                    SELECT id FROM licenses
                    WHERE user_id = :user_id
                      AND status IN ('active', 'pending', 'expired', 'suspended')
                    ORDER BY
                      CASE status WHEN 'active' THEN 0 ELSE 1 END,
                      created_at DESC
                    LIMIT 1
                    """),
                    {"user_id": user_id},
                )
            )
            .mappings()
            .first()
        )
        notes = f"Activated via NOWPayments LIVE order {order['order_code']}"
        if existing is not None:
            await session.execute(
                text("""
                    UPDATE licenses
                    SET tier = :tier,
                        status = 'active',
                        seats = 1,
                        issued_at = COALESCE(issued_at, :issued_at),
                        expires_at = :expires_at,
                        revoked_at = NULL,
                        notes = :notes,
                        updated_at = timezone('utc', now())
                    WHERE id = :id
                    """),
                {
                    "tier": tier,
                    "issued_at": now,
                    "expires_at": grace_end,
                    "notes": notes,
                    "id": str(existing["id"]),
                },
            )
        else:
            await session.execute(
                text("""
                    INSERT INTO licenses (
                      user_id, tier, status, seats, issued_at, expires_at, notes
                    ) VALUES (
                      :user_id, :tier, 'active', 1, :issued_at, :expires_at, :notes
                    )
                    """),
                {
                    "user_id": user_id,
                    "tier": tier,
                    "issued_at": now,
                    "expires_at": grace_end,
                    "notes": notes,
                },
            )

        await session.execute(
            text("""
                UPDATE users
                SET subscription_plan_id = :plan_id,
                    subscription_status = 'active',
                    subscription_expires_at = :expires_at,
                    subscription_provider = 'nowpayments',
                    updated_at = timezone('utc', now())
                WHERE id = :user_id
                """),
            {
                "plan_id": str(order["plan_id"]),
                "expires_at": grace_end,
                "user_id": user_id,
            },
        )
        await session.execute(
            text("""
                UPDATE billing_trials
                SET status = 'converted',
                    converted_at = COALESCE(converted_at, :now),
                    updated_at = timezone('utc', now())
                WHERE user_id = :user_id
                  AND status IN ('active', 'expired')
                """),
            {"now": now, "user_id": user_id},
        )
        logger.info(
            "billing_entitlement_activated",
            user_id=user_id,
            order_code=str(order["order_code"]),
            license_tier=tier,
            period_end=period_end.isoformat(),
        )
        return "activated"


def _map_provider_status(status: str) -> str:
    if status == FINISHED_STATUS:
        return "active"
    if status == "partially_paid":
        return "partially_paid"
    if status in {"confirming", "confirmed", "sending"}:
        return "confirming"
    if status == "waiting":
        return "pending_payment"
    if status == "expired":
        return "expired"
    if status == "refunded":
        return "refunded"
    if status == "failed":
        return "payment_failed"
    return "pending_payment"


async def _mark_event(
    session: Any, *, event_key: str, processed: bool, result: str
) -> None:
    await session.execute(
        text("""
            UPDATE billing_webhook_events
            SET processed = :processed, process_result = :result
            WHERE provider = 'nowpayments' AND event_key = :event_key
            """),
        {"processed": processed, "result": result, "event_key": event_key},
    )


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        result = isoformat()
        return str(result) if result is not None else None
    return str(value)


def _row_order(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row["id"]) if row.get("id") is not None else None,
        "order_code": row.get("order_code"),
        "invoice_number": row.get("invoice_number") or row.get("order_code"),
        "plan_id": row.get("plan_id"),
        "license_tier": row.get("license_tier"),
        "amount_usd": (
            float(row["amount_usd"]) if row.get("amount_usd") is not None else None
        ),
        "currency": row.get("currency") or "usd",
        "status": row.get("status"),
        "provider_status": row.get("provider_status") or "",
        "invoice_url": row.get("invoice_url"),
        "provider_invoice_id": row.get("provider_invoice_id"),
        "provider_payment_id": row.get("provider_payment_id"),
        "pay_currency": row.get("pay_currency"),
        "payment_method_label": "Crypto Payment",
        "period_start": _iso(row.get("period_start")),
        "period_end": _iso(row.get("period_end")),
        "paid_at": _iso(row.get("paid_at")),
        "cancelled_at": _iso(row.get("cancelled_at")),
        "expires_at": _iso(row.get("expires_at")),
        "created_at": _iso(row.get("created_at")),
    }


def _row_invoice(row: Any) -> dict[str, Any] | None:
    """Customer invoice projection (no processor brand)."""
    base = _row_order(row)
    if base is None:
        return None
    status = str(base.get("status") or "")
    display = {
        "pending_payment": "Awaiting payment",
        "confirming": "Confirming",
        "partially_paid": "Partially paid",
        "active": "Paid",
        "renewal_due": "Renewal due",
        "past_due": "Past due",
        "payment_failed": "Failed",
        "cancelled": "Cancelled",
        "expired": "Expired",
        "suspended": "Suspended",
        "refunded": "Refunded",
    }.get(status, status.replace("_", " ").title() or "Unknown")
    return {
        **base,
        "status_label": display,
        "payment_method_label": "Crypto Payment",
    }


async def _sync_trial_row(session: Any, trial_row: Any) -> dict[str, Any] | None:
    if trial_row is None:
        return None
    status = str(trial_row.get("status") or "")
    expires = trial_row.get("expires_at")
    now = datetime.now(UTC)
    if status == "active" and isinstance(expires, datetime) and expires <= now:
        await session.execute(
            text("""
                UPDATE billing_trials
                SET status = 'expired', updated_at = timezone('utc', now())
                WHERE id = :id AND status = 'active'
                """),
            {"id": str(trial_row["id"])},
        )
        await session.execute(
            text("""
                UPDATE licenses
                SET status = 'expired', updated_at = timezone('utc', now())
                WHERE id = (
                  SELECT license_id FROM billing_trials WHERE id = :id
                )
                AND status = 'active' AND tier = 'trial'
                """),
            {"id": str(trial_row["id"])},
        )
        await session.execute(
            text("""
                UPDATE users
                SET trial_status = 'expired',
                    subscription_status = CASE
                      WHEN subscription_status = 'trial' THEN 'expired'
                      ELSE subscription_status
                    END,
                    updated_at = timezone('utc', now())
                WHERE id = (
                  SELECT user_id FROM billing_trials WHERE id = :id
                )
                """),
            {"id": str(trial_row["id"])},
        )
        await session.commit()
        status = "expired"
    days_remaining = 0
    if isinstance(expires, datetime) and status == "active":
        days_remaining = max(0, int((expires - now).total_seconds() // 86400))
    return {
        "status": status,
        "plan_id": trial_row.get("plan_id") or "starter",
        "plan_name": "Starter Trial",
        "started_at": _iso(trial_row.get("started_at")),
        "expires_at": _iso(expires),
        "days_remaining": days_remaining,
        "payment_required": False,
    }


def _row_license(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row["id"]),
        "tier": row.get("tier"),
        "status": row.get("status"),
        "seats": row.get("seats"),
        "issued_at": _iso(row.get("issued_at")),
        "expires_at": _iso(row.get("expires_at")),
        "notes": row.get("notes") or "",
    }


def _plan_name(plan_id: str | None) -> str | None:
    if not plan_id:
        return None
    plan = get_plan(str(plan_id))
    return plan.name if plan else str(plan_id).replace("_", " ").title()


def _derive_subscription(
    license_row: Any,
    orders: Any,
    settings: Settings,
    *,
    trial: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_order = next((o for o in orders if o.get("status") == "active"), None)
    cancelled = next((o for o in orders if o.get("status") == "cancelled"), None)
    failed = next(
        (
            o
            for o in orders
            if o.get("status") in {"payment_failed", "expired", "suspended"}
        ),
        None,
    )
    pending = next(
        (
            o
            for o in orders
            if o.get("status") in {"pending_payment", "confirming", "partially_paid"}
        ),
        None,
    )
    grace = int(settings.billing_grace_days)
    base = {
        "payment_method_label": "Crypto Payment",
        "billing_frequency": "Monthly invoice (no automatic crypto charge)",
        "grace_days": grace,
        "renewal_instructions": (
            "Before your period ends, open Subscription or Invoices and pay a new "
            "Crypto Payment invoice for your plan. Access renews only after verified payment."
        ),
    }
    if active_order is not None:
        period_end = active_order.get("period_end")
        return {
            **base,
            "state": "active",
            "subscription_type": "paid",
            "plan_id": active_order.get("plan_id"),
            "plan_name": _plan_name(active_order.get("plan_id")),
            "activated_at": _iso(active_order.get("paid_at")),
            "period_start": _iso(active_order.get("period_start")),
            "period_end": _iso(period_end),
            "next_renewal_due": _iso(period_end),
            "grace_ends_at": _iso(active_order.get("expires_at")),
            "invoice_url": active_order.get("invoice_url"),
            "order_code": active_order.get("order_code"),
        }
    if cancelled is not None and cancelled.get("period_end"):
        end = cancelled["period_end"]
        if isinstance(end, datetime) and end > datetime.now(UTC):
            return {
                **base,
                "state": "cancelled",
                "subscription_type": "paid",
                "plan_id": cancelled.get("plan_id"),
                "plan_name": _plan_name(cancelled.get("plan_id")),
                "period_end": _iso(end),
                "grace_ends_at": _iso(cancelled.get("expires_at")),
                "access_until": _iso(end),
            }
    if pending is not None:
        return {
            **base,
            "state": "pending_payment",
            "subscription_type": "paid_pending",
            "plan_id": pending.get("plan_id"),
            "plan_name": _plan_name(pending.get("plan_id")),
            "period_end": None,
            "invoice_url": pending.get("invoice_url"),
            "order_code": pending.get("order_code"),
        }
    if trial and trial.get("status") == "active":
        return {
            **base,
            "state": "trial",
            "subscription_type": "trial",
            "plan_id": "starter",
            "plan_name": "Starter Trial",
            "activated_at": trial.get("started_at"),
            "trial_started_at": trial.get("started_at"),
            "trial_expires_at": trial.get("expires_at"),
            "period_end": trial.get("expires_at"),
            "days_remaining": trial.get("days_remaining"),
            "trial": True,
        }
    if trial and trial.get("status") == "expired":
        return {
            **base,
            "state": "trial_expired",
            "subscription_type": "trial",
            "plan_id": "starter",
            "plan_name": "Starter Trial",
            "trial_started_at": trial.get("started_at"),
            "trial_expires_at": trial.get("expires_at"),
            "period_end": trial.get("expires_at"),
        }
    if license_row is not None and str(license_row.get("status")) == "active":
        tier = str(license_row.get("tier") or "")
        plan_id = plan_id_for_license_tier(tier)
        return {
            **base,
            "state": "trial" if tier == "trial" else "active",
            "subscription_type": "trial" if tier == "trial" else "paid",
            "plan_id": plan_id,
            "plan_name": ("Starter Trial" if tier == "trial" else _plan_name(plan_id)),
            "activated_at": _iso(license_row.get("issued_at")),
            "period_end": _iso(license_row.get("expires_at")),
            "next_renewal_due": _iso(license_row.get("expires_at")),
        }
    if failed is not None:
        return {
            **base,
            "state": str(failed.get("status") or "payment_failed"),
            "subscription_type": "paid_pending",
            "plan_id": failed.get("plan_id"),
            "plan_name": _plan_name(failed.get("plan_id")),
            "period_end": _iso(failed.get("period_end")),
            "order_code": failed.get("order_code"),
            "invoice_url": failed.get("invoice_url"),
        }
    return {
        **base,
        "state": "none",
        "subscription_type": None,
        "plan_id": None,
        "plan_name": None,
        "period_end": None,
    }


def _safe_ipn_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist IPN fields without oversized blobs."""
    keep = {
        "payment_id",
        "payment_status",
        "pay_address",
        "price_amount",
        "price_currency",
        "pay_amount",
        "actually_paid",
        "pay_currency",
        "order_id",
        "order_description",
        "purchase_id",
        "outcome_amount",
        "outcome_currency",
        "network",
        "updated_at",
        "created_at",
    }
    return {k: payload.get(k) for k in keep if k in payload}


def _json_dump(value: dict[str, Any]) -> str:
    import json

    return json.dumps(value, default=str)
