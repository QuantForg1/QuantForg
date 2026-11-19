"""Trade explanation HTTP API.

Hidden until TRADE_EXPLANATION_ENABLED is true. The route does not
accept a client-supplied reason and does not read a shared decision file.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings

router = APIRouter(prefix="/trade-explanations", tags=["trade-explanation"])


@router.get("")
async def trade_explanations(user: CurrentUser) -> dict[str, Any]:
    """User-scoped explanations. No per-user decision log is attached yet."""
    del user
    if not get_settings().trade_explanation_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trade explanation is not enabled",
        )
    return {
        "schema_version": "trade-explanation.v1",
        "places_orders": False,
        "overrides_execution": False,
        "authoritative_for_execution": False,
        "status": "unavailable",
        "source": "none",
        "explanations": [],
        "reason": "no_user_scoped_decision_log",
    }
