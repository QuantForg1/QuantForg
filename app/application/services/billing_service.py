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
from app.domain.billing.plans import get_plan, plans_public
from app.domain.exceptions.base import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationError,
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
    configured = _configured(settings)
    return {
        "configured": configured,
        "provider": "nowpayments" if configured else None,
        "mode": "live" if configured else None,
        "recurring_supported": False,
        "recurring_note": (
            "NOWPayments recurring crypto billing is not enabled for this deployment. "
            "Customers pay via one-time LIVE invoices and renew with a new invoice."
        ),
        "note": (
            "LIVE NOWPayments checkout is configured."
            if configured
            else (
                "NOWPayments LIVE credentials are not configured. Set "
                "NOWPAYMENTS_API_KEY and NOWPAYMENTS_IPN_SECRET on Railway "
                "(production API only — sandbox is forbidden)."
            )
        ),
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
        return NowPaymentsLiveClient(
            api_key=self.settings.nowpayments_api_key.get_secret_value(),
            base_url=self.settings.nowpayments_api_base,
        )

    def list_plans(self) -> dict[str, Any]:
        return {
            "plans": plans_public(),
            "provider": billing_provider_status(self.settings),
            "grace_days": int(self.settings.billing_grace_days),
            "period_days": int(self.settings.billing_period_days),
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
        return {"currencies": currencies, "provider": "nowpayments", "mode": "live"}

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
            return {
                "provider": billing_provider_status(self.settings),
                "license": _row_license(license_row),
                "orders": [_row_order(r) for r in orders],
                "subscription": _derive_subscription(
                    license_row, orders, self.settings
                ),
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
                               amount_usd, plan_id, created_at
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
                    "invoice_url": existing["invoice_url"],
                    "provider": "nowpayments",
                    "mode": "live",
                }

            code = _order_code()
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
                    "Unable to create NOWPayments LIVE invoice",
                    code="NOWPAYMENTS_INVOICE_FAILED",
                    details={"error": str(exc)},
                ) from exc

            invoice_id = str(invoice.get("id") or invoice.get("invoice_id") or "")
            invoice_url = str(invoice.get("invoice_url") or "")
            if not invoice_url:
                raise ServiceUnavailableError(
                    "NOWPayments returned no invoice URL",
                    code="NOWPAYMENTS_INVOICE_INCOMPLETE",
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
                "invoice_url": invoice_url,
                "provider": "nowpayments",
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
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _row_order(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row["id"]) if row.get("id") is not None else None,
        "order_code": row.get("order_code"),
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
        "period_start": _iso(row.get("period_start")),
        "period_end": _iso(row.get("period_end")),
        "paid_at": _iso(row.get("paid_at")),
        "cancelled_at": _iso(row.get("cancelled_at")),
        "expires_at": _iso(row.get("expires_at")),
        "created_at": _iso(row.get("created_at")),
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


def _derive_subscription(
    license_row: Any, orders: Any, settings: Settings
) -> dict[str, Any]:
    active_order = next((o for o in orders if o.get("status") == "active"), None)
    cancelled = next((o for o in orders if o.get("status") == "cancelled"), None)
    pending = next(
        (
            o
            for o in orders
            if o.get("status") in {"pending_payment", "confirming", "partially_paid"}
        ),
        None,
    )
    if active_order is not None:
        return {
            "state": "active",
            "plan_id": active_order.get("plan_id"),
            "period_end": _iso(active_order.get("period_end")),
            "grace_days": int(settings.billing_grace_days),
        }
    if cancelled is not None and cancelled.get("period_end"):
        end = cancelled["period_end"]
        if isinstance(end, datetime) and end > datetime.now(UTC):
            return {
                "state": "cancelled",
                "plan_id": cancelled.get("plan_id"),
                "period_end": _iso(end),
                "grace_days": int(settings.billing_grace_days),
            }
    if pending is not None:
        return {
            "state": "pending_payment",
            "plan_id": pending.get("plan_id"),
            "period_end": None,
            "grace_days": int(settings.billing_grace_days),
        }
    if license_row is not None and str(license_row.get("status")) == "active":
        return {
            "state": "active",
            "plan_id": None,
            "period_end": _iso(license_row.get("expires_at")),
            "grace_days": int(settings.billing_grace_days),
        }
    return {
        "state": "none",
        "plan_id": None,
        "period_end": None,
        "grace_days": int(settings.billing_grace_days),
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
