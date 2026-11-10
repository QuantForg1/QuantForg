"""Authenticated customer risk preference APIs.

Ordinary users manage only their own preferences. Owner/global policy remains
on ``/admin/control`` (OWNER role) and is never returned here as a full document.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.user_risk_preferences_service import (
    get_user_risk_preferences,
    list_risk_history,
    preference_bounds,
    protection_status,
    update_user_risk_preferences,
)
from app.domain.exceptions.base import ValidationError
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/risk/preferences", tags=["risk-preferences"])


class UserRiskPreferenceUpdate(BaseModel):
    planned_risk_pct: str = Field(min_length=1, max_length=32)
    aggregate_open_risk_pct: str = Field(min_length=1, max_length=32)
    max_lot: str = Field(min_length=1, max_length=32)
    daily_loss_pct: str = Field(min_length=1, max_length=32)
    max_concurrent_positions: int = Field(ge=1, le=100)


def _dec_field(raw: str, field: str) -> Decimal:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValidationError(
            f"Invalid decimal for {field}",
            code="invalid_risk_preference",
            details={"field": field},
        ) from exc
    return value


@router.get("")
async def read_own_preferences(user: CurrentUser) -> dict[str, Any]:
    return get_user_risk_preferences(UUID(str(user.id)))


@router.put("")
async def write_own_preferences(
    body: UserRiskPreferenceUpdate,
    user: CurrentUser,
) -> dict[str, Any]:
    return update_user_risk_preferences(
        UUID(str(user.id)),
        planned_risk_pct=_dec_field(body.planned_risk_pct, "planned_risk_pct"),
        aggregate_open_risk_pct=_dec_field(
            body.aggregate_open_risk_pct, "aggregate_open_risk_pct"
        ),
        max_lot=_dec_field(body.max_lot, "max_lot"),
        daily_loss_pct=_dec_field(body.daily_loss_pct, "daily_loss_pct"),
        max_concurrent_positions=int(body.max_concurrent_positions),
    )


@router.get("/effective")
async def read_effective_preferences(user: CurrentUser) -> dict[str, Any]:
    payload = get_user_risk_preferences(UUID(str(user.id)))
    return {
        "effective": payload["effective"],
        "updated_at": payload.get("updated_at"),
        "source": payload.get("source"),
    }


@router.get("/bounds")
async def read_preference_bounds(user: CurrentUser) -> dict[str, Any]:
    _ = user
    return {
        "bounds": preference_bounds(),
        "protections": protection_status(),
        # Explicitly omit full owner/runtime policy documents.
        "owner_policy_document": None,
    }


@router.get("/history")
async def read_risk_history(
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
) -> dict[str, Any]:
    return list_risk_history(UUID(str(user.id)), limit=limit)
