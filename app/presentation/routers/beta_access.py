"""Closed-beta invite unlock — server-side secret only (never NEXT_PUBLIC)."""

from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config.settings import get_settings

router = APIRouter(prefix="/beta", tags=["beta-access"])


class BetaUnlockBody(BaseModel):
    code: str = Field(min_length=1, max_length=256)


class BetaStatusResponse(BaseModel):
    beta_mode: bool
    invite_configured: bool


@router.get("/status")
def beta_status() -> BetaStatusResponse:
    settings = get_settings()
    return BetaStatusResponse(
        beta_mode=bool(settings.beta_mode),
        invite_configured=bool(str(settings.beta_invite_code or "").strip()),
    )


@router.post("/unlock")
def beta_unlock(body: BetaUnlockBody) -> dict[str, Any]:
    """Verify invite code against server-only BETA_INVITE_CODE."""
    settings = get_settings()
    if not settings.beta_mode:
        return {"ok": True, "unlocked": True, "beta_mode": False}
    expected = str(settings.beta_invite_code or "").strip()
    if not expected:
        # Beta mode without a configured code — fail closed.
        raise HTTPException(
            status_code=503,
            detail="Beta invite is not configured on the server",
        )
    provided = body.code.strip()
    if len(provided) != len(expected) or not hmac.compare_digest(
        provided.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(status_code=403, detail="Invalid invite code")
    return {"ok": True, "unlocked": True, "beta_mode": True}
