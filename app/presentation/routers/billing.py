"""Customer billing API + NOWPayments LIVE IPN webhook."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from app.application.dto.auth import AuthUserDTO
from app.application.services.billing_service import BillingService
from app.domain.enums.user import UserRole
from app.domain.exceptions.base import ValidationError
from app.domain.identity.designated_owner import is_designated_owner_email
from app.presentation.dependencies.auth import CurrentUser, require_roles
from core.config.settings import Settings, get_settings

router = APIRouter(prefix="/billing", tags=["billing"])


def get_billing_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> BillingService:
    return BillingService(settings)


BillingSvc = Annotated[BillingService, Depends(get_billing_service)]


class CheckoutRequest(BaseModel):
    plan_id: str = Field(min_length=3, max_length=40)
    pay_currency: str | None = Field(default=None, max_length=32)
    success_url: str | None = Field(default=None, max_length=500)
    cancel_url: str | None = Field(default=None, max_length=500)


@router.get("/plans")
async def billing_plans(svc: BillingSvc) -> dict[str, Any]:
    return svc.list_plans()


@router.get("/provider")
async def billing_provider(svc: BillingSvc) -> dict[str, Any]:
    from app.application.services.billing_service import billing_provider_status

    return billing_provider_status(svc.settings)


@router.get("/currencies")
async def billing_currencies(svc: BillingSvc) -> dict[str, Any]:
    return svc.list_currencies()


@router.get("/me")
async def billing_me(user: CurrentUser, svc: BillingSvc) -> dict[str, Any]:
    return await svc.get_customer_billing(user_id=user.id)


@router.get("/invoices/{order_code}")
async def billing_invoice(
    order_code: str,
    user: CurrentUser,
    svc: BillingSvc,
) -> dict[str, Any]:
    return await svc.get_invoice(user_id=user.id, order_code=order_code)


@router.post("/trial/start", status_code=status.HTTP_201_CREATED)
async def billing_start_trial(
    request: Request,
    user: CurrentUser,
    svc: BillingSvc,
) -> dict[str, Any]:
    ip = ""
    if request.client and request.client.host:
        ip = request.client.host
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",", 1)[0].strip() or ip
    email = str(getattr(user, "email", "") or "")
    verified = str(getattr(user, "status", "") or "").lower() == "active"
    ua = (request.headers.get("user-agent") or "")[:80]
    fingerprint = f"{ip}|{ua}" if ip or ua else ""
    return await svc.start_trial(
        user_id=user.id,
        email=email,
        email_verified=verified,
        source_ip=ip,
        claim_fingerprint=fingerprint,
    )


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def billing_checkout(
    body: CheckoutRequest,
    user: CurrentUser,
    svc: BillingSvc,
) -> dict[str, Any]:
    return await svc.create_checkout(
        user_id=user.id,
        plan_id=body.plan_id,
        pay_currency=body.pay_currency,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )


@router.post("/cancel")
async def billing_cancel(user: CurrentUser, svc: BillingSvc) -> dict[str, Any]:
    return await svc.cancel_subscription(user_id=user.id)


OwnerAdminUser = Annotated[
    AuthUserDTO, Depends(require_roles(UserRole.OWNER, UserRole.ADMIN))
]


@router.post("/admin/owner-compensation-premium")
async def billing_owner_compensation_premium(
    user: OwnerAdminUser,
    svc: BillingSvc,
) -> dict[str, Any]:
    """Grant Premium to the designated owner only. Target is not request-controlled."""
    email = str(getattr(user, "email", "") or "")
    role = str(getattr(user, "role", "") or "")
    if not is_designated_owner_email(email):
        raise ValidationError(
            "Only the designated owner may execute this grant",
            code="OWNER_GRANT_FORBIDDEN",
        )
    return await svc.grant_owner_compensation_premium(
        actor_user_id=user.id,
        actor_email=email,
        actor_role=role,
    )


@router.post("/internal/reconcile-trials")
async def billing_reconcile_trials(
    svc: BillingSvc,
    settings: Annotated[Settings, Depends(get_settings)],
    x_quantforg_cron_secret: Annotated[
        str | None, Header(alias="x-quantforg-cron-secret")
    ] = None,
) -> dict[str, Any]:
    """Expire due trials. Protected by BILLING_CRON_SECRET."""
    secret = settings.billing_cron_secret
    expected = secret.get_secret_value() if secret else ""
    if not expected:
        raise ValidationError(
            "BILLING_CRON_SECRET is not configured",
            code="CRON_NOT_CONFIGURED",
        )
    if (x_quantforg_cron_secret or "") != expected:
        raise ValidationError("Invalid cron secret", code="CRON_FORBIDDEN")
    return await svc.reconcile_expired_trials()


@router.post("/ipn/nowpayments")
async def nowpayments_ipn(
    request: Request,
    svc: BillingSvc,
    x_nowpayments_sig: Annotated[str | None, Header(alias="x-nowpayments-sig")] = None,
) -> dict[str, Any]:
    """Public IPN endpoint — authenticity is the HMAC signature, not auth JWT."""
    try:
        payload = await request.json()
    except Exception as exc:
        raise ValidationError(
            "Invalid IPN JSON body",
            code="IPN_INVALID_JSON",
        ) from exc
    if not isinstance(payload, dict):
        raise ValidationError(
            "IPN body must be a JSON object",
            code="IPN_INVALID_BODY",
        )
    if not x_nowpayments_sig:
        raise ValidationError(
            "Missing x-nowpayments-sig header",
            code="IPN_MISSING_SIGNATURE",
        )
    return await svc.handle_ipn(payload=payload, signature=x_nowpayments_sig)
