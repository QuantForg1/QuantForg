"""Protection center API. A missing check is unknown, not healthy."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.domain.reliability_center import ProtectionInput, build_protection_report
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings

router = APIRouter(prefix="/reliability", tags=["reliability-center"])


@router.get("/status")
async def reliability_status(user: CurrentUser) -> dict[str, Any]:
    """Account-state separation for the signed-in user."""
    del user
    if not get_settings().reliability_center_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Reliability center is not enabled",
        )
    return build_protection_report(ProtectionInput(read_at=datetime.now(UTC)))
