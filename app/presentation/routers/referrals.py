"""Customer referral API. Hidden until REFERRAL_ENABLED is true."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.application.services.referral_program import ReferralProgram, StoreUnavailable
from app.infrastructure.persistence.referral_store import PostgresReferralStore
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings
from core.di.container import get_container

router = APIRouter(prefix="/referrals", tags=["referrals"])


class AttributeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=32)


def _program() -> ReferralProgram:
    return ReferralProgram(PostgresReferralStore(get_container().database))


def _enabled() -> None:
    if not get_settings().referral_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referral system is not enabled",
        )


@router.get("/me")
async def referral_summary(user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _program().summary(str(user.id))
    except StoreUnavailable:
        return _unavailable()


@router.post("/attribute")
async def attribute_referral(
    body: AttributeRequest, user: CurrentUser
) -> dict[str, Any]:
    _enabled()
    try:
        return await _program().attribute(user_id=str(user.id), code=body.code)
    except StoreUnavailable:
        return _unavailable()


def _unavailable() -> dict[str, Any]:
    return {
        "available": False,
        "code": None,
        "link_path": None,
        "history": [],
        "rewards": [],
        "reward_balance": None,
        "sales_or_payouts": False,
    }
