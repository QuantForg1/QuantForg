"""Trading coach API. It answers only from server-side records."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from app.domain.trading_coach import answer_question
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings

router = APIRouter(prefix="/trading-coach", tags=["trading-coach"])


@router.get("/answer")
async def coach_answer(
    user: CurrentUser,
    question_id: str = Query(min_length=1, max_length=64),
) -> dict[str, Any]:
    """Grounded answer. Client-supplied figures are not accepted."""
    del user
    if not get_settings().trading_coach_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trading coach is not enabled",
        )
    report = answer_question(question_id, None)
    report["places_orders"] = False
    report["changes_settings"] = False
    return report
