"""Customer billing API + NOWPayments LIVE IPN webhook."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, status
from pydantic import BaseModel, Field

from app.application.services.billing_service import BillingService
from app.domain.exceptions.base import ValidationError
from app.presentation.dependencies.auth import CurrentUser
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
    email = str(getattr(user, "email", "") or "")
    # Active QuantForg profile implies email verification / activation completed.
    verified = str(getattr(user, "status", "") or "").lower() == "active"
    return await svc.start_trial(
        user_id=user.id,
        email=email,
        email_verified=verified,
        source_ip=ip,
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
